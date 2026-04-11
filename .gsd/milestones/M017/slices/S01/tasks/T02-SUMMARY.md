---
id: T02
parent: S01
milestone: M017
key_files:
  - backend/src/common/db/session_lifecycle.py
  - backend/tests/unit/test_session_lifecycle_service.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D197: choose optimistic compare-and-swap on `PracticeSession.status` instead of row locks so the lifecycle race is provable in the focused SQLite-backed suite.
  - Only stale writers that lose to an already-persisted terminal state converge to a no-op; fresh pause/resume requests against terminal sessions remain invalid transitions.
duration: 
verification_result: passed
completed_at: 2026-04-11T21:08:06.167Z
blocker_discovered: false
---

# T02: Added optimistic lifecycle convergence so stale pause/resume writes no longer reopen terminal sessions

**Added optimistic lifecycle convergence so stale pause/resume writes no longer reopen terminal sessions**

## What Happened

I promoted the T01 stale-writer proof from strict xfail into an enforced passing contract, then implemented the convergence logic inside `backend/src/common/db/session_lifecycle.py` instead of scattering guards across REST/WebSocket callers. The service now persists lifecycle mutations with an optimistic compare-and-swap on `PracticeSession.status` (`UPDATE ... WHERE session_id=:id AND status=:observed_status`). When that write loses a race, the service loads the latest persisted lifecycle row through an independent async session, logs `practice_session_lifecycle_concurrency_conflict`, syncs the in-memory session back to the durable state, and converges stale non-terminal writers that hit an already-terminal session (`scoring` / `completed`) into `changed=False` no-ops instead of reopening the session. For non-terminal conflicts, the service retries once from the persisted state so normal same-action/idempotent convergence still works. This keeps the existing terminal split intact (`sales -> scoring`, `presentation -> completed`) and leaves report/replay unlock semantics unchanged because only the stale overwrite window changed, not the terminal targets or downstream end-of-session behavior. I updated the unit tests to separate pure state-machine assertions from explicit conflict-path assertions, and I upgraded the integration race proof so it now requires the stale writer itself to observe terminal state and return a no-op before commit. I also recorded the strategy choice in decision D197 and appended the SQLite stale-snapshot gotcha to `.gsd/KNOWLEDGE.md` for downstream slices.

## Verification

I first ran the promoted race proof before the fix and confirmed the expected red state: stale `resume` / `pause` transitions still returned `changed=True` and reopened terminal rows. After implementing the optimistic status-guarded write path, I reran the targeted unit conflict tests, the promoted integration race proof, and finally the full task-plan lifecycle suite. All three passed. I also ran LSP diagnostics on `backend/src/common/db/session_lifecycle.py`, `backend/tests/unit/test_session_lifecycle_service.py`, and `backend/tests/integration/test_session_lifecycle_api.py`; all returned `No diagnostics`. The focused pytest commands still emit existing repo-level warnings from pytest-cov (`Module src was never imported` / `No data was collected`), the existing `passlib` crypt deprecation warning, and the pre-existing `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` in `test_lifecycle_api_end_is_idempotent_and_logs_unified_terminal_context`, but none were introduced by this task and the suite exits 0.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py -k 'stale_terminal_writer_converges_to_persisted_terminal_noop or fresh_terminal_resume_still_raises_invalid_transition' -q` | 0 | ✅ pass | 501ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_session_lifecycle_api.py -k 'lifecycle_race_proof_preserves_terminal_status_against_stale_writer' -q` | 0 | ✅ pass | 2565ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q` | 0 | ✅ pass | 3576ms |

## Deviations

None.

## Known Issues

Existing focused pytest warnings remain: pytest-cov reports `Module src was never imported` / `No data was collected` on these narrow commands, `passlib` emits a `crypt` deprecation warning, and `test_lifecycle_api_end_is_idempotent_and_logs_unified_terminal_context` still produces the pre-existing `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` while the suite passes. No new blocker was discovered.

## Files Created/Modified

- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
