from app.agents.state import AgentState
from app.policy.engine import evaluate


def safety_node(state: AgentState):
    """Risk gate: policy engine + confidence + severity (deterministic)."""
    action = state.get("selected_action") or {}
    action_type = action.get("action_type", "")
    severity = state.get("severity", "SEV-3")
    confidence = float(state.get("confidence_score", 0.0))

    decision = evaluate(action_type, severity, confidence)

    if decision.mode == "deny":
        is_safe = False
        requires_approval = False
        approval_status = "rejected"
    elif decision.mode == "require_approval":
        is_safe = True
        requires_approval = True
        approval_status = "pending"
    else:  # auto
        is_safe = True
        requires_approval = False
        approval_status = "approved"

    return {
        "is_safe": is_safe,
        "requires_approval": requires_approval,
        "approval_status": approval_status,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"Safety: {action_type} at {severity} "
                    f"(conf={confidence:.2f}) -> {decision.mode}: {decision.reason}"
                ),
            }
        ],
    }
