## Initial

## 2026-04-15 — T1 backend diagnostics baseline
- Canonical backend command surface should use the explicit 3.13 interpreter from `backend/`: `/opt/homebrew/opt/python@3.13/bin/python3.13 -m pytest --collect-only || true` and `/opt/homebrew/opt/python@3.13/bin/python3.13 -m mypy src/ || true`.
- In this workspace, `python` is missing, `python3` is Homebrew 3.14, and `pytest` runs on Homebrew 3.13; diagnostics must record the interpreter actually used.
- `reportMissingImports` for `fastapi`, `sqlalchemy`, `websockets`, `httpx`, `jwt`, `passlib.context`, `dotenv`, and `uvicorn` should be treated as likely environment noise first when those packages are already declared in `backend/requirements.txt`.
- Realtime/type hotspots that remain worth fixing later even after import-noise filtering: `backend/src/common/auth/service.py:323-339` and `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:795, 888-895, 1842, 2543, 2627, 2633-2635, 4245-4266`.
- Manual `sys.path.insert(...)` patterns are pervasive across backend entrypoints/scripts/tests; they are a reliable sign that LSP/import behavior may diverge from runtime depending on current working directory.

## 2026-04-15 — T3 stack boot + smoke baseline
- `bash scripts/dev-smoke-up.sh` is the canonical one-command smoke boot entry; it reuses `scripts/dev-up.sh`, waits for `http://localhost:3444/health` and `http://localhost:3445/login`, and bootstraps `admin@qoder.ai` as an admin.
- The smoke wrapper must pin auth via `AUTH_USER_PASSWORDS_JSON` / `AUTH_SHARED_PASSWORD`; relying on whatever password state already exists in the local DB is not deterministic enough for login smoke.
- Stable smoke selectors proved by Playwright:
  - login: heading `欢迎回来`, labels `邮箱地址` / `密码`, button `登录`
  - training entry: heading `训练模式`, child headings `销售对练` and `演讲练习`
  - practice smoke: button `结束练习`, status text `已连接`, preflight copy `开始前先看本次练习重点`
  - admin analytics: heading `数据分析`, button `刷新`, heading `本周经营节奏包`
- The least fragile practice smoke path is: UI login for cookie session + API login for bearer token + query published sales agent/persona + POST `/api/v1/practice/sessions` + open `/practice/{sessionId}`.

## 2026-04-15 — T4 schema baseline discoveries
- For `staged_evaluation_results` and `comprehensive_reports`, the effective runtime contract now comes from the evaluation services plus ORM models, while Alembic `006` still preserves an older analytics-oriented design.
- `Base.metadata.create_all` in `common.db.session.init_db()` is the main schema-drift amplifier for these report/evaluation tables because there is no table-specific legacy repair path for them.
- `staged_evaluation_results.weaknesses` is a critical field: runtime evaluation generates it and comprehensive-report aggregation consumes it, so any canonical schema that omits it is incomplete.
- The report-generation lifecycle is split across tables: `practice_sessions` owns status/error/generated-at control-plane fields, while `comprehensive_reports` stores the report content payload.

## 2026-04-15 — T2 contract/type baseline learnings
- The frontend raw API boundary for admin model-configs is now clearest when `web/src/lib/api/types.ts` owns the snake_case `AdminModelConfig*` family and both `client.ts` and pages import from there instead of re-declaring route-local shapes.
- `backend/src/admin/api/model_configs.py:list_model_configs` is no longer a paginated/filter-rich endpoint; the live response is a grouped `{ llm, embedding, asr, tts, total }` object keyed by `model_type`.
- Replay read endpoints in `backend/src/common/conversation/api.py` consistently return `{ success, data, trace_id }` envelopes even though older examples had drifted into bare payloads.
- For touched admin UI code, the stable pattern is: keep wire-contract fields snake_case in shared API types, and keep purely UI configuration maps (`MODEL_TYPE_CONFIG`, provider label maps, etc.) local to the page.

## 2026-04-15 — T5 auth closure evidence learnings
- In this workspace, the trustworthy backend auth verification command is `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -q`; the hydrated `backend/venv` interpreter has the auth dependencies that the bare Homebrew Python did not.
- The current T5 proof is strongest when split into two layers: backend integration tests for provider/callback/session establishment and frontend login-page tests for explicit provider/dev-fallback presentation.
- The implemented auth provider contract returns explicit provider metadata and absolute backend login URLs, which lets the frontend login page stay a pure consumer instead of embedding WeCom-specific URL construction.

## 2026-04-15 — T5 auth-local typing learnings
- For this auth slice, Pyright narrows `token` / `user_id` correctly once `_raise_auth_http_error(...)` is annotated as `NoReturn`; no runtime guard duplication was needed in `get_current_user`.
- Helper functions that default optional parameters to `None` must use `str | None` annotations in this repo’s auth files, otherwise Pyright reports real `reportArgumentType` errors even when runtime behavior is fine.

## 2026-04-16 — T6 report/evaluation reconciliation learnings
- The safest T6 migration shape is table-rebuild + copy, not piecemeal `ALTER TABLE`: `staged_evaluation_results` and `comprehensive_reports` both had identity/timestamp/legacy-column drift severe enough that rebuilding the tables made the canonical contract much easier to guarantee.
- For staged evaluations, the meaningful legacy backfill is `suggestions <- improvement_suggestions` and `summary <- stage_summary` when the canonical runtime columns are missing; everything else from `006` is truly legacy noise.
- For comprehensive reports, the useful downgrade/backfill mapping is `key_improvements <- priority_improvements`, `recommendations <- practice_recommendations`, and `detailed_feedback <- overall_assessment`; other `006` analytics summary columns are not needed by current runtime paths.
- In this repo, scoped Alembic proof for a single migration is more reliable when the database is stamped to the immediate pre-task revision and upgraded directly to the target revision (`ae1dbf12bd03`) instead of using `head`, because unrelated historical branch debt can still be present elsewhere in the migration tree.

## 2026-04-16 — T7 evidence closure learnings
- The smallest trustworthy T7 telemetry proof is the focused frontend suite `cd web && npx vitest run src/lib/performance.test.ts src/components/error-reporting.test.tsx`; it directly proves the backend analytics targets for performance/custom/error dispatch without needing a broader UI run.
- `bash scripts/dev-smoke-up.sh` + `curl -fsS http://localhost:3444/health` remains the cleanest T7 health proof because it exercises the real local stack and returns a machine-readable payload with `ready: true`.

## 2026-04-16 — T9 quality-gate learnings
- `scripts/dev-smoke-up.sh` is now the critical-flow smoke authority because it seeds one deterministic completed sales session and records `SMOKE_REPORT_SESSION_ID`, `SMOKE_REPORT_PATH`, and `SMOKE_REPLAY_PATH` into `.dev/smoke/state.env` for Playwright to consume.
- The smoke evidence bootstrap must respect the live `conversation_messages.sales_stage` check constraint (`opening|discovery|presentation|objection|closing`); using a semantic-but-invalid label like `next_step` blocks the gate before typecheck or Playwright even start.
- For T9, the trustworthy frontend test stage is a curated Vitest slice aligned to login/dashboard/practice/report-replay/admin-analytics/support-runtime plus auth/error shared seams, not a repo-wide `vitest run` that drags unrelated admin knowledge tests into the release gate.
- `web/vitest.config.ts` should explicitly exclude `tests/e2e/**` so the Playwright smoke suite cannot be picked up by Vitest when CI/local gates run both stages back to back.
