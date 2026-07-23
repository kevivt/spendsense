"""
SQLite storage layer - the durable source of truth for SpendSense.

Schema design: normalized (orders + order_items), not a JSON blob column.
This means we can do real SQL aggregation later - e.g. "how many times did
I order fries", "total spend per item category" - without parsing JSON
inside SQL. The nested hash table (storage/index.py) is a derived,
in-memory view built FROM this table for fast repeated lookups; this file
is the ground truth.
"""

import sqlite3
from contextlib import contextmanager

from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id TEXT UNIQUE NOT NULL,
    platform TEXT NOT NULL,
    restaurant TEXT NOT NULL,
    order_date TEXT NOT NULL,        -- ISO format: YYYY-MM-DD
    total_amount REAL NOT NULL,
    raw_subject TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    item_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_orders_platform_date
    ON orders (platform, order_date);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
    ON order_items (order_id);
"""


@contextmanager
def get_connection():
    """Context manager so callers never forget to close/commit."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables/indexes if they don't exist. Safe to call every startup."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def insert_order(gmail_message_id, platform, restaurant, order_date,
                  total_amount, items, raw_subject=""):
    """
    Insert one order and its items in a single transaction.
    items: list of dicts, e.g. [{"item_name": "Burger", "quantity": 1, "item_price": 220.0}]
    Returns the new order's id, or None if this gmail_message_id already exists
    (prevents duplicate inserts on re-sync).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO orders
                   (gmail_message_id, platform, restaurant, order_date, total_amount, raw_subject)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (gmail_message_id, platform, restaurant, order_date, total_amount, raw_subject),
            )
        except sqlite3.IntegrityError:
            # already ingested this email before - skip silently
            return None

        order_id = cur.lastrowid
        for item in items:
            cur.execute(
                """INSERT INTO order_items (order_id, item_name, quantity, item_price)
                   VALUES (?, ?, ?, ?)""",
                (order_id, item["item_name"], item.get("quantity", 1), item["item_price"]),
            )
        return order_id


def get_all_orders():
    """Returns every order with its items nested in, as a list of dicts.
    This is the shape storage/index.py consumes to build the in-memory index."""
    with get_connection() as conn:
        orders = conn.execute("SELECT * FROM orders ORDER BY order_date").fetchall()
        result = []
        for order in orders:
            items = conn.execute(
                "SELECT item_name, quantity, item_price FROM order_items WHERE order_id = ?",
                (order["id"],),
            ).fetchall()
            result.append({
                "id": order["id"],
                "gmail_message_id": order["gmail_message_id"],
                "platform": order["platform"],
                "restaurant": order["restaurant"],
                "date": order["order_date"],
                "total": order["total_amount"],
                "items": [dict(i) for i in items],
            })
        return result


def get_orders_by_month(platform, year_month):
    """year_month format: 'YYYY-MM'. Direct SQL aggregation example -
    this is the kind of query the nested hash table exists to avoid re-running."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM orders
               WHERE platform = ? AND order_date LIKE ?
               ORDER BY order_date""",
            (platform, f"{year_month}%"),
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {DB_PATH}")
