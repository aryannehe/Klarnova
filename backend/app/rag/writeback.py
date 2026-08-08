"""Write completed incidents back into the knowledge base (closes the RAG loop).

Every resolved or escalated incident is embedded into the
``historical_incidents`` Chroma collection and mirrored as a ``KnowledgeDoc``
row, so future investigations can retrieve it. Fully non-fatal: any failure
only logs a warning and never disturbs the incident pipeline.
"""
import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.domain import KnowledgeDoc
from app.rag.store import HISTORICAL_INCIDENTS, vector_store

logger = logging.getLogger(__name__)


def _build_doc(incident_id: int, state: dict) -> str:
    target = state.get("target_resource", "unknown")
    ns = state.get("namespace", "default")
    severity = state.get("severity", "SEV-3")
    root_cause = state.get("root_cause") or "not diagnosed"
    confidence = state.get("confidence_score", 0.0)
    action = (state.get("selected_action") or {}).get("action_type", "none")
    if state.get("escalated"):
        outcome = "escalated to human"
    elif state.get("is_resolved"):
        outcome = "resolved"
    else:
        outcome = "unknown"
    resolved_at = state.get("resolved_at") or datetime.now(UTC).isoformat()
    return (
        f"Incident {incident_id} ({severity}): {target} in namespace {ns}.\n"
        f"Root cause: {root_cause}\n"
        f"Confidence: {confidence:.2f}\n"
        f"Selected action: {action}\n"
        f"Outcome: {outcome}\n"
        f"Resolved at: {resolved_at}"
    )


def _add_to_chroma(doc_id: str, text: str) -> None:
    vector_store.add_document(
        doc_id=doc_id,
        text=text,
        metadata={
            "title": f"Incident {doc_id}",
            "source": "incident",
            "collection": HISTORICAL_INCIDENTS,
        },
        collection=HISTORICAL_INCIDENTS,
    )


async def writeback_incident(incident_id: int, state: dict, labels: dict) -> bool:
    """Persist a completed incident as a knowledge doc. Returns True on success.

    The ``KnowledgeDoc`` row is the durable record and is written even when the
    embedding index (Chroma) is unavailable, so a completed incident is never
    lost from the knowledge registry. Chroma failure only degrades searchability.
    """
    if not (state.get("is_resolved") or state.get("escalated")):
        return False
    text = _build_doc(incident_id, state)
    doc_id = f"incident-{incident_id}"
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    chroma_ok = True
    try:
        await asyncio.to_thread(_add_to_chroma, doc_id, text)
    except Exception as exc:
        chroma_ok = False
        logger.warning(
            "KB write-back to Chroma failed for incident %s: %s", incident_id, exc
        )

    try:
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(KnowledgeDoc).where(KnowledgeDoc.source_url == f"incident://{incident_id}")
                )
            ).scalar_one_or_none()
            if row is None:
                session.add(
                    KnowledgeDoc(
                        source_url=f"incident://{incident_id}",
                        doc_type="historical_incident",
                        content_hash=content_hash,
                    )
                )
            else:
                row.doc_type = "historical_incident"
                row.content_hash = content_hash
                row.last_ingested = datetime.now(UTC)
            await session.commit()
    except Exception as exc:
        logger.warning(
            "KB write-back persistence failed for incident %s: %s", incident_id, exc
        )
        return False

    logger.info(
        "KB write-back: incident %s recorded (chroma index: %s)", incident_id, chroma_ok
    )
    return True
