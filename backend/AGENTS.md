# backend/ — FastAPI Domain Router

Concise backend entrypoint. For deep coding rules, read `.kiro/steering/backend-principles.md`.

## Stack Reality

- Python 3.11+, async/await
- FastAPI + Pydantic 2
- SQLAlchemy 2.0 (async) + Alembic
- pytest (asyncio), ruff, mypy

## Structure

```
backend/
├── src/
│   ├── common/              # Shared kernel
│   ├── sales_bot/           # Sales practice runtime
│   ├── presentation_coach/  # PPT practice runtime
│   ├── agent/               # Agent platform
│   ├── admin/               # Admin control plane APIs
│   ├── evaluation/          # Staged evaluation & reports
│   ├── curriculum_practice/ # Curriculum / examiner runtime
│   ├── prompt_templates/    # Prompt template governance
│   ├── sales_trainer/       # Sales trainer admin + learner APIs
│   ├── supervisor/          # Supervisor review & retraining
│   ├── training_runtime/    # Unified runtime descriptors & plugins
│   ├── support/             # Support release-health surfaces
│   ├── router_registry.py   # HTTP router mount point
│   └── websocket_routes.py  # WebSocket mount point
├── tests/                   # unit | integration | contract | performance | e2e
├── alembic/                 # Migration authority
└── scripts/                 # Operational scripts
```

## Where to Look

| Concern | Location |
|---------|----------|
| App bootstrap | `src/app_factory.py`, `src/app_lifespan.py` |
| HTTP route registry | `src/router_registry.py` |
| WebSocket registry | `src/websocket_routes.py` |
| Health / metrics | `src/http_routes.py` |
| Shared models | `src/common/db/models.py` |

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

- `backend/tests/AGENTS.md`
- `backend/alembic/AGENTS.md`
- `backend/scripts/AGENTS.md`
- `backend/src/common/AGENTS.md`
- `backend/src/sales_bot/AGENTS.md`
- `backend/src/presentation_coach/AGENTS.md`
- `backend/src/agent/AGENTS.md`
- `backend/src/admin/AGENTS.md`
- `backend/src/evaluation/AGENTS.md`
- `backend/src/curriculum_practice/AGENTS.md`
- `backend/src/prompt_templates/AGENTS.md`
- `backend/src/sales_trainer/AGENTS.md`
- `backend/src/supervisor/AGENTS.md`
- `backend/src/training_runtime/AGENTS.md`
- `backend/src/support/AGENTS.md`

## Backend-Only Hard Rules

- NEVER use synchronous DB operations; use `AsyncSession`.
- NEVER use `session.query()`; use `select()` (SQLAlchemy 2.0).
- NEVER use `orm_mode = True`; use `ConfigDict(from_attributes=True)`.
- NEVER use `@app.on_event("startup")`; use `lifespan`.
- NEVER use `print()`; use `structlog`.
- All migrations live in `alembic/` and must be generated with `alembic revision --autogenerate`.
- ALWAYS register new HTTP routers in `router_registry.py`; WebSocket routes in `websocket_routes.py` or domain `websocket/router.py`.
