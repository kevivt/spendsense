"""
The agent-facing retrieval function. This is what agent/tools.py's
semantic_search tool will call - kept as its own module so the agent layer
doesn't need to know anything about Chroma's API directly.
"""

from rag.vector_store import get_collection
from rag.embed import embed_texts


def semantic_search(query_text, n_results=5):
    """
    Fuzzy/conceptual search over order history - e.g. "spicy food" or
    "healthy bowls" will match relevant orders even without an exact
    keyword match. Returns a list of dicts with the order's text
    description, metadata (platform/restaurant/date/total), and how close
    the match was (lower distance = more similar).
    """
    collection = get_collection()
    query_embedding = embed_texts([query_text])[0]

    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)

    matches = []
    ids = results.get("ids", [[]])[0]
    for i in range(len(ids)):
        matches.append({
            "order_id": ids[i],
            "description": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i] if results.get("distances") else None,
        })
    return matches


if __name__ == "__main__":
    for query in ["spicy chicken dishes", "healthy bowls", "pizza"]:
        print(f"\nQuery: {query!r}")
        for match in semantic_search(query, n_results=3):
            print(f"  [{match['distance']:.3f}] {match['metadata']['restaurant']} "
                  f"({match['metadata']['date']}) - Rs {match['metadata']['total']}")
