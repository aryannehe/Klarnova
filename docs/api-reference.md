# Klarnova — API Reference

REST contract for the Klarnova backend. The Pydantic schemas referenced here are the shared,
frozen contract (KLR-A4); this document tracks the endpoints and request/response shapes.
Final Year BE Project · Version 1.0 · 2026

---

## 1. Conventions

- **Base path:** `https://<host>/api/v1`
- **Auth:** every protected endpoint requires a `Authorization: Bearer <JWT>` header.
  Role is read from validated token claims on every request (Security doc §3.1–3.2).
- **RBAC:** roles are cumulative — Viewer < Engineer < Admin (Security doc §2).
- **Errors:** consistent envelope — `{"detail": "<message>"}` with the appropriate HTTP status.
  Unauthorised (401) and forbidden (403) never partially execute the action.
- **Timestamps:** ISO 8601 UTC. **Severity/priority:** SEV-1…4 / P1…4 (PRD §4.3).
- **Webhooks:** token-protected via the `X-Klarnova-Token` header (shared token, Security doc §3.4).

---

## 2. Schemas (Pydantic, frozen — summary)

| Schema | Key fields |
|--------|-----------|
| `Incident` | `id`, `severity`, `priority`, `status`, `created_at`, `updated_at`, `affected_resource`, `root_cause`, `confidence`, `evidence` |
| `Diagnosis` | `incident_id`, `cause`, `evidence`, `confidence`, `cited_precedent`, `prompt_version`, `agent_run_id` |
| `ActionCandidate` | `action` (whitelist), `rationale`, `confidence`, `bandit_score` |
| `ActionDecision` | `candidate`, `verdict` (`auto`/`require_approval`/`refuse`), `policy_ref`, `reason` |
| `Remediation` | `id`, `incident_id`, `action`, `params`, `executed_at`, `outcome`, `requested_by` |
| `AgentRun` | `id`, `incident_id`, `agent`, `inputs`, `outputs`, `duration_ms`, `prompt_version`, `started_at` |
| `TokenResponse` | `access_token`, `token_type`, `expires_at` |
| `User` | `id`, `username`, `role` (`admin`/`engineer`/`viewer`) |

---

## 3. Endpoints

### 3.1 Health

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `GET` | `/health` | public | Liveness — service is up |
| `GET` | `/health/ready` | public | Readiness — dependencies (DB, Redis, ChromaDB) reachable |

### 3.2 Auth

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `POST` | `/auth/login` | public | Issue JWT. Body: `{username, password}` → `TokenResponse` |
| `GET` | `/auth/me` | authenticated | Current user + role |
| `POST` | `/auth/refresh` | authenticated | Refresh short-lived token |
| `POST` | `/users` | Admin | Create user. Body: `{username, password, role}` |
| `PATCH` | `/users/{id}/role` | Admin | Change user role |
| `GET` | `/users` | Admin | List users |

### 3.3 Incidents

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `GET` | `/incidents` | Viewer+ | List incidents. Query: `status`, `severity`, `resource`, `from`, `to`, `page`, `limit` |
| `GET` | `/incidents/{id}` | Viewer+ | Incident detail (includes diagnosis, evidence, remediations) |
| `GET` | `/incidents/{id}/trace` | Viewer+ | Agent-run trace for the incident (KLR-G5) |
| `POST` | `/incidents/{id}/diagnose` | Engineer+ | Trigger on-demand diagnosis (starts graph at Investigation) |
| `GET` | `/analytics/mttd-mttr` | Viewer+ | MTTD/MTTR summary + trends (KLR-G7, P2) |
| `GET` | `/events` | Viewer+ | SSE stream of live incident updates (KLR-G8, P2) |

### 3.4 Remediation

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `GET` | `/remediations` | Viewer+ | List remediations |
| `GET` | `/remediations/{id}` | Viewer+ | Remediation detail + outcome |
| `POST` | `/remediations/{id}/approve` | Engineer+ | Approve a pending (require_approval) action |
| `POST` | `/remediations/{id}/reject` | Engineer+ | Reject a pending action |
| `POST` | `/incidents/{id}/remediate` | Engineer+ | Manually trigger a whitelisted remediation |

### 3.5 Policy & Knowledge Base (Admin)

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `GET` | `/policies` | Viewer+ | Read current policy rules |
| `PUT` | `/policies` | Admin | Update risk policy rules (KLR-G9, P3) |
| `GET` | `/kb/sources` | Viewer+ | List KB sources (`sources.yaml`) |
| `PUT` | `/kb/sources` | Admin | Manage KB sources (KLR-G9, P3) |
| `POST` | `/kb/refresh` | Admin | Trigger a manual knowledge-base refresh |

### 3.6 Webhook (internal)

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `POST` | `/webhooks/alertmanager` | shared token | Alertmanager → create incident record (KLR-C4) |

---

## 4. Authentication Flow

1. `POST /auth/login` with credentials → `TokenResponse` (short-lived JWT).
2. Frontend stores the token; sends it on every request.
3. Backend validates signature, expiry, and reads the role from claims — client cannot escalate
   by editing state (Security doc §3.1).
4. RBAC enforced on every protected endpoint; the action is never partially performed.

---

## 5. Error Codes

| Status | Meaning |
|--------|---------|
| `400` | Malformed request / validation failure |
| `401` | Missing or invalid token |
| `403` | Authenticated but insufficient role |
| `404` | Resource not found |
| `409` | Conflict (e.g., approving an already-executed remediation) |
| `503` | Dependency unavailable (DB, Redis, ChromaDB, K8s API) |

---

## 6. Open Questions (resolve during KLR-A4)

- Exact pagination shape and default limits for list endpoints.
- SSE event schema for `/events`.
- Whether `/incidents/{id}/diagnose` accepts an optional `resource` filter for multi-resource incidents.
