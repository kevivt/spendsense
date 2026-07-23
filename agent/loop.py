"""
The agentic reasoning loop. The LLM decides which tool(s) to call based on
the user's question - via Ollama's native tool-calling support - we
execute them, feed results back, and let it either call more tools or
produce a final answer. This is the actual agentic behavior: the control
flow isn't hardcoded per question type, the model chooses.
"""

import json
import re
from datetime import datetime

import ollama

from config import OLLAMA_MODEL, OLLAMA_BASE_URL, MAX_AGENT_TOOL_CALLS
from agent.tool_schema import TOOL_SCHEMAS
from agent.tools import TOOL_FUNCTIONS

_client = ollama.Client(host=OLLAMA_BASE_URL)

# Guards against a known small-model failure mode: llama3.2:3b will
# occasionally skip tool-calling on ambiguous input (e.g. a month without a
# year) and free-text a plausible-looking but fabricated answer instead -
# including literal unfilled template text like "[insert amount]". We
# detect that pattern and force a retry rather than let it reach the user.
_PLACEHOLDER_PATTERN = re.compile(r"\[insert|\<[a-z _]+\>|<amount>", re.IGNORECASE)
_YEAR_TOKEN_PATTERN = re.compile(r"\b20\d{2}\b")

_FORCE_TOOL_USE_REMINDER = (
    "You answered without calling a tool. Never invent numbers, dates, or "
    "placeholder text like [insert amount] - if any detail (like the year) "
    "is missing, assume the current year ({current_year}) and the most "
    "recent occurrence of the stated month, then call the appropriate tool "
    "now to get real data."
)


def _correct_year_if_unspecified(args, user_query):
    """
    Deterministic fix for a known small-model weakness: llama3.2:3b is
    unreliable at inferring "the current year" when generating a
    year_month tool argument from an ambiguous query like "in may". Rather
    than rely on the model getting this right, we check with a plain regex
    whether the user's own text contains an explicit 4-digit year - if not,
    we override whatever year the model picked with the real current year.
    This only touches the year; the month the model extracted is trusted.
    """
    year_month = args.get("year_month")
    if not year_month or _YEAR_TOKEN_PATTERN.search(user_query):
        return args  # user gave an explicit year somewhere - trust the model

    try:
        year_str, month_str = year_month.split("-")
        current_year = datetime.now().year
        if int(year_str) != current_year:
            args = dict(args)
            args["year_month"] = f"{current_year}-{month_str}"
    except (ValueError, AttributeError):
        pass  # unexpected format - leave as-is, let the tool's own validation handle it

    return args


def _build_system_prompt():
    now = datetime.now()
    return (
        "You are SpendSense, a personal finance assistant that helps the "
        "user understand their food delivery spending (Swiggy/Zomato). "
        f"Today's date is {now.strftime('%Y-%m-%d')}. You have tools to "
        "query exact numbers, search semantically, compare platforms, and "
        "generate reports. Always use a tool to get real data before "
        "answering - never guess, invent numbers, or write placeholder "
        "text like [insert amount]. If the user gives a month without a "
        f"year, assume the current year ({now.year}) and the most recent "
        "occurrence of that month. After gathering the information you "
        "need, give a clear, concise answer in plain language that cites "
        "the actual numbers you retrieved."
    )


def run_agent(user_query, conversation_history=None, verbose=True, return_trace=False):
    """
    Runs the tool-calling loop for one user query. conversation_history is
    an optional list of prior {"role": "user"|"assistant", "content": str}
    turns - plain text only, no tool-call scaffolding - so the model has
    context for follow-ups like "what about May?" after a prior question.
    The API layer is stateless; the caller (dashboard) owns and passes
    this history each request, rather than the server holding session state.

    Returns the final text answer, or (answer, tools_called) if
    return_trace=True - used by the eval harness to check tool-selection
    accuracy without needing to parse printed output.
    """
    messages = [{"role": "system", "content": _build_system_prompt()}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_query})

    tool_used = False
    forced_retry_used = False
    tools_called = []

    for step in range(MAX_AGENT_TOOL_CALLS):
        response = _client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
        message = response["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")

        if not tool_calls:
            answer = message.get("content", "")

            looks_fabricated = _PLACEHOLDER_PATTERN.search(answer) is not None
            never_used_a_tool = not tool_used

            if (looks_fabricated or never_used_a_tool) and not forced_retry_used:
                # Push back once instead of accepting a hallucinated answer
                forced_retry_used = True
                if verbose:
                    reason = "placeholder text detected" if looks_fabricated else "no tool was called"
                    print(f"[guard] rejecting answer ({reason}), forcing retry")
                messages.append({
                    "role": "user",
                    "content": _FORCE_TOOL_USE_REMINDER.format(current_year=datetime.now().year),
                })
                continue

            return (answer, tools_called) if return_trace else answer

        tool_used = True
        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)

            args = _correct_year_if_unspecified(args, user_query)
            tools_called.append(name)

            if verbose:
                print(f"[tool call] {name}({args})")

            if name not in TOOL_FUNCTIONS:
                result = {"error": f"Unknown tool '{name}'"}
            else:
                try:
                    result = TOOL_FUNCTIONS[name](**args)
                except Exception as e:
                    result = {"error": str(e)}

            messages.append({
                "role": "tool",
                "content": json.dumps(result, default=str),
            })

    fallback = ("I wasn't able to fully answer that within the allowed number "
                "of steps - try narrowing your question.")
    return (fallback, tools_called) if return_trace else fallback


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "How much did I spend on Swiggy in June 2026?"
    print(f"Query: {query}\n")
    answer = run_agent(query)
    print("\nFinal answer:")
    print(answer)
