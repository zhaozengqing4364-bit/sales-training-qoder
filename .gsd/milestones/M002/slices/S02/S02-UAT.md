# S02: 提示节奏收口与单轮唯一动作卡 — UAT

**Milestone:** M002
**Written:** 2026-03-24T20:38:55+08:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02’s proof target is pacing and surface arbitration, not live model quality. The slice is complete when classic + StepFun share one duplicate-suppression contract, reconnect restore does not replay stale coaching, and the practice page clears old turn-bound hints while showing only one primary textual action.

## Preconditions

- Run from the repo root `/Users/zhaozengqing/github/销售训练qoder`.
- Backend dependencies are installed in `backend/venv`.
- Web dependencies are installed in `web/node_modules`.
- Run backend pytest suites sequentially, not in parallel, because this repo’s `pytest-cov` combine step can false-fail if multiple backend runs overlap.
- No local dev server is required for this UAT.

## Smoke Test

1. Run:
   ```bash
   cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/RightPanelContent.test.tsx'
   ```
2. **Expected:** both suites pass, proving that a new final transcript clears stale turn-bound hints and that the right panel now renders `action_card` as the only primary textual coaching surface.

## Test Cases

### 1. Classic + StepFun backend paths share one action-card pacing contract

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
   ```
2. Inspect the passing output for these focused behaviors:
   - classic mode keeps only one primary action card for the same turn
   - StepFun follows the same arbiter rules instead of emitting independent competing coaching
   - terminal evidence fallback still matches the current sales-rollup contract
3. **Expected:**
   - all tests pass
   - `test_duplicate_action_card_is_suppressed_for_same_turn_signature` and `test_run_realtime_feedback_suppresses_duplicate_action_card_for_same_turn` stay green
   - `test_sync_sales_realtime_terminal_evidence_uses_latest_message_score_snapshot` stays green on the updated sales-rollup baseline

### 2. Focused backend diagnostics still catch duplicate suppression and replay regressions

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv
   ```
2. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv
   ```
3. **Expected:**
   - arbiter diagnostics pass and prove same-turn duplicate action suppression without deleting fuzzy/stage/score context
   - StepFun replay diagnostics pass and prove restore does not replay the same-turn action card burst after reconnect

### 3. Existing fuzzy capability cooldown still works under the new shared arbiter

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown
   ```
2. **Expected:**
   - the cooldown regression passes unchanged
   - S02’s new arbiter does not replace or break the low-level `FuzzyDetectionCapability` throttle semantics

### 4. Practice-page consumers clear stale turn hints and keep one primary textual coach surface

1. Run:
   ```bash
   cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'
   ```
2. Inspect the Vitest summary line.
3. **Expected:**
   - all four suites pass
   - `Test Files (4)` is reported, confirming no requested file path was silently skipped
   - reducer tests prove a new final transcript clears `actionCard` and `fuzzyDetections`
   - `RightPanelContent` shows `action_card` as the primary coach text and no competing fuzzy/score advice beside it
   - `ScorePanel` still shows stage and score context, but does not duplicate the active action-card guidance as a second textual instruction

## Edge Cases

### Final transcript arrives before the next turn’s coaching

1. Re-run:
   ```bash
   cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts'
   ```
2. **Expected:** once a user final transcript is reduced, the previous turn’s `actionCard` and `fuzzyDetections` are cleared immediately instead of lingering into the next turn.

### StepFun reconnect restores diagnostics but must not replay the last action card

1. Re-run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_persistence.py -k 'replay or reconnected' -vv
   ```
2. **Expected:** restore keeps the minimal pacing state and read-side diagnostics, but does not emit a duplicate action card for the same turn after reconnect.

### Missing web test files can create a false-green gate if you do not inspect the file count

1. Re-run the web gate:
   ```bash
   cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'
   ```
2. **Expected:** the output explicitly reports `Test Files 4 passed (4)`. Any lower count means the command was green for fewer files than intended.

## Failure Signals

- Backend tests start emitting two action cards for the same turn, or stop preserving fuzzy/stage/score context while deduping the primary action.
- StepFun restore replays `_latest_action_card` as a fresh coach burst after reconnect.
- The fuzzy cooldown regression fails, meaning the new arbiter has interfered with capability-local pacing.
- Web reducer tests show `actionCard` or `fuzzyDetections` surviving into a later turn after a final transcript.
- `RightPanelContent` and `ScorePanel` both render separate text instructions for the same active turn.
- The web gate exits 0 but reports fewer than 4 executed test files.

## Requirements Proved By This UAT

- R009 — proves the prompt-pacing portion of the realtime-coaching requirement: coaching is now throttled to one primary action direction per turn, duplicate/replayed hints are suppressed, and stale turn-bound hints are cleared from the practice page.

## Not Proven By This UAT

- Whether stage progression, score deltas, and action cards converge into one next-turn coaching rule (S03).
- Whether the surviving realtime coaching direction matches report `main_issue` / `next_goal` for the same session (S04).
- Whether degraded / no-coach states are explicitly visible and diagnosable in the product UI/runtime (S05).
- Human-perceived quality in a live sales conversation; this slice intentionally stops at artifact-driven proof.

## Notes for Tester

- Treat the arbiter unit tests, StepFun replay persistence tests, and `message-handlers` / `RightPanelContent` suites as the authoritative diagnostics for this slice. They pin the exact behavior downstream M002 slices will build on.
- If a backend suite looks like it passed but then exits with a coverage combine error, rerun sequentially before assuming a product regression.
- On the web gate, always read the `Test Files` count. Vitest can stay green even if one requested file path did not actually execute.
