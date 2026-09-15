"""Deterministic workflow-level assurance checks."""

from collections.abc import Callable
from datetime import UTC, datetime

from agent_boundary_lab.assurance.models import (
    ApprovalDecision,
    AssuranceReport,
    CheckName,
    CheckResult,
    CheckStatus,
    Finding,
    OverallStatus,
    ReportSummary,
    Severity,
    Workflow,
)
from agent_boundary_lab.models import BoundaryDecision

FindingSpec = tuple[Severity, str, tuple[str, ...], str, str | None, str | None]


def _governance_specs(workflow: Workflow) -> list[FindingSpec]:
    specs: list[FindingSpec] = []
    for step in workflow.steps:
        decision = step.governance_decision
        if decision is None:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Step has no explicit governance decision.",
                    step.evidence_refs,
                    "Record ALLOW, DENY, or REQUIRE_APPROVAL before dispatch.",
                    step.step_id,
                    None,
                )
            )
        if decision is BoundaryDecision.DENY and step.dispatched:
            specs.append(
                (
                    Severity.HIGH,
                    "Step was dispatched despite a DENY governance decision.",
                    step.evidence_refs,
                    "Block dispatch when the governance decision is DENY.",
                    step.step_id,
                    None,
                )
            )
        gated = step.approval_required or decision is BoundaryDecision.REQUIRE_APPROVAL
        approved = (
            step.approval_record is not None
            and step.approval_record.decision is ApprovalDecision.APPROVED
        )
        if gated and step.dispatched and not approved:
            refs = (
                step.approval_record.evidence_refs
                if step.approval_record is not None
                else step.evidence_refs
            )
            specs.append(
                (
                    Severity.HIGH,
                    "Approval-gated step was dispatched without an APPROVED record.",
                    refs,
                    "Record approved structured approval evidence before dispatch.",
                    step.step_id,
                    None,
                )
            )
    return specs


def _provenance_specs(workflow: Workflow) -> list[FindingSpec]:
    specs: list[FindingSpec] = []
    evidence_ids = {item.evidence_id for item in workflow.evidence}
    step_ids = {step.step_id for step in workflow.steps}
    for step in workflow.steps:
        dangling = tuple(ref for ref in step.evidence_refs if ref not in evidence_ids)
        if dangling:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Step references evidence that does not exist.",
                    dangling,
                    "Create the evidence records or remove the dangling references.",
                    step.step_id,
                    None,
                )
            )
    for claim in workflow.claims:
        if not claim.evidence_refs:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Claim does not reference any evidence.",
                    (),
                    "Add at least one existing evidence identifier to the claim.",
                    None,
                    claim.claim_id,
                )
            )
        dangling = tuple(ref for ref in claim.evidence_refs if ref not in evidence_ids)
        if dangling:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Claim references evidence that does not exist.",
                    dangling,
                    "Create the evidence records or remove the dangling references.",
                    None,
                    claim.claim_id,
                )
            )
    for item in workflow.evidence:
        if item.source is None:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Evidence has no source identifier.",
                    (item.evidence_id,),
                    "Record the bounded source identifier for this evidence.",
                    None,
                    None,
                )
            )
        if item.produced_by_step is None:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Evidence is not linked to a producing workflow step.",
                    (item.evidence_id,),
                    "Record the step_id that produced or captured this evidence.",
                    None,
                    None,
                )
            )
        elif item.produced_by_step not in step_ids:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Evidence references a producing step that does not exist.",
                    (item.evidence_id,),
                    "Link the evidence to an existing workflow step.",
                    item.produced_by_step,
                    None,
                )
            )
    return specs


def _human_review_specs(workflow: Workflow) -> list[FindingSpec]:
    specs: list[FindingSpec] = []
    for step in workflow.steps:
        gated = (
            step.approval_required
            or step.governance_decision is BoundaryDecision.REQUIRE_APPROVAL
        )
        if not gated:
            continue
        approval = step.approval_record
        if approval is None:
            specs.append(
                (
                    Severity.HIGH if step.dispatched else Severity.MEDIUM,
                    "Approval-gated step has no structured approval record.",
                    (),
                    "Attach a structured approval record; identity is not authenticated.",
                    step.step_id,
                    None,
                )
            )
        elif approval.decision is ApprovalDecision.REJECTED and step.dispatched:
            specs.append(
                (
                    Severity.HIGH,
                    "Step was dispatched despite a REJECTED approval record.",
                    approval.evidence_refs,
                    "Honor the structured rejection and do not dispatch the step.",
                    step.step_id,
                    None,
                )
            )
    return specs


def _audit_specs(workflow: Workflow) -> list[FindingSpec]:
    specs: list[FindingSpec] = []
    for step in workflow.steps:
        important = step.dispatched or step.governance_decision in {
            BoundaryDecision.DENY,
            BoundaryDecision.REQUIRE_APPROVAL,
        }
        audit = step.audit_record
        if audit is None:
            if important:
                specs.append(
                    (
                        Severity.MEDIUM,
                        "Important executed or blocked step has no audit record.",
                        step.evidence_refs,
                        "Record action, governance decision, and outcome for the step.",
                        step.step_id,
                        None,
                    )
                )
            continue
        missing = tuple(
            name
            for name, value in (
                ("action", audit.action),
                ("decision", audit.decision),
                ("outcome", audit.outcome),
            )
            if value is None
        )
        if missing:
            specs.append(
                (
                    Severity.MEDIUM,
                    f"Audit record is missing: {', '.join(missing)}.",
                    step.evidence_refs,
                    "Record action, governance decision, and outcome for the step.",
                    step.step_id,
                    None,
                )
            )
        if audit.action is not None and audit.action != step.action:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Audit action does not match the workflow step action.",
                    step.evidence_refs,
                    "Record the exact workflow step action in the audit record.",
                    step.step_id,
                    None,
                )
            )
        if (
            step.governance_decision is not None
            and audit.decision is not None
            and audit.decision != step.governance_decision.value
        ):
            specs.append(
                (
                    Severity.MEDIUM,
                    "Audit decision does not match the governance decision.",
                    step.evidence_refs,
                    "Record the exact governance decision in the audit record.",
                    step.step_id,
                    None,
                )
            )
    return specs


def _status(findings: tuple[Finding, ...]) -> CheckStatus:
    if not findings:
        return CheckStatus.PASS
    if any(finding.severity is Severity.HIGH for finding in findings):
        return CheckStatus.FAIL
    return CheckStatus.PARTIAL


def _materialize(check: CheckName, specs: list[FindingSpec]) -> tuple[Finding, ...]:
    return tuple(
        Finding(
            finding_id=f"{check.value}-{index:03d}",
            check=check,
            severity=severity,
            message=message,
            evidence_refs=evidence_refs,
            remediation_hint=remediation,
            step_id=step_id,
            claim_id=claim_id,
        )
        for index, (
            severity,
            message,
            evidence_refs,
            remediation,
            step_id,
            claim_id,
        ) in enumerate(specs, start=1)
    )


def verify_workflow(
    workflow: Workflow, *, generated_at: str | None = None
) -> AssuranceReport:
    """Run all v0.2 checks and return a deterministic semantic report."""
    checkers: tuple[tuple[CheckName, Callable[[Workflow], list[FindingSpec]]], ...] = (
        (CheckName.GOVERNANCE, _governance_specs),
        (CheckName.PROVENANCE, _provenance_specs),
        (CheckName.HUMAN_REVIEW, _human_review_specs),
        (CheckName.AUDIT, _audit_specs),
    )
    check_results: list[CheckResult] = []
    all_findings: list[Finding] = []
    for check, checker in checkers:
        findings = _materialize(check, checker(workflow))
        all_findings.extend(findings)
        check_results.append(
            CheckResult(
                check=check,
                status=_status(findings),
                finding_ids=tuple(finding.finding_id for finding in findings),
            )
        )

    findings_tuple = tuple(all_findings)
    complete = all(result.status is CheckStatus.PASS for result in check_results)
    timestamp = generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return AssuranceReport(
        workflow_id=workflow.workflow_id,
        generated_at=timestamp,
        checks=tuple(check_results),
        findings=findings_tuple,
        summary=ReportSummary(
            overall_status=(
                OverallStatus.COMPLETE if complete else OverallStatus.INCOMPLETE
            ),
            total_findings=len(findings_tuple),
            high_findings=sum(
                finding.severity is Severity.HIGH for finding in findings_tuple
            ),
            medium_findings=sum(
                finding.severity is Severity.MEDIUM for finding in findings_tuple
            ),
            low_findings=sum(
                finding.severity is Severity.LOW for finding in findings_tuple
            ),
        ),
    )
