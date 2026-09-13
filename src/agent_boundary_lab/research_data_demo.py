"""CLI and deterministic evidence for the OpenAlex research-data anchor."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

from agent_boundary_lab.research_data import (
    ALLOWED_TOOL,
    DENIED_TOOL,
    OPENALEX_MCP_PACKAGE,
    LiveOpenAlexTransport,
    McpExecutionRecord,
    ReplayOpenAlexTransport,
    ResearchDataResult,
    run_research_data_workflow,
)

DEFAULT_EVIDENCE_PATH = Path("artifacts/openalex_mcp_evidence.json")


def _audit_evidence(record: McpExecutionRecord) -> dict[str, object]:
    return {
        "server_id": record.server_id,
        "tool_name": record.tool_name,
        "sanitized_arguments": dict(record.sanitized_arguments),
        "boundary_decision": record.boundary_decision.value,
        "dispatched": record.dispatched,
        "result_ids": list(record.result_ids),
        "error": record.error,
        "reason": record.reason,
        "result": record.result,
    }


def build_evidence(result: ResearchDataResult) -> dict[str, object]:
    """Build the intentionally small scholarly-metadata evidence document."""

    return {
        "evidence_mode": result.evidence_mode,
        "provider": "OpenAlex",
        "mcp_package": OPENALEX_MCP_PACKAGE,
        "mcp_negotiated_protocol": result.protocol_version,
        "allowed_tool": ALLOWED_TOOL,
        "allowed_decision": result.allowed.boundary_decision.value,
        "allowed_dispatched": result.allowed.dispatched,
        "records": [asdict(record) for record in result.records],
        "record_ids": [record.openalex_id for record in result.records],
        "dois": [record.doi for record in result.records if record.doi is not None],
        "denied_tool": DENIED_TOOL,
        "denied_decision": result.denied.boundary_decision.value,
        "denied_dispatched": result.denied.dispatched,
        "denied_transport_call_count": result.denied_transport_call_count,
        "audit_records": [_audit_evidence(record) for record in result.audit_records],
        "provenance": asdict(result.provenance),
        "limitations": [
            "COMMUNITY MCP SERVER — NOT OFFICIAL OPENALEX MCP",
            "NO LLM",
            "NO FULL TEXT",
            "NO WRITE OPERATION",
            "NO CLAIM OF A REAL SECURITY VULNERABILITY",
            "Scholarly metadata provenance only; paper contents and authenticity were not verified",
        ],
    }


def write_evidence(
    evidence: dict[str, object],
    output_path: Path = DEFAULT_EVIDENCE_PATH,
) -> Path:
    """Write canonical JSON for deterministic replay evidence."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_path


def _print_result(result: ResearchDataResult) -> None:
    mode = result.evidence_mode.upper()
    mode_detail = "OFFLINE FIXTURE" if mode == "REPLAY" else "COMMUNITY MCP"
    print("Agent Boundary Lab - Research Data Trust Demo")
    print(f"MODE: {mode} ({mode_detail})")
    print("Source: OpenAlex scholarly metadata")
    print("MCP: community OpenAlex MCP server (not official OpenAlex MCP)")
    print()
    print("ALLOW")
    print(f"  Tool: {ALLOWED_TOOL}")
    print(f"  Boundary decision: {result.allowed.boundary_decision.value}")
    print(f"  Dispatched: {'YES' if result.allowed.dispatched else 'NO'}")
    print(f"  Records: {len(result.records)}")
    for record in result.records:
        print(f"    - {record.openalex_id}")
        print(f"      DOI: {record.doi or 'NONE'}")
        print(f"      Title: {record.title}")
        year = (
            record.publication_year if record.publication_year is not None else "NONE"
        )
        print(f"      Publication year: {year}")
    print()
    print("DENY")
    print(f"  Tool: {DENIED_TOOL}")
    print(f"  Boundary decision: {result.denied.boundary_decision.value}")
    print(f"  Dispatched: {'YES' if result.denied.dispatched else 'NO'}")
    print(f"  Result: {result.denied.result}")
    print(f"  Transport calls after DENY: {result.denied_transport_call_count}")
    print()
    print("PROVENANCE")
    print(f"  Input records: {len(result.provenance.openalex_ids)}")
    print(f"  Output: {result.provenance.output_id}")
    print()
    print("AUDIT")
    print(f"  Records: {len(result.audit_records)}")
    print("  Status: RECORDED")
    print()
    print("LIMITATIONS")
    print("  COMMUNITY MCP SERVER - NOT OFFICIAL OPENALEX MCP")
    print("  NO LLM")
    print("  NO FULL TEXT")
    print("  NO WRITE OPERATION")
    print("  NO CLAIM OF A REAL SECURITY VULNERABILITY")


async def _run(live: bool) -> ResearchDataResult:
    transport = LiveOpenAlexTransport() if live else ReplayOpenAlexTransport()
    return await run_research_data_workflow(
        transport,
        evidence_mode="live" if live else "replay",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use the real stdio MCP")
    args = parser.parse_args(argv)
    result = asyncio.run(_run(cast(bool, args.live)))
    if not args.live:
        write_evidence(build_evidence(result))
    _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
