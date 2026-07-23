"""
API routes for the SpendSense dashboard: chat with the agent, get a
month's summary, and trigger a fresh sync from Gmail.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from ingestion.sync_pipeline import sync_orders
from rag.vector_store import rebuild_index as rebuild_vector_index
from agent.tools import generate_monthly_report, refresh_index
from agent.loop import run_agent
from config import PLATFORM_QUERIES

router = APIRouter()

# Cap how much prior conversation we forward to the LLM - bounds token
# usage/latency on long chat sessions while still giving useful context
# for near-term follow-ups.
MAX_HISTORY_MESSAGES = 12


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


class SyncRequest(BaseModel):
    max_results: int = 20


@router.post("/chat")
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    history = None
    if req.history:
        trimmed = req.history[-MAX_HISTORY_MESSAGES:]
        history = [{"role": m.role, "content": m.content} for m in trimmed]

    answer = run_agent(req.message, conversation_history=history, verbose=False)
    return {"answer": answer}


@router.get("/summary")
def summary(year_month: str):
    """year_month format: YYYY-MM"""
    return generate_monthly_report(year_month)


@router.post("/sync")
def sync(req: SyncRequest):
    """
    Pull new orders from Gmail for every configured platform, then rebuild
    both derived indexes (nested hash table + vector store) so the agent
    and dashboard immediately see the new data.
    """
    results = {}
    for platform in PLATFORM_QUERIES:
        results[platform] = sync_orders(platform=platform, max_results=req.max_results, verbose=False)

    refresh_index()
    rebuild_vector_index()

    return {"sync_results": results}
