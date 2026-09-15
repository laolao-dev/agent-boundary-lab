"""Strict JSON parsing for the minimal workflow-assurance schema."""

import json
from pathlib import Path
from typing import Never

from agent_boundary_lab.assurance.models import (
    ApprovalDecision,
    ApprovalRecord,
    AuditRecord,
    Claim,
    Evidence,
    Workflow,
    WorkflowStep,
)
from agent_boundary_lab.models import BoundaryDecision


class WorkflowValidationError(ValueError):
    """A clear structural validation error for workflow JSON."""


def _fail(path: str, message: str) -> Never:
    raise WorkflowValidationError(f"{path}: {message}")


def _mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(path, "expected an object")
    return value


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        _fail(path, "expected an array")
    return value


def _string(value: object, path: str, *, allow_null: bool = False) -> str | None:
    if value is None and allow_null:
        return None
    if not isinstance(value, str) or not value.strip():
        _fail(path, "expected a non-empty string")
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "expected a boolean")
    return value


def _string_tuple(value: object, path: str) -> tuple[str, ...]:
    items = _list(value, path)
    parsed: list[str] = []
    for index, item in enumerate(items):
        parsed_value = _string(item, f"{path}[{index}]")
        assert parsed_value is not None
        parsed.append(parsed_value)
    return tuple(parsed)


def _required(data: dict[str, object], key: str, path: str) -> object:
    if key not in data:
        _fail(path, f"missing required field '{key}'")
    return data[key]


def _reject_unknown(
    data: dict[str, object], allowed_fields: frozenset[str], path: str
) -> None:
    unknown_fields = sorted(set(data) - allowed_fields)
    if unknown_fields:
        fields = ", ".join(repr(field) for field in unknown_fields)
        _fail(path, f"unknown field(s): {fields}")


def _optional_string(data: dict[str, object], key: str, path: str) -> str | None:
    return _string(data.get(key), f"{path}.{key}", allow_null=True)


def _parse_decision(value: object, path: str) -> BoundaryDecision | None:
    if value is None:
        return None
    parsed = _string(value, path)
    assert parsed is not None
    try:
        return BoundaryDecision(parsed)
    except ValueError:
        allowed = ", ".join(decision.value for decision in BoundaryDecision)
        _fail(path, f"expected one of: {allowed}, or null")


def _parse_approval(value: object, path: str) -> ApprovalRecord | None:
    if value is None:
        return None
    data = _mapping(value, path)
    _reject_unknown(
        data,
        frozenset({"approval_id", "decision", "evidence_refs"}),
        path,
    )
    approval_id = _string(_required(data, "approval_id", path), f"{path}.approval_id")
    decision_value = _string(_required(data, "decision", path), f"{path}.decision")
    assert approval_id is not None and decision_value is not None
    try:
        decision = ApprovalDecision(decision_value)
    except ValueError:
        allowed = ", ".join(item.value for item in ApprovalDecision)
        _fail(f"{path}.decision", f"expected one of: {allowed}")
    return ApprovalRecord(
        approval_id=approval_id,
        decision=decision,
        evidence_refs=_string_tuple(
            data.get("evidence_refs", []), f"{path}.evidence_refs"
        ),
    )


def _parse_audit(value: object, path: str) -> AuditRecord | None:
    if value is None:
        return None
    data = _mapping(value, path)
    _reject_unknown(data, frozenset({"action", "decision", "outcome"}), path)
    return AuditRecord(
        action=_optional_string(data, "action", path),
        decision=_optional_string(data, "decision", path),
        outcome=_optional_string(data, "outcome", path),
    )


def _parse_step(value: object, path: str) -> WorkflowStep:
    data = _mapping(value, path)
    _reject_unknown(
        data,
        frozenset(
            {
                "step_id",
                "action",
                "tool",
                "governance_decision",
                "dispatched",
                "evidence_refs",
                "approval_required",
                "approval_record",
                "audit_record",
            }
        ),
        path,
    )
    step_id = _string(_required(data, "step_id", path), f"{path}.step_id")
    action = _string(_required(data, "action", path), f"{path}.action")
    assert step_id is not None and action is not None
    return WorkflowStep(
        step_id=step_id,
        action=action,
        tool=_optional_string(data, "tool", path),
        governance_decision=_parse_decision(
            data.get("governance_decision"), f"{path}.governance_decision"
        ),
        dispatched=_boolean(_required(data, "dispatched", path), f"{path}.dispatched"),
        evidence_refs=_string_tuple(
            data.get("evidence_refs", []), f"{path}.evidence_refs"
        ),
        approval_required=_boolean(
            data.get("approval_required", False), f"{path}.approval_required"
        ),
        approval_record=_parse_approval(
            data.get("approval_record"), f"{path}.approval_record"
        ),
        audit_record=_parse_audit(data.get("audit_record"), f"{path}.audit_record"),
    )


def _parse_evidence(value: object, path: str) -> Evidence:
    data = _mapping(value, path)
    _reject_unknown(
        data, frozenset({"evidence_id", "source", "produced_by_step"}), path
    )
    evidence_id = _string(_required(data, "evidence_id", path), f"{path}.evidence_id")
    assert evidence_id is not None
    return Evidence(
        evidence_id=evidence_id,
        source=_optional_string(data, "source", path),
        produced_by_step=_optional_string(data, "produced_by_step", path),
    )


def _parse_claim(value: object, path: str) -> Claim:
    data = _mapping(value, path)
    _reject_unknown(data, frozenset({"claim_id", "text", "evidence_refs"}), path)
    claim_id = _string(_required(data, "claim_id", path), f"{path}.claim_id")
    text = _string(_required(data, "text", path), f"{path}.text")
    assert claim_id is not None and text is not None
    return Claim(
        claim_id=claim_id,
        text=text,
        evidence_refs=_string_tuple(
            _required(data, "evidence_refs", path), f"{path}.evidence_refs"
        ),
    )


def _require_unique(values: tuple[str, ...], path: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        _fail(path, f"duplicate identifiers: {', '.join(duplicates)}")


def parse_workflow(value: object) -> Workflow:
    """Parse an in-memory JSON value into a validated workflow model."""
    data = _mapping(value, "workflow")
    _reject_unknown(
        data,
        frozenset({"workflow_id", "title", "steps", "evidence", "claims"}),
        "workflow",
    )
    workflow_id = _string(
        _required(data, "workflow_id", "workflow"), "workflow.workflow_id"
    )
    title = _string(_required(data, "title", "workflow"), "workflow.title")
    assert workflow_id is not None and title is not None
    steps = tuple(
        _parse_step(item, f"workflow.steps[{index}]")
        for index, item in enumerate(
            _list(_required(data, "steps", "workflow"), "workflow.steps")
        )
    )
    if not steps:
        _fail("workflow.steps", "expected at least one step")
    evidence = tuple(
        _parse_evidence(item, f"workflow.evidence[{index}]")
        for index, item in enumerate(
            _list(_required(data, "evidence", "workflow"), "workflow.evidence")
        )
    )
    claims = tuple(
        _parse_claim(item, f"workflow.claims[{index}]")
        for index, item in enumerate(
            _list(_required(data, "claims", "workflow"), "workflow.claims")
        )
    )
    _require_unique(tuple(step.step_id for step in steps), "workflow.steps")
    _require_unique(tuple(item.evidence_id for item in evidence), "workflow.evidence")
    _require_unique(tuple(claim.claim_id for claim in claims), "workflow.claims")
    return Workflow(
        workflow_id=workflow_id,
        title=title,
        steps=steps,
        evidence=evidence,
        claims=claims,
    )


def load_workflow(path: Path) -> Workflow:
    """Load workflow JSON and raise a clear validation error on bad input."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise WorkflowValidationError(f"{path}: {error}") from error
    except json.JSONDecodeError as error:
        raise WorkflowValidationError(
            f"{path}: invalid JSON at line {error.lineno}, column {error.colno}"
        ) from error
    return parse_workflow(value)
