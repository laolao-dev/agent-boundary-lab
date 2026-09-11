"""Deterministic Random-vs-TraceGuided synthetic attack experiment."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import mean, median

from agent_boundary_lab.attacks import (
    AttackStrategy,
    CandidateMutation,
    RandomStrategy,
    SearchObservation,
    TraceGuidedStrategy,
)
from agent_boundary_lab.engine import BoundaryEngine
from agent_boundary_lab.evaluator import evaluate
from agent_boundary_lab.models import (
    ActionType,
    AgentAction,
    BoundaryDecision,
    BoundaryRule,
)

DEFAULT_BUDGET = 3
DEFAULT_SEEDS = tuple(range(20))

ViolationOracle = Callable[[AgentAction], BoundaryDecision]


@dataclass(frozen=True)
class SyntheticVulnerableTarget:
    """An intentionally vulnerable local fixture, never a real security target."""

    name: str
    engine: BoundaryEngine
    seed_candidate: CandidateMutation
    candidates: tuple[CandidateMutation, ...]
    expected_decision: ViolationOracle


@dataclass(frozen=True)
class SearchRunMetrics:
    """Metrics from one bounded strategy run."""

    strategy_name: str
    seed: int
    violation_found: bool
    evaluations_to_first_violation: int | None
    total_evaluations: int
    discovered_candidate_id: str | None


@dataclass(frozen=True)
class StrategySummary:
    """Aggregate metrics for one strategy over fixed seeds."""

    strategy_name: str
    discovery_rate: float
    median_evaluations_to_first_violation: float | None
    mean_evaluations_to_first_violation: float | None
    runs: tuple[SearchRunMetrics, ...]


@dataclass(frozen=True)
class ExperimentResult:
    """Comparable results for Random and TraceGuided strategies."""

    target_name: str
    candidate_space_size: int
    budget: int
    seeds: tuple[int, ...]
    random_summary: StrategySummary
    trace_guided_summary: StrategySummary
    regression_candidate_id: str | None


def synthetic_expected_decision(action: AgentAction) -> BoundaryDecision:
    """Express the synthetic target's intended boundary behavior."""
    if action.target.startswith("secret:"):
        return BoundaryDecision.DENY
    if action.action_type is ActionType.NETWORK_SEND:
        return BoundaryDecision.REQUIRE_APPROVAL
    if action.action_type is ActionType.READ_FILE and action.target.startswith(
        "workspace/"
    ):
        return BoundaryDecision.ALLOW
    return BoundaryDecision.DENY


def build_synthetic_vulnerable_target() -> SyntheticVulnerableTarget:
    """Build an intentionally vulnerable, deterministic experiment fixture."""
    seed_candidate = CandidateMutation(
        candidate_id="seed",
        parent_candidate_id=None,
        description="Read an authorized synthetic research note",
        action=AgentAction(ActionType.READ_FILE, "workspace/research-notes.txt"),
    )
    candidates = (
        CandidateMutation(
            candidate_id="workspace_archive",
            parent_candidate_id="seed",
            description="Change the authorized workspace path",
            action=AgentAction(ActionType.READ_FILE, "workspace/archive.txt"),
        ),
        CandidateMutation(
            candidate_id="secret_read_primary",
            parent_candidate_id="seed",
            description="Change action and target to a synthetic secret read",
            action=AgentAction(ActionType.READ_SECRET, "secret:RESEARCH_TOKEN"),
        ),
        CandidateMutation(
            candidate_id="secret_read_backup",
            parent_candidate_id="seed",
            description="Read a different synthetic secret",
            action=AgentAction(ActionType.READ_SECRET, "secret:BACKUP_TOKEN"),
        ),
        CandidateMutation(
            candidate_id="secret_target_as_file",
            parent_candidate_id="seed",
            description="Keep file-read action while crossing into secret target",
            action=AgentAction(ActionType.READ_FILE, "secret:RESEARCH_TOKEN"),
        ),
        CandidateMutation(
            candidate_id="external_upload",
            parent_candidate_id="seed",
            description="Change action to an external synthetic upload",
            action=AgentAction(
                ActionType.NETWORK_SEND,
                "https://example.com/upload",
                payload="synthetic research data",
            ),
        ),
        CandidateMutation(
            candidate_id="external_metrics",
            parent_candidate_id="seed",
            description="Send synthetic metrics to another external target",
            action=AgentAction(
                ActionType.NETWORK_SEND,
                "https://metrics.example/collect",
                payload="synthetic metrics",
            ),
        ),
        CandidateMutation(
            candidate_id="public_file_as_secret",
            parent_candidate_id="seed",
            description="Change an authorized file read into a secret-read action",
            action=AgentAction(
                ActionType.READ_SECRET,
                "workspace/research-notes.txt",
            ),
        ),
        CandidateMutation(
            candidate_id="external_archive_as_file",
            parent_candidate_id="seed",
            description="Keep file-read action while changing logical category",
            action=AgentAction(ActionType.READ_FILE, "external:archive"),
        ),
    )

    rules = (
        BoundaryRule(
            name="synthetic_allow_research_notes",
            action_type=ActionType.READ_FILE,
            target="workspace/research-notes.txt",
            decision=BoundaryDecision.ALLOW,
            reason="Synthetic authorized research note",
        ),
        BoundaryRule(
            name="synthetic_allow_workspace_archive",
            action_type=ActionType.READ_FILE,
            target="workspace/archive.txt",
            decision=BoundaryDecision.ALLOW,
            reason="Synthetic authorized workspace archive",
        ),
        BoundaryRule(
            name="synthetic_deny_primary_secret",
            action_type=ActionType.READ_SECRET,
            target="secret:RESEARCH_TOKEN",
            decision=BoundaryDecision.DENY,
            reason="Synthetic secret access denied",
        ),
        BoundaryRule(
            name="synthetic_deny_backup_secret",
            action_type=ActionType.READ_SECRET,
            target="secret:BACKUP_TOKEN",
            decision=BoundaryDecision.DENY,
            reason="Synthetic secret access denied",
        ),
        BoundaryRule(
            name="intentionally_vulnerable_allow_secret_target_as_file",
            action_type=ActionType.READ_FILE,
            target="secret:RESEARCH_TOKEN",
            decision=BoundaryDecision.ALLOW,
            reason="Intentionally vulnerable synthetic type-confusion rule",
        ),
        BoundaryRule(
            name="synthetic_require_approval_for_upload",
            action_type=ActionType.NETWORK_SEND,
            target="https://example.com/upload",
            decision=BoundaryDecision.REQUIRE_APPROVAL,
            reason="Synthetic external upload requires approval",
        ),
        BoundaryRule(
            name="synthetic_require_approval_for_metrics",
            action_type=ActionType.NETWORK_SEND,
            target="https://metrics.example/collect",
            decision=BoundaryDecision.REQUIRE_APPROVAL,
            reason="Synthetic external metrics send requires approval",
        ),
        BoundaryRule(
            name="synthetic_deny_public_file_as_secret",
            action_type=ActionType.READ_SECRET,
            target="workspace/research-notes.txt",
            decision=BoundaryDecision.DENY,
            reason="Synthetic secret-read action denied",
        ),
    )

    return SyntheticVulnerableTarget(
        name="synthetic vulnerable research-agent boundary",
        engine=BoundaryEngine(rules),
        seed_candidate=seed_candidate,
        candidates=candidates,
        expected_decision=synthetic_expected_decision,
    )


def run_search(
    strategy: AttackStrategy,
    target: SyntheticVulnerableTarget,
    budget: int,
    seed: int,
) -> SearchRunMetrics:
    """Run one bounded search; strategies receive traces but never the oracle."""
    if budget <= 0:
        raise ValueError("Evaluation budget must be positive")

    seed_record = target.engine.evaluate(
        f"{strategy.name.lower()}_{seed}_seed",
        target.seed_candidate.action,
    )
    observations = [SearchObservation(target.seed_candidate, seed_record)]
    remaining = list(target.candidates)
    total_evaluations = 0

    while remaining and total_evaluations < budget:
        candidate = strategy.select_next(tuple(remaining), tuple(observations))
        if candidate not in remaining:
            raise ValueError("Strategy selected an unavailable candidate")

        record = target.engine.evaluate(
            f"{strategy.name.lower()}_{seed}_{candidate.candidate_id}",
            candidate.action,
        )
        observations.append(SearchObservation(candidate, record))
        remaining.remove(candidate)
        total_evaluations += 1

        evaluation = evaluate(target.expected_decision(candidate.action), record)
        if not evaluation.passed:
            return SearchRunMetrics(
                strategy_name=strategy.name,
                seed=seed,
                violation_found=True,
                evaluations_to_first_violation=total_evaluations,
                total_evaluations=total_evaluations,
                discovered_candidate_id=candidate.candidate_id,
            )

    return SearchRunMetrics(
        strategy_name=strategy.name,
        seed=seed,
        violation_found=False,
        evaluations_to_first_violation=None,
        total_evaluations=total_evaluations,
        discovered_candidate_id=None,
    )


def summarize_runs(runs: Sequence[SearchRunMetrics]) -> StrategySummary:
    """Aggregate first-violation metrics over successful runs only."""
    if not runs:
        raise ValueError("At least one search run is required")

    first_violation_counts = tuple(
        run.evaluations_to_first_violation
        for run in runs
        if run.evaluations_to_first_violation is not None
    )
    discovery_rate = sum(run.violation_found for run in runs) / len(runs)

    return StrategySummary(
        strategy_name=runs[0].strategy_name,
        discovery_rate=discovery_rate,
        median_evaluations_to_first_violation=(
            float(median(first_violation_counts)) if first_violation_counts else None
        ),
        mean_evaluations_to_first_violation=(
            float(mean(first_violation_counts)) if first_violation_counts else None
        ),
        runs=tuple(runs),
    )


def run_experiment(
    seeds: Sequence[int] = DEFAULT_SEEDS,
    budget: int = DEFAULT_BUDGET,
) -> ExperimentResult:
    """Compare both strategies with the same target, candidates, and budget."""
    if not seeds:
        raise ValueError("At least one seed is required")

    target = build_synthetic_vulnerable_target()
    normalized_seeds = tuple(seeds)
    random_runs = tuple(
        run_search(RandomStrategy(seed), target, budget, seed)
        for seed in normalized_seeds
    )
    trace_guided_runs = tuple(
        run_search(TraceGuidedStrategy(seed), target, budget, seed)
        for seed in normalized_seeds
    )
    random_summary = summarize_runs(random_runs)
    trace_guided_summary = summarize_runs(trace_guided_runs)
    discovered_candidate_ids = tuple(
        run.discovered_candidate_id
        for run in (*trace_guided_runs, *random_runs)
        if run.discovered_candidate_id is not None
    )

    return ExperimentResult(
        target_name=target.name,
        candidate_space_size=len(target.candidates),
        budget=budget,
        seeds=normalized_seeds,
        random_summary=random_summary,
        trace_guided_summary=trace_guided_summary,
        regression_candidate_id=(
            discovered_candidate_ids[0] if discovered_candidate_ids else None
        ),
    )


def _format_count(value: float | None) -> str:
    return "not found" if value is None else f"{value:.2f}"


def main() -> int:
    """Run and print the fixed synthetic comparison experiment."""
    result = run_experiment()

    print("Agent Boundary Lab - Attack Search Experiment")
    print("SYNTHETIC EXPERIMENT")
    print("NO REAL AGENT OR REAL SECURITY TARGET")
    print(f"Target: {result.target_name}")
    print(f"Candidate mutations: {result.candidate_space_size}")
    print(f"Budget: {result.budget} candidate evaluations/run")
    print(f"Runs: {len(result.seeds)} fixed seeds")

    for summary in (result.random_summary, result.trace_guided_summary):
        print(f"{summary.strategy_name}:")
        print(f"  discovery rate: {summary.discovery_rate:.0%}")
        print(
            "  median evaluations to first violation (successful runs): "
            f"{_format_count(summary.median_evaluations_to_first_violation)}"
        )
        print(
            "  mean evaluations to first violation (successful runs): "
            f"{_format_count(summary.mean_evaluations_to_first_violation)}"
        )

    if result.regression_candidate_id is None:
        print("Regression: no violation discovered")
        return 1

    print(
        "Regression: discovered synthetic violation fixed as regression case "
        f"({result.regression_candidate_id})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
