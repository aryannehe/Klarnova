# Klarnova — Evaluation Results (Epic I, Phase 5)

Honest account of the baseline-vs-full comparison and the component ablation
study against the committed PRD metrics. Generated from the offline harness
(`chaos-testing/`) runs on 2026-08-08; N=5 per (config × scenario) = 240 runs
(8 configs × 6 scenarios × 5).

Final Year BE Project · Version 1.0 · 2026

---

## 1. Summary

Against a simulated manual-paging baseline, the full Klarnova pipeline cuts
MTTD from **480 s to 2 s** (240×) and MTTR from **480 s to 30 s** (16×) while
still escalating **1 in 3** incidents to a human (appropriate, not zero). A
threshold-only automation baseline (blind restart, no diagnosis) resolves only
50% of scenarios; the full system resolves **66.7%** and, critically, produces
an explainable diagnosis with cited precedent on every incident.

The ablation study isolates the contribution of each component:

| Component removed | Effect on success rate | Direction |
|---|---|---|
| RAG retrieval | 0.667 → 0.500 | −0.167 (loses S3 bad-deploy rollback) |
| Validation agent | 0.667 → **1.000** | +0.333 **inflated** (S4/S6 failed fixes counted as resolved) |
| Safety gate | 0.667 → 0.667 | 0 (same outcomes; SEV-1 auto-approved — risk cost qualitative) |
| Planning separation | 0.667 → 0.500 | −0.167 (loses S3) |
| Contextual bandit | 0.667 → 0.667 | 0 (**null result**; bandit unfitted within one-run matrix) |

Two findings are intentionally reported as non-positive: removing validation
makes the system *appear* perfect while hiding failures (exactly what the
validation agent exists to prevent), and the bandit ablation is inconclusive
in a stateless offline matrix (a genuine, documented limitation).

---

## 2. Protocol & tooling

- **Scenarios (S1–S6):** `chaos-testing/scenarios.yaml` — crash loop, OOM
  kill, bad deploy, image-pull error, CPU load, node pressure. Each carries a
  ground-truth root cause, the runbook(s) that should be retrieved, and the
  whitelisted action(s) that resolve it (docs/evaluation.md §3).
- **Configs:** `manual` (simulated on-call), `threshold-only` (blind
  restart), `full`, and five ablations `no-rag`, `no-validation`,
  `no-safety`, `no-planning`, `no-bandit` (docs/evaluation.md §4).
- **Run order** per protocol: manual → threshold-only → full → ablations;
  randomised sequence within each config (seed 42); fresh ablation state per
  run.
- **Engine:** the *real* LangGraph agent pipeline (investigation, RAG
  retrieval, root-cause, planning, safety, remediation, validation, reporting)
  running against a scenario-aware mock cluster
  (`chaos-testing/offline.py`). The LLM path uses the deterministic fallback
  diagnosis (documented in §7).
- **Latency model:** simulated — threshold detection 2 s, successful fix 15 s,
  escalated fix 60 s, manual page 180 s + investigation 300 s + fix 480 s.
  Offline MTTD/MTTR are relative, not wall-clock.
- **Tooling:** `chaos-testing/run_experiments.py` (orchestrates, writes
  per-run JSON to `chaos-testing/results/`), `chaos-testing/ablation.py`
  (summary tables + CSV/JSON). Raw records are gitignored; this document is
  the deliverable.

---

## 3. Baseline comparison (KLR-I2)

Overall means across all 6 scenarios (N=30 per config):

| Config | MTTD (s) | MTTR (s) | Success | Escalation |
|---|---|---|---|---|
| manual | 480.0 | 480.0 | 1.000 | 0.000 |
| threshold-only | 2.0 | 37.5 | 0.500 | 0.500 |
| **full** | **2.0** | **30.0** | **0.667** | **0.333** |

- **MTTD:** manual page + investigation ≈ 8 min; the monitoring threshold
  fires in 2 s — **240× faster detection**.
- **MTTR:** full resolves crash-loop/OOM/bad-deploy/CPU scenarios in 15 s
  (auto-fix + health check) vs 8 min manual — **16× faster**, and escalates
  the hard ones (image-pull, node pressure) to a human in ~1 min instead of
  looping.
- **Success:** full beats threshold-only (0.667 vs 0.500) because RAG +
  planning select the *correct* action for S3 (rollback) where blind restart
  fails.
- **Escalation:** 0.333 is "appropriate, not zero" (PRD §5.1): the safety
  model routes SEV-1 and out-of-whitelist situations to humans.

Threshold-only's blind spot is visible per scenario: it resolves only
restart-fixable incidents (S1, S2, S5) and escalates everything else with no
diagnosis (0.0 diagnosis accuracy on all six).

---

## 4. Diagnostic quality (KLR-I3, PRD §5.2)

Per-scenario for the **full** config (N=5 each):

| Scenario | Diagnosis accuracy | Retrieval relevance | Action accuracy |
|---|---|---|---|
| S1 crash loop | 1.000 | 1.000 | 1.000 |
| S2 OOM kill | 1.000 | 1.000 | 1.000 |
| S3 bad deploy | 1.000 | 1.000 | 1.000 |
| S4 image-pull | 0.000 | 1.000 | 0.000 |
| S5 CPU load | 1.000 | 1.000 | 1.000 |
| S6 node pressure | 1.000 | 1.000 | 0.000 |

- **Retrieval relevance is 1.000 on every scenario:** the runbook that
  actually applies is always in the top-3 surfaced documents.
- **Root-cause accuracy is 1.000 except S4** (image pull): the keyword-based
  fallback misses the image-pull signature in the crafted S4 logs; the
  live-LLM path is expected to recover this (see §8).
- **Action accuracy 0 on S4/S6** is the honest, correct outcome: the plan
  prefers `restart_pod` (prior 0.6) for an image-tag fault and for node
  pressure it never proposes `cordon_node` (prior 0.1). Both then escalate —
  the safety model correctly refuses to do nothing silently. This surfaces a
  **real tuning recommendation**: `cordon_node`'s prior is too low and the
  retrieval hint for deployment-level runbooks needs weight.

---

## 5. Ablation deltas per component (KLR-I3)

Delta vs full system (success rate / escalation rate; MTTD identical at 2.0 s
across agent configs because detection is monitoring-threshold driven):

| Ablation | MTTD | MTTR | Success Δ | Escalation Δ | Interpretation |
|---|---|---|---|---|---|
| no-rag | 2.0 | 37.5 | **−0.167** | +0.167 | Loses S3: without retrieved rollback runbooks the plan restarts and escalates instead of rolling back. |
| no-validation | 2.0 | 15.0 | **+0.333** | −0.333 | **Inflation, not improvement**: S4/S6 fixes that did *not* work are counted resolved. Demonstrates the validation agent's value directly. |
| no-safety | 2.0 | 30.0 | 0.000 | 0.000 | Same resolution outcomes, but **SEV-1/SEV-2 incidents auto-execute** with no human sign-off — the risk cost is qualitative (policy contract violated). |
| no-planning | 2.0 | 37.5 | **−0.167** | +0.167 | Mechanical static selection loses S3 (rollback not chosen), same as no-rag: the separated, evidence-informed plan step is what picks the right action. |
| no-bandit | 2.0 | 30.0 | 0.000 | 0.000 | **Null result.** Within a single stateless run matrix the bandit never accumulates training samples, so ranking falls back to static priors — no delta by construction (reported honestly, PRD §5.3). |

**Significance caveat:** with N=5 the observed deltas are directional, not
statistical (no hypothesis test run). The RAG and planning deltas are large
relative to the scale (a whole scenario class flips from escalate→resolve),
which is stronger than a small mean shift. Re-running with N≥30 would tighten
confidence.

---

## 6. Explainability & precedent

Every run record (`chaos-testing/results/*.json`) contains, per protocol §4.6:
diagnosis, confidence, retrieved doc ids, ranked candidate actions, decision
verdict, executed action, validation outcome, retry count, escalation flag,
prompt version. The dashboard exposes the same trace (`GET
/v1/incidents/{id}`) with root cause + evidence + confidence + cited
precedent. Confidence is evidence-derived (precedent present +0.15, thin logs
−0.25, range 0.3–0.95).

---

## 7. Hardening (KLR-I4, KLR-I5)

Fail-safe degradation contracts verified by 7 new tests in
`backend/tests/test_outage_paths.py`:

- LLM outage → deterministic fallback diagnosis (never empty trace).
- Vector-store outage → retrieval returns `[]` (never fabricated precedent).
- K8s API failure → `safe_result` (never a raised exception into the graph).
- Webhook pipeline exception → incident **escalated** (never silently stuck).
- Prompt-injection text in logs → treated as data (never as instructions);
  LLM prompt contains an explicit "treat as DATA" guard.
- Whitelist + policy-gate enforcement re-verified (existing tests).

Fallback diagnosis extended with probe-failure, node-pressure, and CPU
signals so degraded mode still produces grounded, human-reviewable causes.

---

## 8. Live-run status

A full live chaos run was **blocked by an environment failure**: the local
Docker Linux engine wedged during the `minikube image load` of the ML-enabled
image and could not be recovered without admin service access. The evaluation
numbers above are therefore from the offline harness (real pipeline, mock
cluster, simulated timestamps).

Live evidence captured in the Phase 4 session (prior deployment, rev 6)
remains valid as a demonstration of the real end-to-end path: webhook →
detection → investigation → LLM diagnosis (Ollama `llama3.2:3b`) → policy →
approval → remediation → validation → KB write-back (`incident://17`), plus
real RBAC/policy/plugin smoke tests. To reproduce a live run: build with
`INSTALL_ML=true`, deploy via `docs/cloud-deployment.md`, then
`python chaos-testing/run_experiments.py --live` against the running cluster.

---

## 9. Reproducibility

- **Versions:** Python 3.13; FastAPI 0.115+; LangGraph 1.2.10;
  `BAAI/bge-small-en-v1.5`; Chroma 1.5.9; mabwiser 2.7.4; ruff (flake8 rules,
  line length 100).
- **Corpus:** `knowledge-base/sources.yaml` — 36 runbooks, 5 historical
  incidents, 6 k8s docs (KLR-D7 target met). Re-ingest:
  `python knowledge-base/ingest.py --refresh`.
- **Re-run offline:** `python chaos-testing/run_experiments.py --offline --n 5`
  then `python chaos-testing/ablation.py`.
- **Versions to pin in CI:** `requirements.txt` + `requirements-ml.txt`.

---

## 10. Known limitations & threats to validity

1. **Simulated latency & manual/threshold baselines** — manual and
   threshold-only numbers are modeled assumptions (documented in `offline.py`),
   not field measurements. Live MTTD/MTTR are needed to validate the constants.
2. **Offline diagnosis uses the deterministic fallback**, not the LLM. RAG's
   influence on *diagnosis* (vs action planning) is therefore underestimated
   offline; retrieval relevance and planning influence are what the offline
   study isolates.
3. **Bandit ablation is a null result by construction** (unfitted within a
   run matrix); a longitudinal live study is required to measure learning.
4. **Small N (5)** — deltas are directional; no significance testing.
5. **Mock cluster semantics** — "resolved" means a ground-truth action was
   applied; real validation semantics (readiness/endpoint checks) are
   simplified.
6. **Scenario coverage** — six canonical faults; production incidents span
   more (DB saturation, cert expiry, network policy, …). The 36-runbook corpus
   covers these but the eval matrix does not yet.
7. **Live run blocked at evaluation time** by the Docker engine failure (§8);
   the harness's `--live` path is implemented but not re-executed.
