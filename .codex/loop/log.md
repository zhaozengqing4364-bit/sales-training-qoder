- time: 2026-04-12T05:34:02+08:00
  mode: grow
  item id: M017-S02-T02
  files changed:
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Tightened the practice websocket outbound orchestration seam so reconnect now starts a fresh transport epoch, queued outbound messages no longer leak across reconnect, and interrupt clears both queued outbound work and local backpressure/slow-state flags.
  verification commands:
    - npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts
    - npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"
    - lsp diagnostics web/src/hooks/use-practice-websocket.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.test.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  verification results: passed; the new red-first websocket proofs finished green (17/17 on the focused hook suite), the exact task-plan web verification gate finished 30/30 green across hook/presentation/page surfaces, and diagnostics stayed clean on the touched hook/test files.
  success signal status: future agents can now tell reconnect/backpressure/interrupt regressions apart from downstream runtime problems because stale outbound intent no longer replays after reconnect and interrupt immediately resets the discarded local backlog state.
  rollback note: if later S02/T03 work extracts helpers, preserve the fresh-transport-epoch rule and keep interrupt responsible for clearing queued outbound work plus local backpressure flags; otherwise reconnect can silently replay stale intent against a restored session.

- time: 2026-04-12T05:25:37+08:00
  mode: grow
  item id: M017-S02-T01
  files changed:
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - web/src/hooks/use-practice-websocket.presentation-flow.test.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the real practice-websocket seam instead of doing a size-driven refactor: the hook now documents that it owns transport lifecycle, binary negotiation, outbound backpressure buffering/flush, and interrupt pre-cleanup, while focused tests prove runtime state changes still come back from inbound status/reconnected/interrupted/backpressure messages.
  verification commands:
    - rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts
    - npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts"
    - lsp diagnostics web/src/hooks/use-practice-websocket.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.test.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  verification results: passed; the exact task-plan rg inventory now surfaces the explicit boundary map plus focused reconnect/backpressure/interrupt/binary proofs, the impacted websocket hook suites finished 18/18 green, and diagnostics stayed clean on the touched hook/test files.
  success signal status: future agents can now start S02/T02 from one explicit seam — outbound orchestration pressure lives in use-practice-websocket, while inbound runtime truth continues to flow through websocket/message-handlers; even presentation control:start is now proved to require backend status before sessionStatus flips to in_progress.
  rollback note: if later S02 work extracts helpers from use-practice-websocket, keep reconnect budget, binary negotiation, pending-outbound flush, backpressure buffer ownership, and interrupt pre-cleanup on the same coordinator seam; do not split start/pause/resume or interrupt state transitions into local optimistic state that bypasses backend status/reconnected confirmation.

- time: 2026-04-12T04:27:39+08:00
  mode: grow
  item id: M016-S03-T02
  files changed:
    - backend/src/common/monitoring/logger.py
    - backend/src/common/auth/api.py
    - backend/src/common/auth/service.py
    - backend/src/admin/api/admin.py
    - backend/src/admin/api/analytics.py
    - backend/src/admin/api/release_verification.py
    - backend/src/admin/api/system_logs.py
    - backend/src/admin/api/training_records.py
    - backend/src/admin/api/security_inventory.py
    - backend/src/common/monitoring/log_safety_inventory.py
    - backend/tests/integration/test_admin_users_api.py
    - backend/tests/unit/admin/test_admin_users_api_models.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Explicitly closed the M016/S03 fix-first admin and logging seams by moving five legacy admin router modules onto get_current_admin_user, centralizing token/password/cookie/email redaction in the shared structured logger, switching auth logging to structured masked fields, and refreshing the code-owned security inventories to reflect the now-green baseline.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k "admin_router_modules_require_admin_even_without_main_router_guard" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k "sanitize_log_kwargs" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q
    - lsp diagnostics backend/src/common/monitoring/logger.py
    - lsp diagnostics backend/src/common/auth/api.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/src/admin/api/admin.py
    - lsp diagnostics backend/src/admin/api/analytics.py
    - lsp diagnostics backend/src/admin/api/release_verification.py
    - lsp diagnostics backend/src/admin/api/system_logs.py
    - lsp diagnostics backend/src/admin/api/training_records.py
    - lsp diagnostics backend/src/admin/api/security_inventory.py
    - lsp diagnostics backend/src/common/monitoring/log_safety_inventory.py
    - lsp diagnostics backend/tests/integration/test_admin_users_api.py
    - lsp diagnostics backend/tests/unit/admin/test_admin_users_api_models.py
  verification results: passed; the isolated-router RBAC regression proof finished 5/5 green, the shared logger redaction unit proof finished 2/2 green, the exact task-plan pytest gate finished 33/33 green, and diagnostics stayed clean on the touched backend/runtime/test files.
  success signal status: future agents can now trust the admin security baseline from the code itself — the fix-first routers stay admin-only even when mounted without main.py wrapper dependencies, shared logging strips token/password/cookie/email fields before emission, auth logs preserve observability with masked structured fields, and the code-owned inventories no longer advertise unresolved fix-first surfaces.
  rollback note: if later work changes admin mounting or adds new structured log sinks, keep the router-local get_current_admin_user declarations, logger sanitizer, inventory files, and the isolated-router/log-redaction tests aligned together; otherwise main.py can hide a module-level RBAC gap and new sinks can bypass redaction by drift.

- time: 2026-04-12T04:14:30+08:00
  mode: grow
  item id: M016-S03-T01
  files changed:
    - backend/src/admin/api/security_inventory.py
    - backend/src/common/monitoring/log_safety_inventory.py
    - backend/src/common/auth/service.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the M016/S03 security baseline into code-owned inventories so downstream work can stop re-scanning the backend: one admin permission matrix now names the five legacy /admin route families still gated only by generic authentication, one sensitive-log inventory names the shared logger/auth sinks most likely to leak token/password/cookie/email fields, and the auth service now points future agents at those baselines instead of the stale string-detail drift note.
  verification commands:
    - rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth
    - python3 -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py backend/src/common/auth/service.py
    - backend/venv/bin/python -c 'import sys; sys.path.insert(0, "backend/src"); from admin.api.security_inventory import FIX_FIRST_ADMIN_ROUTE_FAMILIES; from common.monitoring.log_safety_inventory import FIX_FIRST_SENSITIVE_LOG_SURFACES; print(len(FIX_FIRST_ADMIN_ROUTE_FAMILIES), len(FIX_FIRST_SENSITIVE_LOG_SURFACES))'
    - lsp diagnostics backend/src/admin/api/security_inventory.py
    - lsp diagnostics backend/src/common/monitoring/log_safety_inventory.py
    - lsp diagnostics backend/src/common/auth/service.py
  verification results: passed; the task-plan grep gate finished cleanly with the new code-owned inventory surfaces present, py_compile succeeded on the new inventory/auth files, the backend venv imported the fix-first route/log lists successfully (5 route families, 4 log surfaces), and fresh diagnostics stayed clean on the touched Python files.
  success signal status: future S03 work now has one durable target list instead of a broad backend audit — fix-first RBAC work is narrowed to the five legacy get_current_user admin route families, and fix-first redaction work is narrowed to the shared logger/latency sinks plus auth logout/failure logging.
  rollback note: if later S03 tasks change which route families or sinks are first priority, update backend/src/admin/api/security_inventory.py, backend/src/common/monitoring/log_safety_inventory.py, the auth-service baseline note, and D194 together so the code-owned inventory does not drift from the actual repair plan.

- time: 2026-04-12T04:03:30+08:00
  mode: grow
  item id: M016-S02
  files changed:
    - backend/src/prompt_templates/api/routes.py
    - backend/src/presentation_coach/api/presentations.py
    - backend/src/common/auth/service.py
    - backend/src/common/api/practice.py
    - backend/tests/conftest.py
    - backend/tests/contract/test_presentations.py
    - web/src/lib/api/client.ts
    - web/src/lib/api/client.auth.test.ts
    - .gsd/DECISIONS.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M016/S02 after fresh slice-level verification confirmed the audited prompt-template, presentation, and auth dependency surfaces now share one stable error-contract seam, and the frontend API client keeps all of those failures on one ApiRequestError normalization path without page-local guessing.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
    - npm --prefix web test -- --run src/lib/api/client.auth.test.ts
    - lsp diagnostics backend/src/prompt_templates/api/routes.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/src/common/api/practice.py
    - lsp diagnostics backend/tests/conftest.py
    - lsp diagnostics backend/tests/contract/test_presentations.py
    - lsp diagnostics web/src/lib/api/client.ts
    - lsp diagnostics web/src/lib/api/client.auth.test.ts
  verification results: passed; the exact slice-plan backend gate finished 33/33 green, the focused frontend API-client auth suite finished 9/9 green, and diagnostics stayed clean on the touched backend/frontend authority files.
  success signal status: M016/S02 now gives downstream work one durable security/error-contract baseline — route-local audited 4xx failures expose top-level structured envelopes, dependency role/admin guards expose structured detail payloads, and frontend callers normalize both shapes through ApiRequestError.
  rollback note: if later admin-security work changes exception handling, keep `error_response(...)`/`build_server_error(...)`, `_raise_auth_http_error(...)`, `backend/tests/contract/test_presentations.py`, and `web/src/lib/api/client.auth.test.ts` aligned together; otherwise protected-route and not-found failures will drift back into mixed string-vs-envelope parsing.

- time: 2026-04-12T03:58:20+08:00
  mode: grow
  item id: M016-S02-T03
  files changed:
    - backend/src/common/auth/service.py
    - backend/tests/contract/test_presentations.py
    - web/src/lib/api/client.auth.test.ts
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added cross-end proof for the unified API error seam by locking presentation/admin role-guard responses to structured auth detail payloads and proving the frontend API client still normalizes those dependency failures through ApiRequestError without page-local parsing.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py -k "structured_detail_payload" -q
    - npm --prefix web test -- --run src/lib/api/client.auth.test.ts
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/tests/contract/test_presentations.py
    - lsp diagnostics web/src/lib/api/client.auth.test.ts
  verification results: passed; the new role-guard backend proof finished green, the focused frontend API-client auth suite finished 9/9 green including dependency-detail normalization, the slice verification command finished 33/33 green, and diagnostics stayed clean on the touched auth/test files.
  success signal status: backend dependency guards no longer leak raw-string 403 detail on presentation/admin routes, and frontend callers keep one stable ApiRequestError seam across dependency detail, route-local envelopes, and validation arrays.
  rollback note: if later auth or middleware work changes dependency-failure behavior, keep `get_current_user`/`get_current_admin_user`/`require_role(...)`, `backend/tests/contract/test_presentations.py`, and `web/src/lib/api/client.auth.test.ts` aligned together; otherwise admin/protected-route failures will silently fall back to generic HTTP_403 guessing.

- time: 2026-04-12T03:49:54+0800
  mode: grow
  item id: M016-S02-T02
  files changed:
    - backend/src/prompt_templates/api/routes.py
    - backend/src/presentation_coach/api/presentations.py
    - backend/src/common/auth/service.py
    - web/src/lib/api/client.ts
    - backend/tests/integration/test_prompt_templates_api_rbac.py
    - backend/tests/contract/test_presentations.py
    - backend/tests/integration/test_presentation_delete_permissions.py
    - web/src/lib/api/client.auth.test.ts
    - backend/tests/conftest.py
    - backend/src/common/api/practice.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Collapsed the audited backend/frontend error seam onto one stable contract by returning top-level error envelopes from prompt-template and presentation 4xx routes, structuring auth dependency failures, and teaching apiFetch plus segment-audio fetches to normalize route/detail/validation payloads into ApiRequestError.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_prompt_templates_api_rbac.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_delete_permissions.py -q
    - npm --prefix web test -- --run src/lib/api/client.auth.test.ts
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "kb_lock_chain_failures" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
    - lsp diagnostics backend/src/prompt_templates/api/routes.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics web/src/lib/api/client.ts
    - lsp diagnostics backend/src/common/api/practice.py
  verification results: passed; focused prompt-template/presentation/frontend client proof went green, the pre-existing knowledge-check NameError blocker in common/api/practice.py was fixed and re-proved, the slice verification command finished 31/31 green, and diagnostics stayed clean on the touched authority files.
  success signal status: frontend callers now get one stable ApiRequestError seam across top-level Result envelopes, auth dependency detail payloads, and FastAPI validation arrays, while audited prompt-template/presentation routes expose stable top-level error codes plus trace ids for support triage.
  rollback note: if later work changes the shared error helper or global HTTPException policy, keep route-local 4xx response envelopes, auth dependency structured detail, frontend normalization, and the focused contract tests aligned together; otherwise clients will fall back to stringified-dict guessing again.

- time: 2026-04-12T03:30:08+08:00
  mode: grow
  item id: M016-S02-T01
  files changed:
    - backend/src/prompt_templates/api/routes.py
    - backend/src/presentation_coach/api/presentations.py
    - backend/src/common/auth/service.py
    - web/src/lib/api/client.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the high-noise API error-contract drift map directly beside the live prompt-template, presentation, auth, and frontend client seams so downstream work can collapse the contract without re-inventorying the same surfaces.
  verification commands:
    - rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth
    - lsp diagnostics backend/src/prompt_templates/api/routes.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics web/src/lib/api/client.ts
  verification results: passed; the planned rg inventory still shows the intended drift surface, and fresh LSP diagnostics were clean on the four touched authority files after the seam writeback.
  success signal status: future M016/S02 work now has one explicit collapse map — prompt templates are the closest reusable backend seam, while presentations plain-string 403/404 branches, auth dependency HTTPExceptions, and the segment-audio client parser are the only hotspots that still leak error-shape drift.
  rollback note: if T02 chooses a different shared envelope, update the code-adjacent inventory notes, D191, and the knowledge entry together so the documented drift map still matches the real collapse target.

- time: 2026-04-12T03:19:18+08:00
  mode: grow
  item id: M016-S01-T03
  files changed:
    - backend/tests/integration/test_auth_login_api.py
    - backend/tests/integration/test_password_reset_api.py
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Expanded the focused auth recovery proof so the repo-root auth gate now covers reset success, expiry, reuse, same-IP rate limiting, and request-path DDL absence, while the dedicated reset suite also proves superseded-token rejection against the live lifecycle contract.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q
    - lsp diagnostics backend/tests/integration/test_auth_login_api.py
    - lsp diagnostics backend/tests/integration/test_password_reset_api.py
  verification results: passed; the repo-root auth gate finished 17/17 green, the dedicated password-reset suite finished 8/8 green, and diagnostics were clean on both focused proof files.
  success signal status: future agents can now prove forgot/reset health from focused backend tests alone — including successful reset handoff into managed credentials, expired/reused/superseded token rejection, rate limiting, and the absence of request-path auth DDL.
  rollback note: if later auth-recovery work changes handler ownership or token lifecycle semantics, update both focused proof files together so the repo-root auth gate and the dedicated reset lifecycle suite keep describing the same contract.

- time: 2026-04-12T03:08:13+08:00
  mode: grow
  item id: M016-S01-T01
  files changed:
    - backend/src/common/auth/api.py
    - backend/src/common/auth/service.py
    - backend/src/common/db/models.py
    - .gsd/KNOWLEDGE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Documented the narrow password-reset formalization boundary directly in the auth/model files and knowledge log so downstream work can target PasswordResetService + PasswordResetToken + Alembic 026/027 while keeping the current hashed_password-first login fallback stable.
  verification commands:
    - rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py
    - lsp diagnostics backend/src/common/auth/api.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/src/common/db/models.py
  verification results: passed; the planned rg inventory confirmed forgot/reset still lands on the existing auth/model seam without any auth-local CREATE TABLE path, and fresh LSP diagnostics were clean on backend/src/common/auth/api.py, backend/src/common/auth/service.py, and backend/src/common/db/models.py after the seam writeback.
  success signal status: M016/S01/T01 now has one explicit formalization boundary: future work can land on PasswordResetService + PasswordResetToken + Alembic 026/027 while preserving the hashed_password-first login compatibility rule instead of reopening JWT/session helpers or mistaking global startup create_all bootstrap for request-path auth DDL.
  rollback note: If later M016 work changes the auth recovery boundary, update the code-level seam notes in auth/api.py, auth/service.py, db/models.py, and the matching knowledge/decision entries together so migration authority and login fallback rules do not drift apart.


- time: 2026-04-12T02:52:25+08:00
  mode: grow
  item id: M015-S03
  files changed:
    - .gsd/DECISIONS.md
    - .gsd/milestones/M015/slices/S03/S03-SUMMARY.md
    - .gsd/milestones/M015/slices/S03/S03-UAT.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M015/S03 after fresh slice-level verification confirmed learner dashboard/auth/practice routes now share explicit route-level fallback shells, the durable learner route-error seam still reports correctly, and remaining responsive/timezone work is preserved as a focused deferred baseline instead of reopening shell scope.
  verification commands:
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts" "src/components/error-reporting.test.tsx" "src/app/(user)/practice/[sessionId]/error.test.tsx"
    - lsp diagnostics web/src/app/learner-shell-baseline.test.ts
  verification results: passed; the route-file inventory plus learner history/report/replay gate finished 41/41 green, the learner-shell baseline + route-error observability gate finished 8/8 green, and diagnostics were clean on the focused learner proof file.
  success signal status: M015/S03 is now closed on one durable learner-shell contract — group-level dashboard/auth loaders, live-practice fallback coverage, shared durable route-error reporting, and one proof file that future agents can rerun directly.
  rollback note: if later work changes learner route families or resolves the deferred responsive/timezone baseline, update web/src/app/learner-shell-baseline.test.ts, the matching knowledge entries, and this slice summary together so shell scope and proof do not drift.

- time: 2026-04-12T02:47:30+08:00
  mode: grow
  item id: M015-S03-T03
  files changed:
    - web/src/app/learner-shell-baseline.test.ts
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added one focused learner-shell baseline proof that scopes route-shell closure to learner-core routes, locks the shared a11y seam, and records the remaining responsive/timezone work as explicit deferred source facts instead of reopening shell scope.
  verification commands:
    - npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts"
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts" "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - lsp diagnostics web/src/app/learner-shell-baseline.test.ts
  verification results: passed; the new focused baseline proof finished 3/3 green, the slice inventory + learner regression gate finished 44/44 green, and diagnostics were clean on the new proof file.
  success signal status: learner fallback closure, route-shell a11y baseline, and deferred responsive/timezone facts are now all encoded in one focused learner test that future agents can rerun directly.
  rollback note: if later learner-shell work adds/removes route fallbacks or resolves the deferred responsive/timezone baseline, update web/src/app/learner-shell-baseline.test.ts and the matching knowledge entry together so the proof keeps matching the real scope.

- time: 2026-04-12T02:40:55+08:00
  mode: grow
  item id: M015-S03-T02
  files changed:
    - web/src/components/learner/learner-route-loading-state.tsx
    - web/src/components/learner/learner-route-loading-state.test.tsx
    - web/src/app/(auth)/loading.tsx
    - web/src/app/(auth)/error.tsx
    - web/src/app/(auth)/route-shells.test.tsx
    - web/src/app/(dashboard)/loading.tsx
    - web/src/app/(user)/practice/[sessionId]/loading.tsx
    - web/src/components/dashboard-skeleton.tsx
    - web/src/app/(user)/practice/[sessionId]/error.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added shared learner route-level loading/error shells across dashboard, auth, and live practice, plus a narrow-screen-safe dashboard skeleton baseline, so learner-core routes now fail or wait on explicit fallback surfaces instead of blanking.
  verification commands:
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort
    - npm --prefix web test -- --run "src/app/(auth)/route-shells.test.tsx" "src/components/learner/learner-route-loading-state.test.tsx"
    - npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - npm --prefix web test -- --run "src/components/error-reporting.test.tsx" "src/app/(user)/practice/[sessionId]/error.test.tsx"
  verification results: passed; the fallback inventory now shows the new dashboard/auth/practice route shells, the focused auth/loading seam tests finished 3/3 green, the task-plan learner regression command finished 41/41 green, and the route-error observability proof finished 5/5 green.
  success signal status: learner dashboard/auth/live-practice entry routes now have durable route-level fallback surfaces with accessible status semantics, and shared dashboard skeletons no longer force the previous edge-aligned header layout on narrow screens.
  rollback note: if later S03 work adds more learner page-local loaders, keep the default baseline on `(dashboard)/loading`, `(auth)/loading`, and `practice/[sessionId]/loading`; only introduce page-specific loaders when the route needs richer shape than the shared learner loading state.

- time: 2026-04-12T02:32:30+08:00
  mode: grow
  item id: M015-S03-T01
  files changed:
    - web/src/app/(dashboard)/history/loading.tsx
    - web/src/app/(user)/practice/[sessionId]/report/loading.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/loading.tsx
    - web/src/app/(auth)/login/page.tsx
    - web/src/app/(auth)/forgot-password/page.tsx
    - web/src/app/(auth)/reset-password/page.tsx
    - web/src/app/(auth)/login/page.test.tsx
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Established the learner fallback/baseline matrix for M015/S03, recorded the real learner-core gap list in T01-RESEARCH, and shipped the low-risk a11y subset now: existing loading shells announce status and auth forms/errors expose explicit labels/alerts.
  verification commands:
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort
    - npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx"
    - lsp diagnostics web/src/app/(auth)/login/page.tsx
    - lsp diagnostics web/src/app/(auth)/forgot-password/page.tsx
    - lsp diagnostics web/src/app/(auth)/reset-password/page.tsx
    - lsp diagnostics web/src/app/(dashboard)/history/loading.tsx
    - lsp diagnostics web/src/app/(auth)/login/page.test.tsx
  verification results: passed; the route-file scan confirmed the current fallback inventory used in the matrix, the focused auth suite finished 9/9 green after the label/alert updates, and diagnostics were clean on the touched auth/history files.
  success signal status: downstream S03 work now has one durable learner-core route matrix, one documented deferred responsive/timezone boundary, and one small shipped a11y baseline so T02 can focus on real fallback gaps instead of re-triaging scope.
  rollback note: if later S03 tasks add or remove learner-core routes, update the T01 research matrix and the learner-core scope rule in .gsd/KNOWLEDGE.md together; do not let `/support/runtime` or other role-gated dashboard pages drift into learner fallback closure by accident.

- time: 2026-04-12T02:17:45+08:00
  mode: grow
  item id: M015-S02
  files changed:
    - web/src/lib/auth-handler.ts
    - web/src/components/providers/app-providers.tsx
    - web/src/components/layout/dashboard-shell.tsx
    - web/src/components/layout/admin-shell.tsx
    - web/src/app/admin/records/page.tsx
    - web/src/app/admin/rag-profiles/page.tsx
    - web/src/app/admin/personas/[id]/page.tsx
    - web/src/lib/auth-handler.test.ts
    - web/src/app/admin/records/page.test.tsx
    - web/src/app/admin/rag-profiles/page.test.tsx
    - web/src/app/admin/personas/[id]/page.test.tsx
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M015/S02 after fresh slice-level verification confirmed native dialog and hard browser navigation are removed from the planned admin/learner business flows, with auth redirects, destructive confirms, and validation/save feedback all routed through shared authHandler/router/dialog/toast seams.
  verification commands:
    - rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src
    - node allowlist interruptive-ui grep check across web/src
    - npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"
    - npm --prefix web test -- --run src/app/admin/records/page.test.tsx src/lib/auth-handler.test.ts src/components/layout/dashboard-shell.test.tsx src/components/layout/admin-shell.test.tsx src/app/admin/rag-profiles/page.test.tsx
    - lsp diagnostics web/src/lib/auth-handler.ts
    - lsp diagnostics web/src/components/providers/app-providers.tsx
    - lsp diagnostics web/src/components/layout/dashboard-shell.tsx
    - lsp diagnostics web/src/components/layout/admin-shell.tsx
    - lsp diagnostics web/src/app/admin/records/page.tsx
    - lsp diagnostics web/src/app/admin/rag-profiles/page.tsx
    - lsp diagnostics web/src/app/admin/personas/*/page.tsx
  verification results: passed; the raw grep now reports only documented exceptions in ErrorBoundary/performance/admin-error, the stricter allowlist check confirmed no undisclosed native-dialog or hard-navigation hits remain, the focused persona/login suite finished 7/7 green, the expanded seam suite finished 14/14 green, and diagnostics were clean on the touched auth/router/admin authority files.
  success signal status: downstream learner-shell work now inherits one router-aware auth redirect seam, one reusable ConfirmDialog+toast destructive-action pattern, and one strict grep/test boundary for preventing regressions in native dialogs or hard redirects.
  rollback note: if a later slice changes the remaining exception set or adds new auth/destructive flows, update interruptiveUiInventory, its focused tests, and the grep allowlist together instead of letting page-local alert/confirm/location usage drift back into business code.

- time: 2026-04-12T01:36:20+08:00
  mode: grow
  item id: M015-S01
  files changed:
    - web/src/lib/debug.ts
    - web/src/lib/console-boundary.test.ts
    - web/src/components/ErrorBoundary.tsx
    - web/src/components/learner/learner-route-error-state.tsx
    - web/src/app/(dashboard)/error.tsx
    - web/src/app/admin/error.tsx
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M015/S01 after fresh slice-level verification confirmed the shared frontend debug seam, durable route-error reporting, and raw-console exception boundary are all in place for downstream dialog/router and learner-shell cleanup work.
  verification commands:
    - npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"
    - rg -n "console\.(log|error|warn|info)" web/src
    - lsp diagnostics web/src/lib/debug.ts
    - lsp diagnostics web/src/components/ErrorBoundary.tsx
    - lsp diagnostics web/src/components/learner/learner-route-error-state.tsx
    - lsp diagnostics web/src/app/(dashboard)/error.tsx
    - lsp diagnostics web/src/app/admin/error.tsx
    - lsp diagnostics web/src/lib/console-boundary.test.ts
  verification results: passed; the focused frontend seam gate finished 27/27 green, the repo-root raw-console grep returned only web/src/lib/debug.ts plus web/src/instrumentation*.ts, and fresh diagnostics were clean on the shared seam, route-error surfaces, and boundary proof file.
  success signal status: frontend business pages, hooks, and route-error surfaces now share one explicit debug/observability seam, so later M015 slices can distinguish intentional instrumentation exceptions from product/runtime logging with one test and one grep.
  rollback note: if a later slice needs to change the raw-console exception set, update the inventory in web/src/lib/debug.ts, the allowlist in web/src/lib/console-boundary.test.ts, and the matching decision/knowledge entries together rather than letting page-local console usage redefine policy by drift.

- time: 2026-04-12T01:30:30+08:00
  mode: grow
  item id: M015-S01-T03
  files changed:
    - web/src/lib/console-boundary.test.ts
    - web/src/app/(dashboard)/agents/[agentId]/page.tsx
    - web/src/app/(dashboard)/training/presentation/page.tsx
    - web/src/app/(dashboard)/training/sales/page.tsx
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/admin/**/*.tsx
    - web/src/app/test-mic/page.tsx
    - web/src/components/admin/knowledge-answer/tabs/intent-rules-tab.tsx
    - web/src/components/highlights/HighlightCard.tsx
    - web/src/components/highlights/HighlightDetailModal.tsx
    - web/src/components/training/ScenarioList.tsx
    - web/src/components/ui/audio-visualizer.tsx
    - web/src/hooks/use-audio-recorder.ts
    - web/src/hooks/use-debounce-request.ts
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-streaming-audio-player.ts
    - web/src/hooks/websocket/message-handlers.ts
    - web/src/hooks/websocket/use-audio-playback.ts
    - web/src/lib/auth-handler.ts
    - web/src/lib/performance.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Migrated the remaining business-page, hook, and developer/support raw-console callers onto the shared debug seam and added a filesystem-backed console-boundary test that fails whenever raw console leaks outside instrumentation/bootstrap and web/src/lib/debug.ts.
  verification commands:
    - npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"
    - rg -n "console\.(log|error|warn|info)" web/src
    - ./web/node_modules/.bin/tsc --noEmit -p web/tsconfig.json
    - lsp diagnostics web/src/app/(dashboard)/**/*.tsx
    - lsp diagnostics web/src/app/admin/**/*.tsx
    - lsp diagnostics web/src/components/**/*.tsx
    - lsp diagnostics web/src/hooks/**/*.ts
    - lsp diagnostics web/src/lib/*.ts
  verification results: passed for the focused Vitest seam gate (27/27 green), repo-root raw-console grep (only instrumentation/debug seam remain), and sampled LSP diagnostics across the touched frontend surface. The direct tsconfig typecheck still reports unrelated pre-existing errors in dashboard page, replay/error-reporting tests, chat-bubble tests, and admin linked-assets tests; no new errors were reported on the migrated console-cleanup files.
  success signal status: future agents can now prove the frontend console boundary with one grep plus one focused test, and page/hook logging policy no longer depends on scattered raw console calls.
  rollback note: if later slices intentionally add or remove raw-console exceptions, update web/src/lib/debug.ts inventory, web/src/lib/console-boundary.test.ts, and the corresponding decision/knowledge entries together rather than letting page-local callers redefine the boundary by drift.


- time: 2026-04-12T00:32:00+08:00
  mode: grow
  item id: M014-S04-T02
  files changed:
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
    - web/src/app/(user)/practice/[sessionId]/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
    - web/src/app/test-mic/page.tsx
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a truthful preflight brief to the practice page for ordinary learners, upgraded pause/resume/end failures into learner-facing retry guidance with explicit next steps, and relabeled /app/test-mic as a developer-only debug tool without reintroducing it into the learner route map.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"
    - browser smoke attempt: npm --prefix web run dev -> http://localhost:3445/practice/session-current?scenario_type=sales&voice_mode=legacy
  verification results: passed for the focused Vitest gate (13/13 green, clean output). Browser smoke was environment-blocked because local Next dev never served the page and stayed stuck on `Compiling instrumentation Node.js ...`; the managed bg_shell process was killed to keep auto-mode health clean.
  success signal status: learners now see what they are about to practice, how it will be judged, and what to do when pause/resume/end actions fail, while the standalone mic page now clearly reads as a debug-only utility.
  rollback note: if later slices enrich preflight data further, keep learner-readable names/titles hydrated from the existing agent/presentation detail APIs and keep lifecycle failures on the same page-level banner/retry seam instead of moving them back into console-only logs or a separate route.

- time: 2026-04-12T00:04:00+08:00
  mode: grow
  item id: M014-S04-T01
  files changed:
    - .gsd/KNOWLEDGE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
  summary: Inventoried the live practice preflight and interruption surfaces so downstream work can reuse the real seams: ordinary sessions only show thin shell state, retry focus and right-panel live summary already carry goal/evidence context, pause/resume failures are still silent, end failures already expose retry/reconnect affordances, the mic test tool lives off the learner path at /app/test-mic, and the seam choice was recorded as D178.
  verification commands:
    - rg -n "pause|resume|end|test-mic|persona|scenario|goal" 'web/src/app/(user)/practice/[sessionId]/page.tsx' 'web/src/hooks/use-practice-websocket.ts'
    - npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/app/(user)/practice/layout.test.tsx'
  verification results: passed; the planned rg scan confirmed the existing scenario/persona/focus/interruption seams, and the focused practice page/lifecycle/layout Vitest suite finished 11/11 green after the knowledge-only writeback.
  success signal status: future agents can now add S04 UX copy on the existing practice page/right-panel/help seams without reintroducing a learner-facing test-mic path or duplicating retry/live-summary data.
  rollback note: if later practice UX work changes the entrypoints, keep preflight/interruption guidance on the real practice shell and right-panel seams, and keep the standalone /app/test-mic tool off the learner route map unless a deliberate product decision restores it.

- time: 2026-04-11T23:47:30+08:00
  mode: grow
  item id: M014-S03-T03
  files changed:
    - web/src/app/(dashboard)/page.test.tsx
    - web/src/app/(dashboard)/profile/page.test.tsx
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added focused learner-help proof on dashboard home and profile so the shared sidebar/mobile-drawer help guidance is now regression-locked across home, profile, and history instead of only on one page.
  verification commands:
    - npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"
    - npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"
    - npm --prefix web test -- --run "src/components/layout/dashboard-shell.test.tsx"
  verification results: passed; the plan command stayed green but only exercised history under local Vitest glob semantics, so an explicit dashboard page suite was run and finished 22/22 green across home/profile/history, and the focused DashboardShell seam suite finished 2/2 green for the shared desktop/mobile help entry.
  success signal status: future agents can now verify learner help discoverability from the three main dashboard entry pages and separately prove the shared learner shell seam still exists.
  rollback note: if future support UX changes the copy, update the shared learner-help guidance expectations together across the dashboard page suites and the DashboardShell seam proof instead of reintroducing page-local support buttons.

- time: 2026-04-11T23:40:45+08:00
  mode: grow
  item id: M014-S03-T02
  files changed:
    - web/src/components/dashboard/learner-help-card.tsx
    - web/src/app/(dashboard)/page.tsx
    - web/src/app/(dashboard)/profile/page.tsx
    - web/src/app/(dashboard)/history/page.tsx
    - web/src/app/(dashboard)/history/page.test.tsx
    - .codex/loop/state.json
  summary: Added one shared learner help card across dashboard home, profile, and history so learners get the same truthful help/feedback guidance everywhere, with explicit copy that the real entry lives in the sidebar help seam and that admin/runtime links are role-gated.
  verification commands:
    - npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"
    - npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx"
  verification results: passed; the focused history Vitest suite finished 6/6 green including the new help-card regression, and the impacted dashboard home/profile suites finished 14/14 green after reusing the same shared learner guidance card.
  success signal status: learner-facing dashboard entry pages now consistently point back to the single sidebar/mobile-drawer help seam instead of inventing separate support buttons, while explaining why management/runtime routes may be absent on learner accounts.
  rollback note: if future work enriches support UX, extend the shared learner-help card and LearnerHelpEntry seam together instead of adding page-local help endpoints or promising an unimplemented ticketing flow.

- time: 2026-04-11T23:32:52+0800
  mode: grow
  item id: M014-S03-T01
  files changed:
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Inventoried learner shell help/navigation entrypoints and confirmed the real authority seam is DashboardShell + LearnerHelpEntry, so downstream work should close discoverability/proof gaps on that shared shell instead of adding page-local help buttons.
  verification commands:
    - rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)
    - npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx"
  verification results: passed; the rg scan showed help copy only on the shared layout seam while home/profile/history tests still focus on other learner flows, and the focused sidebar/dashboard-shell Vitest suite finished 6/6 green for desktop/mobile help mounts.
  success signal status: M014/S03 can now build on the existing shared learner help seam instead of re-researching or scattering temporary buttons across dashboard pages.
  rollback note: if later slices need richer support UX, extend DashboardShell/LearnerHelpEntry and its focused shell tests rather than reintroducing page-local help affordances on home/profile/history.

- time: 2026-04-11T23:12:00+08:00
  mode: grow
  item id: M014-S02
  files changed:
    - .gsd/milestones/M014/slices/S02/tasks/T03-SUMMARY.md
    - .gsd/milestones/M014/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M014/slices/S02/S02-UAT.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
  summary: Closed M014/S02 by formalizing password-reset lifecycle and delivery observability, preserving the truthful profile → forgot-password handoff, proving forgot/reset page closure, and locking voice-speed refresh persistence to the shared browser-local seam.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q
    - npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"
    - npm --prefix web test -- --run "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts"
  verification results: passed; backend auth/password-reset gates finished 20/20 green, focused web auth/profile/voice-speed gates finished 17/17 green, and diagnostics stayed clean on the profile/password-reset authority files.
  success signal status: learner profile now hands off to the real forgot/reset path, reset tokens keep explicit invalidation + delivery state for recovery/debugging, and voice-speed preference survives refresh truthfully through the shared localStorage seam.
  rollback note: if future account-settings work adds a true authenticated change-password or backend preference contract, extend the existing auth/profile authority seams instead of reintroducing fake profile PATCH persistence, window.location redirects, or split reset-token lifecycle semantics.

- time: 2026-03-31T11:06:08+08:00
  mode: grow
  item id: M011-S02-T03
  files changed:
    - backend/src/common/knowledge_engine/haystack_adapter.py
    - backend/src/common/knowledge_engine/reranker.py
    - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
    - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
    - backend/src/common/knowledge_engine/__init__.py
    - backend/tests/unit/common/test_haystack_adapter.py
    - backend/tests/unit/common/test_knowledge_reranker.py
    - backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a config-driven knowledge-engine execution seam to StepFun internal retrieval, including entity resolution + intent classification + retrieval planning, a Haystack-style step executor with early-stop tracing, and a business reranker that returns explainable score breakdowns on final candidates.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q
  verification results: passed; focused backend pytest finished 16/16 green after the red-to-green TDD cycle, and fresh LSP diagnostics reported no issues on the touched runtime or test files.
  success signal status: StepFun internal knowledge search can now turn queries like '请介绍一下世袭科技' into canonical entity resolution, intent classification, retrieval planning, executed query-step traces, and reranked results with per-document score breakdowns while preserving legacy fallback behavior when no active config snapshot is present.
  rollback note: if downstream slices reshape the answerability flow, keep the StepFun runtime on the new project-owned seam (config snapshot -> resolver -> classifier -> planner -> adapter -> reranker) and preserve the actual-executed query trace contract instead of falling back to ad hoc rewritten-query logic.

- time: 2026-03-31T11:52:40+08:00
  mode: grow
  item id: M011-S02-T02
  files changed:
    - backend/src/common/knowledge_engine/intent_classifier.py
    - backend/src/common/knowledge_engine/retrieval_planner.py
    - backend/src/common/knowledge_engine/__init__.py
    - backend/tests/unit/common/test_knowledge_intent_classifier.py
    - backend/tests/unit/common/test_knowledge_retrieval_planner.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a project-owned intent classifier plus progressive retrieval planner that consume DB-normalized config and entity-resolution output, support regex/keyword/entity+keyword rules, and emit auditable rewritten query steps for downstream Haystack execution.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q
  verification results: passed; focused backend pytest finished 4/4 green after confirming the initial red state was missing classifier/planner modules, and fresh LSP diagnostics reported no issues on the new modules, exports, or focused tests.
  success signal status: normalized entity-aware queries can now be classified into DB-backed profiles and turned into deterministic progressive retrieval plans that preserve existing product-overview rewrite behavior while exposing trace/audit metadata.
  rollback note: if later control-plane work changes rule syntax or rewrite expansion vocabulary, keep the classifier/planner seam on project-owned DTOs and update the focused rule/plan tests in lockstep rather than bypassing the new modules from the Haystack adapter.

- time: 2026-03-23T02:10:18+08:00
  mode: stabilize
  item id: M001-S01-T02
  files changed:
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - .gsd/DECISIONS.md
    - .gsd/milestones/M001/slices/S01/S01-PLAN.md
    - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
  summary: Hooked Sales StepFun back into snapshot recovery, restored turn/session runtime continuity on reconnect, and deleted dirty snapshots on timeout/terminal exits.
  verification commands:
    - cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py
    - cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"
    - cd web && npx vitest --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts
  verification results: passed; exact npm test slice command still fails before execution because the package script duplicates --run
  success signal status: reconnected payloads now restore minimal runtime state and reconnect flow reaches end with session_status=scoring while snapshots are cleared
  rollback note: revert StepFun handler snapshot integration if future work changes reconnect protocol; keep D010 boundary unless replacing it with a broader tested contract

- time: 2026-03-25T15:03:33+0800
  mode: stabilize
  item id: M003-S04-T03
  files changed:
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Learner report and replay now render the canonical claim-truth line from the completed-session evidence snapshot, with shared labels/explanations for unsupported, weak, pending, and verified sales claims.
  verification commands:
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
    - cd web && npx tsc --noEmit
  verification results: focused report/replay Vitest passed; repo-wide web typecheck still reports the pre-existing admin knowledge page error `api.reprocessKnowledgeDocument` missing in `src/app/admin/knowledge/[id]/page.tsx`, and no new type errors remained in the S04 files after the claim-truth parser fix
  success signal status: report and replay now expose the same canonical claim-truth vocabulary already used by realtime diagnostics without leaking kb-lock chain-failure copy into completed-session coaching surfaces
  rollback note: if a future contract version promotes claim-truth to a top-level field, keep report/replay on the completed-session projection line and migrate the shared frontend helper rather than reintroducing knowledge-check as the primary read surface

- time: 2026-03-23T02:35:20+08:00
  mode: stabilize
  item id: M001-S01-T03
  files changed:
    - web/package.json
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - web/src/hooks/websocket/message-handlers.ts
    - web/src/hooks/websocket/message-handlers.test.ts
    - .gsd/DECISIONS.md
    - .gsd/completed-units.json
    - .gsd/milestones/M001/slices/S01/S01-PLAN.md
    - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
  summary: Practice page lifecycle now follows server status/reconnected/session_ended, end failures stay visible on the training page with retry/reconnect affordances, and report navigation waits for confirmed terminal status.
  verification commands:
    - cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"
    - cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts
    - browser verification: legacy sales session + backend-down failure injection confirmed end stays on /practice with retry UI; fresh legacy session confirmed end routes to /report after terminal transition
  verification results: passed
  success signal status: training-page end failures are no longer masked by report redirects, and lifecycle UI state is driven by server events instead of optimistic local writes
  rollback note: revert the T03 frontend lifecycle changes together if future work redefines websocket lifecycle contracts; keep D011 unless a new server-authoritative contract replaces it

- time: 2026-03-30T15:49:00+08:00
  mode: grow
  item id: M010-S03-T01
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
  summary: Added shared frontend conclusion-evidence types and helper-owned provenance/degradation formatters, then wired the learner report page to render canonical report-driven conclusion provenance plus four-layer degradation without parsing raw contract fragments in the page.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx"
  verification results: passed; focused report-page Vitest finished 21/21 green, including happy-path sales provenance/degradation, malformed payload omission, rejected supplemental knowledge-check, and presentation-null suppression.
  success signal status: the learner report now exposes a visible helper-driven authority seam for conclusion provenance and degradation distinct from optional knowledge-check diagnostics.
  rollback note: if T02 replay parity reopens this path, keep token-to-copy mapping and malformed-fragment filtering in session-evidence.ts rather than duplicating page-local parsing.

- time: 2026-03-30T16:09:30+0800
  mode: grow
  item id: M010-S03
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M010/S03 after fresh slice-level verification confirmed learner report and replay both render helper-owned conclusion provenance and four-layer degradation from canonical payload fields, while replay keeps report snapshots retry-metadata-only.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
  verification results: passed; focused report+replay Vitest finished 33/33 green, covering shared provenance/degradation vocabulary, malformed helper inputs, supplemental knowledge-check failure isolation, stale report-snapshot non-authority, replay completion-gate behavior, retry CTA behavior, highlight/deep-link anchors, and presentation-null suppression.
  success signal status: learner-facing report and replay now show the same explanation of why each conclusion is believed and which evidence layers are degraded, without page-local truth derivation.
  rollback note: if future work changes conclusion provenance/degradation fields, keep report and replay on the shared session-evidence helper seam and preserve replay payload authority over any cached report snapshot.

- time: 2026-03-31T14:06:08+08:00
  mode: grow
  item id: M011-S04-T01
  files changed:
    - backend/src/common/knowledge_engine/evaluation.py
    - backend/tests/evaluation/test_knowledge_answer_engine_eval.py
    - backend/tests/fixtures/knowledge_answer_eval_cases.json
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a fixture-driven knowledge-answer evaluation harness plus an initial deterministic case set that runs the real engine seam through product intro, pricing, version comparison, coaching guidance, and blocked-timeout degradation behaviors.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q
    - backend/venv/bin/python -m py_compile backend/src/common/knowledge_engine/evaluation.py backend/tests/evaluation/test_knowledge_answer_engine_eval.py
  verification results: passed; fresh repo-root pytest finished 6/6 green for the new harness and fixture cases, and a follow-up py_compile check passed on the new evaluation module and focused test file.
  success signal status: the backend can now replay a stable eval fixture suite against the project-owned knowledge-answer engine without a live knowledge base, while preserving exact multiline answer formatting and blocked-timeout degradation expectations.
  rollback note: if later slices evolve answer copy or retrieval-summary fields, keep the eval harness on the real engine seam and update fixture expectations in lockstep instead of moving assertions into runtime-handler-specific tests.

  files changed:
    - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
    - backend/tests/unit/common/test_knowledge_answer_control_plane_models.py
    - .gsd/KNOWLEDGE.md
  summary: Added the missing Alembic control-plane revision for knowledge config and answer run/step audit tables, and extended the focused backend model test to fail when the migration file is absent or stops declaring the expected schema.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q
  verification results: passed; focused backend pytest finished 10/10 green, and the new migration-presence assertions verified the revision exists, points to 20260328_1000_022, and names all expected control-plane/audit tables.
  success signal status: knowledge answer control-plane schema history now contains the versioned config plus answer run/step audit tables needed for future DB-backed config reads and execution-trace persistence.
  rollback note: if a future migration reshapes these tables, update the focused regression test in lockstep so ORM definitions and Alembic history cannot drift again.

- time: 2026-03-31T11:31:56+0800
  mode: grow
  item id: M011-S01
  files changed:
    - backend/src/common/knowledge_engine/__init__.py
    - backend/src/common/knowledge_engine/engine.py
    - backend/src/common/knowledge_engine/schemas.py
    - backend/src/common/knowledge_engine/config_repo.py
    - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
    - .gsd/DECISIONS.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
  summary: Closed M011/S01 after fresh slice-level verification confirmed the constructable KnowledgeAnswerEngine seam, control-plane Alembic schema history, and DB-backed normalized active-config repository are all in place for downstream Haystack execution work.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q
  verification results: passed; focused backend slice-close gate finished 14/14 tests green and LSP diagnostics reported no issues on the engine, schemas, repository, migration, and focused test files
  success signal status: downstream slices can now instantiate a project-owned knowledge-answer engine and read one latest enabled active query/ranking/answerability configuration snapshot from the database without leaking Haystack types, ORM rows, or raw JSON control-plane shapes
  rollback note: if S02/S03 reshape the control-plane schema or repository snapshot, keep the project-owned engine/repository seam intact and update migration-presence plus repository-normalization regressions in lockstep rather than bypassing them in runtime handlers

- time: 2026-03-31T13:55:34+0800
  mode: grow
  item id: M011-S04-T02
  files changed:
    - backend/src/common/api/knowledge_debug.py
    - backend/src/main.py
    - backend/tests/integration/test_knowledge_debug_api.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a read-only knowledge debug API for admin/support users that lists recent answer runs, returns one run’s persisted audit payload, and exposes ordered step breakdowns directly from KnowledgeAnswerRun and KnowledgeAnswerRunStep rows.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q
    - backend/venv/bin/python -m py_compile backend/src/common/api/knowledge_debug.py backend/tests/integration/test_knowledge_debug_api.py
  verification results: passed; fresh repo-root focused integration pytest finished 5/5 green for list/detail/steps/RBAC/not-found coverage, py_compile passed on the new router and focused test module, and fresh LSP diagnostics reported no issues on backend/src/common/api/knowledge_debug.py or backend/src/main.py.
  success signal status: admin/support can now inspect recent persisted knowledge-answer runs and their ordered step traces from one stable /api/v1/knowledge-debug surface without reconstructing runtime-local traces.
  rollback note: if T03 or later slices extend report/debug inspection, keep this surface read-only and backed by the persisted audit rows plus compat payload fields rather than teaching runtime handlers to rebuild traces for API consumers.

- time: 2026-04-11T22:18:19+08:00
  mode: grow
  item id: M014-S02-T01
  files changed:
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Inventoried the live auth/profile seams and recorded that backend forgot/reset is already persisted and tested, while profile password change remains a truthful forgot-password handoff and voice-speed preference still lives only in localStorage.
  verification commands:
    - rg -n "forgot|reset|password|speech|rate|window.location" web/src/app/\(auth\) web/src/app/\(dashboard\)/profile backend/src/common/auth
    - rg -n "forgot|reset|PasswordReset|AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS|hashed_password" backend/tests -g "!**/__pycache__/**"
  verification results: passed; repo-root rg verification found the live auth/profile entrypoints and silent-fallback surfaces, and the focused backend test scan confirmed dedicated forgot/reset integration coverage already exists in backend/tests/integration/test_password_reset_api.py rather than only in test_auth_login_api.py.
  success signal status: downstream M014/S02 tasks can now build from the real seams instead of re-researching—PasswordResetService + PasswordResetToken are already the backend authority, the profile password CTA is intentionally a `/forgot-password` link, and voice speed is still frontend-local persistence.
  rollback note: if later slices change these seams, keep one authoritative reset-token lifecycle and one authoritative voice-speed persistence seam instead of reintroducing fake profile password APIs or split storage paths.

- time: 2026-04-12T01:04:39+08:00
  mode: grow
  item id: M015-S01-T01
  files changed:
    - web/src/lib/debug.ts
    - web/src/components/ErrorBoundary.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Inventoried the live frontend console surfaces and encoded one canonical boundary in web/src/lib/debug.ts so downstream migration work can distinguish instrumentation exceptions from durable business errors and debug-only noise without rerunning a repo-wide search.
  verification commands:
    - rg -n "console\.(log|error|warn|info)" web/src
    - lsp diagnostics web/src/lib/debug.ts
    - lsp diagnostics web/src/components/ErrorBoundary.tsx
  verification results: passed; the repo-root rg gate produced the expected raw-console inventory for classification, and fresh LSP diagnostics reported no issues after adding the inventory map to web/src/lib/debug.ts and tagging ErrorBoundary as a durable route-error surface.
  success signal status: future M015/S01 tasks now have an explicit migration contract—only instrumentation bootstrap and the shared debug seam itself are allowed raw-console exceptions, while route errors, business faults, and dev/support debug output have named categories and seam destinations.
  rollback note: if later slices narrow or expand the exception set, update the shared inventory in web/src/lib/debug.ts and the corresponding knowledge/decision entries together instead of letting page-local console calls define policy by drift.

- time: 2026-04-12T01:52:30+08:00
  mode: grow
  item id: M015-S02-T01
  files changed:
    - web/src/lib/auth-handler.ts
    - web/src/lib/auth-handler.test.ts
    - web/src/app/admin/records/page.tsx
    - web/src/app/admin/rag-profiles/page.tsx
    - web/src/app/admin/personas/[id]/page.tsx
    - .gsd/KNOWLEDGE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Centralized the remaining native-dialog and hard-navigation inventory into web/src/lib/auth-handler.ts, annotated the hottest admin touchpoints with their target seams, and locked the inventory with a focused auth-handler unit test so later cleanup work can distinguish true cleanup points from explained grep exceptions.
  verification commands:
    - npm --prefix web test -- --run src/lib/auth-handler.test.ts
    - rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src
    - lsp diagnostics web/src/lib/auth-handler.ts
    - lsp diagnostics web/src/app/admin/records/page.tsx
    - lsp diagnostics web/src/app/admin/rag-profiles/page.tsx
    - lsp diagnostics web/src/app/admin/personas/*/page.tsx
    - lsp diagnostics web/src/lib/auth-handler.test.ts
  verification results: passed; the focused auth-handler test finished 4/4 green, the slice grep gate now reports only the real remaining cleanup points plus the documented ErrorBoundary/performance/admin-error exceptions, and the touched authority files were diagnostics-clean.
  success signal status: downstream S02 tasks can now migrate dialog/toast/router/auth-handler seams from one shared inventory instead of re-scanning admin/learner pages or accidentally treating grep exceptions as product regressions.
  rollback note: if T02/T03 changes the remaining exception set, update interruptiveUiInventory, its focused unit test, and the matching knowledge/decision entries together; do not add literal grep-target strings into the inventory/comments or the grep gate will start matching the documentation itself.

- time: 2026-04-12T04:35:21+08:00
  mode: grow
  item id: M016-S03-T03
  files changed:
    - backend/tests/integration/test_admin_users_api.py
    - backend/tests/unit/admin/test_admin_users_api_models.py
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added focused admin-security baseline proof that locks the repaired router RBAC seam, proves sink-level log redaction, and encodes the current covered-vs-follow-up inventory scope directly in tests.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k "admin_security_baseline_inventory_is_closed_and_scoped or admin_router_modules_require_admin_even_without_main_router_guard" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k "structured_logger_masks_sensitive_fields_before_sink_emission or sensitive_log_security_baseline_inventory_is_closed_and_scoped" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q
    - lsp diagnostics backend/tests/integration/test_admin_users_api.py
    - lsp diagnostics backend/tests/unit/admin/test_admin_users_api_models.py
  verification results: passed; the focused admin baseline subset finished 6/6 green, the focused logger/inventory subset finished 2/2 green, the exact task-plan pytest gate finished 36/36 green, and diagnostics were clean on the two touched proof files.
  success signal status: future agents can now rerun one focused backend bundle to tell whether a regression is in module-level admin RBAC, sink-level redaction, or inventory drift about what this baseline currently covers.
  rollback note: if later admin route families or sensitive-log surfaces are added, update the code-owned inventories and these focused proof subsets together so the watch/baseline split does not drift from runtime reality.

- time: 2026-04-12T05:53:19+08:00
  mode: grow
  item id: M017-S03-T01
  files changed:
    - backend/src/presentation_coach/api/presentations.py
    - backend/tests/contract/test_presentations.py
    - backend/tests/integration/test_presentation_flow.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a code-adjacent presentation upload/resource race inventory, locked replace as the first concurrent-writer proof target, and proved in the focused integration harness that delete currently succeeds without a route-level live-session blocker and detaches the session from its presentation.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py -q
    - rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/tests/contract/test_presentations.py
    - lsp diagnostics backend/tests/integration/test_presentation_flow.py
  verification results: passed; the focused presentation contract/integration suite finished 9/9 green, the exact task-plan rg inventory now surfaces the code-adjacent discovery seam plus the new delete guard-gap proof, and diagnostics stayed clean on the touched backend authority/test files.
  success signal status: future agents can now tell which presentation race surfaces are already covered, which one is already proved as a guard gap, and which one still needs concurrent reproduction before any locking work is justified.
  rollback note: if later S03 work changes presentation mutation rules, keep the runtime inventory in backend/src/presentation_coach/api/presentations.py and the focused proofs in backend/tests/contract/test_presentations.py + backend/tests/integration/test_presentation_flow.py aligned together; otherwise discovery conclusions will drift back into audit guesses.
