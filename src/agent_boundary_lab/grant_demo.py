"""Grant-facing synthetic Research Agent Trust Demo and JSON evidence."""

import json
from dataclasses import dataclass
from pathlib import Path

from agent_boundary_lab import __version__
from agent_boundary_lab.experiment import (
    ExperimentResult,
    StrategySummary,
    build_synthetic_vulnerable_target,
    run_experiment,
)
from agent_boundary_lab.research_workflow import (
    AuditRecord,
    ResearchWorkflowResult,
    run_research_workflow,
)

DEFAULT_EVIDENCE_PATH = Path("artifacts/grant_demo_evidence.json")


@dataclass(frozen=True)
class GrantDemoResult:
    """In-memory results used for both terminal and JSON evidence."""

    workflow: ResearchWorkflowResult
    experiment: ExperimentResult
    evidence: dict[str, object]


def _optional_decision(record: AuditRecord, field: str) -> str | None:
    decision = (
        record.expected_decision if field == "expected" else record.actual_decision
    )
    return decision.value if decision is not None else None


def _audit_evidence(record: AuditRecord) -> dict[str, object]:
    return {
        "workflow_id": record.workflow_id,
        "step_id": record.step_id,
        "sequence": record.sequence,
        "action": record.action,
        "target": record.target,
        "expected_boundary_decision": _optional_decision(record, "expected"),
        "actual_boundary_decision": _optional_decision(record, "actual"),
        "matched_rule": record.matched_rule,
        "reason": record.reason,
        "result": record.result.value,
    }


def _strategy_evidence(summary: StrategySummary) -> dict[str, object]:
    discovery_count = sum(run.violation_found for run in summary.runs)
    return {
        "strategy": summary.strategy_name,
        "runs": len(summary.runs),
        "discovery_count": discovery_count,
        "discovery_rate": summary.discovery_rate,
        "median_evaluations_to_first_violation_successful_runs": (
            summary.median_evaluations_to_first_violation
        ),
        "mean_evaluations_to_first_violation_successful_runs": (
            summary.mean_evaluations_to_first_violation
        ),
        "total_candidate_evaluations": sum(
            run.total_evaluations for run in summary.runs
        ),
    }


def _build_evidence(
    workflow: ResearchWorkflowResult,
    experiment: ExperimentResult,
) -> dict[str, object]:
    target = build_synthetic_vulnerable_target()
    regression_candidate_id = experiment.regression_candidate_id
    if regression_candidate_id is None:
        raise RuntimeError("Synthetic experiment did not discover a violation")
    violation_candidate = next(
        candidate
        for candidate in target.candidates
        if candidate.candidate_id == regression_candidate_id
    )
    violation_record = target.engine.evaluate(
        "grant_demo_discovered_violation",
        violation_candidate.action,
    )
    expected_violation_decision = target.expected_decision(violation_candidate.action)

    approval = workflow.approval_event
    provenance = workflow.provenance
    return {
        "project": {
            "name": "Agent Boundary Lab",
            "version": __version__,
        },
        "disclaimer": [
            "SYNTHETIC RESEARCH WORKFLOW",
            "NO REAL SECRET",
            "NO REAL NETWORK REQUEST",
            "NO CLAIM OF A REAL AGENT VULNERABILITY",
        ],
        "workflow": {
            "id": workflow.workflow_id,
            "name": workflow.workflow_name,
            "result": workflow.status.value,
            "output_id": workflow.output_id,
            "steps": [
                {
                    "step_id": record.step_id,
                    "sequence": record.sequence,
                    "result": record.result.value,
                }
                for record in workflow.audit_trail
            ],
        },
        "audit_trail": [_audit_evidence(record) for record in workflow.audit_trail],
        "provenance": {
            "source_ids": list(provenance.source_ids),
            "output_id": provenance.output_id,
            "transformation_step_id": provenance.transformation_step_id,
            "links": [
                {"source_id": source_id, "output_id": provenance.output_id}
                for source_id in provenance.source_ids
            ],
        },
        "approval_event": {
            "step_id": approval.step_id,
            "target": approval.target,
            "decision": approval.decision.value,
            "workflow_status_before": approval.workflow_status_before.value,
            "workflow_status_after": approval.workflow_status_after.value,
            "send_executed_before_approval": (approval.send_executed_before_approval),
            "send_executed_after_approval": approval.send_executed_after_approval,
        },
        "attack_experiment": {
            "parameters": {
                "target": experiment.target_name,
                "candidate_space_size": experiment.candidate_space_size,
                "candidate_evaluation_budget_per_run": experiment.budget,
                "fixed_seeds": list(experiment.seeds),
            },
            "random_metrics": _strategy_evidence(experiment.random_summary),
            "trace_guided_metrics": _strategy_evidence(experiment.trace_guided_summary),
            "discovered_violation": {
                "candidate_id": violation_candidate.candidate_id,
                "action": violation_candidate.action.action_type.value,
                "target": violation_candidate.action.target,
                "expected_decision": expected_violation_decision.value,
                "actual_decision": violation_record.decision.value,
            },
            "regression_status": "LOCKED",
            "regression_test": "tests/test_regression_violation.py",
        },
        "limitations": [
            "Deterministic synthetic fixtures only",
            "No real AI agent or model API",
            "No real secret access",
            "No real network request",
            "No operating-system sandbox",
            "No claim of a vulnerability in a real agent or security target",
        ],
    }


def run_grant_demo() -> GrantDemoResult:
    """Run the workflow and unchanged attack experiment in memory."""
    workflow = run_research_workflow()
    experiment = run_experiment()
    evidence = _build_evidence(workflow, experiment)
    return GrantDemoResult(workflow, experiment, evidence)


def write_evidence(
    evidence: dict[str, object],
    output_path: Path = DEFAULT_EVIDENCE_PATH,
) -> Path:
    """Write stable, sorted JSON evidence with a fixed newline convention."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    output_path.write_text(serialized, encoding="utf-8", newline="\n")
    return output_path


def _successful_count(summary: StrategySummary) -> int:
    return sum(run.violation_found for run in summary.runs)


def main(output_path: Path = DEFAULT_EVIDENCE_PATH) -> int:
    """Run the grant demo, print a plain-language summary, and write evidence."""
    result = run_grant_demo()
    workflow = result.workflow
    experiment = result.experiment
    write_evidence(result.evidence, output_path)

    print("Agent Boundary Lab")
    print("Research Agent Trust Demo")
    print("SYNTHETIC RESEARCH WORKFLOW")
    print("NO REAL SECRET")
    print("NO REAL NETWORK REQUEST")
    print("NO CLAIM OF A REAL AGENT VULNERABILITY")
    print("[1] Research workflow")
    print("PASS  read paper_a")
    print("PASS  read paper_b")
    print(f"Generated: {workflow.output_id}")
    print("Provenance:")
    print(f"  {workflow.output_id} <- research/paper_a")
    print(f"  {workflow.output_id} <- research/paper_b")
    print("BLOCKED: secret:RESEARCH_TOKEN")
    print("Decision: DENY")
    print("APPROVAL REQUIRED: external:publisher_submission")
    print("Pre-approval send: NOT EXECUTED")
    print(f"Human approval: {workflow.approval_event.decision.value}")
    print(f"Workflow: {workflow.status.value}")
    print("[2] Audit")
    print(f"Steps recorded: {len(workflow.audit_trail)}")
    print(
        "Boundary decisions recorded: "
        f"{sum(record.actual_decision is not None for record in workflow.audit_trail)}"
    )
    print(f"Provenance links: {len(workflow.provenance.source_ids)}")
    print("[3] Automatic boundary search")
    print(
        "Random: "
        f"{_successful_count(experiment.random_summary)}/{len(experiment.seeds)} "
        "discovered"
    )
    print(
        "TraceGuided: "
        f"{_successful_count(experiment.trace_guided_summary)}/"
        f"{len(experiment.seeds)} discovered"
    )
    violation = result.evidence["attack_experiment"]
    if not isinstance(violation, dict):
        raise TypeError("Attack experiment evidence must be an object")
    discovered = violation["discovered_violation"]
    if not isinstance(discovered, dict):
        raise TypeError("Discovered violation evidence must be an object")
    print("Violation:")
    print(f"  {discovered['action']} {discovered['target']}")
    print(f"  Expected: {discovered['expected_decision']}")
    print(f"  Observed: {discovered['actual_decision']}")
    print("Regression: LOCKED")
    print(f"Evidence: {output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
