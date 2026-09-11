"""Regression evaluation for boundary execution records."""

from agent_boundary_lab.models import (
    BoundaryDecision,
    EvaluationResult,
    ExecutionRecord,
)


def evaluate(
    expected: BoundaryDecision,
    execution_record: ExecutionRecord,
) -> EvaluationResult:
    """Compare an engine decision with a scenario's expected decision."""
    return EvaluationResult(
        expected_decision=expected,
        actual_decision=execution_record.decision,
        passed=execution_record.decision == expected,
        execution_record=execution_record,
    )
