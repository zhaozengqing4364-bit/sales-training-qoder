# backend/ — FastAPI Domain Router

Concise backend entrypoint. For deep coding rules, read `.kiro/steering/backend-principles.md`.

## Stack Reality

- Python 3.11+, async/await
- FastAPI + Pydantic 2
- SQLAlchemy 2.0 (async) + Alembic
- pytest (asyncio), ruff, black, mypy

## Structure

```
backend/
├── src/                    # Application code
│   ├── common/             # Shared kernel (AI, audio, db, auth, monitoring)
│   ├── agent/              # Agent platform core
│   ├── sales_bot/          # Sales practice runtime
│   └── presentation_coach/ # PPT practice runtime
├── tests/                  # unit | integration | contract | performance
├── alembic/                # Migration authority
└── scripts/                # Operational scripts
```

## Verification Surfaces

- `pytest` — all tests
- `pytest tests/unit/` — unit
- `pytest tests/integration/` — integration
- `pytest tests/performance/` — performance
- `ruff check src/` — lint
- `ruff format src/` — format
- `mypy src/` — type check
- `alembic upgrade head` — apply migrations

## Child Routing

Enter these before making changes in the corresponding subtree:

- `backend/tests/AGENTS.md` — testing conventions and fixtures
- `backend/src/common/AGENTS.md` — shared platform/kernel work
- `backend/src/sales_bot/AGENTS.md` — realtime sales runtime specifics

## Backend-Only Hard Rules

- NEVER use synchronous DB operations; use `AsyncSession`.
- NEVER use `session.query()`; use `select()` (SQLAlchemy 2.0).
- NEVER use `orm_mode = True`; use `ConfigDict(from_attributes=True)` (Pydantic v2).
- NEVER use `@app.on_event("startup")`; use `lifespan`.
- NEVER use `print()`; use `structlog`.
- All migrations live in `alembic/` and must be generated with `alembic revision --autogenerate`.
