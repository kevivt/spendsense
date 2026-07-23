"""
Tool implementations. Each function here corresponds exactly to one entry
in agent/tool_schema.py's TOOL_SCHEMAS - the LLM calls these by name with
JSON arguments, so names/parameters must match precisely.
"""

from storage.index import (
    build_spend_index,
    month_total,
    month_order_count,
    top_items,
    compare_platforms_month,
)
from rag.retriever import semantic_search as _semantic_search

_cached_index = None


def get_index(force_refresh=False):
    """
    Lazily build and cache the nested hash table index for this process.
    This is the fast-lookup derived view (storage/index.py) - avoids
    rebuilding from SQLite on every single tool call within one agent
    conversation. Call refresh_index() after a new sync to invalidate it.
    """
    global _cached_index
    if _cached_index is None or force_refresh:
        _cached_index = build_spend_index()
    return _cached_index


def refresh_index():
    global _cached_index
    _cached_index = build_spend_index()
    return _cached_index


def query_orders(platform, year_month):
    idx = get_index()
    return {
        "platform": platform,
        "year_month": year_month,
        "total_spent": month_total(idx, platform, year_month),
        "order_count": month_order_count(idx, platform, year_month),
        "top_items": top_items(idx, platform, year_month, n=5),
    }


def semantic_search(query, n_results=5):
    results = _semantic_search(query, n_results=n_results)
    # Simplify for the LLM - it doesn't need raw vector distances
    return [
        {
            "restaurant": r["metadata"]["restaurant"],
            "date": r["metadata"]["date"],
            "total": r["metadata"]["total"],
            "description": r["description"],
        }
        for r in results
    ]


def compare_platforms(year_month):
    idx = get_index()
    return compare_platforms_month(idx, year_month)


def generate_monthly_report(year_month):
    idx = get_index()
    report = {"year_month": year_month, "platforms": {}}
    grand_total = 0.0
    for platform in idx.keys():
        total = month_total(idx, platform, year_month)
        report["platforms"][platform] = {
            "total_spent": total,
            "order_count": month_order_count(idx, platform, year_month),
            "top_items": top_items(idx, platform, year_month, n=5),
        }
        grand_total += total
    report["grand_total"] = round(grand_total, 2)
    return report


TOOL_FUNCTIONS = {
    "query_orders": query_orders,
    "semantic_search": semantic_search,
    "compare_platforms": compare_platforms,
    "generate_monthly_report": generate_monthly_report,
}
