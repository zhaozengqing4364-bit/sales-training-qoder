---
id: S01
parent: M017
milestone: M017
provides:
  - A durable backend concurrency contract for pause/resume/end races that downstream websocket and upload/resource-contention work can reuse.
  - A reusable stale-writer reproduction harness for async SQLite-backed lifecycle races.
  - An explicit, tested terminal split: sales ends into `scoring`; presentation ends into `completed`.
requires:
  []
affects:
  - M017/S02 websocket reconnect/interrupt contract work
  - M017/S03 upload/resource-contention discovery
  - SessionLifecycleService terminal-state authority seam
  - Canonical report/replay/background-finalization behavior that depends on sales=`scoring` vs presentation=`completed`
key_files:
  - backend/src/common/db/session_lifecycle.py
  - backend/tests/unit/test_session_lifecycle_service.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D197 — Use optimistic compare-and-swap on `PracticeSession.status` and converge stale non-terminal writers to the already-persisted terminal state instead of introducing row locks.
  - D198 — Keep the lifecycle concurrency contract in the focused unit/integration lifecycle tests and use the existing repo-root pytest command as the long-term regression entrypoint; isolate presentation terminal-split proof from unrelated coach-service duration math when the proof target is lifecycle terminal semantics.
  - Only stale writers that lose to an already-persisted terminal state converge to a no-op; fresh pause/resume requests against terminal sessions remain invalid transitions.
patterns_established:
  - Reproduce backend stale-writer races with two independent `AsyncSession` instances bound to the same test engine before choosing a convergence strategy.
  - Use a write-time status compare-and-swap at the lifecycle authority seam rather than same-session rereads when SQLite-backed async tests can hold stale snapshots.
  - Keep concurrency contracts as executable constants/assertions adjacent to the focused proof files so downstream slices inherit one durable regression entrypoint instead of a doc-only contract.
observability_surfaces:
  - `backend/src/common/db/session_lifecycle.py` structured warning path `practice_session_lifecycle_concurrency_conflict` for stale-writer conflict visibility.
  - `backend/tests/unit/test_session_lifecycle_service.py` `LIFECYCLE_CONCURRENCY_CONTRACT` plus conflict-path assertions for stale-writer no-op vs fresh invalid transition semantics.
  - `backend/tests/integration/test_session_lifecycle_api.py` `LIFECYCLE_API_CONCURRENCY_CONTRACT`, stale-writer race proof, and presentation terminal-split proof as the long-term lifecycle regression gate.
drill_down_paths:
  - .gsd/milestones/M017/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M017/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M017/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T21:19:54.404Z
blocker_discovered: false
---

# S01: Session lifecycle 并发安全 proof

**Proved and closed the highest-risk SessionLifecycleService stale-writer races so pause/resume can no longer reopen terminal sessions, while preserving the intentional sales=`scoring` vs presentation=`completed` terminal split.**

## What Happened

## What this slice delivered

S01 turned session lifecycle concurrency from an inferred behavior into a mechanically provable backend contract.

1. **Race catalog plus executable failing proof.** The slice first identified the two terminal regressions worth proving: stale `resume` reopening a sales session after `end` already persisted `scoring`, and stale `pause` reopening a presentation session after `end` already persisted `completed`. Those scenarios are now explicit in the lifecycle race catalog and were first preserved as verified red proofs before the fix landed.
2. **Optimistic lifecycle convergence at the authority seam.** `SessionLifecycleService` now resolves lifecycle writes with a status compare-and-swap on `PracticeSession.status` instead of relying on caller-local guards or same-session rereads. When a stale writer loses to a terminal commit, the service reloads the durable state, logs `practice_session_lifecycle_concurrency_conflict`, syncs the in-memory row back to the persisted terminal state, and converges that stale writer to `changed=False` instead of reopening the session.
3. **Intentional terminal split stayed intact.** The slice did not flatten lifecycle semantics. Sales still ends into `scoring` so report-generation/finalization can continue on the existing path; presentation still ends directly into `completed`. Fresh pause/resume calls against already-terminal sessions remain invalid transitions. Only stale non-terminal writers that lost the race to an already-persisted terminal state are collapsed into a no-op.
4. **The contract is now adjacent to the proof.** The focused lifecycle unit and integration suites now carry explicit concurrency-contract constants and assertions that document why the project chose optimistic compare-and-swap over row locks, which races are intentionally converged, and which regression command future slices should rerun before changing lifecycle behavior.

## Why this matters downstream

- **For S02 (practice websocket):** reconnect/interrupt logic now has one stable terminal-state seam to honor. If websocket work reopens a session after `end`, that is now clearly a websocket-layer bug rather than ambiguous lifecycle behavior.
- **For S03 (upload/resource contention discovery):** this slice established the pattern of proving the race first, then choosing the smallest durable convergence seam. Future resource-competition work should reuse that proof-first approach instead of preemptively adding retries, locks, or debounce wrappers.
- **For future lifecycle work:** the authoritative regression entrypoint is the focused lifecycle pytest bundle, not a doc-only contract or a new umbrella suite.

## Operational Readiness (Q8)

- **Health signal:** the focused lifecycle gate passes (`27 passed`) and the concurrency-contract tests still assert the intentional sales/presentation terminal split.
- **Failure signal:** a reopened terminal session, a regression in `changed=False` stale-writer behavior, or a missing `practice_session_lifecycle_concurrency_conflict` path indicates the lifecycle seam has drifted.
- **Recovery procedure:** start from `backend/tests/unit/test_session_lifecycle_service.py` and `backend/tests/integration/test_session_lifecycle_api.py`, rerun the exact slice gate, inspect the compare-and-swap path in `backend/src/common/db/session_lifecycle.py`, and restore convergence at the service layer instead of papering over the issue in REST/WebSocket callers.
- **Monitoring gaps:** the focused proof covers the lifecycle authority seam but not full production telemetry volume or every upstream caller pattern; the pre-existing presentation-coach timezone mismatch and the pre-existing `Connection._cancel` runtime warning remain outside this slice’s scope.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

No new requirement IDs were surfaced. S01 retired a proof gap inside M017 by clarifying lifecycle terminal semantics and their concurrency boundary.

## Requirements Invalidated or Re-scoped

None.

## Verification

- Ran the exact slice-plan gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q` → **27 passed**.
- Ran fresh LSP diagnostics on `backend/src/common/db/session_lifecycle.py`, `backend/tests/unit/test_session_lifecycle_service.py`, and `backend/tests/integration/test_session_lifecycle_api.py` → **No diagnostics**.
- Verified task completion state from GSD milestone status: S01 shows **3/3 tasks done** before slice close-out.
- Non-blocking warnings still present on the focused pytest run: `pytest-cov` no-data/no-report warnings, `passlib` `crypt` deprecation warning, and the pre-existing `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` in the idempotent lifecycle API test path. The slice gate still exited `0` and all targeted assertions passed.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The slice-level proof for the presentation terminal split intentionally isolated lifecycle semantics from a pre-existing `PresentationCoachService.end_session()` timezone-mismatch bug by stubbing that collaborator in the focused API proof. This kept the slice on lifecycle concurrency rather than expanding into unrelated duration math work.

## Known Limitations

A known presentation-coach aware/naive timestamp mismatch still exists outside the lifecycle seam, and the focused pytest run still emits pre-existing warning noise (`pytest-cov` no-data/no-report, `passlib` `crypt` deprecation, and `Connection._cancel` runtime warning). S01 proves the lifecycle contract but does not broaden into full production telemetry or caller-by-caller runtime audit.

## Follow-ups

S02 should reuse this slice’s terminal-state contract when auditing websocket reconnect/interrupt behavior, especially around already-ended sessions. S03 should reuse the same proof-first pattern for upload/resource-contention discovery instead of jumping straight to retries or locking. If future work ever proposes row locks here, it should first produce evidence that the current compare-and-swap seam no longer captures the real failure mode.

## Files Created/Modified

- `backend/src/common/db/session_lifecycle.py` — Added the lifecycle race catalog, terminal-status helper usage, status compare-and-swap conflict handling, stale-writer convergence, and structured conflict logging.
- `backend/tests/unit/test_session_lifecycle_service.py` — Added executable lifecycle concurrency contract assertions plus focused unit proof for stale-terminal-writer no-op vs fresh invalid terminal transitions.
- `backend/tests/integration/test_session_lifecycle_api.py` — Added stale-writer lifecycle race proof, API-side lifecycle contract assertions, and presentation terminal-split proof.
- `.gsd/DECISIONS.md` — Recorded lifecycle concurrency strategy and authoritative proof-seam decisions as D197 and D198.
- `.gsd/KNOWLEDGE.md` — Captured the stale-writer reproduction harness, the need for compare-and-swap instead of same-session rereads, and the presentation coach timezone gotcha.
- `.gsd/PROJECT.md` — Refreshed project state to reflect M017/S01 close-out and the new lifecycle concurrency authority seam.
