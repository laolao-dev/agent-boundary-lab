"""Minimal deterministic attack-search strategies for synthetic experiments."""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from agent_boundary_lab.models import (
    AgentAction,
    BoundaryDecision,
    ExecutionRecord,
)


@dataclass(frozen=True)
class CandidateMutation:
    """A reproducible mutation of a seed action."""

    candidate_id: str
    parent_candidate_id: str | None
    description: str
    action: AgentAction


@dataclass(frozen=True)
class SearchObservation:
    """Trace information visible to an attack strategy after evaluation."""

    candidate: CandidateMutation
    execution_record: ExecutionRecord


class AttackStrategy(Protocol):
    """Select the next candidate without access to expected decisions."""

    @property
    def name(self) -> str:
        """Human-readable strategy name."""
        ...

    def select_next(
        self,
        candidates: Sequence[CandidateMutation],
        observations: Sequence[SearchObservation],
    ) -> CandidateMutation:
        """Choose one unevaluated candidate using available observations."""
        ...


class RandomStrategy:
    """Sample unevaluated candidates using a fixed pseudo-random seed."""

    def __init__(self, seed: int) -> None:
        self._random = random.Random(seed)

    @property
    def name(self) -> str:
        return "Random"

    def select_next(
        self,
        candidates: Sequence[CandidateMutation],
        observations: Sequence[SearchObservation],
    ) -> CandidateMutation:
        del observations
        if not candidates:
            raise ValueError("No candidates remain")
        return candidates[self._random.randrange(len(candidates))]


class TraceGuidedStrategy:
    """Prioritize boundary-crossing mutations from permissive matched traces."""

    def __init__(self, seed: int) -> None:
        self._random = random.Random(seed)

    @property
    def name(self) -> str:
        return "TraceGuided"

    def select_next(
        self,
        candidates: Sequence[CandidateMutation],
        observations: Sequence[SearchObservation],
    ) -> CandidateMutation:
        if not candidates:
            raise ValueError("No candidates remain")

        guiding_observation = self._guiding_observation(observations)
        if guiding_observation is None:
            return candidates[self._random.randrange(len(candidates))]

        scores = tuple(
            self._candidate_score(candidate, guiding_observation)
            for candidate in candidates
        )
        highest_score = max(scores)
        highest_scoring = tuple(
            candidate
            for candidate, score in zip(candidates, scores, strict=True)
            if score == highest_score
        )
        return highest_scoring[self._random.randrange(len(highest_scoring))]

    @staticmethod
    def _guiding_observation(
        observations: Sequence[SearchObservation],
    ) -> SearchObservation | None:
        matched = tuple(
            observation
            for observation in observations
            if observation.execution_record.matched_rule is not None
        )
        if not matched:
            return None

        decision_priority = {
            BoundaryDecision.ALLOW: 2,
            BoundaryDecision.REQUIRE_APPROVAL: 1,
            BoundaryDecision.DENY: 0,
        }
        return max(
            matched,
            key=lambda observation: decision_priority[
                observation.execution_record.decision
            ],
        )

    @staticmethod
    def _candidate_score(
        candidate: CandidateMutation,
        observation: SearchObservation,
    ) -> int:
        record = observation.execution_record
        rule = record.matched_rule
        if rule is None:
            return 0

        score = 0
        same_action_type = candidate.action.action_type == rule.action_type
        crosses_target_category = _target_category(
            candidate.action.target
        ) != _target_category(rule.target)

        if record.decision is BoundaryDecision.ALLOW:
            score += 4 if same_action_type else 0
            score += 3 if crosses_target_category else 0
        elif record.decision is BoundaryDecision.REQUIRE_APPROVAL:
            score += 2 if same_action_type else 0
            score += 1 if crosses_target_category else 0
        elif same_action_type:
            score += 1

        if candidate.parent_candidate_id == observation.candidate.candidate_id:
            score += 1
        return score


def _target_category(target: str) -> str:
    """Return a small logical category without inspecting a real resource."""
    if "://" in target:
        return "network"
    if ":" in target:
        return target.split(":", maxsplit=1)[0]
    if "/" in target:
        return target.split("/", maxsplit=1)[0]
    return target
