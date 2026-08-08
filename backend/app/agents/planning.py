from app.agents.state import AgentState
from app.bandit.model import bandit, build_context


def _prior_bump(state: AgentState, action_type: str) -> float:
    """nudge action rank when retrieved runbooks suggest it."""
    bump = 0.0
    for doc in state.get("retrieved_docs", []):
        text = (doc.get("document") or "").lower()
        hints = {
            "restart_pod": ("restart", "reschedule"),
            "scale_deployment": ("scale", "replica"),
            "rollback_deployment": ("rollback", "revert"),
            "delete_pod": ("delete pod", "kill pod"),
            "cordon_node": ("cordon", "drain"),
        }
        if any(h in text for h in hints.get(action_type, ())):
            bump += 0.1
    return bump


def planning_node(state: AgentState):
    """Generate and rank candidate remediation actions (never a single choice).

    Ranking = bandit expected reward (priors until trained) + retrieval hint.
    """
    context = build_context(state)
    ranked = bandit.get_ranked_actions(context)

    candidates = []
    for item in ranked:
        candidates.append(
            {
                "action_type": item["action_type"],
                "target_resource": state.get("target_resource"),
                "namespace": state.get("namespace", "default"),
                "expected_reward": round(
                    float(item["expected_reward"]) + _prior_bump(state, item["action_type"]), 3
                ),
                "source": item.get("source", "bandit"),
                "parameters": {},
            }
        )
    candidates.sort(key=lambda c: c["expected_reward"], reverse=True)
    selected = candidates[0] if candidates else None

    return {
        "candidate_actions": candidates,
        "selected_action": selected,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"Planning: ranked {len(candidates)} candidate(s), "
                    f"selected {selected['action_type'] if selected else 'none'}"
                ),
            }
        ],
    }
