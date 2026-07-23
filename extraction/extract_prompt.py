"""
Prompt template for turning a distilled Swiggy order email into structured
JSON. Kept separate from extractor.py (which handles the actual Ollama call
and JSON parsing/validation) so the prompt itself can be iterated on
independently - same pattern as the Mail Agent's prompt-iteration workflow.
"""

EXTRACTION_SYSTEM_PROMPT = """You are a data extraction engine. You will be given \
the distilled text of a Swiggy food order email. Extract the order details \
and return ONLY a single valid JSON object - no preamble, no markdown code \
fences, no explanation.

Return JSON in exactly this shape:
{
  "restaurant": "<restaurant name as a string>",
  "order_date": "<YYYY-MM-DD>",
  "total_amount": <number, the final amount actually paid>,
  "items": [
    {"item_name": "<name, without the 'xN' quantity suffix>", "quantity": <integer>, "item_price": <number, price for this line as shown>}
  ]
}

Rules:
- restaurant: copy the text following "Restaurant:" in the input EXACTLY as \
shown, including any trailing descriptive text after a dash (e.g. "Paris Panini \
- Gourmet Sandwiches & Wraps" stays exactly that, in full). Do not shorten, \
rename, or drop any part of it.
- order_date must be in YYYY-MM-DD format. The email text will contain a date \
like "Jun 26, 7:03 PM" - convert this to full YYYY-MM-DD using the year given \
in the "Reference year" line below.
- total_amount is the "Total Paid" value from the email, not the sum of item prices \
(they can differ due to fees/discounts/taxes not shown).
- item_name: copy the item's full name EXACTLY as shown, including any \
parentheses, punctuation, or descriptive text (e.g. "Sourdough Creamy Truffle \
Mushroom Pizza (Reg)", "Michel (Chicken & Mozza Sandwich)" must be kept in \
full, word for word). The ONLY text you may remove from the name is a trailing \
quantity marker like " x1" or " x2". Never shorten, paraphrase, rename, or drop \
any other part of the name - not the parenthetical, not the words before it.
- quantity: the number after "x" in that trailing marker. If no marker is \
present, quantity is 1.
- item_price is EXACTLY the number shown next to that line, copied as-is. This \
number is the total for that entire line (covering all units of that item \
combined), never a per-unit price - do NOT divide it by quantity under any \
circumstances. For example "Chicken Biryani x2 - ₹450" means item_price is \
450, not 225.
- Process items strictly in the order they appear in the input. Match each \
item name to the price shown immediately below it in the input - never swap, \
reorder, or cross-match a name with a price from a different line, even if two \
item names look similar to each other.
- Output must be valid JSON and nothing else.
"""


def build_extraction_prompt(distilled_text, reference_year):
    return (
        f"Reference year: {reference_year}\n\n"
        f"Order email text:\n{distilled_text}"
    )
