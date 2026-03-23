# S05: 销售价值表达与异议处理基线

**Goal:** 让销售训练的客户压力、实时评分和统一报告都围绕“把产品价值翻译成客户收益，并用证据处理价格 / 竞品 / ROI / 风险异议”运转，而不是继续停留在泛化沟通维度或娱乐式闲聊。
**Demo:** 在绑定知识库的新 sales session 中，AI 客户会围绕 ROI、价格、竞品、证据持续追问；live `score_update` / `web/src/components/practice/ScorePanel.tsx` 会显示新的销售维度；结束后 `GET /api/v1/practice/sessions/{id}/report` 的 `main_issue` / `next_goal` 与顶部 3 张总览卡直接指出价值翻译、证据引用或异议推进上的短板，同时继续沿用 S02 的统一 evidence contract。
**Requirements:** Owns active `R003`; advances `R011`; reinforces validated `R005` by keeping the single-report baseline anchored in真实销售价值 / 异议语义而不重新引入事实漂移。

## Must-Haves

- Active write path（`backend/src/agent/capabilities/realtime_scoring.py` + `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` + `backend/src/common/api/practice.py`）必须产出稳定的销售基线事实：至少覆盖“价值表达、客户收益连接、证据使用、异议处理、推进下一步”五类维度；同时保留顶层 `overall_score`、`pass_flags`、`overall_result`、`main_issue`、`next_goal`、`evaluable`、`not_evaluable_reason` 合同，不能让 S02/S03 consumer 失真。
- `logic_score / accuracy_score / completeness_score` 这 3 个 session-level rollup 字段必须继续存在，但含义要改成对销售报告有用的三类总结（如 `价值表达`、`证据与收益`、`异议推进`），避免 report 页面继续把旧 generic 沟通标签伪装成新语义。
- 客户 persona/runtime 指令必须沿用 `persona_policy -> VoiceRuntimePolicyService.resolve_effective_policy(...) -> PracticeSession.voice_policy_snapshot -> /practice/sessions/{id}/knowledge-check` 这条权威材料链；S05 只能扩展 `persona_policy` 的销售焦点字段与编译后的角色契约，不能再发明第二条 materials read path。
- Web 消费面必须用最小改动把新语义真正显示出来：`web/src/components/practice/ScorePanel.tsx`、`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 与 focused tests 要和新后端词汇一致，同时继续把 comprehensive report / highlights 视为可缺失增强层。

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py`
- `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
- Manual/runtime review — 启动绑定知识库的 sales session，分别触发“价值翻译不足”“价格异议”“竞品追问”“证据 / 案例要求”四类对话，确认 live score_update / ScorePanel 出现新的销售维度，`/practice/sessions/{id}/knowledge-check` 展示与该轮问题一致的检索状态，最终 `/practice/sessions/{id}/report` 的 `main_issue` / `next_goal` 与顶部 3 张总览卡都落在销售价值 / 异议语义上。
- Failure-path inspection — 在薄证据 session、KB 未命中 / 检索失败、以及 legacy `score_snapshot.overall` fallback 三种场景下，确认 `practice_session_evidence_not_evaluable` / `practice_session_evidence_persisted` 日志、knowledge-check 状态和 report 降级文案都仍然可排障。

## Observability / Diagnostics

- Runtime signals: `score_update.dimension_scores`、`practice_session_evidence_persisted`、`practice_session_evidence_not_evaluable`、`ConversationMessage.score_snapshot.overall_score`、`PracticeSession.effectiveness_snapshot.main_issue/next_goal`、knowledge-check `status/summary/hit_rate/recent_queries`。
- Inspection surfaces: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 结构化日志、`GET /api/v1/practice/sessions/{id}/knowledge-check`、`GET /api/v1/practice/sessions/{id}/report`、`web/src/components/practice/ScorePanel.tsx`。
- Failure visibility: 显式 `not_evaluable_reason`、legacy/fallback contract tests、KB `miss/search_failed` 状态，以及 score panel 对未知维度的可见 fallback。
- Redaction constraints: 只暴露 KB ID、检索状态、query 摘要、评分与效果快照；不得把原始密钥、敏感资料全文或不必要的 transcript/PII 写入诊断面。

## Integration Closure

- Upstream surfaces consumed: `backend/src/agent/services/persona_policy.py`, `backend/src/sales_bot/services/voice_runtime_policy.py`, `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/api/practice.py`, `backend/src/common/conversation/session_evidence.py`, `web/src/hooks/websocket/message-handlers.ts`, `web/src/components/practice/ScorePanel.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`.
- New wiring introduced in this slice: `persona_policy` 销售焦点字段 -> compiled customer instruction contract -> StepFun realtime score/effectiveness snapshot -> unified report contract -> live score panel / report labels。
- What remains before the milestone is truly usable end-to-end: S06 仍需在这套问题分类之上做跨会话趋势，S08 仍需做最终发布级端到端验收；S05 自身 demo 不应再依赖额外 scorer 或第二条材料事实线。

## Tasks

- [x] **T01: 在 StepFun 写入层落地销售价值评分与效果快照基线** `est:4h`
  - Why: 先把事实写入面改成销售价值 / 异议语义，报告 / 回放 / 历史才能继续沿用 S02 的同一 projection，而不是再造读侧 scorer。
  - Files: `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/common/effectiveness/evaluator.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/api/practice.py`, `backend/tests/unit/test_realtime_scoring.py`, `backend/tests/unit/test_effectiveness_sales_baseline.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`, `backend/tests/contract/test_practice_evidence_contract.py`
  - Do: 用新的 5 维销售 rubric 替换 generic keyword scorer，并在 `evaluate_effectiveness_snapshot` / StepFun session flush / terminal fallback 中保留原有顶层 contract，但把 `main_issue` / `next_goal` 和 3 个 session rollup 改成销售价值、证据与异议推进语义；严禁把这套逻辑搬到 `SessionEvidenceService` 或前端重算。
  - Backend verify: `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py`
  - Done when: 实时写入的 `score_snapshot`、session-level score 字段和 report/replay contract 都稳定输出新的销售语义，同时 `main_issue` / `next_goal` 仍通过统一 evidence contract 读取。
- [ ] **T02: 用 persona policy 与知识库绑定编译真实销售追问契约** `est:3h`
  - Why: 只有评分改了还不够；S05 必须让客户 persona 真正围绕 ROI、价格、竞品、证据发问，并继续消费 S04 已冻结的材料绑定线。
  - Files: `backend/src/agent/services/persona_policy.py`, `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`, `backend/tests/unit/test_voice_instruction_compiler.py`, `backend/tests/unit/test_stepfun_knowledge_helpers.py`, `backend/tests/unit/test_voice_runtime_policy_service.py`
  - Do: 规范并消费 `persona_policy` 的销售焦点扩展键（如 `sales_focus`、`value_axes`、`objection_axes`、`expected_customer_questions`），在 `VoiceInstructionCompiler` 中把这些字段编译成单一客户 voice 的价值 / 异议追问准则，并让价格 / 产品 / 竞品 / 证据类 query 继续走 `stepfun_knowledge_helpers` 的实体型检索优化，而不是新增材料读取入口。
  - Backend verify: `cd backend && pytest tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_voice_runtime_policy_service.py`
  - Done when: 绑定知识库的客户 persona 会在编译后的基础契约里持续追问价值、预算、ROI、竞品与证据，且相关 tests 证明这些扩展字段被标准化、透传并用于检索 / 提问行为。
- [ ] **T03: 对齐 live/report 消费面并补端到端销售语义回归证明** `est:3h`
  - Why: 后端即使已经写入新的销售事实，如果 live score panel 和 report 仍显示旧 generic 标签，用户看到的仍然像“稳定地练错了方向”。
  - Files: `backend/tests/integration/test_sales_value_training_flow.py`, `web/src/components/practice/ScorePanel.tsx`, `web/src/components/practice/ScorePanel.test.tsx`, `web/src/hooks/websocket/message-handlers.test.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - Do: 先写 integration + web failing tests，喂入新的 `score_update` / report payload；再让 `ScorePanel` 的 icon / color / fallback 显示与新销售维度一致，并把 report 顶部 3 张卡与相关文案改成销售语义（保持 comprehensive-report enhancement 可缺失）；最后补一条 backend integration proof，证明真实 report API 会把新的 `main_issue` / `next_goal` 和 rollup 透传到消费面。
  - Backend verify: `cd backend && pytest tests/integration/test_sales_value_training_flow.py`
  - Web verify: `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
  - Done when: live score panel、report 页面和 focused tests 都展示新的销售价值 / 异议语义，且 backend integration proof 证明这些文本来自统一 report contract 而不是前端拼装。

## Files Likely Touched

- `backend/src/agent/services/persona_policy.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/src/agent/capabilities/realtime_scoring.py`
- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_realtime_scoring.py`
- `backend/tests/unit/test_effectiveness_sales_baseline.py`
- `backend/tests/unit/test_voice_instruction_compiler.py`
- `backend/tests/unit/test_stepfun_knowledge_helpers.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_voice_runtime_policy_service.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_sales_value_training_flow.py`
- `web/src/components/practice/ScorePanel.tsx`
- `web/src/components/practice/ScorePanel.test.tsx`
- `web/src/hooks/websocket/message-handlers.test.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
