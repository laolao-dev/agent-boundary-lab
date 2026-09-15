"""Build and load the schema-only frozen ABL v0.1 policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from agent_boundary_lab.models import ActionType, BoundaryDecision, BoundaryRule
from benchmarks.mcpguard_dynamic.tool_manifest import canonical_json_bytes


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        flattened: list[str] = []
        for key, nested in value.items():
            flattened.append(str(key))
            flattened.extend(_flatten_strings(nested))
        return flattened
    if isinstance(value, list):
        flattened = []
        for nested in value:
            flattened.extend(_flatten_strings(nested))
        return flattened
    return []


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower().replace("_", " ")))


def _first_signal(text: str, signals: Sequence[str]) -> str | None:
    padded = f" {text} "
    for signal in signals:
        normalized = _normalize(signal)
        if f" {normalized} " in padded:
            return signal
    return None


def classify_tool(
    entry: Mapping[str, object], rubric: Mapping[str, object]
) -> tuple[BoundaryDecision, str, str | None]:
    """Apply only the pre-registered capability rubric; ignore server identity."""

    text = _normalize(
        " ".join(
            [
                str(entry["tool"]),
                str(entry.get("description", "")),
                *_flatten_strings(entry.get("input_schema", {})),
            ]
        )
    )
    ordered = (
        ("deny", BoundaryDecision.DENY),
        ("require_approval", BoundaryDecision.REQUIRE_APPROVAL),
        ("read_only_allow", BoundaryDecision.ALLOW),
    )
    for rubric_key, decision in ordered:
        section = cast(Mapping[str, object], rubric[rubric_key])
        signals = cast(Sequence[str], section["signals"])
        signal = _first_signal(text, signals)
        if signal is not None:
            return decision, rubric_key, signal
    return BoundaryDecision.REQUIRE_APPROVAL, "ambiguity_default", None


def build_policy(tool_manifest_path: Path, rubric_path: Path) -> dict[str, object]:
    manifest = _load_json(tool_manifest_path)
    rubric = _load_json(rubric_path)
    if not isinstance(manifest, list) or not isinstance(rubric, dict):
        raise TypeError("Invalid policy inputs")
    if rubric.get("arguments_used_for_decisions") is not False:
        raise RuntimeError("Rubric must prohibit argument-based decisions")

    rules: list[dict[str, object]] = []
    for index, raw_entry in enumerate(manifest, 1):
        if not isinstance(raw_entry, dict):
            raise TypeError("Tool manifest entries must be objects")
        entry = cast(dict[str, object], raw_entry)
        server = str(entry["server"])
        tool = str(entry["tool"])
        decision, rubric_rule, signal = classify_tool(entry, rubric)
        reason = f"Schema-only rubric: {rubric_rule}"
        if signal is not None:
            reason += f" (advertised capability signal: {signal})"
        rules.append(
            {
                "action_type": ActionType.MCP_TOOL_CALL.value,
                "classification": {
                    "rubric_rule": rubric_rule,
                    "signal": signal,
                },
                "decision": decision.value,
                "name": f"mcpguard_schema_rule_{index:03d}",
                "reason": reason,
                "target": f"mcp:{server}/{tool}",
            }
        )

    return {
        "arguments_used_for_decisions": False,
        "default_unmatched": BoundaryDecision.DENY.value,
        "policy_type": "ABL v0.1 exact MCP server/tool targets",
        "rules": rules,
        "source_rubric_sha256": sha256_file(rubric_path),
        "source_tool_manifest_sha256": sha256_file(tool_manifest_path),
        "version": "1.0.0",
    }


def load_boundary_rules(policy_path: Path) -> tuple[BoundaryRule, ...]:
    loaded = _load_json(policy_path)
    if (
        not isinstance(loaded, dict)
        or loaded.get("arguments_used_for_decisions") is not False
    ):
        raise RuntimeError("Invalid frozen policy manifest")
    raw_rules = loaded.get("rules")
    if not isinstance(raw_rules, list):
        raise RuntimeError("Frozen policy has no rules")
    rules: list[BoundaryRule] = []
    targets: set[str] = set()
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise RuntimeError("Invalid frozen policy rule")
        target = str(raw_rule["target"])
        if target in targets:
            raise RuntimeError(f"Duplicate frozen policy target: {target}")
        targets.add(target)
        rules.append(
            BoundaryRule(
                name=str(raw_rule["name"]),
                action_type=ActionType(str(raw_rule["action_type"])),
                target=target,
                decision=BoundaryDecision(str(raw_rule["decision"])),
                reason=str(raw_rule["reason"]),
            )
        )
    return tuple(rules)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-manifest", required=True, type=Path)
    parser.add_argument("--rubric", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    policy = build_policy(args.tool_manifest, args.rubric)
    args.output.write_bytes(canonical_json_bytes(policy))
    print(f"Wrote {len(cast(list[object], policy['rules']))} frozen rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
