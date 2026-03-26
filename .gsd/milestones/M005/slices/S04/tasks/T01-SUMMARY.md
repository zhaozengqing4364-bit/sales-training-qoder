---
id: T01
parent: S04
milestone: M005
provides: []
requires: []
affects: []
key_files: ["backend/src/common/analytics/admin_analytics_service.py", "backend/src/admin/api/analytics.py", "backend/tests/unit/common/test_admin_analytics_service.py", "backend/tests/contract/test_analytics.py", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M005/slices/S04/tasks/T01-SUMMARY.md"]
key_decisions: ["Normalize blocker families through HistoryService issue-family aliases before exposing cohort/department buckets.", "Treat each user’s latest evaluable completed session as the source of truth for current not-passed risk membership.", "Expose the weekly operating pack as a dedicated `/admin/analytics/operating-pack` payload instead of mutating the shipped overview/trends contracts."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan backend verification command `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/contract/test_analytics.py` and confirmed the new operating-pack unit coverage plus analytics contract coverage both pass, including the dedicated `/api/v1/admin/analytics/operating-pack` route."
completed_at: 2026-03-26T10:49:10.348Z
blocker_discovered: false
---

# T01: Add a projection-backed admin operating-pack API for weekly blocker, department, degradation, and manager-risk views.

> Add a projection-backed admin operating-pack API for weekly blocker, department, degradation, and manager-risk views.

## What Happened
---
id: T01
parent: S04
milestone: M005
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/admin/api/analytics.py
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/contract/test_analytics.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M005/slices/S04/tasks/T01-SUMMARY.md
key_decisions:
  - Normalize blocker families through HistoryService issue-family aliases before exposing cohort/department buckets.
  - Treat each user’s latest evaluable completed session as the source of truth for current not-passed risk membership.
  - Expose the weekly operating pack as a dedicated `/admin/analytics/operating-pack` payload instead of mutating the shipped overview/trends contracts.
duration: ""
verification_result: passed
completed_at: 2026-03-26T10:49:10.352Z
blocker_discovered: false
---

# T01: Add a projection-backed admin operating-pack API for weekly blocker, department, degradation, and manager-risk views.

**Add a projection-backed admin operating-pack API for weekly blocker, department, degradation, and manager-risk views.**

## What Happened

Added a new `/api/v1/admin/analytics/operating-pack` route on the existing admin analytics router and backed it with a projection-based operating-pack aggregation in `AdminAnalyticsService`. The new payload derives weekly cohort blocker-family buckets, department issue buckets, degradation/not-evaluable breakdowns, inactive and improving lists, and current not-passed risk membership from the same session-evidence projection used by learner and supervisor surfaces. Blocker families are normalized through `HistoryService`’s issue-family aliases so downstream drill-ins align with intervention focus families, and current risk membership is anchored to each learner’s latest evaluable completed session so older fails do not keep recovered learners on the weekly risk list. Added a real projection-backed unit test with seeded sessions plus degraded conversation-message evidence, a contract test for the new route, recorded the semantic choice in `.gsd/DECISIONS.md`, and added a knowledge note warning future work not to regress the latest-evaluable-per-user risk logic.

## Verification

Ran the task-plan backend verification command `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/contract/test_analytics.py` and confirmed the new operating-pack unit coverage plus analytics contract coverage both pass, including the dedicated `/api/v1/admin/analytics/operating-pack` route.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/contract/test_analytics.py` | 0 | ✅ pass | 19200ms |


## Deviations

Added a dedicated `/admin/analytics/operating-pack` endpoint on the existing analytics router instead of extending the existing overview or trends responses, so T02 can consume one coherent weekly pack payload without destabilizing the S01 analytics contracts.

## Known Issues

The current admin analytics page still reads the older manager-lite endpoint; until T02 switches the weekly UI onto `operating-pack.manager_lists`, `/api/v1/admin/interventions/lists` and `/api/v1/admin/analytics/operating-pack` may disagree for learners who failed earlier in the window but later recovered in a newer evaluable session.

## Files Created/Modified

- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/admin/api/analytics.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/contract/test_analytics.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M005/slices/S04/tasks/T01-SUMMARY.md`


## Deviations
Added a dedicated `/admin/analytics/operating-pack` endpoint on the existing analytics router instead of extending the existing overview or trends responses, so T02 can consume one coherent weekly pack payload without destabilizing the S01 analytics contracts.

## Known Issues
The current admin analytics page still reads the older manager-lite endpoint; until T02 switches the weekly UI onto `operating-pack.manager_lists`, `/api/v1/admin/interventions/lists` and `/api/v1/admin/analytics/operating-pack` may disagree for learners who failed earlier in the window but later recovered in a newer evaluable session.
