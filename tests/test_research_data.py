import asyncio
import json
from pathlib import Path

import pytest

from agent_boundary_lab.models import BoundaryDecision
from agent_boundary_lab.research_data import (
    ALLOWED_TOOL,
    DENIED_TOOL,
    OPENALEX_SERVER_ID,
    McpToolCall,
    ReplayOpenAlexTransport,
    execute_tool_intent,
    run_research_data_workflow,
)
from agent_boundary_lab.research_data_demo import (
    build_evidence,
    main,
    write_evidence,
)


def _run_replay():  # type annotation is inferred from the workflow result
    return asyncio.run(
        run_research_data_workflow(
            ReplayOpenAlexTransport(),
            evidence_mode="replay",
        )
    )


def test_publication_search_is_allowed_and_dispatched() -> None:
    result = _run_replay()

    assert result.allowed.tool_name == ALLOWED_TOOL
    assert result.allowed.boundary_decision is BoundaryDecision.ALLOW
    assert result.allowed.dispatched is True
    assert result.transport_call_count == 1


def test_citation_graph_is_denied_before_transport() -> None:
    transport = ReplayOpenAlexTransport()
    call = McpToolCall(
        OPENALEX_SERVER_ID,
        DENIED_TOOL,
        {"seed_id": "https://openalex.org/W2741809807", "direction": "cites"},
    )

    record, records = asyncio.run(execute_tool_intent(call, transport))

    assert record.boundary_decision is BoundaryDecision.DENY
    assert record.dispatched is False
    assert record.result == "BLOCKED_PRE_DISPATCH"
    assert records == ()
    assert transport.call_count == 0


def test_replay_returns_two_normalized_records_with_provenance() -> None:
    result = _run_replay()

    assert len(result.records) == 2
    assert all(
        record.openalex_id.startswith("https://openalex.org/W")
        for record in result.records
    )
    assert result.provenance.openalex_ids == tuple(
        record.openalex_id for record in result.records
    )
    assert result.provenance.provider == "OpenAlex"
    assert result.provenance.output_id == "research_evidence_bundle"


def test_allow_and_deny_are_both_audited_without_secrets() -> None:
    result = _run_replay()

    assert result.audit_records == (result.allowed, result.denied)
    assert result.allowed.result_ids == result.provenance.openalex_ids
    assert result.denied.dispatched is False
    serialized = json.dumps(build_evidence(result), sort_keys=True)
    assert "OPENALEX_API_KEY" not in serialized


def test_replay_evidence_is_deterministic(tmp_path: Path) -> None:
    first = build_evidence(_run_replay())
    second = build_evidence(_run_replay())
    first_path = write_evidence(first, tmp_path / "first.json")
    second_path = write_evidence(second, tmp_path / "second.json")

    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()


def test_default_demo_is_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    def fail_if_live_transport_is_created() -> None:
        raise AssertionError("default demo attempted live transport")

    monkeypatch.setattr(
        "agent_boundary_lab.research_data_demo.LiveOpenAlexTransport",
        fail_if_live_transport_is_created,
    )

    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Mode: REPLAY" in output
    assert "BLOCKED_PRE_DISPATCH" in output
    assert (tmp_path / "artifacts" / "openalex_mcp_evidence.json").is_file()
