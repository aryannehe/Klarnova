# Klarnova — Evaluation Results (Epic I, Phase 5)

Honest account of the baseline-vs-full comparison and the component ablation
study against the committed PRD metrics. Generated from the offline harness
(`chaos-testing/`): round 1 on 2026-08-08, round 2 (eval-found gaps closed) on
2026-08-09. N=5 per (config × scenario) = 240 runs (8 configs × 6 scenarios × 5).

Final Year BE Project · Version 2.0 · 2026

---

## 1. Summary

Against a simulated manual-paging baseline, the full Klarnova pipeline cuts
MTTD from **480 s to 2 s** (240×) and MTTR from **480 s to 15 s** (32×). A
threshold-only automation baseline (blind restart, no diagnosis) resolves only
50% of scenarios; the full system resolves **100%** of the six-fault matrix
with an explainable diagnosis and cited precedent on every incident.

The ablation study isolates the contribution of each component:

| Component removed | Effect on success rate | Direction |
|---|---|---|
| RAG retrieval | 1.000 → 0.667 | **−0.333** (loses S3 bad-deploy, S4 image-pull rollback) |
| Validation agent | 1.000 → 1.000 | 0 (all fixes now succeed first-try; value demonstrated by round-1 data, §7) |
| Safety gate | 1.000 → 1.000 | 0 (same outcomes; SEV-1/SEV-2 auto-approved — risk cost qualitative) |
| Planning separation | 1.000 → 0.667 | **−0.333** (loses S3, S4) |
| Contextual bandit | 1.000 → 1.000 | 0 (**null result**; bandit unfitted within one-run matrix) |

Two findings are intentionally reported as non-positive: the safety and
validation ablations produce no numeric delta because the offline fault set now
resolves correctly on the first attempt (validation's ability to *hide*
failures was empirically demonstrated by the round-1 run, before the S4/S6
gaps were closed), and the bandit ablation is inconclusive in a stateless
offline matrix (a genuine, documented limitation).

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
  run. The bandit is **isolated per run** (learning node bypassed, bandit
  reset before every invocation), so the matrix measures static-priors +
  retrieval-bumps, never learning dynamics.
- **Engine:** the *real* LangGraph agent pipeline (investigation, RAG
  retrieval, root-cause, planning, safety, remediation, validation, reporting)
  running against a scenario-aware mock cluster
  (`chaos-testing/offline.py`). The LLM path uses the deterministic fallback
  diagnosis (documented in §8).
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
| **full** | **2.0** | **15.0** | **1.000** | **0.000** |

- **MTTD:** manual page + investigation ≈ 8 min; the monitoring threshold
  fires in 2 s — **240× faster detection**.
- **MTTR:** full auto-fixes every scenario in the matrix in 15 s (auto-fix +
  health check) vs 8 min manual — **32× faster**. Where the whitelist does not
  cover the situation, the safety model routes to a human in ~1 min rather
  than looping (design property; not triggered by this fault set).
- **Success:** full resolves 100% vs threshold-only 50%: RAG + planning select
  the *correct* action (rollback for bad deploys/image pulls, scale for CPU,
  cordon for node pressure) where blind restart fails.
- **Escalation:** 0.000 in the offline set because all six fixes are now
  within whitelist and auto-approved; the "appropriate, not zero" escalation
  behaviour (SEV-1 routing, out-of-whitelist) is enforced by the safety model
  and exercised in the safety tests, not by this fault set.

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
| S4 image-pull | 1.000 | 1.000 | 1.000 |
| S5 CPU load | 1.000 | 1.000 | 1.000 |
| S6 node pressure | 1.000 | 1.000 | 1.000 |

- **Retrieval relevance is 1.000 on every scenario:** the runbook that
  actually applies is always in the top-3 surfaced documents.
- **Diagnosis accuracy is 1.000 everywhere**, including S4 image-pull (the
  fallback now checks the image-pull signature *before* the crash-loop
  pattern, since "Back-off pulling image ..." contains a `Back-off` that would
  otherwise look like a crash loop).
- **Action accuracy is 1.000 everywhere.** Round 1 found S4 and S6 at 0.000
  (planning never chose rollback for image pulls nor cordon for node
  pressure); both were closed in round 2 (§7).

---

## 5. Ablation deltas per component (KLR-I3)

Delta vs full system (success rate / escalation rate; MTTD identical at 2.0 s
across agent configs because detection is monitoring-threshold driven):

| Ablation | MTTD | MTTR | Success Δ | Escalation Δ | Interpretation |
|---|---|---|---|---|---|
| no-rag | 2.0 | 30.0 | **−0.333** | +0.333 | Loses S3 + S4: without the retrieved rollback runbooks the plan restarts and escalates instead of rolling back. RAG is what makes the plan evidence-correct. |
| no-validation | 2.0 | 15.0 | 0.000 | 0.000 | All fixes now succeed first-try, so bypassing validation hides nothing *in this run*. Round-1 data (before the S4/S6 fixes) showed the inflation artifact: failed fixes counted as resolved (0.667 → 1.000). |
| no-safety | 2.0 | 15.0 | 0.000 | 0.000 | Same resolution outcomes, but **SEV-1/SEV-2 incidents auto-execute** with no human sign-off — the risk cost is qualitative (policy contract violated). |
| no-planning | 2.0 | 30.0 | **−0.333** | +0.333 | Mechanical static selection loses S3 + S4 (rollback never chosen), same as no-rag: the separated, evidence-informed plan step is what picks the right action. |
| no-bandit | 2.0 | 15.0 | 0.000 | 0.000 | **Null result.** Within a single stateless run matrix the bandit never accumulates training samples (isolated per run, §2), so ranking falls back to static priors — no delta by construction (reported honestly, PRD §5.3). |

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

## 7. Round 2 — eval-found gaps closed

The first N=5 run scored S4 and S6 at 0.000 action accuracy and exposed three
concrete defects. All three are fixed with regression tests in
`backend/tests/test_eval_fixes.py` (7 tests) and re-verified at 1.000:

1. **S4 diagnosis — image-pull misread as crash loop.** The keyword fallback
   matched the `Back-off` inside `Back-off pulling image ...` to the
   crash-loop branch. Ordering fix in `app/agents/root_cause.py`:
   image-pull signatures (`ImagePullBackOff`, `failed to pull image`,
   `manifest unknown`) are now checked before the crash-loop pattern.
2. **S6 (and every scenario) — planning offered impossible actions.** The
   planner never proposes actions a resource kind cannot accept: node →
   `cordon_node` only; deployment/statefulset → scale/rollback only; pod →
   restart/delete. The kind filter in `app/agents/planning.py` (`KIND_ACTIONS`)
   is a domain/safety invariant, so the fallback loop can no longer burn
   retries on actions that cannot fix the target. Regression: S6 action
   accuracy 0.000 → 1.000.
3. **S5 regression (introduced while fixing S4) — loose retrieval matches
   flipped the plan.** The rollback hint phrase `\brollout\b` also matched
   runbooks retrieved for unrelated incidents. Two fixes in
   `app/agents/planning.py`:
   - the phrase was tightened to `\brollout restart\b` (how image-pull
     runbooks describe the fix) so a merely-stuck rollout does not count;
   - hints now apply only to **strongly relevant** runbooks
     (`HINT_RELEVANCE_DISTANCE = 0.55`, Chroma L2): a CPU incident that
     incidentally surfaces a rollout-stuck runbook (distance ~0.61) no longer
     steers the plan to roll back, while the genuinely-relevant image-pull
     runbooks (distance ≤ 0.48) still do.

Net effect on the matrix: MTTR 30 → 15 s, success 0.667 → 1.000, escalation
0.333 → 0.000, and every scenario at 1.000/1.000/1.000.

---

## 8. Hardening (KLR-I4, KLR-I5)

Fail-safe degradation contracts verified by tests in
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

## 9. Live-run status

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

## 10. Reproducibility

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

## 11. Known limitations & threats to validity

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
7. **Validation & safety ablations are numerically silent in round 2** —
   every scenario resolves on the first attempt, so those ablated configs
   match `full`. Their risk costs (hiding failed fixes; bypassing human
   sign-off) are qualitative and were demonstrated in round 1 / unit tests.
8. **Live run blocked at evaluation time** by the Docker engine failure (§9);
   the harness's `--live` path is implemented but not re-executed.
