# `abl` CLI (v0.2 alpha)

Install from this repository with Python 3.12 and `uv`:

```console
uv sync --locked
uv run abl verify examples/research_workflow.json
```

General form: `abl verify <workflow.json> [--output <report.json>]`. From the
repository root, the default output is `artifacts/assurance_report.json`.
The CLI creates its parent directory and writes UTF-8 JSON with sorted keys.
Use `--output` to choose another path. The console prints `workflow_id`,
`status`, `findings`, and `report` path; the four check statuses and detailed
findings are in the JSON file.

| Exit code | Meaning |
| --- | --- |
| `0` | All current checks are `PASS`; overall `COMPLETE`. |
| `1` | Report written, but overall `INCOMPLETE`. This includes any `PARTIAL`, `FAIL`, or `NOT_EVALUATED`. |
| `2` | Invalid CLI arguments, missing/unreadable input, invalid JSON, or workflow structural validation failure. |

The checked-in example intentionally returns **1**. A representative console
run from the repository root is:

```text
workflow_id=literature_review_v02_preview
status=INCOMPLETE
findings=3
report=artifacts\assurance_report.json
```

Path separators vary by platform. The matching [sanitized example report](../examples/assurance_report.example.json)
shows `GOVERNANCE=FAIL`, `PROVENANCE=PARTIAL`, `HUMAN_REVIEW=FAIL`, and
`AUDIT=PASS`. The runtime report includes `generated_at`; the checked-in copy
omits that timestamp for stable review. Read [report semantics](assurance-semantics.md)
and the [input schema](workflow-schema.md) before interpreting findings.

The default example uses local synthetic data and makes no external calls.
`abl verify` reads a recorded JSON workflow; it is not a universal interceptor
for a running research agent. Output write failures are ordinary I/O errors,
not the workflow-validation exit code `2`.
