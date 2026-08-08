"""Retrieval agent - RAG semantic search over the knowledge base.

Queries the ``runbooks`` collection for relevant precedents, degrading to
empty results (never fabricated) when the vector store is unavailable.
"""
from typing import Any

from app.agents.state import AgentState
from app.rag.store import RUNBOOKS, vector_store


def build_query(state: AgentState) -> str:
    alert = state.get("incident_data", {}).get("alert_name", "")
    logs = " ".join(state.get("logs", []))[-2000:]
    query = f"{alert}. {logs}"
    return query.strip() or "kubernetes incident"


def retrieve(
    query: str,
    n_results: int = 3,
    collection: str = RUNBOOKS,
    similarity_threshold: float = 1.2,
) -> list[dict[str, Any]]:
    """Return top-k matching documents; empty list when the store is down."""
    try:
        return vector_store.query_text(
            query,
            n_results=n_results,
            collection=collection,
            similarity_threshold=similarity_threshold,
        )
    except Exception:
        return []


def retrieval_node(state: AgentState):
    query = build_query(state)
    docs = retrieve(query)
    if not docs:
        messages = [{"role": "system", "content": "Retrieval: no relevant runbook found"}]
    else:
        messages = [
            {
                "role": "system",
                "content": f"Retrieval: {len(docs)} relevant runbook(s) found",
            }
        ]
    return {
        "retrieved_docs": docs,
        "messages": messages,
    }
