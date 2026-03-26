---
id: T01
parent: S01
milestone: M005
provides: []
requires: []
affects: []
key_files: ["backend/src/common/analytics/admin_analytics_service.py", "backend/src/common/analytics/history_service.py", "backend/src/admin/api/users.py", "backend/tests/unit/common/test_admin_analytics_service.py", "backend/tests/integration/test_admin_users_api.py", "backend/tests/contract/test_analytics.py", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Recorded D074: admin analytics aggregates from HistoryService / SessionEvidenceService projection summaries instead of legacy weighted SQL score math.", "Carried evaluability and score-basis metadata through admin analytics and admin user stats instead of keeping the new semantics implicit in averages alone."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the focused backend verification suite from the slice plan: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py`. All 27 targeted tests passed, covering projection-backed overview/trends/leaderboard/agent stats, aligned admin user stats/progress, and admin analytics contract metadata."
completed_at: 2026-03-26T05:47:47.828Z
blocker_discovered: false
---

# T01: Switched admin analytics and user stats to projection-backed session evidence summaries with evaluability metadata.

> Switched admin analytics and user stats to projection-backed session evidence summaries with evaluability metadata.

## What Happened
---
id: T01
parent: S01
milestone: M005
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/common/analytics/history_service.py
  - backend/src/admin/api/users.py
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/contract/test_analytics.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Recorded D074: admin analytics aggregates from HistoryService / SessionEvidenceService projection summaries instead of legacy weighted SQL score math.
  - Carried evaluability and score-basis metadata through admin analytics and admin user stats instead of keeping the new semantics implicit in averages alone.
duration: ""
verification_result: passed
completed_at: 2026-03-26T05:47:47.828Z
blocker_discovered: false
---

# T01: Switched admin analytics and user stats to projection-backed session evidence summaries with evaluability metadata.

**Switched admin analytics and user stats to projection-backed session evidence summaries with evaluability metadata.**

## What Happened

Added focused red tests for the admin analytics service and current admin API surfaces, then replaced the old 0.4/0.3/0.3 SQL score aggregation with HistoryService-backed projection summaries. Admin analytics overview/trends/leaderboard/agent stats now aggregate from the same completed-session evidence line used by learner/admin drill-ins and expose evaluability-aware fields such as score_basis, evaluable/not-evaluable counts, top issue families, and primary issue/next-goal types. The admin user stats route now forwards the same evaluability metadata so drill-in surfaces stay aligned with the corrected admin truth line. I also recorded the projection-source decision in GSD and added a knowledge note about admin analytics RBAC being applied in main.py router wiring rather than the endpoint file itself.

## Verification

Ran the focused backend verification suite from the slice plan: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py`. All 27 targeted tests passed, covering projection-backed overview/trends/leaderboard/agent stats, aligned admin user stats/progress, and admin analytics contract metadata.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py` | 0 | ✅ pass | 8300ms |


## Deviations

Expanded `backend/tests/contract/test_analytics.py` to cover `/api/v1/admin/analytics/*` directly and corrected those checks to allow the real 403 branch because admin RBAC is applied in `backend/src/main.py` router wiring, not inside `backend/src/admin/api/analytics.py`.

## Known Issues

Unrelated `passlib` / Python `crypt` deprecation warning still appears in the focused pytest output. It does not affect admin analytics semantics.

## Files Created/Modified

- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/admin/api/users.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/contract/test_analytics.py`
- `.gsd/KNOWLEDGE.md`


## Deviations
Expanded `backend/tests/contract/test_analytics.py` to cover `/api/v1/admin/analytics/*` directly and corrected those checks to allow the real 403 branch because admin RBAC is applied in `backend/src/main.py` router wiring, not inside `backend/src/admin/api/analytics.py`.

## Known Issues
Unrelated `passlib` / Python `crypt` deprecation warning still appears in the focused pytest output. It does not affect admin analytics semantics.
