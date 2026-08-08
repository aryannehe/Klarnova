from kubernetes import client, config

from app.config import settings


class K8sClient:
    def __init__(self):
        if settings.KUBE_IN_CLUSTER:
            config.load_incluster_config()
        else:
            config.load_kube_config()
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.custom_objects = client.CustomObjectsApi()
        
    def get_pods(self, namespace: str = "default"):
        return self.core_v1.list_namespaced_pod(namespace)

    def get_pod_logs(self, name: str, namespace: str = "default", tail_lines: int = 100):
        try:
            return self.core_v1.read_namespaced_pod_log(name, namespace, tail_lines=tail_lines)
        except Exception as e:
            return f"Error fetching logs: {e!s}"

    def get_previous_pod_logs(self, name: str, namespace: str = "default", tail_lines: int = 100):
        try:
            return self.core_v1.read_namespaced_pod_log(
                name, namespace, tail_lines=tail_lines, previous=True
            )
        except Exception:
            return None
            
    def get_events(self, namespace: str = "default"):
        return self.core_v1.list_namespaced_event(namespace)

    def get_deployments(self, namespace: str = "default"):
        return self.apps_v1.list_namespaced_deployment(namespace)

k8s_client = K8sClient()
