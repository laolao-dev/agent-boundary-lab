# Agent Boundary Lab

## Research-Agent Workflow Assurance & Adversarial Verification

> “We verify why a multi-step research-agent workflow should be trusted.”

Research agents can search many sources without leaving a verifiable record of
which evidence actually supports their final output. Agent Boundary Lab (ABL)
audits the **recorded workflow evidence**: it checks governance decisions,
source/evidence lineage, human-review records, and audit completeness, then
writes a JSON Assurance Report with findings. This is an alpha research prototype.

```text
Research Agent Workflow
        ↓
ABL Verify
        ↓
Governance · Provenance · Human Review · Audit Completeness
        ↓
Assurance Report
```

Current development package version: `0.2.0a1` (planned public release name:
`v0.2.0-alpha`). The existing `v0.1.0-alpha` release and its benchmark evidence
remain historical.

## Quick start: verify a recorded workflow

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required. From the
repository root:

```console
uv sync --locked
uv run abl verify examples/research_workflow.json
```

This local synthetic example intentionally contains an executed approval-gated
event without an approved record and a claim without evidence. **Exit code 1
means `INCOMPLETE` by design; the CLI has generated a report, not crashed.** The
command writes `artifacts/assurance_report.json` (override with `--output`). The
CLI prints the workflow ID, overall status, finding count, and report path.

The following check statuses come from the verifier's report for this example:

```text
GOVERNANCE      FAIL
PROVENANCE      PARTIAL
HUMAN_REVIEW    FAIL
AUDIT           PASS
OVERALL         INCOMPLETE
FINDINGS        3
```

Read the [sanitized example report](examples/assurance_report.example.json) for
the three findings. The live report also contains `generated_at`; the checked-in
example omits that changing timestamp. See the [CLI guide](docs/cli.md),
[workflow schema](docs/workflow-schema.md), and
[assurance semantics](docs/assurance-semantics.md). The example is fully offline;
it needs no API key, MCP server, or live research-agent integration.

## What v0.2 implements

- A deterministic parser for workflow JSON. Observed workflow facts are separate
  from optional assurance context; missing context stays unknown rather than
  becoming an invented `false` or policy decision.
- Four workflow checks: governance, source/evidence provenance, structured
  human-review evidence, and observed-event audit completeness.
- Claims and explicitly marked `FINAL_OUTPUT` artifacts as provenance subjects.
  Recorded lineage must reach a `SourceRecord` for current grounding.
- Per-check `PASS`, `PARTIAL`, `FAIL`, or `NOT_EVALUATED`; overall `COMPLETE` only
  when all four checks pass, otherwise `INCOMPLETE`.
- Stable finding IDs, severity, references, and remediation hints in a JSON
  Assurance Report; an `abl verify` CLI with explicit exit codes.

The input schema has `Workflow`, `ObservedEvent`, `SourceRecord`, `Evidence`,
`Claim`, `WorkflowArtifact`, and optional `AssuranceContext` records. Evidence
uses plural `source_refs`; events can record optional parent hierarchy; artifacts
have `FINAL_OUTPUT`, `INTERMEDIATE`, or `UNKNOWN` roles. This is a breaking
**development-preview** schema change from earlier v0.2 work; there is no
compatibility importer. The example and guide show the current format.

## Product boundary and limitations

ABL checks recorded identifiers and decisions for modeled workflows. A
source-grounded claim or output has a recorded path to a source; that does not
establish source truth, factual correctness, or citation entailment. ABL does not
infer causality from event hierarchy, authenticate a human approval, or make its
audit evidence tamper-proof. It has no universal research-agent adapter,
automatic LangGraph support, or production security/compliance certification.
Its checked-in external-style fixtures are manually authored synthetic
structures, not redistributed third-party traces or production adapters.

The `ALLOW` / `DENY` / `REQUIRE_APPROVAL` boundary harness is an earlier
pre-dispatch governance layer, not the entire v0.2 product. Attack Search and the
frozen MCPGuard-Dynamic evaluation assess bounded v0.1 behavior; they do not
validate the whole workflow verifier or imply third-party endorsement.

## Other implemented components and future direction

The repository also includes the deterministic boundary harness, a synthetic
research workflow with a fixed approval fixture, bounded seeded Attack Search,
an offline-first OpenAlex metadata replay with optional live access, and public
sanitized v0.1 MCPGuard evidence. A broader reproducible Evidence Bundle,
production workflow adapters, authenticated review, and content-level
verification remain future work. No design-partner or user validation is claimed.

## Architecture in v0.1

- **Boundary Harness** — exact action/target rules produce `ALLOW`, `DENY`, or
  `REQUIRE_APPROVAL`; unmatched modeled actions fail closed.
- **Research Workflow** — a deterministic synthetic workflow demonstrates
  governance decisions, a fixed approval fixture, audit records, and minimal
  provenance.
- **Attack Search** — seeded Random and simplified TraceGuided strategies search
  an intentionally vulnerable synthetic fixture under the same fixed budget.
- **OpenAlex Research-Data Anchor** — a narrow policy and transport seam supports
  offline replay plus explicitly selected live scholarly-metadata access.
- **MCPGuard-Dynamic Integration** — a frozen adapter, policy rubric/manifests,
  conformance support, and tests preserve the evaluated pre-dispatch layer.

Additional local demos:

```console
uv run python -m agent_boundary_lab
uv run python -m agent_boundary_lab.experiment
uv run python -m agent_boundary_lab.grant_demo
```

Live OpenAlex mode is optional and explicitly selected with
`uv run python -m agent_boundary_lab.research_data_demo --live`. It requires the
user's own API key, network access, `npx`, and the pinned community
`@cyanheads/openalex-mcp-server` package. The default validation path never uses
it.

## External benchmark evidence

The frozen MCPGuard-Dynamic evaluation tests ABL v0.1's current pre-dispatch
governance / adversarial-verification layer. It does not validate the whole
future workflow-assurance system.

- V-APR: **43.8% (21/48)**
- FPR: **38.1% (8/21)**
- Benign success: **61.9% (13/21)**

This is a security–utility tradeoff, not a superiority result. Read the
[public benchmark report](docs/benchmarks/mcpguard_dynamic_v01.md) and inspect
the [sanitized public evidence copies](benchmarks/mcpguard_dynamic/public_evidence/).

The Agent Boundary Lab project executed the evaluation itself. “External”
describes the benchmark source; it does not mean that Meta, the MCPGuard-Dynamic
authors, a third-party laboratory, or an independent auditor performed,
certified, or endorsed the evaluation.

## Current limitations

- v0.2 remains an alpha research prototype, not production security enforcement, an
  operating-system sandbox, or proof of compliance.
- It models actions in process; it does not run a real AI agent or intercept
  arbitrary filesystem and network operations.
- The policy uses a small exact-target model. Benchmark results do not establish
  universal attack detection or protection outside the frozen cases.
- The synthetic approval fixture does not authenticate a human or implement a
  real approval service.
- Audit and provenance are structured and deterministic, but not immutable,
  externally attested, or tamper-proof.
- The bounded Attack Search fixture does not establish performance on real
  systems.
- The OpenAlex live path covers one narrow metadata flow and uses a community MCP
  package, not an official OpenAlex MCP server.
- No full text is downloaded or synthesized; content authenticity and
  completeness are not verified.

See [SECURITY.md](SECURITY.md) before reporting security-sensitive cases.
Contributions should follow [CONTRIBUTING.md](CONTRIBUTING.md).
