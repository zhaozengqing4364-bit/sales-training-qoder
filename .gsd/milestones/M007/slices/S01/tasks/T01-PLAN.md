---
estimated_steps: 4
estimated_files: 7
skills_used:
  - test-driven-development
  - fastapi-python
  - react-best-practices
  - verification-before-completion
---

# T01: 锁定 coach-health reconnect 真相合同

**Slice:** S01 — 教练健康状态真相收口
**Milestone:** M007

## Description

Lock the highest-risk boundary first: backend snapshot/restore plus frontend websocket restore must agree on one coach-health truth source before any learner-page UI work. Preserve backend runtime snapshot semantics as the only authority for reconnect state, and keep `/api/v1/practice/sessions/{id}/knowledge-check` as an inspection surface rather than a second runtime driver.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | Keep reconnect truth explicit via focused restore tests before changing UI behavior | Do not add fallback polling; treat missing restore proof as a blocker for learner-page truth | Normalize invalid `coach_health.status` back to healthy-safe semantics instead of crashing |
| `backend/src/sales_bot/websocket/enhanced_handler.py` | Keep classic handler aligned with StepFun before claiming parity | Avoid introducing classic-only reconnect branches | Reject malformed restored `coach_health` payloads by normalizing reason/status safely |
| `web/src/hooks/websocket/message-handlers.ts` | Fail the focused reducer tests rather than hiding stale degraded state | Do not loop or refetch; reconnect restore must stay O(1) | Treat unknown payload shapes as `healthy` only when snapshot truly omits `coach_health` |
| `backend/src/common/api/practice.py` | Keep `/knowledge-check` usable as diagnostics even if websocket path regresses | No extra synchronous wait on runtime inspection | Preserve stable `coach_health` / `coach_health_status` / `coach_health_reason` / `coach_health_summary` keys |

## Load Profile

- **Shared resources**: websocket reconnect path and in-memory session snapshot state
- **Per-operation cost**: one snapshot read/restore plus reducer normalization; no new network round-trips
- **10x breakpoint**: reconnect storms would first regress by adding accidental fetch loops or per-reconnect heavy work; this task must keep restore O(1)

## Negative Tests

- **Malformed inputs**: invalid `coach_health.status`, missing `reason`, partial reconnect payloads, non-dict runtime state
- **Error paths**: stale degraded state before reconnect, omitted `coach_health` after recovery, classic and StepFun handlers restoring different shapes
- **Boundary conditions**: `healthy -> degraded -> resumed -> healthy` lifecycle, live `/knowledge-check` degraded payload parity, reconnect payload with no `coach_health` after prior degraded state

## Steps

1. Verify the current StepFun and classic snapshot/restore semantics against the real handler code and existing focused tests before changing behavior.
2. Adjust handler or reducer code only where reconnect can currently lie, keeping backend snapshot data as the single source of truth.
3. Extend backend and frontend focused tests to cover degraded, resumed, malformed, and omitted-after-recovery restore cases.
4. Re-run the focused reconnect and diagnostics suite from repo root using the repo-safe commands captured below.

## Must-Haves

- [ ] `reconnected` only clears stale degraded state when the snapshot truly omits `coach_health`
- [ ] StepFun and classic handlers restore the same `coach_health` contract before notifying the frontend
- [ ] `/knowledge-check` continues to expose live coach-health diagnostics matching the runtime contract
- [ ] No polling loop, second authority, or client-only reconnect derivation is introduced

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_persistence.py -k "restore_session_state"`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py -k "live_coach_health"`
- `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts'`

## Observability Impact

- Signals added/changed: reconnect truth remains inspectable through `reconnected.data.restored_state.runtime_state.coach_health` and `/api/v1/practice/sessions/{id}/knowledge-check`
- How a future agent inspects this: compare handler snapshot tests, reducer restore tests, and the live knowledge-check diagnostics payload
- Failure state exposed: stale-healthy or stale-degraded reconnect lies become localizable to handler snapshot creation, handler restore, API diagnostics, or reducer normalization

## Inputs

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun runtime snapshot/restore authority
- `backend/src/sales_bot/websocket/enhanced_handler.py` — classic runtime snapshot/restore authority
- `backend/src/common/websocket/base_handler.py` — reconnect event emission path
- `backend/src/common/api/practice.py` — live knowledge-check diagnostics surface
- `backend/src/common/conversation/runtime_diagnostics.py` — shared coach-health diagnostics normalizer
- `backend/tests/unit/test_stepfun_realtime_handler.py` — current StepFun coach-health behavior assertions
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — reconnect-safe restore contract tests
- `backend/tests/unit/test_enhanced_handler_coach_health.py` — classic snapshot/restore contract tests
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — live knowledge-check coach-health API assertions
- `web/src/hooks/websocket/message-handlers.ts` — frontend reconnect restore normalizer
- `web/src/hooks/websocket/message-handlers.test.ts` — websocket reducer restore assertions

## Expected Output

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — reconnect snapshot/restore contract stays truthful or is corrected
- `backend/src/sales_bot/websocket/enhanced_handler.py` — classic reconnect contract stays aligned with StepFun
- `web/src/hooks/websocket/message-handlers.ts` — reducer restore semantics match backend omission/non-omission rules
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — reconnect restore edge cases are explicitly covered
- `backend/tests/unit/test_enhanced_handler_coach_health.py` — classic handler restore parity is locked down
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — live knowledge-check degraded payload shape remains asserted
- `web/src/hooks/websocket/message-handlers.test.ts` — frontend degraded/resumed/omitted reconnect behavior is proven
