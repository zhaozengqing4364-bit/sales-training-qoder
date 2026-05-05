# API Routing Audit

Generated on: 2026-05-06

## Scope

This audit covers Phase 1.1: OpenAPI paths, mounted FastAPI router sources, permission dependencies, and frontend API-call mapping. It is evidence-only for this atomic task. Route fixes and contract migrations are tracked as later atomic tasks in `DELIVERY_STATE.md`.

## Implementation-Before-Coding Judgment

- Stable code logic: route registration must be centralized through `backend/src/app_factory.py`, `backend/src/router_registry.py`, `backend/src/http_routes.py`, and `backend/src/websocket_routes.py`; frontend API calls should remain concentrated in `web/src/lib/api/*` plus websocket hooks.
- Configurable business rules: none introduced by this audit document.
- New configuration items: none.
- Reused configuration items: existing API base configuration (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`) and existing backend environment-based auth/CORS settings were only observed.
- Configuration read location: frontend API base is read in `web/src/lib/api/client.ts`; websocket base is read in `web/src/hooks/websocket/types.ts`.
- Configuration manager: not changed in this atomic task.
- Configuration validation: not changed in this atomic task.
- Configuration missing fallback: current frontend defaults are `http://localhost:3444/api/v1` and `ws://localhost:3444`; this audit does not alter them.
- Configuration illegal handling: not changed in this atomic task.
- Logic that must not be hardcoded during later fixes: permission mappings, scoring-ruleset routes, admin menu visibility, business copy, business thresholds, and route aliases that product/operations may need to manage.

Based on the currently inspected code, the existing configuration and RBAC systems are only partially confirmed. There are `common/business_rules`, `admin/settings`, `admin/api/permissions.py`, and governance inventory surfaces, but persistent multi-role RBAC tables and full admin UI are not yet confirmed in the actual routing surface.

## Evidence Commands

- Actual mounted routes:
  - `cd backend && PYTHONPATH=src ./.venv-test/bin/python - <<'PY' ... create_app(); iterate APIRoute/WebSocketRoute ... PY`
- OpenAPI contract:
  - `specs/001-ai-practice-system/contracts/openapi.yaml`
- Backend router source scan:
  - `rg -n "FastAPI\\(|APIRouter\\(|include_router|@[^\\n]*\\.(get|post|put|patch|delete|websocket)\\(" backend/src backend/tests specs -g '*.py' -g '*.yaml'`
- Permission dependency scan:
  - `rg -n "Depends\\(|Security\\(|require_|current_user|get_current_user|permission|permissions|role|roles|admin|403|HTTPException\\(" backend/src -g '*.py'`
- Frontend call scan:
  - `rg -n "fetch\\(|apiFetch|request<|/api/|WebSocket|buildPracticeWebSocketUrl" web/src -g '*.ts' -g '*.tsx'`

## Summary

| Metric | Count | Evidence |
| --- | ---: | --- |
| Runtime route entries | 315 | `create_app()` APIRoute/WebSocketRoute export |
| Runtime `/api/v1` HTTP routes | 309 | `create_app()` APIRoute export |
| Runtime WebSocket routes | 4 | `/ws/sales`, `/ws/sales/{session_id}`, `/ws/presentation`, `/ws/presentation/{session_id}` |
| OpenAPI operations | 18 | `specs/001-ai-practice-system/contracts/openapi.yaml` |
| OpenAPI operations missing in backend | 1 | `POST /api/v1/auth/wechat` |
| Backend routes missing from OpenAPI | 291 | Contract is materially stale compared with runtime routes |
| Concentrated frontend call sites scanned | 231 | `web/src/lib/api/*`, websocket hooks, server auth/performance helpers |
| Frontend path mismatches found by static scan | 10 raw hits | Most are dynamic-query false positives; confirmed actionable items are listed below |

## Router Sources and Permission Dependencies

| Route family | Mounted prefix | Router source | Permission dependency observed | Frontend/API consumer |
| --- | --- | --- | --- | --- |
| Core health/auth fallback | `/health`, `/metrics`, `/api/v1/auth/dev-login` | `backend/src/http_routes.py` | dev-login uses `get_db`; production disabled by `is_dev_login_enabled()` | `web/src/lib/api/client.ts`, login fallback page |
| Auth | `/api/v1/auth/*` | `backend/src/common/auth/api.py` via `router_registry.py` | login/providers public; logout uses `get_current_user` | `web/src/lib/api/client-domains.ts`, `web/src/app/(auth)/login/page.tsx` |
| Presentations user API | `/api/v1/presentations*` | `presentation_coach.api.presentations` via `router_registry.py` | router-level `require_role(["admin", "user"])`, endpoint-level `get_current_user` or `get_current_admin_user` | `web/src/lib/api/client-domains.ts`, `web/src/lib/api/client.ts` |
| Practice sessions | `/api/v1/practice/sessions*`, `/api/v1/practice/history*`, `/api/v1/sessions/stats` | `backend/src/common/api/practice.py` | router-level `require_role(["admin", "user"])`; ownership checks in practice endpoints | `web/src/lib/api/client-domains.ts`, `web/src/lib/api/client.ts`, audio upload hook |
| Replay/session evidence | `/api/v1/sessions/{session_id}/*` | `backend/src/common/conversation/api.py` | `get_current_user`, ownership checks in route handlers | report/replay pages and `web/src/lib/api/client-domains.ts` |
| Analytics user API | `/api/v1/analytics/*`, `/api/v1/practice/history/statistics`, `/api/v1/practice/history/trends` | `backend/src/common/api/analytics.py` | mostly `get_current_user`; storage stats uses `get_current_admin_user` | dashboard analytics client methods |
| Dashboard/growth/training/scenarios | `/api/v1/dashboard/*`, `/api/v1/growth/*`, `/api/v1/training-categories`, `/api/v1/scenarios*` | `common.api.dashboard`, `growth`, `training`, `sales_bot.api.scenarios` | role checks for growth/training/scenarios; dashboard uses `get_current_user` | dashboard/training pages |
| Business rules user/admin | `/api/v1/business-rules/*`, `/api/v1/admin/business-rules/*` | `common.api.business_rules`, `admin.api.business_rules` | user active route uses `require_role(["admin", "user"])`; publish/rollback/disable use `require_admin_permission(BUSINESS_RULE_PUBLISH_PERMISSION)` | `web/src/lib/api/client.ts`, `web/src/lib/api/sales-combinations.ts` |
| Admin users/training records/logs/interventions/analytics | `/api/v1/admin/users*`, `/api/v1/admin/training-records*`, `/api/v1/admin/system-logs*`, `/api/v1/admin/interventions*`, `/api/v1/admin/analytics*` | `backend/src/admin/api/*.py` via `router_registry.py` | mostly `get_current_admin_user` and/or `get_current_admin_user_for_app_routes` | admin pages/client methods |
| Admin governance/settings | `/api/v1/admin/governance/*`, `/api/v1/admin/settings/*` | `backend/src/admin/api/governance.py`, `settings.py` | governance uses `get_current_admin_user`; settings uses `require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)` | admin governance/settings pages |
| Admin knowledge/RAG/knowledge answer | `/api/v1/admin/knowledge*`, `/api/v1/admin/knowledge-bases*`, `/api/v1/admin/rag-profiles*`, `/api/v1/admin/knowledge-answer*`, `/api/v1/knowledge-debug*` | `common.knowledge.api`, `admin.api.rag_profiles`, `admin.api.knowledge_answer_config`, `common.api.knowledge_debug` | admin knowledge uses app-route admin guard plus endpoint `get_current_user`; RAG/knowledge-answer use admin guards; knowledge-debug allows admin/support | admin knowledge UI and debug panels |
| Agent/persona admin and user APIs | `/api/v1/admin/agents*`, `/api/v1/admin/personas*`, `/api/v1/agents*` | `backend/src/agent/api/*.py` | mixed: some admin routes use `get_current_user`; personas/agent-persona routes use `get_current_admin_user` | admin agent/persona pages and learner training selection |
| Model/voice/presentation AI config | `/api/v1/admin/model-configs*`, `/api/v1/admin/voice-runtime*`, `/api/v1/admin/presentation-ai*` | `backend/src/admin/api/model_configs.py`, `voice_runtime.py`, `presentation_ai.py` | model configs/presentation AI use admin guards and some fine-grained helpers; voice runtime currently uses `get_current_user` | admin config pages |
| Prompt templates/scenario prompts | `/api/v1/prompt-templates*`, `/api/v1/scenario-prompts*` | `backend/src/prompt_templates/api/routes.py` | `get_current_user` plus manual admin-only guard `_require_prompt_admin_or_error` | admin prompt pages |
| Evaluation/report/scoring rulesets | `/api/v1/evaluation/*` | `backend/src/evaluation/api.py`; includes `admin_scoring_rulesets_router` | report/feedback use `get_current_user`; scoring rulesets use `require_admin_permission(SCORING_RULESET_MANAGE_PERMISSION)` | report pages and admin scoring-rulesets client |
| WebSockets | `/ws/sales*`, `/ws/presentation*` | `backend/src/websocket_routes.py`, `backend/src/sales_bot/websocket/router.py` | auth resolved in websocket handlers; query token compatibility is environment controlled | `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/websocket/transport.ts` |

## OpenAPI Contract Findings

| Finding | Current evidence | Impact | Required action |
| --- | --- | --- | --- |
| OpenAPI contains `POST /api/v1/auth/wechat`, but backend mounts WeCom auth as `/api/v1/auth/wecom/start` and `/api/v1/auth/wecom/callback`. | `openapi.yaml` has `/auth/wechat`; runtime route export has no `/api/v1/auth/wechat`. | Contract consumers generated from the spec call a missing route. | Phase 1.2: either update spec to WeCom start/callback contract or add a compatibility endpoint if product requires old `/auth/wechat`. |
| OpenAPI has only 18 operations while backend exposes 309 `/api/v1` HTTP routes. | Runtime export vs `openapi.yaml`. | Contract consistency cannot be claimed; most admin/practice/replay/scoring APIs are undocumented in the committed spec. | Phase 1.2: regenerate or expand OpenAPI from FastAPI runtime and decide whether specs/001 remains historical or authoritative. |
| Runtime backend exposes many endpoints absent from spec, including scoring rulesets, replay, admin users, admin business rules, admin knowledge, prompt templates, model configs, and release verification. | `BACKEND_MISSING_SPEC_COUNT 291`. | Frontend and tests rely on undocumented endpoints. | Phase 1.2/Phase 2: move to runtime-generated OpenAPI or commit updated contract sections per domain. |

## Frontend Call Mapping

| Frontend surface | Representative frontend paths | Runtime backend status | Notes |
| --- | --- | --- | --- |
| Auth | `/auth/login`, `/auth/logout`, `/auth/providers`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/dev-login` | Mounted | WeCom start/callback are used through provider payload from `/auth/providers`, not a hardcoded `/auth/wechat` frontend call. |
| Practice/session/replay | `/practice/sessions`, `/practice/sessions/{id}/lifecycle`, `/sessions/{id}/replay`, `/sessions/{id}/messages`, `/sessions/{id}/audio*` | Mounted | Static scanner false positives came from dynamic query-template strings; manual route check confirms matching runtime routes. |
| Presentations | `/presentations`, `/presentations/{id}`, `/presentations/{id}/replace`, `/presentations/{id}/pages`, `/presentations/{id}/forbidden-words`, `/admin/forbidden-words/{id}` | Mounted | OpenAPI lacks runtime-only replace/progress/thumbnail/admin delete details. |
| Admin business rules | `/admin/business-rules/*` | Mounted | Publish/rollback use fine-grained `business_rule.publish`; frontend uses current route family. |
| Admin scoring rulesets | `/evaluation/admin/scoring-rulesets*` | Mounted at old path only | Target route `/api/v1/admin/scoring-rulesets` is not mounted; frontend still calls old path. This is a Phase 2.1/2.2 migration item. |
| Admin knowledge/RAG/model/voice/settings | `/admin/knowledge*`, `/admin/rag-profiles*`, `/admin/model-configs*`, `/admin/voice-runtime*`, `/admin/settings*` | Mounted | Voice runtime route family currently appears to rely on `get_current_user`, requiring RBAC hardening in Phase 2. |
| Prompt governance | `/prompt-templates*`, `/scenario-prompts*` | Mounted | Router prefix already includes `/api/v1`; `router_registry.py` includes without extra prefix, which is correct. |
| WebSocket | `/ws/sales?session_id=...`, `/ws/presentation?session_id=...` | Mounted | Frontend builds query-style URLs; backend supports query and path-style modes. |

## Actionable Routing Issues

| ID | Severity | Issue | Evidence | Phase |
| --- | --- | --- | --- | --- |
| R1 | High | Committed OpenAPI spec is stale and missing 291 runtime routes. | `BACKEND_MISSING_SPEC_COUNT 291`; `openapi.yaml` has 18 operations. | Phase 1.2 |
| R2 | High | OpenAPI declares `POST /api/v1/auth/wechat`, which is not mounted. | `SPEC_MISSING_BACKEND ('POST', '/api/v1/auth/wechat')`. | Phase 1.2 |
| R3 | High | Required target scoring-ruleset admin path `/api/v1/admin/scoring-rulesets` is absent; only `/api/v1/evaluation/admin/scoring-rulesets` is mounted. | Runtime flags: `HAS_NEW_SCORING_ROUTE False`, `HAS_OLD_SCORING_ROUTE True`; frontend calls old path in `web/src/lib/api/client.ts`. | Phase 2.1/2.2 |
| R4 | Medium | Several admin route families are admin-scoped by path but still use generic `get_current_user` or transitional guards. | Runtime admin permission counts: `admin_user=150`, `generic_user=16`, `fine_grained=22`; `admin.api.permissions.py` documents role rollout is not persisted yet. | Phase 2.2/2.3 |
| R5 | Medium | `web/src/lib/api/sales-combinations.ts` still contains client default sales-combination rule data and user-facing fallback copy. | `CLIENT_DEFAULT_SALES_COMBINATIONS_V1`, `formatSalesCombinationFallbackReason`. | Phase 5.1 |

## Current Scoring Ruleset Contract Detail

| Capability | Current route | Target route | Current permission | Frontend status |
| --- | --- | --- | --- | --- |
| list | `GET /api/v1/evaluation/admin/scoring-rulesets` | `GET /api/v1/admin/scoring-rulesets` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |
| active | `GET /api/v1/evaluation/admin/scoring-rulesets/active` | `GET /api/v1/admin/scoring-rulesets/active` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |
| create | `POST /api/v1/evaluation/admin/scoring-rulesets` | `POST /api/v1/admin/scoring-rulesets` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |
| update | `PUT /api/v1/evaluation/admin/scoring-rulesets/{ruleset_id}` | `PUT /api/v1/admin/scoring-rulesets/{ruleset_id}` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |
| publish | `POST /api/v1/evaluation/admin/scoring-rulesets/{ruleset_id}/publish` | `POST /api/v1/admin/scoring-rulesets/{ruleset_id}/publish` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |
| rollback | `POST /api/v1/evaluation/admin/scoring-rulesets/{ruleset_id}/rollback` | `POST /api/v1/admin/scoring-rulesets/{ruleset_id}/rollback` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |
| dry-run | `POST /api/v1/evaluation/admin/scoring-rulesets/dry-run` | `POST /api/v1/admin/scoring-rulesets/dry-run` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |
| audit logs | `GET /api/v1/evaluation/admin/scoring-rulesets/audit-logs` | `GET /api/v1/admin/scoring-rulesets/audit-logs` | `require_admin_permission(scoring_ruleset.manage)` | Calls old route |

## Verification Notes

- No business functionality was modified in this atomic task.
- The scan did not rely on proxy success signals; it instantiated the actual FastAPI application and enumerated mounted routes.
- Static frontend mismatch count includes dynamic-query false positives, so actionable frontend items were manually checked against surrounding code before listing.
- Warnings during app instantiation reported missing optional `python-pptx` and `Pillow`; they do not block route enumeration but may affect Phase 4 PPT fixture work.
