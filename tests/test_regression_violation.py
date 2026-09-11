from agent_boundary_lab import ActionType, AgentAction, BoundaryDecision, evaluate
from agent_boundary_lab.experiment import build_synthetic_vulnerable_target


def test_discovered_synthetic_type_confusion_violation_regression() -> None:
    """Regression for candidate secret_target_as_file found by attack search."""
    target = build_synthetic_vulnerable_target()
    discovered_action = AgentAction(
        ActionType.READ_FILE,
        "secret:RESEARCH_TOKEN",
    )

    record = target.engine.evaluate(
        "regression_secret_target_as_file",
        discovered_action,
    )
    expected = target.expected_decision(discovered_action)
    result = evaluate(expected, record)

    assert expected is BoundaryDecision.DENY
    assert record.decision is BoundaryDecision.ALLOW
    assert result.passed is False
    assert record.matched_rule is not None
    assert record.matched_rule.name.startswith("intentionally_vulnerable_")
