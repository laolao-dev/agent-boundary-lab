import json
import re
from dataclasses import asdict
from pathlib import Path

import pytest

from agent_boundary_lab.assurance.models import (
    ApprovalRequirement,
    ArtifactRole,
    CheckName,
    CheckStatus,
    OverallStatus,
    Severity,
)
from agent_boundary_lab.assurance.schema import WorkflowValidationError, parse_workflow
from agent_boundary_lab.assurance.verifier import verify_workflow


def _clean_workflow() -> dict[str, object]:
    return {
        "workflow_id": "clean_review",
        "title": "Clean literature review",
        "research_goal": "Review a bounded local corpus.",
        "events": [
            {
                "event_id": "search",
                "event_type": "search",
                "action": "search papers",
                "tool": "local_index",
                "executed": True,
                "evidence_refs": ["search_results"],
                "observation": "results returned",
                "sequence": 1,
            },
            {
                "event_id": "send",
                "event_type": "delivery",
                "action": "send summary",
                "tool": "external_send",
                "executed": True,
                "evidence_refs": ["summary"],
                "observation": "sent after approval",
                "sequence": 2,
            },
        ],
        "sources": [
            {
                "source_id": "local-index",
                "source_type": "local_index",
                "locator": "local:index-query-1",
                "title": "Bounded local index",
            }
        ],
        "evidence": [
            {
                "evidence_id": "search_results",
                "source_refs": ["local-index"],
                "produced_by_event": "search",
            },
            {
                "evidence_id": "summary",
                "parent_evidence_refs": ["search_results"],
                "produced_by_event": "search",
            },
        ],
        "claims": [
            {
                "claim_id": "claim-1",
                "text": "The search returned a bounded result.",
                "evidence_refs": ["search_results"],
                "question_ref": "question-1",
            }
        ],
        "artifacts": [],
        "assurance_context": {
            "events": [
                {
                    "event_id": "search",
                    "governance_decision": "ALLOW",
                    "policy_ref": "fixture-policy",
                    "approval_requirement": "NOT_REQUIRED",
                },
                {
                    "event_id": "send",
                    "governance_decision": "REQUIRE_APPROVAL",
                    "policy_ref": "fixture-policy",
                    "approval_requirement": "REQUIRED",
                    "approval_record": {
                        "approval_id": "approval-1",
                        "decision": "APPROVED",
                        "evidence_refs": ["summary"],
                    },
                },
            ]
        },
    }


def _observed_only_workflow() -> dict[str, object]:
    data = _clean_workflow()
    data.pop("assurance_context")
    return data


def _event_only_workflow() -> dict[str, object]:
    data = _clean_workflow()
    data["sources"] = []
    data["evidence"] = []
    data["claims"] = []
    data["artifacts"] = []
    for index in range(2):
        _nested(data, "events", index)["evidence_refs"] = []
    _nested(data, "assurance_context", "events", 1, "approval_record")[
        "evidence_refs"
    ] = []
    return data


def _verify(data: dict[str, object]):
    return verify_workflow(parse_workflow(data), generated_at="2026-01-01T00:00:00Z")


def _check(report, check: CheckName):
    return next(result for result in report.checks if result.check is check)


def _findings(report, check: CheckName):
    return tuple(finding for finding in report.findings if finding.check is check)


def _mapping_value(value: object, key: str) -> object:
    assert isinstance(value, dict)
    return value[key]


def _list_value(value: object, index: int) -> object:
    assert isinstance(value, list)
    return value[index]


def _nested(data: dict[str, object], *path: str | int) -> dict[str, object]:
    current: object = data
    for part in path:
        if isinstance(part, str):
            current = _mapping_value(current, part)
        else:
            assert isinstance(part, int)
            current = _list_value(current, part)
    assert isinstance(current, dict)
    return current


def test_clean_workflow_is_complete() -> None:
    report = _verify(_clean_workflow())

    assert report.summary.overall_status is OverallStatus.COMPLETE
    assert report.findings == ()
    assert all(result.status is CheckStatus.PASS for result in report.checks)


def test_workflow_without_governance_parses_observed_facts_honestly() -> None:
    workflow = parse_workflow(_observed_only_workflow())

    assert workflow.events[0].executed is True
    assert workflow.events[0].action == "search papers"
    assert workflow.assurance_context.events == ()


def test_missing_governance_context_is_neither_pass_nor_fail() -> None:
    report = _verify(_observed_only_workflow())

    assert _check(report, CheckName.GOVERNANCE).status is CheckStatus.NOT_EVALUATED
    assert report.summary.overall_status is OverallStatus.INCOMPLETE


def test_missing_governance_does_not_create_fabricated_failure() -> None:
    report = _verify(_observed_only_workflow())

    assert _check(report, CheckName.GOVERNANCE).status is not CheckStatus.FAIL
    assert _findings(report, CheckName.GOVERNANCE) == ()


def test_approval_unknown_is_supported_and_not_not_required() -> None:
    data = _observed_only_workflow()
    data["assurance_context"] = {"events": [{"event_id": "search"}]}

    workflow = parse_workflow(data)
    context = workflow.assurance_context.events[0]
    report = verify_workflow(workflow, generated_at="fixed")

    assert context.approval_requirement is ApprovalRequirement.UNKNOWN
    assert context.approval_requirement is not ApprovalRequirement.NOT_REQUIRED
    assert _check(report, CheckName.HUMAN_REVIEW).status is CheckStatus.NOT_EVALUATED


def test_source_and_parent_evidence_references_remain_distinct() -> None:
    workflow = parse_workflow(_clean_workflow())

    source, derived = workflow.evidence
    assert source.source_refs == ("local-index",)
    assert source.parent_evidence_refs == ()
    assert derived.source_refs == ()
    assert derived.parent_evidence_refs == ("search_results",)


def test_claim_evidence_linkage_still_produces_a_finding() -> None:
    data = _clean_workflow()
    _nested(data, "claims", 0)["evidence_refs"] = ["missing"]

    findings = _findings(_verify(data), CheckName.PROVENANCE)

    assert any(finding.claim_id == "claim-1" for finding in findings)
    assert any(finding.evidence_refs == ("missing",) for finding in findings)


def test_control_flow_decision_is_not_governance() -> None:
    data = _observed_only_workflow()
    _nested(data, "events", 0)["control_flow_decision"] = "replan"

    workflow = parse_workflow(data)
    report = verify_workflow(workflow, generated_at="fixed")

    assert workflow.events[0].control_flow_decision == "replan"
    assert _check(report, CheckName.GOVERNANCE).status is CheckStatus.NOT_EVALUATED


def test_audit_completeness_is_evaluated_without_governance() -> None:
    report = _verify(_observed_only_workflow())

    assert _check(report, CheckName.AUDIT).status is CheckStatus.PASS


def test_parent_event_reference_parses() -> None:
    data = _clean_workflow()
    _nested(data, "events", 1)["parent_event_id"] = "search"

    workflow = parse_workflow(data)

    assert workflow.events[1].parent_event_id == "search"


def test_missing_parent_event_is_rejected() -> None:
    data = _clean_workflow()
    _nested(data, "events", 1)["parent_event_id"] = "missing"

    with pytest.raises(WorkflowValidationError, match=r"unknown event_id 'missing'"):
        parse_workflow(data)


def test_self_parent_event_is_rejected() -> None:
    data = _clean_workflow()
    _nested(data, "events", 0)["parent_event_id"] = "search"

    with pytest.raises(WorkflowValidationError, match="cannot reference itself"):
        parse_workflow(data)


def test_parent_event_cycle_is_rejected() -> None:
    data = _clean_workflow()
    _nested(data, "events", 0)["parent_event_id"] = "send"
    _nested(data, "events", 1)["parent_event_id"] = "search"

    with pytest.raises(WorkflowValidationError, match="cycle"):
        parse_workflow(data)


def test_multiple_source_records_and_multi_source_evidence_parse() -> None:
    data = _clean_workflow()
    sources = data["sources"]
    assert isinstance(sources, list)
    sources.append(
        {
            "source_id": "local-method",
            "source_type": "method_note",
            "locator": "local:method-note",
            "metadata": {"synthetic": "true"},
        }
    )
    _nested(data, "evidence", 0)["source_refs"] = [
        "local-index",
        "local-method",
    ]

    workflow = parse_workflow(data)

    assert len(workflow.sources) == 2
    assert workflow.evidence[0].source_refs == ("local-index", "local-method")


def test_missing_source_reference_is_rejected() -> None:
    data = _clean_workflow()
    _nested(data, "evidence", 0)["source_refs"] = ["missing-source"]

    with pytest.raises(
        WorkflowValidationError, match=r"unknown source_id\(s\): missing-source"
    ):
        parse_workflow(data)


def test_duplicate_source_id_is_rejected() -> None:
    data = _clean_workflow()
    sources = data["sources"]
    assert isinstance(sources, list)
    sources.append({"source_id": "local-index"})

    with pytest.raises(WorkflowValidationError, match="duplicate identifiers"):
        parse_workflow(data)


def test_generic_plan_artifact_parses() -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {
            "artifact_id": "plan-1",
            "artifact_type": "research_plan",
            "produced_by_event": "search",
            "source_refs": ["local-index"],
            "metadata": {"fixture_notice": "synthetic"},
        }
    ]

    workflow = parse_workflow(data)

    assert workflow.artifacts[0].artifact_type == "research_plan"
    assert workflow.artifacts[0].artifact_role is ArtifactRole.UNKNOWN
    assert workflow.artifacts[0].source_refs == ("local-index",)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("FINAL_OUTPUT", ArtifactRole.FINAL_OUTPUT),
        ("INTERMEDIATE", ArtifactRole.INTERMEDIATE),
        ("UNKNOWN", ArtifactRole.UNKNOWN),
        (None, ArtifactRole.UNKNOWN),
    ],
)
def test_artifact_role_parses_with_unknown_default(
    value: str | None, expected: ArtifactRole
) -> None:
    data = _clean_workflow()
    artifact = {
        "artifact_id": "artifact-1",
        "artifact_type": "report",
        "source_refs": ["local-index"],
    }
    if value is not None:
        artifact["artifact_role"] = value
    data["artifacts"] = [artifact]

    workflow = parse_workflow(data)

    assert workflow.artifacts[0].artifact_role is expected


def test_invalid_artifact_role_is_rejected() -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {
            "artifact_id": "artifact-1",
            "artifact_type": "report",
            "artifact_role": "REPORT",
        }
    ]

    with pytest.raises(
        WorkflowValidationError, match="FINAL_OUTPUT, INTERMEDIATE, UNKNOWN"
    ):
        parse_workflow(data)


def test_checkpoint_parent_artifact_lineage_parses() -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {
            "artifact_id": "plan-1",
            "artifact_type": "research_plan",
            "produced_by_event": "search",
        },
        {
            "artifact_id": "checkpoint-1",
            "artifact_type": "checkpoint",
            "produced_by_event": "send",
            "parent_artifact_refs": ["plan-1"],
        },
    ]

    workflow = parse_workflow(data)

    assert workflow.artifacts[1].parent_artifact_refs == ("plan-1",)


def test_missing_artifact_producing_event_is_rejected() -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {
            "artifact_id": "plan-1",
            "artifact_type": "research_plan",
            "produced_by_event": "missing-event",
        }
    ]

    with pytest.raises(
        WorkflowValidationError, match=r"unknown event_id 'missing-event'"
    ):
        parse_workflow(data)


@pytest.mark.parametrize(
    ("field", "reference", "expected"),
    [
        ("parent_artifact_refs", "missing-artifact", "unknown artifact_id"),
        ("source_refs", "missing-source", "unknown source_id"),
        ("evidence_refs", "missing-evidence", "unknown evidence_id"),
    ],
)
def test_dangling_artifact_references_are_rejected(
    field: str, reference: str, expected: str
) -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {
            "artifact_id": "artifact-1",
            "artifact_type": "synthetic",
            field: [reference],
        }
    ]

    with pytest.raises(WorkflowValidationError, match=expected):
        parse_workflow(data)


def test_artifact_cycle_is_rejected() -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {
            "artifact_id": "artifact-1",
            "artifact_type": "checkpoint",
            "parent_artifact_refs": ["artifact-2"],
        },
        {
            "artifact_id": "artifact-2",
            "artifact_type": "critique",
            "parent_artifact_refs": ["artifact-1"],
        },
    ]

    with pytest.raises(WorkflowValidationError, match="cycle"):
        parse_workflow(data)


def test_self_parent_artifact_is_rejected() -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {
            "artifact_id": "artifact-1",
            "artifact_type": "checkpoint",
            "parent_artifact_refs": ["artifact-1"],
        }
    ]

    with pytest.raises(WorkflowValidationError, match="cannot reference itself"):
        parse_workflow(data)


def test_duplicate_artifact_id_is_rejected() -> None:
    data = _clean_workflow()
    data["artifacts"] = [
        {"artifact_id": "duplicate", "artifact_type": "plan"},
        {"artifact_id": "duplicate", "artifact_type": "report"},
    ]

    with pytest.raises(WorkflowValidationError, match="duplicate identifiers"):
        parse_workflow(data)


def test_unlinked_source_does_not_create_provenance_pass() -> None:
    data = _clean_workflow()
    sources = data["sources"]
    assert isinstance(sources, list)
    sources.append({"source_id": "unlinked", "locator": "local:unlinked"})

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PARTIAL
    assert any("unlinked" in finding.message for finding in report.findings)


def test_artifact_without_lineage_does_not_create_provenance_pass() -> None:
    data = _clean_workflow()
    data["artifacts"] = [{"artifact_id": "orphan", "artifact_type": "checkpoint"}]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PARTIAL
    assert any("no recorded lineage" in finding.message for finding in report.findings)


def test_missing_evidence_producing_event_is_detected() -> None:
    data = _clean_workflow()
    _nested(data, "evidence", 0)["produced_by_event"] = "missing-event"

    findings = _findings(_verify(data), CheckName.PROVENANCE)

    assert any(finding.event_id == "missing-event" for finding in findings)


def test_external_style_fixture_maps_without_invention() -> None:
    fixture = Path("tests/fixtures/external_style_workflow.json")
    workflow = parse_workflow(json.loads(fixture.read_text(encoding="utf-8")))
    report = verify_workflow(workflow, generated_at="fixed")

    assert workflow.assurance_context.events == ()
    assert _check(report, CheckName.GOVERNANCE).status is CheckStatus.NOT_EVALUATED
    assert _check(report, CheckName.HUMAN_REVIEW).status is CheckStatus.NOT_EVALUATED
    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PASS
    assert _check(report, CheckName.AUDIT).status is CheckStatus.PASS


def test_external_graph_fixture_maps_without_invention() -> None:
    fixture = Path("tests/fixtures/external_graph_workflow.json")
    workflow = parse_workflow(json.loads(fixture.read_text(encoding="utf-8")))
    report = verify_workflow(workflow, generated_at="fixed")

    assert workflow.assurance_context.events == ()
    assert any(event.parent_event_id is not None for event in workflow.events)
    assert len(workflow.sources) == 2
    assert {artifact.artifact_type for artifact in workflow.artifacts} == {
        "research_plan",
        "checkpoint",
        "critique",
        "final_report",
    }
    assert workflow.artifacts[-1].artifact_role is ArtifactRole.FINAL_OUTPUT
    assert _check(report, CheckName.GOVERNANCE).status is CheckStatus.NOT_EVALUATED
    assert _check(report, CheckName.HUMAN_REVIEW).status is CheckStatus.NOT_EVALUATED
    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PASS
    assert _check(report, CheckName.AUDIT).status is CheckStatus.PASS


def test_deny_executed_is_high() -> None:
    data = _clean_workflow()
    _nested(data, "assurance_context", "events", 0)["governance_decision"] = "DENY"

    findings = _findings(_verify(data), CheckName.GOVERNANCE)

    assert any(finding.severity is Severity.HIGH for finding in findings)
    assert any("DENY" in finding.message for finding in findings)


@pytest.mark.parametrize(
    ("decision", "executed", "expected_status"),
    [
        ("DENY", True, CheckStatus.FAIL),
        ("DENY", False, CheckStatus.PASS),
        ("DENY", None, CheckStatus.PARTIAL),
        ("REQUIRE_APPROVAL", None, CheckStatus.PARTIAL),
    ],
)
def test_restrictive_governance_requires_known_execution_outcome(
    decision: str, executed: bool | None, expected_status: CheckStatus
) -> None:
    data = _clean_workflow()
    index = 0 if decision == "DENY" else 1
    _nested(data, "events", index)["executed"] = executed
    _nested(data, "assurance_context", "events", index)["governance_decision"] = (
        decision
    )

    report = _verify(data)

    assert _check(report, CheckName.GOVERNANCE).status is expected_status
    if executed is None:
        assert _findings(report, CheckName.GOVERNANCE) == ()
        assert report.summary.overall_status is OverallStatus.INCOMPLETE


def test_require_approval_without_record_is_high_when_executed() -> None:
    data = _clean_workflow()
    _nested(data, "assurance_context", "events", 1)["approval_record"] = None

    report = _verify(data)

    assert _findings(report, CheckName.GOVERNANCE)[0].severity is Severity.HIGH
    assert _findings(report, CheckName.HUMAN_REVIEW)[0].severity is Severity.HIGH


def test_rejected_approval_without_execution_passes_human_review() -> None:
    data = _clean_workflow()
    _nested(data, "events", 1)["executed"] = False
    _nested(data, "assurance_context", "events", 1, "approval_record")["decision"] = (
        "REJECTED"
    )

    report = _verify(data)

    assert _check(report, CheckName.HUMAN_REVIEW).status is CheckStatus.PASS


@pytest.mark.parametrize("requirement", ["REQUIRED", "NOT_REQUIRED", "UNKNOWN"])
@pytest.mark.parametrize("executed", [True, False, None])
def test_rejected_approval_is_checked_independent_of_requirement(
    requirement: str, executed: bool | None
) -> None:
    data = _clean_workflow()
    _nested(data, "events", 1)["executed"] = executed
    context = _nested(data, "assurance_context", "events", 1)
    context["approval_requirement"] = requirement
    _nested(data, "assurance_context", "events", 1, "approval_record")["decision"] = (
        "REJECTED"
    )

    report = _verify(data)
    findings = _findings(report, CheckName.HUMAN_REVIEW)
    status = _check(report, CheckName.HUMAN_REVIEW).status

    if executed is True:
        assert status is CheckStatus.FAIL
        assert any(finding.severity is Severity.HIGH for finding in findings)
    elif executed is False:
        assert findings == ()
        assert status is (
            CheckStatus.PARTIAL if requirement == "UNKNOWN" else CheckStatus.PASS
        )
    else:
        assert findings == ()
        assert status is not CheckStatus.PASS


def test_empty_provenance_surface_is_not_evaluated_or_complete() -> None:
    report = _verify(_event_only_workflow())

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.NOT_EVALUATED
    assert _findings(report, CheckName.PROVENANCE) == ()
    assert report.summary.overall_status is OverallStatus.INCOMPLETE


def test_valid_evidence_lineage_without_subjects_is_not_evaluated() -> None:
    data = _clean_workflow()
    data["claims"] = []

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.NOT_EVALUATED
    assert report.summary.overall_status is OverallStatus.INCOMPLETE


def test_final_output_produced_by_event_only_is_partial_provenance() -> None:
    data = _clean_workflow()
    data["claims"] = []
    data["artifacts"] = [
        {
            "artifact_id": "final-1",
            "artifact_type": "report",
            "artifact_role": "FINAL_OUTPUT",
            "produced_by_event": "send",
        }
    ]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PARTIAL
    assert any(
        finding.message.startswith("PROV_FINAL_OUTPUT_UNGROUNDED:")
        for finding in _findings(report, CheckName.PROVENANCE)
    )


def test_final_output_with_direct_source_is_grounded() -> None:
    data = _clean_workflow()
    data["claims"] = []
    data["artifacts"] = [
        {
            "artifact_id": "final-1",
            "artifact_type": "report",
            "artifact_role": "FINAL_OUTPUT",
            "source_refs": ["local-index"],
        }
    ]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PASS
    assert report.summary.overall_status is OverallStatus.COMPLETE


def test_final_output_with_evidence_to_source_is_grounded() -> None:
    data = _clean_workflow()
    data["claims"] = []
    data["artifacts"] = [
        {
            "artifact_id": "final-1",
            "artifact_type": "report",
            "artifact_role": "FINAL_OUTPUT",
            "evidence_refs": ["summary"],
        }
    ]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PASS


def test_final_output_with_parent_artifact_to_evidence_to_source_is_grounded() -> None:
    data = _clean_workflow()
    data["claims"] = []
    data["artifacts"] = [
        {
            "artifact_id": "intermediate-1",
            "artifact_type": "checkpoint",
            "artifact_role": "INTERMEDIATE",
            "evidence_refs": ["summary"],
        },
        {
            "artifact_id": "final-1",
            "artifact_type": "report",
            "artifact_role": "FINAL_OUTPUT",
            "parent_artifact_refs": ["intermediate-1"],
        },
    ]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PASS


def test_final_output_with_sourceless_evidence_is_partial() -> None:
    data = _clean_workflow()
    data["claims"] = []
    evidence = data["evidence"]
    assert isinstance(evidence, list)
    evidence.append({"evidence_id": "sourceless"})
    data["artifacts"] = [
        {
            "artifact_id": "final-1",
            "artifact_type": "report",
            "artifact_role": "FINAL_OUTPUT",
            "evidence_refs": ["sourceless"],
        }
    ]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PARTIAL
    assert any(
        finding.message.startswith("PROV_FINAL_OUTPUT_UNGROUNDED:")
        for finding in _findings(report, CheckName.PROVENANCE)
    )


def test_claim_with_sourceless_evidence_is_not_provenance_pass() -> None:
    data = _clean_workflow()
    evidence = data["evidence"]
    assert isinstance(evidence, list)
    evidence.append({"evidence_id": "sourceless"})
    _nested(data, "claims", 0)["evidence_refs"] = ["sourceless"]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PARTIAL
    assert any(
        finding.message.startswith("PROV_CLAIM_UNGROUNDED:")
        for finding in _findings(report, CheckName.PROVENANCE)
    )


def test_claim_with_parent_evidence_path_to_source_is_grounded() -> None:
    data = _clean_workflow()
    _nested(data, "claims", 0)["evidence_refs"] = ["summary"]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PASS


@pytest.mark.parametrize("role", ["INTERMEDIATE", "UNKNOWN"])
def test_non_final_artifacts_without_claims_are_not_evaluated(role: str) -> None:
    data = _clean_workflow()
    data["claims"] = []
    data["artifacts"] = [
        {
            "artifact_id": "not-final",
            "artifact_type": "checkpoint",
            "artifact_role": role,
            "produced_by_event": "search",
        }
    ]

    report = _verify(data)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.NOT_EVALUATED


def test_produced_by_event_never_counts_as_final_output_grounding() -> None:
    data = _clean_workflow()
    data["claims"] = []
    data["artifacts"] = [
        {
            "artifact_id": "final-1",
            "artifact_type": "report",
            "artifact_role": "FINAL_OUTPUT",
            "produced_by_event": "search",
        }
    ]

    report = _verify(data)
    findings = _findings(report, CheckName.PROVENANCE)

    assert _check(report, CheckName.PROVENANCE).status is CheckStatus.PARTIAL
    assert len(findings) == 1
    assert findings[0].message.startswith("PROV_FINAL_OUTPUT_UNGROUNDED:")


def test_executed_event_without_observation_or_error_is_partial_audit() -> None:
    data = _clean_workflow()
    _nested(data, "events", 0)["observation"] = None

    findings = _findings(_verify(data), CheckName.AUDIT)

    assert len(findings) == 1
    assert findings[0].event_id == "search"


def test_repeated_run_is_semantically_deterministic() -> None:
    workflow = parse_workflow(_clean_workflow())
    first = asdict(verify_workflow(workflow, generated_at="first"))
    second = asdict(verify_workflow(workflow, generated_at="second"))
    first.pop("generated_at")
    second.pop("generated_at")

    assert first == second


@pytest.mark.parametrize(
    ("path", "field", "expected_path"),
    [
        ((), "unexpected_workflow", "workflow"),
        (("events", 0), "approval_required", "workflow.events[0]"),
        (("evidence", 0), "source", "workflow.evidence[0]"),
        (("evidence", 0), "source_ref", "workflow.evidence[0]"),
        (("claims", 0), "unexpected_claim", "workflow.claims[0]"),
        (
            ("assurance_context", "events", 0),
            "control_flow_decision",
            "workflow.assurance_context.events[0]",
        ),
    ],
)
def test_unknown_schema_field_is_rejected(
    path: tuple[str | int, ...], field: str, expected_path: str
) -> None:
    data = _clean_workflow()
    _nested(data, *path)[field] = True

    with pytest.raises(
        WorkflowValidationError, match=rf"{re.escape(expected_path)}.*{field}"
    ):
        parse_workflow(data)


def test_empty_events_are_rejected() -> None:
    data = _clean_workflow()
    data["events"] = []

    with pytest.raises(
        WorkflowValidationError, match=r"workflow\.events.*at least one event"
    ):
        parse_workflow(data)


@pytest.mark.parametrize("field", ["sources", "artifacts"])
def test_structural_collections_are_required(field: str) -> None:
    data = _clean_workflow()
    data.pop(field)

    with pytest.raises(
        WorkflowValidationError, match=rf"missing required field '{field}'"
    ):
        parse_workflow(data)


@pytest.mark.parametrize(
    "malformed, expected",
    [
        ({"workflow_id": "broken"}, "missing required field 'events'"),
        (
            {"workflow_id": "broken", "events": {}, "evidence": [], "claims": []},
            "array",
        ),
    ],
)
def test_malformed_workflow_has_clear_error(
    malformed: dict[str, object], expected: str
) -> None:
    with pytest.raises(WorkflowValidationError, match=expected):
        parse_workflow(malformed)


def test_report_payload_is_json_serializable() -> None:
    report = _verify(_clean_workflow())

    encoded = json.dumps(report.to_dict(), sort_keys=True)

    assert '"overall_status": "COMPLETE"' in encoded
