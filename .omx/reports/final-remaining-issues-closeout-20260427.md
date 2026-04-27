# Final Remaining Issues Closeout — 2026-04-27

Worker: worker-1
Model: gpt-5.5

## Status Matrix

| Item | Status | Evidence | Residual risk / owner |
| --- | --- | --- | --- |
| A-004 Runtime fault closeout | FIXED-CODE / DATA-RESIDUAL | `/support/runtime` already renders structured diagnostics without `[object Object]`; this pass hardened admin log object rendering and kept runtime audit spec forbidden-text checks. Full live root-cause attribution remains blocked without running stack/data. | Data residual owner: Support/runtime ops. Re-run Playwright route audit on live stack and triage returned blocking/warning sessions by `session_id`, linked assets, `kind`, and action copy. |
| A-009 PromptTemplate governance | FIXED | Added `realtime_scoring` prompt type, strict `variables: list[str]` validation with save-time 400, `/api/v1/prompt-templates/governance/status`, `/governance/remediate-invalid`, audit log with before/after rollback payload, admin governance banner/action, RBAC coverage. Targeted backend tests: `62 passed`. | Rollback: restore `is_active`/`is_default` from `SystemLog.details.items.before` for action `prompt_template.governance.remediate_invalid`. |
| A-012 Playwright live audit | FIXED-CODE / ENV-BLOCKED-LIVE | Spec uses `context.request.post` for dev-login, writes structured JSON with ENV_BLOCKED metadata, screenshots/traces, route console/network errors, and fails critical thresholds instead of fake assertions. Run produced `ECONNREFUSED ::1:3444` and JSON at `.sisyphus/evidence/frontend-audit/frontend-audit-routes.json` (not committed). | Start backend `3444` and web `3445`, then rerun: `cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line`. |
| A-014 Python version policy | DEFERRED-WITH-ADR | `backend/pyproject.toml` now declares `requires-python = ">=3.11,<3.14"`; ADR added at `docs/adr/2026-04-27-python-runtime-policy.md`. | Owner: Backend platform. Python 3.14 support requires dependency migration for LangChain/Pydantic v1 shims and full backend gate pass. |
| Admin UX governance | FIXED-CODE / PARTIAL-BY-DESIGN | `/admin/settings` copy now states read-only governance and required API/permission/audit/rollback before editing; `/admin/logs` serializes object details instead of `[object Object]`; `/admin/rag-profiles` distinguishes API failure from empty state; `/admin` production copy no longer exposes `真实度说明`/`inventory`/`不再伪装`; prompt admin has governance status and remediation action. | Remaining non-model settings stay read-only until persistence API/permission/audit/rollback is implemented. |

## Config / Governance Inventory

| Config / surface | Default | Read location | Admin entry | Validation | Permission | Audit | Fallback / rollback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `prompt_templates.allowed_runtime_types` | `summary`, `system`, `system_prompt`, `extraction`, `scoring`, `stage`, `fuzzy_detection`, `interruption`, `tracking`, `welcome`, `evaluation`, `report`, `realtime_scoring` | `backend/src/prompt_templates/models.py::PromptType` and `/api/v1/prompt-templates/governance/status` | `/admin/prompts` | Pydantic enum rejects unknown values; API converts validation failures to 400 `[PROMPT_TEMPLATE_VALIDATION_FAILED]` | Admin only | Existing prompt API RBAC plus remediation SystemLog | Invalid history visible in governance status; remediation disables active/default. |
| Prompt template variables schema | `list[str]` | `PromptTemplateCreate/Update/PromptTemplate` validators | `/admin/prompts` create/edit/governance banner | Rejects dict, non-list, blank, non-string, invalid JSON | Admin only | Remediation writes `prompt_template.governance.remediate_invalid` with before/after snapshots, reason, trace_id | Re-enable manually from audit before snapshot after correcting schema. |
| Admin settings non-model tabs | Read-only governance view | `web/src/app/admin/settings/page.tsx` | `/admin/settings` | Inputs disabled/readOnly until API exists | Admin shell | Deferred; model settings retain existing API audit | No fake save; enable only after API+permission+audit+rollback. |
| Admin logs details | Structured JSON string for object details | `web/src/app/admin/logs/page.tsx` | `/admin/logs` | Safe stringify; fallback message for unserializable details | Admin shell | Backend SystemLog exposure policy | No `[object Object]`; trace_id available for backend audit lookup. |
| RAG legacy profile page | Error state distinct from empty state | `web/src/app/admin/rag-profiles/page.tsx` | `/admin/rag-profiles` with handoff to `/admin/retrieval-strategies` | Name required on save; API failure state blocks false empty | Admin shell | Existing RAG APIs | Retry or migrate to retrieval strategies page. |

## Verification Evidence

- `git diff --check` → PASS (exit 0).
- Backend targeted tests: `cd backend && /Users/zhaozengqing/github/销售训练qoder/backend/venv/bin/python -m pytest tests/unit/prompt_templates/test_models.py tests/unit/prompt_templates/test_service.py tests/integration/test_prompt_templates_api_rbac.py -q --no-cov` → PASS, `62 passed, 2 warnings` (Python 3.14 warnings documented by ADR).
- Backend ruff targeted/full source path: `cd backend && /Users/zhaozengqing/github/销售训练qoder/backend/.venv/bin/ruff check src tests --quiet` → PASS.
- Backend full pytest / pip check → ENV-BLOCKED in this worker: `backend/venv/bin/python` currently resolves to a symlink loop, while `backend/.venv` lacks `pip` and has a broken Python stdlib (`html.entities` missing). Per leader directive, no venv repair/recreate was attempted.
- Web typecheck: `cd web && ./node_modules/.bin/tsc --noEmit --pretty false` with existing dependency mirror → PASS.
- Web eslint: `cd web && ./node_modules/.bin/eslint . --quiet` with existing dependency mirror → PASS.
- Web vitest full: `cd web && ./node_modules/.bin/vitest run --reporter=dot` with existing dependency mirror → PASS, `82 passed`, `501 passed`.
- Web build → ENV-BLOCKED in this worktree because Next/Turbopack rejects a temporary external `node_modules` symlink (`Symlink [project]/node_modules is invalid, it points out of the filesystem root`). No dependency install was performed.
- Web npm audit: `cd web && npm audit --audit-level=moderate --json` → PASS, `0 vulnerabilities`, `648` dependencies.
- Playwright audit: `cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 ./node_modules/.bin/playwright test tests/e2e/audit/audit.spec.ts --reporter=line` → ENV-BLOCKED, backend `localhost:3444` refused dev-login; structured JSON evidence generated locally and excluded from commit.

## Notes

- No backend venv/env artifact is committed. Temporary web `node_modules` symlink used only to run local verification was removed before commit.
- Live stack gates must be rerun by the integrator in an environment with backend `3444`, web `3445`, and local dependencies installed inside `web/` rather than symlinked outside the worktree.
