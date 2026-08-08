import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Collections per the Technical Architecture Document section 3.2
RUNBOOKS = "runbooks"
HISTORICAL_INCIDENTS = "historical_incidents"
KUBERNETES_DOCS = "kubernetes_docs"

COLLECTIONS = [RUNBOOKS, HISTORICAL_INCIDENTS, KUBERNETES_DOCS]


class VectorStore:
    """Chroma-backed store. Degrades to an empty/missing store when the ML
    dependencies (chromadb / sentence-transformers) are not installed, so the
    rest of the graph can keep running with rule-based fallbacks."""

    def __init__(self, _loaded: bool = False):
        self._loaded = _loaded
        self.client = None
        self.collections: dict[str, Any] = {}

    @classmethod
    def connect(cls) -> "VectorStore":
        try:
            import chromadb

            from app.rag.embedder import embedder

            store = cls(_loaded=True)
            store.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            store.collections = {
                name: store.client.get_or_create_collection(name=name)
                for name in COLLECTIONS
            }
            store.embedder = embedder
            return store
        except Exception as exc:
            logger.warning("Chroma unavailable (%s); RAG retrieval degraded", exc)
            return cls(_loaded=False)

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict | None = None,
        collection: str = RUNBOOKS,
    ):
        if not self._loaded:
            raise RuntimeError("vector store not available (ML deps missing)")
        embedding = self.embedder.embed_text(text)
        self.collections[collection].upsert(
            ids=[doc_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata or {}],
        )

    def query(
        self,
        query_text: str,
        n_results: int = 3,
        collection: str = RUNBOOKS,
        where: dict | None = None,
    ):
        if not self._loaded:
            raise RuntimeError("vector store not available (ML deps missing)")
        embedding = self.embedder.embed_text(query_text)
        results = self.collections[collection].query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
        )
        return results

    def counts(self) -> dict[str, int]:
        """Per-collection document counts; empty dict when the store is degraded."""
        if not self._loaded:
            return {}
        try:
            return {name: self.collections[name].count() for name in COLLECTIONS}
        except Exception as exc:
            logger.warning("Chroma counts unavailable: %s", exc)
            return {}

    def query_text(
        self,
        query_text: str,
        n_results: int = 3,
        collection: str = RUNBOOKS,
        similarity_threshold: float = 1.0,
    ):
        """Return a list of {document, distance, metadata} above the threshold.

        ``distance`` is Chroma L2 distance (lower = more similar, 0 = identical).
        ``similarity_threshold`` is a maximum-distance cutoff: documents farther
        than it are excluded.
        """
        results = self.query(query_text, n_results=n_results, collection=collection)
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        out = []
        for doc_id, doc, dist, meta in zip(ids, docs, dists, metas, strict=False):
            if dist is not None and dist > similarity_threshold:
                continue
            out.append(
                {
                    "doc_id": doc_id,
                    "document": doc,
                    "distance": dist,
                    "metadata": meta or {},
                }
            )
        return out


vector_store = VectorStore.connect()
