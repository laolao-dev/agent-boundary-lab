"""Pre-dispatch ABL adapter composed over MCPGuard's pure C0 transport."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from agent_boundary_lab.engine import BoundaryEngine
from agent_boundary_lab.models import (
    ActionType,
    AgentAction,
    BoundaryDecision,
    BoundaryRule,
)


class C0Transport(Protocol):
    """The unmodified MCPGuard C0 proxy surface used by this adapter."""

    config: str

    @property
    def active_layers(self) -> Sequence[str]: ...

    def start_server(self) -> None: ...

    def stop_server(self) -> None: ...

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]: ...


@dataclass(frozen=True)
class CABLAuditRecord:
    """A label-free record of one boundary decision and dispatch outcome."""

    action_type: str
    argument_keys: tuple[str, ...]
    decision: str
    dispatched: bool
    reason: str
    server_name: str
    target: str
    tool_name: str


def _blocked_result(decision: BoundaryDecision) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": f"Blocked pre-dispatch by ABL boundary: {decision.value}",
            }
        ],
        "isError": True,
    }


class CABLAdapter:
    """Apply frozen ABL rules before a single possible C0 tools/call dispatch."""

    def __init__(
        self,
        *,
        server_name: str,
        c0_transport: C0Transport,
        rules: Sequence[BoundaryRule],
        audit_log_path: Path | None = None,
    ) -> None:
        if c0_transport.config != "C0" or tuple(c0_transport.active_layers):
            raise RuntimeError("C-ABL transport must have pure C0 semantics")
        self.server_name = server_name
        self._transport = c0_transport
        self._engine = BoundaryEngine(rules)
        self._audit_log_path = audit_log_path
        self.audit_records: list[CABLAuditRecord] = []

    @property
    def active_layers(self) -> tuple[()]:
        """Expose an empty set so MCPGuard defenses cannot be inferred or enabled."""

        return ()

    def __enter__(self) -> CABLAdapter:
        self.start_server()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop_server()

    def start_server(self) -> None:
        self._assert_c0_transport()
        self._transport.start_server()

    def stop_server(self) -> None:
        self._transport.stop_server()

    def _assert_c0_transport(self) -> None:
        if self._transport.config != "C0" or tuple(self._transport.active_layers):
            raise RuntimeError("MCPGuard defenses became active in C-ABL transport")

    def _audit(self, record: CABLAuditRecord) -> None:
        self.audit_records.append(record)
        if self._audit_log_path is None:
            return
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Decide from the exact target only, then dispatch at most once."""

        self._assert_c0_transport()
        start = time.monotonic()
        target = f"mcp:{self.server_name}/{tool_name}"
        action = AgentAction(
            action_type=ActionType.MCP_TOOL_CALL,
            target=target,
            payload=None,
            metadata={"server_name": self.server_name, "tool_name": tool_name},
        )
        execution = self._engine.evaluate("mcpguard_dynamic_pre_dispatch", action)
        dispatched = execution.decision is BoundaryDecision.ALLOW

        audit = CABLAuditRecord(
            action_type=action.action_type.value,
            argument_keys=tuple(sorted(arguments)),
            decision=execution.decision.value,
            dispatched=dispatched,
            reason=execution.reason,
            server_name=self.server_name,
            target=target,
            tool_name=tool_name,
        )

        if not dispatched:
            latency_ms = (time.monotonic() - start) * 1000
            self._audit(audit)
            return _blocked_result(execution.decision), {
                "blocked": True,
                "layer": "C-ABL-boundary",
                "reason": execution.reason,
                "latency_ms": latency_ms,
            }

        try:
            result, defense_info = self._transport.call_tool(tool_name, arguments)
        except BaseException:
            self._audit(audit)
            raise
        if defense_info.get("blocked") or defense_info.get("layer") is not None:
            raise RuntimeError("Pure C0 transport reported an inherited defense")
        self._audit(audit)
        returned_info = dict(defense_info)
        returned_info.update(
            {
                "blocked": False,
                "layer": None,
                "reason": execution.reason,
                "latency_ms": (time.monotonic() - start) * 1000,
            }
        )
        return result, returned_info
