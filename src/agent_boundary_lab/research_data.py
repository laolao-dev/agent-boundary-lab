"""Minimal pre-dispatch boundary anchor for OpenAlex scholarly metadata."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_boundary_lab.engine import BoundaryEngine
from agent_boundary_lab.models import (
    ActionType,
    AgentAction,
    BoundaryDecision,
    BoundaryRule,
)

OPENALEX_SERVER_ID = "openalex"
OPENALEX_PROVIDER = "OpenAlex"
OPENALEX_MCP_PACKAGE = "@cyanheads/openalex-mcp-server@0.7.8"
OPENALEX_PROTOCOL = "2025-06-18"
ALLOWED_TOOL = "openalex_search_entities"
DENIED_TOOL = "openalex_get_citation_graph"
OUTPUT_ID = "research_evidence_bundle"
REPLAY_FIXTURE = Path(__file__).parent / "fixtures" / "openalex_replay.json"

SEARCH_ARGUMENTS: dict[str, object] = {
    "entity_type": "works",
    "filters": {"openalex": "W2741809807|W2919115771"},
    "select": ["doi", "publication_year"],
    "per_page": 2,
}

RESEARCH_DATA_RULES: tuple[BoundaryRule, ...] = (
    BoundaryRule(
        name="allow_openalex_publication_search",
        action_type=ActionType.MCP_TOOL_CALL,
        target=f"mcp:{OPENALEX_SERVER_ID}/{ALLOWED_TOOL}",
        decision=BoundaryDecision.ALLOW,
        reason="This workflow allows bounded OpenAlex publication search",
    ),
    BoundaryRule(
        name="deny_openalex_citation_graph",
        action_type=ActionType.MCP_TOOL_CALL,
        target=f"mcp:{OPENALEX_SERVER_ID}/{DENIED_TOOL}",
        decision=BoundaryDecision.DENY,
        reason="This least-privilege workflow does not allow citation graph access",
    ),
)


@dataclass(frozen=True)
class McpToolCall:
    """Intent to invoke one tool on the only configured MCP server."""

    server_id: str
    tool_name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True)
class ScholarlyRecord:
    """The only OpenAlex metadata retained by the workflow."""

    openalex_id: str
    doi: str | None
    title: str
    publication_year: int | None


@dataclass(frozen=True)
class McpExecutionRecord:
    """Auditable boundary and dispatch outcome for one MCP tool intent."""

    server_id: str
    tool_name: str
    sanitized_arguments: Mapping[str, object]
    dispatched: bool
    result_ids: tuple[str, ...]
    error: str | None
    boundary_decision: BoundaryDecision
    reason: str
    result: str


@dataclass(frozen=True)
class ResearchDataProvenance:
    """Metadata lineage from OpenAlex records to the evidence bundle."""

    provider: str
    openalex_ids: tuple[str, ...]
    dois: tuple[str, ...]
    mcp_server: str
    mcp_tool: str
    workflow_step: str
    output_id: str


@dataclass(frozen=True)
class ResearchDataResult:
    """Complete result of the minimal allow/deny research-data demo."""

    evidence_mode: str
    protocol_version: str
    records: tuple[ScholarlyRecord, ...]
    allowed: McpExecutionRecord
    denied: McpExecutionRecord
    audit_records: tuple[McpExecutionRecord, ...]
    provenance: ResearchDataProvenance
    transport_call_count: int
    denied_transport_call_count: int


class OpenAlexTransport(Protocol):
    """Small transport seam used by replay and the real stdio client."""

    protocol_version: str
    call_count: int
    tool_names: tuple[str, ...]

    async def start(self) -> None:
        """Start the transport and complete MCP discovery."""
        ...

    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        """Call one MCP tool and return its structured result."""
        ...

    async def close(self) -> None:
        """Close any transport resources."""
        ...


class ReplayOpenAlexTransport:
    """Deterministic, network-free transport backed by a minimal fixture."""

    protocol_version: str = OPENALEX_PROTOCOL
    tool_names: tuple[str, ...] = (ALLOWED_TOOL, DENIED_TOOL)

    def __init__(self, fixture_path: Path = REPLAY_FIXTURE) -> None:
        self.fixture_path = fixture_path
        self.call_count = 0

    async def start(self) -> None:
        """Replay startup performs no I/O beyond reading the local fixture later."""

    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self.call_count += 1
        if tool_name != ALLOWED_TOOL:
            raise RuntimeError(f"Replay has no response for tool: {tool_name}")
        if dict(arguments) != SEARCH_ARGUMENTS:
            raise RuntimeError("Replay arguments do not match the bounded fixture")
        loaded = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise TypeError("Replay fixture must contain a JSON object")
        return cast(dict[str, object], loaded)

    async def close(self) -> None:
        """Replay transport holds no external resources."""


class LiveOpenAlexTransport:
    """Real stdio MCP transport for the pinned community OpenAlex server."""

    def __init__(self) -> None:
        self.protocol_version = ""
        self.call_count = 0
        self.tool_names: tuple[str, ...] = ()
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def start(self) -> None:
        api_key = os.environ.get("OPENALEX_API_KEY")
        if not api_key:
            raise RuntimeError("OPENALEX_API_KEY is not present")
        command = shutil.which("npx.cmd" if os.name == "nt" else "npx")
        if command is None:
            raise RuntimeError("npx executable was not found")

        stack = AsyncExitStack()
        try:
            errlog = stack.enter_context(open(os.devnull, "w", encoding="utf-8"))
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(
                    StdioServerParameters(
                        command=command,
                        args=["--yes", OPENALEX_MCP_PACKAGE],
                        env={"OPENALEX_API_KEY": api_key},
                    ),
                    errlog=errlog,
                )
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            initialized = await session.initialize()
            tools = await session.list_tools()
        except BaseException:
            await stack.aclose()
            raise

        self._stack = stack
        self._session = session
        self.protocol_version = initialized.protocol_version
        self.tool_names = tuple(tool.name for tool in tools.tools)

    async def call_tool(
        self, tool_name: str, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if self._session is None:
            raise RuntimeError("Live MCP transport has not started")
        self.call_count += 1
        response = await self._session.call_tool(tool_name, dict(arguments))
        if getattr(response, "is_error", False):
            raise RuntimeError("OpenAlex MCP tool returned an error")
        structured = getattr(response, "structured_content", None)
        if not isinstance(structured, Mapping):
            raise RuntimeError("OpenAlex MCP tool returned no structured content")
        return cast(Mapping[str, object], structured)

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None


def sanitize_arguments(arguments: Mapping[str, object]) -> dict[str, object]:
    """Copy tool arguments while removing any secret-shaped fields."""

    sanitized: dict[str, object] = {}
    for key, value in arguments.items():
        if any(
            token in key.lower() for token in ("key", "secret", "token", "password")
        ):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, Mapping):
            sanitized[key] = sanitize_arguments(cast(Mapping[str, object], value))
        elif isinstance(value, list):
            sanitized[key] = list(value)
        else:
            sanitized[key] = value
    return sanitized


def _normalize_records(response: Mapping[str, object]) -> tuple[ScholarlyRecord, ...]:
    raw_results = response.get("results")
    if not isinstance(raw_results, list):
        raise RuntimeError("OpenAlex MCP response has no results list")

    records: list[ScholarlyRecord] = []
    for raw in raw_results:
        if not isinstance(raw, Mapping):
            raise RuntimeError("OpenAlex MCP returned a non-object record")
        openalex_id = raw.get("id")
        title = raw.get("display_name")
        doi = raw.get("doi")
        publication_year = raw.get("publication_year")
        if not isinstance(openalex_id, str) or not openalex_id.startswith(
            "https://openalex.org/W"
        ):
            raise RuntimeError("OpenAlex MCP returned an invalid work ID")
        if not isinstance(title, str) or not title:
            raise RuntimeError("OpenAlex MCP returned a work without a title")
        records.append(
            ScholarlyRecord(
                openalex_id=openalex_id,
                doi=doi if isinstance(doi, str) else None,
                title=title,
                publication_year=(
                    publication_year if isinstance(publication_year, int) else None
                ),
            )
        )

    records.sort(key=lambda record: record.openalex_id)
    if len(records) != 2:
        raise RuntimeError(
            f"Expected exactly 2 OpenAlex works, received {len(records)}"
        )
    return tuple(records)


def _boundary_decision(call: McpToolCall) -> tuple[BoundaryDecision, str]:
    action = AgentAction(
        action_type=ActionType.MCP_TOOL_CALL,
        target=f"mcp:{call.server_id}/{call.tool_name}",
        metadata={"server_id": call.server_id, "tool_name": call.tool_name},
    )
    record = BoundaryEngine(RESEARCH_DATA_RULES).evaluate(
        f"research_data_{call.tool_name}", action
    )
    return record.decision, record.reason


async def execute_tool_intent(
    call: McpToolCall,
    transport: OpenAlexTransport,
) -> tuple[McpExecutionRecord, tuple[ScholarlyRecord, ...]]:
    """Decide first, and dispatch only when the boundary returns ALLOW."""

    decision, reason = _boundary_decision(call)
    sanitized = sanitize_arguments(call.arguments)
    if decision is not BoundaryDecision.ALLOW:
        return (
            McpExecutionRecord(
                server_id=call.server_id,
                tool_name=call.tool_name,
                sanitized_arguments=sanitized,
                dispatched=False,
                result_ids=(),
                error=None,
                boundary_decision=decision,
                reason=reason,
                result="BLOCKED_PRE_DISPATCH",
            ),
            (),
        )

    try:
        response = await transport.call_tool(call.tool_name, call.arguments)
        records = _normalize_records(response)
    except Exception as error:
        return (
            McpExecutionRecord(
                server_id=call.server_id,
                tool_name=call.tool_name,
                sanitized_arguments=sanitized,
                dispatched=True,
                result_ids=(),
                error=str(error),
                boundary_decision=decision,
                reason=reason,
                result="DISPATCH_ERROR",
            ),
            (),
        )

    return (
        McpExecutionRecord(
            server_id=call.server_id,
            tool_name=call.tool_name,
            sanitized_arguments=sanitized,
            dispatched=True,
            result_ids=tuple(record.openalex_id for record in records),
            error=None,
            boundary_decision=decision,
            reason=reason,
            result="RETURNED_2_RECORDS",
        ),
        records,
    )


async def run_research_data_workflow(
    transport: OpenAlexTransport,
    *,
    evidence_mode: str,
) -> ResearchDataResult:
    """Run one allowed search and one pre-dispatch denied intent."""

    await transport.start()
    try:
        if ALLOWED_TOOL not in transport.tool_names:
            raise RuntimeError(f"MCP tool not found: {ALLOWED_TOOL}")

        allowed_call = McpToolCall(
            server_id=OPENALEX_SERVER_ID,
            tool_name=ALLOWED_TOOL,
            arguments=SEARCH_ARGUMENTS,
        )
        allowed, records = await execute_tool_intent(allowed_call, transport)
        if allowed.error is not None:
            raise RuntimeError(allowed.error)

        calls_before_deny = transport.call_count
        denied_call = McpToolCall(
            server_id=OPENALEX_SERVER_ID,
            tool_name=DENIED_TOOL,
            arguments={
                "seed_id": records[0].openalex_id,
                "direction": "cites",
                "per_page": 2,
            },
        )
        denied, denied_records = await execute_tool_intent(denied_call, transport)
        denied_call_count = transport.call_count - calls_before_deny
        if denied_records or denied_call_count != 0:
            raise RuntimeError("Denied MCP intent reached the transport")

        provenance = ResearchDataProvenance(
            provider=OPENALEX_PROVIDER,
            openalex_ids=tuple(record.openalex_id for record in records),
            dois=tuple(record.doi for record in records if record.doi is not None),
            mcp_server=OPENALEX_SERVER_ID,
            mcp_tool=ALLOWED_TOOL,
            workflow_step="bounded_publication_search",
            output_id=OUTPUT_ID,
        )
        return ResearchDataResult(
            evidence_mode=evidence_mode,
            protocol_version=transport.protocol_version,
            records=records,
            allowed=allowed,
            denied=denied,
            audit_records=(allowed, denied),
            provenance=provenance,
            transport_call_count=transport.call_count,
            denied_transport_call_count=denied_call_count,
        )
    finally:
        await transport.close()
