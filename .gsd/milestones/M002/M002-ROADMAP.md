# M002: 实时教练闭环

**Vision:** 在 M001 稳定主链路和统一训练事实源之上，把销售训练从“结束后看报告”推进到“训练中就能被正确地教”。实时提示必须少而准、与最终报告同口径、失败时不打断训练主线。

## Success Criteria

- 用户在真实销售演练中能看到围绕**价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步**的实时评分变化，而不是旧的泛化维度。
- 每一轮对话最多暴露一个主要动作方向；阶段提示、模糊表达提示和动作卡不会刷屏或互相打架。
- 训练中的主提示方向与训练后报告中的 `main_issue` / `next_goal` 保持一致，不出现“实时教练说 A、报告总结说 B”的漂移。
- 当实时教练链路部分失败、被静音或重连恢复时，训练主链路继续可用，并明确暴露“教练已降级 / 数据暂缺”的状态。

## Key Risks / Unknowns

- 实时提示可能沿用历史泛化维度与旧 UI 标签，导致用户看到的训练目标仍然偏离销售价值表达。— 这会让 M001/S05 刚建立的销售语义在训练页被重新冲淡。
- 多条反馈通道（模糊词 / 阶段 / score_update / action_card）可能同时推送，造成提示噪声和心流破坏。— 若训练中被系统不断打断，实时教练反而会降低完成率。
- 训练中提示与训练后报告若不共享同一判断基线，会继续出现事实漂移。— 用户和主管都不会信任教练建议。
- capability 模块失败、WebSocket 重连或 StepFun 上游抖动时，实时教练可能比训练主链路更脆弱。— 若失败被静默吞掉，用户会把“没提示”误判成自己练得没问题。

## Proof Strategy

- 销售语义仍停留在旧实时维度 / 旧前端标签 → retire in S01 by proving practice 右侧面板直接展示当前 sales rubric，并且 WebSocket `score_update` / `stage_update` / `action_card` 契约被同一套测试覆盖。
- 多反馈通道刷屏 → retire in S02 by proving 多轮真实会话中每轮提示数被约束、重复消息被去重、同一轮只保留唯一主动作卡。
- 训练中建议与报告结论漂移 → retire in S04 by proving 同一 session 的 realtime snapshot 与 report `main_issue` / `next_goal` 可以一一对照且不冲突。
- 实时教练成为新的不稳定源 → retire in S05 by proving capability 失败、重连恢复、上游短暂抖动都只让 coach surface 降级，不会让训练主链路卡死。

## Verification Classes

- Contract verification: `score_update` / `stage_update` / `action_card` payload、前端 `ScoreUpdate` 类型、右侧面板显示 contract、report 对照 contract 的 focused tests。
- Integration verification: 销售训练页 `practice/[sessionId]` + sales WebSocket + realtime scoring/stage/fuzzy/action 真实多轮串联验证。
- Operational verification: capability failure、StepFun 重连、WS reconnect、临时无提示 / coach degrade 可视化验证。
- UAT / human verification: 真实销售话术演练里，提示是否足够少、足够明确，且能指导用户下一轮改法。

## Milestone Definition of Done

This milestone is complete only when all are true:

- 实时教练使用的销售维度、阶段语义和动作卡规则已经与当前销售训练基线对齐。
- 训练页不会同时堆叠多条相互竞争的建议；用户能明确知道“这一轮最该改什么”。
- 报告页、回放页和实时训练页对同一 session 的主问题与下一目标不再各说各话。
- 训练链路在教练模块降级时仍能继续，且降级状态对用户和排障都可见。
- 至少一条真实销售训练路径完成 live UAT：训练中提示可用、结束后报告一致、失败路径可诊断。

## Requirement Coverage

- Covers: R009
- Partially covers: R003, R005
- Leaves for later: R010, R011, R012
- Orphan risks: none

## Likely Work Surfaces

- `backend/src/agent/capabilities/realtime_scoring.py`
- `backend/src/agent/capabilities/sales_stage.py`
- `backend/src/agent/capabilities/fuzzy_detection.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/effectiveness/evaluator.py`
- `web/src/hooks/websocket/types.ts`
- `web/src/hooks/websocket/message-handlers.ts`
- `web/src/components/practice/ScorePanel.tsx`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `backend/tests/unit/test_realtime_scoring.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `web/src/components/practice/ScorePanel.test.tsx`
- `web/src/hooks/websocket/message-handlers.test.ts`

## Slices

- [x] **S01: 实时评分与训练页销售语义对齐** `risk:high` `depends:[]`
  > After this: 用户在训练页看到的实时评分维度、阶段标签和建议文案已经与当前销售价值表达 / 异议处理 rubric 对齐，而不是旧的泛化评分面板。

- [x] **S02: 提示节奏收口与单轮唯一动作卡** `risk:high` `depends:[S01]`
  > After this: 多轮对话里每一轮只保留一个主要动作方向，重复阶段/模糊词/评分提示被节流和去重，不再刷屏。

- [ ] **S03: 阶段推进教练与下一轮规则闭环** `risk:medium` `depends:[S01,S02]`
  > After this: 实时阶段、分维变化和动作卡能共同指向“下一轮该怎么问 / 怎么答 / 怎么推进”，而不是三套平行提示。

- [ ] **S04: 训练中建议与报告结论一致性** `risk:medium` `depends:[S01,S03]`
  > After this: 同一 session 的实时教练快照可以和 report / replay 中的 `main_issue`、`next_goal`、`stage_summary` 对齐复查。

- [ ] **S05: 教练链路降级与重连可观测性** `risk:medium` `depends:[S02,S03]`
  > After this: capability 失败、上游短暂抖动或重连恢复时，训练继续进行，同时 UI 和日志能明确显示 coach degraded / resume 状态。

- [ ] **S06: 实时教练端到端验收** `risk:medium` `depends:[S04,S05]`
  > After this: 一条真实销售训练链路已经证明实时提示可用、频率受控、报告一致、降级路径可诊断。

## Boundary Map

### S01 → S02

Produces:
- 统一的 sales realtime score contract：训练页、WebSocket payload、StepFun runtime 对同一组销售维度命名与字段结构达成一致。
- 前端 `ScoreUpdate` / 右侧面板消费边界，能够识别 turn、stage、dimension、suggestions 的同一读形。
- 围绕 sales rubric 的 focused tests，防止旧“专业度/沟通技巧/成交能力”标签回流。

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- 每轮提示上限、冷却规则、重复消息抑制规则。
- `fuzzy_detection`、`stage_update`、`score_update`、`action_card` 的优先级与合并语义。
- 训练页中“唯一主动作”的稳定展示边界。

Consumes from S01:
- 已统一的 realtime score/stage/action payload 语义。

### S03 → S04

Produces:
- 阶段推进建议与下一轮动作规则的统一生成/展示面。
- 从实时 score delta + stage context 到 action card 的稳定映射边界。
- 多轮训练中可回放的 coach snapshot 语义。

Consumes from S01:
- 销售实时维度 contract。

Consumes from S02:
- 提示节奏与单轮唯一动作规则。

### S01 + S03 → S04

Produces:
- report / replay / realtime 对齐所需的 coach snapshot 字段或稳定派生规则。
- `main_issue` / `next_goal` 与 realtime action card 的对照基线。

Consumes from S01:
- 标准化 score/stage payload。

Consumes from S03:
- 统一的下一轮动作规则。

### S02 + S03 → S05

Produces:
- coach degrade 状态、reconnect 恢复后的 UI / log / runtime 可观测边界。
- capability 失败不打断训练主链路的降级策略。
- 对“无提示是因为无问题”与“无提示是因为链路降级”的显式区分。

Consumes from S02:
- 提示节奏收口规则。

Consumes from S03:
- 阶段推进与动作卡生成链路。

### S04 + S05 → S06

Produces:
- 实时教练最终验收路径：练中提示 → 练后报告 → 降级恢复 → 证据复查。
- 真实销售训练的 live proof 与失败路径 proof。

Consumes from S04:
- 练中 / 练后结论一致性。

Consumes from S05:
- 教练链路降级与可观测性。
