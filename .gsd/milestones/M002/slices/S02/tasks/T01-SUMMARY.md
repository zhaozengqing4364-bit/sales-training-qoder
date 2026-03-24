---
id: T01
parent: S02
milestone: M002
provides:
  - Shared backend arbitration for classic sales realtime coaching with one primary action card per turn, same-turn duplicate suppression, and preserved fuzzy/stage/score context signals.
key_files:
  - backend/src/sales_bot/websocket/realtime_feedback_arbiter.py
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_capability_processor.py
  - .gsd/milestones/M002/slices/S02/S02-PLAN.md
key_decisions:
  - D036 — use a shared realtime-feedback arbiter that prefers scoring guidance over low-severity fuzzy detections for the primary action card while deduping by action signature within the same turn.
patterns_established:
  - Realtime coaching paths should preserve low-level fuzzy/stage/score payloads as context and centralize primary action-card selection behind a tiny turn+signature pacing state.
observability_surfaces:
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_capability_processor.py
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv`
duration: 10m
verification_result: passed
completed_at: 2026-03-24T19:58:10+0800
blocker_discovered: false
---

# T01: Add a shared backend arbiter for single-turn coaching

**Added a shared realtime feedback arbiter for classic sales coaching, with score-over-filler priority and same-turn action-card dedupe.**

## What Happened

I first fixed the slice-plan pre-flight gap by adding an explicit arbiter failure-path verification command to `.gsd/milestones/M002/slices/S02/S02-PLAN.md`.

Then I followed the TDD path for the actual seam. I added a new `backend/tests/unit/test_realtime_feedback_arbiter.py` contract file plus new classic-path regressions in `backend/tests/unit/test_capability_processor.py`, ran them red, and confirmed the missing-module failure before implementing anything.

The implementation adds `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` with a minimal reconnect-safe pacing state (`last_action_signature` + `last_action_turn`) and a single decision point for primary coaching selection. The arbiter keeps fuzzy detections, stage context, and score context intact, prefers score guidance when the competing fuzzy signal is only low-severity filler, and suppresses duplicate action cards only when the same signature repeats within the same turn.

Finally, I refactored `CapabilityProcessor` to use that seam without changing S01 field names or `build_action_card(...)` payload shape. Classic mode still emits fuzzy/stage/score messages, `FuzzyDetectionCapability` cooldown behavior remains untouched, and only the primary action-card emission is deduped.

## Verification

Task-level verification passed fresh:
- new arbiter + classic processor suite
- existing fuzzy cooldown regression
- new arbiter diagnostic filter for duplicate suppression / context preservation

Slice-level verification was partially rerun as required for an intermediate task. The web slice command is already green with current files. The broader backend slice command is still red on an existing StepFun persistence expectation outside T01’s classic-path seam.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py` | 0 | ✅ pass | 5.75s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv` | 0 | ✅ pass | 5.49s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown` | 0 | ✅ pass | 5.53s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py` | 1 | ❌ fail | 6.28s |
| 5 | `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'` | 0 | ✅ pass | 1.31s |

## Diagnostics

Future agents can inspect the new seam in three places:
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` for the score-vs-fuzzy priority and same-turn signature dedupe rules.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` for the contract around priority, suppression, and preserved context.
- `backend/tests/unit/test_capability_processor.py` for the classic runtime behavior that now routes action-card emission through the arbiter while keeping fuzzy/stage/score events live.

## Deviations

Added an arbiter-specific diagnostic verification command to `S02-PLAN.md` before implementation because the pre-flight check flagged the slice verification section as missing an inspectable failure-path command.

## Known Issues

The slice-level backend command still fails on `backend/tests/unit/test_stepfun_realtime_persistence.py::test_sync_sales_realtime_terminal_evidence_uses_latest_message_score_snapshot`. That failure is outside T01’s classic-path seam: the fixture feeds legacy `专业度/沟通技巧/销售流程` dimension keys, while `backend/src/common/api/practice.py` currently normalizes terminal evidence through sales rollups and falls back to `overall_score`, producing `88/88/88` instead of the test’s expected `91/86/87`.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S02/S02-PLAN.md` — added an explicit arbiter failure-path verification command per the pre-flight requirement.
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — new shared backend pacing and priority seam for realtime coaching.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic runtime now delegates primary action-card selection and same-turn dedupe to the arbiter.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — new contract coverage for priority selection, duplicate suppression, and preserved context.
- `backend/tests/unit/test_capability_processor.py` — added classic-path regressions for score-over-filler priority and same-turn duplicate action-card suppression.
- `.gsd/DECISIONS.md` — recorded D036 for the shared realtime-feedback arbitration policy.
