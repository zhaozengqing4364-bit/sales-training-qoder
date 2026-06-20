# Expansion Log

## Phase 0

Core question: 当前 AI 高速开发后的项目架构是否已经混乱；哪里混乱；应该按什么顺序治理。

Axes:
- backend runtime boundaries: FastAPI app factory, router registry, WebSocket routes, runtime/session services.
- frontend surfaces: Next App Router pages, admin/user/dashboard routes, API client/types, hooks.
- data and operations: Alembic migrations, ORM models, backend scripts, root scripts.
- testing and release gates: pytest/vitest/playwright/critical-quality-gate coverage and gaps.
- docs and planning entropy: AGENTS/CLAUDE/Trellis/docs/audits/task pile.
- churn and complexity hotspots: recent git churn, large files, compatibility/backfill/fallback density.

Codebase relevant: yes. External: no. Browsing: no. Verification likely: yes, by local command execution. Report requested: no, synthesis markdown.

## Wave 1

Spawned:
- backend runtime/service coupling researcher: `019ee48f-6a2f-7710-87e5-2e7ae901fcc1`
- frontend route/API coupling researcher: `019ee48f-956d-7d60-9d56-528fb924c101`

Direct verification commands:
- `rg --files ... | awk ...` for repository file/type counts.
- `wc -l` over `*.py/*.ts/*.tsx` for large-file hotspots.
- Python AST import scan for backend cross-domain imports.
- `git log --since='30 days ago' --numstat` for churn hotspots.
- `alembic heads` for migration head count.
- `find backend/tests web/src web/tests ...` for test inventory.
- `rg TODO/FIXME/legacy/deprecated/compat/backfill/fallback` for compatibility debt.

Leads opened:
- LEAD: cross-domain imports break declared module isolation — WHY: sales_trainer/curriculum_practice/evaluation depend on each other beyond `common` — ANGLE: identify anti-corruption/adapters.
- LEAD: frontend API type/client files are giant aggregation points — WHY: `web/src/lib/api/types.ts` and `client.ts` dominate line counts — ANGLE: split by generated/domain contracts.
- LEAD: WebSocket realtime debt is already documented and still active — WHY: audit file identifies inheritance/mixin coupling and protocol drift — ANGLE: convert to staged runtime boundary plan.
- LEAD: scripts and seeds mutate state heavily — WHY: large seed/repair scripts and many compatibility paths — ANGLE: require dry-run/count/idempotency.
- LEAD: dirty working tree is too large for safe architecture work — WHY: 84 tracked modifications + 35 untracked files — ANGLE: freeze/stabilize before refactor.

## Worker returns

Backend runtime/service coupling researcher returned:
- HTTP composition root: `backend/src/app_factory.py` -> `register_http_routes`, `register_routers`, `register_websocket_routes`.
- Largest backend coupling center: `backend/src/router_registry.py`, mixing contributor registration, RBAC route mounting, legacy aliasing.
- WebSocket coupling center: `backend/src/websocket_routes.py`, mixing presentation session ownership, runtime admission, handler selection, and registering sales/curriculum/presentation websocket routers.
- Shared kernel candidates: `common/services/runtime_gate.py`, `common/services/practice_session_ports.py`.
- Prompt governance is cross-domain kernel, not isolated feature: `prompt_templates/service.py` is used by `evaluation` and `sales_trainer`.

Frontend route/API coupling researcher returned:
- `web/src/app/(dashboard)/sales-trainer/business-skills/page.tsx` is the largest sales-trainer page-owned business logic hotspot.
- `web/src/app/admin/sales-trainer/paths/page.tsx` owns save/publish/rollback flow in route layer.
- `web/src/app/admin/sales-trainer/questions/page.tsx` owns question governance status transitions in route layer.
- `web/src/lib/api/domains/sales-trainer.ts`, `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts` form the main API/type coupling chain.
- Tests exist around many pages, but tests have not prevented page-owned rule growth.
