"""Data models for the v0.2 workflow-assurance vertical slice."""

from dataclasses import asdict, dataclass
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


class OverallStatus(str, Enum):
    """Overall workflow-assurance completeness."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class ApprovalDecision(str, Enum):
    """Decision represented by a structured approval record."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ApprovalRecord:
    """Structured approval evidence; it does not authenticate a person."""

    approval_id: str
    decision: ApprovalDecision
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditRecord:
    """Minimum audit fields required for an important workflow step."""

    action: str | None
    decision: str | None
    outcome: str | None


@dataclass(frozen=True)
class WorkflowStep:
    """One action and its governance, dispatch, approval, and audit evidence."""

    step_id: str
    action: str
    tool: str | None
    governance_decision: BoundaryDecision | None
    dispatched: bool
    evidence_refs: tuple[str, ...]
    approval_required: bool
    approval_record: ApprovalRecord | None
    audit_record: AuditRecord | None


@dataclass(frozen=True)
class Evidence:
    """Identifier-level evidence lineage for a workflow output."""

    evidence_id: str
    source: str | None
    produced_by_step: str | None


@dataclass(frozen=True)
class Claim:
    """A research claim and the evidence identifiers it cites."""

    claim_id: str
    text: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class Workflow:
    """The minimal workflow input accepted by ``abl verify``."""

    workflow_id: str
    title: str
    steps: tuple[WorkflowStep, ...]
    evidence: tuple[Evidence, ...]
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class Finding:
    """A deterministic, actionable assurance finding."""

    finding_id: str
    check: CheckName
    severity: Severity
    message: str
    evidence_refs: tuple[str, ...]
    remediation_hint: str
    step_id: str | None = None
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
