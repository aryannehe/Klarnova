import re

from app.ablation import ablation
from app.agents.state import AgentState
from app.bandit.model import PRIORS, bandit, build_context


def _prior_bump(state: AgentState, action_type: str) -> float:
    """nudge action rank when retrieved runbooks suggest it.

    +0.2 per matching runbook, capped at +0.6: a runbook that clearly
    recommends an action should be able to outweigh the static priors, but no
    single signal should dominate the plan. Hints are matched on word
    boundaries so substrings (e.g. "replica" inside "ReplicaSet") do not count.
    """
    bump = 0.0
    hints = {
        "restart_pod": (r"\brestart", r"\breschedule"),
        "scale_deployment": (r"\bscale", r"\breplicas?\b"),
        "rollback_deployment": (r"\brollback\b", r"\broll back\b", r"\brevert\b", r"\bundo\b"),
        "delete_pod": (r"\bdelete pod\b", r"\bkill pod\b"),
        "cordon_node": (r"\bcordon\b", r"\bdrain\b"),
    }
    for doc in state.get("retrieved_docs", []):
        text = (doc.get("document") or "").lower()
        if any(re.search(h, text) for h in hints.get(action_type, ())):
            bump += 0.2
    return min(0.6, bump)


def _static_ranked() -> list[tuple[str, float]]:
    """Static arm ordering from bandit priors (used when bandit/planning
    are ablated or before any training sample exists)."""
    return sorted(PRIORS.items(), key=lambda kv: kv[1], reverse=True)


def _ranked_for(state: AgentState, use_bandit: bool) -> list[tuple[str, float]]:
    if use_bandit:
        context = build_context(state)
        return [
            (item["action_type"], float(item["expected_reward"]))
            for item in bandit.get_ranked_actions(context)
        ]
    return _static_ranked()


def planning_node(state: AgentState):
    """Generate and rank candidate remediation actions (never a single choice).

    Ranking = bandit expected reward (priors until trained) + retrieval hint,
    unless the corresponding ablation switch is active:

    - without bandit: static priors, retrieval hints still applied;
    - without planning separation: mechanical static-priority selection,
      ignoring both the bandit and retrieval evidence.
    """
    use_bandit = not (ablation.disable_bandit or ablation.disable_planning)
    use_retrieval_bump = not ablation.disable_planning

    ranked = _ranked_for(state, use_bandit)
    candidates = []
    for action_type, base_reward in ranked:
        reward = base_reward
        if use_retrieval_bump:
            reward += _prior_bump(state, action_type)
        candidates.append(
            {
                "action_type": action_type,
                "target_resource": state.get("target_resource"),
                "namespace": state.get("namespace", "default"),
                "expected_reward": round(reward, 3),
                "source": "bandit" if use_bandit else "static",
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
