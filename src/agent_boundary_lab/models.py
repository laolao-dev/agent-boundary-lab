"""Domain models for deterministic boundary decisions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class BoundaryDecision(str, Enum):
    """A policy decision for an agent action."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ActionType(str, Enum):
    """Action types supported by the v0.1 harness."""

    READ_FILE = "READ_FILE"
    READ_SECRET = "READ_SECRET"
    NETWORK_SEND = "NETWORK_SEND"


@dataclass(frozen=True)
class AgentAction:
    """An action submitted to the boundary engine."""

    action_type: ActionType
    target: str
    payload: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BoundaryRule:
    """An exact action-and-target policy rule."""

    name: str
    action_type: ActionType
    target: str
    decision: BoundaryDecision
    reason: str | None = None


@dataclass(frozen=True)
class ExecutionRecord:
    """The auditable result of evaluating one action."""

    scenario_name: str
    action: AgentAction
    decision: BoundaryDecision
    matched_rule: BoundaryRule | None
    reason: str


@dataclass(frozen=True)
class EvaluationResult:
    """Comparison between an expected decision and an execution record."""

    expected_decision: BoundaryDecision
    actual_decision: BoundaryDecision
    passed: bool
    execution_record: ExecutionRecord
