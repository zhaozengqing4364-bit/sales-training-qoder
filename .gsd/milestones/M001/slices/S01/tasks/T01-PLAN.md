---
estimated_steps: 4
estimated_files: 5
---

# T01: 收口会话结束与生命周期单写入口

**Slice:** S01 — 多轮会话稳定化与运行时状态收口
**Milestone:** M001

## Description

把 practice session 的终态控制收拢到一套后端实现，先消掉 `POST /practice/sessions/{id}/lifecycle` 与旧 `DELETE /practice/sessions/{id}` 的分叉副作用。这个任务完成后，sales / presentation 的结束行为、report trigger、live handler 同步和 terminal close 都应由同一条权威路径驱动，后续重连和前端失败显式化才有稳定基线。

## Steps

1. 抽出 `backend/src/common/api/practice.py` 中共享的终态收口 helper，明确 `start/pause/resume/end` 与 scenario-specific 终态、副作用、响应字段的边界。
2. 让 lifecycle `end` 与旧 DELETE 兼容入口委托同一结束实现，保留 sales summary / runtime cleanup / report trigger 能力，但不能再复制第二套状态迁移语义。
3. 在 `backend/tests/integration/test_session_lifecycle_api.py`、`backend/tests/contract/test_sessions.py`、`backend/tests/integration/test_session_flow.py` 补齐 regression 覆盖，断言 sales=`scoring`、presentation=`completed`、live handler sync/close 与 idempotent terminal end 一致。
4. 运行针对性 pytest，修正终态副作用与响应差异，直到两条入口的可观察行为收敛为一套合约。

## Must-Haves

- [ ] `control_session_lifecycle()` 与旧 `end_session()` 共享同一结束副作用实现，不再出现一条路清理 runtime / 生成 summary，另一条路只改状态的分叉。
- [ ] sales / presentation 终态规则继续保留场景差异，但无论走哪个入口都能同步 live handler、广播终态事件并关闭 terminal connection。

## Verification

- `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`
- 检查断言覆盖 sales=`scoring`、presentation=`completed`、重复结束幂等，以及 live handler close / report trigger 的统一行为。

## Observability Impact

- Signals added/changed: lifecycle / terminal close 日志应统一带上 `session_id`、`scenario_type`、`action`、`to_status`。
- How a future agent inspects this: 查看 targeted pytest 输出和 `backend/src/common/api/practice.py` 中统一 helper 的日志路径即可定位终态差异。
- Failure state exposed: 若仍有入口分叉，测试会直接报出具体 endpoint、场景类型和终态副作用不一致的位置。

## Inputs

- `backend/src/common/api/practice.py` — 现有 lifecycle POST 与旧 DELETE 兼容路由仍在分叉结束逻辑。
- `backend/src/common/db/session_lifecycle.py` — 唯一合法状态机与 sales / presentation 终态差异。
- `.gsd/milestones/M001/slices/S01/S01-RESEARCH.md` — 已确认生命周期单写入口是 S01 的首要收口点。

## Expected Output

- `backend/src/common/api/practice.py` — 统一的终态收口实现，被 lifecycle `end` 与旧 DELETE 入口共同使用。
- `backend/tests/integration/test_session_lifecycle_api.py` — 终态一致性与 live handler sync/close 回归覆盖。
- `backend/tests/contract/test_sessions.py` / `backend/tests/integration/test_session_flow.py` — 兼容入口与整体 session flow 的终态合约保护。
