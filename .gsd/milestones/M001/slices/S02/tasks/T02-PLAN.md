---
estimated_steps: 4
estimated_files: 7
---

# T02: 建立共享会话证据读模型并收口报告/回放

**Slice:** S02 — 训练证据落库与报告事实源统一
**Milestone:** M001

## Description

这个任务把 S02 的核心边界落成一个显式服务：共享 session evidence projection。它从 `PracticeSession` + ordered `ConversationMessage` 生成标准化事实视图，再让 quick report 与 replay 共用这层，而不是继续各自直接拼 DB 字段。完成后，同一 completed session 在 report 与 replay 上看到的 overall/evaluable/stage evidence 必须是同一个投影。

## Steps

1. 新增 `backend/src/common/conversation/session_evidence.py`（或同等职责文件），封装 session + messages 读取、legacy score key 归一、overall score 计算、阶段汇总、evidence completeness 与 session-level result metadata 组装。
2. 让 `get_session_report()` 与 `ReplayService` 改读这个 projection，而不是各自直接访问 `PracticeSession` / `ConversationMessage` 后再临时拼 shape。
3. 补充 unit / contract / integration tests，断言 report 与 replay 对同一 session 的 top-line score、stage summary、逐轮 score snapshot、evaluable 语义完全一致，并保持 completed-session gating 与访问控制不变。
4. 运行 focused pytest，直到 report / replay 共用 projection 的行为稳定可回归。

## Must-Haves

- [ ] quick report 与 replay 都从同一个 evidence projection 取 overall score、阶段摘要、逐轮 evidence 与 evaluable/result metadata。
- [ ] 共享 projection 兼容历史 `score_snapshot.overall` 数据，不要求先做一次性回填才能读取旧会话。

## Verification

- `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
- 额外断言：同一 completed session 的 report / replay 响应在 overall score、main issue / next goal、not_evaluable_reason 上对齐。

## Observability Impact

- Signals added/changed: evidence projection 构建日志要能标出 session_id、message_count、是否回退 legacy key、projection completeness。
- How a future agent inspects this: 直接看 `SessionEvidenceService`、对应 unit/contract tests，以及 report/replay API 响应里的 evidence 字段即可判断偏差发生在哪层。
- Failure state exposed: 若 projection 缺字段，要能知道是会话顶层缺 score、消息缺 analysis，还是 consumer 绕开了共享读模型。

## Inputs

- `backend/src/common/conversation/replay.py` — 当前 replay 已拥有 completed-session gating 与消息 shape，是共享读模型最适合复用的消费面之一。
- `backend/src/common/api/practice.py` — quick report 仍主要直接读取 `PracticeSession` 顶层字段，需要被切到共享 projection。
- T01 提供的稳定 `overall_score` / evaluable 落库语义 — 没有这个前提，共享读模型只能继续携带写入漂移。

## Expected Output

- `backend/src/common/conversation/session_evidence.py` — 单一的 session evidence projection service。
- `backend/src/common/conversation/replay.py` / `backend/src/common/api/practice.py` — report 与 replay 统一改读共享 projection。
- `backend/tests/unit/test_session_evidence_service.py` / `backend/tests/contract/test_practice_evidence_contract.py` / `backend/tests/integration/test_practice_evidence_flow.py` — 锁定 report/replay 共享事实源的回归保护。
