---
id: T03
parent: S03
milestone: M002
provides:
  - StepFun sales runtime now keeps rich stage/score arbitration context while preserving the stable public score snapshot contract
key_files:
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
key_decisions:
  - D039 carry-forward — keep StepFun `score_update` / `_latest_score_snapshot` stable while passing separate rich raw stage/score context into the shared coaching-focus arbiter
patterns_established:
  - `_latest_stage_data` is the StepFun seam between stage analysis and later action-card arbitration
  - `_run_realtime_feedback()` can enrich arbiter-only score context from raw realtime scoring payloads without changing the emitted snapshot shape
observability_surfaces:
  - backend/tests/unit/test_stepfun_realtime_handler.py
duration: 57m
verification_result: passed
completed_at: 2026-03-24T22:09:36+0800
blocker_discovered: false
---

# T03: Normalize StepFun stage and score context to classic parity

**StepFun now retains rich stage/score context so its sales `action_card` matches classic coaching direction without changing `score_update` or persisted snapshot shapes.**

## What Happened

I treated T03 as a strict TDD handoff fix. First I updated the StepFun handler expectations that were still asserting the old suggestion-only `action_card` text, then I added three focused regressions in `backend/tests/unit/test_stepfun_realtime_handler.py`:

- stage analysis must retain the latest rich `stage_data`
- realtime feedback must pass rich stage context plus raw scoring `dimensions[*].delta/trend` into the arbiter while keeping the public `score_update` snapshot stable
- the StepFun path must pick the same declining-dimension objection action card as classic for equivalent stage + score input

Those red tests exposed the exact seam the plan predicted: `_analyze_and_emit_sales_stage(...)` only returned a stage id, and `_run_realtime_feedback(...)` rebuilt a narrow `stage_context` / `score_context` for arbitration from `sales_stage` plus the stable score snapshot, which dropped `guidance`, `key_actions`, `progress`, and raw `dimensions[*].delta/trend`.

I fixed only that seam in `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` by introducing `_latest_stage_data`, capturing a deep copy of rich stage analysis output, and feeding that forward into the arbiter when the current turn still matches the analyzed stage. On the scoring side, I kept `_latest_score_snapshot` and emitted `score_update` exactly on the existing stable shape, but passed a separate raw `score_context_for_arbiter` copy that preserves the original realtime scoring payload plus normalized `overall_score`, `dimension_scores`, `suggestions`, and `stage_name`.

## Verification

I ran the new red-step selectors first, confirmed the missing rich handoff and declining-dimension drift, then applied the minimal handler patch and reran the focused StepFun suite until it passed. After that I ran the full task-level StepFun verification and the full slice-level verification matrix; all required commands passed fresh.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py` | 0 | ✅ pass | 5.98s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv` | 0 | ✅ pass | 6.21s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv` | 0 | ✅ pass | 5.84s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv` | 0 | ✅ pass | 5.88s |
| 5 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py` | 0 | ✅ pass | 6.55s |
| 6 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv` | 0 | ✅ pass | 2.95s |

## Diagnostics

Use `backend/tests/unit/test_stepfun_realtime_handler.py` as the canonical T03 inspection surface.

The two highest-signal assertions are:

- `test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable`
- `test_run_realtime_feedback_uses_declining_dimension_to_match_classic_action_card`

If StepFun drifts from classic again, inspect `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` in exactly two places first:

1. `_analyze_and_emit_sales_stage(...)` — this must keep `_latest_stage_data` rich enough for arbitration
2. `_run_realtime_feedback(...)` — this must preserve the split between stable public `score_snapshot` and richer arbiter-only `score_context_for_arbiter`

The runtime-facing continuity surfaces remain `_latest_score_snapshot` and `_latest_action_card`; T03 intentionally did not change their public shape.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — retained rich `stage_data` for later arbitration and passed raw scoring context with `dimensions[*].delta/trend` into the arbiter while keeping the public score snapshot stable.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — updated StepFun parity expectations to the shared coaching-focus text and added focused regressions for rich stage retention, raw score-context handoff, and declining-dimension parity.
- `.gsd/KNOWLEDGE.md` — recorded the non-obvious StepFun split between stable public score snapshots and richer arbiter-only context.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — marked T03 done.
