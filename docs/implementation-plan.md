# Klarnova Implementation Plan v2

The objective is to implement Klarnova, a Plug-and-Play, AI-Powered AIOps Platform for Kubernetes. This plan has been reconciled against the PRD, Security, and Technical Architecture documents, as well as the actual state of the repository.

## Locked Decisions & Environment Constraints
- **Cluster**: Minikube (docker driver, K8s v1.34.1). *Note: Docker Desktop is currently stopped and needs to be restarted.*
- **Chaos Target**: Sock Shop (14 pods) — already deployed.
- **Backend Placement**: Kubernetes Deployment in-cluster.
- **Loki**: Deferred — use K8s API logs (`--previous`) to save memory.
- **LLM**: Ollama with `llama3.2:3b` (OpenAI/Gemini switchable via `.env`) — already running.
- **RAG**: ChromaDB in-process + `BAAI/bge-small-en-v1.5` — already working and persisted.
- **Database**: pgvector Postgres 15.4, `klarnova` DB — already created.
- **Repo State**: The directory structure and all `.py` files exist but are **empty** (0 bytes). We are filling the skeletons, not creating them.

### Version Reconciliations
- **Node**: Keep v22.19.0 (diverges from TAD's 24.x LTS, but is stable for Next 16).
- **Helm**: Keep v4.2.3 (diverges from TAD's 3.21.x, syntax is compatible).
- **Sentence-Transformers**: Keep v5.6.1 (newer than TAD's 3/4.x).
- **Embedding Model**: Keep `bge-small-en-v1.5` (already downloaded & verified, diverges from TAD).
- **KB Scheduler**: Use **asyncio task** instead of Celery worker to avoid Windows multiprocessing traps.

## Pre-flight (P0, do first)
- **Start Docker Desktop**: Wait for minikube Ready → re-verify monitoring + Sock Shop 14/14.
- **Dependencies**: `pip install python-jose ruff` into `backend/.venv`.
- **Make**: Install GNU Make (`winget install GnuWin32.Make`).
- **Security**: Create `.gitignore` to protect `.env`, `.venv/`, `data/`, `node_modules/`, `*.kubeconfig`, `chaos-testing/results/`.
- **Frontend**: Run `npx shadcn@latest init` + `npm i recharts`.
- **Alertmanager**: Patch `kube-prometheus-stack-values.yaml` to route to `http://klarnova-backend.<ns>.svc:8000/v1/webhooks/alertmanager` with `ALERTMANAGER_WEBHOOK_TOKEN` header.

## Phase A — Foundations & Contracts (KLR-A1–A9)
- **Contracts**: Freeze `agents/state.py` (LangGraph 1.x TypedDict + Annotated reducers) and schemas (incident must include `created_at` → `detected_at` → `remediated_at` for MTTD/MTTR ablation studies, diagnosis, remediation, agent, auth).
- **Backend Skeleton**: Fill `app/config.py` → `app/main.py` (FastAPI, CORS for `:3000`, `/health`, `/ready`) → `app/core/database.py` (async SQLAlchemy). Fill `app/models/*` (8 ORM tables) + first Alembic migration.
- **Tooling**: Fill `Makefile` (setup/dev/test/lint/seed/demo/deploy) and `docker-compose.yml`.
- **Frontend Skeleton**: Wire default Next page to backend `/health`.

## Phase B — Cluster, Monitoring, Sample (KLR-B1–B7)
- **Verify**: Cluster + `kube-prometheus-stack` + Sock Shop.
- **RBAC**: Build `k8s/rbac/` ServiceAccount + least-privilege ClusterRole (pods get/list/watch/delete, deployments get/list/watch/patch, nodes get/list/watch/patch (cordon), events get/list/watch, pods/log).
- **Scripts**: Build `scripts/inject-failure.sh` + `setup.sh`.

## Phase C — Ingestion & Detection (KLR-C1–C7)
- **K8s Client**: Fill `k8s/client.py` and `k8s/metrics.py` (PromQL: up, unavailable replicas, restart counters).
- **Auto-Discovery**: `discovery/discovery.py` detects K8s API + Prometheus.
- **Webhook Integration**: `api/v1/endpoints/webhooks.py` token-protected Alertmanager receiver.
- **Detection & Classification**: `agents/monitoring.py` + `agents/graph.py` (Monitoring → decision); severity classification SEV-1…4/P1…4.

## Phase D — Investigation & RAG (KLR-D1–D8)
- **Data Collection**: Fill `k8s/logs.py` (`--previous`) and `k8s/events.py`.
- **Investigation Agent**: `agents/investigation.py` (rule-match first, Ollama fallback).
- **Knowledge Base & RAG**: `rag/chroma_client.py`, `rag/embeddings.py`, `rag/ingest.py`, `rag/retriever.py`.
- **Seeding**: Fill `knowledge-base/sources.yaml` + `seed.py` (30–50 runbooks mapped to chaos scenarios + historical incidents for bandit warm-start).
- **Live-refresh**: Scheduled asyncio task with content-hash diff.

## Phase E — Reasoning, Planning, Bandit (KLR-E1–E8)
- **LLM Client**: `E1` abstraction layer (Ollama default, OpenAI/Gemini drop-in).
- **Agents**: `E2` Root Cause (cause + confidence), `E3` versioned prompt templates, `E4` Planning (ranked candidates).
- **Bandit**: `E5–E7` MABWiser 2.7.4. Policy in `bandit_policy` table. Reward = Validation outcome + MTTR delta. Seed priors from runbooks.
- **Safety Gate**: `E8` confidence gate (below threshold → human regardless of risk tier).

## Phase F — Safety, Remediation, Validation (KLR-F1–F10)
- **Policy Engine**: `policy/engine.py` + `policy/rules/default.yaml` (action × severity → auto/require_approval). SEV-1 always requires approval.
- **Remediation Actions**: Fill 5 action modules (restart_pod, scale_deployment, rollback_deployment, delete_pod, cordon_node) → safe-action whitelist only.
- **Agents**: `safety.py` → `remediation.py` → `validation.py` (re-check pods Ready + Prometheus) → retry-then-escalate.
- **Reporting & Audit**: `reporting.py` (closes RAG loop). `F10` append-only `audit_log` writer on every agent + human action.

## Phase G — Dashboard & Auth (KLR-G1–G9)
- **Security**: `core/security.py` (JWT, bcrypt), `core/rbac.py` (Admin/Engineer/Viewer).
- **Frontend Views**: Login flow → incident feed (with SEV/P badges) → agent reasoning trace → approval panel → MTTD/MTTR analytics.

## Phase H — Packaging, Cloud, Plugin (KLR-H1–H5)
- **Dockerization**: Backend Dockerfile (optimize for `torch` size), frontend Dockerfile.
- **Helm Chart**: `helm/klarnova/` chart.
- **Validation**: Test the single-command install.

## Phase I — Evaluation & Hardening (KLR-I1–I7)
- **Chaos Testing**: `chaos-testing/run_experiments.py` and `ablation.py`.
- **Hardening**: Ensure graceful degradation during LLM/vector-DB/K8s/DB/Prometheus outages.
- **Demo**: `scripts/demo.sh` + `reset.sh`.

## Verification Plan (DoD per phase)
- **Automated**: `ruff check` + `pytest` + `tsc --noEmit`.
- **End-to-End**: Inject failure in Sock Shop → alert → webhook → classified incident → investigate → RAG → root cause → plan → safety gate → auto-remediate (low risk) or approve (high/SEV-1) → validate → report → KB write-back.
