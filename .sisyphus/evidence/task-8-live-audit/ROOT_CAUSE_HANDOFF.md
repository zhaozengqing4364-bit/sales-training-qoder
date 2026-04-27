# Task 8 live audit handoff (worker-5, model gpt-5.5)

## Environment/state evidence
- Initial 3444/3445 curl failed: `health-check.txt`.
- Worktree had no backend `.venv`, no `.venv-test`; leader cwd had broken Python 3.11.12 `.venv` (`html.entities` missing): `leader-venv-probe.txt`.
- Created an isolated worktree `backend/.venv` with Homebrew Python 3.11.15 and installed backend requirements; did **not** touch `backend/.venv-test` or business data: `local-venv-create.log`.
- Web had no `node_modules`, so `scripts/dev-smoke-up.sh` initially let `npm exec` fetch `next@16.2.4` and Turbopack could not resolve the project root. Ran `npm ci` in `web/`: `web-npm-ci.log`.
- Default Postgres startup failed because role `dev` did not exist; restarted with isolated SQLite DB under `.dev/task-8-live-audit.sqlite3`: `dev-smoke-up-sqlite-after-npm.log`, `dev-smoke-up-held2.log`.

## Stable service evidence
- Held stack is reachable at 3444/3445 while the worker shell keeps the parent process alive: `curl-health-held-pass.txt` and `repeated-health-probes.txt`.
- Backend `/health` returns 200/ready/database ok.
- Frontend `/login` returns 200.

## Playwright result
- Command: `cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_EVIDENCE_PREFIX=task-8-live-audit SMOKE_BACKEND_BASE_URL=http://localhost:3444/api/v1 SMOKE_WEB_BASE_URL=http://localhost:3445 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line`
- First run failed on cold Next compilation timeout for `/training/sales`: `playwright-audit.log`.
- Rerun emitted structured JSON/screenshots/trace/video but failed without skipping/relaxing: `playwright-audit-rerun.log`, `frontend-audit-routes.json`, `task-8-live-audit-test-results/**`.

## Exact failing conditions from `frontend-audit-routes.json`
1. `/admin/business-rules/sales-combinations` (critical) returned status 200 but final URL was `/`, with `REQUEST_FAILED net::ERR_ABORTED ... node_modules_0b8jb3z._.js`.
2. `/support/runtime` (critical) returned status 200 at the route, but browser saw `net::ERR_NETWORK_CHANGED` for two Next static chunks and two console errors.
3. Admin routes (`/admin`, `/admin/settings`, `/admin/logs`, `/admin/rag-profiles`) final URL was `/`, indicating the audit is not actually exercising admin pages with the current `dev-login` user.

## Likely root cause / owner ADR
- `web/tests/e2e/audit/audit.spec.ts` logs in through backend `/auth/dev-login`, which returns `role: "user"` (`curl-health-held-pass.txt`). Admin audit routes then redirect away to `/` instead of rendering governance pages. Owner should define a real audit-auth persona (admin cookie/token or smoke admin login) instead of relying on non-admin dev-login for admin route assertions.
- The `net::ERR_NETWORK_CHANGED` chunk failures are environmental/browser-network instability captured by Playwright trace/video. Because the test currently treats all failed static chunk requests as critical, this remains a real live-audit failure, not a pass.

## Artifacts
- Structured route JSON: `.sisyphus/evidence/task-8-live-audit/frontend-audit-routes.json`
- Screenshots: `.sisyphus/evidence/task-8-live-audit/*.png`
- Trace/video/error context: `.sisyphus/evidence/task-8-live-audit-test-results/audit-audit-frontend-audit-40cda-orces-P0-failure-thresholds-chromium/`
