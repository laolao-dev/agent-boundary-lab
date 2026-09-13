# Agent Boundary Lab

Agent Boundary Lab is an alpha trust-verification prototype for making an
agent-like action explicit, deciding whether it may be dispatched, and recording
the result as deterministic evidence.

Public alpha: `0.1.0-alpha` (Python package version `0.1.0a1`).

## What it does

```text
Agent action
    -> Boundary decision
    -> Dispatch / Block
    -> Structured audit
    -> Provenance
    -> Boundary stress testing
```

The repository contains a small deterministic Boundary Harness, a synthetic
research workflow, a bounded synthetic attack-search experiment, and an optional
research-data anchor for real OpenAlex scholarly metadata.

## Quick Start

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```console
uv sync
uv run pytest
uv run python -m agent_boundary_lab.research_data_demo
```

This default path is fully local: it requires no API key, starts no MCP server,
and makes no network request. The demo replays a small checked-in metadata
fixture.

## What you should see

The replay demo clearly labels its mode and shows the two policy outcomes:

```text
MODE: REPLAY (OFFLINE FIXTURE)

ALLOW
  Boundary decision: ALLOW
  Dispatched: YES

DENY
  Boundary decision: DENY
  Dispatched: NO
  Result: BLOCKED_PRE_DISPATCH

PROVENANCE
  ... -> research_evidence_bundle

AUDIT
  Records: 2
```

It writes deterministic, machine-readable replay evidence to
`artifacts/openalex_mcp_evidence.json`.

## Real OpenAlex integration

Live mode is optional:

```console
uv run python -m agent_boundary_lab.research_data_demo --live
```

It requires `OPENALEX_API_KEY`, network access, `npx`, and the pinned
`@cyanheads/openalex-mcp-server` package. This is a community OpenAlex MCP server,
not an official OpenAlex MCP server. The integration retains only bounded
scholarly metadata; it does not download or synthesize full text.

The pre-dispatch policy decision occurs before transport dispatch. The configured
publication search is allowed and dispatched, while the citation-graph intent is
denied with a transport call count of zero. Audit output never includes the API
key.

## Architecture

- **Boundary Harness** — exact action/target rules produce `ALLOW`, `DENY`, or
  `REQUIRE_APPROVAL`; unmatched actions fail closed inside the modeled harness.
- **Research Workflow** — a deterministic synthetic workflow demonstrates
  boundary decisions, a fixed approval fixture, structured audit records, and
  minimal provenance.
- **Attack Search** — seeded Random and simplified TraceGuided strategies search
  an intentionally vulnerable synthetic fixture and preserve a discovered case
  as a regression test.
- **MCP Research Data Anchor** — one narrow OpenAlex policy and transport seam
  supports offline replay plus explicitly selected live metadata access.

Additional local demos are available with:

```console
uv run python -m agent_boundary_lab
uv run python -m agent_boundary_lab.experiment
uv run python -m agent_boundary_lab.grant_demo
```

## Attack Search Experiment

The checked-in experiment has a candidate space of 8, a budget of 3 candidate
evaluations per run, and 20 fixed seeds. Its deterministic results are:

| Strategy | Synthetic violations discovered |
| --- | ---: |
| Random | 7/20 |
| TraceGuided | 20/20 |

TraceGuided uses only prior `ExecutionRecord` data; neither strategy receives
expected decisions or violation labels. This is a bounded synthetic benchmark and
does not establish general vulnerability-detection performance.

## Current limitations

- This is an alpha prototype, not production security enforcement, an operating-
  system sandbox, or evidence of institutional or regulatory compliance.
- It models agent-like actions in process. It does not run a real AI agent,
  intercept real filesystem/network operations, or provide adapters for arbitrary
  agents.
- Policies use a small exact-match model. Results do not establish universal
  attack detection or protection outside the modeled scenarios.
- The attack-search result is from one bounded, intentionally vulnerable synthetic
  fixture; it is not discovery of a vulnerability in a real agent or system.
- The approval step is a fixed synthetic fixture. It does not authenticate a human
  approver or establish a real approval identity.
- Audit and provenance are structured and deterministic, but are not immutable,
  externally attested, or tamper-proof.
- The OpenAlex live path uses a pinned community MCP package, not an official
  OpenAlex MCP server. It covers one narrow scholarly-metadata flow and requires
  the user to supply their own API key.
- No full text is downloaded or synthesized. Paper contents, completeness, and
  authenticity are not verified.
- Replay evidence is a checked-in point-in-time fixture and does not validate the
  availability or behavior of the live service.
- The project provides neither a generic MCP framework nor write operations.

See [SECURITY.md](SECURITY.md) before using or reporting security-sensitive test
cases. Contributions should follow [CONTRIBUTING.md](CONTRIBUTING.md).
