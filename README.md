# SpendSense

An agentic AI system that ingests my own Gmail food-delivery and grocery order confirmations (Swiggy, Swiggy Instamart), extracts structured spending data using a locally-hosted LLM, and answers natural-language questions about my spending through a hand-written ReAct-style tool-calling agent with RAG-based semantic search.

Built entirely with local, zero-cost tools — no paid APIs, no LangChain/LangGraph. Every extraction step, the agent's tool-selection loop, and the RAG pipeline are implemented from scratch so every design decision is explainable.

## Why this project

I wanted a portfolio project that was genuinely useful to me day-to-day (I actually use it to check my Swiggy/Instamart spending) while covering the parts of applied AI engineering that a pure classification project doesn't: retrieval-augmented generation, agentic tool-calling, and evaluating an LLM pipeline's real accuracy rather than assuming it works.

## Architecture

```
Gmail (OAuth) → Platform-specific distillers → Local LLM extraction (Ollama)
  → SQLite (source of truth) → [Nested hash index | ChromaDB vector store]
  → ReAct agent (4 tools, native function-calling) → FastAPI → Dashboard
```

**Ingestion** — Pulls order-confirmation emails per platform via Gmail API queries, strips HTML, redacts the delivery address (PII) before it ever touches disk or the LLM, and filters out marketing/retention emails that share the same sender as real orders.

**Distillation** — Each platform has its own distiller (`ingestion/html_clean.py` for Swiggy food orders, `ingestion/instamart_clean.py` for Instamart) since email templates differ structurally between platforms. All distillers normalize to the same intermediate text shape, so one extraction prompt works across platforms without platform-specific branching downstream.

**Extraction** — A local Ollama model (`llama3.2:3b`) converts distilled text into structured JSON (restaurant, date, items, total), validated against a strict schema and retried once on failure. Numeric fields are coerced to real Python types regardless of whether the model returns them as JSON numbers or strings.

**Storage** — SQLite is the durable source of truth (normalized `orders` + `order_items` tables). A nested hash table (`platform → month → restaurant → stats`) is rebuilt from SQLite as an in-memory derived index, avoiding repeated SQL aggregation on every agent tool call — the classic durable-storage-plus-derived-cache tradeoff.

**RAG** — Order records are embedded with `sentence-transformers` and stored in a local ChromaDB collection, enabling semantic search over spending history (e.g. a query for "healthy bowls" surfaces relevant orders by meaning, not just keyword match).

**Agent** — A ReAct-style loop using Ollama's native tool-calling API. The model chooses between 4 tools (`query_orders`, `semantic_search`, `compare_platforms`, `generate_monthly_report`) based on the question — this is genuine agentic control flow, not a hardcoded if/else router. Includes deterministic guardrails for known small-model failure modes (see below).

**Dashboard** — A FastAPI backend + vanilla JS/HTML frontend with a receipt-ledger visual theme, showing monthly spend breakdowns and a chat interface to the agent.

## Known small-model failure modes I found and fixed

Running a real evaluation harness against real data surfaced several concrete failure patterns in `llama3.2:3b` — documenting them (and how they were fixed) is, to me, the most interesting part of this project:

- **Date hallucination**: given an ambiguous month with no year, the model would sometimes fabricate a plausible-but-wrong year, or place identical dates across unrelated orders. Fixed deterministically in code (not by re-prompting) — the correct year is computed from the query and Gmail's own timestamp, never left to model inference.
- **Placeholder echoing**: the model occasionally returned unfilled template text (e.g. `[insert amount]`) as if it were real data. The agent loop now detects this pattern and forces a retry rather than surfacing it.
- **Tool-skipping on ambiguous input**: without an explicit tool call, the model would sometimes free-text an answer instead of querying real data. The agent now rejects any final answer that never used a tool.
- **Near-duplicate item confusion**: given two similarly-named line items (e.g. "Bowl Supreme Boneless Chicken Biryani" vs "Supreme Boneless Chicken Biryani"), the model occasionally swapped which price belonged to which item. Fixed by adding an explicit strict-positional-pairing rule to the extraction prompt.
- **Output truncation on long item lists**: grocery orders with many line items occasionally hit Ollama's default output length cap mid-generation, producing invalid truncated JSON. Fixed by raising `num_predict` for extraction calls.

## Evaluation

`eval/run_eval.py` scores two things against hand-labeled test cases built from my real inbox:

- **Extraction accuracy** — does the structured JSON match the verified ground truth (restaurant, date, total, and every item's name/quantity/price)?
- **Tool-selection accuracy** — does the agent call the *correct* tool for a given natural-language question? This is the more novel metric: it measures agentic decision quality, not just output correctness.

Run it yourself:
```bash
python -m eval.run_eval
```

## improvements

- Zomato and Amazon/Flipkart distillers (architecture already supports adding new platforms via `config.py` + a new distiller — no agent/schema changes needed)
- A larger hand-labeled eval set (currently 5 real cases; targeting 20+)
- CI running the eval suite on every push

## Stack

Python, FastAPI, Gmail API (OAuth), Ollama (Llama 3.2), ChromaDB, Sentence-Transformers, SQLite, vanilla JS/HTML/CSS

## Running it locally

```bash
pip install -r requirements.txt
python -m storage.db                 # initialize the database
python -m ingestion.sync_pipeline    # pull and extract real orders from Gmail
python -m rag.vector_store           # build the semantic search index
python -m api.main                   # start the dashboard at localhost:8000
```

Requires a Google Cloud OAuth `credentials.json` (Gmail API, read/modify scope) and a local Ollama install with `llama3.2:3b` pulled.
