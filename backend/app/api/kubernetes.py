from fastapi import APIRouter, Depends, HTTPException

from app.core.rbac import require_roles
from app.k8s.actions import K8sActions
from app.k8s.client import k8s_client

router = APIRouter()

@router.get("/pods")
def list_pods(
    namespace: str = "default",
    _: dict = Depends(require_roles("admin", "engineer", "viewer")),
):
    try:
        pods = k8s_client.get_pods(namespace)
        return {"pods": [pod.metadata.name for pod in pods.items]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/pods/{name}/logs")
def get_pod_logs(
    name: str,
    namespace: str = "default",
    tail_lines: int = 50,
    _: dict = Depends(require_roles("admin", "engineer", "viewer")),
):
    logs = k8s_client.get_pod_logs(name, namespace, tail_lines)
    if logs.startswith("Error"):
        raise HTTPException(status_code=500, detail=logs)
    return {"logs": logs}

@router.post("/pods/{name}/restart")
def restart_pod(
    name: str,
    namespace: str = "default",
    _: dict = Depends(require_roles("admin", "engineer")),
):
    result = K8sActions.restart_pod(name, namespace)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result
