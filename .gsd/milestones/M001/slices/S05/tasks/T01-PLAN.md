---
estimated_steps: 4
estimated_files: 8
skills_used:
  - safe-grow
  - test-driven-development
  - systematic-debugging
  - code-refactoring
  - verification-before-completion
---

# T01: 在 StepFun 写入层落地销售价值评分与效果快照基线

**Slice:** S05 — 销售价值表达与异议处理基线
**Milestone:** M001

## Description

这个任务先解决 S05 最关键的“事实到底写成什么”问题：所有后续 report / replay / history / trends 都已经被 S02 收口到统一 evidence projection，所以这里必须在 StepFun realtime 写入层直接生成销售价值语义，而不是去改 `SessionEvidenceService` 或前端重算。目标是在不破坏既有 top-level contract 的前提下，把旧 generic `专业度 / 沟通技巧 / 销售流程 / 异议处理 / 成交能力` 改成销售训练真正需要的价值表达、客户收益连接、证据使用、异议处理、推进下一步语义，并让 `main_issue` / `next_goal` 直接指出价值翻译和异议承接短板。

## Steps

1. 先在 `backend/tests/unit/test_realtime_scoring.py`、新增的 `backend/tests/unit/test_effectiveness_sales_baseline.py`、`backend/tests/unit/test_stepfun_realtime_handler.py` 和 `backend/tests/contract/test_practice_evidence_contract.py` 写 failing tests，锁住新的五维销售 rubric、sales-specific `main_issue` / `next_goal`、以及 `logic_score / accuracy_score / completeness_score` 的三类 sales rollup 映射，同时确保原有 top-level contract keys 不消失。
2. 在 `backend/src/agent/capabilities/realtime_scoring.py` 用最小可解释的规则替换 generic keyword heuristic：输入优先参考当前 stage、用户文本、会话上下文和 persona scoring weights，输出 canonical `overall_score` + 新的 `dimension_scores`，维度至少覆盖 `价值表达`、`客户收益连接`、`证据使用`、`异议处理`、`推进下一步`。
3. 在 `backend/src/common/effectiveness/evaluator.py`、`backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 和 `backend/src/common/api/practice.py` 把 session-level rollup、`pass_flags`、`main_issue`、`next_goal`、not-evaluable fallback 全部改成销售语义，但继续保留 `overall_result` / `evaluable` / `not_evaluable_reason` / report contract 的字段形状；严禁把这套逻辑搬到 `backend/src/common/conversation/session_evidence.py` 或前端。
4. 跑完 focused backend suites，确认 report/replay contract 仍通过统一 evidence 读到新的 sales-specific issue/goal 和 rollup 结果，再记录任何为了兼容 legacy `score_snapshot.overall` 做的 fallback 约束。

## Must-Haves

- [ ] `backend/src/agent/capabilities/realtime_scoring.py` 的输出必须从 generic 沟通评分切换成销售价值 / 异议语义，但 transport shape 仍保持 canonical `overall_score` + `dimension_scores`，不能让 websocket consumer 破裂。
- [ ] `backend/src/common/effectiveness/evaluator.py`、`backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 和 `backend/src/common/api/practice.py` 必须继续输出 `pass_flags`、`overall_result`、`main_issue`、`next_goal`、`evaluable`、`not_evaluable_reason`，且这些结果直接可被 report/replay contract 复用；不得把语义修正放到 projection/read-side 或前端。

## Verification

- `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py`
- `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py -k 'value or objection or report'`

## Observability Impact

- Signals added/changed: `ConversationMessage.score_snapshot.dimension_scores` 新维度命名、`PracticeSession.logic_score/accuracy_score/completeness_score` 的 sales rollup 含义、`PracticeSession.effectiveness_snapshot.main_issue/next_goal` 的销售问题分类、`practice_session_evidence_persisted` / `practice_session_evidence_not_evaluable` 日志。
- How a future agent inspects this: 读取 `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 中 score flush 逻辑、查看 `GET /api/v1/practice/sessions/{id}/report` 返回值、运行 `backend/tests/contract/test_practice_evidence_contract.py`。
- Failure state exposed: 薄证据 session 的 `INSUFFICIENT_TURN_DATA`、legacy `overall` fallback、以及 sales dimension 未正确映射到 3 个 report rollup 时的 contract failure。

## Inputs

- `backend/src/agent/capabilities/realtime_scoring.py` — 当前仍是 generic keyword heuristic，需要成为销售价值基线的权威写入口。
- `backend/src/common/effectiveness/evaluator.py` — 当前仍按 `3分钟连续表达 / 5轮追问 / 四段结构` 输出主问题与下一轮目标。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — active StepFun runtime 的 score_update 与 session flush 都在这里。
- `backend/src/common/api/practice.py` — terminal fallback 仍按旧维度把 realtime score 映射成 session score 字段。
- `backend/tests/unit/test_realtime_scoring.py` — 现有 realtime scorer 单测骨架。
- `backend/tests/unit/test_stepfun_realtime_handler.py` — current write-path session flush 行为测试。
- `backend/tests/contract/test_practice_evidence_contract.py` — 统一 report/replay contract 的边界证明。

## Expected Output

- `backend/src/agent/capabilities/realtime_scoring.py` — 产出销售价值五维 rubric 的 canonical realtime scorer。
- `backend/src/common/effectiveness/evaluator.py` — 输出 sales-specific `main_issue` / `next_goal` / `pass_flags` 的 evaluator。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 将最新 sales score snapshot 和 session rollup 持久化到 StepFun runtime/session。
- `backend/src/common/api/practice.py` — terminal fallback 与 session rollup 映射对齐新销售语义。
- `backend/tests/unit/test_realtime_scoring.py` — 锁住新的五维销售评分输出与权重/趋势行为。
- `backend/tests/unit/test_effectiveness_sales_baseline.py` — 锁住新的 `main_issue` / `next_goal` / rollup 语义和 not-evaluable fallback。
- `backend/tests/unit/test_stepfun_realtime_handler.py` — 锁住 StepFun session flush 的 sales rollup 映射与 evidence logging。
- `backend/tests/contract/test_practice_evidence_contract.py` — 锁住 report/replay 继续通过统一 contract 暴露新的 sales-specific facts。
