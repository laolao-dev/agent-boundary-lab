"""Execute the first blind C-ABL run after explicit post-freeze authorization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.mcpguard_dynamic.adapter import CABLAdapter
from benchmarks.mcpguard_dynamic.freeze import adapter_working_hash
from benchmarks.mcpguard_dynamic.policy import load_boundary_rules, sha256_file
from benchmarks.mcpguard_dynamic.upstream import (
    assert_rootless_user_namespace,
    load_upstream_module,
    verify_upstream,
)

FREEZE_FILES = {
    "policy_rubric_sha256": "policy_rubric.json",
    "policy_manifest_sha256": "policy_manifest.json",
    "sanitized_tool_manifest_sha256": "sanitized_tool_manifest.json",
}


def verify_freeze(integration_dir: Path) -> dict[str, object]:
    manifest_path = integration_dir / "benchmark_manifest.json"
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("Invalid benchmark freeze manifest")
    for field, filename in FREEZE_FILES.items():
        if loaded.get(field) != sha256_file(integration_dir / filename):
            raise RuntimeError(f"Frozen artifact hash mismatch: {filename}")
    if loaded.get("official_c_abl_score_run_yet") is not False:
        raise RuntimeError("Freeze manifest does not predate the first score run")
    if loaded.get("arguments_used_for_decisions") is not False:
        raise RuntimeError("Freeze manifest permits argument-based decisions")
    working_hash, file_hashes = adapter_working_hash(integration_dir)
    if loaded.get("abl_adapter_working_sha256") != working_hash:
        raise RuntimeError("Frozen adapter working hash mismatch")
    if loaded.get("adapter_files_sha256") != file_hashes:
        raise RuntimeError("Frozen adapter file hashes mismatch")
    return loaded


def run_first_blind_benchmark(
    *, upstream_root: Path, run_id: str, integration_dir: Path
) -> None:
    """Reuse upstream cases/verifier/scoring path without modifying upstream."""

    verify_upstream(upstream_root)
    assert_rootless_user_namespace()
    verify_freeze(integration_dir)
    rules = load_boundary_rules(integration_dir / "policy_manifest.json")
    proxy_base = load_upstream_module(upstream_root, "proxy.proxy_base")
    evaluate = load_upstream_module(upstream_root, "runner.evaluate")
    audit_path = upstream_root / "results" / "C-ABL" / f"{run_id}.audit.jsonl"

    class FrozenCABLProxy:
        active_layers: tuple[()] = ()

        def __init__(
            self,
            server_name: str,
            config: str,
            workspace_dir: str,
            **_unused: Any,
        ) -> None:
            if config != "C-ABL":
                raise RuntimeError("Frozen adapter accepts only C-ABL")
            c0_transport = proxy_base.MCPProxy(
                server_name=server_name,
                config="C0",
                workspace_dir=workspace_dir,
            )
            self._adapter = CABLAdapter(
                server_name=server_name,
                c0_transport=c0_transport,
                rules=rules,
                audit_log_path=audit_path,
            )

        def __enter__(self) -> FrozenCABLProxy:
            self._adapter.start_server()
            return self

        def __exit__(self, *_exc: object) -> None:
            self._adapter.stop_server()

        def call_tool(
            self, tool_name: str, arguments: dict[str, Any]
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            return self._adapter.call_tool(tool_name, arguments)

    setattr(evaluate, "MCPProxy", FrozenCABLProxy)
    evaluate.run_evaluation(config="C-ABL", run_id=run_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--execute-first-blind-run",
        action="store_true",
        help="Required acknowledgement; Stage 1 must not pass this flag.",
    )
    args = parser.parse_args(argv)
    if not args.execute_first_blind_run:
        raise SystemExit("Refusing score run without --execute-first-blind-run")
    integration_dir = Path(__file__).resolve().parent
    run_first_blind_benchmark(
        upstream_root=args.upstream_root.resolve(),
        run_id=args.run_id,
        integration_dir=integration_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
