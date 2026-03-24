---
estimated_steps: 4
estimated_files: 4
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - systematic-debugging
  - verification-before-completion
---

# T02: Wire StepFun feedback pacing and reconnect-safe arbiter state

**Slice:** S02 — 提示节奏收口与单轮唯一动作卡
**Milestone:** M002

## Description

Bring the StepFun runtime onto the same pacing line as classic mode. `_run_realtime_feedback(...)` still sends fuzzy, score, and action outputs independently, and reconnect snapshots only preserve stage / score / action read-side data. This task should make StepFun reuse the shared arbiter, then persist only the minimum pacing metadata required to avoid replaying stale coaching immediately after restore.

## Steps

1. Extend `backend/tests/unit/test_stepfun_realtime_handler.py` with failing cases for same-turn single-action behavior, duplicate coaching suppression, and cross-channel priority when fuzzy detections and score guidance both exist.
2. Extend `backend/tests/unit/test_stepfun_realtime_persistence.py` with failing cases that prove reconnect restores the minimal pacing state needed to avoid replay bursts while preserving `_latest_score_snapshot` / `_latest_action_card` diagnostics.
3. Update `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` to route `_run_realtime_feedback(...)` through `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`, then serialize only the arbiter state required by the new tests into the existing reconnect snapshot flow.
4. Re-run the focused StepFun handler/persistence suites and keep the persisted state surface intentionally small so S05 can layer degraded-state observability later without inheriting a bloated cache.

## Must-Haves

- [ ] StepFun uses the same shared arbitration logic as classic mode for single-turn primary coaching.
- [ ] Reconnect-safe state persists only what is needed to prevent immediate replay bursts, not a full policy cache.
- [ ] `_latest_score_snapshot` and `_latest_action_card` remain valid read-side diagnostics after the refactor.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`

## Observability Impact

- Signals added/changed: StepFun handler assertions for single-turn coaching decisions, plus reconnect snapshot assertions for persisted pacing metadata.
- How a future agent inspects this: run the focused StepFun pytest command and inspect `_create_state_snapshot()` / `_restore_session_state()` expectations in `backend/tests/unit/test_stepfun_realtime_persistence.py`.
- Failure state exposed: replay bursts after restore or StepFun/classic priority drift fail as explicit handler/persistence assertions.

## Inputs

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — shared pacing contract produced by T01.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun realtime feedback and reconnect snapshot path.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — current StepFun handler coverage.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — current reconnect snapshot coverage.

## Expected Output

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun runtime routed through the shared arbiter with minimal reconnect-safe pacing state.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — focused StepFun arbitration regressions.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — reconnect-safe pacing persistence regressions.
