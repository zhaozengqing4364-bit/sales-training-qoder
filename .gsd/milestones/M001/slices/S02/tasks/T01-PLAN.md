---
estimated_steps: 4
estimated_files: 6
---

# T01: 稳定逐轮证据写入与无证据终态语义

**Slice:** S02 — 训练证据落库与报告事实源统一
**Milestone:** M001

## Description

先把“写进数据库的到底是什么”收稳。这个任务只处理写入边界：StepFun 逐轮消息分析 payload 的稳定键形，以及会话结束时的 evaluable / result metadata。它不试图解决所有消费面问题，但必须把零轮/薄证据会话从“summary 失败”改成“明确不可评估”，否则后续任何共享读模型都只能翻译异常。

## Steps

1. 规范 `stepfun_message_helpers` 与相关 realtime persistence 写入口，让逐轮 analysis payload 始终写出稳定字段，特别是 `score_snapshot.overall_score`、`sales_stage`、`fuzzy_words`、`ai_feedback`、`transcript_metadata` 的落库语义。
2. 检查 sales realtime session 结束时的会话级 score/effectiveness 写入，补齐证据不足场景的 `evaluable=false`、`not_evaluable_reason` 与 result metadata，避免 completed terminal path 继续依赖 summary 成功。
3. 在现有 unit tests 基础上补充 legacy `overall` 兼容、duplicate patch、session-level score flush、零轮/薄证据终态语义断言。
4. 运行 focused pytest，确保后续任务读取到的是稳定写入事实，而不是靠 consumer 猜测修补。

## Must-Haves

- [ ] 逐轮消息 persistence 对历史 `score_snapshot.overall` 保持兼容，但新的写入与 patch 路径都以 `overall_score` 为规范键形。
- [ ] 结束零轮/薄证据销售会话时，系统会持久化明确的不可评估事实和原因，而不是把 `[SUMMARY_GENERATION_FAILED]` 冒充成终态语义。

## Verification

- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py`
- 额外断言：同一 session 的 persisted message analysis 与 terminal session snapshot 都能提供稳定 `overall_score` / evaluable 语义。

## Observability Impact

- Signals added/changed: 写入与终态收口日志要能区分“证据已持久化”“证据不足但已显式不可评估”“summary 真正异常”。
- How a future agent inspects this: 看 StepFun persistence unit tests，加上 `backend/src/common/api/practice.py` / realtime handler 的结构化日志即可判断问题出在 message write 还是 terminal flush。
- Failure state exposed: 会暴露缺的是 turn-level analysis、session-level snapshot，还是 summary pipeline 本身，而不是统一收敛成 500。

## Inputs

- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — 当前逐轮分析 payload 已集中在这里归一，但还没有把 `overall_score` 与 legacy key 漂移彻底收口。
- `backend/src/common/api/practice.py` — S01 已把终态写入口统一到这里；S02 需要在这个单写入口上补齐“不可评估也算一种事实”。
- `.gsd/milestones/M001/slices/S01/S01-SUMMARY.md` — 已明确零轮终态现在会暴露 `[SUMMARY_GENERATION_FAILED]`，这是本任务必须退休的前置风险。

## Expected Output

- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` / `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 稳定的逐轮与会话级 evidence write contract。
- `backend/src/common/api/practice.py` — completed terminal path 对薄证据会话写出显式 evaluable/result metadata。
- `backend/tests/unit/test_stepfun_message_helpers.py` / `backend/tests/unit/test_stepfun_realtime_persistence.py` / `backend/tests/unit/test_sales_message_persistence.py` — 回归覆盖写入键形与无证据终态语义。
