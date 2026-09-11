from agent_boundary_lab.attacks import RandomStrategy, TraceGuidedStrategy
from agent_boundary_lab.evaluator import evaluate
from agent_boundary_lab.experiment import (
    DEFAULT_BUDGET,
    DEFAULT_SEEDS,
    build_synthetic_vulnerable_target,
    run_experiment,
    run_search,
)


def test_synthetic_fixture_has_one_violation_among_multiple_mutations() -> None:
    target = build_synthetic_vulnerable_target()
    violating_candidates = []

    seed_record = target.engine.evaluate("seed", target.seed_candidate.action)
    seed_result = evaluate(
        target.expected_decision(target.seed_candidate.action),
        seed_record,
    )
    assert seed_result.passed is True

    for candidate in target.candidates:
        record = target.engine.evaluate(candidate.candidate_id, candidate.action)
        result = evaluate(target.expected_decision(candidate.action), record)
        if not result.passed:
            violating_candidates.append(candidate.candidate_id)

    assert len(target.candidates) == 8
    assert violating_candidates == ["secret_target_as_file"]


def test_both_strategies_use_the_same_budget_and_are_reproducible() -> None:
    first = run_experiment()
    second = run_experiment()

    assert first == second
    assert first.seeds == DEFAULT_SEEDS
    assert first.budget == DEFAULT_BUDGET
    assert first.random_summary.discovery_rate == 0.35
    assert first.random_summary.median_evaluations_to_first_violation == 1.0
    assert first.random_summary.mean_evaluations_to_first_violation == 12 / 7
    assert first.trace_guided_summary.discovery_rate == 1.0
    assert first.trace_guided_summary.median_evaluations_to_first_violation == 1.0
    assert first.trace_guided_summary.mean_evaluations_to_first_violation == 1.45
    assert all(
        run.total_evaluations <= DEFAULT_BUDGET
        for run in (*first.random_summary.runs, *first.trace_guided_summary.runs)
    )


def test_search_reports_not_found_without_treating_it_as_a_violation() -> None:
    target = build_synthetic_vulnerable_target()

    random_result = run_search(RandomStrategy(0), target, budget=1, seed=0)
    trace_result = run_search(TraceGuidedStrategy(0), target, budget=1, seed=0)

    assert random_result.total_evaluations == 1
    assert trace_result.total_evaluations == 1
    assert random_result.violation_found is False
    assert random_result.evaluations_to_first_violation is None
    assert trace_result.violation_found is False
    assert trace_result.evaluations_to_first_violation is None
