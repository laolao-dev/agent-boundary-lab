# Workflow JSON schema (v0.2 alpha)

`abl verify` accepts one JSON object describing **recorded** research-workflow
facts and optional assurance judgments. Use
[`examples/research_workflow.json`](../examples/research_workflow.json) as a
complete structural example. The parser rejects unknown fields, missing required
fields, invalid types, duplicate identifiers within a collection, event-parent
cycles, and artifact-parent cycles. It does not infer absent facts.

## Top-level Workflow

| Field | Requirement | Meaning |
| --- | --- | --- |
| `workflow_id` | Required, non-empty string | Stable identifier copied into the report. |
| `events` | Required, non-empty array of `ObservedEvent` | Observed steps in the workflow. |
| `sources`, `evidence`, `claims`, `artifacts` | Required arrays; each may be empty | Source identities, evidence, claim subjects, and other artifacts. |
| `title`, `research_goal` | Optional strings | Human context; not assurance evidence by themselves. |
| `assurance_context` | Optional object | Judgments about events, separate from observed facts. |

Absent optional strings and `null` mean unknown. Each `metadata` object, where
supported, is a map of string keys to non-empty string values. References use
IDs; they do not embed source content or prove its authenticity.

## Observed facts and lineage

| Object | Required fields | Important optional fields and behavior |
| --- | --- | --- |
| `ObservedEvent` | `event_id` | `event_type`, `action`, `tool`, `executed`, `observation`, `error`, `sequence`, `evidence_refs`, `parent_event_id`, `timestamp`, `latency_ms`, `query`, `question_ref`, `control_flow_decision`, `metadata`. `parent_event_id` must name another event; self-links and cycles are rejected. A control-flow decision is not a governance decision. |
| `SourceRecord` | `source_id` | `source_type`, `locator`, `title`, `metadata` identify a recorded source. A source record does not certify source truth. |
| `Evidence` | `evidence_id` | `source_refs` names sources; `parent_evidence_refs` names upstream evidence; `produced_by_event` names an observed producing event; `supporting_text`, `question_ref`, `metadata` are optional. Plural `source_refs` replaces the older singular field. |
| `Claim` | `claim_id`, `text`, `evidence_refs` array | `question_ref` is optional. An empty evidence list parses but produces a provenance finding. |
| `WorkflowArtifact` | `artifact_id`, `artifact_type` | `artifact_role`, `source_refs`, `evidence_refs`, `parent_artifact_refs`, `produced_by_event`, `metadata`. Parent and source/evidence references must resolve; parent cycles are rejected. |

`artifact_role` is `FINAL_OUTPUT`, `INTERMEDIATE`, or `UNKNOWN` (the default
when omitted). An explicit `null` is invalid. Claims and `FINAL_OUTPUT`
artifacts are provenance subjects. `INTERMEDIATE` and `UNKNOWN` artifacts can
contribute lineage but are not themselves treated as final outputs. If there is
no Claim or `FINAL_OUTPUT`, provenance is `NOT_EVALUATED` unless a concrete
provenance finding exists.

For the current grounding check, a Claim must reach a `SourceRecord` through
referenced Evidence and its parent-evidence chain. A `FINAL_OUTPUT` artifact
can reach a source directly, through referenced Evidence, or through parent
artifacts. `produced_by_event` records **execution origin**, not research
grounding; that field alone cannot produce a provenance `PASS`.

## AssuranceContext and review

`assurance_context` may contain an `events` array. Each entry requires an
`event_id` and may supply `governance_decision` (`ALLOW`, `DENY`, or
`REQUIRE_APPROVAL`), `governance_evidence_refs`, `policy_ref`,
`approval_requirement`, and `approval_record`. Its event ID should refer to an
observed event; an orphan context produces a governance finding. This context
represents supplied judgments and evidence; the parser does not turn a research
control-flow choice into an ABL governance decision.

`approval_requirement` is `REQUIRED`, `NOT_REQUIRED`, or `UNKNOWN`. Omitted or
`null` becomes `UNKNOWN`, **not** `NOT_REQUIRED`. An optional `approval_record`
requires `approval_id` and `decision` (`APPROVED` or `REJECTED`); it may list
`evidence_refs`. The record is structured review evidence, not authenticated
human identity. Missing context is not a `false` approval requirement.

`executed` is an optional Boolean on the **observed** event; absent or `null`
means the execution fact is unknown, not `false`. The verifier may return
`NOT_EVALUATED` or `PARTIAL` when the facts needed for a check are missing.

See [assurance semantics](assurance-semantics.md) for the checks and
[CLI usage](cli.md) for running the parser. This schema is a development-preview
breaking change; no v0.1/v0.2 compatibility importer is provided.
