# Klarnova — Agent Design Document

Design of the nine-agent pipeline: roles, LangGraph state machine, contracts, and prompts.
Final Year BE Project · Version 1.0 · 2026

---

## 1. Design Principles

- **Deterministic core, probabilistic edges.** Generative LLM reasoning is concentrated in exactly
  three agents (Root Cause, Planning, Reporting). Detection, risk classification, execution, and
  validation are rule-based, so safety guarantees never depend on probabilistic model output.
- **A shared, frozen state.** Every agent reads from and writes to one `AgentState` object
  (`agents/state.py`). It is frozen in Phase 0 (KLR-A3) and treated as an integration contract.
- **Advisory output, whitelisted action.** LLM output is advice. Anything that becomes an executed
  action is mapped to the fixed safe-action whitelist (`k8s/actions/`) through the policy engine.
- **Fail-safe.** Any agent that cannot proceed degrades gracefully (skip → lower confidence →
  escalate), never fabricates evidence, and never acts blindly.
- **Deterministic modules outside the LLM path.** The contextual bandit (`bandit/`) and
  auto-discovery (`discovery/`) are deterministic and sit outside the LLM path.

---

## 2. The Nine Agents

| # | Agent | Mode | Responsibility | Module |
|---|-------|------|----------------|--------|
| 1 | Monitoring | rule-based | Poll Prometheus + K8s API, evaluate detection rules, classify incident | `agents/monitoring.py` |
| 2 | Investigation | rule-based first, LLM fallback | Collect events, pod status, logs (incl. `--previous`), deploy history | `agents/investigation.py` |
| 3 | Retrieval | deterministic | Semantic top-k search over ChromaDB with threshold | `agents/retrieval.py` |
| 4 | Root Cause | **LLM** | Reason over evidence + precedent → cause + confidence | `agents/root_cause.py` |
| 5 | Planning | **LLM** | Emit ranked candidate actions (never a single choice) | `agents/planning.py` |
| 6 | Safety | rule-based | Classify risk: apply policy + severity + confidence gate | `agents/safety.py` |
| 7 | Remediation | rule-based | Execute the approved whitelisted action | `agents/remediation.py` |
| 8 | Validation | rule-based | Re-check live health post-action → success/fail | `agents/validation.py` |
| 9 | Reporting | **LLM** | Compile incident record; feed result back to KB | `agents/reporting.py` |

### 2.1 Monitoring Agent

- Polls `k8s/metrics.py` (Prometheus) and `k8s/client.py` (K8s API) on an interval.
- Also consumes incidents pushed via the token-protected Alertmanager webhook (KLR-C4).
- Applies detection rules and produces the severity/priority classification
  (SEV-1…4 / P1…4) per PRD §4.3.
- Output: an `Incident` record (severity, priority, status, affected resource, timestamps).

### 2.2 Investigation Agent

- On incident, gathers structured evidence via the K8s data collectors (KLR-D1):
  events, pod status, logs (including previous-container logs), deployment history.
- Rule-based pattern matching first; ambiguous logs fall back to the LLM client (KLR-E1).
- Never blocks on a slow source — bounded collection time, then proceeds with what it has.

### 2.3 Retrieval Agent

- Searches the three ChromaDB collections: `runbooks`, `historical_incidents`, `kubernetes_docs`.
- Top-k retrieval with a similarity threshold (KLR-D8). Filter by collection and `doc_type`.
- If the vector DB is down, returns no precedent and lowers downstream confidence — it never
  fabricates retrieval results.

### 2.4 Root Cause Agent (LLM)

- Inputs: investigation evidence + retrieved precedent.
- Outputs: a diagnosis — root cause, supporting evidence, confidence score, and cited precedent
  (PRD §5.2).
- If the LLM is unavailable, falls back to the local model (Ollama) or halts at diagnosis and
  escalates (Security doc §5.1).

### 2.5 Planning Agent (LLM)

- Inputs: diagnosis + policy context.
- Outputs: **ranked candidate actions** — an ordered list, not a single choice. The bandit
  (KLR-E6) re-ranks this list by learned reward before the safety gate; it never overrides it.
- Each candidate maps to an allowed action in the whitelist.

### 2.6 Safety Agent

- Applies the policy engine (`policy/engine.py` + `rules/default.yaml`) to each candidate:
  (action × severity) → `auto` / `require_approval`.
- Applies the confidence-threshold gate (default `0.75`): below threshold routes to human
  regardless of risk tier (KLR-E8).
- SEV-1 always requires explicit human approval — no role and no confidence score can override
  (Security doc §2.2).
- Output: for each candidate, `auto`, `require_approval`, or `refuse`.

### 2.7 Remediation Agent

- Executes only the approved, whitelisted action via `k8s/actions/` (KLR-F3/F4).
- Non-whitelisted actions are refused outright (Security doc §5.4).
- Runs under the scoped ServiceAccount; the K8s API server enforces the hard permission ceiling
  even if this agent misbehaves.

### 2.8 Validation Agent

- Re-checks live health after the action (KLR-F5), using the same detection rules.
- Decides success/fail. Outcome feeds:
  1. the contextual bandit as a reward (KLR-E7), and
  2. the retry-then-escalate loop (KLR-F6): bounded retries → back to Planning, else escalate
     with full history. No infinite loops.

### 2.9 Reporting Agent (LLM)

- Compiles the incident record: cause, evidence, action, outcome, confidence.
- Writes the resolved incident back into the knowledge base (KLR-F8) — closes the RAG loop.
- Fires notifications/escalation via Slack/email (KLR-F9, P2) and writes to the audit log.

---

## 3. LangGraph Orchestration

The graph is defined in `agents/graph.py` and wires the agents into a state machine.
All state lives in `AgentState`.

### 3.1 Graph flow

```
Monitoring ──▶ detection decision (severity classified)
   │
   ▼
Investigation ──▶ Retrieval ──▶ Root Cause ──▶ Planning ──▶ [bandit re-rank]
   │                                                         │
   │                                                         ▼
   │                                                        Safety
   │                                                         │
   │                                     ┌───────────────────┤
   │                                     ▼                   ▼
   │                               require_approval      auto
   │                                     │                   │
   │                                     ▼                   ▼
   │                              [approval panel]   Remediation ──▶ Validation
   │                                                        │
   │                                     ┌───────────────────┤
   │                                     ▼                   ▼
   │                                success            fail (bounded)
   │                                     │                   │
   │                                     ▼                   ▼
   │                                 Reporting ──▶ [write to KB]   back to Planning
   │                                     │
   │                                     ▼
   │                                 [notifications] · [audit log]
   │
   └── escalation to human at any gate: low confidence, SEV-1, missing data,
       failed dependency, non-whitelisted action, retries exhausted
```

### 3.2 State transitions

- **Decision points are deterministic.** The LLM agents produce content and confidence; all
  routing (escalate, approve, retry, auto) is decided by rule-based gates.
- **Single entry point.** Every incident enters at Monitoring; an on-demand diagnosis
  (Engineer role) can also start the graph at Investigation.
- **Bounded execution.** Retry-then-escalate is bounded (small fixed count). After escalation the
  graph halts and awaits a human; it never loops indefinitely.

---

## 4. `AgentState` Contract (frozen in Phase 0, KLR-A3)

> Golden rule: this schema is frozen before parallel development. Changes require a cross-team
> review and a migration note.

```python
# agents/state.py — illustrative; exact frozen schema lives in code
class AgentState(BaseModel):
    incident_id: str | None = None
    incident: IncidentSchema | None = None          # from Monitoring / webhook
    severity: Severity | None = None                 # SEV-1…4
    priority: Priority | None = None                 # P1…4
    investigation: InvestigationSchema | None = None # evidence bundle (D1)
    retrieval: list[RetrievedDocSchema] = []         # top-k, filtered, thresholded
    diagnosis: DiagnosisSchema | None = None         # cause + evidence + confidence + cites
    candidates: list[ActionCandidateSchema] = []     # ranked list from Planning (+ bandit)
    decision: list[ActionDecisionSchema] = []        # auto / require_approval / refuse
    remediation: RemediationSchema | None = None     # executed action + result
    validation: ValidationSchema | None = None       # success / fail + metrics
    report: ReportSchema | None = None
    audit: list[AuditEventSchema] = []
    retries: int = 0
    status: IncidentStatus = IncidentStatus.DETECTED
```

Each agent consumes only the fields it is declared to depend on and writes only the fields it owns
(ownership table to be kept in sync with `agents/state.py`).

---

## 5. Prompt Contracts

Prompt templates live in `agents/prompts/`, versioned (KLR-E3). A prompt change increments its
version; runs record which prompt version produced each result so results stay attributable.

| Prompt | Versioning | Inputs | Output contract |
|--------|-----------|--------|-----------------|
| `root_cause.txt` | v1 | investigation, retrieved docs, severity | cause, evidence, confidence (0–1), cited precedent |
| `planning.txt` | v1 | diagnosis, policy summary | ranked candidate actions (JSON list) |
| `report.txt` | v1 | full state | narrative report (human-readable) |
| `investigation_fallback.txt` | v1 | ambiguous log excerpts | structured note (optional; rule-based path preferred) |

**Prompt safety rules** (Security doc §5.4): instructions found inside logs, events, or retrieved
documents are treated as data, never as commands; LLM output is mapped to the safe-action
whitelist before anything executes.

---

## 6. Deterministic Modules Outside the LLM Path

- **`bandit/`** — contextual-bandit policy store, reward, and update (KLR-E5–E7). Re-ranks
  candidates by learned reward per `(incident_category, action)`; seeded from runbook priors so it
  cannot hurt when data is sparse; P2 by design.
- **`discovery/`** — Auto-Discovery (KLR-C3): detects K8s API, Prometheus, Loki-if-present and
  self-configures, with manual override for non-standard setups.
- **`k8s/actions/`** — the safe-action whitelist: `restart_pod`, `scale_deployment`,
  `rollback_deployment`, `delete_pod`, `cordon_node`.
