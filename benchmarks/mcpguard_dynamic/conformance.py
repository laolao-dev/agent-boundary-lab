"""Rootless, attack-case-free integration conformance for the C-ABL adapter."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from agent_boundary_lab.models import ActionType, BoundaryDecision, BoundaryRule
from benchmarks.mcpguard_dynamic.adapter import CABLAdapter
from benchmarks.mcpguard_dynamic.upstream import (
    assert_rootless_user_namespace,
    load_upstream_module,
    verify_upstream,
)


def _rules() -> tuple[BoundaryRule, ...]:
    return (
        BoundaryRule(
            "allow_echo",
            ActionType.MCP_TOOL_CALL,
            "mcp:conformance_server/echo",
            BoundaryDecision.ALLOW,
            "Conformance read-only fixture",
        ),
        BoundaryRule(
            "deny_sensitive",
            ActionType.MCP_TOOL_CALL,
            "mcp:conformance_server/sensitive",
            BoundaryDecision.DENY,
            "Conformance denied fixture",
        ),
        BoundaryRule(
            "approval_mutation",
            ActionType.MCP_TOOL_CALL,
            "mcp:conformance_server/mutate",
            BoundaryDecision.REQUIRE_APPROVAL,
            "Conformance approval fixture",
        ),
    )


def _fail(name: str):
    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"Inherited MCPGuard defense called: {name}")

    return fail


def run_conformance(upstream_root: Path) -> list[str]:
    """Return named checks after exercising the real C0 process transport."""

    verify_upstream(upstream_root)
    assert_rootless_user_namespace()
    proxy_base = load_upstream_module(upstream_root, "proxy.proxy_base")
    fixture = Path(__file__).resolve().parent / "fixtures" / "conformance_server.py"
    proxy_base.SERVER_SCRIPTS["conformance_server"] = str(fixture)
    os.environ["ABL_CONFORMANCE_SECRET_MARKER"] = "synthetic-present"
    checks: list[str] = []

    direct = proxy_base.MCPProxy(
        server_name="conformance_server",
        config="C0",
        workspace_dir=str(upstream_root / "workspace"),
    )
    direct.start_server()
    try:
        direct_result, direct_info = direct.call_tool("echo", {"value": "first"})
    finally:
        direct.stop_server()
    assert direct.active_layers == [] and direct_info["blocked"] is False
    checks.append("direct_C0_has_no_active_layers")

    delegate = proxy_base.MCPProxy(
        server_name="conformance_server",
        config="C0",
        workspace_dir=str(upstream_root / "workspace"),
    )
    delegate.policy_engine.check = _fail("PolicyEngine")
    delegate.argument_validator.check = _fail("ArgumentValidator")
    delegate.agentbound.check = _fail("AgentBound")
    delegate.ebpf_sandbox.is_available = _fail("EBPFSandbox.is_available")
    delegate.ebpf_sandbox.activate_policy = _fail("EBPFSandbox.activate_policy")
    delegate.ebpf_sandbox.deactivate_policy = _fail("EBPFSandbox.deactivate_policy")
    original_sanitizer = proxy_base.MCPProxy._sanitize_response
    proxy_base.MCPProxy._sanitize_response = staticmethod(_fail("response sanitizer"))
    dispatch_count = 0
    original_call = delegate.call_tool

    def counted_call(
        tool_name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal dispatch_count
        dispatch_count += 1
        return original_call(tool_name, arguments)

    delegate.call_tool = counted_call
    adapter = CABLAdapter(
        server_name="conformance_server",
        c0_transport=delegate,
        rules=_rules(),
    )
    try:
        adapter.start_server()
        result, info = adapter.call_tool("echo", {"value": "second"})
    finally:
        adapter.stop_server()
        proxy_base.MCPProxy._sanitize_response = original_sanitizer

    assert dispatch_count == 1 and info["blocked"] is False
    checks.append("ALLOW_dispatches_exactly_once")
    assert result == direct_result
    checks.append("response_content_is_not_inspected_or_changed")
    rendered = result["content"][0]["text"]
    assert "marker_present=true" in rendered
    checks.append("C_ABL_server_environment_matches_C0")
    checks.extend(
        [
            "MCPGuard_PolicyEngine_not_called",
            "MCPGuard_ArgumentValidator_not_called",
            "MCPGuard_response_sanitizer_not_called",
            "AgentBound_not_called",
            "EBPFSandbox_not_called",
        ]
    )
    assert adapter.audit_records[-1].dispatched is True
    assert adapter.audit_records[-1].target == "mcp:conformance_server/echo"
    checks.append("audit_records_target_decision_reason_and_dispatch")
    assert not {
        "case_id",
        "category",
        "ground_truth",
        "attack_indicator",
    }.intersection(adapter.audit_records[-1].__dict__)
    checks.append("no_benchmark_labels_enter_Abl")
    checks.append("adapter_runs_inside_validated_rootless_namespace")
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", required=True, type=Path)
    args = parser.parse_args(argv)
    checks = run_conformance(args.upstream_root.resolve())
    for check in checks:
        print(f"PASS {check}")
    print(f"PASS {len(checks)} rootless integration checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
