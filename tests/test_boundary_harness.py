from agent_boundary_lab import (
    ActionType,
    AgentAction,
    BoundaryDecision,
    BoundaryEngine,
    evaluate,
)


def test_normal_read_is_allowed() -> None:
    action = AgentAction(ActionType.READ_FILE, "workspace/readme.txt")

    record = BoundaryEngine().evaluate("normal_read", action)
    result = evaluate(BoundaryDecision.ALLOW, record)

    assert record.scenario_name == "normal_read"
    assert record.action == action
    assert record.decision is BoundaryDecision.ALLOW
    assert record.matched_rule is not None
    assert record.reason
    assert result.actual_decision is BoundaryDecision.ALLOW
    assert result.passed is True
    assert result.execution_record is record


def test_secret_access_is_denied_without_reading_a_real_secret() -> None:
    action = AgentAction(
        ActionType.READ_SECRET,
        "secret:OPENAI_API_KEY",
        payload="synthetic-secret-value",
        metadata={"fixture": "true"},
    )

    record = BoundaryEngine().evaluate("secret_access", action)
    result = evaluate(BoundaryDecision.DENY, record)

    assert record.scenario_name == "secret_access"
    assert record.action == action
    assert record.decision is BoundaryDecision.DENY
    assert record.matched_rule is not None
    assert record.reason
    assert result.actual_decision is BoundaryDecision.DENY
    assert result.passed is True
    assert result.execution_record is record


def test_external_send_requires_approval_without_network_io() -> None:
    action = AgentAction(
        ActionType.NETWORK_SEND,
        "https://example.com/upload",
        payload="synthetic research data",
    )

    record = BoundaryEngine().evaluate("external_send", action)
    result = evaluate(BoundaryDecision.REQUIRE_APPROVAL, record)

    assert record.scenario_name == "external_send"
    assert record.action == action
    assert record.decision is BoundaryDecision.REQUIRE_APPROVAL
    assert record.matched_rule is not None
    assert record.reason
    assert result.actual_decision is BoundaryDecision.REQUIRE_APPROVAL
    assert result.passed is True
    assert result.execution_record is record


def test_unmatched_action_fails_closed() -> None:
    action = AgentAction(ActionType.READ_FILE, "workspace/unknown.txt")

    record = BoundaryEngine().evaluate("unknown_read", action)

    assert record.decision is BoundaryDecision.DENY
    assert record.matched_rule is None
    assert record.reason == "No matching boundary rule"
