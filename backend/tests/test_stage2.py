import asyncio

from app.agents.validation import _check_pod, _container_failing
from app.bandit.model import bandit, build_context


class _Detail:
    def __init__(self, reason):
        self.reason = reason


class _ContainerState:
    def __init__(self, waiting_reason, terminated_reason):
        self.waiting = _Detail(waiting_reason)
        self.terminated = _Detail(terminated_reason)


class _ContainerStatus:
    def __init__(self, waiting_reason=None, terminated_reason=None):
        self.state = _ContainerState(waiting_reason, terminated_reason)


class _PodStatus:
    def __init__(self, phase="Running", container_statuses=None):
        self.phase = phase
        self.container_statuses = container_statuses or []


class _Pod:
    def __init__(self, status):
        self.status = status


class _FakeCoreV1:
    def __init__(self, pod):
        self._pod = pod

    def read_namespaced_pod(self, name, namespace):
        return self._pod


def test_container_failing_crashloop():
    assert _container_failing(_ContainerStatus(waiting_reason="CrashLoopBackOff"))


def test_container_failing_image_pull():
    assert _container_failing(_ContainerStatus(waiting_reason="ImagePullBackOff"))


def test_container_not_failing_when_ready():
    assert not _container_failing(_ContainerStatus())


def test_check_pod_crashloop_is_not_resolved(monkeypatch):
    from app.k8s.client import k8s_client

    pod = _Pod(_PodStatus(container_statuses=[_ContainerStatus(waiting_reason="CrashLoopBackOff")]))
    monkeypatch.setattr(k8s_client, "core_v1", _FakeCoreV1(pod))
    state = {"target_resource": "pod-a", "namespace": "ns", "resource_kind": "pod"}
    assert _check_pod(state) is False


def test_check_pod_healthy_is_resolved(monkeypatch):
    from app.k8s.client import k8s_client

    pod = _Pod(_PodStatus(container_statuses=[_ContainerStatus()]))
    monkeypatch.setattr(k8s_client, "core_v1", _FakeCoreV1(pod))
    state = {"target_resource": "pod-a", "namespace": "ns", "resource_kind": "pod"}
    assert _check_pod(state) is True


def test_partial_fit_awaited_trains_mab():
    state = {
        "severity": "SEV-3",
        "metrics": {},
        "resource_kind": "pod",
    }
    asyncio.run(bandit.partial_fit("restart_pod", 1.0, build_context(state)))
    assert bandit.is_fitted is True
    ranked = bandit.get_ranked_actions(build_context(state))
    assert ranked[0]["action_type"] == "restart_pod"
