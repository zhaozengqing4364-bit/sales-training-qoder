# backend/tests/ — Test Tree Router

This file governs the backend test tree only. For broader backend rules, see `backend/AGENTS.md`. For detailed testing principles, see `.kiro/steering/testing-principles.md`.

## Test Taxonomy

```
backend/tests/
├── unit/           # Fast, isolated tests (functions, classes, utilities)
├── integration/    # Module interactions, DB + service layers
├── contract/       # API contract alignment with docs/api-contract/
├── performance/    # Latency, throughput, NFR bounds
├── e2e/            # End-to-end flows (WebSocket, full scenarios)
├── evaluation/     # Model/output quality evaluation scripts
├── fixtures/       # Shared data files and JSON payloads
├── scripts/        # Test helpers and setup scripts
└── conftest.py     # Root fixtures (test_db, async_client, auth_headers)
```

## Pytest Configuration

Markers and options live in `backend/pyproject.toml` under `[tool.pytest.ini_options]`:

- `contract` — API contract tests
- `integration` — Integration tests
- `performance` — Performance and latency tests

Run subsets:

```bash
pytest tests/unit/
pytest tests/integration/ -m integration
pytest tests/contract/ -m contract
pytest tests/performance/ -m performance
```

## Fixture Hierarchy

- `backend/tests/conftest.py` — root fixtures: `test_db`, `async_client`, `auth_headers`, `test_user`, `another_user`
- Sub-directory `conftest.py` files — local overrides and specialized fixtures
- `fixtures/` — static data files; load with `json.loads((FIXTURES_DIR / "file.json").read_text())`

## Local Conventions

- Name tests: `test_should_<behavior>_when_<condition>`
- Use AAA pattern: Arrange, Act, Assert
- Unit tests must mock external services (DB, LLM, ASR, TTS)
- Integration tests use the in-memory SQLite engine from `conftest.py`
- Contract tests verify responses against `docs/api-contract/`
- Performance tests assert explicit latency bounds and include `@pytest.mark.performance`

## Orientation Note

A root symlink `tests -> backend/tests` exists for convenience. All pytest execution should run from `backend/` so `pyproject.toml` options apply.

## Verification Expectations

- New features need matching unit tests.
- API changes need updated contract tests.
- Bugfixes need a failing test first.
- Run `pytest` before considering work complete.
