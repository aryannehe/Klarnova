"""Shared scenario-aware fakes for the offline/test pipeline.

Extracted from ``chaos-testing/offline.py`` so that the offline evaluation
harness and the pytest integration suite exercise the *same* doubles:

* ``MockCluster`` fakes the Kubernetes client. It follows the scenario ground
  truth: once any ``expected_actions`` has been applied, the cluster reads as
  healthy, which makes validation pass.
* ``MockVectorStore`` fakes the Chroma-backed retrieval store, returning the
  scenario's ``retrieval_ground_truth`` runbooks as if they were the top-k
  semantic matches. This keeps the pipeline hermetic (no chromadb /
  sentence-transformers, no warm index) while preserving the full-vs-no-rag
  contrast: the ``disable_rag`` ablation still short-circuits to no docs.
"""
import types
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
_KB_FALLBACK = REPO_ROOT / "knowledge-base" / "sources.yaml"

# L2 distance assigned to the scenario's ground-truth runbooks. Well inside the
# planner's ``HINT_RELEVANCE_DISTANCE`` (0.55) so the hint always counts.
RELEVANT_DISTANCE = 0.1


def _kb_sources_path() -> Path:
    from app.config import settings

    configured = Path(settings.KB_SOURCE_LIST)
    if configured.exists():
        return configured
    return _KB_FALLBACK


@lru_cache(maxsize=1)
def _load_kb_documents(path: str | None = None) -> dict[str, dict]:
    """Map every knowledge-base doc id to its entry, across all collections."""
    import yaml

    source = Path(path) if path else _kb_sources_path()
    with open(source, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    docs: dict[str, dict] = {}
    for entries in (data.get("collections") or {}).values():
        for entry in entries or []:
            if entry.get("id"):
                docs[entry["id"]] = entry
    return docs


class MockVectorStore:
    """Deterministic stand-in for ``app.rag.store.vector_store``.

    ``query_text`` returns the scenario's ground-truth runbooks (loaded from the
    knowledge base) instead of embedding the query, so retrieval is reproducible
    without the ML stack. Writes are accepted and ignored.
    """

    def __init__(self, scenario: dict, kb_documents: dict[str, dict] | None = None):
        self.scenario = scenario
        self._docs = kb_documents if kb_documents is not None else _load_kb_documents()
        self._loaded = True
        self.collections: dict[str, Any] = {}

    def query_text(
        self,
        query_text: str,
        n_results: int = 3,
        collection: str = "runbooks",
        similarity_threshold: float = 1.2,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for doc_id in self.scenario.get("retrieval_ground_truth") or []:
            entry = self._docs.get(doc_id)
            if entry is None:
                continue
            results.append(
                {
                    "doc_id": doc_id,
                    "document": (entry.get("text") or "").strip(),
                    "distance": RELEVANT_DISTANCE,
                    "metadata": {
                        "title": entry.get("title", ""),
                        "source": entry.get("source", ""),
                        "collection": collection,
                    },
                }
            )
            if len(results) >= n_results:
                break
        return results

    def query(self, *_args, **_kwargs) -> dict[str, list[list]]:
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}

    def add_document(self, *_args, **_kwargs) -> None:
        return None

    def counts(self) -> dict[str, int]:
        return {"runbooks": len(self._docs)}


def _failing_container_status():
    return types.SimpleNamespace(
        state=types.SimpleNamespace(
            waiting=types.SimpleNamespace(reason="CrashLoopBackOff"),
            terminated=None,
        )
    )


class _CoreV1:
    def __init__(self, cluster):
        self._cluster = cluster

    def read_namespaced_pod(self, name, namespace):
        if self._cluster._fixed():
            return types.SimpleNamespace(
                status=types.SimpleNamespace(phase="Running", container_statuses=[])
            )
        return types.SimpleNamespace(
            status=types.SimpleNamespace(
                phase="Running",
                container_statuses=[_failing_container_status()],
            )
        )

    def delete_namespaced_pod(self, name, namespace):
        # restart_pod and delete_pod share this API call; both reset the pod,
        # so the simulator records restart_pod (delete_pod is never a ground
        # truth action in the scenario set).
        self._cluster._apply("restart_pod", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))

    def patch_node(self, name, body):
        self._cluster._apply("cordon_node", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))

    def list_namespaced_event(self, namespace):
        return types.SimpleNamespace(items=[])


class _AppsV1:
    def __init__(self, cluster):
        self._cluster = cluster

    def read_namespaced_deployment(self, name, namespace):
        fixed = self._cluster._fixed()
        return types.SimpleNamespace(
            metadata=types.SimpleNamespace(
                annotations={"deployment.kubernetes.io/revision": "2"}
            ),
            spec=types.SimpleNamespace(
                template=types.SimpleNamespace(
                    spec=types.SimpleNamespace(
                        containers=[
                            types.SimpleNamespace(name="app", image="sock-shop/app:bad")
                        ]
                    )
                )
            ),
            status=types.SimpleNamespace(
                replicas=3, available_replicas=3 if fixed else 0
            ),
        )

    def list_namespaced_replica_set(self, namespace):
        return types.SimpleNamespace(
            items=[
                types.SimpleNamespace(
                    metadata=types.SimpleNamespace(
                        annotations={"deployment.kubernetes.io/revision": "1"},
                        creation_timestamp=None,
                    ),
                    spec=types.SimpleNamespace(
                        template=types.SimpleNamespace(
                            spec=types.SimpleNamespace(
                                containers=[
                                    types.SimpleNamespace(image="sock-shop/app:good")
                                ]
                            )
                        )
                    ),
                )
            ]
        )

    def patch_namespaced_deployment(self, name, namespace, body):
        self._cluster._apply("rollback_deployment", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))

    def patch_namespaced_deployment_scale(self, name, namespace, body):
        self._cluster._apply("scale_deployment", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))


class MockCluster:
    """Scenario-aware fake of ``app.k8s.client.k8s_client``.

    Health follows the ground truth: once any ``expected_actions`` has been
    applied, the cluster reads as healthy and validation passes.
    """

    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.applied: list[dict[str, Any]] = []
        self.core_v1 = _CoreV1(self)
        self.apps_v1 = _AppsV1(self)

    def _apply(self, action_type: str, target: str):
        self.applied.append({"action_type": action_type, "target": target})

    def _fixed(self) -> bool:
        applied_types = {a["action_type"] for a in self.applied}
        return bool(applied_types & set(self.scenario.get("expected_actions", [])))

    def get_pod_logs(self, name, namespace="default", tail_lines=100):
        return self.scenario.get("logs", "")

    def get_previous_pod_logs(self, name, namespace="default", tail_lines=100):
        return None

    def get_pods(self, namespace="default"):
        return types.SimpleNamespace(items=[])

    def get_deployments(self, namespace="default"):
        return types.SimpleNamespace(items=[])


def install_mock(cluster: MockCluster):
    """Swap the k8s client *and* vector store in every module that imported them.

    Returns a list of ``(module, attribute, original)`` triples so callers can
    restore the real bindings afterwards (the eval harness leaves the mock
    installed; tests undo it).
    """
    import app.api.config as config_mod
    import app.k8s.actions as actions_mod
    import app.k8s.client as client_mod
    from app.agents import investigation as inv_mod
    from app.agents import retrieval as retrieval_mod
    from app.agents import validation as val_mod
    from app.rag import ingest as ingest_mod
    from app.rag import store as store_mod
    from app.rag import writeback as writeback_mod

    pairs = []
    for mod in (client_mod, inv_mod, val_mod, actions_mod):
        pairs.append((mod, "k8s_client", getattr(mod, "k8s_client", None)))
        mod.k8s_client = cluster

    store = MockVectorStore(cluster.scenario)
    for mod in (
        store_mod, retrieval_mod, writeback_mod, ingest_mod, config_mod,
    ):
        if hasattr(mod, "vector_store"):
            pairs.append((mod, "vector_store", mod.vector_store))
            mod.vector_store = store
    return pairs


def restore_mock(pairs):
    for mod, attr, original in pairs:
        setattr(mod, attr, original)


def force_fallback_llm():
    """Force the deterministic diagnosis path (no Ollama in tests/offline)."""
    from app.agents import root_cause

    def _raise(_state):
        raise RuntimeError("deterministic fallback: no LLM available")

    root_cause._diagnose_with_llm = _raise


def fast_validation(timeout: float = 0.0, interval: float = 0.0):
    """The mock cluster is deterministic, so the health poll must not wait."""
    from app.agents import validation as val_mod

    val_mod.HEALTH_POLL_TIMEOUT = timeout
    val_mod.HEALTH_POLL_INTERVAL = interval


def real_validation():
    """Restore the production health-poll defaults."""
    from app.agents import validation as val_mod

    val_mod.HEALTH_POLL_TIMEOUT = 120.0
    val_mod.HEALTH_POLL_INTERVAL = 5.0
