# Final Remaining Issues Closeout — 2026-04-27

Worker: worker-2  
Model: gpt-5.5  
Scope: source-only continuation of task-2; no `backend/venv`, `node_modules`, or generated environment artifacts are part of the intended deliverable.

## Status matrix

| Area | Status | Evidence | Remaining risk / owner |
| --- | --- | --- | --- |
| A-009 PromptTemplate governance | FIXED | Added `realtime_scoring` as a governed prompt type; strict save-time `variables: list[str]` validation returns 400 for historical object-shaped payloads; admin governance endpoints migrate invalid rows and rollback from SystemLog snapshots; list/detail responses expose `governance_status` / `governance_issues`; admin prompts UI shows needs-review state and migration/rollback controls; backend integration test file passed `11 passed`. | Rollback depends on retained `SystemLog` audit snapshot. Owner: platform/admin-governance for any future schema extension. |
| A-012 Playwright live audit | ENV-BLOCKED | `web/tests/e2e/audit/audit.spec.ts` already uses `context.request.post`, structured route evidence, screenshots, console/network capture, and critical failure thresholds. Fresh run failed honestly with `ECONNREFUSED ::1:3444`; `curl` confirmed `localhost:3444` and `3445` were not listening. | Start backend/frontend stack, then rerun exact command below. Owner: release/QA runner. |
| A-004 Runtime fault closeout | FIXED / DATA-RESIDUAL | Prior runtime UI and tests already prevent `[object Object]`; fresh Playwright live verification is env-blocked because services are down. | True live blocking/warning attribution remains data-residual until a real stack with production-like data is available. Owner: support/runtime operator. |
| A-014 Python 3.14/version policy | DEFERRED-WITH-ADR | Full backend suite on Python 3.14 env reached `1715 passed, 20 skipped, 25 deselected` with 3 dependency/env failures: missing `alembic.op`, missing `funasr`, missing Pillow. `uv pip check` is green for both Python 3.14 `.venv-test` and Python 3.11 `.venv`. | ADR: project remains Python 3.11 CI/dev primary (`pyproject`/mypy already point to 3.11). Python 3.14 support requires a separate dependency image containing Alembic runtime, FunASR and Pillow-compatible stack. Owner: platform/tooling. |
| Admin UX governance | FIXED / PARTIAL | `/admin/settings` copy now says read-only and routes effective changes to model config/governance work instead of “editable but not saved”; `/admin/rag-profiles` distinguishes API failure from empty state, offers retry and migration path to retrieval strategies; tests pass. `/admin/logs` existing masked diagnostics test remains green. | Full persistence/audit/rollback for legacy non-model settings is deferred until each setting has a backend config definition. Owner: admin-platform. |

## Configuration / governance contract

| Config / rule | Default | Read location | Admin entry | Validation | Permission | Audit | Fallback / rollback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `prompt_templates.allowed_runtime_types` | Enum includes existing types plus `realtime_scoring` | `backend/src/prompt_templates/models.py`, frontend `PromptType` | `/admin/prompts`, new/edit pages | Pydantic enum validation; sales binding allowlist includes `realtime_scoring` | Admin-only prompt APIs | SystemLog for governance migration/rollback | Unknown historical types are marked needs-review and disabled by migration |
| PromptTemplate `variables` contract | `[]` when absent; list of non-empty strings when authored | PromptTemplate create/update API and service read model | `/admin/prompts` | Object/non-array variables rejected with 400 on save; historical objects visible as governance issue | Admin-only mutate; support/user denied | `prompt_template.governance_migrate`, `prompt_template.governance_rollback` | Migration converts object keys to list; rollback restores captured before snapshot |
| Admin settings non-model tabs | Read-only | `web/src/app/admin/settings/page.tsx` | `/admin/settings` | Inputs disabled/readOnly; save/discard disabled | Admin page access; no mutation endpoint used | Deferred; no fake write | Users are directed to model config or governance ticket |
| Legacy RAG profiles | Existing API result, empty list, or explicit failure | `web/src/app/admin/rag-profiles/page.tsx` | `/admin/rag-profiles` and `/admin/retrieval-strategies` | Failure state separated from empty state; delete still confirm-dialog guarded | Existing admin API permissions | Existing API-side audit if configured; UI does not fake success | Retry on API failure; migration link for empty/deprecated state |

## Verification evidence

- `git diff --check` → PASS.
- `backend ruff`: `PYTHONPATH=src /Users/zhaozengqing/github/销售训练qoder/backend/.venv/bin/ruff check backend/src backend/tests --quiet` → PASS.
- Backend targeted: `cd backend && PYTHONPATH=src /Users/zhaozengqing/github/销售训练qoder/backend/.venv-test/bin/python -m pytest tests/integration/test_prompt_templates_api_rbac.py -q --no-cov` → PASS, `11 passed`.
- Backend full non-performance: `cd backend && PYTHONPATH=src /Users/zhaozengqing/github/销售训练qoder/backend/.venv-test/bin/python -m pytest tests -q --no-cov -m 'not performance'` → FAIL due environment/dependency gaps unrelated to this source change: missing `alembic.op`, `funasr`, Pillow in `.venv-test`; summary `3 failed, 1715 passed, 20 skipped, 25 deselected`.
- Backend dependency check: `uv pip check --python .../backend/.venv-test/bin/python` and `uv pip check --python .../backend/.venv/bin/python` → PASS, all installed packages compatible. Direct `python -m pip check` is ENV-BLOCKED because both reused envs omit the pip module.
- Frontend typecheck: `cd web && npm exec -- tsc --noEmit --pretty false` → PASS.
- Frontend eslint: `cd web && npm exec -- eslint . --quiet` → PASS.
- Frontend targeted Admin UX tests: `cd web && npm exec -- vitest run 'src/app/admin/settings/page.test.tsx' 'src/app/admin/logs/page.test.tsx' 'src/app/admin/rag-profiles/page.test.tsx' --reporter=dot` → PASS, `3 files / 7 tests`.
- Frontend full vitest: `cd web && npm exec -- vitest run --reporter=dot` → PASS, `82 files / 502 tests`.
- Frontend build: after replacing the temporary external `node_modules` symlink with local `npm ci`, `cd web && npm run build` → PASS.
- Frontend npm audit: `cd web && npm audit --audit-level=moderate --json` → PASS, 0 vulnerabilities.
- Playwright audit: `cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line` → ENV-BLOCKED, backend/frontend services not listening; failed at `POST http://localhost:3444/api/v1/auth/dev-login` with `ECONNREFUSED ::1:3444`.

## Reverification commands

```bash
git status --short
git diff --check
cd backend && PYTHONPATH=src /Users/zhaozengqing/github/销售训练qoder/backend/.venv/bin/ruff check src tests --quiet
cd backend && PYTHONPATH=src /Users/zhaozengqing/github/销售训练qoder/backend/.venv-test/bin/python -m pytest tests/integration/test_prompt_templates_api_rbac.py -q --no-cov
cd backend && PYTHONPATH=src /Users/zhaozengqing/github/销售训练qoder/backend/.venv-test/bin/python -m pytest tests -q --no-cov -m 'not performance'
uv pip check --python /Users/zhaozengqing/github/销售训练qoder/backend/.venv-test/bin/python
cd web && npm exec -- tsc --noEmit --pretty false
cd web && npm exec -- eslint . --quiet
cd web && npm exec -- vitest run --reporter=dot
cd web && npm run build
cd web && npm audit --audit-level=moderate --json
cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line
```
