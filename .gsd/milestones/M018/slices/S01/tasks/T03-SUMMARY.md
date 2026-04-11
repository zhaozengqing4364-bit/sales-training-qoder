---
id: T03
parent: S01
milestone: M018
key_files:
  - backend/tests/contract/test_analytics.py
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Kept the reusable M018 query/index discovery backlog in `backend/tests/contract/test_analytics.py` itself, layered by focused proof, code-path-confirmed gaps, and Postgres-only hypotheses so future work can start from one executable artifact instead of scattered inventory comments.
duration: 
verification_result: passed
completed_at: 2026-04-11T22:46:22.108Z
blocker_discovered: false
---

# T03: Added a layered analytics contract backlog that separates confirmed query/index gaps from Postgres-only hypotheses.

**Added a layered analytics contract backlog that separates confirmed query/index gaps from Postgres-only hypotheses.**

## What Happened

I extended `backend/tests/contract/test_analytics.py` from a baseline-presence check into the canonical M018/S01 discovery conclusion artifact. The contract now pulls in the admin training-records DB baseline alongside the existing admin analytics, history, and session-evidence inventories so the reusable backlog covers the confirmed admin list N+1 seam as well as the projection-window paths already proved in T02. I then added `QUERY_INDEX_DISCOVERY_CONCLUSIONS`, which is explicitly layered into `confirmed_gaps.focused_proof`, `confirmed_gaps.code_path_confirmed`, and `needs_real_postgres_evidence`. The focused-proof bucket names the two gaps already backed by executable proof: overview growth replays the projection window for current-vs-previous comparison, and admin leaderboard still requires a full projection-window load before top-N ranking. The code-path-confirmed bucket preserves the actionable but not yet focused-tested gaps: export fanout rebuilding the same projection window, the admin training-records row-level agent/persona N+1, and the manager-intervention overlay’s duplicate completed-history reload. The Postgres-only bucket keeps the speculative items honest by requiring a measurement plan instead of pretending they are already ready for implementation: practice-session composite window indexes, admin analytics scenario-filter planning, conversation-message timestamp index extension, and admin training-record search text indexes. I drove the change red→green by first making the contract fail on the missing layered backlog, then filling in the discovery artifact with concrete proof/follow-up language so downstream agents can decide whether to open a real optimization slice without re-reading scattered inventory comments.

## Verification

Ran a focused red-green contract gate with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py -k "db_performance_baseline or query_index_discovery_conclusions" -q`; it finished 2 selected tests green after the layered backlog was added. Then ran the full task-plan verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q`; it finished 23/23 green. Also re-checked LSP diagnostics on `backend/tests/contract/test_analytics.py`, `backend/tests/unit/common/test_admin_analytics_service.py`, and `backend/tests/unit/common/test_leaderboard_service.py`; all returned clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py -k "db_performance_baseline or query_index_discovery_conclusions" -q` | 0 | ✅ pass | 2201ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q` | 0 | ✅ pass | 4257ms |

## Deviations

None.

## Known Issues

Repo-root backend pytest still emits the pre-existing pytest-cov warning pattern (`Module src was never imported` / `No data was collected`) for these focused commands, but both verification commands exited 0 and the task gate passed.

## Files Created/Modified

- `backend/tests/contract/test_analytics.py`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
