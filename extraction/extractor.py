"""
Calls the local Ollama LLM to turn distilled order text into structured
JSON, with parsing/validation and one retry if the model returns malformed
output (small local models occasionally wrap JSON in markdown fences or
add stray commentary despite instructions).
"""

import json
import re

import ollama

from config import OLLAMA_MODEL, OLLAMA_BASE_URL
from extraction.extract_prompt import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt

_REQUIRED_KEYS = {"restaurant", "order_date", "total_amount", "items"}
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_client = ollama.Client(host=OLLAMA_BASE_URL)


def _strip_markdown_fences(text):
    """Small local models sometimes wrap JSON in ```json ... ``` despite
    instructions not to - strip that before parsing rather than failing."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text)
        text = re.sub(r"```$", "", text)
    return text.strip()


def _validate(parsed):
    """Returns (is_valid, error_message)."""
    if not isinstance(parsed, dict):
        return False, "Top-level output is not a JSON object"

    missing = _REQUIRED_KEYS - parsed.keys()
    if missing:
        return False, f"Missing required keys: {missing}"

    # Guard against the model echoing our prompt's placeholder syntax
    # (e.g. "<restaurant name as a string>") instead of a real value
    if "<" in str(parsed.get("restaurant", "")) and ">" in str(parsed.get("restaurant", "")):
        return False, f"restaurant looks like an unfilled placeholder: {parsed.get('restaurant')}"

    if not _DATE_PATTERN.match(str(parsed.get("order_date", ""))):
        return False, f"order_date not in YYYY-MM-DD format: {parsed.get('order_date')}"

    if not isinstance(parsed.get("items"), list) or len(parsed["items"]) == 0:
        return False, "items must be a non-empty list"

    for item in parsed["items"]:
        if not {"item_name", "quantity", "item_price"} <= item.keys():
            return False, f"item missing required fields: {item}"
        try:
            int(item["quantity"])
            float(item["item_price"])
        except (TypeError, ValueError):
            return False, f"item has non-numeric quantity/price: {item}"

    try:
        float(parsed["total_amount"])
    except (TypeError, ValueError):
        return False, f"total_amount is not numeric: {parsed.get('total_amount')}"

    return True, None


def _coerce_types(parsed):
    """
    The LLM sometimes returns numbers as JSON strings ("1" instead of 1)
    despite the schema asking for numbers - harmless-looking, but a real
    landmine downstream: storage/index.py does item_counter[name] +=
    quantity, which crashes with a TypeError the moment quantity is a str
    instead of an int. Force real Python int/float types here, once, so
    every downstream consumer (storage, RAG, agent tools) can trust the
    types without re-checking.
    """
    parsed = dict(parsed)
    parsed["total_amount"] = float(parsed["total_amount"])
    parsed["items"] = [
        {
            "item_name": item["item_name"],
            "quantity": int(item["quantity"]),
            "item_price": float(item["item_price"]),
        }
        for item in parsed["items"]
    ]
    return parsed


def _call_ollama(user_prompt):
    response = _client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        # Grocery orders (Instamart) can have many line items - the
        # default output length cap was cutting JSON off mid-generation
        # before it closed properly. 2048 gives enough headroom for a
        # long item list without letting a single call run away.
        options={"num_predict": 2048},
    )
    return response["message"]["content"]


def extract_order(distilled_text, reference_year, max_retries=1):
    """
    Extract structured order data from distilled email text.
    Returns (parsed_dict, None) on success, or (None, error_message) on failure
    after retries - caller decides whether to skip this email or log it.
    """
    prompt = build_extraction_prompt(distilled_text, reference_year)
    last_error = None

    for attempt in range(max_retries + 1):
        raw_output = _call_ollama(prompt)
        cleaned = _strip_markdown_fences(raw_output)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}. Raw output: {raw_output[:300]}"
            continue

        is_valid, error = _validate(parsed)
        if is_valid:
            return _coerce_types(parsed), None
        last_error = error

    return None, last_error


if __name__ == "__main__":
    sample = """Restaurant: Truth Bowl
Order Time: Jun 26, 7:03 PM
Delivery Time: Jun 26, 7:42 PM
Items:
  Paneer Tikka Masala Bowl x1 - ₹329
Total Paid: ₹238.00"""

    result, error = extract_order(sample, reference_year=2026)
    if error:
        print("Extraction failed:", error)
    else:
        print(json.dumps(result, indent=2))
