import json
import re
from dataclasses import asdict

import pytest

from agent_boundary_lab.assurance.models import (
    CheckName,
    CheckStatus,
    OverallStatus,
    Severity,
)
from agent_boundary_lab.assurance.schema import (
    WorkflowValidationError,
    parse_workflow,
)
from agent_boundary_lab.assurance.verifier import verify_workflow


def _clean_workflow() -> dict[str, object]:
    return {
        "workflow_id": "clean_review",
        "title": "Clean literature review",
        "steps": [
            {
                "step_id": "search",
                "action": "search papers",
                "tool": "local_index",
                "governance_decision": "ALLOW",
                "dispatched": True,
                "evidence_refs": ["search_results"],
                "approval_required": False,
                "approval_record": None,
                "audit_record": {
                    "action": "search papers",
                    "decision": "ALLOW",
                    "outcome": "results returned",
                },
            },
            {
                "step_id": "send",
                "action": "send summary",
                "tool": "external_send",
                "governance_decision": "REQUIRE_APPROVAL",
                "dispatched": True,
                "evidence_refs": ["summary"],
                "approval_required": True,
                "approval_record": {
                    "approval_id": "approval-1",
                    "decision": "APPROVED",
                    "evidence_refs": ["summary"],
                },
                "audit_record": {
                    "action": "send summary",
                    "decision": "REQUIRE_APPROVAL",
                    "outcome": "sent after approval",
                },
            },
        ],
        "evidence": [
            {
                "evidence_id": "search_results",
                "source": "local:index-query-1",
                "produced_by_step": "search",
            },
            {
                "evidence_id": "summary",
                "source": "search_results",
                "produced_by_step": "search",
            },
        ],
        "claims": [
            {
                "claim_id": "claim-1",
                "text": "The search returned a bounded result.",
                "evidence_refs": ["search_results"],
            }
        ],
    }


def _verify(data: dict[str, object]):
    return verify_workflow(parse_workflow(data), generated_at="2026-01-01T00:00:00Z")


def _findings(report, check: CheckName):
    return tuple(finding for finding in report.findings if finding.check is check)


def _mapping_value(value: object, key: str) -> object:
    assert isinstance(value, dict)
    return value[key]


def _list_value(value: object, index: int) -> object:
    assert isinstance(value, list)
    return value[index]


def _nested_object(
    data: dict[str, object], path: tuple[str | int, ...]
) -> dict[str, object]:
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


def test_missing_claim_evidence_produces_finding() -> None:
    data = _clean_workflow()
    data["claims"][0]["evidence_refs"] = []  # type: ignore[index]

    findings = _findings(_verify(data), CheckName.PROVENANCE)

    assert len(findings) == 1
    assert findings[0].claim_id == "claim-1"
    assert "does not reference" in findings[0].message


def test_dangling_evidence_reference_produces_finding() -> None:
    data = _clean_workflow()
    data["claims"][0]["evidence_refs"] = ["missing"]  # type: ignore[index]

    findings = _findings(_verify(data), CheckName.PROVENANCE)

    assert findings[0].evidence_refs == ("missing",)
    assert "does not exist" in findings[0].message


def test_deny_dispatched_is_high() -> None:
    data = _clean_workflow()
    data["steps"][0]["governance_decision"] = "DENY"  # type: ignore[index]

    findings = _findings(_verify(data), CheckName.GOVERNANCE)

    assert any(finding.severity is Severity.HIGH for finding in findings)
    assert any("DENY" in finding.message for finding in findings)


def test_require_approval_without_approval_dispatched_is_high() -> None:
    data = _clean_workflow()
    data["steps"][1]["approval_record"] = None  # type: ignore[index]

    report = _verify(data)

    governance = _findings(report, CheckName.GOVERNANCE)
    human_review = _findings(report, CheckName.HUMAN_REVIEW)
    assert governance[0].severity is Severity.HIGH
    assert human_review[0].severity is Severity.HIGH


def test_rejected_approval_without_dispatch_satisfies_human_review() -> None:
    data = _clean_workflow()
    send = _nested_object(data, ("steps", 1))
    approval = _nested_object(data, ("steps", 1, "approval_record"))
    send["dispatched"] = False
    approval["decision"] = "REJECTED"

    report = _verify(data)
    human_review = next(
        result for result in report.checks if result.check is CheckName.HUMAN_REVIEW
    )

    assert human_review.status is CheckStatus.PASS
    assert _findings(report, CheckName.HUMAN_REVIEW) == ()


def test_rejected_approval_with_dispatch_is_high() -> None:
    data = _clean_workflow()
    approval = _nested_object(data, ("steps", 1, "approval_record"))
    approval["decision"] = "REJECTED"

    findings = _findings(_verify(data), CheckName.HUMAN_REVIEW)

    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH
    assert "REJECTED" in findings[0].message


def test_missing_audit_record_produces_finding() -> None:
    data = _clean_workflow()
    data["steps"][0]["audit_record"] = None  # type: ignore[index]

    findings = _findings(_verify(data), CheckName.AUDIT)

    assert len(findings) == 1
    assert findings[0].step_id == "search"


def test_audit_action_mismatch_produces_finding() -> None:
    data = _clean_workflow()
    audit = _nested_object(data, ("steps", 0, "audit_record"))
    audit["action"] = "different action"

    findings = _findings(_verify(data), CheckName.AUDIT)

    assert len(findings) == 1
    assert "action does not match" in findings[0].message


def test_audit_decision_mismatch_produces_finding() -> None:
    data = _clean_workflow()
    audit = _nested_object(data, ("steps", 0, "audit_record"))
    audit["decision"] = "DENY"

    findings = _findings(_verify(data), CheckName.AUDIT)

    assert len(findings) == 1
    assert "decision does not match" in findings[0].message


def test_dangling_step_evidence_reference_produces_finding() -> None:
    data = _clean_workflow()
    step = _nested_object(data, ("steps", 0))
    step["evidence_refs"] = ["missing"]

    findings = _findings(_verify(data), CheckName.PROVENANCE)

    assert len(findings) == 1
    assert findings[0].step_id == "search"
    assert findings[0].evidence_refs == ("missing",)


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
        (("steps", 0), "approval_requred", "workflow.steps[0]"),
        (("evidence", 0), "unexpected_evidence", "workflow.evidence[0]"),
        (("claims", 0), "unexpected_claim", "workflow.claims[0]"),
        (
            ("steps", 1, "approval_record"),
            "unexpected_approval",
            "workflow.steps[1].approval_record",
        ),
        (
            ("steps", 0, "audit_record"),
            "unexpected_audit",
            "workflow.steps[0].audit_record",
        ),
    ],
)
def test_unknown_schema_field_is_rejected(
    path: tuple[str | int, ...], field: str, expected_path: str
) -> None:
    data = _clean_workflow()
    _nested_object(data, path)[field] = True

    with pytest.raises(
        WorkflowValidationError,
        match=rf"{re.escape(expected_path)}.*{field}",
    ):
        parse_workflow(data)


def test_empty_steps_are_rejected() -> None:
    data = _clean_workflow()
    data["steps"] = []

    with pytest.raises(
        WorkflowValidationError,
        match=r"workflow\.steps.*at least one step",
    ):
        parse_workflow(data)


@pytest.mark.parametrize(
    "malformed, expected",
    [
        ({"workflow_id": "broken"}, "missing required field 'title'"),
        ({"workflow_id": "broken", "title": "Broken", "steps": {}}, "array"),
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
