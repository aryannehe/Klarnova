# Klarnova — Feature Ticket Backlog

A working breakdown of the committed PRD scope into small, executable tickets.
Each ticket is intended to be a few days of work at most. Tickets are grouped into **Epics**,
sequenced into **Phases** that map to the six-month plan, and tagged with **priority** and
**dependencies** so the team always knows what is safe to pick up next.

---

## How to read this backlog

**Priority**
- `P0` — Blocking. Nothing meaningful proceeds until this is done.
- `P1` — Core. Part of the committed MVP; must ship.
- `P2` — Important. Strongly wanted, but the system works without it if time runs out.
- `P3` — Nice-to-have. Cut first under pressure.

**Status** (fill in as you go): `todo` · `in-progress` · `review` · `done` · `blocked`

**Ticket ID** format: `KLR-<epic><number>` (e.g. `KLR-A1`).

**The golden rule of sequencing:** freeze the shared contracts (`state.py`, Pydantic schemas,
API shapes) in Phase 0 before anyone builds against them. Most integration pain comes from
skipping this.

---

## Epic map

| Epic | Theme | Phase(s) |
|---|---|---|
| A | Foundations & contracts | Phase 0 (Month 1) |
| B | Cluster, monitoring & sample workloads | Phase 0–1 (Month 1–2) |
| C | Ingestion & detection pipeline | Phase 1 (Month 2) |
| D | Investigation & RAG | Phase 2 (Month 3) |
| E | Reasoning, planning & the bandit | Phase 2–3 (Month 3–4) |
| F | Safety, remediation & validation | Phase 3 (Month 4) |
| G | Dashboard & auth | Phase 4 (Month 5) |
| H | Packaging, cloud & plugin | Phase 4–5 (Month 5–6) |
| I | Evaluation & hardening | Phase 5 (Month 6) |

---

## Epic A — Foundations & Contracts  *(Phase 0 · Month 1)*

> Everything downstream depends on these. Do them first, freeze them, resist changing them.

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-A1 | Initialise monorepo, branching model, `CONTRIBUTORS.md`; ensure every teammate has a first commit on `main` | P0 | — |
| KLR-A2 | Set up `docker-compose` for local dev (backend, frontend, postgres, redis, chromadb, ollama) | P0 | A1 |
| KLR-A3 | Define and **freeze** the shared `AgentState` schema (`agents/state.py`) | P0 | A1 |
| KLR-A4 | Define and **freeze** core Pydantic schemas (incident, diagnosis, remediation, agent, auth) | P0 | A1 |
| KLR-A5 | Stand up FastAPI skeleton with health/readiness endpoints and config loader | P0 | A2 |
| KLR-A6 | Postgres schema + first Alembic migration (incidents, agent_runs, remediations, bandit_policy, policies, users, audit_log, knowledge_docs) | P0 | A5 |
| KLR-A7 | Next.js skeleton wired to backend; a single page fetching `/health` to prove the loop | P1 | A5 |
| KLR-A8 | `Makefile` targets (`dev`, `test`, `seed`, `reset`) + `.env.example` documenting every variable | P1 | A2 |
| KLR-A9 | CI: lint + test workflows for backend and frontend | P2 | A5, A7 |

**Phase 0 exit criteria:** cluster-less local stack boots with one command; schemas frozen; skeleton frontend talks to skeleton backend.

---

## Epic B — Cluster, Monitoring & Sample Workloads  *(Phase 0–1 · Month 1–2)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-B1 | Provision local cluster (Kind or Minikube) + setup script | P0 | A1 |
| KLR-B2 | Install monitoring stack via `kube-prometheus-stack` Helm chart | P0 | B1 |
| KLR-B3 | Build three intentionally-breakable sample microservices (api-gateway, user-service, database-service) with structured JSON logging | P1 | B1 |
| KLR-B4 | Deploy sample apps (manifests + configmap) | P1 | B1, B3 |
| KLR-B5 | Author `k8s/rbac/` — ServiceAccount + scoped ClusterRole + binding (the remediation permission boundary) | P0 | B1 |
| KLR-B6 | Wire Alertmanager routing to a placeholder webhook URL | P1 | B2 |
| KLR-B7 | Failure-injection scripts (crash pod, OOM, bad deploy, image-pull error, CPU load) | P1 | B4 |

**Phase 0–1 exit criteria:** a monitored cluster running breakable workloads, with RBAC in place and a way to trigger failures on demand.

---

## Epic C — Ingestion & Detection Pipeline  *(Phase 1 · Month 2)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-C1 | Kubernetes client wrapper (`k8s/client.py`) using the ServiceAccount | P0 | A5, B5 |
| KLR-C2 | Prometheus query wrapper (`k8s/metrics.py`) | P0 | A5, B2 |
| KLR-C3 | **Auto-Discovery module** — detect K8s API, Prometheus, Loki-if-present; self-configure with fallback | P1 | C1, C2 |
| KLR-C4 | Alertmanager webhook receiver endpoint (token-protected) → creates incident record | P0 | A6, B6 |
| KLR-C5 | Monitoring/Ingestion Agent — poll metrics + API, evaluate detection rules | P1 | C1, C2 |
| KLR-C6 | Incident detection decision + persistence (severity/priority classification: SEV-1…4 / P1…4) | P1 | C4, C5 |
| KLR-C7 | Minimal LangGraph graph wiring Monitoring → detection decision | P1 | A3, C5 |

**Phase 1 exit criteria:** trigger a real failure → alert fires → webhook lands → a severity-classified incident record is created. No AI yet.

---

## Epic D — Investigation & RAG  *(Phase 2 · Month 3)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-D1 | K8s data collectors: events, pod status, logs (incl. `--previous`), deploy history | P0 | C1 |
| KLR-D2 | Investigation Agent — rule-based pattern match first, LLM fallback for ambiguous logs | P1 | D1, C7 |
| KLR-D3 | Embedding pipeline (sentence-transformers, all-MiniLM-L6-v2) | P0 | A2 |
| KLR-D4 | ChromaDB client + collection design (runbooks, historical_incidents, kubernetes_docs) | P0 | A2, D3 |
| KLR-D5 | Knowledge-base ingestion script + `sources.yaml` (chunk, embed, upsert) | P1 | D4 |
| KLR-D6 | **Scheduled live-refresh** job — periodic fetch from source URLs, content-hash diff, re-embed changed docs (Redis-backed) | P1 | D5 |
| KLR-D7 | Curate initial corpus: 30–50 runbooks mapped to the chaos scenarios | P1 | D5 |
| KLR-D8 | Retrieval/RAG Agent — semantic search, top-k with threshold, filter by collection | P1 | D4, D2 |

**Phase 2 (mid-project) exit criteria:** an incident produces a structured investigation plus retrieved, relevant precedent. Strong standalone review-2 demo.

---

## Epic E — Reasoning, Planning & the Contextual Bandit  *(Phase 2–3 · Month 3–4)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-E1 | LLM client with provider toggle (OpenAI ↔ Ollama) + rate-limit handling | P0 | A5 |
| KLR-E2 | Root Cause Agent — reason over investigation + retrieved precedent → cause + confidence | P1 | D8, E1 |
| KLR-E3 | Prompt templates (root cause, planning, report) + versioning | P1 | E1 |
| KLR-E4 | Planning Agent — emit **ranked candidate actions** (not a single choice) | P1 | E2 |
| KLR-E5 | Bandit policy store (`bandit/`) — per (incident_category, action) reward + count | P2 | A6 |
| KLR-E6 | Bandit re-ranking — reorder candidate actions by learned reward; seed priors from runbooks | P2 | E4, E5 |
| KLR-E7 | Bandit update — compute reward (success/time/cost) from validation outcome, write back | P2 | E5, F5 |
| KLR-E8 | Confidence-threshold gate — below threshold routes to human regardless of risk tier | P1 | E2 |

> **Note:** E5–E7 (the bandit) are P2 by design — the system works without them. Build the cheap
> version, seed priors so it can't hurt, hold loosely, and cut first if Month 6 is tight.

---

## Epic F — Safety, Remediation & Validation  *(Phase 3 · Month 4)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-F1 | Policy engine (`policy/engine.py`) + `default.yaml` — severity-aware (action × severity → auto / require_approval) | P0 | A6 |
| KLR-F2 | Safety Agent / risk assessment — classify action, apply policy + confidence + severity | P1 | F1, E8 |
| KLR-F3 | Remediation actions: restart_pod, scale_deployment, rollback_deployment, delete_pod, cordon_node | P1 | C1, B5 |
| KLR-F4 | Remediation Agent — execute approved action via the safe-action whitelist only | P1 | F2, F3 |
| KLR-F5 | Validation Agent — re-check live health post-action; success/fail decision | P1 | F4, C2 |
| KLR-F6 | Retry-then-escalate loop — bounded retries → back to Planning, else escalate | P1 | F5, E4 |
| KLR-F7 | Reporting Agent — compile incident record (cause, evidence, action, outcome, confidence) | P1 | F5 |
| KLR-F8 | Write resolved incident back into knowledge base (closes the RAG loop) | P1 | F7, D4 |
| KLR-F9 | Notification/escalation — Slack/email on high severity or failed remediation | P2 | F6 |
| KLR-F10 | Audit-log writer — record every agent + human action | P1 | A6 |

**Phase 3 exit criteria:** full closed loop — inject failure → detect → diagnose → auto-remediate a low-risk case → validate → report; high-risk case escalates for approval.

---

## Epic G — Dashboard & Auth  *(Phase 4 · Month 5)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-G1 | JWT auth backend — login, bcrypt hashing, token issue/validate | P0 | A6 |
| KLR-G2 | RBAC enforcement — Admin / Engineer / Viewer on every protected endpoint | P0 | G1 |
| KLR-G3 | Login page + auth flow (frontend) | P1 | G1, A7 |
| KLR-G4 | Incident feed + detail view (with severity/priority badges) | P1 | A7, C6 |
| KLR-G5 | Agent-reasoning trace view (per-agent steps + timing) | P1 | G4, A3 |
| KLR-G6 | Approval panel — approve/reject high-risk actions (Engineer+) | P1 | G4, F2 |
| KLR-G7 | Analytics: MTTD / MTTR / trend charts (Recharts) | P2 | G4 |
| KLR-G8 | Live updates (SSE) for the incident feed | P2 | G4 |
| KLR-G9 | Policy & knowledge-source config views (Admin) | P3 | G2, F1, D6 |

**Phase 4 exit criteria:** an operator can log in, watch incidents live, inspect agent reasoning, and approve/reject actions — with role-appropriate access.

---

## Epic H — Packaging, Cloud & Plugin  *(Phase 4–5 · Month 5–6)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-H1 | Helm chart for the platform (backend, frontend, postgres, redis, chromadb, SA, ingress) | P1 | A5, A7, B5 |
| KLR-H2 | Dockerfiles + image build workflow | P1 | A5, A7 |
| KLR-H3 | One-command install validation on the local cluster | P1 | H1, H2 |
| KLR-H4 | **Cloud deployment** — deploy the same chart to a managed cluster (EKS/AKS/GKE) to prove portability | P2 | H3 |
| KLR-H5 | kubectl plugin (`cli/`) — thin API client: `diagnose` / `remediate` / `status` | P3 | A4, E2 |

> **Note:** H4 is the cloud-compatibility milestone (final-phase, not Phase 1). H5 (plugin) is P3 —
> build only if Month 6 has slack, after evaluation is done.

---

## Epic I — Evaluation & Hardening  *(Phase 5 · Month 6)*

| ID | Ticket | Priority | Depends on |
|---|---|---|---|
| KLR-I1 | Chaos-test harness — run each scenario, log MTTD/MTTR/success/escalation to `results/` | P0 | F6, B7 |
| KLR-I2 | Baseline runs — same scenarios under manual + threshold-only automation | P1 | I1 |
| KLR-I3 | **Ablation study** — full vs. without-RAG, without-Validation, without-Safety, without-bandit | P1 | I1 |
| KLR-I4 | Error-handling hardening — LLM/vector-DB/K8s-API/DB outage paths fail safe | P1 | F6 |
| KLR-I5 | Input-safety hardening — instructions-in-data ignored; non-whitelisted actions refused | P1 | F4 |
| KLR-I6 | Results analysis + write-up (honest reporting, incl. any null bandit result) | P0 | I2, I3 |
| KLR-I7 | Demo script + reset script for a clean, repeatable live demo | P1 | H3 |

**Phase 5 exit criteria:** documented evaluation with baseline comparison + ablation; hardened failure paths; a repeatable demo.

---

## Priority rollup — what to cut first if time runs short

Cut in this order, from the top:

1. **KLR-H5** kubectl plugin (P3)
2. **KLR-G9** admin config views (P3)
3. **KLR-E5–E7** contextual bandit (P2) — demote to Future Work; the core loop still stands
4. **KLR-G7/G8** analytics + live SSE (P2) — static polling is an acceptable fallback
5. **KLR-H4** cloud deployment (P2) — claim portability by design if you can't run it
6. **KLR-F9** notifications (P2)

**Never cut:** the closed loop (Epics C–F core), auth/RBAC (G1–G2), and the evaluation (I1, I3, I6).
A polished core system with a clean evaluation beats a feature-complete system with no results.

---

## Suggested working rhythm

- Freeze contracts (Epic A) before parallelising.
- Work in pairs per epic, rotate weekly, so knowledge doesn't concentrate (matters for the viva).
- One person per week owns integration — makes sure everything merged that week runs end-to-end.
- Keep a `blocked` column honest; a ticket blocked for more than a day is a standup topic.
