# Final Remaining Issues Closeout — 2026-04-27

Worker: worker-5
Model reported: gpt-5.5

## Status Matrix

| Area | Status | Evidence / owner |
| --- | --- | --- |
| A-004 Runtime fault closeout | Fixed for code/UI; live data residual owner: Support Ops | Runtime page formats object/array diagnostics safely, expanded actionable fault advice for KB lock/projection/audio/evaluation faults. Live blocking/warning counts still require started stack + real data review. |
| A-009 PromptTemplate governance | Fixed | Added admin-visible governance status, invalid historical quarantine endpoint, 400 save-time validation for invalid prompt payloads, admin option endpoint, SystemLog audit for prompt mutations/quarantine, and rollback policy. |
| A-012 Playwright audit | Env-blocked unless services are running | `web/tests/e2e/audit/audit.spec.ts` already uses `context.request.post` dev-login and structured JSON/screenshots/errors; do not mark green if 3444/3445 are down. Re-run command below. |
| A-014 Python 3.14/version policy | Deferred with ADR | `docs/adr/2026-04-27-python-version-policy.md` pins current release support to Python 3.11 and requires a separate dependency-upgrade lane for Python 3.14. |
| Admin UX follow-up | Fixed/deferred split | `/admin/settings` read-only copy now names missing persistence/permission/audit/rollback. `/admin/logs` distinguishes API failure from empty logs. `/admin/rag-profiles` distinguishes API failure from empty legacy profile state and directs users to retrieval strategies. |

## Configuration / Governance Details

| Item | Default | Read location | Admin entry | Validation | Permission | Audit | Fallback / rollback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Prompt template types | `PromptType` enum excluding `realtime_scoring` | `backend/src/prompt_templates/models.py` | `/admin/prompts`, `/api/v1/prompt-templates/options` | Save-time 400 on invalid enum/variables; governance scan reports invalid history | admin only | `SystemLog.action=prompt_template.governance.*` | Quarantine disables invalid rows; rollback only after fixing prompt type/variables then re-enabling. |
| Prompt template variables | `list[str]` | Pydantic models + governance status | `/admin/prompts` | dict/object variables rejected; historical dict rows visible | admin only | create/update/default/disable/assignment/quarantine logged | Existing row data preserved; no destructive delete. |
| Runtime fault action copy | central TS dictionary | `web/src/lib/support/runtime-fault-actions.ts` | `/support/runtime` read-only support/admin surface | unknown kind uses safe default | support/admin page access | no DB audit for copy change | source code revert; future config migration recommended. |
| Admin settings read-only tabs | disabled/readonly | `web/src/app/admin/settings/page.tsx` | `/admin/settings` | controls disabled until persistence contract exists | admin page | deferred owner: Admin platform | rollback by reverting copy; no data mutation. |
| RAG legacy profiles | existing API response | `/api/v1/admin/rag-profiles` client | `/admin/rag-profiles`; recommended `/admin/retrieval-strategies` | API failure != empty state | admin | backend API owner | retry or use retrieval strategies. |

## Remaining Risk / Reverification Commands

- Run Playwright only with services already listening:
  `cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line`
- If live data still contains blocking runtime faults, Support Ops must assign owners from `/support/runtime` linked diagnostics.
- Python 3.14 enablement remains a separate ADR-backed dependency upgrade.
