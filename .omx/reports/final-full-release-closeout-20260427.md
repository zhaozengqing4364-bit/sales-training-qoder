# Final Full Release Closeout — 2026-04-27

Worker: `worker-1`
Model reported by this worker: `gpt-5.5`
Snapshot time: 2026-04-27T04:10Z UTC / 2026-04-27 12:10 Asia/Shanghai

## Scope covered by this worker

This closeout update records worker-1 completion evidence for:

- Task 4 — A-009 PromptTemplate governance regression.
- Task 6 — Python version strategy and local `backend/.venv` repair policy.

It incorporates worker-6 task 1 environment-repair evidence from `.omx/reports/worker-6-task1-venv-repair-20260427T033142Z.log` and task state, without modifying or deleting `backend/.venv-test`.

## Executive verdict

**Not enough evidence here to declare the full release green.** Task 4 and task 6 are closed by this worker, and task 1 is closed by worker-6. The remaining live audit/static gate tasks must still be integrated by the leader before a final ship/no-ship decision.

## Closed items

| Item | Status | Evidence |
| --- | --- | --- |
| Task 1 — repair `backend/.venv` | Completed by worker-6 | `backend/.venv` recreated from Python 3.11.15; broken Python 3.11.12 quarantined; `.venv-test` untouched; imports, `pip check`, ruff, targeted pytest passed. |
| Task 4 — A-009 PromptTemplate governance | Completed by worker-1 | Commit `6be2c4a5`; backend prompt suite `114 passed`; frontend tsc/lint/client vitest passed; safe rollback and backend-owned admin options implemented. |
| Task 6 — Python version strategy | Completed by worker-1 | `docs/adr/2026-04-27-local-venv-repair-policy.md` plus existing Python support ADRs. |

## Python policy

- Primary dev/CI backend target: Python 3.11.
- Release-line supported range: `>=3.11,<3.14` from `backend/pyproject.toml`.
- CI release truth gate uses Python 3.11.
- Python 3.14 is not a supported runtime for this release; `.venv-test` may remain an auxiliary local verification environment only.
- Owner: Backend Platform / Release Engineering.
- Migration path: upgrade and recertify Pydantic/LangChain/Haystack/Chroma/audio dependencies before widening Python support.

## Local `.venv` repair evidence

Worker-6 recorded:

- Before repair: `backend/.venv` Python 3.11.12 failed `html.entities`, `pip`, and FastAPI import probes.
- Repair: moved broken environment to `backend/.venv.broken-20260427T033229Z` and recreated `backend/.venv` from `/opt/homebrew/opt/python@3.11/bin/python3.11` (Python 3.11.15).
- Verification: `html`, `html.entities`, `ensurepip`, `pip`, `fastapi`, `uvicorn`, `sqlalchemy`, and `ruff` import probes passed; `pip check` passed; backend ruff passed; targeted pytest `6 passed, 1 warning`.
- Protection: `backend/.venv-test` remained untouched and still reports Python 3.14.3.

## Worker-1 verification evidence

| Gate | Result |
| --- | --- |
| `git diff --check` | PASS |
| Backend ruff targeted | PASS — `ruff check src/prompt_templates/service.py src/prompt_templates/models.py src/prompt_templates/api/routes.py tests/integration/test_prompt_templates_api_rbac.py` |
| Backend targeted pytest via `.venv-test` | PASS — `114 passed, 1 warning` for `tests/unit/prompt_templates tests/integration/test_prompt_templates_api_rbac.py` |
| Backend dependency check | PASS from worker-6 repaired `.venv`: `pip check` → `No broken requirements found.` |
| `.venv-test` Python 3.14 preservation | PASS — Python 3.14.3 import/test gate used for backend prompt suite; no mutation performed. |
| Web typecheck | PASS — `npm exec -- tsc --noEmit` |
| Web lint targeted | PASS with 0 errors; 15 pre-existing warnings in `web/src/lib/api/client.ts` |
| Web vitest targeted | PASS — `src/lib/api/client-governance.test.ts`, 1 file / 3 tests |
| Backend modified-file diagnostics | PASS — 0 LSP errors on modified backend files |
| Frontend modified-file diagnostics | PASS — 0 LSP errors on modified frontend files |

## PromptTemplate governance closure summary

Task 4 added or revalidated:

- Save-before-400 behavior for invalid `prompt_type` and object-shaped `variables`.
- Admin options include backend-owned `realtime_scoring` sales binding policy.
- Invalid historical templates remain visible in governance status.
- Migration/audit/rollback path returns explicit governance rollback response.
- Rollback never reactivates invalid historical rows; invalid rows stay disabled until corrected.
- Frontend prompt governance UI consumes backend prompt options instead of duplicating sales binding business rules.

## Remaining release-close conditions for leader integration

Before the full release can be called green, the integrated branch still needs exact fresh evidence for the team-level matrix:

1. Full static/backend/frontend gates from the final integrated branch.
2. Curl health checks on backend `3444` and frontend `3445`.
3. Playwright live audit on the real local stack with JSON/screenshots/trace/console/network evidence.
4. Web full vitest/build/npm audit if not already produced by the final gate owner.
5. Leader confirmation that all worker commits are integrated and no team task remains pending/in-progress.
