# Agent Boundary Lab

## Research-Agent Workflow Assurance & Adversarial Verification

> “We verify why a multi-step research-agent workflow should be trusted.”

Agent Boundary Lab (ABL) is an alpha research prototype for making trust claims
about a multi-step research-agent workflow inspectable. It connects governance,
provenance, human-review evidence, audit completeness, reproducibility, and
adversarial boundary testing without claiming that the full target product is
already implemented.

```text
Research-agent workflow
    ↓
Governance verification
    ↓
Provenance / evidence lineage
    ↓
Human review / approval evidence
    ↓
Audit completeness
    ↓
Adversarial boundary testing
    ↓
Assurance Report + Evidence Bundle
```

Public alpha: `0.1.0-alpha` (Python package version `0.1.0a1`).

## Product boundary

ABL's core object is the whole multi-step research-agent workflow, represented
by a workflow, trace, adapter, and evidence. The target outputs are an Assurance
Report, an Evidence Bundle, findings, and regression scenarios.

The current `ALLOW` / `DENY` / `REQUIRE_APPROVAL` logic is a governance detector,
not the whole product. Audit records are trace evidence; provenance records are
evidence-lineage components; approval records are evidence about a modeled
human-review point; and Attack Search is an adversarial-assurance experiment.
The MCPGuard-Dynamic benchmark is technical validation evidence produced by the
ABL project, not a product certification.

ABL is not presented as a generic MCP gateway, generic policy engine, agent
firewall, enterprise security platform, generic observability tool, or generic
citation checker.

## Currently implemented

- A deterministic boundary/governance harness with explicit `ALLOW`, `DENY`, and
  `REQUIRE_APPROVAL` decisions and pre-dispatch enforcement.
- Structured audit and identifier-level provenance components.
- A synthetic multi-step research workflow with a fixed approval fixture.
- A bounded, seeded Attack Search experiment and a preserved regression case.
- A replay-first OpenAlex research-data anchor with optional live metadata access.
- A frozen MCPGuard-Dynamic evaluation and public sanitized evidence copies.

## Target product direction

- Full workflow-level assurance across research-agent traces and adapters.
- A reviewable Assurance Report.
- A reproducible Evidence Bundle.
- Research-specific governance, provenance, review, audit, and adversarial
  verification.

These are product directions, not completed v0.1 capabilities. The repository
does not yet provide a complete end-to-end verifier, production workflow support,
an authenticated human-approval system, broad research-agent integrations, or
evidence of design partners or users.

## Quick start

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```console
uv sync --locked
uv run pytest
uv run python -m agent_boundary_lab.research_data_demo
```

The default demo is fully local: it requires no API key, starts no MCP server,
and makes no network request. It replays a small checked-in scholarly-metadata
fixture and writes deterministic evidence to
`artifacts/openalex_mcp_evidence.json`.

## v0.2 workflow assurance development preview

The alpha v0.2 vertical slice adds deterministic, workflow-level checks for
governance, evidence lineage, structured human-review records, and observed-event
audit completeness. Its minimal schema keeps observed workflow facts separate
from optional assurance context: a trace can record events, evidence, claims,
control-flow decisions, and outcomes without inventing an ABL governance or
approval decision.

Approval requirements in assurance context are explicitly `REQUIRED`,
`NOT_REQUIRED`, or `UNKNOWN`. Missing governance or approval context produces a
`NOT_EVALUATED` check, never a fabricated pass or failure, and any
`NOT_EVALUATED` check keeps the overall report `INCOMPLETE`. Evidence keeps
`source_ref` separate from `parent_evidence_refs`; claims retain identifier-level
evidence links but ABL does not validate whether claim text is true.

The checked-in `tests/fixtures/external_style_workflow.json` is a sanitized,
manually authored synthetic structural fixture. It reflects only schema
characteristics observed in the first external fit study; it is not a copied
third-party trace and no production adapter or importer is included.

Run the intentionally incomplete local example with no external API calls:

```console
uv run abl verify examples/research_workflow.json
```

The command writes `artifacts/assurance_report.json`. Exit code `0` means every
current check passed. Exit code `1` means the report is `INCOMPLETE`, including
when a check is `PARTIAL`, `FAIL`, or `NOT_EVALUATED`. Exit code `2` means the
workflow input could not be validated.

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

- v0.1 is an alpha research prototype, not production security enforcement, an
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
