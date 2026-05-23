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

---

## Operational Seed Scripts

Use `backend/scripts/` for idempotent, operator-run seed scripts that create demo or training configuration data without changing schema. These scripts are **data/config writers**, not migration authority.

### 1. Scope / Trigger

- Trigger: adding a runnable seed command such as `PYTHONPATH=src uv run python scripts/seed_<name>.py`.
- Scope: create or update existing ORM records needed for local demos, training samples, or admin-config bootstraps.
- Not scope: schema changes, production migrations, or one-off hidden manual SQL.

### 2. Signatures

Seed scripts must expose:

```bash
PYTHONPATH=src uv run python scripts/seed_<name>.py
PYTHONPATH=src uv run python scripts/seed_<name>.py --verify-only
```

Python entrypoint shape:

```python
async def run(verify_only: bool) -> tuple[int, dict[str, object]]: ...
def parse_args() -> argparse.Namespace: ...
def main() -> None: ...
```

### 3. Contracts

- Use `AsyncSessionLocal()` and SQLAlchemy 2.0 `select()` / `execute()` only.
- Scripts must be idempotent: first run creates records, second run updates existing records rather than duplicating them.
- `--verify-only` must not create or update records.
- Output must be a single JSON object written to stdout with:
  - `ok: bool`
  - `verify_only: bool`
  - `changes: {created: int, updated: int}`
  - `ids: {...}` for created/verified primary IDs
  - `counts: {...}` for core asset counts
  - `keys: {...}` for operator-facing lookup keys such as emails, versions, template names

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Missing expected record in `--verify-only` | Exit `1`, output `{"ok": false, "errors": [...]}` |
| Required asset not published/active | Exit `1`, explain the failed asset/state |
| Required child count mismatch | Exit `1`, include expected vs actual count |
| Relationship mismatch | Exit `1`, name the mismatched field |
| Successful seed or verify | Exit `0`, output summary JSON |

### 5. Good/Base/Bad Cases

- Good: seed creates a complete linked sample, then `--verify-only` confirms assets and relationships.
- Base: rerunning the seed returns `created=0` and updates the existing records.
- Bad: seed uses generated names without stable lookup keys, making reruns duplicate records.

### 6. Tests Required

- Minimum: `python3 -m py_compile scripts/seed_<name>.py` and `uv run ruff check scripts/seed_<name>.py`.
- If a writable dev database is available: run the script, rerun it once for idempotency, then run `--verify-only`.
- For reusable seed frameworks, add integration tests around the upsert/verify functions.

### 7. Wrong vs Correct

#### Wrong

```python
record = Model(name="Demo")
db.add(record)
await db.commit()
```

This duplicates data on every run and has no verification mode.

#### Correct

```python
record = await _first(db, select(Model).where(Model.name == NAME))
if record is None:
    record = Model(id=_uuid(), name=NAME)
    db.add(record)
    counters["created"] += 1
else:
    counters["updated"] += 1
record.status = "published"
```

Stable lookup keys make the script safe to rerun and easy to verify.
