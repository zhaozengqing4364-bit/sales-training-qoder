# Final Remaining Issues Closeout — 2026-04-27

Worker: `worker-3`  
Model reported: `gpt-5.5`  
Scope: close remaining A-004/A-009/A-012/A-014/Admin UX issues without report-only completion.

## Status matrix

| Area | Status | Evidence | Remaining risk / owner |
| --- | --- | --- | --- |
| A-004 Runtime fault closeout | FIXED-CODE / DATA-RESIDUAL | Existing `/support/runtime` renders typed overview/faults, stringifies object diagnostics as JSON, and focused tests assert no `[object Object]` plus actionable next steps. Full Vitest: `82 passed / 501 tests`. | Live blocking/warning attribution still needs an actually running stack and production data owner review. Owner: support/backend runtime maintainers. |
| A-009 PromptTemplate governance | FIXED | Added `realtime_scoring` as a first-class prompt type/admin option; create/update now manually returns 400 for invalid variables; governance endpoints list and migrate invalid historical rows; migration disables invalid active/default templates and writes `SystemLog` audit entries. Focused backend prompt tests passed earlier in this run: `46 passed`; frontend admin prompt page exposes invalid-template migration banner/action. | No destructive DB operation is automatic; admins must invoke migration with a reason. Rollback is re-enable/edit from admin prompt governance after audit review. |
| A-012 Playwright live audit | ENV-BLOCKED | `web/tests/e2e/audit/audit.spec.ts` already uses `context.request.post`, structured route result collection, screenshot paths, console/network errors, and critical-route assertions. Command run: `SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line` failed at dev-login with `ECONNREFUSED ::1:3444`. | Backend/frontend stack was not listening on `3444/3445`; do not mark pass until services are started. Re-run command above after stack startup. |
| A-014 Python 3.14/version policy | DEFERRED-WITH-ADR | Added `docs/adr/2026-04-27-python-version-policy.md`: CI/dev support remains Python 3.11; Python 3.14 is best-effort until dependency stack is upgraded. Local 3.14 dependency install hit timeout/build issues for `funasr -> editdistance -> cython`. | Owner: platform/backend maintainers. Supersede ADR only with dependency upgrades + full backend gate evidence. |
| Admin UX governance | FIXED | `/admin` no longer exposes production-visible `真实度说明`/`inventory`/`不再伪装`; `/admin/settings` read-only tabs now explicitly require persistence/permission/audit/rollback before editing; `/admin/logs` distinguishes filtered empty state; `/admin/rag-profiles` distinguishes load failure from empty state and points to retrieval strategy handoff. Targeted admin tests: `4 passed / 7 tests`; full Vitest: `82 passed / 501 tests`. | Settings non-model tabs remain read-only by design until persistence APIs exist. Owner: admin platform/product. |

## Configuration / governance table

| Item | Default | Read location | Admin entry | Validation | Permission | Audit / fallback / rollback |
| --- | --- | --- | --- | --- | --- | --- |
| `prompt_templates.prompt_type.realtime_scoring` | Enabled enum option | `PromptType.REALTIME_SCORING`, frontend `PromptType` labels | `/admin/prompts`, create/edit/select filters | Pydantic enum + manual route validation | admin-only prompt API | create/update/default actions go through prompt API; invalid historical rows are not silently selected. |
| Prompt template variables | `[]` or extracted Jinja variables | `PromptTemplateCreate/Update`, `PromptTemplate` DB normalization | `/admin/prompts` create/edit | save-time 400 for non-`list[str]`; dict variables rejected | admin-only | invalid historical rows visible at `/api/v1/prompt-templates/governance/invalid`; migration disables active/default and writes `SystemLog`. |
| Invalid prompt migration | Report-only until admin action | `PromptTemplateService.list_invalid_template_governance()` | `/admin/prompts` banner/action + API | invalid type, dict/non-list variables, empty template | admin-only | `prompt_template_invalid_migration` audit with actor/reason/before/after/trace_id; rollback by reviewed admin edit/re-enable. |
| Admin settings read-only tabs | disabled | `/admin/settings` | same | disabled controls, no fake persistence | admin UI only | no mutation until API/permission/audit/rollback exists. |
| Python runtime policy | Python 3.11 supported | `backend/pyproject.toml`, CI workflow, ADR | docs ADR | full gates required for support expansion | platform maintainers | rollback/supersede by new ADR and CI/dependency update. |

## Verification evidence

- `git diff --check` → PASS.
- LSP diagnostics on modified backend prompt files and key frontend admin files → 0 errors.
- Backend focused prompt governance tests → PASS earlier in run: `46 passed, 2 warnings` using available backend venv before environment drift.
- Backend ruff targeted (`src/prompt_templates`, prompt tests) → PASS before backend venv drift.
- Backend full `ruff/pytest/pip check` → ENV-BLOCKED after local `backend/venv` became a self-referential symlink during dependency rehydration attempts; a Python 3.14 `uv pip install -r backend/requirements.txt ...` attempt also timed out fetching/building `cython` for `editdistance` via `funasr`. Re-run from a clean Python 3.11 backend venv.
- Frontend tsc: `cd web && npm exec -- tsc --noEmit --pretty false` → PASS.
- Frontend eslint: `cd web && npm exec -- eslint . --quiet` → PASS.
- Frontend targeted admin tests: `4 passed / 7 tests`.
- Frontend full Vitest: `82 passed / 501 tests`.
- Frontend build: `npm exec -- next build --webpack` → PASS. Plain `npm run build` was blocked by Turbopack rejecting the temporary external `node_modules` symlink in this worktree.
- `npm audit --audit-level=moderate --json` → PASS, 0 vulnerabilities.
- Playwright audit spec → ENV-BLOCKED (`ECONNREFUSED ::1:3444`).

## Reverification commands

```bash
# Backend, from a clean Python 3.11-compatible venv
cd backend
venv/bin/ruff check src tests --quiet
venv/bin/python -m pytest tests -q --no-cov -m 'not performance'
venv/bin/python -m pip check

# Frontend
cd web
npm exec -- tsc --noEmit --pretty false
npm exec -- eslint . --quiet
npm exec -- vitest run --reporter=dot
npm run build
npm audit --audit-level=moderate --json
SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line
```
