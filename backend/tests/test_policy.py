from app.policy.engine import evaluate, requires_approval


def test_sev1_always_requires_approval():
    decision = evaluate("restart_pod", "SEV-1", confidence=0.99)
    assert decision.mode == "require_approval"
    assert requires_approval("restart_pod", "SEV-1", 0.99) is True


def test_low_confidence_requires_approval_even_in_auto_tier():
    decision = evaluate("restart_pod", "SEV-3", confidence=0.4)
    assert decision.mode == "require_approval"


def test_auto_tier_runs_without_approval():
    decision = evaluate("restart_pod", "SEV-3", confidence=0.9)
    assert decision.mode == "auto"


def test_non_whitelisted_action_denied():
    decision = evaluate("delete_namespace", "SEV-3", confidence=0.99)
    assert decision.mode == "deny"


def test_default_policy_rules_load():
    from app.policy.engine import load_rules

    rules = load_rules()
    assert rules["confidence_threshold"] == 0.75
    assert "restart_pod" in rules["actions"]
    assert "cordon_node" in rules["actions"]
