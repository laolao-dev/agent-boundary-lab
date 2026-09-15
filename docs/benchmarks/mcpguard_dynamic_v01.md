# Agent Boundary Lab v0.1: First Blind Evaluation on an External Benchmark

**Status:** Public technical report

**Evidence run:** `first_blind_attempt_03`

**Scope:** One frozen benchmark and its same-session baselines; not a
production-security certification

## Executive result

This report documents the first blind evaluation of C-ABL v0.1 on the externally
authored MCPGuard-Dynamic benchmark. The Agent Boundary Lab project executed the
evaluation itself. “External” describes the benchmark's source; it does not mean
that the benchmark authors, Meta, a third-party laboratory, or an independent
auditor performed, certified, or endorsed the evaluation or its result.

In the frozen benchmark, C-ABL v0.1 prevented 34 of 61 attack cases (Raw APR
55.7%) and 21 of the 48 attacks shown to be viable under C0 (V-APR 43.8%). It
allowed 13 of 21 benign cases to complete (benign success 61.9%) and blocked 8
benign cases (FPR 38.1%).

C-ABL v0.1 achieved higher viable-attack prevention than the app-level baselines
in this frozen benchmark, but at a substantial false-positive / utility cost.
**This is a security–utility tradeoff, not a superiority result.** The result
supports only the tested configuration, cases, and execution conditions.

## Methodology

The ABL project executed the evaluation using MCPGuard-Dynamic pinned at commit
`f36a2f593cb7fbc4cbf3a8a6770ed28426371b68` (tree
`ee0acc5993c1363391efab169c04c7d02f203378`). The clean public lineage baseline
for this packaging is ABL commit
`d9c381d13500b1f69efc404eab6792e0e4f5f7e7`; the evaluated ABL integration source
is identified at tree level by
`c6cfff8f97cf1a35901740e4803c814371443174`.

All four configurations—C0, C-AB, C-app, and C-ABL—completed the same ordered set
of 82 cases in one persistent rootless session: 61 attack cases and 21 benign
cases. Raw APR is the fraction of all 61 attacks prevented. V-APR uses the 48
attacks that succeeded under same-session C0 as its viability denominator. FPR
is the fraction of 21 benign cases blocked; benign success is its observed
complement.

C-ABL mapped each invocation to `MCP_TOOL_CALL` with an exact
`mcp:<server>/<tool>` target. The frozen v0.1 engine decided from that target
only. `ALLOW` dispatched exactly once through an unmodified C0 proxy. `DENY`,
unmatched fail-closed decisions, and `REQUIRE_APPROVAL` dispatched zero calls
under the benchmark semantics. C-ABL was composed over C0 and did not activate
the benchmark's other configuration layers.

## Frozen setup and integrity controls

The generic policy rubric was written before tool extraction. Policy
construction used only the public `tools/list` surface of 14 pinned servers and
retained `server`, `tool`, `description`, and `input_schema`. The server name was
needed to form an exact target but was excluded from classification text.
Arguments, case IDs, categories, attack indicators, ground truth, verifier
output, and results were excluded from policy decisions.

The policy and integration artifacts were sealed before the first score-bearing
execution. Attempts 01 and 02 executed zero C-ABL cases and were not
score-bearing. Attempt 03 completed all 82 C-ABL cases. There was no score retry
or tuning, and neither policy nor adapter changed after the score.

The checked-in publication copy of `benchmark_manifest.json` translates only
its ABL base-commit pointer to the corresponding clean public commit named
above. The two commits have the same source tree. Executable integration files,
the frozen policy/rubric/tool manifests, their hashes, and all benchmark
semantics are unchanged. The frozen benchmark-manifest SHA-256 below identifies
the sealed evaluation original, not this identity-sanitized publication copy.
The retained `official_c_abl_score_run_yet: false` value records the pre-score
freeze state of the manifest; it is not a claim that no score-bearing evaluation
exists at publication time.

- Every configuration used the same benchmark commit, case set, case order,
  viability definition, and persistent rootless namespace.
- The benchmark's evaluator and attack verifier were reused without upstream
  source modification.
- Every configuration produced 82 raw results; the C-ABL audit has 82 records.
- All worktrees began pristine; tracked source remained clean after execution.
- Frozen hashes were checked before and after scoring.
- Policy construction was blind to cases, labels, verifier output, and scores.

## Results

| Configuration | Raw APR | Viable attacks prevented | V-APR | Benign success | FPR |
| --- | ---: | ---: | ---: | ---: | ---: |
| C0 | 13/61 (21.3%) | 0/48 | 0.0% | 21/21 (100.0%) | 0/21 (0.0%) |
| C-AB | 23/61 (37.7%) | 10/48 | 20.8% | 21/21 (100.0%) | 0/21 (0.0%) |
| C-app | 25/61 (41.0%) | 12/48 | 25.0% | 21/21 (100.0%) | 0/21 (0.0%) |
| **C-ABL v0.1** | **34/61 (55.7%)** | **21/48** | **43.8%** | **13/21 (61.9%)** | **8/21 (38.1%)** |

Latency is excluded from comparative claims: blocked and dispatched paths
differ, so recorded timings are descriptive benchmark latency rather than
isolated policy overhead.

## Category results

| Attack category | Raw prevention | Viable prevention | Viable false negatives |
| --- | ---: | ---: | ---: |
| File Read | 8/15 (53.3%) | 2/9 (22.2%) | 7 |
| Exfiltration | 6/11 (54.5%) | 5/10 (50.0%) | 5 |
| Env Leak | 3/9 (33.3%) | 3/9 (33.3%) | 6 |
| Sandbox Escape | 6/10 (60.0%) | 4/8 (50.0%) | 4 |
| Privilege Escalation | 7/10 (70.0%) | 6/9 (66.7%) | 3 |
| Cross-Language | 4/6 (66.7%) | 1/3 (33.3%) | 2 |
| **Total** | **34/61 (55.7%)** | **21/48 (43.8%)** | **27** |

These are descriptive slices with small, unequal denominators.

## Security–utility interpretation

C-ABL prevented 21 attacks viable under C0 and withheld dispatch for 8 benign
cases. Relative to the same-session app-level baselines, the gain therefore came
with a 38.1% FPR and benign success of 61.9%. The benchmark does not establish a
universal ordering, performance on untested attacks, or operational suitability.
**This is a security–utility tradeoff, not a superiority result.**

All 8 benign false positives were `REQUIRE_APPROVAL` decisions. The benchmark
contains no real human approval event, so its defined semantics treat
`REQUIRE_APPROVAL` as non-dispatch. This explains the mechanism; it does not
erase or reclassify the false positives. FPR remains 38.1%.

Across all 82 cases, C-ABL produced 49 `ALLOW`, 0 explicit `DENY`, and 33
`REQUIRE_APPROVAL` decisions. The 33 approval-gated cases—25 attacks and 8 benign
cases—were blocked before dispatch.

## Limitation analysis

The 27 viable attacks not prevented by C-ABL were all dispatched after a
tool-level `ALLOW`. The multi-label classification records 26 involving hidden
implementation behavior, 1 involving argument-dependent behavior, and 5
involving response-dependent behavior; these overlap.

The result exposes four limits of the frozen decision surface:

1. Advertised tool identity and schema do not reveal hidden server behavior.
2. Invocation arguments were not passed to the v0.1 policy engine.
3. Returned content was not inspected or sanitized.
4. One decision attached to each exact server/tool target and did not vary with
   invocation context.

These are limitations, not case-specific remediation claims. The benchmark
does not validate provenance, a complete human approval workflow, or the full
future research-agent workflow-assurance system.

## Reproducibility identifiers and hashes

| Source item | Identifier |
| --- | --- |
| ABL clean public lineage baseline commit | `d9c381d13500b1f69efc404eab6792e0e4f5f7e7` |
| ABL preserved evaluated-source tree | `c6cfff8f97cf1a35901740e4803c814371443174` |
| MCPGuard-Dynamic commit | `f36a2f593cb7fbc4cbf3a8a6770ed28426371b68` |
| MCPGuard-Dynamic tree | `ee0acc5993c1363391efab169c04c7d02f203378` |

| Frozen item | SHA-256 |
| --- | --- |
| Adapter working set | `b9abd0dc52da2553113dadfaab2050c8b992b5d7b5b8f807c58cb9b2844d92ca` |
| Benchmark manifest (public clean-history copy) | `496d95650ecbb551728a8eabdffdb5ad10e9dde1e32ff5bb7803de130e1e8ad4` |
| Benchmark manifest (sealed evaluation original) | `45d7ba23a0edff8932d0ebadb755f7faf9bfe76d1d6401062a44e9234da6dc4c` |
| Policy manifest | `c65f2edbb1b2721810f274f1afc24f163a0c606d29bbb02389519d813c41f0bb` |
| Policy rubric | `e1182dac59151d2787e3de445eb85c852980fd249d7f51dda12008ea23485f7c` |
| Sanitized tool manifest | `7b4d4bca733e8edb314c6dc30fd795cf8e7b06fe11732373eb58a444dca41d71` |

The complete sealed raw-artifact hashes are recorded in the public evidence
bundle. Files containing sanitized machine-local paths have different public
hashes, mapped without exposing the removed values in
`SANITIZATION_MANIFEST.json`.

## Clean-history and evidence disclosure

> The public repository history was identity-sanitized after the evaluation.
> The source tree used for the evaluation is byte-for-byte identical to the
> corresponding clean-history tree; only Git author, committer, and tagger
> identity metadata changed.

The statement is tree-level: evaluated source bytes are anchored by the
preserved ABL tree above. It does not claim that Git commit objects remain
byte-identical, because identity metadata is part of a commit object.

The [public evidence directory](../../benchmarks/mcpguard_dynamic/public_evidence/)
contains clearly labelled copies. Sealed originals remain private and unchanged.
Only machine-local identity/path metadata was sanitized; scores, counts, case
IDs, decisions, classifications, methodology, false positives, false negatives,
and benchmark semantics were not changed.
