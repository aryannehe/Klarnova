# Klarnova — End-to-End Walkthrough (Stage 2)

This walkthrough demonstrates the full incident loop running in minikube: a real
failure in Sock Shop is detected by Prometheus, fired to Alertmanager, ingested by
the Klarnova backend, investigated, escalated for human approval, remediated, and
used to train the contextual bandit — all against the live cluster.

## Prerequisites

| Component            | Version / setup                                  |
| -------------------- | ------------------------------------------------ |
| minikube             | v1.34.1, `containerd` runtime, profile `minikube`|
| kubectl / helm       | latest; helm v4.x                                |
| docker               | host daemon (build then `minikube image load`)   |
| Sock Shop            | running in namespace `sock-shop`                 |
| kube-prometheus-stack| running in namespace `monitoring`                |
| Postgres             | reachable at `host.minikube.internal:5432/klarnova` |

### Alertmanager wiring

Install the stack with the repo's values file so Alertmanager routes alerts to the
backend (the `klarnova-webhook` receiver) and silences known minikube control-plane
noise (etcd, scheduler/controller-manager unreachable, `TargetDown`) that would
otherwise spam the incident feed:

```bash
helm upgrade --install kube-prometheus-stack \
  prometheus-community/kube-prometheus-stack \
  -n monitoring -f k8s/monitoring/kube-prometheus-stack-values.yaml
```

```yaml
route:
  receiver: 'klarnova-webhook'
  routes:
  - { match: { alertname: Watchdog }, receiver: 'null' }
  - { match_re: { alertname: 'etcdInsufficientMembers|etcdMembersDown|etcdHighNumberOfFailedProposals|KubeSchedulerInstanceUnreachable|KubeControllerManagerInstanceUnreachable|TargetDown' }, receiver: 'null' }
receivers:
- { name: 'null' }
- name: 'klarnova-webhook'
  webhook_configs:
  - url: 'http://klarnova-backend.default.svc:8000/v1/webhooks/alertmanager'
    http_config: { authorization: { type: Bearer, credentials: 'dev-token' } }
```

The built-in `KubePodCrashLooping` rule fires after 15m — too slow for a demo.
Shorten it (dev cluster only):

```bash
kubectl -n monitoring patch prometheusrule kube-prometheus-stack-kubernetes-apps \
  --type=json \
  --patch='[{"op":"replace","path":"/spec/groups/0/rules/0/for","value":"1m"}]'
```

Note: any later `helm upgrade` of the stack regenerates the rule (resetting `for`)
and the Alertmanager secret; re-run both commands above afterwards.

## 1. Build and deploy the backend

```bash
bash scripts/setup.sh
```

This builds `backend/Dockerfile` with the host docker daemon, loads it into
minikube (`containerd` runtime — `minikube docker-env` does not apply), and
installs/upgrades the Helm chart `helm/klarnova`:

- `Deployment klarnova` (namespace `default`) — uvicorn on :8000, probes on `/health`
- `Service klarnova-backend:8000` — the URL Alertmanager posts to
- `ConfigMap` — `KUBE_IN_CLUSTER=true`, `DATABASE_URL`, `PROMETHEUS_URL`,
  `CHROMA_PERSIST_DIR=/data/chroma`, webhook token, JWT secret
- `PVC` for the Chroma store
- `ServiceAccount klarnova-backend` + `ClusterRole` (pods/events/logs read,
  deployments/statefulsets/replicasets read, deployments+scale patch, pods delete,
  nodes patch)

Expose the API locally:

```bash
kubectl -n default port-forward svc/klarnova-backend 8000:8000 &
```

Health check and login:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/v1/auth/login \
  -d 'username=admin&password=admin123'
```

## 2. Inject a real failure

```bash
bash scripts/inject-failure.sh
```

The script first restores a clean baseline
(`weaveworksdemos/catalogue:0.3.5`, arg 4) so the deployment's previous revision is
the known-good image, then replaces the `catalogue` image with `alpine:3.18`
(arg 3). Alpine has no entrypoint, so the container exits immediately; Kubernetes
restarts it and the pod enters `CrashLoopBackOff`. Prometheus observes
`kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"}` and fires the
`KubePodCrashLooping` alert (within ~1m with the patched rule), which Alertmanager
forwards to `http://klarnova-backend.default.svc:8000/v1/webhooks/alertmanager`.

Repeated firing notifications are deduplicated server-side: only one incident is
opened per (alert, namespace, resource) while it remains unresolved.

## 3. Watch the loop

Run the full demo:

```bash
bash scripts/demo.sh
```

Or step through it manually (`scripts/demo.py` does exactly this):

1. **Detect** — the webhook creates an `Incident`
   (`alert_name=KubePodCrashLooping`, namespace `sock-shop`).
2. **Investigate** — the LangGraph pipeline reads pod events + previous logs
   (RBAC allows `pods/log`), classifies severity, retrieves runbook precedents,
   and produces a root-cause diagnosis with a confidence score.
3. **Plan + Safety** — candidate actions are ranked (bandit priors + runbook
   hints); `restart_pod` ranks first. Confidence 0.45 is below the 0.75 approval
   threshold, so the incident moves to **Awaiting Approval**.
4. **Approve (operator override)** — the approving engineer selects
   `rollback_deployment` against the `catalogue` deployment (the right fix for a
   bad image), overriding the system's `restart_pod` choice:

   ```bash
   curl -s -X POST localhost:8000/v1/actions/approve \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"incident_id":"<ID>","action_type":"rollback_deployment",
          "approved":true,"target_resource":"catalogue","namespace":"sock-shop"}'
   ```

5. **Remediate + validate** — `rollback_deployment` undoes the deployment to its
   previous revision (mirrors `kubectl rollout undo`), restoring
   `weaveworksdemos/catalogue:0.3.5`. Validation polls the live deployment until
   the rollout settles and confirms `available == desired`; the incident is
   marked **Resolved**. If the fix did not take, validation retries up to
   `max_retries` and then **escalates to a human** instead of looping forever.
6. **Learn** — a `Remediation` row is recorded and the contextual bandit trains:
   `partial_fit("rollback_deployment", reward=1.0, context)` and the
   `BanditPolicy` row for `KubePodCrashLooping` is updated (EMA reward + counter).
   On restart, `seed_bandit_from_db` replays learned policy.

## 4. Inspect the evidence

```bash
# Incident + trace
curl -s localhost:8000/v1/incidents            -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/v1/incidents/<ID>/trace -H "Authorization: Bearer $TOKEN"
```

The trace shows the agent sequence: monitoring -> investigation -> retrieval ->
root_cause -> planning -> safety, then remediation -> validation -> reporting, plus
the recorded remediation action and time-to-resolve.

## 5. Reset

```bash
bash scripts/reset.sh    # restores weaveworksdemos/catalogue:0.3.5
```

## Cleanup

```bash
helm uninstall klarnova -n default
kubectl delete pvc -n default -l app.kubernetes.io/name=klarnova
```

## Notes / known tradeoffs

- The runtime image ships the **core** stack (FastAPI, LangGraph, k8s client, bandit).
  The RAG embedding stack (torch / sentence-transformers / chromadb) lives in
  `backend/requirements-ml.txt` and can be baked in with `INSTALL_ML=true`
  (build arg) when semantic retrieval is needed. Without it, retrieval degrades
  gracefully to rule-based diagnosis (by design).
- In-cluster LLM (Ollama) is optional; when unreachable the diagnosis falls back to
  deterministic rules, keeping the safety guarantees LLM-independent.
- Bandit ranking needs `k+1` training samples before mabwiser re-ranks arms; until
  then it uses static priors. Learning is still persisted on every remediation.
- After the rollback the `KubePodCrashLooping` alert can lag by several minutes:
  kube-state-metrics keeps the crash-loop reason series for the deleted pod and the
  rule uses a 5m `max_over_time` window. It clears on its own; server-side dedup
  prevents a resolved incident from being re-opened by the stale notification.
- On minikube the control-plane noise alerts (etcd, scheduler/controller-manager
  unreachable, `TargetDown`) are silenced at the Alertmanager route; remove that
  route in a real cluster so infra alerts reach the incident pipeline.
