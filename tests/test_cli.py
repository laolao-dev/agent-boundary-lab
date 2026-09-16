import json
from pathlib import Path

import pytest

from agent_boundary_lab.cli import main


def test_verify_cli_writes_intentionally_incomplete_example(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "verify",
            "examples/research_workflow.json",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert report["summary"]["overall_status"] == "INCOMPLETE"
    assert report["summary"]["total_findings"] == 3


def test_verify_cli_reports_validation_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = tmp_path / "malformed.json"
    workflow.write_text('{"workflow_id": "broken"}', encoding="utf-8")

    exit_code = main(["verify", str(workflow)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "WORKFLOW_VALIDATION_ERROR" in captured.err
    assert "missing required field 'events'" in captured.err
