from langgraph.graph import END, StateGraph

from app.agents.investigation import investigation_node
from app.agents.planning import planning_node
from app.agents.remediation import remediation_node
from app.agents.reporting import reporting_node
from app.agents.retrieval import retrieval_node
from app.agents.root_cause import root_cause_node
from app.agents.safety import safety_node
from app.agents.state import AgentState
from app.agents.validation import validation_node


def build_investigation_graph():
    """Detection -> evidence -> diagnosis -> plan -> safety gate."""
    workflow = StateGraph(AgentState)

    workflow.add_node("investigation", investigation_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("root_cause", root_cause_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("safety", safety_node)

    workflow.set_entry_point("investigation")
    workflow.add_edge("investigation", "retrieval")
    workflow.add_edge("retrieval", "root_cause")
    workflow.add_edge("root_cause", "planning")
    workflow.add_edge("planning", "safety")
    workflow.add_edge("safety", END)

    return workflow.compile()


def _route_after_validation(state):
    """Bounded retry-then-escalate: retry, or report once resolved/escalated."""
    if state.get("is_resolved") or state.get("escalated"):
        return "reporting"
    return "remediation"


def build_remediation_graph():
    """Execute approved action -> validate -> (retry | report)."""
    workflow = StateGraph(AgentState)

    workflow.add_node("remediation", remediation_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("reporting", reporting_node)

    workflow.set_entry_point("remediation")
    workflow.add_edge("remediation", "validation")
    workflow.add_conditional_edges(
        "validation",
        _route_after_validation,
        {"reporting": "reporting", "remediation": "remediation"},
    )
    workflow.add_edge("reporting", END)

    return workflow.compile()


def build_graph():
    """Backwards-compatible alias: the investigation phase graph."""
    return build_investigation_graph()
