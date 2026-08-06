# Klarnova_Technical_Architecture

KLARNOVA

Technical Architecture Document

A Plug-and-Play, AI-Powered AIOps Platform for Kubernetes

System design, technology stack, data stores, repository structure, and configuration management

Final Year BE Project  Â·  Version 1.0  Â·  2026

1.  Architecture Overview

Klarnova is a standalone, cloud-portable service that deploys into a Kubernetes cluster and manages incidents on the workloads running there. It is organised in five layers, each with a distinct responsibility.

Layer

Responsibility

Presentation

Next.js dashboard for incident review, agent-reasoning traces, approvals, and analytics; optional kubectl plugin as a thin client.

API & Orchestration

FastAPI service exposing REST endpoints; LangGraph state machine coordinating the nine agents.

Intelligence

LLM reasoning (root cause, planning, reporting), RAG retrieval, and the contextual-bandit action-selection layer.

Data & State

PostgreSQL (incidents, audit, policy, users), Redis (cache, queues), ChromaDB (vector knowledge base).

Integration

Kubernetes API (via scoped ServiceAccount), Prometheus, Alertmanager, and live documentation sources.

Design principle: generative LLM reasoning is concentrated in three agents (Root Cause, Planning, Reporting). Detection, risk classification, execution, and validation are deterministic and rule-based, so the platformâ€™s safety guarantees never depend on probabilistic model output.

2.  Technology Stack

Versions reflect current stable releases and should be pinned at project kickoff, then held fixed for the duration to keep the environment reproducible across the team.

2.1  Frontend

Technology

Version

Role

Node.js

24.x LTS

Runtime for the frontend build toolchain

Next.js

16.x

React framework, App Router

React

19.x

UI library (bundled with Next.js)

TypeScript

5.7+

Typed JavaScript

Tailwind CSS

4.x

Utility-first styling

shadcn/ui

CLI-installed

Component primitives (copied into repo)

Recharts

2.x

MTTD / MTTR / trend charts

2.2  Backend

Technology

Version

Role

Python

3.12 / 3.13

Backend language (3.12/3.13 for ML lib compatibility)

FastAPI

latest

REST API framework

Uvicorn

latest

ASGI server (uvicorn[standard])

Pydantic

2.x

Schemas / validation (the shared contract)

SQLAlchemy

2.x

ORM (async engine, asyncpg driver)

Alembic

1.x

Database migrations

2.3  AI, Agents & RAG

Technology

Version

Role

LangGraph

1.2.x

Multi-agent orchestration state machine

LangChain

1.3.x

LLM tooling / integrations

OpenAI SDK

1.x

Cloud LLM provider path

Ollama

latest

Local LLM path (cost/rate-limit fallback)

sentence-transformers

3.x / 4.x

Embeddings (all-MiniLM-L6-v2)

ChromaDB

1.5.x

Vector database

2.4  Infrastructure & Observability

Technology

Version

Role

Docker

29.x

Containerisation

Kubernetes

1.33â€“1.34

Orchestration (Kind/Minikube dev, managed cloud final)

Helm

4.2.x

Packaging & deployment

Prometheus

3.x

Metrics (via kube-prometheus-stack)

Alertmanager

latest

Alert routing â†’ Klarnova webhook

Grafana

13.x

Dashboards (existing tool Klarnova reads from)

Loki

3.x (optional)

Log aggregation; logs also read via K8s API

Recommendation: install the monitoring stack via the kube-prometheus-stack Helm chart â€” it bundles Prometheus, Alertmanager, Grafana, kube-state-metrics, and node-exporter together, dramatically reducing the YAML you maintain.

3.  Data Stores

Klarnova uses three complementary stores. Each has a distinct role; conflating them would create bottlenecks.

3.1  PostgreSQL â€” system of record

The relational store for all structured operational data. Chosen over SQLite (used by comparable academic prototypes) because incident ingestion, dashboard reads, and agent writes are concurrent.

Table

Holds

incidents

Incident record: severity, priority, status, timestamps, affected resource, root cause, confidence

agent_runs

Per-agent execution trace for a given incident (inputs, outputs, timing) â€” powers the dashboard trace view

remediations

Action taken, incident_category, outcome, time_to_resolve â€” also the reward source for the contextual bandit

bandit_policy

Per (incident_category, action) learned reward and update count

policies

Risk rules: which actions are auto-approved vs. require sign-off, by severity

users

Accounts and role (Admin / Engineer / Viewer)

audit_log

Every significant action by agents and humans â€” detection, retrieval, recommendation, approval, execution, outcome

knowledge_docs

Metadata + source URL + content hash for ingested docs (freshness tracking for live-refresh)

3.2  ChromaDB â€” vector knowledge base

The semantic store the Retrieval Agent searches. Runbooks and documentation are ingested from live source URLs on a schedule, chunked, embedded with all-MiniLM-L6-v2, and upserted here. Retrieval at incident time is fast and offline.

Aspect

Design

Collections

runbooks, historical_incidents, kubernetes_docs (separated so retrieval can weight by source type)

Embedding model

all-MiniLM-L6-v2 (384-dim) via sentence-transformers

Metadata per chunk

source_url, doc_type, last_ingested, content_hash, chunk_index

Refresh strategy

Scheduled ingestion; content_hash compared before re-embedding to skip unchanged docs

Search filters

By collection and doc_type; retrieve top-k with similarity threshold

3.3  Redis â€” cache & queue

In-memory store for transient state, keeping Postgres unburdened by high-frequency reads and background work.

Caching of recent metric snapshots and frequently-read dashboard data.

Task queue / broker for background jobs â€” notably the scheduled knowledge-base ingestion.

Short-lived agent-run state and rate-limit counters for LLM calls.

4.  Repository Structure

A monorepo. The backend service is the substantial system; the frontend is the operator surface; the CLI plugin is a thin client of the API, built last. Abbreviated to the significant paths:

klarnova/â”œâ”€ docker-compose.yml        # backend + frontend + postgres + redis + chromadb + ollamaâ”œâ”€ Makefile                  # make dev / test / seed / demo / resetâ”œâ”€ docs/                     # architecture, agent-design, api-reference, evaluationâ”‚â”œâ”€ backend/                  # CORE SERVICEâ”‚  â””â”€ app/â”‚     â”œâ”€ main.py  config.py  dependencies.pyâ”‚     â”œâ”€ api/v1/endpoints/  # auth, incidents, diagnose, remediate, webhooks, ...â”‚     â”œâ”€ agents/           # graph.py, state.py + 9 agent modules + prompts/â”‚     â”œâ”€ bandit/           # policy store, reward, update (contextual bandit)â”‚     â”œâ”€ rag/              # embeddings, chroma_client, ingest, retrieverâ”‚     â”œâ”€ k8s/              # client, metrics, events, logs + actions/â”‚     â”œâ”€ discovery/        # auto-discovery & auto-configuration moduleâ”‚     â”œâ”€ policy/           # engine.py + rules/ (severity-aware risk rules)â”‚     â”œâ”€ core/             # security (JWT), rbac, databaseâ”‚     â”œâ”€ models/  schemas/ # SQLAlchemy ORM  +  Pydantic (shared contract)â”‚     â””â”€ services/         # orchestrator, notification, analyticsâ”‚â”œâ”€ frontend/                 # Next.js dashboard (app/, components/, lib/, hooks/)â”œâ”€ cli/                      # kubectl plugin (thin API client â€” build last)â”œâ”€ sample-app/               # intentionally-breakable microservicesâ”œâ”€ k8s/                      # namespace, rbac/, sample-app, monitoring/â”œâ”€ helm/klarnova/            # Chart.yaml, values.yaml, templates/â”œâ”€ knowledge-base/           # runbook/doc source list + ingest scriptâ”œâ”€ chaos-testing/            # scenarios/, run_experiments.py, ablation.py, results/â””â”€ scripts/                  # setup, seed, inject-failure, reset, demo

Note the two additions to the agent core: the bandit/ module (contextual-bandit policy, reward, and update logic) and the discovery/ module (auto-discovery for plug-and-play deployment). Both are deterministic and sit outside the LLM path.

5.  Configuration Management

Configuration is layered: environment variables for deployment-specific values and secrets, YAML for policy and discovery rules, and Helm values for cluster deployment. Nothing sensitive is committed to the repository.

5.1  Environment variables

Variable group

Examples / purpose

LLM provider

LLM_PROVIDER (openai|ollama), OPENAI_API_KEY, OLLAMA_BASE_URL, LLM_MODEL

Databases

DATABASE_URL (Postgres), REDIS_URL, CHROMA_HOST / CHROMA_PORT

Kubernetes

KUBE_IN_CLUSTER (true in-cluster), KUBECONFIG (dev), target namespace(s)

Observability

PROMETHEUS_URL, ALERTMANAGER_WEBHOOK_TOKEN, LOKI_URL (optional)

Auth

JWT_SECRET, JWT_EXPIRY, token signing algorithm

Knowledge base

KB_REFRESH_INTERVAL, KB_SOURCE_LIST (path to source-URL config)

Notifications

SLACK_WEBHOOK_URL, SMTP settings for email escalation

Secrets (API keys, JWT secret, DB credentials, webhook tokens) are supplied via .env locally and Kubernetes Secrets in-cluster â€” never hard-coded. A committed .env.example documents every variable without real values.

5.2  Policy configuration (YAML)

The risk engine is driven by declarative rules, not code, so behaviour can be tuned without redeployment. Rules map (action, severity) to an execution mode.

# policy/rules/default.yamlactions:  restart_pod:    sev_4: auto    sev_3: auto    sev_2: auto    sev_1: require_approval    # severity raises the bar for the same action  rollback_deployment:    sev_4: auto    sev_3: require_approval    sev_1: require_approval  cordon_node:    default: require_approval  # always human-gatedconfidence_threshold: 0.75     # below this, route to human regardless

5.3  Knowledge-base source configuration

Live documentation sources are declared as a list of URLs with refresh cadence, enabling the continuously-refreshed RAG layer.

# knowledge-base/sources.yamlsources:  - url: https://kubernetes.io/docs/...    type: kubernetes_docs    refresh_hours: 24  - url: https://<org-runbook-host>/oom.md    type: runbook    refresh_hours: 6

5.4  Helm values

Deployment-time configuration for the cluster: image tags, replica counts, resource requests/limits, the LLM provider default, ingress host, and references to the Secret and ServiceAccount. A single values.yaml per environment (local, cloud) keeps deployments reproducible.

5.5  Kubernetes RBAC

Klarnova acts on the cluster through a dedicated ServiceAccount bound to a scoped ClusterRole â€” granting only the verbs its remediation actions require: get/list/watch on pods, deployments, and nodes; patch/delete on pods; patch on deployments (scale, rollback) and nodes (cordon). This least-privilege boundary is a security feature, not boilerplate: even a faulty remediation cannot exceed these permissions.

6.  Configuration Management Principles

Principle

Practice

No secrets in git

.env (local) and Kubernetes Secrets (cluster) only; .env.example documents the shape

Pin versions early

Lock requirements.txt and package-lock.json at kickoff; upgrade only deliberately

Declarative over code

Risk policy, KB sources, and severity mapping live in YAML, tunable without redeployment

One source of truth per env

A single Helm values file per environment (local / cloud)

Least privilege

Scoped ServiceAccount + ClusterRole; JWT + three-role RBAC on the API

Provider-agnostic

Only the standard Kubernetes API is used â€” no cloud-specific calls, so the same config runs on Kind or managed cloud

Reproducibility rule: a new team member should be able to clone the repo, copy .env.example to .env, fill in secrets, and run a single make command to bring the full stack up locally. Every deviation from that ideal is configuration debt to be fixed, not worked around.
