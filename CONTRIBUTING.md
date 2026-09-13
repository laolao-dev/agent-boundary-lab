# Contributing

Agent Boundary Lab is an alpha prototype. Keep changes small, deterministic, and
within the documented scope.

Before submitting a change, run:

```console
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

Tests must not require secrets or make live OpenAlex or external MCP requests.
Never commit API keys, `.env` files, credentials, private data, caches, generated
build output, or large raw service responses. Use synthetic fixtures or the
minimal checked-in replay fixture instead.
