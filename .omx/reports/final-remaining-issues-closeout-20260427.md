# Final Remaining Issues Closeout — 2026-04-27

Leader follow-up after `omx-reports-team-fix-final-clo` shutdown. The team mailbox/state directory is no longer present after shutdown, so this report records the direct verification/fix pass performed in the leader workspace.

## Status Matrix

| Item | Status | Evidence | Residual risk / owner |
| --- | --- | --- | --- |
| A-009 PromptTemplate governance | CLOSED-CODE | Removed duplicate `realtime_scoring` enum/type entries, restored save-time 400 validation, added governance status/remediation/migration/rollback endpoints, actor-scoped audit logging, invalid-history visibility, and frontend admin status actions. Backend targeted prompt suite: `110 passed`. | Existing UI display labels/colors remain front-end dictionaries until a centralized i18n/settings source is introduced. Owner: Admin UX/platform. |
| A-012 Playwright live audit | CODE PRESENT / ENV-BLOCKED-LIVE | `web/tests/e2e/audit/audit.spec.ts` exists, but live run is blocked: default Playwright global setup invokes `scripts/dev-smoke-up.sh`; backend startup fails in `.venv` because Python 3.11 stdlib is missing `html.entities`. No browser route assertions executed. | Run only after a healthy already-started stack is available, preferably with `SMOKE_REUSE_EXISTING_STACK=1`; repair/recreate backend `.venv` outside this no-dependency/no-restart pass. Owner: Dev environment/platform. |
| A-004 Runtime/admin UX object rendering | CLOSED-FRONTEND-SMOKE | Prompt admin and RAG profile admin no longer fail TypeScript; RAG profile page now distinguishes API failure from empty state and provides retry/migration action. Full web vitest `505 passed`; build passes. | Live `/support/runtime` route not re-audited because services were not available without invoking global setup. Owner: QA on healthy live stack. |
| A-014 Python 3.14 policy | VERIFIED-PARTIAL | Backend prompt governance tests pass under `.venv-test` Python 3.14.3; `uv pip check --python .venv-test/bin/python` passes. | Runtime `.venv` Python 3.11.12 remains environment-broken (`html.entities` missing; no `pip` module). This is an environment repair task, not committed code. |
| Admin prompt/RAG frontend compile | CLOSED | Fixed duplicate prompt-type labels/colors, duplicate API client methods/imports, wrong admin prompt `Promise.allSettled` tuple ordering, undefined governance JSX handlers, and malformed RAG profile test block. | Prompt-type options should be sourced from `/api/v1/prompt-templates/options` in a future UI cleanup to reduce duplicated display config. |

## Config / Governance Inventory

| Config / surface | Default | Read location | Admin entry | Validation | Permission | Audit | Fallback / rollback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PromptTemplate allowed runtime types | `summary`, `system`, `system_prompt`, `extraction`, `scoring`, `realtime_scoring`, `stage`, `fuzzy_detection`, `interruption`, `tracking`, `welcome`, `evaluation`, `report` | `backend/src/prompt_templates/models.py::PromptType`; exposed by `/api/v1/prompt-templates/options` and `/governance/status` | `/admin/prompts` | Pydantic enum; invalid writes return 400 `[PROMPT_TEMPLATE_VALIDATION_FAILED]` | Admin only via prompt routes | Create/update/delete/remediate/migrate/rollback actions write `SystemLog` when invoked with actor | Invalid history is visible; remediation disables active/default templates; migration audit supports rollback endpoint. |
| Prompt variables schema | `list[str]` | `PromptTemplateCreate/Update/PromptTemplate` validators | `/admin/prompts` create/edit/governance banner | Rejects object-shaped variables, non-list, blank/non-string entries, invalid JSON strings on DB read | Admin only | `prompt_template.governance.*` audit records include before/after/reason/trace | Historical invalid rows remain visible and can be disabled/migrated instead of silently normalized at runtime. |
| Prompt governance remediation | default reason: `prompt governance remediation` | `/api/v1/prompt-templates/governance/remediate-invalid` | `/admin/prompts` | Request body/query reason length 1..500 | Admin only | `prompt_template.governance.remediate_invalid` | Rollback by audit before snapshot or `/governance/{template_id}/rollback` for migration records. |
| RAG profile legacy page | API failure is not treated as empty list | `web/src/app/admin/rag-profiles/page.tsx` | `/admin/rag-profiles` | Existing API validation plus explicit load error state | Admin shell | Existing backend APIs | Retry or navigate to `/admin/retrieval-strategies`; no fake empty state. |

## Verification Evidence

- `git diff --check` → PASS.
- Backend ruff: `cd backend && .venv/bin/python -m ruff check src/prompt_templates src/app_factory.py tests/integration/test_prompt_templates_api_rbac.py tests/unit/prompt_templates` → PASS.
- Backend prompt governance/unit/integration tests: `cd backend && PYTHONPATH=src .venv-test/bin/python -m pytest tests/unit/prompt_templates tests/integration/test_prompt_templates_api_rbac.py -q --no-cov` → PASS, `110 passed, 1 warning`.
- Backend dependency compatibility: `cd backend && uv pip check --python .venv-test/bin/python` → PASS, `132 packages` compatible.
- Web typecheck/lint/tests: `cd web && npm exec -- tsc --noEmit --pretty false && npm run lint && npm run test -- --reporter=dot` → PASS; lint has `0 errors, 36 warnings`; vitest `82 files / 505 tests passed`.
- Web build: `cd web && npm run build` → PASS; Next.js generated 33 static pages.
- Web dependency audit: `cd web && npm audit --audit-level=moderate --json` → PASS, `0 vulnerabilities`, `648` dependencies.
- Playwright live audit: attempted `cd web && npm run e2e -- tests/e2e/audit/audit.spec.ts --reporter=line` → ENV-BLOCKED before browser assertions. Global setup tried `scripts/dev-smoke-up.sh`; backend failed with `ModuleNotFoundError: No module named 'html.entities'` from `.venv` Python 3.11.12. Generated evidence mutations were reverted.

## Environment Notes

- Team state/mailbox path `.omx/state/team/omx-reports-team-fix-final-clo/...` no longer exists after team shutdown.
- `backend/.venv/bin/python` reports Python 3.11.12 but cannot import stdlib `html.entities`; `.venv/bin/python -m pip` is unavailable. `.venv-test` Python 3.14.3 was used for backend tests without changing dependencies.
- No dependency installs or DB migrations were performed. One Playwright verification attempt invoked the default global setup, which attempted to restart dev services and failed before browser route assertions; generated artifacts were reverted and no further service operations were performed. Do not rerun Playwright in this constrained mode without an already healthy stack and reuse flag.
