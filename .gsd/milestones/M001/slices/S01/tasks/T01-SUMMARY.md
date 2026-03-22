---
id: T01
parent: S01
milestone: M001
provides:
  - Shared backend terminal session path for lifecycle end and legacy DELETE
key_files:
  - backend/src/common/api/practice.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - backend/tests/contract/test_sessions.py
  - backend/tests/integration/test_session_flow.py
key_decisions:
  - D009: lifecycle end and legacy DELETE now delegate to one terminal helper and differ only in response payload shape
patterns_established:
  - Route-specific response over a shared `_run_lifecycle_action()` / `_prepare_terminal_lifecycle_result()` executor for terminal session writes
observability_surfaces:
  - `practice_session_lifecycle_transition_applied` / `practice_session_terminal_connection_close` structured logs with `session_id` `scenario_type` `action` `to_status`
  - targeted pytest coverage for sales/presentation terminal status, report trigger, live handler sync/close, and idempotent end
  - slice verification command outputs in backend/web test runs
duration: 1h20m
verification_result: passed
completed_at: 2026-03-23T01:46:00+08:00
blocker_discovered: false
---

# T01: 收口会话结束与生命周期单写入口

**Unified practice-session terminal writes so lifecycle `end` and legacy DELETE now share one backend authority path, with explicit regression coverage for sales/presentation terminal status, report trigger, live sync/close, and idempotent end.**

## What Happened

`backend/src/common/api/practice.py` 里新增了共享的终态执行 helper：`_prepare_terminal_lifecycle_result()` 负责 scenario-specific 终态副作用，`_run_lifecycle_action()` 负责 commit、report trigger、live handler sync、广播和 terminal close。`POST /practice/sessions/{id}/lifecycle` 的 `end` 与旧 `DELETE /practice/sessions/{id}` 现在都走这条路径；两者只在最后返回 lifecycle payload 还是 report payload 上分叉。

终态规则保持了原本差异：sales 仍落到 `scoring`，presentation 仍落到 `completed`。但 sales summary 生成、presentation score flush、report trigger、live handler sync/close、terminal close 不再各写一套。针对 observability，也把 lifecycle transition 和 terminal close 日志统一到带 `session_id`、`scenario_type`、`action`、`to_status` 的结构化字段上。

测试侧在三个指定文件里补了回归：
- `backend/tests/integration/test_session_lifecycle_api.py` 现在显式断言 lifecycle end 会触发 report trigger、同步/关闭 live handler，并在重复 end 时保持幂等且输出统一日志上下文。
- `backend/tests/contract/test_sessions.py` 现在覆盖 lifecycle end / legacy DELETE 在 sales=`scoring`、presentation=`completed` 下的稳定合约，并断言 sales DELETE 仍会触发 report trigger。
- `backend/tests/integration/test_session_flow.py` 现在覆盖 legacy DELETE 在 lifecycle end 之后的幂等行为，确保旧兼容入口不会重新跑第二套终态迁移。

## Verification

Passed:
- `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`
  - 18 selected tests passed
  - 覆盖了 sales=`scoring`、presentation=`completed`、report trigger、live handler sync/close、DELETE 兼容入口、重复结束幂等
- `cd web && npx vitest --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - 3 files / 27 tests passed

Slice-level command status:
- `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
  - failed immediately because `tests/unit/test_stepfun_realtime_persistence.py` does not exist yet; this is expected unfinished T02 surface, not a T01 regression
- `cd web && npm test -- --run src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - package-script invocation currently errors with duplicated `--run`; equivalent direct `npx vitest --run ...` passes as above

## Diagnostics

- Read `backend/src/common/api/practice.py` around `_prepare_terminal_lifecycle_result()` and `_run_lifecycle_action()` to inspect the unified terminal path.
- Check structured logs `practice_session_lifecycle_transition_applied` and `practice_session_terminal_connection_close` for `session_id` / `scenario_type` / `action` / `to_status`.
- Use these tests for fast regression inspection:
  - `backend/tests/integration/test_session_lifecycle_api.py::test_lifecycle_api_end_triggers_report_on_first_terminal_transition`
  - `backend/tests/integration/test_session_lifecycle_api.py::test_lifecycle_api_end_is_idempotent_and_logs_unified_terminal_context`
  - `backend/tests/contract/test_sessions.py::TestSessionsContract::test_end_session_contract_sales_returns_report_and_scoring_status`
  - `backend/tests/integration/test_session_flow.py::TestSessionLifecycleTransitions::test_delete_compat_entry_is_idempotent_after_lifecycle_end_sales`

## Deviations

- None.

## Known Issues

- The second backend slice verification command still fails because T02 test files are not present yet.
- The slice-plan web verification command is currently malformed when routed through `npm test -- --run ...` because the package script already supplies `--run`; use direct `npx vitest --run ...` for accurate status until that script shape is revisited.

## Files Created/Modified

- `backend/src/common/api/practice.py` — added the shared lifecycle executor and unified terminal observability/logging for lifecycle end + legacy DELETE.
- `backend/tests/integration/test_session_lifecycle_api.py` — added report-trigger, idempotent-end, log-context, and live-handler regression coverage.
- `backend/tests/contract/test_sessions.py` — added legacy DELETE terminal contract coverage for sales/presentation and idempotent lifecycle end coverage.
- `backend/tests/integration/test_session_flow.py` — added flow-level DELETE-after-lifecycle-end idempotency coverage and aligned sales end flow to the unified summary/cleanup path.
- `.gsd/DECISIONS.md` — recorded D009 for the single terminal-write-entry pattern.
- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — marked T01 done.
- `.gsd/STATE.md` — advanced the next action to T02 and recorded the remaining slice-level verification gap.
