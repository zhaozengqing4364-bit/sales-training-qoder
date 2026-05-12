# 2026-05-10 StepFun-only Sales Training Flow Preflight Baseline

Generated: `2026-05-10 21:10:09 CST`  
Parent PRD: `#7`  
Slice: `#8` — StepFun-only 迁移预检与基线锁定  
Baseline HEAD: `d41d4a10461e53f0e3b476eefb8d9c6f578c1a04`

## Scope

This is a preflight and baseline-lock artifact only. It does not change runtime behavior. The goal is to make the StepFun-only Sales Training Flow migration safe by listing current legacy entrypoints, delete candidates, shared services that must not be removed, Presentation Training Flow regression boundaries, and verification command results before implementation slices #9-#22 begin.

## Git / Worktree Snapshot

`git status --short --branch` showed existing uncommitted work before this baseline document was created. Those changes are not part of slice #8 and were not modified by this slice.

```text
## main...origin/main
 M AGENTS.md
 M DELIVERY_STATE.md
 M backend/src/common/knowledge/models.py
 M backend/src/common/knowledge/schemas.py
 M backend/src/common/knowledge/service.py
 M backend/tests/contract/test_knowledge_dictionary_contract.py
 M backend/tests/integration/test_knowledge_api.py
 M backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
 M docs/api-contract/knowledge.md
 M web/src/app/admin/knowledge/[id]/page.test.tsx
 M web/src/app/admin/knowledge/[id]/page.tsx
 M web/src/lib/api/client.ts
 M web/src/lib/api/types.ts
?? .sisyphus/
?? CONTEXT.md
?? backend/alembic/versions/20260510_0900_040_kb_dictionary_extraction_metadata.py
?? backend/src/common/knowledge/dictionary_extractor.py
?? backend/tests/unit/common/test_dictionary_extractor.py
```

`git diff --check` passed in the same command sequence.

## Sales Training Flow Legacy Entrypoints

| Surface | Current entrypoint | Baseline finding |
| --- | --- | --- |
| Sales WebSocket routing | `backend/src/sales_bot/websocket/router.py` | `/ws/sales` and `/ws/sales/{session_id}` accept `voice_mode`; persisted `PracticeSession.voice_mode` selects StepFun vs enhanced legacy path. |
| Sales WS default | `backend/src/sales_bot/websocket/router.py` | `_default_voice_mode()` falls back to `legacy` when `DEFAULT_VOICE_MODE` is unset. This conflicts with the StepFun-only target. |
| Sales StepFun path | `backend/src/sales_bot/websocket/router.py` | `stepfun_realtime` routes to `create_stepfun_realtime_handler()`. |
| Sales legacy path | `backend/src/sales_bot/websocket/router.py` | Any non-StepFun persisted mode routes to `create_enhanced_sales_handler()`. |
| DB model default | `backend/src/common/db/models.py` | `PracticeSession.voice_mode` currently has Python default `legacy` and check constraint allowing `legacy` or `stepfun_realtime`. |
| Voice runtime policy | `backend/src/sales_bot/services/voice_runtime_policy.py` | Env fallback policy defaults to `stepfun_realtime`, creating a default mismatch with sales WS routing and DB model defaults. |
| Frontend runtime lock | `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts` | `normalizeVoiceMode()` treats anything except `stepfun_realtime` as `legacy`. |
| Frontend WebSocket hook | `web/src/hooks/use-practice-websocket.ts` | Hook default is `voiceMode = "legacy"`; URL transport passes `voice_mode` to the backend. |
| Frontend sales entry | `web/src/app/(dashboard)/agents/[agentId]/page.tsx` | UI still exposes legacy/StepFun voice mode selection and can start sales practice with `voice_mode=legacy`. |
| Admin runtime config | `backend/src/admin/api/voice_runtime.py`, `web/src/app/admin/voice-runtime/page.tsx` | Voice runtime profiles still allow `legacy` and `stepfun_realtime`; this must be handled by later slices, not by #8. |

## Legacy Delete Candidates and Shared-Service Boundary

### Delete candidates after references are cleared

| Candidate | Reason | Gate before deletion |
| --- | --- | --- |
| `backend/src/sales_bot/websocket/enhanced_handler.py` | Enhanced legacy Sales ASR/LLM/TTS path. | `/ws/sales` must no longer route to it; tests must cover StepFun-only behavior. |
| `backend/src/sales_bot/websocket/base_sales_handler.py` | Base for legacy Sales handlers, not the StepFun handler base. | Confirm no remaining sales or test imports except deliberate historical tests. |
| `backend/src/sales_bot/websocket/simple_handler.py` | Deprecated simple legacy Sales handler. | Remove or migrate remaining tests that instantiate `SimpleSalesHandler`. |
| `backend/src/sales_bot/websocket/sales_handler.py.deprecated` | Already marked deprecated. | Confirm no import or runtime reference. |

### Must retain or review, not blindly delete

| Surface | Decision | Reason |
| --- | --- | --- |
| `voice_runtime_policy.py` | Retain / refactor only with tests. | Policy resolution is shared by session creation and admin voice-runtime configuration. |
| `transcript_normalization.py` | Retain. | Conversation evidence/report flows may still need normalized transcript shape. |
| `summary_service.py` | Retain. | Session summary/report orchestration can be shared outside legacy WS handlers. |
| `bot_service.py` | Review before deletion. | Contains legacy bot-session cleanup, but may still be referenced by common practice APIs. |
| `common/websocket/base_handler.py` | Retain. | Generic WebSocket base, not legacy Sales-specific. |
| `common/conversation/**` | Retain. | Evidence, replay, and report projection infrastructure. |
| `common/effectiveness/**` | Retain. | Existing score/effectiveness snapshot remains part of the minimum EvaluationRun bridge. |
| `common/knowledge/kb_lock_guard.py` | Retain. | StepFun paths enforce KB-lock safety. |

## Presentation Training Flow Regression Boundary

Presentation Training Flow is outside the legacy-sales deletion scope. It still shares StepFun code and therefore must be protected while Sales becomes StepFun-only.

| Boundary | Baseline finding |
| --- | --- |
| `backend/src/websocket_routes.py` | Presentation WebSocket routing has its own voice-mode switch and also falls back to `legacy` when `DEFAULT_VOICE_MODE` is unset. |
| `PresentationStepFunRealtimeHandler` | Inherits from the Sales `StepFunRealtimeHandler`; StepFun handler changes can regress Presentation. |
| `PresentationWebSocketHandler` | Legacy Presentation handler is not part of this Sales-only deletion track. |
| Minimum regression command | `cd backend && .venv-test/bin/python -m pytest tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_presentation_handler_persistence.py -q --no-cov` |

## Baseline Command Results

| Check | Command | Result | Classification |
| --- | --- | --- | --- |
| Git baseline | `git status --short --branch && git rev-parse HEAD && git diff --check` | PASS for HEAD capture and whitespace; worktree already dirty with unrelated changes. | Baseline fact |
| Sales StepFun/router tests | `cd backend && .venv-test/bin/python -m pytest tests/unit/test_sales_websocket_router.py tests/unit/test_stepfun_realtime_persistence.py -q --no-cov` | PASS: 18 passed, 1 warning. | Current green baseline |
| Frontend runtime tests | `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/transport.test.ts' --reporter=dot` | PASS: 3 files, 26 tests. | Current green baseline |
| Frontend typecheck | `pnpm --dir web exec tsc --noEmit --pretty false` | PASS: no output, exit code 0. | Current green baseline |
| OpenAPI runtime parity | `cd backend && .venv-test/bin/python -m pytest tests/unit/common/test_route_integrity.py -q --no-cov` | FAIL: 5 passed, 1 failed. `test_committed_openapi_contract_matches_runtime_paths` reports runtime paths missing from committed OpenAPI, including knowledge dictionary and supervisor routes. | Existing contract baseline failure; must not be confused with StepFun migration regression. |
| Presentation regression | `cd backend && .venv-test/bin/python -m pytest tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_presentation_handler_persistence.py -q --no-cov` | PASS: 40 passed, 1 warning. | Current green baseline |
| Frontend production build | `pnpm --dir web build` | PASS: Next.js build completed and generated 39 static pages. | Current green baseline |
| Backend full test suite | `cd backend && .venv-test/bin/python -m pytest -q --no-cov` | FAIL during collection: `ModuleNotFoundError: No module named 'alembic.config'` in `tests/unit/common/test_alembic_migration_graph.py`; 1896 items collected before interruption, 1 skipped. | Environment/dependency baseline failure. |

## HITL Stop Gate

Before #9-#22 modify runtime behavior, a maintainer should accept these scope decisions:

- Sales legacy deletion scope is limited to Sales legacy handler paths and their proven Sales-only dependencies.
- Shared services listed above must be retained unless a later issue proves they have no live references.
- Presentation Training Flow is not in the deletion scope; it remains protected by the Presentation regression command.
- OpenAPI parity currently has a known failure unrelated to StepFun migration and must be tracked separately or fixed before claiming a full release gate.
- Backend full-suite collection currently has an Alembic dependency failure; targeted StepFun/router/Presentation baselines are green.

## Next Slice Gate

#9 can start only after this baseline is reviewed. Its first implementation target should be preventing new Sales Training Flow sessions from persisting or selecting `legacy`, while keeping historical/read-only compatibility explicit and preserving the Presentation boundary above.
