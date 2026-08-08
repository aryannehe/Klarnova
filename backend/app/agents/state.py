import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    # Incident context
    incident_id: str
    incident_data: dict[str, Any]
    severity: str | None
    priority: str | None
    detected_at: str | None

    # K8s context
    namespace: str
    target_resource: str
    resource_kind: str

    # Evidence & Analysis
    logs: Annotated[list[str], operator.add]
    events: Annotated[list[str], operator.add]
    metrics: dict[str, Any]

    # RAG
    retrieved_docs: Annotated[list[dict[str, Any]], operator.add]

    # Reasoning
    root_cause: str | None
    confidence_score: float

    # Planning
    candidate_actions: list[dict[str, Any]]
    selected_action: dict[str, Any] | None

    # Safety & Policy
    is_safe: bool
    requires_approval: bool
    approval_status: str | None  # pending, approved, rejected

    # Execution
    remediation_result: str | None
    remediation_success: bool
    is_resolved: bool
    retry_count: int
    max_retries: int
    escalated: bool
    resolved_at: str | None

    # Report
    report: str | None

    # Errors/Metadata
    messages: Annotated[list[dict[str, Any]], operator.add]
