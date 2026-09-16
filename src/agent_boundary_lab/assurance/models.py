"""Data models for the v0.2 workflow-assurance development preview."""

from dataclasses import asdict, dataclass, field
from enum import Enum

from agent_boundary_lab.models import BoundaryDecision


class CheckName(str, Enum):
    """The deterministic checks included in the v0.2 preview."""

    GOVERNANCE = "GOVERNANCE"
    PROVENANCE = "PROVENANCE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    AUDIT = "AUDIT"


class Severity(str, Enum):
    """Finding severity without a numerical trust score."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CheckStatus(str, Enum):
    """Outcome of one assurance check."""

    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class OverallStatus(str, Enum):
    """Overall workflow-assurance completeness."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class ApprovalDecision(str, Enum):
    """Decision represented by a structured approval record."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequirement(str, Enum):
    """Whether an assurance policy expects human approval for an event."""

    REQUIRED = "REQUIRED"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ApprovalRecord:
    """Structured approval evidence; it does not authenticate a person."""

    approval_id: str
    decision: ApprovalDecision
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedEvent:
    """Facts observed in a workflow trace, without assurance judgments."""

    event_id: str
    event_type: str | None = None
    action: str | None = None
    tool: str | None = None
    control_flow_decision: str | None = None
    executed: bool | None = None
    evidence_refs: tuple[str, ...] = ()
    observation: str | None = None
    timestamp: str | None = None
    error: str | None = None
    latency_ms: float | None = None
    sequence: int | None = None
    question_ref: str | None = None
    query: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    """Research evidence with separate source and parent-evidence lineage."""

    evidence_id: str
    produced_by_event: str | None = None
    source_ref: str | None = None
    parent_evidence_refs: tuple[str, ...] = ()
    supporting_text: str | None = None
    question_ref: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Claim:
    """A research claim and the evidence identifiers it cites."""

    claim_id: str
    text: str
    evidence_refs: tuple[str, ...]
    question_ref: str | None = None


@dataclass(frozen=True)
class EventAssuranceContext:
    """Policy and review judgments associated with one observed event."""

    event_id: str
    governance_decision: BoundaryDecision | None = None
    governance_evidence_refs: tuple[str, ...] = ()
    policy_ref: str | None = None
    approval_requirement: ApprovalRequirement = ApprovalRequirement.UNKNOWN
    approval_record: ApprovalRecord | None = None


@dataclass(frozen=True)
class AssuranceContext:
    """Optional assurance judgments, kept separate from observed facts."""

    events: tuple[EventAssuranceContext, ...] = ()


@dataclass(frozen=True)
class Workflow:
    """The minimal workflow input accepted by ``abl verify``."""

    workflow_id: str
    events: tuple[ObservedEvent, ...]
    evidence: tuple[Evidence, ...]
    claims: tuple[Claim, ...]
    title: str | None = None
    research_goal: str | None = None
    assurance_context: AssuranceContext = AssuranceContext()


@dataclass(frozen=True)
class Finding:
    """A deterministic, actionable assurance finding."""

    finding_id: str
    check: CheckName
    severity: Severity
    message: str
    evidence_refs: tuple[str, ...]
    remediation_hint: str
    event_id: str | None = None
    claim_id: str | None = None


@dataclass(frozen=True)
class CheckResult:
    """Status and stable finding identifiers for one check."""

    check: CheckName
    status: CheckStatus
    finding_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReportSummary:
    """Compact overall result without a numerical trust score."""

    overall_status: OverallStatus
    total_findings: int
    high_findings: int
    medium_findings: int
    low_findings: int


@dataclass(frozen=True)
class AssuranceReport:
    """Machine-readable result of all current workflow checks."""

    workflow_id: str
    generated_at: str
    checks: tuple[CheckResult, ...]
    findings: tuple[Finding, ...]
    summary: ReportSummary

    def to_dict(self) -> dict[str, object]:
        """Return an enum-safe mapping suitable for JSON serialization."""
        return asdict(self)
