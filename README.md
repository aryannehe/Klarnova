# Klarnova

> **AI-driven Kubernetes incident response** — detect, diagnose, get approval, and remediate failures automatically, then learn from every incident.

Klarnova is an AI-powered SRE assistant that watches your cluster through Prometheus/Alertmanager, turns alerts into structured incidents, runs a multi-agent investigation to find the root cause, proposes a safe remediation, and executes it — subject to a declarative risk policy and human approval when needed. Every outcome feeds a contextual bandit that learns which action works best per incident type, and resolved incidents are written back into a knowledge base so the system gets smarter over time.

---

## Table of Contents

- [Highlights](#highlights)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
  - [A. Local development](#a-local-development)
  - [B. Docker Compose](#b-docker-compose)
  - [C. Kubernetes demo (minikube + Sock Shop)](#c-kubernetes-demo-minikube--sock-shop)
- [Configuration](#configuration)
- [Safety & policy](#safety--policy)
- [Learning](#learning)
- [Knowledge base (RAG)](#knowledge-base-rag)
- [API overview](#api-overview)
- [Operator dashboard](#operator-dashboard)
- [kubectl plugin](#kubectl-plugin)
- [Testing & CI](#testing--ci)
- [Evaluation & chaos testing](#evaluation--chaos-testing)
- [Documentation](#documentation)
- [Contributors](#contributors)

---

## Highlights

- **End-to-end automation** — from Alertmanager webhook to resolved incident with zero human touch for low-risk cases.
- **Multi-agent investigation** — a LangGraph pipeline performs log collection, retrieval-augmented diagnosis, root-cause analysis, action planning, and safety gating before anything executes.
- **Human-in-the-loop** — a declarative policy engine decides *auto vs. require approval* per action/severity, with a hard rule that **SEV-1 always needs approval**.
- **Self-improving** — a contextual multi-armed bandit (MABWiser) learns the best remediation per incident category, and write-back grows a vector knowledge base from resolved incidents.
- **RAG knowledge base** — ChromaDB + `bge-small-en-v1.5` embeddings over curated runbooks, historical incidents, and Kubernetes docs.
- **Operator dashboard** — Next.js app with incidents, approvals, analytics, cluster overview, and settings.
- **Drop-in monitoring** — a tuned `kube-prometheus-stack` values file routes alerts straight into Klarnova.
- **Runs anywhere** — Helm chart for in-cluster deployment (minikube, EKS, AKS, GKE) or pure local dev.

---

## How it works

1. **Ingest** — Prometheus evaluates alerting rules and Alertmanager pushes notifications to `POST /v1/webhooks/alertmanager`. Klarnova deduplicates, classifies severity, and creates an `Incident`.
2. **Investigate** — a LangGraph investigation graph runs:
   `investigation → retrieval → root_cause → planning → safety`
   - gather pod events, logs, and metrics
   - retrieve relevant runbooks from the knowledge base
   - produce an evidence-grounded root-cause diagnosis with a confidence score
   - rank candidate remediation actions
   - apply the risk policy and decide `auto` vs `require_approval`
3. **Approve** — if approval is required (policy or low confidence), the action waits for an operator via the dashboard or API.
4. **Remediate** — a second graph runs `remediation → validation → reporting`, applying the approved Kubernetes action (restart, delete, scale, rollback, cordon) and verifying recovery.
5. **Learn** — the outcome (resolved / failed) becomes a bandit reward sample for that incident category, and the resolved incident is written back to the historical knowledge base.

---

## Architecture

```
                         +---------------------------------------------+
   Prometheus            |              Klarnova Backend               |
    + alerting rules     |                (FastAPI)                    |
        |                |                                             |
        v                |   /v1/webhooks/alertmanager  (dedup + sev)  |
   Alertmanager  ------> |            |                                 |
   (webhook + token)     |            v                                |
                         |   +----------------------------+            |
                         |   |   INVESTIGATION GRAPH      |            |
                         |   | investigation -> retrieval |            |
                         |   | -> root_cause -> planning  |            |
                         |   | -> safety                  |            |
                         |   +-------------+--------------+            |
                         |                 |                           |
                         |                 v                           |
                         |   +----------------------------+            |
                         |   |   POLICY ENGINE            |            |
                         |   |   auto | require_approval  |            |
                         |   +-------------+--------------+            |
                         |                 |  (operator approval via   |
                         |                 |   dashboard / API)        |
                         |                 v                           |
                         |   +----------------------------+            |
                         |   |   REMEDIATION GRAPH        |            |
                         |   | remediation -> validation  |            |
                         |   | -> reporting               |            |
                         |   +-------------+--------------+            |
                         |                 |                           |
                         +-----------------|---------------------------+
                                           v
                 +-----------------+   +----------------+   +-----------------+
                 |  Kubernetes API |   |  PostgreSQL    |   |  ChromaDB (RAG) |
                 |  (in-cluster /  |   |  incidents,    |   |  runbooks,      |
                 |   kubeconfig)   |   |  runs, bandit, |   |  history, docs  |
                 |                 |   |  audit log     |   |                 |
                 +-----------------+   +----------------+   +-----------------+

                +------------------------------------------------------+
                |  Operator dashboard (Next.js)  +  kubectl-klarnova   |
                +------------------------------------------------------+
```

---

## Tech stack

| Layer       | Technology |
|-------------|------------|
| Backend     | Python 3.13 · FastAPI · SQLAlchemy 2 (async) · asyncpg · Alembic |
| Orchestration | LangGraph · LangChain · langchain-ollama |
| LLM         | Ollama (`llama3.2:3b` default) · OpenAI · Gemini (switchable via config) |
| RAG         | ChromaDB · `BAAI/bge-small-en-v1.5` embeddings |
| Learning    | MABWiser (Epsilon-Greedy + k-Nearest contextual bandit) |
| Storage     | PostgreSQL (SQLite fallback for tests) |
| Frontend    | Next.js 16 · React 19 · Tailwind CSS v4 · shadcn/ui · Recharts |
| Kubernetes  | kube-prometheus-stack (Prometheus + Alertmanager + Grafana) · Helm |
| Demo app    | Sock Shop (microservices-demo) on minikube |
| CI/CD       | GitHub Actions (ruff + pytest · eslint + tsc + build) |

---

## Repository layout

```
.
├── backend/                FastAPI application
│   ├── app/
│   │   ├── agents/         LangGraph agents (investigation, retrieval, root_cause,
│   │   │                   planning, safety, remediation, validation, reporting, monitoring)
│   │   ├── api/v1/         REST endpoints (auth, incidents, actions, webhooks, kubernetes, config)
│   │   ├── bandit/         MABWiser contextual bandit + learning
│   │   ├── core/           settings, database, security
│   │   ├── k8s/            Kubernetes client + actions, events, logs, metrics
│   │   ├── policy/         Risk policy engine + declarative rules
│   │   ├── rag/            ChromaDB store, ingest, embedder, write-back
│   │   ├── models/         SQLAlchemy models
│   │   └── schemas/        Pydantic schemas
│   └── tests/              Backend test suite
├── frontend/               Next.js operator dashboard
├── helm/klarnova/          Helm chart for in-cluster deployment
├── k8s/                    Namespaces, monitoring values, RBAC, sample-app manifests
├── scripts/                setup.sh · inject-failure.sh · demo.sh/demo.py · reset.sh · seed.py
├── cli/                    kubectl-klarnova plugin
├── knowledge-base/         RAG sources (runbooks, historical incidents, Kubernetes docs)
├── chaos-testing/          Offline evaluation + chaos scenarios
├── docs/                   Design, API reference, walkthrough, evaluation results
└── docker-compose.yml      Compose-based local run
```

---

## Prerequisites

- **Docker** (for image builds and Docker Desktop-based minikube)
- **Minikube** + **kubectl** (for the cluster demo) — or any cluster with `kube-prometheus-stack`
- **Helm** v3
- **Python 3.13** (backend)
- **Node.js 22+** (frontend)
- **PostgreSQL** running locally on `localhost:5432` (database `klarnova`)
- **Ollama** on `localhost:11434` with `llama3.2:3b` pulled (or OpenAI/Gemini key)

---

## Quick start

### A. Local development

Backend — run from the `backend/` directory (config reads `.env` relative to cwd):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item ..\.env.example .env        # adjust secrets
.\.venv\Scripts\uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev -- -p 3001
```

- Backend API: <http://localhost:8000> (interactive docs at <http://localhost:8000/docs>)
- Dashboard: <http://localhost:3001> — default login `admin` / `admin123`
- CORS is pre-configured for `localhost:3000` and `localhost:3001`.

> **Note:** local dev runs against your kubeconfig (`KUBE_IN_CLUSTER=false`); an Ollama/Postgres instance must be reachable on the host.

### B. Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Compose exposes the backend on `:8000` and frontend on `:3000`. Services expect Postgres, Redis, and Ollama on the host via `host.docker.internal`.

### C. Kubernetes demo (minikube + Sock Shop)

Run the full self-healing demo on a single minikube cluster. From **Git Bash** in the repo root (or PowerShell for the kubectl/helm lines):

```bash
minikube start
kubectl apply -f k8s/namespace.yaml
kubectl create namespace monitoring

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring -f k8s/monitoring/kube-prometheus-stack-values.yaml

# Speed up the crash-loop alert for the demo (15m -> 1m)
kubectl -n monitoring patch prometheusrule kube-prometheus-stack-kubernetes-apps \
  --type=json --patch='[{"op":"replace","path":"/spec/groups/0/rules/0/for","value":"1m"}]'

# Deploy the demo application
kubectl apply -n sock-shop -f https://raw.githubusercontent.com/microservices-demo/microservices-demo/master/deploy/kubernetes/complete-demo.yaml

# Build, load, and deploy Klarnova
bash scripts/setup.sh

# Expose the API
kubectl -n default port-forward svc/klarnova-backend 8000:8000
```

Then run the live demo — inject a crash-loop into Sock Shop's `catalogue`, let Klarnova diagnose it, approve the rollback, and watch it resolve:

```bash
bash scripts/inject-failure.sh sock-shop catalogue alpine:3.18
backend/.venv/Scripts/python.exe scripts/demo.py
bash scripts/reset.sh
```

`demo.py` prints the investigation trace, the operator approval, the resolved status, and the bandit policy rows learned.

> **Gotchas**
> - Klarnova pod stuck on `ImagePullBackOff` → `minikube image load klarnova-backend:latest` then `kubectl -n default rollout restart deployment/klarnova`.
> - No incident after ~2 minutes → confirm the PrometheusRule patch above and that the port-forward is still alive.
> - Postgres/Ollama must run on the **host**; the chart reaches them via `host.minikube.internal`.

---

## Configuration

Copy `.env.example` to `backend/.env` (or the repo root `.env`) and adjust. Key settings:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `ollama` | `ollama` \| `openai` \| `gemini` |
| `LLM_MODEL` | `llama3.2:3b` | Model used for diagnosis/planning |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/klarnova` | PostgreSQL (asyncpg) |
| `CHROMA_PERSIST_DIR` | `data/chroma` | ChromaDB persistence directory |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model |
| `KUBE_IN_CLUSTER` | `false` | `true` inside a cluster (service account), `false` for kubeconfig |
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus API (metrics) |
| `ALERTMANAGER_WEBHOOK_TOKEN` | `dev-token` | Bearer token expected on the Alertmanager webhook |
| `JWT_SECRET` | `change-me-in-production` | JWT signing secret |
| `KB_SOURCE_LIST` | `knowledge-base/sources.yaml` | RAG source manifest |
| `KB_REFRESH_INTERVAL` | `3600` | Knowledge-base re-ingest interval (seconds) |

> **RAG embeddings are optional.** The backend image installs the ML/RAG stack only when built with `--build-arg INSTALL_ML=true` (adds several GB / minutes). Without it the retrieval agent degrades gracefully and the pipeline falls back to heuristic diagnosis and planning.

---

## Safety & policy

Risk policy is declarative and severity-aware (`backend/app/policy/rules/default.yaml`):

| Action | SEV-4 | SEV-3 | SEV-2 | SEV-1 |
|--------|-------|-------|-------|-------|
| `restart_pod` | auto | auto | auto | **approval** |
| `delete_pod` | auto | auto | auto | **approval** |
| `scale_deployment` | auto | auto | approval | **approval** |
| `rollback_deployment` | auto | approval | approval | **approval** |
| `cordon_node` | approval (always) | | | |

- **Hard rule:** SEV-1 always requires approval, regardless of policy table or confidence.
- **Confidence gate:** when the diagnosis confidence is below `confidence_threshold` (0.75), the proposed action requires approval even if the table says `auto`.
- All executed actions are recorded in the audit log; Kubernetes changes go through `backend/app/k8s/actions.py`.

---

## Learning

The bandit (`backend/app/bandit/`) uses MABWiser with Epsilon-Greedy + k-Nearest neighbors. Context features include severity, unavailable replicas, and restart count. Each incident resolution updates the policy:

- **reward = 1.0** when the chosen action resolves the incident, **0.0** when it fails
- priors encode expert bias (e.g., `restart` > `delete` > `scale` > `rollback` > `cordon`) and are replaced by experience as the system sees more incidents
- learned rows are persisted to `bandit_policies` in PostgreSQL and seeded at startup

---

## Knowledge base (RAG)

- **Sources** are declared in `knowledge-base/sources.yaml` — curated **runbooks**, **historical incidents**, and **Kubernetes docs**.
- **Ingestion** embeds documents into ChromaDB (`backend/app/rag/ingest.py`); the backend re-ingests on startup and on an interval (`KB_REFRESH_INTERVAL`), or on demand via `POST /v1/config/knowledge/refresh`.
- **Retrieval** during investigation surfaces the most relevant runbook to the diagnosis and planning agents (relevance-gated at `HINT_RELEVANCE_DISTANCE = 0.55`).
- **Write-back** (`backend/app/rag/writeback.py`) embeds resolved incidents into the `historical_incidents` collection so the knowledge base grows with real experience.

---

## API overview

All endpoints are under `/v1` (interactive docs at `/docs`):

| Area | Endpoints |
|------|-----------|
| Auth | `POST /v1/auth/login` |
| Incidents | `GET /v1/incidents` · `GET /v1/incidents/{id}` · `GET /v1/incidents/{id}/trace` |
| Actions | `POST /v1/actions/approve` · action execution |
| Webhooks | `POST /v1/webhooks/alertmanager` (Bearer token) |
| Kubernetes | cluster/resources inspection |
| Config | `GET/POST /v1/config/*` · `POST /v1/config/knowledge/refresh` |

See [docs/api-reference.md](docs/api-reference.md) for the full reference.

---

## Operator dashboard

The Next.js dashboard (`frontend/app/(dashboard)/`) provides:

- **Incidents** — live list + per-incident investigation trace and status
- **Approvals** — review and approve/deny proposed remediations
- **Analytics** — resolution metrics and bandit/learning trends
- **Cluster** — namespace/resource overview
- **Settings** — configuration view

Default login: `admin` / `admin123`.

---

## kubectl plugin

A `kubectl` plugin provides incident response from the terminal:

```bash
export PATH="$PWD/cli:$PATH"
kubectl klarnova incidents
kubectl klarnova incidents <id> --trace
```

See [cli/README.md](cli/README.md).

---

## Testing & CI

```powershell
# Backend
cd backend && .\.venv\Scripts\pytest          # test suite
cd backend && .\.venv\Scripts\ruff check .    # lint

# Frontend
cd frontend
npm run lint
npx next typegen && npx tsc --noEmit
npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs backend lint + tests and frontend lint + typecheck + build on every push/PR.

---

## Evaluation & chaos testing

`chaos-testing/` contains an offline evaluation harness and chaos scenarios:

- **Offline eval** (`offline.py`) replays curated incident scenarios against the agent pipeline with fixed seeds.
- **Component ablation** (`ablation.py`) measures the contribution of each agent to resolution quality.
- **Scenarios** are defined in `scenarios.yaml` (e.g., crash-looping, image-pull failures, probe failures).
- Results and methodology are tracked in [docs/evaluation.md](docs/evaluation.md) and [docs/evaluation-results.md](docs/evaluation-results.md).

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/understanding-klarnova.md](docs/understanding-klarnova.md) | Newcomer's guide — concepts, flow, and how parts connect |
| [docs/implementation-plan.md](docs/implementation-plan.md) | Roadmap & implementation status |
| [docs/Klarnova_Technical_Architecture.md](docs/Klarnova_Technical_Architecture.md) | Deep-dive architecture |
| [docs/api-reference.md](docs/api-reference.md) | API reference |
| [docs/walkthrough.md](docs/walkthrough.md) | Guided demo walkthrough |
| [docs/evaluation.md](docs/evaluation.md) · [docs/evaluation-results.md](docs/evaluation-results.md) | Evaluation methodology & results |
| [docs/cloud-deployment.md](docs/cloud-deployment.md) | EKS / AKS / GKE deployment |
| [docs/Klarnova_Security_Access.md](docs/Klarnova_Security_Access.md) | Security model & access |
| [docs/Klarnova_PRD.md](docs/Klarnova_PRD.md) | Product requirements |

---

## Contributors

- Aryan
- Piyush
- Shravani
- Gayatri
- Om

See [docs/CONTRIBUTORS.md](docs/CONTRIBUTORS.md).
