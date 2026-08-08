"""Runtime ablation toggles for the Epic I evaluation study.

Unlike ``app.config`` (pinned at import time), these flags are mutable so the
evaluation harness can switch components on/off between runs in a single
process. Defaults are all ``False``: the system runs fully featured unless the
harness flips a switch.

Interpretation of each switch (see ``docs/evaluation.md`` §4):

- ``disable_rag``: retrieval returns no precedent; diagnosis and planning run
  without grounded runbooks.
- ``disable_validation``: every remediation is treated as resolved (no health
  re-check, no retry, no escalation). Failed fixes are counted as success.
- ``disable_safety``: the policy gate always auto-approves; even SEV-1 and
  human-gated actions execute without approval.
- ``disable_planning``: the plan step is mechanical - the action is selected by
  static priority order, ignoring bandit ranking and retrieval hints
  (planning no longer separated/informed by evidence).
- ``disable_bandit``: planning uses static priors instead of the learned
  contextual bandit, but still applies retrieval hints.
"""

from dataclasses import dataclass


@dataclass
class Ablation:
    disable_rag: bool = False
    disable_validation: bool = False
    disable_safety: bool = False
    disable_planning: bool = False
    disable_bandit: bool = False


ablation = Ablation()
