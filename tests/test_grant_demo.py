import json
from pathlib import Path

import pytest

from agent_boundary_lab.grant_demo import main, run_grant_demo, write_evidence


def test_grant_demo_runs_and_writes_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "grant_demo_evidence.json"

    exit_code = main(output_path)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output_path.is_file()
    assert "SYNTHETIC RESEARCH WORKFLOW" in output
    assert "Pre-approval send: NOT EXECUTED" in output
    assert "Random: 7/20 discovered" in output
    assert "TraceGuided: 20/20 discovered" in output
    assert "Regression: LOCKED" in output


def test_json_evidence_is_reproducible(tmp_path: Path) -> None:
    result = run_grant_demo()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    write_evidence(result.evidence, first_path)
    write_evidence(run_grant_demo().evidence, second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert json.loads(first_path.read_text(encoding="utf-8")) == result.evidence


def test_grant_demo_preserves_existing_attack_metrics() -> None:
    experiment = run_grant_demo().experiment

    assert experiment.random_summary.discovery_rate == 0.35
    assert experiment.random_summary.mean_evaluations_to_first_violation == 12 / 7
    assert experiment.trace_guided_summary.discovery_rate == 1.0
    assert experiment.trace_guided_summary.mean_evaluations_to_first_violation == 1.45
