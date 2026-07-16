# Implementation Notes — Team Workbench Perf Fix

## Completed

### Slice 1 — Journey list summary
- Added `JourneySummaryReadService` with batch enrollment page load, one active revision resolve, optional one-shot stale enrollment heal, batched latest attempts, batched lesson progress, and summary projection.
- `GET /admin/newcomer-training/journeys` now returns `summary` DTO (not full `journey` tree). Detail `GET /journeys/{learner_id}` unchanged.
- List commits only when enrollment revisions were healed.
- Frontend consumers updated: `/team`, `/admin/newcomer-training/learners`, types, `toTeamJourneyRow`, API contract doc.

### Slice 2 — Workbench light path
- `_filtered_training_tasks` / `_filtered_sessions` push `created_at` / `start_time` bounds into SQL.
- Added `SupervisorReviewService.get_team_workbench()`; API no longer builds full insights then drops fields.
- Lazy retraining fallback only when report weaknesses are empty; no per-learner score refresh.

### Slice 3 — `/team` UX
- Search draft + ≥300ms debounce to URL.
- Scope loaded once (manual refresh reloads scope).
- `initialLoading` vs refreshing live region; partial failure states for journeys / current / previous workbench.
- Request generation guard against stale responses.
- **Check fix**: `initialLoading` no longer clears when only `scope` resolves; full-page Skeleton stays until the first journeys/workbench payload (or a data error) arrives. Vitest covers this gap.

### Slice 0/4 — Tests & evidence
- Performance tests: SQL constancy for journey limits, date predicate capture, workbench query bound, 500→limit 100 total/returned.
- Added heal-once stale enrollment test and summary↔full journey progress/next/risk parity test.
- Removed wall-clock `elapsed < 0.5` from team-lead insights integration test.
- Frontend vitest coverage for debounce, previous-period failure, refresh retention, initial Skeleton gate, view-model mapping.

## Deviations
- Full before/after 50/100/500 median/p95 latency harness with 10 samples was not run in a controlled PostgreSQL environment; structural SQL-count tests are the CI gate. Absolute ms must not be claimed as production SLO.
- Workbench 50→100 linear-growth comparison uses a single 100-learner seed + query-count ceiling instead of two sequential seeds in one session (avoids dirty DB accumulation).

## Residual risks
- Journey list still caps at 100 rows; 500-person teams need separate pagination product work.
- Dual workbench period calls remain; payload still duplicates learner rows for comparison UX.
- SQLite date timezone behavior may differ from PostgreSQL; date predicate presence is asserted, inclusive boundary parity covered by existing filter semantics + SQL capture.

## Not touched
- `/admin/teams` and related admin team maintenance code.
