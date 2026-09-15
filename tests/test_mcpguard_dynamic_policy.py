from __future__ import annotations

import inspect
import json
from collections import Counter
from pathlib import Path

from benchmarks.mcpguard_dynamic.adapter import CABLAdapter
from benchmarks.mcpguard_dynamic.policy import (
    build_policy,
    classify_tool,
    load_boundary_rules,
    sha256_file,
)
from benchmarks.mcpguard_dynamic.runner import verify_freeze

from agent_boundary_lab.models import BoundaryDecision

INTEGRATION_DIR = Path(__file__).parents[1] / "benchmarks" / "mcpguard_dynamic"


def _json(name: str):  # type annotation is intentionally inferred from JSON
    return json.loads((INTEGRATION_DIR / name).read_text(encoding="utf-8"))


def test_sanitized_manifest_has_only_allowed_fields_and_unique_targets() -> None:
    manifest = _json("sanitized_tool_manifest.json")
    assert len(manifest) == 44
    assert all(
        set(entry) == {"server", "tool", "description", "input_schema"}
        for entry in manifest
    )
    assert len({(entry["server"], entry["tool"]) for entry in manifest}) == 44
    serialized = json.dumps(manifest)
    for forbidden in (
        "case_id",
        "category",
        "attack_indicator",
        "expected_without_defense",
        "ground_truth",
    ):
        assert f'"{forbidden}"' not in serialized


def test_checked_in_policy_is_reproducible_from_frozen_inputs() -> None:
    expected = build_policy(
        INTEGRATION_DIR / "sanitized_tool_manifest.json",
        INTEGRATION_DIR / "policy_rubric.json",
    )
    assert expected == _json("policy_manifest.json")


def test_policy_counts_and_exact_targets_are_frozen() -> None:
    policy = _json("policy_manifest.json")
    counts = Counter(rule["decision"] for rule in policy["rules"])
    assert counts == {"ALLOW": 30, "REQUIRE_APPROVAL": 14}
    rules = load_boundary_rules(INTEGRATION_DIR / "policy_manifest.json")
    assert len(rules) == 44
    assert len({rule.target for rule in rules}) == 44


def test_server_name_has_no_effect_on_classification() -> None:
    rubric = _json("policy_rubric.json")
    common = {
        "tool": "read_public_record",
        "description": "Read a public record",
        "input_schema": {"type": "object"},
    }
    ordinary = {**common, "server": "ordinary_server"}
    label_like = {**common, "server": "malicious_trojan_attack_server"}
    assert classify_tool(ordinary, rubric) == classify_tool(label_like, rubric)
    assert classify_tool(ordinary, rubric)[0] is BoundaryDecision.ALLOW


def test_adapter_decision_surface_has_no_case_or_argument_input() -> None:
    source = inspect.getsource(CABLAdapter.call_tool)
    assert "case_id" not in source
    assert "ground_truth" not in source
    assert "attack_indicator" not in source
    assert "payload=None" in source


def test_freeze_hashes_match_current_artifacts() -> None:
    manifest = verify_freeze(INTEGRATION_DIR)
    assert manifest["policy_frozen_before_results"] is True
    assert manifest["official_c_abl_score_run_yet"] is False
    assert manifest["policy_manifest_sha256"] == sha256_file(
        INTEGRATION_DIR / "policy_manifest.json"
    )
