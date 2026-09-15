"""Create the pre-result benchmark freeze manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from benchmarks.mcpguard_dynamic.policy import sha256_file
from benchmarks.mcpguard_dynamic.tool_manifest import canonical_json_bytes
from benchmarks.mcpguard_dynamic.upstream import MCPGUARD_COMMIT, MCPGUARD_TREE

ADAPTER_FILES = (
    "adapter.py",
    "conformance.py",
    "fixtures/conformance_server.py",
    "freeze.py",
    "policy.py",
    "runner.py",
    "tool_manifest.py",
    "upstream.py",
)


def adapter_working_hash(integration_dir: Path) -> tuple[str, dict[str, str]]:
    """Hash the executable integration surface without a Git self-reference."""

    digest = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for relative in ADAPTER_FILES:
        path = integration_dir / relative
        content = path.read_bytes()
        file_hashes[relative] = hashlib.sha256(content).hexdigest()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest(), file_hashes


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def build_freeze_manifest(repository: Path) -> dict[str, object]:
    integration_dir = repository / "benchmarks" / "mcpguard_dynamic"
    tool_path = integration_dir / "sanitized_tool_manifest.json"
    rubric_path = integration_dir / "policy_rubric.json"
    policy_path = integration_dir / "policy_manifest.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    counts = {decision: 0 for decision in ("ALLOW", "DENY", "REQUIRE_APPROVAL")}
    for rule in policy["rules"]:
        counts[rule["decision"]] += 1
    working_hash, file_hashes = adapter_working_hash(integration_dir)
    return {
        "abl_adapter_commit": None,
        "abl_adapter_working_sha256": working_hash,
        "abl_base_commit": _git(repository, "rev-parse", "main"),
        "adapter_files_sha256": file_hashes,
        "arguments_used_for_decisions": False,
        "decision_semantics": {
            "ALLOW": "exactly one upstream C0 tools/call dispatch",
            "DENY": "zero upstream tools/call dispatches",
            "REQUIRE_APPROVAL": (
                "zero dispatches because the benchmark has no real approval event"
            ),
            "unmatched": "DENY",
        },
        "environment": {
            "kernel": "6.18.33.2-microsoft-standard-WSL2",
            "node": "24.20.0",
            "python": "3.14.4",
            "ubuntu": "26.04.1 LTS",
            "wsl": "2.7.12.0",
        },
        "mcpguard_commit": MCPGUARD_COMMIT,
        "mcpguard_tree_sha": MCPGUARD_TREE,
        "official_c_abl_score_run_yet": False,
        "policy_counts": counts,
        "policy_frozen_before_results": True,
        "policy_manifest_sha256": sha256_file(policy_path),
        "policy_rubric_sha256": sha256_file(rubric_path),
        "rootless_namespace": {
            "wrapper": "unshare -Ur",
            "requirement": "namespace uid 0 maps to one non-root host uid",
            "stage_0_5_shadow_read_rc": 1,
        },
        "sanitized_tool_manifest_sha256": sha256_file(tool_path),
        "version": "1.0.0",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = build_freeze_manifest(args.repository.resolve())
    args.output.write_bytes(canonical_json_bytes(manifest))
    print(f"Wrote pre-result freeze manifest to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
