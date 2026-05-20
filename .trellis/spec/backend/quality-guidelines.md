# Quality Guidelines

> Code standards, testing, and forbidden patterns for the backend.

---

## Overview

Quality gates: **pytest** (with coverage floor), **ruff**, **mypy**. Tests mirror the domain layout under `backend/tests/`. Contract tests keep `docs/api-contract/` aligned.

Reference: `backend/pyproject.toml`, `backend/tests/AGENTS.md`, `backend/AGENTS.md`.

---

## Test Structure

```
backend/tests/
├── unit/           # Fast, isolated, mock external APIs
├── integration/    # DB + service layer (in-memory SQLite)
├── contract/       # API shape vs docs/api-contract/
├── performance/    # Latency / concurrency NFRs
├── e2e/
└── conftest.py     # test_db, async_client, auth_headers
```

### Naming

Preferred: `test_should_<behavior>_when_<condition>` (`tests/AGENTS.md`).

Also accepted: `test_<unit>_<behavior>` — e.g. `tests/unit/test_realtime_audio_flow.py`.

### Async tests

```python
@pytest.mark.asyncio
async def test_should_commit_when_valid():
    ...
```

Fixtures: `pytest_asyncio.fixture` in `tests/conftest.py`.

### Markers

- `@pytest.mark.integration`
- `@pytest.mark.contract`
- `@pytest.mark.performance`

Examples: `tests/integration/test_sales_flow.py`, `tests/contract/test_admin_governance_contract.py`.

### Unit test style

- Fake/stub dependencies — no real StepFun, DashScope, or PostgreSQL in unit tests.
- Parametrize edge cases — see `tests/unit/test_session_control_adapter.py`.

---

## Lint and Format

From `backend/pyproject.toml`:

| Tool | Settings |
|------|----------|
| **ruff** | line-length 88, `select = E,F,I,N,W,UP`, `src = ["src"]` |
| **black** | line-length 88, py311 |
| **mypy** | `disallow_untyped_defs = true`, `mypy_path = "src"` |

Commands:

```bash
cd backend && ruff check src/
cd backend && ruff format src/
cd backend && mypy src/
```

---

## Coverage

Default pytest addopts include `--cov=src --cov-fail-under=48`. Run full suite before large merges:

```bash
cd backend && pytest
cd backend && pytest tests/unit/
```

---

## Forbidden Patterns

From `backend/AGENTS.md` and `.kiro/steering/backend-principles.md`:

| Never | Always |
|-------|--------|
| `print()` | `get_logger(__name__)` |
| `session.query(Model)` | `select(Model)` |
| `orm_mode = True` | `ConfigDict(from_attributes=True)` |
| `@app.on_event("startup")` | lifespan in `app_lifespan.py` |
| Sync DB | `AsyncSession` |
| Raw HTTPException 500 to practice clients | `Result` + `error_response` |
| Unit tests hitting real LLM/TTS APIs | mocks / fakes |

---

## Code Review Checklist

- [ ] Types on new public functions (mypy-clean).
- [ ] Errors use `Result` or `error_response`, not bare exceptions to clients.
- [ ] Logs use structlog with trace_id; no secrets logged.
- [ ] DB changes include Alembic migration.
- [ ] API changes update contract tests if applicable.
- [ ] Scenario code stays in its module (`sales_bot` vs `presentation_coach` — no cross-contamination).

---

## Common Mistakes

- Running pytest from repo root instead of `backend/` — loses `pyproject.toml` config.
- Adding integration test dependencies to unit tests — slows CI and flakes on network.
- Changing response shape without updating `tests/contract/` and `docs/api-contract/`.

---

## Verification Commands

```bash
cd backend && pytest tests/unit/
cd backend && pytest tests/contract/
cd backend && ruff check src/ && mypy src/
```
