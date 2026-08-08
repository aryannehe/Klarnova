"""Seed the Chroma collections (runbooks, historical incidents, k8s docs).

Idempotent: existing doc ids are skipped unless ``refresh=True``.
"""
import logging
from pathlib import Path

import yaml

from app.config import settings
from app.rag.store import (
    HISTORICAL_INCIDENTS,
    KUBERNETES_DOCS,
    RUNBOOKS,
    vector_store,
)

logger = logging.getLogger(__name__)

COLLECTION_BY_NAME = {
    "runbooks": RUNBOOKS,
    "historical_incidents": HISTORICAL_INCIDENTS,
    "kubernetes_docs": KUBERNETES_DOCS,
}


def sources_path() -> Path:
    configured = Path(settings.KB_SOURCE_LIST)
    if configured.exists():
        return configured
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "knowledge-base" / "sources.yaml"
    if fallback.exists():
        return fallback
    raise FileNotFoundError("knowledge base sources.yaml not found")


def run_ingest(refresh: bool = False, path: str | None = None) -> int:
    """Seed the collections. Returns the number of documents added."""
    source_file = Path(path) if path else sources_path()
    with open(source_file, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    added = 0
    for group, entries in (data.get("collections") or {}).items():
        collection = COLLECTION_BY_NAME.get(group)
        if collection is None:
            continue
        chroma_col = vector_store.collections[collection]
        for entry in entries:
            doc_id = entry.get("id")
            text = (entry.get("text") or "").strip()
            if not doc_id or not text:
                continue
            if not refresh:
                existing = chroma_col.get(ids=[doc_id], include=[])
                if existing and existing.get("ids"):
                    continue
            vector_store.add_document(
                doc_id=doc_id,
                text=text,
                metadata={
                    "title": entry.get("title", ""),
                    "source": entry.get("source", ""),
                    "collection": group,
                },
                collection=collection,
            )
            added += 1
    return added
