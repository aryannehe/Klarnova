from app.rag.writeback import _build_doc, writeback_incident


def _resolved_state():
    return {
        "target_resource": "catalogue-abc",
        "namespace": "sock-shop",
        "severity": "SEV-3",
        "root_cause": "in-memory cache grew unbounded",
        "confidence_score": 0.92,
        "selected_action": {"action_type": "restart_pod"},
        "is_resolved": True,
        "escalated": False,
        "resolved_at": "2026-08-08T00:00:00+00:00",
    }


class _NoResult:
    def scalar_one_or_none(self):
        return None


class _FakeSession:
    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, *args, **kwargs):
        return _NoResult()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None


def test_build_doc_fields():
    text = _build_doc(7, _resolved_state())
    assert "Incident 7" in text
    assert "SEV-3" in text
    assert "catalogue-abc" in text
    assert "sock-shop" in text
    assert "cache grew unbounded" in text
    assert "restart_pod" in text
    assert "resolved" in text


def test_build_doc_escalated_outcome():
    text = _build_doc(7, {**_resolved_state(), "is_resolved": False, "escalated": True})
    assert "escalated to human" in text


async def test_writeback_skips_live_incidents():
    # Not resolved nor escalated -> no write-back, no side effects.
    assert await writeback_incident(7, {"is_resolved": False, "escalated": False}, {}) is False


async def test_writeback_persists_row_even_if_chroma_unavailable(monkeypatch):
    # Durable KnowledgeDoc row is written even when the embedding index fails.
    from app.rag import writeback

    def _boom(*args, **kwargs):
        raise RuntimeError("vector store not available (ML deps missing)")

    fake = _FakeSession()
    monkeypatch.setattr(writeback.vector_store, "add_document", _boom)
    monkeypatch.setattr(writeback, "SessionLocal", lambda: fake)

    assert await writeback_incident(7, _resolved_state(), {}) is True
    assert len(fake.added) == 1


async def test_writeback_returns_false_when_persistence_fails(monkeypatch):
    from app.rag import writeback

    class _BoomSession(_FakeSession):
        async def commit(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(writeback, "SessionLocal", lambda: _BoomSession())
    assert await writeback_incident(7, _resolved_state(), {}) is False
