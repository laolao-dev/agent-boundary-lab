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
operations, access secrets, provide an operating-system sandbox, integrate with
MCP or agent frameworks, discover vulnerabilities in real systems, or provide
production security.

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

## Next directions

Possible next steps are richer policy matching, persisted regression scenarios,
and evaluation on controlled research-agent fixtures. Those capabilities are not
part of the current prototype.
