from typing import Any

from pydantic import BaseModel, Field


class ActionBase(BaseModel):
    action_type: str # restart_pod, scale_deployment, rollback_deployment, delete_pod, cordon_node
    target_resource: str
    namespace: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    
class RankedAction(ActionBase):
    expected_reward: float
    source: str # e.g. "bandit", "runbook"
    
class RemediationPlan(BaseModel):
    candidate_actions: list[RankedAction]
    selected_action: RankedAction | None = None
    requires_approval: bool = False
    
class RemediationResult(BaseModel):
    success: bool
    message: str
    time_to_resolve_seconds: float | None = None
