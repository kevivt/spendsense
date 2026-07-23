"""
Wraps the local sentence-transformers embedding model. Kept as a thin
abstraction (like the LLM client pattern from Mail Agent) so the rest of
the RAG layer doesn't care which embedding model is actually in use.
"""

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL

_model = None  # lazy-loaded singleton - loading the model has real startup cost


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts):
    """texts: list[str] -> list[list[float]] embeddings, one per input text."""
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


if __name__ == "__main__":
    sample = ["Chicken Biryani from Biryani House", "Paneer Tikka Masala Bowl from Truth Bowl"]
    vectors = embed_texts(sample)
    print(f"Embedded {len(vectors)} texts, dimension {len(vectors[0])}")
