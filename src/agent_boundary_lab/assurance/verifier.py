"""Deterministic workflow-level assurance checks."""

from dataclasses import dataclass
from datetime import UTC, datetime

from agent_boundary_lab.assurance.models import (
    ApprovalDecision,
    ApprovalRequirement,
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


@dataclass(frozen=True)
class CheckAssessment:
    """Internal check output including coverage needed for honest status."""

    specs: tuple[FindingSpec, ...]
    evaluated_items: int
    not_evaluated_items: int = 0


def _governance_assessment(workflow: Workflow) -> CheckAssessment:
    specs: list[FindingSpec] = []
    events = {event.event_id: event for event in workflow.events}
    evaluated = 0
    not_evaluated = 0
    contexts = {item.event_id: item for item in workflow.assurance_context.events}

    for event in workflow.events:
        context = contexts.get(event.event_id)
        if context is None or context.governance_decision is None:
            not_evaluated += 1
            continue
        decision = context.governance_decision
        if (
            decision in {BoundaryDecision.DENY, BoundaryDecision.REQUIRE_APPROVAL}
            and event.executed is None
        ):
            not_evaluated += 1
            continue
        evaluated += 1
        if decision is BoundaryDecision.DENY and event.executed is True:
            specs.append(
                (
                    Severity.HIGH,
                    "Event was executed despite a DENY governance decision.",
                    context.governance_evidence_refs,
                    "Block execution when the assurance decision is DENY.",
                    event.event_id,
                    None,
                )
            )
        approved = (
            context.approval_record is not None
            and context.approval_record.decision is ApprovalDecision.APPROVED
        )
        if (
            decision is BoundaryDecision.REQUIRE_APPROVAL
            and event.executed is True
            and not approved
        ):
            specs.append(
                (
                    Severity.HIGH,
                    "Approval-gated event was executed without an APPROVED record.",
                    (
                        context.approval_record.evidence_refs
                        if context.approval_record is not None
                        else context.governance_evidence_refs
                    ),
                    "Record approved review evidence before executing the event.",
                    event.event_id,
                    None,
                )
            )

    for context in workflow.assurance_context.events:
        if context.event_id not in events:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Assurance context references an event that does not exist.",
                    context.governance_evidence_refs,
                    "Link the assurance context to an observed event identifier.",
                    context.event_id,
                    None,
                )
            )

    return CheckAssessment(tuple(specs), evaluated, not_evaluated)


def _provenance_assessment(workflow: Workflow) -> CheckAssessment:
    specs: list[FindingSpec] = []
    evidence_ids = {item.evidence_id for item in workflow.evidence}
    event_ids = {event.event_id for event in workflow.events}
    source_ids = {source.source_id for source in workflow.sources}
    artifact_ids = {artifact.artifact_id for artifact in workflow.artifacts}

    for event in workflow.events:
        dangling = tuple(ref for ref in event.evidence_refs if ref not in evidence_ids)
        if dangling:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Event references evidence that does not exist.",
                    dangling,
                    "Create the evidence records or remove the dangling references.",
                    event.event_id,
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
        if not item.source_refs and not item.parent_evidence_refs:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Evidence has neither source references nor parent evidence.",
                    (item.evidence_id,),
                    "Record source_refs or one or more parent_evidence_refs.",
                    None,
                    None,
                )
            )
        dangling_sources = tuple(
            ref for ref in item.source_refs if ref not in source_ids
        )
        if dangling_sources:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Evidence references source records that do not exist.",
                    (item.evidence_id,),
                    "Create the source records or remove the dangling references.",
                    None,
                    None,
                )
            )
        if (
            item.produced_by_event is not None
            and item.produced_by_event not in event_ids
        ):
            specs.append(
                (
                    Severity.MEDIUM,
                    "Evidence references a producing event that does not exist.",
                    (item.evidence_id,),
                    "Link the evidence to an existing observed event.",
                    item.produced_by_event,
                    None,
                )
            )
        dangling_parents = tuple(
            ref for ref in item.parent_evidence_refs if ref not in evidence_ids
        )
        if dangling_parents:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Evidence references parent evidence that does not exist.",
                    dangling_parents,
                    "Create the parent evidence records or remove the dangling references.",
                    None,
                    None,
                )
            )

    referenced_source_ids = {
        ref for item in workflow.evidence for ref in item.source_refs
    } | {ref for artifact in workflow.artifacts for ref in artifact.source_refs}
    for source in workflow.sources:
        if source.source_id not in referenced_source_ids:
            specs.append(
                (
                    Severity.MEDIUM,
                    f"Source record '{source.source_id}' is not linked to evidence or an artifact.",
                    (),
                    "Reference the source from evidence or a workflow artifact.",
                    None,
                    None,
                )
            )

    for artifact in workflow.artifacts:
        if (
            artifact.produced_by_event is None
            and not artifact.parent_artifact_refs
            and not artifact.source_refs
            and not artifact.evidence_refs
        ):
            specs.append(
                (
                    Severity.MEDIUM,
                    f"Artifact '{artifact.artifact_id}' has no recorded lineage.",
                    (),
                    "Link the artifact to a producing event or parent, source, or evidence records.",
                    None,
                    None,
                )
            )
        if (
            artifact.produced_by_event is not None
            and artifact.produced_by_event not in event_ids
        ):
            specs.append(
                (
                    Severity.MEDIUM,
                    f"Artifact '{artifact.artifact_id}' references a producing event that does not exist.",
                    artifact.evidence_refs,
                    "Link the artifact to an existing observed event.",
                    artifact.produced_by_event,
                    None,
                )
            )
        dangling_artifacts = tuple(
            ref for ref in artifact.parent_artifact_refs if ref not in artifact_ids
        )
        if dangling_artifacts:
            specs.append(
                (
                    Severity.MEDIUM,
                    f"Artifact '{artifact.artifact_id}' references parent artifacts that do not exist.",
                    artifact.evidence_refs,
                    "Create the parent artifacts or remove the dangling references.",
                    None,
                    None,
                )
            )
        dangling_sources = tuple(
            ref for ref in artifact.source_refs if ref not in source_ids
        )
        if dangling_sources:
            specs.append(
                (
                    Severity.MEDIUM,
                    f"Artifact '{artifact.artifact_id}' references source records that do not exist.",
                    artifact.evidence_refs,
                    "Create the source records or remove the dangling references.",
                    None,
                    None,
                )
            )
        dangling_evidence = tuple(
            ref for ref in artifact.evidence_refs if ref not in evidence_ids
        )
        if dangling_evidence:
            specs.append(
                (
                    Severity.MEDIUM,
                    f"Artifact '{artifact.artifact_id}' references evidence that does not exist.",
                    dangling_evidence,
                    "Create the evidence records or remove the dangling references.",
                    None,
                    None,
                )
            )

    for context in workflow.assurance_context.events:
        refs = context.governance_evidence_refs
        if context.approval_record is not None:
            refs += context.approval_record.evidence_refs
        dangling = tuple(ref for ref in refs if ref not in evidence_ids)
        if dangling:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Assurance context references evidence that does not exist.",
                    dangling,
                    "Create the evidence records or remove the dangling references.",
                    context.event_id,
                    None,
                )
            )

    evaluated = (
        len(workflow.sources)
        + len(workflow.evidence)
        + len(workflow.claims)
        + len(workflow.artifacts)
        + sum(1 for event in workflow.events if event.evidence_refs)
        + sum(
            1
            for context in workflow.assurance_context.events
            if context.governance_evidence_refs
        )
        + sum(
            1
            for context in workflow.assurance_context.events
            if context.approval_record is not None
            and context.approval_record.evidence_refs
        )
    )
    return CheckAssessment(tuple(specs), evaluated, int(evaluated == 0))


def _human_review_assessment(workflow: Workflow) -> CheckAssessment:
    specs: list[FindingSpec] = []
    contexts = {item.event_id: item for item in workflow.assurance_context.events}
    evaluated = 0
    not_evaluated = 0

    for event in workflow.events:
        context = contexts.get(event.event_id)
        requirement = (
            ApprovalRequirement.UNKNOWN
            if context is None
            else context.approval_requirement
        )
        approval = None if context is None else context.approval_record
        if approval is not None and approval.decision is ApprovalDecision.REJECTED:
            if event.executed is None:
                not_evaluated += 1
                continue
            evaluated += 1
            if requirement is ApprovalRequirement.UNKNOWN:
                not_evaluated += 1
            if event.executed is True:
                specs.append(
                    (
                        Severity.HIGH,
                        "Event was executed despite a REJECTED approval record.",
                        approval.evidence_refs,
                        "Honor the structured rejection and do not execute the event.",
                        event.event_id,
                        None,
                    )
                )
            continue
        if requirement is ApprovalRequirement.UNKNOWN:
            not_evaluated += 1
            continue
        evaluated += 1
        if requirement is ApprovalRequirement.NOT_REQUIRED:
            continue
        assert context is not None
        if approval is None:
            specs.append(
                (
                    Severity.HIGH if event.executed is True else Severity.MEDIUM,
                    "Approval-required event has no structured approval record.",
                    (),
                    "Attach a structured approval record; identity is not authenticated.",
                    event.event_id,
                    None,
                )
            )
    return CheckAssessment(tuple(specs), evaluated, not_evaluated)


def _audit_assessment(workflow: Workflow) -> CheckAssessment:
    specs: list[FindingSpec] = []
    sequences = [
        event.sequence for event in workflow.events if event.sequence is not None
    ]
    if sequences and len(sequences) != len(workflow.events):
        specs.append(
            (
                Severity.MEDIUM,
                "Observed event ordering is only partially recorded.",
                (),
                "Record sequence for every event when sequence data is available.",
                None,
                None,
            )
        )
    duplicates = sorted({value for value in sequences if sequences.count(value) > 1})
    if duplicates:
        specs.append(
            (
                Severity.MEDIUM,
                "Observed event sequence values are not unique.",
                (),
                "Use a unique sequence value for each ordered event.",
                None,
                None,
            )
        )

    for event in workflow.events:
        if event.event_type is None and event.action is None:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Observed event has neither an event type nor an action.",
                    event.evidence_refs,
                    "Record the observed event type or action without adding a judgment.",
                    event.event_id,
                    None,
                )
            )
        if event.executed is True and event.observation is None and event.error is None:
            specs.append(
                (
                    Severity.MEDIUM,
                    "Executed event has neither an observation nor an error.",
                    event.evidence_refs,
                    "Record the observed outcome or error for the executed event.",
                    event.event_id,
                    None,
                )
            )

    return CheckAssessment(tuple(specs), len(workflow.events))


def _status(assessment: CheckAssessment, findings: tuple[Finding, ...]) -> CheckStatus:
    if any(finding.severity is Severity.HIGH for finding in findings):
        return CheckStatus.FAIL
    if findings or assessment.not_evaluated_items:
        if assessment.evaluated_items == 0 and not findings:
            return CheckStatus.NOT_EVALUATED
        return CheckStatus.PARTIAL
    return CheckStatus.PASS


def _materialize(
    check: CheckName, specs: tuple[FindingSpec, ...]
) -> tuple[Finding, ...]:
    return tuple(
        Finding(
            finding_id=f"{check.value}-{index:03d}",
            check=check,
            severity=severity,
            message=message,
            evidence_refs=evidence_refs,
            remediation_hint=remediation,
            event_id=event_id,
            claim_id=claim_id,
        )
        for index, (
            severity,
            message,
            evidence_refs,
            remediation,
            event_id,
            claim_id,
        ) in enumerate(specs, start=1)
    )


def verify_workflow(
    workflow: Workflow, *, generated_at: str | None = None
) -> AssuranceReport:
    """Run all v0.2 checks and return a deterministic semantic report."""
    assessments = (
        (CheckName.GOVERNANCE, _governance_assessment(workflow)),
        (CheckName.PROVENANCE, _provenance_assessment(workflow)),
        (CheckName.HUMAN_REVIEW, _human_review_assessment(workflow)),
        (CheckName.AUDIT, _audit_assessment(workflow)),
    )
    check_results: list[CheckResult] = []
    all_findings: list[Finding] = []
    for check, assessment in assessments:
        findings = _materialize(check, assessment.specs)
        all_findings.extend(findings)
        check_results.append(
            CheckResult(
                check=check,
                status=_status(assessment, findings),
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
