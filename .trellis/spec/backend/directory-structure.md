# Directory Structure

> How backend code is organized in this project.

---

## Overview

The backend is a single Python package under `backend/src/`, organized by **domain module** (sales, presentation, agent, admin, etc.) plus a shared **`common/` kernel**. HTTP routes and WebSocket handlers are registered centrally; business logic lives in `services/`.

Reference: `backend/AGENTS.md`, `.kiro/steering/backend-principles.md`.

---

## Directory Layout

```
backend/
├── src/
│   ├── main.py                 # Entry → create_app() (+ legacy test shims)
│   ├── app_factory.py          # FastAPI app construction
│   ├── app_lifespan.py         # Lifespan (not @app.on_event)
│   ├── http_routes.py          # Health, dev login, core HTTP (with router_registry)
│   ├── router_registry.py      # Domain HTTP routers → /api/v1
│   ├── websocket_routes.py     # WebSocket registration (some routes inline here)
│   ├── common/                 # Shared kernel (no single-scenario logic)
│   │   ├── api/                # success_response / error_response
│   │   ├── db/                 # Base, session, get_db
│   │   ├── error_handling/     # Result[T], middleware
│   │   ├── monitoring/         # structlog, trace_id
│   │   ├── websocket/          # BaseWebSocketHandler
│   │   └── audio/, ai/, auth/, knowledge/, ...
│   ├── sales_bot/              # Sales practice (independent scenario)
│   │   ├── api/                # REST routers
│   │   ├── services/           # BotService, voice policy, etc.
│   │   └── websocket/          # stepfun_realtime_handler, components/
│   ├── presentation_coach/     # PPT practice (WS registered in websocket_routes.py)
│   ├── agent/                  # Agent / Persona platform
│   ├── admin/                  # api/, services/, config_bundles/
│   ├── training_runtime/       # Scenario plugin dispatch for WS handlers
│   └── evaluation/, curriculum_practice/, supervisor/, support/, ...
├── tests/
│   ├── unit/                   # Fast, mocked
│   ├── integration/            # DB + services
│   ├── contract/               # docs/api-contract alignment
│   └── performance/
├── alembic/                    # Migration authority
└── scripts/                    # Ops / seed scripts
```

---

## Module Organization

### Adding a new REST feature

1. Define `APIRouter` in `{module}/api/*.py`.
2. Implement logic in `{module}/services/*.py`.
3. Register router in `router_registry.py` with prefix `/api/v1`.
4. Add Pydantic schemas in `{module}/schemas.py`, `common/db/schemas.py`, or `common/{domain}/schemas.py`.

Example: `sales_bot/api/scenarios.py` + `sales_bot/services/bot_service.py` (no local `schemas.py` — uses shared schemas).

### Adding WebSocket behavior

Two patterns exist:

**A. Domain router module** (sales, curriculum):

1. Handler in `{module}/websocket/*_handler.py`.
2. Route in `{module}/websocket/router.py`.
3. Register via `websocket_routes.py` (often through `training_runtime` plugin dispatch).

**B. Inline root registration** (presentation):

1. Handler in `presentation_coach/websocket/*_handler.py`.
2. Route declared directly in `websocket_routes.py` (no `presentation_coach/websocket/router.py`).

Split large handlers into `websocket/components/` (see `sales_bot/websocket/components/stepfun_*`).

Examples: `sales_bot/websocket/stepfun_realtime_handler.py`, `common/websocket/base_handler.py`.

### ORM models

- `class Base` and **most core tables** live in `common/db/models.py` (User, Scenario, PracticeSession, etc.).
- Some domains add `{module}/models.py` (e.g. `agent/models.py`, `common/knowledge/models.py`).
- `common/conversation/models.py` is a **re-export shim** — not where tables are defined.
- Register all models in `alembic/env.py` for autogenerate.

### Where logic must NOT go

- **`common/`** — only cross-domain utilities; no sales-only or PPT-only rules (`backend/src/common/AGENTS.md`).
- **`main.py`** — no business routes; use `app_factory` / `router_registry`.

---

## Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| Files / functions | `snake_case` | `bot_service.py`, `get_scenario` |
| Classes | `PascalCase` | `StepfunRealtimeHandler` |
| Constants | `UPPER_SNAKE_CASE` | `SALES_WS_AUTH_POLICY` |
| Private | `_prefix` | `_handle_upstream_event` |
| HTTP prefix | `/api/v1` | All REST routers |
| WS paths | `/ws/{scenario}` | `/ws/sales`, `/ws/presentation`, `/ws/curriculum/examiner` |

---

## Examples

Well-organized modules to copy:

| Pattern | Reference files |
|---------|-----------------|
| Thin API + service | `sales_bot/api/scenarios.py`, `sales_bot/services/bot_service.py` |
| WebSocket decomposition | `sales_bot/websocket/stepfun_realtime_handler.py`, `stepfun_realtime_upstream.py` |
| Shared kernel | `common/error_handling/result.py`, `common/api/response.py` |
| App wiring | `app_factory.py`, `router_registry.py`, `websocket_routes.py` |

---

## Anti-Patterns

- Putting scenario-specific logic in `common/`.
- Re-enabling legacy sales handlers (legacy runtime is disabled per `sales_bot/AGENTS.md`).
- Using `@app.on_event("startup")` instead of lifespan in `app_lifespan.py`.
- Synchronous DB or `session.query()` (see Database Guidelines).
