"""Kubernetes API client wrapper (KLR-C1).

Loads in-cluster config when deployed, otherwise the local kubeconfig.
Read-only by design at this phase; the ServiceAccount/ClusterRole caps the
permissions the cluster actually grants (KLR-B5).
"""

from __future__ import annotations

import logging

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

logger = logging.getLogger(__name__)


class KubernetesClient:
    def __init__(self, *, in_cluster: bool = False, kubeconfig: str | None = None) -> None:
        if in_cluster:
            k8s_config.load_incluster_config()
        elif kubeconfig:
            k8s_config.load_kube_config(config_file=kubeconfig)
        else:
            k8s_config.load_kube_config()
        self.core = k8s_client.CoreV1Api()
        self.apps = k8s_client.AppsV1Api()

    def list_namespaces(self) -> list[str]:
        return [ns.metadata.name for ns in self.core.list_namespace().items]

    def list_pods(self, namespace: str | None = None) -> list[dict]:
        if namespace:
            pods = self.core.list_namespaced_pod(namespace)
        else:
            pods = self.core.list_pod_for_all_namespaces()
        return [_pod_dict(p) for p in pods.items]

    def get_pod(self, name: str, namespace: str = "default") -> dict:
        return _pod_dict(self.core.read_namespaced_pod(name, namespace))

    def list_deployments(self, namespace: str | None = None) -> list[dict]:
        if namespace:
            deployments = self.apps.list_namespaced_deployment(namespace)
        else:
            deployments = self.apps.list_deployment_for_all_namespaces()
        result = []
        for d in deployments.items:
            result.append(
                {
                    "name": d.metadata.name,
                    "namespace": d.metadata.namespace,
                    "replicas": d.spec.replicas,
                    "available": d.status.available_replicas or 0,
                    "ready": d.status.ready_replicas or 0,
                }
            )
        return result

    def list_events(
        self, namespace: str | None = None, field_selector: str | None = None
    ) -> list[dict]:
        if namespace:
            events = self.core.list_namespaced_event(namespace, field_selector=field_selector)
        else:
            events = self.core.list_event_for_all_namespaces(field_selector=field_selector)
        return [
            {
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "involved_object": e.involved_object.kind
                + "/"
                + e.involved_object.name,
                "count": e.count,
                "last_timestamp": e.last_timestamp,
            }
            for e in events.items
        ]


def _pod_dict(pod) -> dict:
    container_statuses = []
    for status in pod.status.container_statuses or []:
        state = {}
        if status.state and status.state.running:
            state = {"state": "running", "started_at": str(status.state.running.started_at)}
        elif status.state and status.state.terminated:
            state = {
                "state": "terminated",
                "reason": status.state.terminated.reason,
                "exit_code": status.state.terminated.exit_code,
            }
        elif status.state and status.state.waiting:
            state = {"state": "waiting", "reason": status.state.waiting.reason}
        container_statuses.append(
            {
                "name": status.name,
                "restart_count": status.restart_count,
                "ready": status.ready,
                **state,
            }
        )
    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "node": pod.spec.node_name,
        "phase": pod.status.phase,
        "container_statuses": container_statuses,
    }


_client: KubernetesClient | None = None


def get_k8s_client() -> KubernetesClient:
    """Lazily create a shared client (Auto-Discovery picks config, KLR-C3)."""
    global _client
    if _client is None:
        from app.discovery.auto_discovery import detect_kube_mode

        in_cluster = detect_kube_mode()
        logger.info("Initialising Kubernetes client (in_cluster=%s)", in_cluster)
        _client = KubernetesClient(in_cluster=in_cluster)
    return _client
