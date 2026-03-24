---
id: T02
parent: S03
milestone: M002
provides:
  - classic sales realtime action_card output now follows the shared stage-aware coaching-focus rule
key_files:
  - backend/src/sales_bot/websocket/realtime_feedback_arbiter.py
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_capability_processor.py
  - .gsd/milestones/M002/slices/S03/S03-PLAN.md
key_decisions:
  - D039 carry-forward — finish classic wiring by passing the already-available stage/score context through RealtimeFeedbackArbiter into build_action_card without changing websocket payload shapes
patterns_established:
  - classic mode already forwards raw stage_data and score_payload into the arbiter; the final rich-context seam is the arbiter's build_action_card handoff
observability_surfaces:
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_capability_processor.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
duration: 36m
verification_result: passed
completed_at: 2026-03-24T21:51:30+0800
blocker_discovered: false
---

# T02: Route classic arbitration through the shared coaching-focus rule

**Classic sales arbiter now emits shared stage-aware coaching-focus action cards.**

## What Happened

I treated the arbiter/classic regressions as the TDD red step first: I extended `backend/tests/unit/test_realtime_feedback_arbiter.py` to pin three new behaviors — rich-context score guidance beats low-severity fuzzy noise, stage changes can switch the chosen action-card text, and a declining dimension can overtake the previously weakest dimension. I also extended `backend/tests/unit/test_capability_processor.py` so the classic runtime proves those richer action cards come through the existing websocket contract while `fuzzy_detection`, `stage_update`, and `score_update` remain contextual side channels.

The failing runs showed one clear root cause: `CapabilityProcessor` was already passing raw `stage_data` and raw realtime-scoring payloads into `RealtimeFeedbackArbiter`, but `RealtimeFeedbackArbiter.decide()` still called `build_action_card(...)` with only suggestions/fuzzy detections plus pass flags. I fixed only that seam in `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` by threading `stage_context` and `score_context` into both primary-source branches.

That minimal change flipped classic mode onto the shared `common.effectiveness` coaching-focus rule without altering websocket payload shapes. As a pre-flight housekeeping fix, I also updated `S03-PLAN.md` to add the missing diagnostic verification selector that proves context is preserved even when no primary action card is emitted.

## Verification

The two task-level classic verification commands both passed fresh after the arbiter handoff change landed. The carried-forward slice selectors for shared coaching focus and arbiter context preservation also passed.

The broad slice suite and the focused StepFun verbose suite are now intentionally the only red surfaces: both fail on T03-owned StepFun action-card expectation drift because classic arbitration now emits shared rich-context coaching-focus text. The failing StepFun tests are:

- `test_run_realtime_feedback_keeps_single_action_card_and_prioritizes_score_over_low_severity_fuzzy_detection`
- `test_run_realtime_feedback_suppresses_duplicate_action_card_for_same_turn`
- `test_run_realtime_feedback_emits_canonical_sales_score_and_action_card`

That is an expected intermediate-task carry-forward, not a T02 blocker, because T03 explicitly owns StepFun parity and assertion updates.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py` | 0 | ✅ pass | 5.74s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py -vv` | 0 | ✅ pass | 5.64s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py` | 1 | ❌ fail | 5.89s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv` | 0 | ✅ pass | 6.26s |
| 5 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv` | 0 | ✅ pass | 5.37s |
| 6 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv` | 0 | ✅ pass | 6.14s |
| 7 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv` | 1 | ❌ fail | 6.35s |

## Diagnostics

Use `backend/tests/unit/test_realtime_feedback_arbiter.py` to inspect the direct arbitration contract for stage-aware and declining-dimension selection. Use `backend/tests/unit/test_capability_processor.py` to inspect the classic websocket payload behavior and confirm that `fuzzy_detection` / `stage_update` / `score_update` remain contextual messages while `action_card` is the only primary coach surface.

If classic mode ever falls back to suggestion-only action cards again, inspect `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` first: the decisive seam is whether `decide()` forwards `stage_context` and `score_context` into `build_action_card(...)`.

## Deviations

I made one plan-aligned pre-flight correction before implementation: `S03-PLAN.md` now includes an explicit diagnostic verification selector for `preserve_context_without_primary_action`, because the slice plan had been flagged for lacking a failure/diagnostic check.

I did not change `backend/src/sales_bot/websocket/components/capability_processor.py` itself after verifying the local reality: it was already forwarding raw `stage_data` and raw `score_payload` into the arbiter, so the real missing seam was only inside `RealtimeFeedbackArbiter`.

## Known Issues

- The slice-level StepFun suites are now red until T03 updates StepFun parity/assertions to the shared coaching-focus action-card text.
- The verification harness helper shell initially failed because this environment exposes `python3`, not `python`; I reran the same verification matrix immediately with `python3` and no product files changed between those attempts.

## Files Created/Modified

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — passed rich `stage_context` and `score_context` through the final `build_action_card(...)` seam for both fuzzy-primary and score-primary arbitration.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — added stage-aware and declining-dimension arbitration regressions and updated score-primary expectations to the shared coaching-focus text.
- `backend/tests/unit/test_capability_processor.py` — added classic-path regressions proving richer action-card output while preserving contextual `fuzzy_detection` / `stage_update` / `score_update` messages and same-turn duplicate suppression.
- `.gsd/KNOWLEDGE.md` — recorded the non-obvious classic-vs-arbiter seam and the expected T03 StepFun carry-forward effect.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — added the missing diagnostic verification selector and marked T02 done.
