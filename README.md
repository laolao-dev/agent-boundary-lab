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

## What v0.1 cannot do

This prototype does not run a real AI agent, intercept filesystem or network
operations, access secrets, provide an operating-system sandbox, integrate with
MCP or agent frameworks, discover attacks, or provide production security.

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

## Next directions

After the v0.1 semantics are stable, possible next steps are richer policy
matching, regression scenario storage, and adapters for controlled test
environments. Those capabilities are not part of the current prototype.
