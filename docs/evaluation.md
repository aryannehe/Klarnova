# Klarnova — Evaluation Plan

Protocol for measuring success against the committed PRD metrics, running the chaos scenarios,
and running the ablation study with honest reporting.
Final Year BE Project · Version 1.0 · 2026

---

## 1. Goal

Show, with evidence, that Klarnova improves operational outcomes over a baseline of manual
investigation and simple threshold-based automation — and quantify each component's contribution.
Per the backlog: *"a polished core system with a clean evaluation beats a feature-complete system
with no results."* Inconclusive results are reported honestly, never omitted.

---

## 2. Metrics

### 2.1 Operational performance (PRD §5.1)

| Metric | Definition | Target direction |
|--------|-----------|------------------|
| MTTD | Time from failure injection to detection | Substantial reduction vs. baseline |
| MTTR | Time from detection to validated fix | Substantial reduction vs. baseline |
| Remediation success rate | Fixes validated as healthy on first attempt | High, honest reporting |
| Escalation rate | Incidents routed to humans | Appropriate, **not zero** |
| Time-to-first-monitor | Helm install → active monitoring on a standard cluster | Minutes, minimal config |

> A zero escalation rate is not a goal — correctly escalating out-of-boundary incidents is evidence
> the safety model works (PRD §5.1 note).

### 2.2 Diagnostic quality (PRD §5.2)

| Metric | Definition |
|--------|-----------|
| Root-cause accuracy | Proportion of incidents where the identified cause matches ground truth from the injected scenario |
| Retrieval relevance | Whether RAG surfaces the genuinely applicable runbook / past incident |
| Explainability | Every recommendation carries root cause + evidence + confidence + cited precedent |

### 2.3 Bandit (if built — P2, KLR-E5–E7)

- Whether learned re-ranking improves remediation success over static (seeded) selection.
- A null result here is a valid, reportable result. Do not force a positive.

---

## 3. Chaos Scenarios (KLR-B7, KLR-I1)

Each scenario is an injected, intentional failure on the sample workload (api-gateway,
user-service, database-service) with a known ground-truth root cause.

| ID | Scenario | Injection | Expected ground truth |
|----|----------|-----------|----------------------|
| S1 | Crash loop | Repeatedly crash the container | `restart_pod` / crash-loop from bad startup |
| S2 | OOM kill | Memory limit exceeded | OOMKilled → resource limit too low |
| S3 | Bad deploy | Deploy image with failing liveness probe | `rollback_deployment` to previous revision |
| S4 | Image-pull error | Deploy non-existent image tag | ImagePullBackOff → `scale_deployment` / fix tag |
| S5 | CPU load | Run CPU-stress container | CPU saturation → scale or restart |
| S6 | Node pressure | Cordon / stress a node | `cordon_node` (human-gated) |

Scripts live in `scripts/` (inject-failure) and `chaos-testing/scenarios/` (definitions). Each run
logs MTTD/MTTR/success/escalation to `chaos-testing/results/`.

---

## 4. Experimental Configurations (KLR-I2, KLR-I3)

| Configuration | Question it answers |
|---------------|--------------------|
| Full system | Baseline for the complete pipeline |
| Without RAG retrieval | How much does grounded precedent improve diagnosis? |
| Without Validation Agent | How many failed fixes would go unnoticed? |
| Without Safety Agent | What is the risk cost of removing the policy gate? |
| Without Planning separation | Does separating planning from reasoning improve action choice? |
| Without contextual bandit | Does learned action-ranking beat static selection? |

### Protocol

1. **Run order:** manual baseline → threshold-only baseline → full system → each ablation config.
2. **Same scenarios, same cluster state, same order** across all configs to control drift.
3. **N runs per (config × scenario):** fix N at kickoff (suggest ≥ 5) so variance is reportable.
4. **Randomised sequence** within each config to avoid order effects.
5. **Fresh state** between runs: reset cluster + KB state (reset script, KLR-I7).
6. **Data recorded per run:** timestamps, incident ID, severity, diagnosis vs. ground truth,
   retrieved docs, candidate actions, decision verdict, executed action, validation outcome,
   retry count, escalation flag, confidence, prompt versions.

---

## 5. Tooling

- `chaos-testing/run_experiments.py` — orchestrates runs across configurations, writes `results/`.
- `chaos-testing/ablation.py` — toggles components (RAG, Validation, Safety, Planning, bandit) and
  summarises deltas.
- `chaos-testing/results/` — raw run logs + summary tables (JSON/CSV).
- Analysis scripts produce: metric tables, trend charts, and per-component contribution deltas.

---

## 6. Reporting (KLR-I6)

The write-up must include:

1. Baseline comparison (manual + threshold-only) vs. full system: MTTD, MTTR, success, escalation.
2. Ablation deltas per component with direction and significance.
3. Honest reporting of null / inconclusive results (especially the bandit).
4. Reproducibility section: versions pinned, cluster setup, how to re-run.
5. Known limitations and threats to validity.

Deliverable: `docs/evaluation-results.md` (created in Month 6) + presentation-ready summary for
the demo (KLR-I7).
