---
estimated_steps: 4
estimated_files: 2
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - systematic-debugging
  - verification-before-completion
---

# T03: Normalize StepFun stage and score context to classic parity

**Slice:** S03 — 阶段推进教练与下一轮规则闭环
**Milestone:** M002

## Description

Close the last runtime drift seam. StepFun still strips stage guidance and score `trend` / `delta` information before arbitration, so it cannot benefit fully from the shared coaching-focus rule even if classic mode is fixed. This task should preserve rich stage context from the StepFun stage-analysis path, pass raw realtime-scoring output into the arbiter, and prove the handler now emits the same coaching direction as classic for equivalent stage and score inputs — without changing the emitted `score_update` or persisted snapshot shapes.

## Steps

1. Extend `backend/tests/unit/test_stepfun_realtime_handler.py` with failing cases that compare equivalent classic/StepFun stage + score inputs and assert the same `action_card.issue`, `replacement`, and `next_turn_rule` are emitted on the StepFun path.
2. Update `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` so `_analyze_sales_stage_and_emit(...)` retains the latest rich `stage_data` for later arbitration, and `_run_realtime_feedback(...)` passes raw scoring dimensions plus `trend` / `delta` context into the arbiter instead of stripping everything down to `stage_name` and a narrow snapshot.
3. Keep emitted `score_update` and persisted `_latest_score_snapshot` / `ai_feedback` payload shapes stable for the existing consumer and replay surfaces; do not add frontend fields or persistence schema in this task.
4. Re-run the focused StepFun handler suite and confirm the runtime now stays on the same coaching direction as classic for matched inputs.

## Must-Haves

- [ ] StepFun retains enough stage context for arbitration to see `guidance`, `key_actions`, and progression semantics instead of only the stage id.
- [ ] StepFun passes raw scoring context with per-dimension change signals to the arbiter while keeping the public `score_update` snapshot stable.
- [ ] Focused handler tests prove classic/StepFun coaching parity for equivalent stage + score inputs.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv`

## Observability Impact

- Signals added/changed: richer in-handler stage/score context used for arbitration, plus focused StepFun assertions that pin parity against the classic coaching direction.
- How a future agent inspects this: run the StepFun handler suite and inspect `_latest_action_card`, `_latest_score_snapshot`, and the new stage-context expectations in `backend/tests/unit/test_stepfun_realtime_handler.py`.
- Failure state exposed: if StepFun still strips context or diverges from classic mode, the handler suite fails with explicit expected `action_card` values rather than later browser-only symptoms.

## Inputs

- `backend/src/common/effectiveness/evaluator.py` — shared coaching-focus helper and updated action-card builder from T01.
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — shared arbiter contract from T02.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun stage-analysis and realtime-feedback orchestration.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — current StepFun runtime coverage.

## Expected Output

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun runtime preserving rich stage/score context for the shared arbiter while keeping emitted snapshot shapes stable.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — focused StepFun regressions proving stage-aware, dimension-aware coaching parity with classic mode.
