"""Extract a label-free tool manifest through MCP tools/list only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.mcpguard_dynamic.upstream import (
    assert_rootless_user_namespace,
    load_upstream_module,
    verify_upstream,
)

FORBIDDEN_KEYS = {
    "attack_indicator",
    "case_id",
    "category",
    "expected_without_defense",
    "ground_truth",
}


def canonical_json_bytes(value: object) -> bytes:
    """Serialize a frozen artifact canonically."""

    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _assert_label_free(value: object) -> None:
    if isinstance(value, dict):
        overlap = FORBIDDEN_KEYS.intersection(value)
        if overlap:
            raise RuntimeError(
                f"Forbidden benchmark labels in tool manifest: {overlap}"
            )
        for nested in value.values():
            _assert_label_free(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_label_free(nested)


def extract_tool_manifest(upstream_root: Path) -> list[dict[str, object]]:
    """Query every pinned server using the unmodified C0 transport."""

    verify_upstream(upstream_root)
    assert_rootless_user_namespace()
    proxy_base = load_upstream_module(upstream_root, "proxy.proxy_base")
    entries: list[dict[str, object]] = []
    workspace_dir = str(upstream_root.resolve() / "workspace")

    for server_name in sorted(proxy_base.SERVER_SCRIPTS):
        proxy = proxy_base.MCPProxy(
            server_name=server_name,
            config="C0",
            workspace_dir=workspace_dir,
        )
        if proxy.active_layers:
            raise RuntimeError("Schema extraction inherited an MCPGuard defense")
        proxy.start_server()
        try:
            proxy._send_to_server(
                {"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}}
            )
            response: dict[str, Any] = proxy._read_from_server()
        finally:
            proxy.stop_server()

        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
            raise RuntimeError(f"Invalid tools/list response from {server_name}")
        for tool in result["tools"]:
            if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
                raise RuntimeError(f"Invalid tool entry from {server_name}")
            input_schema = tool.get("inputSchema", {})
            if not isinstance(input_schema, dict):
                raise RuntimeError(f"Invalid input schema from {server_name}")
            description = tool.get("description", "")
            if not isinstance(description, str):
                raise RuntimeError(f"Invalid tool description from {server_name}")
            entries.append(
                {
                    "description": description,
                    "input_schema": input_schema,
                    "server": server_name,
                    "tool": tool["name"],
                }
            )

    entries.sort(key=lambda entry: (str(entry["server"]), str(entry["tool"])))
    targets = {(entry["server"], entry["tool"]) for entry in entries}
    if len(targets) != len(entries):
        raise RuntimeError("Duplicate server/tool target in manifest")
    _assert_label_free(entries)
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = extract_tool_manifest(args.upstream_root)
    args.output.write_bytes(canonical_json_bytes(manifest))
    print(f"Wrote {len(manifest)} label-free tool entries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
