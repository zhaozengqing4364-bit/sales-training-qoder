---
id: T01
parent: S06
milestone: M001
provides:
  - Projection-backed supervisor progress snapshot and aligned admin stats score fields
key_files:
  - backend/src/common/analytics/history_service.py
  - backend/src/admin/api/users.py
  - backend/tests/unit/test_history_service_evidence_projection.py
  - backend/tests/integration/test_admin_users_api.py
  - .gsd/milestones/M001/slices/S06/S06-PLAN.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D027: Route admin user-detail stats/progress score-bearing fields through HistoryService projection helpers instead of route-local weighted SQL.
patterns_established:
  - Admin supervisor aggregates must be built from HistoryService summaries, with repeated issue/goal buckets and not-evaluable counts derived from the same SessionEvidence projection used by session previews.
observability_surfaces:
  - practice_history_projection_query(query_name=admin_user_progress|admin_user_projection_scores)
  - GET /api/v1/admin/users/{id}/progress
  - GET /api/v1/admin/users/{id}/stats
  - backend/tests/unit/test_history_service_evidence_projection.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/app/admin/users/[id]/page.test.tsx
duration: 2h
verification_result: passed
completed_at: 2026-03-23T23:56:00+08:00
blocker_discovered: false
---

# T01: 把主管连续变化聚合收口到 HistoryService 并对齐 admin stats/progress

**Aligned admin user stats/progress with HistoryService evidence projections and added supervisor trend buckets.**

## What Happened

I added a supervisor snapshot path to `backend/src/common/analytics/history_service.py` so admin progress now comes from the same completed-session evidence projection already used by session previews. The new helper groups truthful `day/week` trend buckets, separates evaluable vs not-evaluable completed sessions, surfaces repeated `main_issue.issue_type` / `next_goal.goal_type` buckets, computes a conservative `should_switch_focus` recommendation, and logs those fields on `practice_history_projection_query`.

I then rewired `backend/src/admin/api/users.py` so `/api/v1/admin/users/{id}/progress` calls the new HistoryService snapshot and `/api/v1/admin/users/{id}/stats` reads projection-backed `average_score` / `best_score` / `worst_score` from HistoryService instead of route-local 0.4/0.3/0.3 SQL math. Raw totals, completion rate, and usage breakdowns still come from the existing SQL query path.

To lock the contract, I added a unit test for supervisor snapshot granularity/repeated buckets/recommendation/log fields and an integration test proving `/stats` matches `/sessions` preview scores while `/progress` exposes repeated blockers, repeated next goals, not-evaluable counts, and weekly grouping.

## Verification

Fresh backend task-level verification passed, including the full focused unit+integration suite and the narrower `/progress` / `/stats` API check. I also ran the slice-level web page test so T01 ends with both backend evidence and a confirmed non-breaking admin page baseline. Manual `/admin/users/{id}` runtime review is still deferred to T02 because the page has not yet been converted to the new supervisor summary UI.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py` | 0 | ✅ pass | 3.40s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py -k 'progress or stats'` | 0 | ✅ pass | 2.73s |
| 3 | `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 0.72s |
| 4 | Manual/runtime review for `/admin/users/{id}` | n/a | ⚪ deferred | n/a |

## Diagnostics

- `practice_history_projection_query` now emits supervisor-specific fields under `query_name=admin_user_progress`: `repeated_main_issues`, `repeated_next_goals`, `should_switch_focus`, and `recommendation_reason`.
- `query_name=admin_user_projection_scores` shows the same projection coverage counts used to align admin `/stats` with `/sessions` preview facts.
- Focused inspection surfaces: `GET /api/v1/admin/users/{id}/progress`, `GET /api/v1/admin/users/{id}/stats`, `backend/tests/unit/test_history_service_evidence_projection.py`, and `backend/tests/integration/test_admin_users_api.py`.

## Deviations

- Pre-flight required a slice-plan correction: I added an explicit focused `/progress` / `/stats` verification step plus inline failure-state wording to `.gsd/milestones/M001/slices/S06/S06-PLAN.md` before implementation.
- Weekly trend buckets use week-start ISO dates (`Monday 00:00 UTC`) as the bucket label so `granularity=week` is inspectable and unambiguous.

## Known Issues

- The admin user detail page still renders the old generic progress summary; T02 still needs to consume the richer supervisor payload and finish the inline empty/error UX.
- Manual browser/runtime review for `/admin/users/{id}` is intentionally deferred until T02 ships the page-level consumer.

## Files Created/Modified

- `backend/src/common/analytics/history_service.py` — added projection-backed supervisor snapshot, repeated issue/goal aggregation, recommendation logic, and progress/stat logs.
- `backend/src/admin/api/users.py` — replaced route-local weighted SQL score math with HistoryService-backed `/stats` and `/progress` reads.
- `backend/tests/unit/test_history_service_evidence_projection.py` — added supervisor snapshot unit coverage for day/week granularity, repeated buckets, recommendation, and log fields.
- `backend/tests/integration/test_admin_users_api.py` — added admin `/progress` + `/stats` alignment proof against projection-backed `/sessions` previews.
- `.gsd/milestones/M001/slices/S06/S06-PLAN.md` — added the missing focused failure-path verification step and marked the task-ready verification surface explicitly.
- `.gsd/KNOWLEDGE.md` — recorded the projection test fixture gotcha about session-row scores taking precedence over message snapshots.
- `.gsd/DECISIONS.md` — appended D027 for the HistoryService-as-single-score-truth decision.
