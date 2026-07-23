"""
In-memory nested hash table - a derived, fast-lookup view of the orders
stored in SQLite (storage/db.py is the source of truth).

Why this exists: the agent's tools (compare_platforms, generate_monthly_report)
would otherwise re-run SQL GROUP BY queries on every single agent turn.
This index is rebuilt once per sync (see api/sync_job.py, built later) and
gives O(1) dict-lookup access to the same aggregates instead.

Structure:
    index[platform][year_month][restaurant] = {
        "total": float,
        "order_count": int,
        "item_counter": Counter(item_name -> total quantity ordered)
    }
"""

from collections import defaultdict, Counter

from storage.db import get_all_orders


def _new_bucket():
    return {"total": 0.0, "order_count": 0, "item_counter": Counter()}


def build_spend_index(orders=None):
    """
    Build the nested index from order records.
    orders: optional list of order dicts (shape from db.get_all_orders()).
            If None, fetches fresh from SQLite.
    """
    if orders is None:
        orders = get_all_orders()

    index = defaultdict(lambda: defaultdict(lambda: defaultdict(_new_bucket)))

    for order in orders:
        year_month = order["date"][:7]  # "2026-07-03" -> "2026-07"
        bucket = index[order["platform"]][year_month][order["restaurant"]]
        bucket["total"] += order["total"]
        bucket["order_count"] += 1
        for item in order["items"]:
            bucket["item_counter"][item["item_name"]] += item.get("quantity", 1)

    return index


def month_total(index, platform, year_month):
    """Total spend on a platform in a given month, across all restaurants."""
    restaurants = index.get(platform, {}).get(year_month, {})
    return round(sum(r["total"] for r in restaurants.values()), 2)


def month_order_count(index, platform, year_month):
    restaurants = index.get(platform, {}).get(year_month, {})
    return sum(r["order_count"] for r in restaurants.values())


def top_items(index, platform, year_month, n=5):
    """Most-ordered items on a platform in a given month, across all restaurants."""
    combined = Counter()
    restaurants = index.get(platform, {}).get(year_month, {})
    for r in restaurants.values():
        combined.update(r["item_counter"])
    return combined.most_common(n)


def compare_platforms_month(index, year_month, platforms=None):
    """
    Side-by-side totals/order-counts for the given month across platforms.
    Defaults to every platform actually present in the index (not a fixed
    pair) so new platforms show up in comparisons automatically.
    """
    if platforms is None:
        platforms = list(index.keys())
    return {
        platform: {
            "total": month_total(index, platform, year_month),
            "order_count": month_order_count(index, platform, year_month),
            "top_items": top_items(index, platform, year_month, n=3),
        }
        for platform in platforms
    }


if __name__ == "__main__":
    idx = build_spend_index()
    print("Index built. Platforms present:", list(idx.keys()))
