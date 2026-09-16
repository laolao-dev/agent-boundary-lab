"""Strict JSON parsing for the minimal workflow-assurance schema."""

import json
from pathlib import Path
from typing import Never

from agent_boundary_lab.assurance.models import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequirement,
    AssuranceContext,
    Claim,
    EventAssuranceContext,
    Evidence,
    ObservedEvent,
    Workflow,
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


def _optional_string(data: dict[str, object], key: str, path: str) -> str | None:
    return _string(data.get(key), f"{path}.{key}", allow_null=True)


def _optional_boolean(data: dict[str, object], key: str, path: str) -> bool | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        _fail(f"{path}.{key}", "expected a boolean or null")
    return value


def _optional_number(data: dict[str, object], key: str, path: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        _fail(f"{path}.{key}", "expected a non-negative number or null")
    return float(value)


def _optional_integer(data: dict[str, object], key: str, path: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{path}.{key}", "expected a non-negative integer or null")
    return value


def _string_tuple(value: object, path: str) -> tuple[str, ...]:
    items = _list(value, path)
    parsed: list[str] = []
    for index, item in enumerate(items):
        parsed_value = _string(item, f"{path}[{index}]")
        assert parsed_value is not None
        parsed.append(parsed_value)
    return tuple(parsed)


def _metadata(value: object, path: str) -> dict[str, str]:
    data = _mapping(value, path)
    parsed: dict[str, str] = {}
    for key in sorted(data):
        item = _string(data[key], f"{path}.{key}")
        assert item is not None
        parsed[key] = item
    return parsed


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


def _parse_boundary_decision(value: object, path: str) -> BoundaryDecision | None:
    if value is None:
        return None
    parsed = _string(value, path)
    assert parsed is not None
    try:
        return BoundaryDecision(parsed)
    except ValueError:
        allowed = ", ".join(decision.value for decision in BoundaryDecision)
        _fail(path, f"expected one of: {allowed}, or null")


def _parse_approval_requirement(value: object, path: str) -> ApprovalRequirement:
    if value is None:
        return ApprovalRequirement.UNKNOWN
    parsed = _string(value, path)
    assert parsed is not None
    try:
        return ApprovalRequirement(parsed)
    except ValueError:
        allowed = ", ".join(item.value for item in ApprovalRequirement)
        _fail(path, f"expected one of: {allowed}, or null")


def _parse_approval(value: object, path: str) -> ApprovalRecord | None:
    if value is None:
        return None
    data = _mapping(value, path)
    _reject_unknown(data, frozenset({"approval_id", "decision", "evidence_refs"}), path)
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


def _parse_event(value: object, path: str) -> ObservedEvent:
    data = _mapping(value, path)
    _reject_unknown(
        data,
        frozenset(
            {
                "event_id",
                "event_type",
                "action",
                "tool",
                "control_flow_decision",
                "executed",
                "evidence_refs",
                "observation",
                "timestamp",
                "error",
                "latency_ms",
                "sequence",
                "question_ref",
                "query",
                "metadata",
            }
        ),
        path,
    )
    event_id = _string(_required(data, "event_id", path), f"{path}.event_id")
    assert event_id is not None
    return ObservedEvent(
        event_id=event_id,
        event_type=_optional_string(data, "event_type", path),
        action=_optional_string(data, "action", path),
        tool=_optional_string(data, "tool", path),
        control_flow_decision=_optional_string(data, "control_flow_decision", path),
        executed=_optional_boolean(data, "executed", path),
        evidence_refs=_string_tuple(
            data.get("evidence_refs", []), f"{path}.evidence_refs"
        ),
        observation=_optional_string(data, "observation", path),
        timestamp=_optional_string(data, "timestamp", path),
        error=_optional_string(data, "error", path),
        latency_ms=_optional_number(data, "latency_ms", path),
        sequence=_optional_integer(data, "sequence", path),
        question_ref=_optional_string(data, "question_ref", path),
        query=_optional_string(data, "query", path),
        metadata=_metadata(data.get("metadata", {}), f"{path}.metadata"),
    )


def _parse_evidence(value: object, path: str) -> Evidence:
    data = _mapping(value, path)
    _reject_unknown(
        data,
        frozenset(
            {
                "evidence_id",
                "produced_by_event",
                "source_ref",
                "parent_evidence_refs",
                "supporting_text",
                "question_ref",
                "metadata",
            }
        ),
        path,
    )
    evidence_id = _string(_required(data, "evidence_id", path), f"{path}.evidence_id")
    assert evidence_id is not None
    return Evidence(
        evidence_id=evidence_id,
        produced_by_event=_optional_string(data, "produced_by_event", path),
        source_ref=_optional_string(data, "source_ref", path),
        parent_evidence_refs=_string_tuple(
            data.get("parent_evidence_refs", []), f"{path}.parent_evidence_refs"
        ),
        supporting_text=_optional_string(data, "supporting_text", path),
        question_ref=_optional_string(data, "question_ref", path),
        metadata=_metadata(data.get("metadata", {}), f"{path}.metadata"),
    )


def _parse_claim(value: object, path: str) -> Claim:
    data = _mapping(value, path)
    _reject_unknown(
        data, frozenset({"claim_id", "text", "evidence_refs", "question_ref"}), path
    )
    claim_id = _string(_required(data, "claim_id", path), f"{path}.claim_id")
    text = _string(_required(data, "text", path), f"{path}.text")
    assert claim_id is not None and text is not None
    return Claim(
        claim_id=claim_id,
        text=text,
        evidence_refs=_string_tuple(
            _required(data, "evidence_refs", path), f"{path}.evidence_refs"
        ),
        question_ref=_optional_string(data, "question_ref", path),
    )


def _parse_event_assurance(value: object, path: str) -> EventAssuranceContext:
    data = _mapping(value, path)
    _reject_unknown(
        data,
        frozenset(
            {
                "event_id",
                "governance_decision",
                "governance_evidence_refs",
                "policy_ref",
                "approval_requirement",
                "approval_record",
            }
        ),
        path,
    )
    event_id = _string(_required(data, "event_id", path), f"{path}.event_id")
    assert event_id is not None
    return EventAssuranceContext(
        event_id=event_id,
        governance_decision=_parse_boundary_decision(
            data.get("governance_decision"), f"{path}.governance_decision"
        ),
        governance_evidence_refs=_string_tuple(
            data.get("governance_evidence_refs", []),
            f"{path}.governance_evidence_refs",
        ),
        policy_ref=_optional_string(data, "policy_ref", path),
        approval_requirement=_parse_approval_requirement(
            data.get("approval_requirement"), f"{path}.approval_requirement"
        ),
        approval_record=_parse_approval(
            data.get("approval_record"), f"{path}.approval_record"
        ),
    )


def _parse_assurance_context(value: object, path: str) -> AssuranceContext:
    if value is None:
        return AssuranceContext()
    data = _mapping(value, path)
    _reject_unknown(data, frozenset({"events"}), path)
    events = tuple(
        _parse_event_assurance(item, f"{path}.events[{index}]")
        for index, item in enumerate(_list(data.get("events", []), f"{path}.events"))
    )
    _require_unique(tuple(item.event_id for item in events), f"{path}.events")
    return AssuranceContext(events=events)


def _require_unique(values: tuple[str, ...], path: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        _fail(path, f"duplicate identifiers: {', '.join(duplicates)}")


def parse_workflow(value: object) -> Workflow:
    """Parse an in-memory JSON value into a validated workflow model."""
    data = _mapping(value, "workflow")
    _reject_unknown(
        data,
        frozenset(
            {
                "workflow_id",
                "title",
                "research_goal",
                "events",
                "evidence",
                "claims",
                "assurance_context",
            }
        ),
        "workflow",
    )
    workflow_id = _string(
        _required(data, "workflow_id", "workflow"), "workflow.workflow_id"
    )
    assert workflow_id is not None
    events = tuple(
        _parse_event(item, f"workflow.events[{index}]")
        for index, item in enumerate(
            _list(_required(data, "events", "workflow"), "workflow.events")
        )
    )
    if not events:
        _fail("workflow.events", "expected at least one event")
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
    assurance_context = _parse_assurance_context(
        data.get("assurance_context"), "workflow.assurance_context"
    )
    _require_unique(tuple(event.event_id for event in events), "workflow.events")
    _require_unique(tuple(item.evidence_id for item in evidence), "workflow.evidence")
    _require_unique(tuple(claim.claim_id for claim in claims), "workflow.claims")
    return Workflow(
        workflow_id=workflow_id,
        title=_optional_string(data, "title", "workflow"),
        research_goal=_optional_string(data, "research_goal", "workflow"),
        events=events,
        evidence=evidence,
        claims=claims,
        assurance_context=assurance_context,
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
