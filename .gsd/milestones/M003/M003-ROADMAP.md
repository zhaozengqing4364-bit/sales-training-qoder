# M003: 知识与角色真实性

**Vision:** 让 AI 客户真正围绕公司材料、价格/竞品/证据问题和 Persona 设定持续追问，并且能证明这些追问确实来自已绑定的知识和角色策略，而不是随机 prompt 漂移。

## Success Criteria

- 用户在价格、ROI、竞品、案例、实施风险等问题上，遇到的追问明显带有**公司材料和 Persona 立场**，而不是泛泛聊天。
- 同一 Persona 在多轮会话里保持稳定的人设强度、关注点和挑战方式，不会中途“失忆”或切换风格。
- 管理端能够区分三种状态：**知识库无答案 / 知识链未触发 / 知识检索失败**，而不是统一显示“没命中”。
- richer retrieval 和 persona 守卫不会明显拖慢实时训练，也不会让 sales runtime 变成新的不稳定源。

## Key Risks / Unknowns

- 知识库虽然已绑定到 `voice_policy_snapshot`，但价格/竞品/证据类问题未必真的走到运行时检索链。— 若没有“训练时真实使用”的证据，M003 只会让后台配置看起来更完整。
- Persona 真实性仍可能主要靠 prompt 维持，缺少运行时守卫。— 角色一旦漂移，用户会迅速感知到“这是假的客户”。
- 为了增强真实性而扩大检索和指令复杂度，可能导致响应变慢或上游抖动。— 若实时性显著变差，真实性增强会损害训练心流。
- 若为 M003 再发明第二套知识接入面，会破坏 M001/S04 已建立的 authority line。— 后续排障将再次回到“到底哪条链生效”的混乱状态。

## Proof Strategy

- “已绑定知识库”不等于“训练时真用上” → retire in S01 by proving 价格 / 竞品 / ROI / 证据类 query 的检索调用、hit/miss/search_failed 都能被同一条运行时证据线复查。
- Persona 容易漂移 → retire in S02 by proving Persona policy health 与 runtime 守卫能发现缺失策略、KB lock 漂移和明显人设失真。
- 真实追问仍然不够业务化 → retire in S03 by proving 训练中的连续追问围绕材料中的价值点、案例、竞争替代和实施顾虑展开。
- 管理员无法提前判断“这组 Persona + 材料到底会怎么追问” → retire in S04 by proving admin 侧存在可检查的预览 / 审计 / session 证据面。
- richer retrieval 让 runtime 变慢或更脆弱 → retire in S05 by proving objection-heavy session 下 latency、fallback、coach diagnostics 仍可控。

## Verification Classes

- Contract verification: persona policy / voice policy / knowledge-check / retrieval runtime metrics / report fields 的 schema 与 focused tests。
- Integration verification: admin Persona/knowledge 配置 → create session → StepFun runtime 检索 → 报告/knowledge-check 审计 的真实链路验证。
- Operational verification: 检索失败、KB not ready、无绑定知识库、Persona 缺策略、上游检索超时的降级与日志验证。
- UAT / human verification: 使用价格 / 竞品 / ROI / 案例问题进行真人脚本演练，判断 AI 客户是否更像真实业务对象。

## Milestone Definition of Done

This milestone is complete only when all are true:

- 销售训练在价格 / 竞品 / 证据类场景下，能够持续表现出材料驱动和角色驱动的追问，而不是偶尔答对。
- Persona 的关注点、挑战频率和行为边界具备可校验的 runtime 守卫，而不只是后台文案配置。
- 管理员可以在后台或 session 证据面看清楚：用了哪些知识、为什么没命中、是没答案还是链路失败。
- 知识真实性增强没有明显破坏实时训练稳定性和响应时延。
- 至少一条真实材料驱动的 objection-heavy 演练完成 live UAT 并留下可复查证据。

## Requirement Coverage

- Covers: R010
- Partially covers: R003, R004
- Leaves for later: R011, R012, R019
- Orphan risks: none

## Likely Work Surfaces

- `backend/src/sales_bot/services/voice_runtime_policy.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
- `backend/src/sales_bot/websocket/components/stepfun_tool_helpers.py`
- `backend/src/agent/services/persona_policy.py`
- `backend/src/agent/api/personas.py`
- `backend/src/common/api/practice.py`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/app/admin/knowledge/[id]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `docs/knowledge-base-audit-report.md`
- `backend/tests/unit/test_voice_instruction_compiler.py`
- `backend/tests/unit/test_stepfun_knowledge_helpers.py`
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`
- `backend/tests/unit/test_voice_runtime_policy_service.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/integration/test_persona_api.py`
- `backend/tests/integration/test_agent_persona_api.py`

## Slices

- [ ] **S01: 价格 / 竞品 / 证据 query 的知识真值线** `risk:high` `depends:[]`
  > After this: objection-heavy query 在 runtime 里的检索触发、命中状态、fallback 模式和失败原因都能被同一条 knowledge evidence line 复查。

- [ ] **S02: Persona 一致性守卫与策略健康收口** `risk:high` `depends:[S01]`
  > After this: Persona policy 缺失、KB lock 漂移、角色停用/失真等问题能在 admin 和 runtime 两侧被及时发现，而不是等到训练时“感觉不对”。

- [ ] **S03: 材料驱动的真实异议施压** `risk:high` `depends:[S01,S02]`
  > After this: AI 客户会围绕材料里的价值点、ROI、案例、替代方案、实施风险持续追问，而不只是把关键词复述一遍。

- [ ] **S04: 管理端预览与会话审计证据面** `risk:medium` `depends:[S01,S02]`
  > After this: 管理员可以在 Persona/knowledge 配置和已完成 session 上检查“这组材料 + 角色到底如何生效”，无需靠猜测排障。

- [ ] **S05: 检索时延、fallback 与稳定性护栏** `risk:medium` `depends:[S03,S04]`
  > After this: richer retrieval / persona 守卫在 objection-heavy 训练里仍保持可接受时延，并把 timeout / degraded 状态显式暴露。

- [ ] **S06: 真实业务脚本验收** `risk:medium` `depends:[S05]`
  > After this: 至少一组价格 / 竞品 / ROI / 案例脚本完成 live UAT，证明训练更像真实客户场景而不是知识问答 demo。

## Boundary Map

### S01 → S02

Produces:
- objection query 的统一 runtime evidence：query、hit/miss、retrieval mode、status、失败原因与 KB 绑定快照。
- `knowledge-check` / report / runtime metrics 之间可对照的最小检索证据面。
- 价格 / 竞品 / 证据 query 的 focused regression tests。

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- 已证明真实触发的 objection retrieval path。
- 针对 objection query 的 top_k / threshold / keyword candidate / snippet 策略基线。
- 可供 Persona 指令层复用的材料命中语义。

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- Persona policy 的 runtime 守卫规则、policy health issue types 和 drift 检测边界。
- 角色强度、常见追问、challenge frequency、KB grounding 等稳定生效前提。

Consumes from S01:
- 已可复查的检索证据线。

### S01 + S02 → S04

Produces:
- admin 侧 Persona/knowledge 预览或审计入口。
- session 侧“材料如何参与本次训练”的 drill-in 证据面。
- 从后台配置到训练运行时的可检查闭环。

Consumes from S01:
- 检索调用与状态证据。

Consumes from S02:
- Persona policy 健康与守卫语义。

### S03 + S04 → S05

Produces:
- objection-heavy runtime 的 latency budget、timeout/fallback 状态和 degraded diagnostics。
- richer retrieval 不拖垮 realtime flow 的护栏。
- 对“真实性增强有效”与“真实性增强拖慢系统”的平衡基线。

Consumes from S03:
- 材料驱动的真实异议施压链路。

Consumes from S04:
- admin / session 审计证据面。

### S05 → S06

Produces:
- 真人脚本 UAT 路径和可复查证据。
- 真实价格 / 竞品 / ROI / 案例场景下的最终 acceptance proof。

Consumes from S05:
- 稳定性、fallback 与时延护栏。
