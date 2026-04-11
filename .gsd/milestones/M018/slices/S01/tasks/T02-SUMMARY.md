---
id: T02
parent: S01
milestone: M018
key_files:
  - backend/tests/contract/test_analytics.py
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/unit/common/test_leaderboard_service.py
key_decisions:
  - Kept T02 strictly evidence-building: add executable baseline proof in tests/contracts without preemptively changing query shapes or adding indexes.
duration: 
verification_result: passed
completed_at: 2026-04-11T22:39:32.948Z
blocker_discovered: false
---

# T02: Added evidence-backed DB baseline tests for analytics projection and leaderboard query shapes

**Added evidence-backed DB baseline tests for analytics projection and leaderboard query shapes**

## What Happened

I turned the first-round DB baseline from code-adjacent inventory into executable proof without changing the runtime queries themselves. In `backend/tests/unit/common/test_admin_analytics_service.py` I added SQL-capture helpers plus focused tests that prove two confirmed admin analytics behaviors: `get_leaderboard()` loads one projection window and one batched `conversation_messages ... IN (...)` query for multiple sessions instead of per-session message reads, and `get_overview_stats(time_range="30d")` replays the projection window twice for current-vs-previous growth comparison, including a second batched message fetch. In `backend/tests/unit/common/test_leaderboard_service.py` I added a focused SQL-shape proof showing `LeaderboardService.calculate_leaderboard()` keeps ranking aggregation in SQL via one grouped AVG/MAX query plus one `count(distinct users.user_id)` query, rather than issuing per-user follow-ups. In `backend/tests/contract/test_analytics.py` I added a contract guard that keeps the M018 baseline inventories aligned to the expected hotspot paths and explicitly requires each entry to carry both a confirmed query-shape fact and an evidence-level marker that still points to runtime/Postgres proof for index prioritization. Together these tests give downstream work a concrete baseline for what is already proven versus what remains hypothesis-level.

## Verification

Ran a focused pytest proof for the new evidence-backed baseline tests only, covering the contract baseline partition plus the new admin-analytics and leaderboard SQL-shape assertions; all 4 targeted tests passed. Then ran the full task verification command from the plan — `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q` — and all 22 tests passed. Also checked LSP diagnostics on `backend/tests/contract/test_analytics.py`, `backend/tests/unit/common/test_admin_analytics_service.py`, and `backend/tests/unit/common/test_leaderboard_service.py`; all returned clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py::TestAnalyticsContract::test_db_performance_baseline_keeps_confirmed_shapes_separate_from_runtime_hypotheses backend/tests/unit/common/test_admin_analytics_service.py::test_get_leaderboard_batches_projection_window_and_messages_once backend/tests/unit/common/test_admin_analytics_service.py::test_get_overview_stats_replays_projection_window_for_growth_comparison backend/tests/unit/common/test_leaderboard_service.py::test_calculate_leaderboard_pushes_ranking_aggregation_into_sql -q` | 0 | ✅ pass | 2947ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q` | 0 | ✅ pass | 5130ms |

## Deviations

None.

## Known Issues

Focused repo-root pytest runs still emit the existing pytest-cov "Module src was never imported / No data was collected" warning pattern for these backend test files, but the verification commands exit 0 and the task gate passed.

## Files Created/Modified

- `backend/tests/contract/test_analytics.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/unit/common/test_leaderboard_service.py`
