# LangSmith trace import (experimental)

`abl import langsmith` normalizes one LangSmith CLI `trace export --full` JSONL file into the current ABL Workflow format. Each line must be one CLI-normalized run object; the file must contain exactly one trace with its root and complete parent links. The input is a local file. The adapter makes no network or LangSmith API call.

```text
abl import langsmith <trace.jsonl> --output <workflow.json>
abl verify <workflow.json> --output <report.json>
```

The import command exits 0 on success and 2 for an invalid or unreadable export. It will not overwrite an existing output. The existing `abl verify` exit codes and assurance semantics are unchanged.

The adapter preserves run IDs, parent nesting, run types, names, timestamps, error presence/content when safe, completed-run outcome, and bounded structural summaries of I/O. An explicit `inputs.query` string can become an event query. Explicit `Document.metadata.doc_id` or a safe HTTP(S) locator can become a candidate `SourceRecord` from a retriever output. An explicit completed root output becomes a `FINAL_OUTPUT` artifact. Unknown external fields are ignored. Masked or absent values remain unknown.

**LangSmith adapter performs normalization only.** A retrieved document is not automatically supporting Evidence. Run nesting does not establish semantic causality. A tool run is not approval. A completed root output is not source grounded merely because retrieval happened. The adapter does not create Claims, Evidence, governance decisions, approval records, or final-output→source refs from generic trace data. The existing verifier decides PASS/PARTIAL/FAIL/NOT_EVALUATED. In particular, a retrieved source and an unlinked final output should yield incomplete provenance.

The adapter does not prove source truth, factual correctness, semantic entailment, approval, governance, or final-output evidence grounding. It also cannot prove that untraced side effects did not happen. Raw prompt and document contents are not copied into ABL fields. Secret-shaped query/error text and credential-bearing or query-bearing URLs are omitted. Input is bounded to 16 MiB, each JSONL line to 1 MiB, and fewer than 1000 runs because the inspected CLI export fetches at most 1000 per trace.

**Real-export compatibility was validated with one ABL-owned test trace exported as JSONL by the official LangSmith `trace export --full` command.** `abl import langsmith` succeeded, and `abl verify` produced an Assurance Report with the expected `INCOMPLETE` result (exit 1). This validation found one format difference, a blank `status` on completed runs; the adapter fix has a synthetic regression test. The checked-in `tests/fixtures/langsmith_trace_synthetic.jsonl` is synthetic test data, not the real export.

This single-trace validation does not establish compatibility with every LangSmith trace. Missing governance, human review, and final-output-to-source lineage remain unknown, `NOT_EVALUATED`, or `PARTIAL` as determined by the verifier; the adapter does not infer them. This adapter is not production-ready.
