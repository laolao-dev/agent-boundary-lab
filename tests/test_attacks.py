from agent_boundary_lab.attacks import (
    CandidateMutation,
    RandomStrategy,
    SearchObservation,
    TraceGuidedStrategy,
)
from agent_boundary_lab.engine import BoundaryEngine
from agent_boundary_lab.models import (
    ActionType,
    AgentAction,
    BoundaryDecision,
    BoundaryRule,
)


def _candidate(candidate_id: str, action: AgentAction) -> CandidateMutation:
    return CandidateMutation(candidate_id, "seed", candidate_id, action)


def test_random_strategy_is_reproducible_for_a_fixed_seed() -> None:
    candidates = tuple(
        _candidate(
            f"candidate_{index}",
            AgentAction(ActionType.READ_FILE, f"workspace/{index}.txt"),
        )
        for index in range(5)
    )

    first = RandomStrategy(seed=17).select_next(candidates, ())
    second = RandomStrategy(seed=17).select_next(candidates, ())

    assert first == second


def test_trace_guided_uses_allow_trace_to_prioritize_boundary_crossing() -> None:
    seed = _candidate(
        "seed",
        AgentAction(ActionType.READ_FILE, "workspace/research-notes.txt"),
    )
    seed_record = BoundaryEngine(
        (
            BoundaryRule(
                name="synthetic_allow_seed",
                action_type=ActionType.READ_FILE,
                target="workspace/research-notes.txt",
                decision=BoundaryDecision.ALLOW,
            ),
        )
    ).evaluate("seed", seed.action)
    observations = (SearchObservation(seed, seed_record),)
    candidates = (
        _candidate(
            "same_category",
            AgentAction(ActionType.READ_FILE, "workspace/archive.txt"),
        ),
        _candidate(
            "cross_category",
            AgentAction(ActionType.READ_FILE, "synthetic:archive"),
        ),
        _candidate(
            "different_action",
            AgentAction(ActionType.READ_SECRET, "synthetic:archive"),
        ),
    )

    selected = TraceGuidedStrategy(seed=17).select_next(candidates, observations)

    assert selected.candidate_id == "cross_category"
