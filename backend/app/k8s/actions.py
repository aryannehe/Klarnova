from app.k8s.client import k8s_client


def _safe_result(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}


class K8sActions:
    @staticmethod
    def restart_pod(name: str, namespace: str = "default"):
        return _safe_result(k8s_client.core_v1.delete_namespaced_pod, name, namespace)

    @staticmethod
    def delete_pod(name: str, namespace: str = "default"):
        return _safe_result(k8s_client.core_v1.delete_namespaced_pod, name, namespace)

    @staticmethod
    def scale_deployment(name: str, replicas: int, namespace: str = "default"):
        try:
            body = {"spec": {"replicas": replicas}}
            k8s_client.apps_v1.patch_namespaced_deployment_scale(name, namespace, body)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def rollback_deployment(name: str, namespace: str = "default"):
        """Roll the deployment back to the image of the previous revision.

        Mirrors ``kubectl rollout undo``: the target ReplicaSet is the one
        whose ``deployment.kubernetes.io/revision`` annotation is one less
        than the deployment's current revision. Falls back to the newest
        ReplicaSet with a different image if the history was pruned.
        """
        try:
            deploy = k8s_client.apps_v1.read_namespaced_deployment(name, namespace)
            current_image = deploy.spec.template.spec.containers[0].image
            current_rev = int(
                (deploy.metadata.annotations or {}).get(
                    "deployment.kubernetes.io/revision", "0"
                )
            )
            replicasets = k8s_client.apps_v1.list_namespaced_replica_set(namespace).items

            def _revision(rs) -> int | None:
                try:
                    return int(
                        (rs.metadata.annotations or {}).get(
                            "deployment.kubernetes.io/revision", "0"
                        )
                    )
                except (TypeError, ValueError):
                    return None

            previous = [
                rs for rs in replicasets if _revision(rs) == current_rev - 1
            ] if current_rev > 1 else []

            if not previous:
                candidates = [
                    rs
                    for rs in replicasets
                    if rs.spec.template.spec.containers[0].image != current_image
                ]
                candidates.sort(
                    key=lambda rs: rs.metadata.creation_timestamp or 0, reverse=True
                )
                previous = candidates[:1]

            if not previous:
                return {"success": False, "message": "no previous revision found"}
            image = previous[0].spec.template.spec.containers[0].image
            container_name = deploy.spec.template.spec.containers[0].name
            body = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{"name": container_name, "image": image}]
                        }
                    }
                }
            }
            k8s_client.apps_v1.patch_namespaced_deployment(name, namespace, body)
            return {"success": True, "message": f"rolled back to image {image}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def cordon_node(name: str):
        return _safe_result(
            k8s_client.core_v1.patch_node, name, {"spec": {"unschedulable": True}}
        )

