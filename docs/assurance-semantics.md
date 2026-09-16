# Assurance Report semantics (v0.2 alpha)

`abl verify` assesses a **recorded workflow** with four current checks:
`GOVERNANCE`, `PROVENANCE`, `HUMAN_REVIEW`, and `AUDIT`. It writes one JSON
Assurance Report. The report is an alpha, identifier-level assessment, not a
numerical trust score or certification.

## Per-check status

| Status | Exact current rule | Reading |
| --- | --- | --- |
| `PASS` | No finding and no unevaluated item for the check. | The recorded input satisfied the current deterministic rule. |
| `PARTIAL` | A finding without HIGH severity, or some unevaluated items alongside evaluated items; also used when a concrete finding exists despite no evaluable subject. | There is a gap or incomplete coverage. |
| `FAIL` | At least one HIGH-severity finding in that check. | A modeled high-severity rule was contradicted by recorded facts. |
| `NOT_EVALUATED` | No evaluated items and no concrete finding. | Required context or provenance subject is absent; no pass/fail judgment was made. |

`NOT_EVALUATED` is neither `PASS` nor `FAIL`. In particular, absent governance
or review context is not inferred to mean `ALLOW` or `NOT_REQUIRED`. A Claim or
`FINAL_OUTPUT` without a recorded path to a `SourceRecord` cannot receive
provenance `PASS`; a producer-event link alone is not grounding.

`summary.overall_status` is `COMPLETE` **only when all four checks are `PASS`**.
Any `PARTIAL`, `FAIL`, or `NOT_EVALUATED` makes it `INCOMPLETE`. `COMPLETE` means
complete under these checks and supplied facts, not a real-world security,
compliance, or factual-correctness guarantee.

## What each check reads

- **Governance:** supplied event-level `ALLOW` / `DENY` /
  `REQUIRE_APPROVAL` context against recorded execution. Executing after `DENY`,
  or after `REQUIRE_APPROVAL` without an `APPROVED` record, is a HIGH finding.
- **Provenance:** claim/final-output source reachability and reference integrity.
  Claims use Evidence chains; final outputs may use direct sources, Evidence,
  and parent artifacts. Event origin and source truth are separate questions.
- **Human review:** supplied approval requirement and structured approval
  record against observed execution. Missing requirement remains `UNKNOWN`.
  A record does not authenticate a reviewer.
- **Audit:** recorded event order and minimal type/action and outcome/error
  fields. The parser checks hierarchy references but does not establish timing
  or causality.

## Report fields and example

`workflow_id` identifies the input. `generated_at` is the current UTC runtime
timestamp. `checks[]` lists check names, statuses, and finding IDs.
`findings[]` contains stable IDs in check order, severity (`HIGH`, `MEDIUM`,
`LOW`), message, referenced evidence IDs, optional event/claim ID, and a
remediation hint. `summary` gives overall status and finding counts by severity.
Finding IDs are stable for the same workflow and rule order in this version;
they are not a cross-version guarantee.

The checked-in [example report](../examples/assurance_report.example.json) was
generated from `examples/research_workflow.json` by the current CLI and then
had only its changing `generated_at` field omitted. The live command writes
that field. Its `GOVERNANCE=FAIL`, `PROVENANCE=PARTIAL`, `HUMAN_REVIEW=FAIL`,
`AUDIT=PASS`, overall `INCOMPLETE` and exit 1 are **intentional** synthetic
findings, not a failed installation or a certification result.

Grounded means only that recorded identifiers connect a subject to a source.
ABL does not verify source truth, factual correctness, whether source text
entails claim prose, authenticated approval, or tamper-proof evidence.
