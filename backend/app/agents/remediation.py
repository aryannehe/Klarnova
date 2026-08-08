"""Remediation agent - executes approved actions through the whitelist only.

Defense in depth: even if an LLM or a bug proposes an action, this node
only runs when the safety gate cleared it AND (the action does not require
approval OR an explicit approval exists).
"""

from app.agents.state import AgentState
from app.k8s.actions import K8sActions
from app.policy.engine import WHITELIST

EXECUTORS = {
    "restart_pod": lambda s: K8sActions.restart_pod(
        s["target_resource"], s.get("namespace", "default")
    ),
    "delete_pod": lambda s: K8sActions.delete_pod(
        s["target_resource"], s.get("namespace", "default")
    ),
    "scale_deployment": lambda s: K8sActions.scale_deployment(
        s["target_resource"],
        int(s.get("selected_action", {}).get("parameters", {}).get("replicas", 1)),
        s.get("namespace", "default"),
    ),
    "rollback_deployment": lambda s: K8sActions.rollback_deployment(
        s["target_resource"], s.get("namespace", "default")
    ),
    "cordon_node": lambda s: K8sActions.cordon_node(s["target_resource"]),
}


def can_execute(state: AgentState) -> str | None:
    if not state.get("is_safe"):
        return "action rejected by safety gate"
    if state.get("requires_approval") and state.get("approval_status") != "approved":
        return "action requires human approval (pending)"
    return None


def remediation_node(state: AgentState):
    action = state.get("selected_action") or {}
    action_type = action.get("action_type")

    # Whitelist check (hard ceiling even if the policy layer was bypassed).
    if action_type not in WHITELIST:
        result = {"success": False, "message": f"action '{action_type}' not whitelisted"}
    else:
        blocker = can_execute(state)
        if blocker:
            result = {"success": False, "message": blocker}
        else:
            executor = EXECUTORS.get(action_type)
            result = executor(state) if executor else {"success": False, "message": "no executor"}

    message = (
        f"Remediation: {action_type} on {state.get('target_resource')} -> "
        f"{'ok' if result.get('success') else result.get('message')}"
    )
    return {
        "remediation_result": message,
        "remediation_success": bool(result.get("success")),
        "messages": [{"role": "system", "content": message}],
    }
