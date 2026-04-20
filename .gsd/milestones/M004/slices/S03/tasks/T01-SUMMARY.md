---
id: T01
parent: S03
milestone: M004
provides: []
requires: []
affects: []
key_files: ["backend/src/common/api/practice.py", "backend/src/common/db/schemas.py", "backend/tests/contract/test_practice_evidence_contract.py", "backend/tests/integration/test_practice_evidence_flow.py", "backend/tests/integration/test_sales_value_training_flow.py", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Expose retry focus on the existing sales report `retry_entry` payload as `focus_intent` instead of inventing a second retry-launch contract.", "Persist validated create-session retry focus under `voice_policy_snapshot.focus_intent` so later runtime/practice-page work can read the same carry-forward seam from the frozen session snapshot.", "Treat replay-only `replay_anchor` as additive metadata when checking report/replay issue-goal parity in focused tests."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Task verification passed with `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` (9 tests). Adjacent session/report contract coverage also passed with `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_sales_value_training_flow.py tests/integration/test_voice_runtime_session_snapshot.py tests/contract/test_sessions.py` (24 tests), confirming the new `retry_entry.focus_intent` shape and `SessionCreate.focus_intent` persistence did not regress nearby practice/report contracts."
completed_at: 2026-03-25T17:44:24.617Z
blocker_discovered: false
---

# T01: Added structured sales retry focus intent to the report/create-session contract and persisted it on new session snapshots

> Added structured sales retry focus intent to the report/create-session contract and persisted it on new session snapshots

## What Happened
---
id: T01
parent: S03
milestone: M004
key_files:
  - backend/src/common/api/practice.py
  - backend/src/common/db/schemas.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - backend/tests/integration/test_sales_value_training_flow.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Expose retry focus on the existing sales report `retry_entry` payload as `focus_intent` instead of inventing a second retry-launch contract.
  - Persist validated create-session retry focus under `voice_policy_snapshot.focus_intent` so later runtime/practice-page work can read the same carry-forward seam from the frozen session snapshot.
  - Treat replay-only `replay_anchor` as additive metadata when checking report/replay issue-goal parity in focused tests.
duration: ""
verification_result: passed
completed_at: 2026-03-25T17:44:24.618Z
blocker_discovered: false
---

# T01: Added structured sales retry focus intent to the report/create-session contract and persisted it on new session snapshots

**Added structured sales retry focus intent to the report/create-session contract and persisted it on new session snapshots**

## What Happened

Started with TDD: added a focused contract test proving `/api/v1/practice/sessions/{id}/report` should emit a structured sales `retry_entry.focus_intent`, plus an integration flow that reads that payload from report output and posts it back into `POST /api/v1/practice/sessions`. The first red run also exposed a local mismatch in existing report/replay tests because replay now legitimately appends `replay_anchor`; I narrowed those assertions so they continue checking shared issue/goal facts without treating anchor metadata as drift. On the implementation side, I added small helpers in `backend/src/common/api/practice.py` to sanitize/build retry focus intent, reused them from both the report response and the delete-end-session compatibility response, extended `SessionCreate` with an optional `focus_intent` field, and persisted validated sales focus intent into `voice_policy_snapshot.focus_intent` on the new session instead of introducing a new store. I also updated the adjacent sales report integration expectation to the new retry-entry shape, recorded the architectural seam in `.gsd/DECISIONS.md`, added the replay-anchor testing gotcha to `.gsd/KNOWLEDGE.md`, and refreshed the safe-grow loop state/log so downstream work resumes from M004/S03/T01 rather than stale S02 state.

## Verification

Task verification passed with `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` (9 tests). Adjacent session/report contract coverage also passed with `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_sales_value_training_flow.py tests/integration/test_voice_runtime_session_snapshot.py tests/contract/test_sessions.py` (24 tests), confirming the new `retry_entry.focus_intent` shape and `SessionCreate.focus_intent` persistence did not regress nearby practice/report contracts.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` | 0 | ✅ pass | 7140ms |
| 2 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_sales_value_training_flow.py tests/integration/test_voice_runtime_session_snapshot.py tests/contract/test_sessions.py` | 0 | ✅ pass | 8190ms |


## Deviations

In addition to the task-plan files, I updated `backend/src/common/db/schemas.py` so the existing create-session surface can actually accept `focus_intent`, and I refreshed `backend/tests/integration/test_sales_value_training_flow.py` because it had an exact sales `retry_entry` expectation that would otherwise fail against the new contract.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/api/practice.py`
- `backend/src/common/db/schemas.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `backend/tests/integration/test_sales_value_training_flow.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
In addition to the task-plan files, I updated `backend/src/common/db/schemas.py` so the existing create-session surface can actually accept `focus_intent`, and I refreshed `backend/tests/integration/test_sales_value_training_flow.py` because it had an exact sales `retry_entry` expectation that would otherwise fail against the new contract.

## Known Issues
None.
