"""
Shared configuration for SpendSense.
Every other module should import constants from here rather than
hardcoding values, so we have one place to change models/paths/queries.
"""

import os

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "spendsense.db")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_store")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# --- Gmail ---
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# NOTE: verify these against your actual inbox before running fetch_orders.py
# (see inspect_orders.py step) - platform senders vary by account/region.
# Instamart shares Swiggy's sender domain, so it's split out by subject
# rather than sender - "swiggy" excludes Instamart subjects, "instamart"
# matches only them. Each platform maps to its own distiller in
# ingestion/distillers/ since the two use different email templates.
PLATFORM_QUERIES = {
    "zomato": "from:zomato.com",
    "swiggy": "from:swiggy.in -subject:Instamart",
    "instamart": "from:swiggy.in subject:Instamart",
}

# --- LLM (Ollama) ---
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_BASE_URL = "http://localhost:11434"

# --- Embeddings (RAG) ---
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_COLLECTION_NAME = "spendsense_orders"

# --- Agent ---
MAX_AGENT_TOOL_CALLS = 5  # safety cap on ReAct loop iterations per user query
