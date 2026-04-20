---
id: S01
parent: M018
milestone: M018
provides:
  - A reusable query/index discovery baseline for analytics/history/projection/admin read paths.
  - A focused proof bundle that distinguishes already-proved query costs from unproved index ideas.
  - One canonical follow-up backlog (`QUERY_INDEX_DISCOVERY_CONCLUSIONS`) future performance slices can start from.
requires:
  []
affects:
  - future performance implementation slices on analytics/history/projection/admin read paths
  - M018/S02 and M018/S03 downstream baseline consumers
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/common/analytics/history_service.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/admin/api/training_records.py
  - backend/tests/contract/test_analytics.py
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/unit/common/test_leaderboard_service.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D203 — keep the first-round M018 DB performance baseline in code-adjacent inventories and grade confirmed query-shape facts separately from unproved index ideas.
  - D204 — keep `QUERY_INDEX_DISCOVERY_CONCLUSIONS` in `backend/tests/contract/test_analytics.py` as the canonical layered follow-up backlog.
patterns_established:
  - Keep performance discovery artifacts in live authority files plus focused contract/unit tests, not in markdown-only audits.
  - Partition discovery into focused-proof-confirmed gaps, code-path-confirmed gaps, and real-Postgres/runtime hypotheses.
  - Require real Postgres evidence before turning index ideas into implementation scope.
observability_surfaces:
  - Code-adjacent inventories: `ADMIN_ANALYTICS_DB_PERFORMANCE_BASELINE`, `HISTORY_QUERY_DB_PERFORMANCE_BASELINE`, `SESSION_EVIDENCE_DB_PERFORMANCE_BASELINE`, `TRAINING_RECORDS_DB_PERFORMANCE_BASELINE`.
  - Contract backlog seam: `backend/tests/contract/test_analytics.py::QUERY_INDEX_DISCOVERY_CONCLUSIONS`.
  - Focused proof seams: `test_get_leaderboard_batches_projection_window_and_messages_once`, `test_get_overview_stats_replays_projection_window_for_growth_comparison`, and `test_calculate_leaderboard_pushes_ranking_aggregation_into_sql`.
  - Fresh slice gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q`.
drill_down_paths:
  - .gsd/milestones/M018/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M018/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M018/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T22:52:37.227Z
blocker_discovered: false
---

# S01: 数据库性能基线 discovery

**Established an evidence-backed query/index discovery baseline for analytics, history/projection, leaderboard, and admin training records, separating proved query-cost gaps from hypotheses that still need real Postgres evidence.**

## What Happened

# S01: 数据库性能基线 discovery

**Turned audit-era performance suspicion into one reusable discovery baseline:** the live analytics/history/projection/admin seams now carry code-adjacent DB hotspot inventories, focused backend tests prove which query shapes are already confirmed, and one layered contract backlog tells future slices exactly which items are ready for implementation discussion versus which still require real Postgres/runtime evidence.

## Delivered
- Added code-adjacent DB baseline inventories at the live authority seams:
  - `backend/src/common/analytics/admin_analytics_service.py`
  - `backend/src/common/analytics/history_service.py`
  - `backend/src/common/conversation/session_evidence.py`
  - `backend/src/admin/api/training_records.py`
- Added executable proof in:
  - `backend/tests/unit/common/test_admin_analytics_service.py`
  - `backend/tests/unit/common/test_leaderboard_service.py`
  - `backend/tests/contract/test_analytics.py`
- Recorded the reusable discovery conclusion in `QUERY_INDEX_DISCOVERY_CONCLUSIONS`, split into:
  - `confirmed_gaps.focused_proof`
  - `confirmed_gaps.code_path_confirmed`
  - `needs_real_postgres_evidence`
- Saved the slice-level decision/knowledge handoff so later agents know where the canonical performance-discovery seam lives.

## What This Slice Actually Established
1. **The main proved admin analytics cost today is repeated projection-window work, not hidden leaderboard SQL N+1.**
   - `get_overview_stats(time_range="30d")` replays the projection window for current-vs-previous comparison.
   - admin leaderboard still loads a full projection window before top-N ranking.
2. **History/progress is heavy, but not a classical DB N+1 path.**
   - The current history/progress path batches sessions and messages instead of issuing per-session DB reads.
   - Its cost comes from rebuilding session projections over large windows, especially when manager-intervention overlays trigger an extra reload.
3. **There is one confirmed row-level admin N+1 seam worth future implementation attention.**
   - `backend/src/admin/api/training_records.py::session_to_response()` can still issue per-record agent/persona lookups after the page query completes.
4. **Index work remains hypothesis-level unless real Postgres evidence says otherwise.**
   - Practice-session composite window indexes, analytics scenario-filter planning, message timestamp index extension, and training-record search indexes are now explicitly classified as “needs real Postgres evidence”, not pre-approved fixes.
5. **The discovery artifact is now executable and code-adjacent.**
   - Future slices do not need to reconstruct this baseline from grep output or audit prose; they can start from the inventories + focused tests + layered backlog contract.

## Patterns Established For Future Work
- Keep performance discovery conclusions beside the live backend authority seams and pin them with focused contract/unit tests.
- Separate **focused-proof-confirmed gaps**, **code-path-confirmed gaps**, and **runtime/Postgres-only hypotheses** before opening an implementation slice.
- Do not convert index guesses into implementation work until EXPLAIN / pg_stat_statements / real runtime timing proves the bottleneck.
- When the discovery backlog changes, update the code-adjacent inventories, `QUERY_INDEX_DISCOVERY_CONCLUSIONS`, and the focused analytics tests together.

## Downstream Notes
- The strongest implementation candidates after this slice are the repeated admin analytics projection rebuilds and the training-records agent/persona row-level N+1 seam.
- Index candidates remain intentionally deferred pending real database evidence; this slice proves where to measure next, not which indexes to add immediately.
- M018/S02 and M018/S03 can now treat the data-plane baseline as known context instead of reverse-engineering query hotspots from scratch.

## Requirements Advanced
None.

## Requirements Validated
None.

## New Requirements Surfaced
None.

## Requirements Invalidated or Re-scoped
None.

## Known Limitations
- This slice does **not** include live Postgres `EXPLAIN`, `pg_stat_statements`, or production/runtime timing evidence; index candidates remain hypotheses by design.
- The focused pytest gate still emits the existing pytest-cov `Module src was never imported / No data was collected` warnings on repo-root backend runs, but the suite exits 0 and the slice proof remains green.
- No production observability surface yet exposes these query costs directly; today the trustworthy baseline is the code-adjacent inventory plus focused test bundle.

## Follow-ups
1. Open a narrow implementation slice for the proved projection-window replay hotspots (`overview`, `leaderboard`, `export`) if product priority warrants it.
2. Open a narrow implementation slice for the admin training-records row-level agent/persona N+1 seam.
3. Gather real Postgres/runtime evidence before promoting any index candidate out of `needs_real_postgres_evidence`.


## Verification

Fresh slice-close verification passed from the repository root. `rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api` exited 0 and surfaced the intended analytics/history/projection/admin query inventory seams. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q` exited 0 with 23/23 tests passing. Fresh LSP diagnostics on `backend/tests/contract/test_analytics.py`, `backend/tests/unit/common/test_admin_analytics_service.py`, and `backend/tests/unit/common/test_leaderboard_service.py` returned no diagnostics. The pytest run still reported the pre-existing pytest-cov no-data warning pattern, but it was non-blocking and did not invalidate the green test result.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

- No live Postgres EXPLAIN / pg_stat_statements / runtime timing evidence yet; index candidates remain intentionally hypothesis-level.
- Repo-root backend pytest still emits the pre-existing pytest-cov no-data warning pattern on this focused slice bundle.

## Follow-ups

None.

## Files Created/Modified

- `backend/src/common/analytics/admin_analytics_service.py` — Added code-adjacent admin analytics DB hotspot inventory and evidence-level notes.
- `backend/src/common/analytics/history_service.py` — Added history/progress projection-window baseline inventory and N+1/non-N+1 classification.
- `backend/src/common/conversation/session_evidence.py` — Added session-evidence projection cost baseline for per-session message fan-in.
- `backend/src/admin/api/training_records.py` — Added admin training-records DB baseline noting the row-level agent/persona N+1 seam.
- `backend/tests/contract/test_analytics.py` — Added the layered `QUERY_INDEX_DISCOVERY_CONCLUSIONS` contract and baseline-presence guards.
- `backend/tests/unit/common/test_admin_analytics_service.py` — Added focused SQL-shape proof for overview and leaderboard projection behavior.
- `backend/tests/unit/common/test_leaderboard_service.py` — Added focused SQL-shape proof that ranking aggregation stays in SQL.
- `.gsd/DECISIONS.md` — Recorded the canonical location of the reusable query/index discovery backlog (D204).
- `.gsd/KNOWLEDGE.md` — Captured the follow-on rule to keep inventories, discovery backlog, and focused proof aligned.
