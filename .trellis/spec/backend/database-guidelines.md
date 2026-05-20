# Database Guidelines

> ORM, migrations, and query patterns for this project.

---

## Overview

PostgreSQL in production, SQLite in tests. All access is **async SQLAlchemy 2.0** via `AsyncSession`. Schema changes go through **Alembic only** in production.

Reference: `common/db/session.py`, `common/db/models.py`, `alembic/env.py`, `backend/AGENTS.md`.

---

## Engine and Session

- `create_async_engine` + `AsyncSessionLocal` in `common/db/session.py`.
- FastAPI dependency: `get_db()` yields `AsyncSession`.
- Callers **explicitly `commit()`**; no implicit auto-commit on exit.

```python
# Pattern in API routes
async def get_scenario(db: AsyncSession = Depends(get_db)) -> ...:
    result = await db.execute(select(Scenario).where(...))
    rows = result.scalars().all()
```

Example: `sales_bot/api/scenarios.py`.

---

## Query Patterns

Use SQLAlchemy 2.0 style exclusively:

```python
from sqlalchemy import select

stmt = select(Scenario).where(Scenario.id == scenario_id)
result = await session.execute(stmt)
scenario = result.scalar_one_or_none()
```

- Prefer `select()` + `await session.execute()`.
- Use `.scalars().all()` / `.scalar_one_or_none()` for results.
- Use `select(Model)` with filters; never `session.query(Model)`.

---

## Models

- `class Base(DeclarativeBase)` in `common/db/models.py`.
- **Most ORM tables** are defined in `common/db/models.py` (not scattered per module).
- Additional domain-specific tables may live in `{module}/models.py` (e.g. `agent/models.py`).
- UUIDs stored as `String(36)` for SQLite/PostgreSQL compatibility.
- Table/column names: **snake_case**.

Examples: `common/db/models.py`, `agent/models.py`.

Note: `common/conversation/models.py` re-exports from `common/db/models.py` for backward-compatible imports.

### Pydantic schemas

Schemas are **not** always `{module}/schemas.py`. Common locations:

- `{module}/schemas.py` — e.g. `agent/schemas.py`, `evaluation/schemas.py`
- `common/db/schemas.py` — shared DTOs used by presentation and other modules
- `common/{domain}/schemas.py` — e.g. `common/conversation/schemas.py`

Use `ConfigDict(from_attributes=True)` (Pydantic v2), not `orm_mode = True`.

---

## Migrations

- **Authority**: `backend/alembic/` — run `alembic upgrade head` for production.
- Autogenerate: `alembic revision --autogenerate -m "description"`.
- `alembic/env.py` imports all models so `target_metadata = Base.metadata` is complete.
- `init_db()` / `create_all` — **dev/test bootstrap only**; not production schema authority.

Migration naming example: `alembic/versions/20260516_1000_064_learner_profile_runtime_bindings.py`.

---

## Test Database

Integration tests use in-memory SQLite:

- Fixture in `tests/conftest.py`: `sqlite+aiosqlite:///:memory:`.
- `Base.metadata.create_all` in test setup.
- Import domain models in conftest so metadata is registered.

---

## Anti-Patterns

| Forbidden | Use instead |
|-----------|-------------|
| `session.query(Model)` | `select(Model)` + `execute` |
| Sync DB drivers / blocking calls | `AsyncSession` + asyncpg |
| `orm_mode = True` | `from_attributes=True` |
| Production schema via `create_all` | Alembic migrations |
| Missing model import in `alembic/env.py` | Import new models before autogenerate |

---

## Common Mistakes

- Forgetting to register a new model in `alembic/env.py` → incomplete migrations.
- Implicit commit assumptions — always commit after writes in the service/API layer.
- Cross-module FK without importing both models in Alembic env.

---

## Verification

```bash
cd backend && alembic upgrade head
cd backend && pytest tests/integration/
```
