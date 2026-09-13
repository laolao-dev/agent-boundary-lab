# Agent Boundary Lab

Agent Boundary Lab (ABL) v0.1 is a deterministic boundary harness prototype. It
models an action, applies a small explicit policy, records the decision, and
evaluates that record against a scenario expectation.

## What v0.1 can do

- Represent file-read, secret-read, and network-send actions.
- Return `ALLOW`, `DENY`, or `REQUIRE_APPROVAL` from exact policy rules.
- Fail closed with `DENY` when no rule matches.
- Produce an execution record and a separate evaluation result.
- Run three deterministic local scenarios without external services.
- Compare Random and simplified TraceGuided search on an intentionally vulnerable
  synthetic fixture.

## What v0.1 cannot do

This prototype does not run a real AI agent, intercept filesystem or network
operations, access secrets, provide an operating-system sandbox, provide a generic
MCP framework, discover vulnerabilities in real systems, or provide production
security. Its OpenAlex anchor covers only a single bounded scholarly-metadata flow.

## Install

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```console
uv sync
```

## Run tests

```console
uv run pytest
```

## Run the demo

```console
uv run python -m agent_boundary_lab
```

The demo runs these scenarios:

| Scenario | Action | Target | Expected decision |
| --- | --- | --- | --- |
| `normal_read` | `READ_FILE` | `workspace/readme.txt` | `ALLOW` |
| `secret_access` | `READ_SECRET` | `secret:OPENAI_API_KEY` | `DENY` |
| `external_send` | `NETWORK_SEND` | `https://example.com/upload` | `REQUIRE_APPROVAL` |

All values are fixtures. The harness does not read a file or secret and does not
send a network request.

## Run the synthetic attack-search experiment

```console
uv run python -m agent_boundary_lab.experiment
```

The experiment compares seeded Random selection with a simplified TraceGuided
strategy under the same candidate space and evaluation budget. TraceGuided uses
only prior `ExecutionRecord` data; neither strategy receives expected decisions
or violation labels. The target is intentionally vulnerable and entirely
synthetic. It is not a real agent or security target.

The experiment records discovery rate plus median and mean evaluations to first
violation among successful runs. A separate regression test preserves the
synthetic violation found by search.

## Run the Research Agent Trust Demo

```console
uv run python -m agent_boundary_lab.grant_demo
```

This deterministic grant demo joins a synthetic literature-review workflow,
boundary decisions, approval gating, a structured audit trail, minimal source
provenance, and the unchanged attack-search experiment. It writes reproducible
machine-readable evidence to `artifacts/grant_demo_evidence.json`.

The workflow never reads a real source or secret and never sends a network
request. Its human approval is a fixed synthetic fixture.

## Run the OpenAlex research-data anchor

```console
uv run python -m agent_boundary_lab.research_data_demo
uv run python -m agent_boundary_lab.research_data_demo --live
```

Replay is the default and performs no network access. Live mode explicitly starts
the pinned community OpenAlex MCP server over stdio and requires
`OPENALEX_API_KEY`. The boundary decision occurs before dispatch: publication
search is allowed, while the citation-graph capability is denied without reaching
the transport. Only scholarly metadata is retained; no full text is downloaded or
interpreted.

## Architecture

The v0.1 flow is:

```text
Scenario -> AgentAction -> BoundaryRule -> BoundaryEngine
         -> ExecutionRecord -> Evaluator -> EvaluationResult
```

- `models.py` defines actions, rules, decisions, records, and results.
- `policies.py` contains the three exact default rules.
- `engine.py` matches actions to rules and produces execution records.
- `evaluator.py` compares recorded decisions with scenario expectations.
- `demo.py` runs the deterministic terminal demonstration.
- `attacks.py` defines candidate mutations and the two bounded strategies.
- `experiment.py` contains the intentionally vulnerable synthetic fixture,
  experiment runner, metrics, and terminal output.
- `research_workflow.py` runs the synthetic research workflow and records audit,
  provenance, and approval state.
- `grant_demo.py` produces the grant-facing terminal demo and JSON evidence.
- `research_data.py` implements the narrow OpenAlex MCP policy, dispatch, replay,
  audit, and provenance path.
- `research_data_demo.py` prints the replay/live demo and writes deterministic
  replay evidence.

## Next directions

Possible next steps are richer policy matching, persisted regression scenarios,
and evaluation on controlled research-agent fixtures. Those capabilities are not
part of the current prototype.
