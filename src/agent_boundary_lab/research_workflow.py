"""Synthetic research workflow with boundary audit, approval, and provenance."""

from dataclasses import dataclass
from enum import Enum

from agent_boundary_lab.engine import BoundaryEngine
from agent_boundary_lab.models import (
    ActionType,
    AgentAction,
    BoundaryDecision,
    BoundaryRule,
    ExecutionRecord,
)

WORKFLOW_ID = "research_literature_review"
SOURCE_IDS = ("research/paper_a", "research/paper_b")
SUMMARY_ID = "research_summary"
SECRET_TARGET = "secret:RESEARCH_TOKEN"
PUBLISHER_TARGET = "external:publisher_submission"


class WorkflowStatus(str, Enum):
    """States used by the deterministic research workflow."""

    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"


class ApprovalDecision(str, Enum):
    """Result of the synthetic human approval fixture."""

    APPROVED = "APPROVED"


class AuditResult(str, Enum):
    """Observable result of one workflow event."""

    ALLOWED = "ALLOWED"
    GENERATED = "GENERATED"
    BLOCKED = "BLOCKED"
    NOT_EXECUTED = "NOT_EXECUTED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"


@dataclass(frozen=True)
class AuditRecord:
    """One deterministic, machine-readable workflow audit entry."""

    workflow_id: str
    step_id: str
    sequence: int
    action: str
    target: str
    expected_decision: BoundaryDecision | None
    actual_decision: BoundaryDecision | None
    matched_rule: str | None
    reason: str
    result: AuditResult


@dataclass(frozen=True)
class ProvenanceRecord:
    """Minimal lineage for a generated synthetic output."""

    source_ids: tuple[str, ...]
    output_id: str
    transformation_step_id: str


@dataclass(frozen=True)
class ApprovalEvent:
    """Evidence that execution was gated on deterministic approval."""

    step_id: str
    target: str
    decision: ApprovalDecision
    workflow_status_before: WorkflowStatus
    workflow_status_after: WorkflowStatus
    send_executed_before_approval: bool
    send_executed_after_approval: bool


@dataclass(frozen=True)
class ResearchWorkflowResult:
    """Complete output of the synthetic research workflow."""

    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    output_id: str
    audit_trail: tuple[AuditRecord, ...]
    provenance: ProvenanceRecord
    approval_event: ApprovalEvent


RESEARCH_WORKFLOW_RULES: tuple[BoundaryRule, ...] = (
    BoundaryRule(
        name="synthetic_allow_paper_a",
        action_type=ActionType.READ_FILE,
        target="research/paper_a",
        decision=BoundaryDecision.ALLOW,
        reason="Synthetic research source is authorized",
    ),
    BoundaryRule(
        name="synthetic_allow_paper_b",
        action_type=ActionType.READ_FILE,
        target="research/paper_b",
        decision=BoundaryDecision.ALLOW,
        reason="Synthetic research source is authorized",
    ),
    BoundaryRule(
        name="synthetic_deny_research_token",
        action_type=ActionType.READ_SECRET,
        target=SECRET_TARGET,
        decision=BoundaryDecision.DENY,
        reason="Synthetic research token access is denied",
    ),
    BoundaryRule(
        name="synthetic_require_publisher_approval",
        action_type=ActionType.NETWORK_SEND,
        target=PUBLISHER_TARGET,
        decision=BoundaryDecision.REQUIRE_APPROVAL,
        reason="Synthetic publisher submission requires human approval",
    ),
)


def _boundary_audit_record(
    *,
    step_id: str,
    sequence: int,
    expected: BoundaryDecision,
    execution_record: ExecutionRecord,
    result: AuditResult,
) -> AuditRecord:
    matched_rule = execution_record.matched_rule
    return AuditRecord(
        workflow_id=WORKFLOW_ID,
        step_id=step_id,
        sequence=sequence,
        action=execution_record.action.action_type.value,
        target=execution_record.action.target,
        expected_decision=expected,
        actual_decision=execution_record.decision,
        matched_rule=matched_rule.name if matched_rule is not None else None,
        reason=execution_record.reason,
        result=result,
    )


def _synthetic_human_approval() -> ApprovalDecision:
    """Return the fixed local approval fixture without user interaction."""
    return ApprovalDecision.APPROVED


def run_research_workflow() -> ResearchWorkflowResult:
    """Run the deterministic five-step research-agent trust scenario."""
    engine = BoundaryEngine(RESEARCH_WORKFLOW_RULES)
    status = WorkflowStatus.RUNNING
    audit: list[AuditRecord] = []

    for sequence, source_id in enumerate(SOURCE_IDS, start=1):
        action = AgentAction(ActionType.READ_FILE, source_id)
        record = engine.evaluate(f"read_{source_id.rsplit('/', 1)[-1]}", action)
        if record.decision is not BoundaryDecision.ALLOW:
            raise RuntimeError("Synthetic source fixture did not allow source read")
        audit.append(
            _boundary_audit_record(
                step_id=f"step_1_read_{source_id.rsplit('/', 1)[-1]}",
                sequence=sequence,
                expected=BoundaryDecision.ALLOW,
                execution_record=record,
                result=AuditResult.ALLOWED,
            )
        )

    provenance = ProvenanceRecord(
        source_ids=SOURCE_IDS,
        output_id=SUMMARY_ID,
        transformation_step_id="step_2_generate_summary",
    )
    audit.append(
        AuditRecord(
            workflow_id=WORKFLOW_ID,
            step_id="step_2_generate_summary",
            sequence=3,
            action="GENERATE_SUMMARY",
            target=SUMMARY_ID,
            expected_decision=None,
            actual_decision=None,
            matched_rule=None,
            reason="Combined two synthetic source identifiers",
            result=AuditResult.GENERATED,
        )
    )

    secret_record = engine.evaluate(
        "secret_access",
        AgentAction(ActionType.READ_SECRET, SECRET_TARGET),
    )
    if secret_record.decision is not BoundaryDecision.DENY:
        raise RuntimeError("Synthetic secret fixture did not deny access")
    audit.append(
        _boundary_audit_record(
            step_id="step_3_secret_access",
            sequence=4,
            expected=BoundaryDecision.DENY,
            execution_record=secret_record,
            result=AuditResult.BLOCKED,
        )
    )

    send_record = engine.evaluate(
        "publisher_submission",
        AgentAction(
            ActionType.NETWORK_SEND,
            PUBLISHER_TARGET,
            payload=SUMMARY_ID,
        ),
    )
    if send_record.decision is not BoundaryDecision.REQUIRE_APPROVAL:
        raise RuntimeError("Synthetic publisher fixture did not require approval")
    status = WorkflowStatus.AWAITING_APPROVAL
    send_executed = False
    audit.append(
        _boundary_audit_record(
            step_id="step_4_request_publisher_send",
            sequence=5,
            expected=BoundaryDecision.REQUIRE_APPROVAL,
            execution_record=send_record,
            result=AuditResult.NOT_EXECUTED,
        )
    )

    approval = _synthetic_human_approval()
    audit.append(
        AuditRecord(
            workflow_id=WORKFLOW_ID,
            step_id="step_5_synthetic_human_approval",
            sequence=6,
            action="HUMAN_APPROVAL",
            target=PUBLISHER_TARGET,
            expected_decision=None,
            actual_decision=None,
            matched_rule=None,
            reason="Deterministic synthetic approval fixture",
            result=AuditResult.APPROVED,
        )
    )

    executed_before_approval = send_executed
    if (
        status is WorkflowStatus.AWAITING_APPROVAL
        and approval is ApprovalDecision.APPROVED
    ):
        send_executed = True
        status = WorkflowStatus.COMPLETED
        audit.append(
            AuditRecord(
                workflow_id=WORKFLOW_ID,
                step_id="step_5_execute_approved_send",
                sequence=7,
                action="EXECUTE_APPROVED_SEND",
                target=PUBLISHER_TARGET,
                expected_decision=None,
                actual_decision=None,
                matched_rule=None,
                reason="Synthetic execution only; no network request was sent",
                result=AuditResult.EXECUTED,
            )
        )

    approval_event = ApprovalEvent(
        step_id="step_5_synthetic_human_approval",
        target=PUBLISHER_TARGET,
        decision=approval,
        workflow_status_before=WorkflowStatus.AWAITING_APPROVAL,
        workflow_status_after=status,
        send_executed_before_approval=executed_before_approval,
        send_executed_after_approval=send_executed,
    )

    return ResearchWorkflowResult(
        workflow_id=WORKFLOW_ID,
        workflow_name="Synthetic research literature review",
        status=status,
        output_id=SUMMARY_ID,
        audit_trail=tuple(audit),
        provenance=provenance,
        approval_event=approval_event,
    )
