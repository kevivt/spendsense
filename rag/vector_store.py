"""
Local Chroma vector store for order records. This is a derived index,
same philosophy as storage/index.py's nested hash table - SQLite remains
the source of truth, and this gets rebuilt from it whenever we want fresh
semantic search over the current order history.
"""

import chromadb

from config import CHROMA_DIR, CHROMA_COLLECTION_NAME
from rag.embed import embed_texts
from storage.db import get_all_orders


def _order_to_document(order):
    """
    Turn one order record into a single text blob for embedding. Includes
    platform, restaurant, items, and date so semantic search can match on
    any of these (e.g. a query about "biryani" should match orders whose
    item list contains biryani, even if the restaurant name doesn't).
    """
    item_text = ", ".join(
        f"{item['item_name']} x{item['quantity']}" for item in order["items"]
    )
    return (
        f"Platform: {order['platform']}. Restaurant: {order['restaurant']}. "
        f"Date: {order['date']}. Items: {item_text}. Total: Rs {order['total']}."
    )


def get_client():
    return chromadb.PersistentClient(path=CHROMA_DIR)


def rebuild_index(orders=None):
    """
    Rebuild the Chroma collection from scratch based on current SQLite
    orders. We delete + recreate rather than incrementally upsert, since
    order history is small enough that a full rebuild is cheap and this
    avoids ever having stale/duplicate entries after re-syncs.
    """
    if orders is None:
        orders = get_all_orders()

    client = get_client()
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
    except Exception:
        pass  # collection didn't exist yet - fine
    collection = client.create_collection(CHROMA_COLLECTION_NAME)

    if not orders:
        return collection

    documents = [_order_to_document(o) for o in orders]
    ids = [str(o["id"]) for o in orders]
    metadatas = [
        {
            "platform": o["platform"],
            "restaurant": o["restaurant"],
            "date": o["date"],
            "total": o["total"],
        }
        for o in orders
    ]
    embeddings = embed_texts(documents)

    collection.add(
        documents=documents, ids=ids, metadatas=metadatas, embeddings=embeddings
    )
    return collection


def get_collection():
    """Get the existing collection without rebuilding (fails if it doesn't exist yet)."""
    client = get_client()
    return client.get_collection(CHROMA_COLLECTION_NAME)


if __name__ == "__main__":
    collection = rebuild_index()
    print(f"Rebuilt index with {collection.count()} orders")
