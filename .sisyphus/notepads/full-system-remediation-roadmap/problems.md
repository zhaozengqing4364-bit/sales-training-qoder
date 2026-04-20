## Initial

## 2026-04-15 — T1 unresolved environment ambiguity
- Repo-local `backend/sitecustomize.py` / `backend/usercustomize.py` are not active in this workspace because Python loads Homebrew global `sitecustomize` first.
- `python3` (3.14.3) and `pytest` (3.13.12) are different interpreter families; shell shims alone are not a trustworthy baseline.
- `/opt/homebrew/opt/python@3.13/bin/python3.13` still lacks `mypy` and cannot import `jwt`, so backend verification remains dependency-incomplete even when the interpreter is pinned.
- `lsp_diagnostics` did not reflect newly added Pyright config files during this session, so the active LSP service likely needs restart or is pinned to external config/state.
- `backend/tests/integration/test_nfr_ci_integration.py:19` inserts `backend/tests/src` instead of `backend/src`, causing stale-path import noise around `common.monitoring.nfr_reporter`.
- JSON-file `lsp_diagnostics` is blocked in this workspace because the configured `biome` server is not installed, so Pyright config files were validated via JSON parsing instead of JSON-language diagnostics.

## 2026-04-15 — T3 remaining environment constraints
- Repo-wide frontend quality gates are still blocked by pre-existing files unrelated to T3, so later remediation tasks still need to clear the existing `tsc`/`eslint`/`next build` backlog before the whole frontend can claim a clean baseline.
- The smoke teardown can distinguish whether PostgreSQL / Redis were already listening before the smoke boot, but brew service state reporting itself is not trustworthy in this workspace; stop/start decisions still rely on port ownership rather than a perfect service-manager signal.

## 2026-04-15 — T4 ambiguities for T6 to resolve explicitly
- `comprehensive_reports.overall_score` is required by the API/runtime contract, but legacy rows from the migration-era schema may still be nullable; T6 must decide whether to backfill to `0.0` or regenerate before enforcing `NOT NULL`.
- If any downstream requirement still needs `comparison_to_baseline`, `total_stages`, `trend_analysis`, or the other migration-era report columns, that requirement is no longer represented in active runtime code and must be re-justified before preserving them.
- `staged_evaluation_results.id` is currently application-generated string UUID text, while migration `006` used a PostgreSQL UUID with `gen_random_uuid()`; T6 should keep one identity strategy and remove the other instead of preserving both semantics.
- There is still no evidence-backed decision to add foreign keys from `staged_evaluation_results` or `comprehensive_reports` to `practice_sessions`; if T6 wants FK enforcement, orphan/backfill behavior must be specified first.

## 2026-04-15 — T2 unresolved follow-up questions
- `backend/src/common/db/schemas.py:259-262` exposes `SessionCreate.focus_intent`, but it is still unclear whether that field should be promoted into `docs/api-contract/sessions.md` as a supported public write contract or remain an internal retry-entry carry-forward detail.
- `backend/src/admin/api/analytics.py` now has a materially large wrapped admin analytics surface, but this task did not author a new dedicated contract file because that would have expanded beyond the requested baseline/diff scope.
- `web/src/app/admin/agents/[id]/page.tsx` still carries local model-config list interfaces; the higher-value `admin/settings` hotspot is fixed, but a smaller duplicate remains for a future cleanup pass.

## 2026-04-15 — T5 evidence closure problems
- Backend auth evidence gathered from repo-root pytest commands still includes non-blocking coverage noise, so future evidence collection should not mistake those warnings for T5 auth regressions.
- No additional auth-local code problem surfaced during this closure run; the remaining blocker was purely missing evidence bookkeeping.

## 2026-04-15 — T5 auth-local typing problems
- `lsp_diagnostics` in this workspace still reports auth dependency imports as unresolved even though the hydrated `backend/venv` can import and run the auth suite successfully; that remaining noise is environmental, not a T5-local code defect.

## 2026-04-16 — T6 remaining problems / constraints
- `lsp_diagnostics` still reports environment-level missing-import noise for `sqlalchemy`, `alembic`, `pytest`, and `dotenv` on the changed backend files, so T6 relied on passing pytest and live Alembic/PostgreSQL verification for correctness evidence.
- `backend/tests/unit/evaluation/test_comprehensive_report_service.py` still has unrelated pre-existing Pyright optional-access errors deep in untouched test sections; T6 verification did not broaden into that older typing backlog.

## 2026-04-16 — T7 evidence closure problems
- No new T7-local code problem surfaced during closure; the only remaining gap was missing evidence/notepad bookkeeping.
- Future reviewers should remember that smoke startup may log transient local service warnings even when the final readiness payload is healthy, so closure should key off the returned health JSON rather than early bootstrap noise.
