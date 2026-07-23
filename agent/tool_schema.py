"""
Tool schemas passed to Ollama's native tool-calling API. The LLM sees
these descriptions and decides which tool (if any) to call based on the
user's question - this is the actual agentic decision-making, not a fixed
if/else pipeline.

Names and parameter shapes here must exactly match the functions in
agent/tools.py (TOOL_FUNCTIONS dispatch dict).

The platform enum is generated from config.PLATFORM_QUERIES rather than
hardcoded, so adding a new platform (e.g. instamart, amazon) to config.py
automatically makes it available to the agent without editing this file.
"""

from config import PLATFORM_QUERIES


def build_tool_schemas():
    platforms = list(PLATFORM_QUERIES.keys())

    return [
        {
            "type": "function",
            "function": {
                "name": "query_orders",
                "description": (
                    "Get exact spend total, order count, and top items for one "
                    "platform in one month, from precise stored data. Use this "
                    "for questions asking for an exact number or count."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "platform": {
                            "type": "string",
                            "enum": platforms,
                            "description": "Which platform to query",
                        },
                        "year_month": {
                            "type": "string",
                            "description": "Month to query, format YYYY-MM, e.g. '2026-06'",
                        },
                    },
                    "required": ["platform", "year_month"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "semantic_search",
                "description": (
                    "Search order history by meaning/concept rather than exact "
                    "keywords - e.g. 'spicy food', 'healthy bowls', 'comfort food'. "
                    "Use this when the question is fuzzy/conceptual, not asking "
                    "for an exact number."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language description of what to search for",
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "How many results to return (default 5)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_platforms",
                "description": (
                    "Compare total spend, order count, and top items across "
                    "all platforms (e.g. Swiggy, Instamart, Zomato) for a "
                    "given month. Use this for 'which platform did I spend "
                    "more on' type questions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year_month": {
                            "type": "string",
                            "description": "Month to compare, format YYYY-MM",
                        },
                    },
                    "required": ["year_month"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_monthly_report",
                "description": (
                    "Generate a full spend summary across all platforms for a "
                    "given month - grand total, per-platform breakdown, top items. "
                    "Use this for broad 'summarize my spending' type questions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year_month": {
                            "type": "string",
                            "description": "Month to report on, format YYYY-MM",
                        },
                    },
                    "required": ["year_month"],
                },
            },
        },
    ]


# Built once at import time - fine since PLATFORM_QUERIES doesn't change at
# runtime. If that ever changes, call build_tool_schemas() directly instead.
TOOL_SCHEMAS = build_tool_schemas()
