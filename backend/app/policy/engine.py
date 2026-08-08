"""Severity-aware policy engine (deterministic, outside the LLM path).

Enforces the safety rules from the Security & Access Control document:

* SEV-1 critical incidents ALWAYS require human approval, regardless of
  the confidence score (hard rule, not configurable).
* A confidence score below ``confidence_threshold`` routes the action to a
  human regardless of its risk tier.
* Only whitelisted actions can ever execute; anything else is denied.
"""
import os
from dataclasses import dataclass
from functools import lru_cache

import yaml

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules", "default.yaml")

# The safe-action whitelist. Anything an LLM invents that is not here cannot run.
WHITELIST: list[str] = [
    "restart_pod",
    "delete_pod",
    "scale_deployment",
    "rollback_deployment",
    "cordon_node",
]

SEV_ORDER = {"SEV-1": 1, "SEV-2": 2, "SEV-3": 3, "SEV-4": 4}


@dataclass(frozen=True)
class Decision:
    mode: str  # "auto" | "require_approval" | "deny"
    reason: str


@lru_cache(maxsize=1)
def load_rules(path: str | None = None) -> dict:
    path = path or RULES_PATH
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _rule_for(action: str, severity: str, rules: dict) -> str:
    actions = rules.get("actions", {})
    action_rules = actions.get(action, {})
    sev_key = f"sev_{SEV_ORDER.get(severity, 4)}"
    if sev_key in action_rules:
        return action_rules[sev_key]
    if "default" in action_rules:
        return action_rules["default"]
    return "deny"


def evaluate(
    action_type: str,
    severity: str = "SEV-3",
    confidence: float = 0.9,
    rules: dict | None = None,
) -> Decision:
    rules = rules or load_rules()
    threshold = float(rules.get("confidence_threshold", 0.75))

    # Hard rule: unknown / non-whitelisted actions are always denied.
    if action_type not in WHITELIST:
        return Decision("deny", f"action '{action_type}' is not on the safe-action whitelist")

    # Hard rule: SEV-1 always requires human approval.
    if severity == "SEV-1":
        return Decision(
            "require_approval",
            "SEV-1 critical incident: human approval is always required",
        )

    # Hard rule: uncertain diagnosis routes to a human regardless of risk tier.
    if confidence < threshold:
        return Decision(
            "require_approval",
            f"confidence {confidence:.2f} below threshold {threshold}",
        )

    mode = _rule_for(action_type, severity, rules)
    if mode not in ("auto", "require_approval"):
        return Decision("deny", f"no policy rule for {action_type} at {severity}")
    return Decision(mode, f"policy rule for {action_type} at {severity}")


def requires_approval(action_type: str, severity: str, confidence: float) -> bool:
    return evaluate(action_type, severity, confidence).mode == "require_approval"
