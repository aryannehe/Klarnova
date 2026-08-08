from app.agents.state import AgentState
from app.k8s.client import k8s_client


def investigation_node(state: AgentState):
    """Gathers logs and events for the target resource."""
    target = state.get("target_resource")
    ns = state.get("namespace", "default")
    
    logs = ""
    if target:
        logs = k8s_client.get_pod_logs(target, ns)
        
    return {
        "logs": [logs] if logs else [],
        "messages": [{"role": "system", "content": "Investigation complete. Logs gathered."}]
    }
