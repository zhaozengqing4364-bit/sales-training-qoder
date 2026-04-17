## Initial

## 2026-04-15 — T1 baseline decisions
- Added `backend/pyrightconfig.json` so backend-local editor/CLI usage has an explicit diagnostics scope for `src`, `tests`, `alembic`, and `scripts`.
- Added repo-root `pyrightconfig.json`, but scoped only to backend paths, because the live LSP behavior appears repo-rooted rather than `backend/`-rooted.
- Kept root `pyproject.toml` and `backend/pyproject.toml` pytest `pythonpath` settings distinct; the baseline documents `backend/` as the canonical working directory instead of merging configs prematurely.
- Did not touch auth/db/realtime/admin business logic even where real defects were confirmed; T1 only classifies and freezes the backlog.

## 2026-04-15 — T3 baseline decisions
- Chose thin wrapper scripts (`scripts/dev-smoke-up.sh` / `scripts/dev-smoke-stop.sh`) instead of introducing Docker Compose, because the repo already had a real non-Docker authority in `scripts/dev-up.sh` / `scripts/dev-stop.sh`.
- Chose Playwright global setup/teardown over `webServer` because `scripts/dev-up.sh` backgrounds backend/frontend and exits; explicit lifecycle hooks are a safer fit for this repo’s existing process model.
- Chose to auto-run `npx playwright install chromium` in Playwright global setup so `cd web && npx playwright test` remains a one-command smoke entry even on a fresh workstation.
- Chose API-driven session creation for practice smoke (discover published agent/persona at runtime, then POST `/practice/sessions`) instead of hard-coding seed IDs or adding broad test-only product behavior.

## 2026-04-15 — T4 canonical schema decisions
- Canonical truth for the report/evaluation storage layer is defined in `.sisyphus/evidence/task-4-schema-baseline.md`, with runtime read/write paths used as the deciding authority when ORM and historical migrations disagree.
- `staged_evaluation_results` remains a surrogate-key table (`id`) but must also keep the unique `(session_id, stage_number)` contract and the runtime-required `weaknesses` field.
- `comprehensive_reports` uses `session_id` as the canonical primary key; the migration-era surrogate `id` and legacy analytics-summary columns are non-canonical.
- `practice_sessions.report_status/report_generated_at/report_error` remain the canonical control-plane state for report generation; report content itself belongs in `comprehensive_reports`.

## 2026-04-15 — T2 shared typing boundary decisions
- The shared admin model-config contract surface now lives in `web/src/lib/api/types.ts` under `AdminModelConfig*` names, preserving backend snake_case field names instead of inventing camelCase API aliases in route-local pages.
- `web/src/lib/api/client.ts` is treated as a consumer of that shared type surface, not a second type authority; route-local pages may alias imported types for readability, but they should not own duplicate request/response interfaces.
- This task intentionally stopped at `admin/settings` + shared client/types rather than normalizing every remaining consumer (for example `web/src/app/admin/agents/[id]/page.tsx`) so downstream tasks can continue on a stable but narrowly scoped baseline.

## 2026-04-15 — T5 evidence closure decisions
- Closed T5 with evidence-only work because the live backend auth integration suite and frontend auth-focused Vitest suite already verified the implemented WeCom SSO + explicit dev fallback behavior; no further auth code changes were justified.
- Used plain-text evidence artifacts instead of screenshots because the missing deliverable was verification traceability, not visual diagnosis.
- Recorded both broad auth-slice commands and scenario-focused commands so future reviewers can verify either the whole auth seam or just the T5-critical SSO/dev-fallback behaviors.

## 2026-04-15 — T5 auth-local typing decisions
- Resolved the remaining real auth-local LSP defects with annotation-only changes (`str | None` helper params and `NoReturn` for the auth error raiser) instead of adding new runtime branches, because the functional tests already proved the behavior was correct.

## 2026-04-16 — T6 reconciliation decisions
- Kept the T4 canonical schema exactly as documented: `staged_evaluation_results` keeps text `id` + unique `(session_id, stage_number)` and regains persisted `weaknesses`; `comprehensive_reports` stays keyed by `session_id` with `created_at` as the persisted timestamp name.
- Chose production-only startup exclusion for the two report/evaluation content tables: `init_db()` still bootstraps the rest of the metadata, but production no longer silently creates or repairs these two tables outside Alembic authority.
- Ordered the new report/evaluation production guard after the existing persona/knowledge compatibility guards so legacy-persona failures still surface with their original targeted error message.
- Verified the migration through direct upgrade to `ae1dbf12bd03` from stamped pre-T6 state instead of broad `head`, because the unrelated `001` branch debt is not part of T6 and should not be “fixed” under this task.

## 2026-04-16 — T7 evidence closure decisions
- Used a plain-text telemetry evidence artifact (`task-7-telemetry.txt`) instead of a HAR because the targeted Vitest suite plus extracted asserted URLs gives a more deterministic proof of dispatch targets/behavior than an ad-hoc browser capture.
- Kept T7 closure evidence-only: no additional code change was needed because Atlas already confirmed the telemetry/health fixes and local diagnostics state.

## 2026-04-16 — T9 quality-gate decisions
- Kept T9 centered on one ordered authority script (`scripts/critical-quality-gate.sh`) and made the GitHub workflow call that script directly, so local and CI gate order cannot drift.
- Chose deterministic report/replay seeding during smoke bootstrap instead of adding test-only product APIs or hard-coded session IDs; the smoke harness now owns the minimum data needed for dashboard/report/replay coverage.
- Scoped the Vitest stage to the critical-flow slice and excluded `tests/e2e/**` from Vitest discovery because T9 is a release-confidence gate for the smoke surface, not a mandate to fix every unrelated frontend test already present in the repo.
