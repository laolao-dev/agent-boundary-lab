from agent_boundary_lab.models import BoundaryDecision
from agent_boundary_lab.research_workflow import (
    ApprovalDecision,
    AuditResult,
    WorkflowStatus,
    run_research_workflow,
)


def test_research_workflow_completes_after_approval() -> None:
    result = run_research_workflow()

    assert result.status is WorkflowStatus.COMPLETED
    assert result.output_id == "research_summary"
    assert result.approval_event.decision is ApprovalDecision.APPROVED


def test_secret_access_is_denied_by_research_workflow_policy() -> None:
    result = run_research_workflow()
    secret_audit = next(
        record
        for record in result.audit_trail
        if record.step_id == "step_3_secret_access"
    )

    assert secret_audit.expected_decision is BoundaryDecision.DENY
    assert secret_audit.actual_decision is BoundaryDecision.DENY
    assert secret_audit.result is AuditResult.BLOCKED


def test_external_send_is_not_executed_until_approval() -> None:
    result = run_research_workflow()
    send_request = next(
        record
        for record in result.audit_trail
        if record.step_id == "step_4_request_publisher_send"
    )
    approval = next(
        record
        for record in result.audit_trail
        if record.step_id == "step_5_synthetic_human_approval"
    )
    execution = next(
        record
        for record in result.audit_trail
        if record.step_id == "step_5_execute_approved_send"
    )

    assert send_request.actual_decision is BoundaryDecision.REQUIRE_APPROVAL
    assert send_request.result is AuditResult.NOT_EXECUTED
    assert send_request.sequence < approval.sequence < execution.sequence
    assert result.approval_event.send_executed_before_approval is False
    assert result.approval_event.send_executed_after_approval is True


def test_summary_provenance_points_to_both_sources() -> None:
    provenance = run_research_workflow().provenance

    assert provenance.source_ids == ("research/paper_a", "research/paper_b")
    assert provenance.output_id == "research_summary"
    assert provenance.transformation_step_id == "step_2_generate_summary"


def test_audit_trail_contains_every_boundary_decision() -> None:
    audit = run_research_workflow().audit_trail
    boundary_records = tuple(
        record for record in audit if record.actual_decision is not None
    )

    assert tuple(record.sequence for record in audit) == tuple(range(1, 8))
    assert len(boundary_records) == 4
    assert all(record.expected_decision is not None for record in boundary_records)
    assert all(record.matched_rule is not None for record in boundary_records)
    assert all(record.reason for record in audit)
