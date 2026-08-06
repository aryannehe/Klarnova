# Klarnova — Implementation Plan

Six-month, phase-by-phase execution schedule derived from the feature backlog
(`Klarnova_Feature_Backlog_1.md`). Maps Epics A–I to weekly goals, milestones, and exit criteria.

Final Year BE Project · Version 1.0 · 2026

---

## 1. Assumptions & Conventions

- **Kickoff:** Month 1, Week 1 = the first Monday after the plan is accepted (adjust all dates
  below if kickoff moves). Example dates below assume kickoff **Mon 10 Aug 2026**.
- **Work in pairs per epic, rotate weekly** so knowledge spreads before the viva (backlog rhythm).
- **One integration owner per week** — everything merged that week must run end-to-end.
- **Freeze contracts before parallelising:** `AgentState` (KLR-A3) and Pydantic schemas (KLR-A4)
  are frozen in Month 1 before anyone builds against them.
- **Exit criteria are gates:** a phase is not done until its criteria are met.

---

## 2. Milestone Map

| Phase | Month | Epic(s) | Milestone / exit criteria |
|---|---|---|---|
| 0 | 1 | A, B (start) | Local stack boots with one command; schemas frozen; skeleton frontend↔backend round-trip |
| 1 | 2 | B (finish), C | Real failure → alert → webhook → severity-classified incident record (no AI) |
| 2 | 3 | D, E (start) | Incident → structured investigation + retrieved relevant precedent (review-2 demo) |
| 3 | 4 | E (finish), F | Full closed loop: detect → diagnose → auto-remediate low-risk / escalate high-risk → validate → report |
| 4 | 5 | G, H (start) | Operator login, live incidents, agent traces, approval workflow with RBAC |
| 5 | 6 | H (finish), I | Documented evaluation (baseline + ablation), hardened failure paths, repeatable demo |

---

## 3. Month-by-Month Schedule

### Month 1 — Phase 0 · Foundations & Contracts (Epic A + B start)
| Week | Goals (tickets) |
|---|---|
| 1 | **KLR-A1** monorepo init, branching model, `CONTRIBUTORS.md`, first commit per teammate · **KLR-A2** docker-compose (backend, frontend, postgres, redis, chromadb, ollama) |
| 2 | Finish **A2** · **A3** freeze `AgentState` · **A4** freeze Pydantic schemas (contract-freeze gate) |
| 3 | **A5** FastAPI skeleton + health/readiness + config loader · **A6** Postgres schema + first Alembic migration · start **B1** local cluster (Kind/Minikube) |
| 4 | **A7** Next.js skeleton `/health` round-trip · **A8** Makefile + `.env.example` · **A9** CI (lint + test) · finish **B1** |

**Exit criteria:** cluster-less stack boots with one command; contracts frozen; skeleton frontend talks to skeleton backend.

### Month 2 — Phase 1 · Cluster, Monitoring & Ingestion (Epic B finish + C)
| Week | Goals (tickets) |
|---|---|
| 5 | **B2** monitoring stack (`kube-prometheus-stack`) · **B3** three breakable sample microservices with structured JSON logging |
| 6 | **B4** deploy sample apps (manifests + configmap) · **B5** ServiceAccount + scoped ClusterRole + binding |
| 7 | **B6** Alertmanager routing to placeholder webhook · **C1** K8s client wrapper · **C2** Prometheus query wrapper |
| 8 | **B7** failure-injection scripts (crash, OOM, bad deploy, image-pull, CPU) · **C3** Auto-Discovery module · **C4** token-protected webhook receiver → incident record |
| 9 | **C5** Monitoring/Ingestion Agent (poll metrics + API) · **C6** detection decision + SEV-1…4 / P1…4 classification · **C7** minimal LangGraph wiring |

**Exit criteria:** trigger a real failure → alert fires → webhook lands → severity-classified incident record created. **No AI yet.**

### Month 3 — Phase 2 · Investigation & RAG (Epic D + E start)
| Week | Goals (tickets) |
|---|---|
| 10 | **D1** K8s data collectors (events, pod status, logs incl. `--previous`, deploy history) · start **D2** Investigation Agent (rule-based first) |
| 11 | **D3** embedding pipeline (all-MiniLM-L6-v2) · **D4** ChromaDB client + 3 collections |
| 12 | **D5** KB ingestion script + `sources.yaml` · **E1** LLM client (OpenAI ↔ Ollama toggle + rate limiting) |
| 13 | **D6** scheduled live-refresh (content-hash diff, Redis-backed) · **D7** curate 30–50 runbooks |
| 14 | **D8** Retrieval Agent (semantic top-k + threshold) · finish **D2** (LLM fallback path) |

**Exit criteria:** incident produces structured investigation + retrieved relevant precedent. Strong standalone review-2 demo.

### Month 4 — Phase 3 · Reasoning, Safety & Closed Loop (Epic E finish + F)
| Week | Goals (tickets) |
|---|---|
| 15 | **E2** Root Cause Agent (cause + confidence) · **E3** versioned prompt templates |
| 16 | **E4** Planning Agent (ranked candidate actions) · **E8** confidence-threshold gate |
| 17 | **F1** policy engine + `default.yaml` (action × severity) · **F2** Safety Agent · **E5–E7** bandit (P2, seed priors) |
| 18 | **F3** whitelist actions (restart, scale, rollback, delete, cordon) · **F4** Remediation Agent |
| 19 | **F5** Validation Agent (re-check live health) · **F6** bounded retry-then-escalate loop |
| 20 | **F7** Reporting Agent · **F8** write resolved incident back to KB · **F10** audit-log writer · **F9** notifications (P2, if on track) |

**Exit criteria:** full closed loop — inject failure → detect → diagnose → auto-remediate a low-risk case → validate → report; high-risk case escalates for approval.

### Month 5 — Phase 4 · Dashboard & Auth (Epic G + H start)
| Week | Goals (tickets) |
|---|---|
| 21 | **G1** JWT auth backend (bcrypt) · **G2** RBAC enforcement (Admin/Engineer/Viewer) |
| 22 | **G3** login page + auth flow · **G4** incident feed + detail with severity badges |
| 23 | **G5** agent-reasoning trace view · **G6** approval panel (high-risk actions) |
| 24 | **G7** MTTD/MTTR analytics (Recharts, P2) · **G8** SSE live updates (P2) · **H2** Dockerfiles |

**Exit criteria:** operator can log in, watch incidents live, inspect agent reasoning, and approve/reject actions — with role-appropriate access.

### Month 6 — Phase 5 · Packaging & Evaluation (Epic H finish + I)
| Week | Goals (tickets) |
|---|---|
| 25 | **H1** Helm chart · **H3** one-command install validation on the local cluster |
| 26 | **I1** chaos-test harness (log MTTD/MTTR/success/escalation) · **I2** baseline runs (manual + threshold-only) |
| 27 | **I3** ablation study (RAG/Validation/Safety/Planning/bandit) · **I4** error-handling hardening · **I5** input-safety hardening |
| 28 | **I6** results analysis + honest write-up · **I7** demo + reset scripts · slack: **H4** cloud deploy (P2), **H5** kubectl plugin (P3), **G9** admin views (P3) |

**Exit criteria:** documented evaluation with baseline comparison + ablation; hardened failure paths; repeatable clean demo.

---

## 4. Risk & Contingency

- **Cut-first order if Month 6 is tight** (backlog priority rollup): H5 plugin → G9 admin views →
  E5–E7 bandit → G7/G8 analytics+SSE → H4 cloud deploy → F9 notifications.
- **Never cut:** the closed loop (C–F core), auth/RBAC (G1–G2), evaluation (I1, I3, I6).
- **Blocked ticket rule:** a ticket blocked > 1 day is a standup topic; keep the `blocked` column honest.
- **Version discipline:** pin all dependency versions at kickoff and hold them fixed (reproducibility).

---

## 5. Phase Handoffs

Each phase ends with a working demo of its exit criteria, an updated backlog status, and a
knowledge-sharing session (every teammate can explain that phase's design before the next phase starts).
