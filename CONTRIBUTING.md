# Contributing to knowledge-graph-api

Thanks for contributing! This project combines Neo4j graph traversal with
pgvector semantic search, so schema and embedding changes can affect query
quality in both engines.

## Getting started

```sh
make install     # install dev + runtime dependencies
make dev         # start the API and its data stores (see Makefile targets)
```

## Before you open a PR

- Run the tests: `make test` (or `pytest`).
- Run `pre-commit run --all-files` (ruff + formatting hooks).
- If you change the entity/relation extraction or the retrieval queries, run
  the evaluation/accuracy checks and share the numbers in the PR.
- Never commit real API keys or model credentials — use environment variables
  or a secret manager.

## Commits

Use conventional-commits style, e.g. `feat(ingest): ...`,
`fix(retrieval): ...`, `docs(security): ...`.

## Reaching out

Open an issue to discuss bugs, feature ideas, or large changes before
submitting a PR.
