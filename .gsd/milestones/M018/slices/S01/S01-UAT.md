# S01: 数据库性能基线 discovery — UAT

**Milestone:** M018
**Written:** 2026-04-11T22:52:37.229Z

# S01: 数据库性能基线 discovery — UAT

**Milestone:** M018

# S01 UAT — query/index baseline discovery

## Preconditions
- Repository dependencies are installed and the backend virtualenv exists at `backend/venv`.
- Execute commands from the repository root: `/Users/zhaozengqing/github/销售训练qoder`.
- No browser or live database is required for acceptance of this slice; the slice closes on focused backend proof plus code-adjacent discovery artifacts.

## Test Case 1 — Code-adjacent baseline inventories exist on the live authority seams
1. Run:
   `rg -n "DB_PERFORMANCE_BASELINE|leaderboard_python_reduce|projection_window|training_records" backend/src/common/analytics backend/src/common/conversation/session_evidence.py backend/src/admin/api/training_records.py`
2. Confirm the output includes the four discovery seams:
   - `ADMIN_ANALYTICS_DB_PERFORMANCE_BASELINE`
   - `HISTORY_QUERY_DB_PERFORMANCE_BASELINE`
   - `SESSION_EVIDENCE_DB_PERFORMANCE_BASELINE`
   - `TRAINING_RECORDS_DB_PERFORMANCE_BASELINE`
3. Confirm the baseline text distinguishes confirmed query-shape facts from index candidates that still require runtime/Postgres proof.

**Expected outcome**
- Command exits 0.
- The current data-plane baseline is stored beside the live backend authority files, not only in external notes.

## Test Case 2 — Focused analytics proof locks the already-confirmed query costs
1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py::test_get_leaderboard_batches_projection_window_and_messages_once backend/tests/unit/common/test_admin_analytics_service.py::test_get_overview_stats_replays_projection_window_for_growth_comparison backend/tests/unit/common/test_leaderboard_service.py::test_calculate_leaderboard_pushes_ranking_aggregation_into_sql -q`
2. Verify the proof behavior:
   - leaderboard batches the projection window and messages instead of per-session message reads;
   - overview stats replays the projection window for current-vs-previous growth comparison;
   - leaderboard ranking aggregation stays in SQL instead of per-user follow-up queries.

**Expected outcome**
- Command exits 0.
- The slice has executable proof for the already-confirmed analytics/leaderboard query-shape costs.

## Test Case 3 — The canonical discovery backlog separates proved gaps from hypotheses
1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py -k "db_performance_baseline or query_index_discovery_conclusions" -q`
2. Confirm the contract keeps `QUERY_INDEX_DISCOVERY_CONCLUSIONS` partitioned into:
   - `confirmed_gaps.focused_proof`
   - `confirmed_gaps.code_path_confirmed`
   - `needs_real_postgres_evidence`
3. Confirm the backlog names both the proved analytics hotspots and the still-hypothesis index candidates.

**Expected outcome**
- Command exits 0.
- Future agents have one executable backlog artifact instead of reconstructing scope from audit prose or grep output.

## Test Case 4 — Full slice gate stays green
1. Run the exact slice verification command:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q`
2. Confirm all focused analytics/leaderboard/discovery tests pass.

**Expected outcome**
- Exit 0.
- 23/23 tests pass.

## Edge Cases To Re-check If This Slice Regresses
1. **Index guess promoted too early:** if a follow-on change moves an item out of `needs_real_postgres_evidence`, verify that real Postgres/runtime evidence was added rather than only code-structure reasoning.
2. **Backlog drift:** if baseline inventories and `QUERY_INDEX_DISCOVERY_CONCLUSIONS` start disagreeing, update the inventories, contract backlog, and focused proof together.
3. **False N+1 assumptions:** if a future agent claims history/progress or leaderboard is classical DB N+1, re-run the focused tests first; current proof shows the main cost is projection-window replay / Python reduction, not per-session DB fanout.
4. **Training-record optimization work:** if `session_to_response()` is changed, re-check that the row-level agent/persona metadata path is truly collapsed rather than merely hidden by fixture shape or caching.

