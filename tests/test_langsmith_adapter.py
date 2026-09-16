"""Offline regression tests for LangSmith CLI JSONL normalization."""

import json
from pathlib import Path
from typing import Any

import pytest

from agent_boundary_lab.assurance.models import ArtifactRole
from agent_boundary_lab.assurance.verifier import verify_workflow
from agent_boundary_lab.cli import main
from agent_boundary_lab.langsmith_adapter import (
    LangSmithImportError,
    LangSmithTraceAdapter,
)

FIXTURE = Path(__file__).parent / "fixtures/langsmith_trace_synthetic.jsonl"


def _rows() -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()
    ]


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def test_root_children_types_and_safe_io_are_preserved() -> None:
    workflow = LangSmithTraceAdapter().import_file(FIXTURE)
    assert workflow.workflow_id == "langsmith:11111111-1111-4111-8111-111111111111"
    assert workflow.title == "research_answer"
    assert len(workflow.events) == 4
    assert [event.event_type for event in workflow.events] == [
        "chain",
        "tool",
        "retriever",
        "llm",
    ]
    assert [event.sequence for event in workflow.events] == [0, 1, 2, 3]
    assert workflow.events[0].parent_event_id is None
    assert all(
        event.parent_event_id == workflow.events[0].event_id
        for event in workflow.events[1:]
    )
    assert workflow.events[1].tool == "web_search"
    assert workflow.events[1].query == "example bounded workflow"
    assert workflow.events[2].query == "example bounded workflow"
    assert workflow.events[3].tool is None
    assert all(event.executed is True for event in workflow.events)
    assert workflow.events[0].timestamp == "2026-09-16T01:00:00Z"
    assert workflow.events[0].latency_ms == 3000
    assert workflow.events[3].observation == "status=success; output field present"


def test_candidate_source_is_not_supporting_evidence() -> None:
    workflow = LangSmithTraceAdapter().import_file(FIXTURE)
    assert len(workflow.sources) == 1
    assert workflow.sources[0].source_id == "doc-1"
    assert workflow.sources[0].locator == "https://example.org/bounded-workflow"
    assert workflow.sources[0].title == "Bounded Workflow"
    assert workflow.evidence == ()
    assert workflow.claims == ()
    assert workflow.assurance_context.events == ()
    assert len(workflow.artifacts) == 2
    retrieval, final = workflow.artifacts
    assert retrieval.artifact_role is ArtifactRole.INTERMEDIATE
    assert retrieval.source_refs == ("doc-1",)
    assert final.artifact_role is ArtifactRole.FINAL_OUTPUT
    assert final.produced_by_event == workflow.events[0].event_id
    assert final.source_refs == ()
    assert final.evidence_refs == ()
    assert final.parent_artifact_refs == ()


def test_import_then_verify_keeps_provenance_incomplete(tmp_path: Path) -> None:
    normalized = tmp_path / "workflow.json"
    report_path = tmp_path / "report.json"
    assert main(["import", "langsmith", str(FIXTURE), "--output", str(normalized)]) == 0
    assert main(["verify", str(normalized), "--output", str(report_path)]) == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checks = {check["check"]: check["status"] for check in report["checks"]}
    assert report["summary"]["overall_status"] == "INCOMPLETE"
    assert checks["PROVENANCE"] != "PASS"
    assert checks["GOVERNANCE"] == "NOT_EVALUATED"
    assert checks["HUMAN_REVIEW"] == "NOT_EVALUATED"
    assert any(
        "PROV_FINAL_OUTPUT_UNGROUNDED" in finding["message"]
        for finding in report["findings"]
    )


def test_error_run_keeps_error_and_outcome(tmp_path: Path) -> None:
    rows = _rows()
    rows[3]["status"] = "error"
    rows[3]["error"] = "model timed out"
    rows[3]["outputs"] = None
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "error.jsonl", rows)
    )
    llm = workflow.events[3]
    assert llm.executed is True
    assert llm.error == "model timed out"
    assert llm.observation == "status=error; error recorded"


def test_error_with_secret_is_redacted(tmp_path: Path) -> None:
    rows = _rows()
    rows[3]["status"] = "error"
    rows[3]["error"] = "api_key=do-not-copy"
    rows[3]["outputs"] = None
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "secret.jsonl", rows)
    )
    assert workflow.events[3].error == "LangSmith error recorded; details omitted"
    assert "do-not-copy" not in str(workflow)


def test_root_without_output_has_no_final_artifact(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["outputs"] = None
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "no-output.jsonl", rows)
    )
    assert all(
        artifact.artifact_role is not ArtifactRole.FINAL_OUTPUT
        for artifact in workflow.artifacts
    )


@pytest.mark.parametrize(
    "root_change", [{"status": "error"}, {"end_time": None}, {"outputs": {}}]
)
def test_incomplete_root_is_not_final(
    tmp_path: Path, root_change: dict[str, Any]
) -> None:
    rows = _rows()
    rows[0].update(root_change)
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "root.jsonl", rows)
    )
    assert all(
        artifact.artifact_role is not ArtifactRole.FINAL_OUTPUT
        for artifact in workflow.artifacts
    )


def test_unknown_external_fields_are_ignored(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["future_field"] = {"anything": [1, 2, 3]}
    nested: dict[str, Any] = {}
    current = nested
    for _ in range(40):
        child: dict[str, Any] = {}
        current["child"] = child
        current = child
    rows[1]["new_cost_field"] = nested
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "extra.jsonl", rows)
    )
    assert len(workflow.events) == 4
    assert "future_field" not in str(workflow)


@pytest.mark.parametrize(
    "content",
    [
        "{broken}\n",
        "\n",
        '{"runs": []}\n',
        "[]\n",
    ],
)
def test_malformed_jsonl_returns_exit_2_without_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    input_path = tmp_path / "bad.jsonl"
    input_path.write_text(content, encoding="utf-8")
    output = tmp_path / "workflow.json"
    assert main(["import", "langsmith", str(input_path), "--output", str(output)]) == 2
    assert not output.exists()
    message = capsys.readouterr().err
    assert "LANGSMITH_IMPORT_ERROR" in message
    assert str(input_path) in message
    assert "line 1" in message


@pytest.mark.parametrize(
    "edit",
    [
        lambda rows: rows[0].pop("run_id"),
        lambda rows: rows[1].update(run_id=rows[0]["run_id"]),
    ],
)
def test_missing_or_duplicate_run_id_rejected(tmp_path: Path, edit: Any) -> None:
    rows = _rows()
    edit(rows)
    path = _write_rows(tmp_path / "bad-id.jsonl", rows)
    with pytest.raises(LangSmithImportError, match="run_id"):
        LangSmithTraceAdapter().import_file(path)


def test_dangling_parent_rejected(tmp_path: Path) -> None:
    rows = _rows()
    rows[1]["parent_run_id"] = "missing-parent"
    path = _write_rows(tmp_path / "dangling.jsonl", rows)
    with pytest.raises(LangSmithImportError, match="dangling parent_run_id"):
        LangSmithTraceAdapter().import_file(path)


def test_mixed_traces_rejected(tmp_path: Path) -> None:
    rows = _rows()
    rows[1]["trace_id"] = "other-trace"
    path = _write_rows(tmp_path / "mixed.jsonl", rows)
    with pytest.raises(LangSmithImportError, match="mixed trace_id"):
        LangSmithTraceAdapter().import_file(path)


def test_parent_cycle_rejected_by_existing_schema(tmp_path: Path) -> None:
    rows = _rows()
    rows[1]["parent_run_id"] = rows[2]["run_id"]
    rows[2]["parent_run_id"] = rows[1]["run_id"]
    path = _write_rows(tmp_path / "cycle.jsonl", rows)
    with pytest.raises(LangSmithImportError, match="cycle"):
        LangSmithTraceAdapter().import_file(path)


def test_unidentified_document_does_not_become_source(tmp_path: Path) -> None:
    rows = _rows()
    rows[2]["outputs"]["documents"][0]["metadata"] = {"title": "No locator"}
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "no-source.jsonl", rows)
    )
    assert workflow.sources == ()
    assert workflow.evidence == ()
    assert workflow.artifacts[0].source_refs == ()


def test_explicit_document_id_without_url_is_a_candidate_source(tmp_path: Path) -> None:
    rows = _rows()
    rows[2]["outputs"]["documents"][0]["metadata"] = {"doc_id": "doc-only"}
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "id-only.jsonl", rows)
    )
    assert workflow.sources[0].source_id == "doc-only"
    assert workflow.sources[0].locator is None


def test_query_and_url_with_sensitive_fields_are_not_copied(tmp_path: Path) -> None:
    rows = _rows()
    rows[1]["inputs"]["query"] = "api_key=do-not-copy"
    rows[2]["outputs"]["documents"][0]["metadata"]["source"] = (
        "https://example.org/doc?token=do-not-copy"
    )
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "sensitive.jsonl", rows)
    )
    assert workflow.events[1].query is None
    assert workflow.sources[0].locator is None
    assert "do-not-copy" not in str(workflow)


def test_import_is_deterministic_and_does_not_overwrite(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    assert main(["import", "langsmith", str(FIXTURE), "--output", str(first)]) == 0
    assert main(["import", "langsmith", str(FIXTURE), "--output", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()
    before = first.read_bytes()
    assert main(["import", "langsmith", str(FIXTURE), "--output", str(first)]) == 2
    assert first.read_bytes() == before


def test_masked_io_remains_unknown(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["outputs"] = None
    rows[1]["inputs"] = None
    workflow = LangSmithTraceAdapter().import_file(
        _write_rows(tmp_path / "masked.jsonl", rows)
    )
    assert workflow.events[1].query is None
    assert all(
        artifact.artifact_role is not ArtifactRole.FINAL_OUTPUT
        for artifact in workflow.artifacts
    )
    assert verify_workflow(workflow).summary.overall_status.value == "INCOMPLETE"
