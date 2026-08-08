from app.bandit.learning import reward_for, selected_action


def _state(**overrides):
    state = {
        "selected_action": {"action_type": "restart_pod"},
        "remediation_success": True,
        "is_resolved": True,
        "incident_data": {"labels": {"alertname": "KubePodCrashLooping"}},
    }
    state.update(overrides)
    return state


def test_selected_action_whitelisted():
    assert selected_action(_state()) == "restart_pod"


def test_selected_action_rejects_non_whitelisted():
    state = _state(selected_action={"action_type": "rm_rf"})
    assert selected_action(state) is None


def test_reward_resolved_is_one():
    assert reward_for(_state(is_resolved=True)) == 1.0


def test_reward_failed_is_zero():
    assert reward_for(_state(is_resolved=False)) == 0.0


def test_reward_none_when_not_executed():
    state = _state(remediation_success=False, is_resolved=False)
    assert reward_for(state) is None
