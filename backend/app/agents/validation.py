"""Validation agent - verifies health after remediation and enforces the
bounded retry-then-escalate loop.

After an action, we re-check the live cluster state. If the incident
persists, the graph routes back to planning (bounded by ``max_retries``);
once the budget is exhausted the incident is escalated to a human instead
of looping indefinitely.
"""
import time

from app.agents.state import AgentState
from app.k8s.client import k8s_client

DEFAULT_MAX_RETRIES = 2

HEALTH_POLL_TIMEOUT = 120.0
HEALTH_POLL_INTERVAL = 5.0

# Actions that mutate a Deployment/StatefulSet (target_resource is the
# workload name) rather than an individual pod.
DEPLOYMENT_SCOPED_ACTIONS = {"rollback_deployment", "scale_deployment"}


CRASH_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerError",
    "InvalidImageName",
    "RunContainerError",
    "OOMKilled",
}


def _container_failing(status) -> bool:
    state = getattr(status, "state", None)
    waiting = getattr(state, "waiting", None)
    if waiting is not None and getattr(waiting, "reason", "") in CRASH_REASONS:
        return True
    terminated = getattr(state, "terminated", None)
    if terminated is not None and getattr(terminated, "reason", "") in CRASH_REASONS:
        return True
    return False


def _check_pod(state: AgentState) -> bool:
    try:
        pod = k8s_client.core_v1.read_namespaced_pod(
            state["target_resource"], state.get("namespace", "default")
        )
        if getattr(pod.status, "phase", "Unknown") != "Running":
            return False
        statuses = getattr(pod.status, "container_statuses", None) or []
        return not any(_container_failing(s) for s in statuses)
    except Exception:
        return False


def _check_deployment(state: AgentState) -> bool:
    try:
        deploy = k8s_client.apps_v1.read_namespaced_deployment(
            state["target_resource"], state.get("namespace", "default")
        )
        status = deploy.status
        desired = getattr(status, "replicas", None)
        available = getattr(status, "available_replicas", None)
        if desired is None:
            return False
        return available == desired
    except Exception:
        return False


def check_health(state: AgentState) -> bool:
    action_type = (state.get("selected_action") or {}).get("action_type", "")
    kind = state.get("resource_kind", "pod").lower()
    if action_type in DEPLOYMENT_SCOPED_ACTIONS or kind in (
        "deployment",
        "deployments",
        "statefulset",
    ):
        return _check_deployment(state)
    return _check_pod(state)


def _poll_health(state: AgentState) -> bool:
    """Give the rollout / restart time to settle before declaring failure."""
    deadline = time.monotonic() + HEALTH_POLL_TIMEOUT
    while True:
        if check_health(state):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(HEALTH_POLL_INTERVAL)


def validation_node(state: AgentState):
    resolved = _poll_health(state)
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", DEFAULT_MAX_RETRIES))

    if resolved:
        message = "Validation: incident resolved after remediation"
    else:
        retry_count += 1
        if retry_count > max_retries:
            message = (
                f"Validation: not resolved after {max_retries} retries - ESCALATING to human"
            )
        else:
            message = f"Validation: not resolved (attempt {retry_count}/{max_retries}) - retrying"

    return {
        "is_resolved": resolved,
        "retry_count": retry_count,
        "escalated": (not resolved) and retry_count > max_retries,
        "messages": [{"role": "system", "content": message}],
    }
