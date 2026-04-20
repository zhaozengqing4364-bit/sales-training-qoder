---
id: T01
parent: S05
milestone: M001
provides:
  - StepFun 写入层现在会直接产出销售价值五维 score snapshot、三类 session rollup，以及 sales-specific main_issue/next_goal，而 unified report/replay contract 继续复用原字段形状
key_files:
  - backend/src/agent/capabilities/realtime_scoring.py
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/api/practice.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_realtime_scoring.py
  - backend/tests/unit/test_effectiveness_sales_baseline.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - 保留 `pass_flags.*` 和 `SessionReport.logic_score/accuracy_score/completeness_score` 这些既有键名，只在 write layer 重映射为销售价值表达、证据收益和异议推进语义（D024）
patterns_established:
  - 用 `build_sales_rollup_scores` + `build_sales_effectiveness_metrics` 统一驱动 StepFun session flush、terminal fallback 和 evaluator，避免在 SessionEvidenceService/read-side 再算一套 sales scorer
observability_surfaces:
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/api/practice.py
  - practice_session_evidence_persisted / practice_session_evidence_not_evaluable
  - ConversationMessage.score_snapshot.overall_score / dimension_scores
  - PracticeSession.effectiveness_snapshot.main_issue / next_goal
  - none for manual runtime in this task
duration: 1h35m
verification_result: passed
completed_at: 2026-03-23T20:06:53+08:00
blocker_discovered: false
---

# T01: 在 StepFun 写入层落地销售价值评分与效果快照基线

**Replaced the generic StepFun sales scorer with a five-dimension value/evidence/objection rubric and mapped the persisted session evidence back onto the existing unified report contract.**

## What Happened

我按任务计划先把测试改成销售语义，再让实现追上这些断言，没有去改 `SessionEvidenceService` 或前端读侧逻辑。

这次真正落地的写入层变化有四块：

1. `backend/src/agent/capabilities/realtime_scoring.py`
   - 默认维度从 `专业度 / 沟通技巧 / 销售流程 / 异议处理 / 成交能力` 改成 `价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`。
   - 评分规则从泛化关键词法切到销售语义：会结合当前 stage、当前文本、最近上下文，以及 persona 提供的 scoring weights。
   - 输出现在以 canonical `overall_score + dimension_scores` 为主，同时保留 legacy `overall + dimensions` 兼容字段，避免现有 websocket consumer 立刻断裂。
   - feedback 也切成销售价值导向建议，而不是泛化沟通提示。

2. `backend/src/common/effectiveness/evaluator.py`
   - 新增共享 helper：`build_sales_rollup_scores` 和 `build_sales_effectiveness_metrics`。
   - 三个 session-level rollup 字段的语义被重映射为：
     - `logic_score` → 价值表达 / 客户收益连接
     - `accuracy_score` → 客户收益连接 / 证据使用
     - `completeness_score` → 异议处理 / 推进下一步
   - `evaluate_effectiveness_snapshot` 在保留顶层 contract 形状的同时，改为返回 sales-specific `main_issue` / `next_goal`，并给薄证据会话提供销售语义的 `not_evaluable` 降级文案。
   - 为了避免跨 slice 级联破坏，`pass_flags.pass_3min_flow / pass_5turn_defense / pass_4step_structure` 的 key 没改，但语义已经重映射到销售价值表达、异议承接和证据/下一步基线。

3. `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
   - StepFun runtime flush session 时，不再把 snapshot 粗暴映射回旧通用维度，而是通过共享 helper 生成 sales rollup 和效果快照。
   - live feedback 读取 scorer 结果时，也改成优先消费 canonical `overall_score / dimension_scores`。
   - `practice_session_evidence_persisted` / `practice_session_evidence_not_evaluable` 继续保留，并且现在伴随销售语义快照一起输出。

4. `backend/src/common/api/practice.py`
   - terminal fallback 复用同一套 sales rollup helper，把 runtime/message snapshot 映射成 session-level 3 分数字段。
   - `_ensure_effectiveness_snapshot` 的 fallback 指标也改为销售语义，确保 report API 继续沿用 unified evidence contract 时看到的 `main_issue / next_goal` 已经是销售价值 / 证据 / 异议推进问题，而不是旧的“3分钟连续表达 / 4段结构”。

测试侧我做了对应的最小闭环：

- 重写 `backend/tests/unit/test_realtime_scoring.py`，锁住 5 维销售 rubric、canonical scorer payload、stage/persona-weight 行为。
- 新增 `backend/tests/unit/test_effectiveness_sales_baseline.py`，锁住三类 rollup 映射、sales-specific `main_issue / next_goal`、以及 `not_evaluable` 降级。
- 更新 `backend/tests/unit/test_stepfun_realtime_handler.py`，证明 StepFun session flush 会把新五维 snapshot 映射到三类 session rollup 并产出 sales issue/goal。
- 更新 `backend/tests/contract/test_practice_evidence_contract.py`，证明 report/replay 继续通过统一 evidence contract 暴露新的销售事实，而 top-level keys 没消失。

## Verification

我先按 TDD 把新断言写进去，再跑 task-focused backend suite，看到 scorer / evaluator / StepFun flush / contract 全部按预期失败，然后才改实现。

完成实现后，重新跑了 task plan 要求的两条 focused backend 命令：都通过。

另外按 slice 级 gate 我补跑了：

- slice backend command：当前仍失败，因为 `tests/integration/test_sales_value_training_flow.py` 还不存在，这是 T03 计划里的 integration proof，不是本任务遗留的本地回归。
- slice web command：当前返回 0，实际只跑到了现有的 `message-handlers` 与 `report/page` 两个文件；`ScorePanel.test.tsx` 尚未落地，这同样属于 T03 的消费面对齐工作。
- Manual/runtime review 与 Failure-path inspection：本任务没有触碰 UI/knowledge-check 消费面，也还没创建 `test_sales_value_training_flow.py`，因此没有在 T01 阶段宣称完成这两项 slice 级人工验证。

此外我用一个仓库内小脚本直接验证了 observability 信号：

- `score_update.dimension_scores` 已输出新的五个销售维度；
- StepFun flush 后 `session.logic_score/accuracy_score/completeness_score` 已是新的 sales rollup；
- `effectiveness_snapshot.main_issue/next_goal` 已落在 value/evidence 语义上；
- `practice_session_evidence_persisted` / `practice_session_evidence_not_evaluable` 日志都仍然可见。

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 2.24s |
| 2 | `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py -k 'value or objection or report'` | 0 | ✅ pass | 3.20s |
| 3 | `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py` | 4 | ❌ fail | 0.01s |
| 4 | `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 0.74s |
| 5 | `cd backend && PYTHONPATH=src venv/bin/python - <<'PY' ...`（直接触发 scorer + StepFun flush + not_evaluable fallback observability） | 0 | ✅ pass | ~1s |

## Diagnostics

后续 agent 可以用这些面快速确认本任务输出仍然成立：

- `backend/src/agent/capabilities/realtime_scoring.py`
  - 默认五维 rubric
  - canonical `overall_score / dimension_scores`
  - persona weights 与 stage-aware scoring
- `backend/src/common/effectiveness/evaluator.py`
  - `build_sales_rollup_scores`
  - `build_sales_effectiveness_metrics`
  - sales-specific `main_issue / next_goal`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `_run_realtime_feedback`
  - `_apply_latest_scores_to_session`
  - `practice_session_evidence_persisted`
  - `practice_session_evidence_not_evaluable`
- `backend/src/common/api/practice.py`
  - `_apply_sales_realtime_score_snapshot_to_session`
  - `_ensure_effectiveness_snapshot`
  - `GET /api/v1/practice/sessions/{id}/report`
- 直接信号
  - `ConversationMessage.score_snapshot.overall_score`
  - `ConversationMessage.score_snapshot.dimension_scores`
  - `PracticeSession.logic_score / accuracy_score / completeness_score`
  - `PracticeSession.effectiveness_snapshot.main_issue / next_goal / not_evaluable_reason`

## Deviations

- 为了不把 S05 又做成 read-side scorer，我额外新增了 `build_sales_rollup_scores / build_sales_effectiveness_metrics` 这组共享 helper，并让 StepFun flush 与 terminal fallback 都复用它；这属于实现细节上的局部收口，方向仍完全符合计划里“write layer 负责销售语义”的约束。
- `RealtimeScoringCapability` 没有直接删掉 legacy `overall / dimensions` 字段，而是改成 canonical + legacy 双写。这是一个兼容性让步，避免当前未纳入 T01 范围的 presentation/legacy consumer 被无关破坏；权威读取路径已经切到 canonical key 优先。

## Known Issues

- slice backend 验证中的 `tests/integration/test_sales_value_training_flow.py` 还不存在，导致整条 slice backend command 目前必然报 `file or directory not found`；这是 T03 计划内的待建 integration proof，不是本任务内的回归。
- slice web 验证中的 `src/components/practice/ScorePanel.test.tsx` 还未落地，所以当前 web command 只跑到了另外两个现有文件；真正的 ScorePanel 词汇对齐要等 T03。
- Manual/runtime review 与 failure-path inspection 还没有在真实绑定 KB 的 sales session 上做完；这部分必须等 T02/T03 把 persona prompt 与 UI 消费面都补齐后再做端到端验收。
- `common.conversation.session_evidence` 里基于 message snapshot 的 legacy fallback 仍保留旧维度 alias；当前 T01 通过 write layer 保证 sales session 会优先落到 session-level rollup，不需要在读侧再动它，但后续如果有人绕开 write layer 只喂 message snapshot，仍可能看到 legacy fallback 行为。

## Files Created/Modified

- `backend/src/agent/capabilities/realtime_scoring.py` — 将 realtime scorer 改成销售价值五维 rubric，并双写 canonical/legacy payload
- `backend/src/common/effectiveness/evaluator.py` — 新增 sales rollup helper，并把 `main_issue / next_goal / not_evaluable` 语义切到销售价值/证据/异议方向
- `backend/src/common/effectiveness/__init__.py` — 导出 sales rollup/effectiveness helper
- `backend/src/common/api/practice.py` — terminal fallback 与 snapshot fallback 复用 sales rollup helper，对齐统一 report contract
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun runtime score flush 与 live feedback 消费改为 sales rollup / canonical snapshot
- `backend/tests/unit/test_realtime_scoring.py` — 锁住新的五维销售评分输出与 persona/stage 行为
- `backend/tests/unit/test_effectiveness_sales_baseline.py` — 新增 sales baseline 单测，覆盖三类 rollup 与 sales issue/goal
- `backend/tests/unit/test_stepfun_realtime_handler.py` — 锁住 StepFun flush 到 session rollup 的销售语义映射
- `backend/tests/contract/test_practice_evidence_contract.py` — 锁住 unified report/replay contract 继续暴露新的 sales-specific facts
- `.gsd/DECISIONS.md` — 追加 D024，记录“保留 contract key、重映射 sales 语义”的架构决策
- `.gsd/KNOWLEDGE.md` — 记录 S05 改语义时应保 key、不保旧语义的 gotcha
- `.gsd/milestones/M001/slices/S05/tasks/T01-SUMMARY.md` — 记录本任务执行与验证证据
