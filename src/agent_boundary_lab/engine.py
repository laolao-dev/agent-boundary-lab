"""Deterministic evaluation engine for boundary rules."""

from collections.abc import Sequence

from agent_boundary_lab.models import (
    AgentAction,
    BoundaryDecision,
    BoundaryRule,
    ExecutionRecord,
)
from agent_boundary_lab.policies import DEFAULT_BOUNDARY_RULES


class BoundaryEngine:
    """Match actions against an ordered policy and record the decision."""

    def __init__(
        self,
        rules: Sequence[BoundaryRule] = DEFAULT_BOUNDARY_RULES,
    ) -> None:
        self._rules = tuple(rules)

    def evaluate(
        self,
        scenario_name: str,
        action: AgentAction,
    ) -> ExecutionRecord:
        """Evaluate an action, using a fail-closed decision when no rule matches."""
        for rule in self._rules:
            if rule.action_type == action.action_type and rule.target == action.target:
                return ExecutionRecord(
                    scenario_name=scenario_name,
                    action=action,
                    decision=rule.decision,
                    matched_rule=rule,
                    reason=rule.reason or f"Matched boundary rule: {rule.name}",
                )

        return ExecutionRecord(
            scenario_name=scenario_name,
            action=action,
            decision=BoundaryDecision.DENY,
            matched_rule=None,
            reason="No matching boundary rule",
        )
