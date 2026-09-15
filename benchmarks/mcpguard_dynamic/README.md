# MCPGuard-Dynamic C-ABL integration

This directory contains the pre-registered ABL v0.1 integration for
MCPGuard-Dynamic commit `f36a2f593cb7fbc4cbf3a8a6770ed28426371b68`.
It is benchmark tooling, not a change to the ABL product core.

## Frozen claim

C-ABL maps every invocation to `ActionType.MCP_TOOL_CALL` with the exact target
`mcp:<server>/<tool>`. The frozen v0.1 `BoundaryEngine` decides from that target
only. Arguments are not passed to the engine and response content is never
inspected. ABL v0.1 is therefore tool-target-level only.

`ALLOW` performs exactly one call through an unmodified MCPGuard `C0` proxy.
`DENY` and `REQUIRE_APPROVAL` perform zero calls; approval cannot dispatch because
the benchmark has no real approval event. An unmatched target fails closed.

The adapter is composed over `MCPProxy(config="C0")`. It is not entered into
MCPGuard's `CONFIG_LAYERS`, so it does not activate MCPGuard L1, L2, AgentBound,
eBPF, environment filtering, or response sanitization.

## Blinded policy preparation

The policy rubric was written before tool extraction. The extractor queried only
the public `tools/list` interface of the 14 pinned servers and retained only
`server`, `tool`, `description`, and `input_schema`. It did not read benchmark
cases, labels, ground truth, verifier results, or scores.

The policy builder excludes the server name from classification text. Label-like
server-name tokens are retained only because the exact dispatch target requires
the real server identifier. The generic rubric is ordered as follows:

1. `DENY` if the advertised capability inherently requires secrets, credentials,
   authentication material, or privilege elevation.
2. `REQUIRE_APPROVAL` for write/delete/execute/network/state-changing capability.
3. `ALLOW` for clearly read-only, side-effect-free capability.
4. `REQUIRE_APPROVAL` when ambiguous.

Arguments and benchmark outcomes cannot alter a decision. The policy must not be
edited after `benchmark_manifest.json` is created.

## Stage 1 validation only

The attack-case-free rootless integration check is:

```console
PYTHONPATH="$PWD:$PWD/src" python3 -m benchmarks.mcpguard_dynamic.conformance \
  --upstream-root /path/to/pinned/mcpguard-dynamic
```

Run it inside the Stage 0.5 `unshare -Ur` environment. The normal ABL validation
gate remains:

```console
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
git diff --check
```

Do not run `runner.py` during Stage 1. It requires the explicit
`--execute-first-blind-run` acknowledgement, validates the rootless namespace and
all frozen hashes, and then reuses upstream `run_evaluation` and `AttackVerifier`
without modifying upstream files.
