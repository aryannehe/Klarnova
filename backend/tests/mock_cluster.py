"""Shared scenario-aware fake Kubernetes client.

Extracted from ``chaos-testing/offline.py`` so that the offline evaluation
harness and the pytest integration suite exercise the *same* cluster double.
The mock follows the scenario ground truth: once any ``expected_actions`` has
been applied, the cluster reads as healthy, which makes validation pass.
"""
import types
from typing import Any


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
    """Swap the k8s client binding in every module that imported it.

    Returns a list of ``(module, original)`` pairs so callers can restore the
    real client afterwards (the eval harness leaves it installed; tests undo it).
    """
    import app.k8s.actions as actions_mod
    import app.k8s.client as client_mod
    from app.agents import investigation as inv_mod
    from app.agents import validation as val_mod

    pairs = []
    for mod in (client_mod, inv_mod, val_mod, actions_mod):
        pairs.append((mod, getattr(mod, "k8s_client", None)))
        mod.k8s_client = cluster
    return pairs


def restore_mock(pairs):
    for mod, original in pairs:
        mod.k8s_client = original


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
