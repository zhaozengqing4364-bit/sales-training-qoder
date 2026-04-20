# S03: 多轮异议 ledger 与持续施压 — UAT

**Milestone:** M003
**Written:** 2026-03-25T06:06:42.545Z

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: this slice changes runtime persistence, reconnect restore, projection alignment, and the learner panel’s coaching-priority rules on existing surfaces. The focused backend and web tests exercise those seams directly without introducing any parallel runtime or placeholder surface.

## Preconditions

- Use the current repository checkout with M003/S03 changes applied.
- Backend virtualenv dependencies and web dependencies are installed.
- Run backend pytest commands sequentially; do not parallelize them because this repo’s coverage combine step can collide.
- If a later human spot-check extends this into a live localhost run, keep frontend and backend on the same loopback host so cookies do not create fake auth failures.

## Smoke Test

Run the three slice verification commands exactly as written in the plan. Expected outcome: backend verifies `62 passed` for T01 and `68 passed` for T02, and web verifies `2 passed` test files / `13 passed` tests for T03.

## Test Cases

### 1. Persist one unresolved objection ledger on the existing evidence chain

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py`.
2. Confirm `test_context_manager_updates_objection_ledger_and_exposes_it_in_summary` and the two `TestMessageStorageObjectionLedger` tests pass.
3. **Expected:** the runtime summary carries `objection_ledger`, and persisted message `transcript_metadata` includes `objection_ledger.objection_family`, `promised_proof`, `next_expected_evidence`, and `closure_state`.

### 2. Keep pressuring the same open objection after topic drift

1. In the same backend run, inspect `test_run_realtime_feedback_reuses_open_objection_ledger_when_score_focus_drifts`.
2. Use its fixture shape as the contract: an open ROI ledger exists, but the new turn text drifts toward generic closing talk.
3. **Expected:** the resulting `analysis["objection_ledger"]` stays open, and the emitted `action_card` still asks for ROI / case evidence instead of switching to a generic closing-only hint.

### 3. Restore the ledger on reconnect without replaying stale action cards

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`.
2. Confirm the restore/snapshot tests pass: `test_create_state_snapshot_includes_objection_ledger_copy`, `test_restore_session_state_rehydrates_objection_ledger`, and `test_restore_session_state_suppresses_replayed_action_card_for_same_turn`.
3. **Expected:** StepFun reconnect snapshots persist the normalized `objection_ledger`, restore it on reconnect, preserve the latest score snapshot, and do **not** replay the last action card for the same turn.

### 4. Closing the gap should release objection focus

1. In the same backend run, inspect `test_run_realtime_feedback_marks_objection_ledger_gap_acknowledged_and_releases_focus`.
2. Use the test turn text where the seller explicitly admits the missing ROI evidence.
3. **Expected:** `objection_ledger.closure_state` becomes `gap_acknowledged`, and the primary `action_card` returns to the generic next-step/closing seam instead of staying stuck on ROI pressure.

### 5. Report/replay should explain the same unresolved blocker

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k latest_open_objection_ledger`.
2. Confirm the projection-preference test passes.
3. **Expected:** when the latest persisted ledger is still open, `SessionEvidenceService` projects ledger-derived sales `main_issue` / `next_goal` text, so completed-session read-side surfaces continue to explain the unresolved proof or objection family instead of falling back to a stale generic snapshot.

### 6. Learner panel should clear stale hints but keep the proof prompt visible

1. Run `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'`.
2. Confirm Vitest reports exactly `2` passing test files.
3. Check the reconnect/final-transcript tests plus the right-panel component tests.
4. **Expected:** reconnect or a new final user transcript clears stale `actionCard` / `fuzzyDetections`, but `scores.suggestions` survives; when an action card is active, the right panel shows it as the only primary coaching text and renders the surviving suggestion as “当前仍卡住的证明”.

## Edge Cases

### Closed ledger should stop overriding read-side conclusions

1. Use the gap-acknowledged backend case from test case 4.
2. Re-run read-side projection checks against a ledger whose latest persisted `closure_state` is not `open`.
3. **Expected:** report/replay projection falls back to normal sales alignment instead of continuing to force the old objection into `main_issue` / `next_goal`.

### Reconnect should preserve the open gap but not duplicate same-turn coaching

1. Use the StepFun restore tests from test case 3.
2. Restore a snapshot that contains both an open `objection_ledger` and prior `feedback_pacing_state`.
3. **Expected:** the open ledger is restored, the unresolved gap still influences later feedback, and no duplicate `action_card` is emitted for the already-finished turn.

## Failure Signals

- `ConversationMessage.transcript_metadata` no longer contains `objection_ledger` after persistence.
- An open objection ledger is present, but runtime feedback switches to unrelated generic closing/next-step advice after topic drift.
- Reconnect replay emits the previous turn’s `action_card` again.
- Report/replay `main_issue` / `next_goal` ignore an open objection ledger and revert to a generic stale snapshot.
- The learner panel loses the lingering proof prompt after reconnect or still shows stale fuzzy/action hints from the previous turn.

## Requirements Proved By This UAT

- R010 — proves that current-session Persona/knowledge pressure can now stay anchored to one unresolved objection family across runtime turns, reconnect, and report/replay read-side explanations on the current product routes.

## Not Proven By This UAT

- Whether a later seller response is unsupported, merely promised, or actually evidence-backed on the canonical report/replay contract. That is S04’s truth-contract work.
- A full live objection-heavy admin Persona/knowledge -> practice runtime -> report/replay localhost run. That remains S05’s proof burden.

## Notes for Tester

Treat the ledger as a minimal one-gap memory, not a multi-objection backlog. The intended invariant is: one open business gap keeps owning the coaching seam until it is explicitly closed, and once it is closed the system should release that focus instead of dragging the old objection forever.
