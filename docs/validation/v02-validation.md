# ABL v0.2 Validation Evidence

This document summarizes frozen, bounded evaluations that the **Agent Boundary
Lab (ABL) project performed itself** against two externally authored workflow
projects, two public trajectory releases, and ABL-owned synthetic cases.
“External” identifies the source project or corpus; its authors did not perform,
certify, or endorse these ABL evaluations. The results describe the tested ABL
schema and verifier revisions, not the quality or security of those projects.
No third-party trace body, raw trajectory, report body, or copied source code is
included here or in [the aggregate JSON](v02-results.json).

## 1. Scope

The studies probe workflow schema fit, provenance false-PASS resistance,
assurance-status semantics, cross-corpus parsing/representation, and deterministic
verifier behavior on the frozen inputs below. The historical schema-fit studies
tested earlier development schemas; their decisions are not new scores for the
current `0.2.0a1` package. The initial BrowseComp-Plus result also predates the
source-grounding fix; the retests and later exams use the fixed semantics.

These tests do **not** verify source truth, answer factual correctness,
source-to-claim semantic entailment, causal correctness of reasoning, universal
research-agent compatibility, production security, compliance, or independent
third-party certification. A recorded source path is only identifier-level
grounding. The current checks cannot establish that a cited source supports the
prose of a claim.

## 2. External schema-fit studies

**Study 01 — [deep-research-agent](https://github.com/Xrrr1111/deep-research-agent/commit/1741dc85b6ee69058a8b748a94190d6b547b86f7)**,
pinned at `1741dc85b6ee69058a8b748a94190d6b547b86f7`. ABL inspected the
project's research-state, trace, evidence, and claim structures and ran its
native deterministic offline loop with mock search, fetch, and extraction. The
resulting 11-event trace showed research control flow and citation lineage, but
no ABL governance decision or approval requirement. Under the **pre-revision**
ABL schema, a clean mapping would have required inventing a governance decision
or converting missing approval context into `false`. The frozen decision was
`C — SCHEMA_REVISION_REQUIRED`. It motivated separating observed facts from
optional Assurance Context and representing absent approval requirements as
`UNKNOWN`. This was a schema-fit judgment, not a security assessment of the
external agent.

**Study 02 — [OpenResearchGraph](https://github.com/wjarchy/OpenResearchGraph/commit/f8ad69ebb15607590e3ee4c79b85db87d55389d6)**,
pinned at `f8ad69ebb15607590e3ee4c79b85db87d55389d6`. ABL studied an
unrelated, deterministic offline LangGraph workflow with six roles and a
33-event persisted SQLite trace. The revised fact/context schema accepted an
honest projection without inventing governance or approval facts; the frozen
decision was `B — FIT_WITH_ADAPTER`, with documented structural loss. Across the
two architectures, three representational gaps recurred: event hierarchy,
structured source identity, and first-class artifacts. The cross-study decision
was `CROSS_STUDY_SCHEMA_DECISION=REVISION_JUSTIFIED`. These observations led to
optional `ObservedEvent.parent_event_id`, `SourceRecord`, `WorkflowArtifact`, and
plural `source_refs`. The current schema still does not claim lossless adapters
for either project. Neither project endorsed ABL.

## 3. BrowseComp-Plus false-PASS discovery and fix

ABL examined a deterministic 20-case sample from the public
[BrowseComp-Plus](https://github.com/texttron/BrowseComp-Plus/commit/046949032b0328319cc9a02663a759ec601d9402)
trajectory release. The benchmark repository was pinned at
`046949032b0328319cc9a02663a759ec601d9402`; the official
[run-data repository](https://huggingface.co/datasets/Tevatron/browsecomp-plus-runs/tree/3c2b136c6382d2f7d43587bbc0a77f68b024c339)
was pinned at `3c2b136c6382d2f7d43587bbc0a77f68b024c339`. The sampled run
was labeled `gpt5` with the `qwen3-embed-8b` retriever. This is one run and one
frozen sample, not a cross-model accuracy study.

The **initial** verifier returned `PROVENANCE=PASS` in **20/20** sampled cases.
Manual review confirmed **20/20 false PASS** for that check: each mapped final
output lacked a recorded link to supporting sources. No overall false
`COMPLETE` occurred because other checks were incomplete. The root cause was
using artifact-to-producing-event linkage as if execution origin established
research grounding. It does not.

The general fix requires every Claim and explicitly marked `FINAL_OUTPUT`
artifact to reach a `SourceRecord` through recorded evidence, source, or parent
artifact lineage. `produced_by_event` alone is insufficient. The original frozen
20 cases were retested without changing their raw trajectories or source/evidence
links: **20 `PROVENANCE=PARTIAL`, 0 confirmed false PASS, 0 false COMPLETE**.
A separately frozen, unseen deterministic 20-case holdout from the same run
likewise yielded **20 `PROVENANCE=PARTIAL`, 0 confirmed false PASS, 0 false
COMPLETE**. The rule was not tuned per case. This is evidence about recorded
lineage on 40 bounded cases, not proof that provenance is solved or that the
source agents had a real security defect.

## 4. Frozen adversarial assurance exam

ABL ran one pre-registered synthetic/metamorphic exam with **60 total cases**:
48 adversarial cases (46 parser-valid and 2 expected parser rejections) plus 12
valid controls. Unexpected parser rejections: **0**. Of the cases, 58 matched
the frozen oracle; the remaining 2 were the expected parser rejections.
Confirmed false PASS, false COMPLETE, and false non-PASS were **0** in this case
set. The oracle was frozen before verifier execution; its SHA-256 is
`2228279bfc74b64b49cf33bb51dbc32ec4339c94c1efd1a3397898ef6c4d6c03`.

A mixed case with one source-grounded and one ungrounded `FINAL_OUTPUT` correctly
returned `PROVENANCE=PARTIAL` and `INCOMPLETE`. No verifier-semantic change was
required after this exam. Its oracle encodes the current modeled checks; the
cases are synthetic and do not establish real-world security, physically
possible execution causality, or general error rates.

## 5. LRAT cross-corpus trajectory exam

ABL examined **100** frozen trajectories from the official
[LRAT](https://github.com/Yuqi-Zhou/LRAT/commit/3384730b24b914ba0c0a101d648d6cb2ad0603d4)
release, with the repository pinned at
`3384730b24b914ba0c0a101d648d6cb2ad0603d4` and the
[dataset revision](https://huggingface.co/datasets/Yuqi-Zhou/LRAT-Train/tree/26df12d39ec3eb65a30a61d86664931bb0fa4359)
pinned at `26df12d39ec3eb65a30a61d86664931bb0fa4359`. The sample contains
25 cases each from BM25, Qwen3-Embedding-0.6B, Qwen3-Embedding-4B, and
Qwen3-Embedding-8B. All **100/100** strictly parsed; unexpected rejection and
invention-required cases were **0**.

| Check | Frozen result |
| --- | ---: |
| GOVERNANCE | 100 `NOT_EVALUATED` |
| PROVENANCE | 100 `PARTIAL` |
| HUMAN_REVIEW | 100 `NOT_EVALUATED` |
| AUDIT | 100 `PASS` |
| Overall `COMPLETE` | 0 |
| Confirmed false PASS / false COMPLETE | 0 / 0 |

Decision: **`PASS_WITH_GAPS`**. The release records search/browse activity, but
not a structured final-output-to-supporting-source link. Per-search document IDs
also occur in free text rather than structured source/evidence fields in all
100 sampled cases. ABL did not infer that a retrieved document supported the
final output. This is an information-loss and dataset-representation gap for
this adapter/exam, **not** a finding that LRAT's workflow, answer quality, or
security is defective.

## 6. Validation matrix

| Study | External / synthetic | Cases | Primary question | Key result | Known limitation |
| --- | --- | ---: | --- | --- | --- |
| Schema Fit 01 | External architecture; offline native run | — (one 11-event run) | Could the earlier schema represent the trace honestly? | `C — SCHEMA_REVISION_REQUIRED` | Historical schema; no security claim. |
| Schema Fit 02 | External architecture; offline native run | — (one 33-event run) | Does revised fact/context mapping fit another design? | `B — FIT_WITH_ADAPTER`; cross-study revision justified | Structural loss; historical schema revision. |
| BrowseComp-Plus initial | External trajectory corpus | 20 | Did the old provenance check overstate grounding? | 20/20 confirmed false `PROVENANCE=PASS` | One frozen run/sample; no false `COMPLETE`. |
| BrowseComp-Plus retest | Same frozen 20 cases | 20 | Did the general source-grounding fix remove that error? | 0 confirmed false PASS / false COMPLETE | Recorded linkage only. |
| Unseen holdout | External trajectory corpus; frozen before scoring | 20 | Did the fix transfer to unseen cases from the same run? | 0 confirmed false PASS / false COMPLETE | Same source run; not an independent corpus. |
| Adversarial exam | ABL-owned synthetic/metamorphic cases | 60 | Do current checks match a frozen oracle? | 58 match; 2 expected parser rejects; 0 confirmed false PASS/COMPLETE/non-PASS | Modeled cases and oracle only. |
| LRAT exam | External trajectory corpus | 100 | Can a second corpus parse without invented lineage? | 100 parse; 0 confirmed false PASS/COMPLETE; `PASS_WITH_GAPS` | Final citations unstructured; mapping loss. |

## 7. What changed because of evidence

- Study 01 → observed workflow facts separated from optional Assurance Context.
- Study 01 → missing approval requirement represented as `UNKNOWN`, never
  silently changed to `NOT_REQUIRED`.
- Studies 01 and 02 → optional event hierarchy, structured `SourceRecord`,
  plural `source_refs`, and first-class `WorkflowArtifact` identities/lineage.
- BrowseComp-Plus discovery → Claims and `FINAL_OUTPUT` artifacts require a
  recorded route to `SourceRecord`; producing-event identity no longer suffices.
- Frozen adversarial exam → no further semantic change required for its
  pre-registered cases.
- LRAT exam → a structured final-output lineage/integration gap was recorded;
  the verifier was not retuned to make the cases pass.

These are bounded, evidence-driven changes and findings; no benchmark score was
optimized through case-specific tuning.

## 8. Current claim and reproducibility boundary

> In the frozen v0.2 evaluation sets described here, we observed no confirmed
> false PASS or false COMPLETE after the provenance-grounding fix.

This does not establish a universal error rate, production safety, factual
correctness, or independent certification. The **initial** 20/20 false-PASS
result remains part of this record. The current public repository includes the
[verifier](../../src/agent_boundary_lab/assurance/verifier.py),
[synthetic example](../../examples/research_workflow.json), and
[CLI instructions](../cli.md) for the implemented semantics. Frozen per-case
ledgers and third-party raw trajectories were retained locally for audit rather
than redistributed here. The machine-readable file contains aggregate counts
only. Public synthetic tests can reproduce current code behavior, but they do
not reconstruct these external exams without the separately retained source
artifacts and mapping rules.
