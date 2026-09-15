"""Read-only helpers for the pinned MCPGuard-Dynamic checkout."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

MCPGUARD_COMMIT = "f36a2f593cb7fbc4cbf3a8a6770ed28426371b68"
MCPGUARD_TREE = "ee0acc5993c1363391efab169c04c7d02f203378"


def _git(upstream_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(upstream_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_upstream(upstream_root: Path) -> None:
    """Require the exact clean upstream tree selected before Stage 1."""

    root = upstream_root.resolve()
    if _git(root, "rev-parse", "HEAD") != MCPGUARD_COMMIT:
        raise RuntimeError("MCPGuard commit does not match the frozen commit")
    if _git(root, "rev-parse", "HEAD^{tree}") != MCPGUARD_TREE:
        raise RuntimeError("MCPGuard tree does not match the frozen tree")
    if _git(root, "status", "--short"):
        raise RuntimeError("MCPGuard working tree is not clean")
    if _git(root, "diff", "--"):
        raise RuntimeError("MCPGuard tracked files have modifications")


def load_upstream_module(upstream_root: Path, module_name: str) -> ModuleType:
    """Import a module from the verified checkout without editing upstream."""

    root = str(upstream_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module(module_name)


def assert_rootless_user_namespace() -> None:
    """Require uid 0 mapped to exactly one non-root host uid."""

    getuid = getattr(os, "getuid", None)
    if getuid is None or getuid() != 0:
        raise RuntimeError("C-ABL must run as uid 0 inside a rootless user namespace")
    fields = Path("/proc/self/uid_map").read_text(encoding="utf-8").split()
    if len(fields) != 3:
        raise RuntimeError("Unexpected rootless uid map")
    namespace_uid, host_uid, length = (int(field) for field in fields)
    if namespace_uid != 0 or host_uid == 0 or length != 1:
        raise RuntimeError("Namespace uid 0 is not isolated from host root")
