"""Minimal LangGraph wiring (KLR-C7).

Phase 1 graph: a single deterministic `monitoring` node that produces the
detection decision (severity/priority classification) from raw alert data.
Later phases add Investigation → Retrieval → Root Cause → … as nodes; the
frozen AgentState contract (KLR-A3) is the state flowing through it.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.state import AgentState
from app.services.classification import classify_labels


def monitoring_node(state: AgentState) -> AgentState:
    """Detection decision: classify severity/priority from raw alert labels."""
    incident = state.incident
    if incident is None:
        return state
    severity, priority = classify_labels(incident.labels or {})
    incident.severity = severity
    incident.priority = priority
    updated = state.model_dump()
    updated.update(severity=severity, priority=priority, incident=incident)
    return AgentState(**updated)


def build_detection_graph():
    graph = StateGraph(AgentState)
    graph.add_node("monitoring", monitoring_node)
    graph.add_edge(START, "monitoring")
    graph.add_edge("monitoring", END)
    return graph.compile()


_compiled = None


def get_detection_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_detection_graph()
    return _compiled


def run_detection(state: AgentState) -> AgentState:
    """Run the graph and return the resulting (classified) state."""
    result = get_detection_graph().invoke(state)
    if isinstance(result, dict):
        return AgentState(**result)
    return result
