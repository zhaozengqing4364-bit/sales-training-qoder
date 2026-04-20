---
estimated_steps: 4
estimated_files: 6
skills_used:
  - safe-grow
  - test-driven-development
  - systematic-debugging
  - verification-before-completion
---

# T02: 用 persona policy 与知识库绑定编译真实销售追问契约

**Slice:** S05 — 销售价值表达与异议处理基线
**Milestone:** M001

## Description

这个任务把“训练目标围绕真实价值和异议处理”落实到客户 persona 本身。S04 已经把材料绑定权威线收成 `persona_policy -> VoiceRuntimePolicyService.resolve_effective_policy(...) -> PracticeSession.voice_policy_snapshot -> /knowledge-check`，所以这里不能新建第二条材料读取入口，只能扩展 `persona_policy` 的销售焦点字段，并把它们编译成客户语气、追问方向和检索偏好。目标是让绑定知识库的客户稳定追问 ROI、预算、价格、竞品、实施风险和证据，而不是回到泛泛对话。

## Steps

1. 先在 `backend/tests/unit/test_voice_instruction_compiler.py`、`backend/tests/unit/test_stepfun_knowledge_helpers.py` 和 `backend/tests/unit/test_voice_runtime_policy_service.py` 写 failing tests，明确 `persona_policy` 扩展字段（如 `sales_focus`、`value_axes`、`objection_axes`、`expected_customer_questions`）如何被标准化、透传并编译成客户行为约束。
2. 在 `backend/src/agent/services/persona_policy.py` 中规范这些扩展字段的最小 normalization / forward-compat 行为，保证它们在 persona policy 里稳定存在、不过度 schema 化，也不会破坏现有 legacy prompt / KB 字段兼容。
3. 在 `backend/src/sales_bot/services/voice_instruction_compiler.py` 把这些扩展字段编译进基础角色契约：客户必须围绕价值翻译、客户收益、ROI、价格、竞品、实施风险、案例证据持续追问，并继续遵守“一轮最多一个问题句”和 KB lock / coach mode 规则；如有必要，只在 `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` 扩大价格 / 产品 / 竞品 / 证据类 query 的 retrieval 容量与 snippet 策略。
4. 跑完 focused backend suites，确认 effective policy 与 knowledge-check 仍沿用 S04 权威线，且没有引入新的 runtime read path、admin schema 迁移或第二套材料语义。

## Must-Haves

- [ ] `backend/src/agent/services/persona_policy.py` 必须允许 sales-focus 扩展键稳定保留 / 标准化，但不能因此破坏现有 `system_prompt`、`knowledge_base_ids`、`tool_policy` 的兼容行为，也不能强迫这个 slice 顺便改 admin Persona 表单 schema。
- [ ] `backend/src/sales_bot/services/voice_instruction_compiler.py` 和 `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` 必须让绑定知识库的客户围绕 ROI / 预算 / 价格 / 竞品 / 证据追问并优先命中相关材料；整个链路仍只消费 `voice_runtime_policy` 冻结出的 effective policy。

## Verification

- `cd backend && pytest tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_voice_runtime_policy_service.py`
- `cd backend && pytest tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_voice_runtime_policy_service.py -k 'sales or objection or kb'`

## Observability Impact

- Signals added/changed: `persona_policy` 中的 sales-focus 扩展字段、compiled base contract 指令文本、knowledge helper 对 entity / price / competitor / proof query 的 retrieval 参数、`voice_policy_snapshot.persona_policy` 中冻结的 sales-focus 内容。
- How a future agent inspects this: 读取 `backend/src/sales_bot/services/voice_instruction_compiler.py` 编译结果、查看 `backend/tests/unit/test_voice_instruction_compiler.py` 与 `backend/tests/unit/test_voice_runtime_policy_service.py` 的断言、用 `/practice/sessions/{id}/knowledge-check` 复核 query 状态。
- Failure state exposed: 扩展字段丢失或被覆盖、compiled instructions 仍然只讲 generic 客户行为、价格/竞品/证据 query 没有触发实体型 retrieval 优化。

## Inputs

- `backend/src/agent/services/persona_policy.py` — 当前只规范 core keys，但允许保留 extension fields。
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — 当前角色行为准则还偏 generic，需编译真实销售追问语义。
- `backend/src/sales_bot/services/voice_runtime_policy.py` — effective policy 与 snapshot 冻结的上游权威线，任务只消费它，不应重建。
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — 价格 / 产品 / 参数等实体型 query 的 retrieval 调优入口。
- `backend/tests/unit/test_voice_instruction_compiler.py` — 当前 KB lock / 单问题句 contract 测试骨架。
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — 当前 retrieval helper 行为测试。
- `backend/tests/unit/test_voice_runtime_policy_service.py` — effective policy / snapshot 保真测试。

## Expected Output

- `backend/src/agent/services/persona_policy.py` — sales-focus 扩展字段的 normalization / forward-compat 规则。
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — 编译后的价值翻译 / 异议追问 / 单问题句客户契约。
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — 价格 / 竞品 / 证据类 query 的 retrieval 优化仍在原 helper 中完成。
- `backend/tests/unit/test_voice_instruction_compiler.py` — 锁住扩展字段如何进入 compiled contract。
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — 锁住销售异议类 query 的 retrieval 参数和 snippet 策略。
- `backend/tests/unit/test_voice_runtime_policy_service.py` — 锁住 effective policy / snapshot 继续沿用同一材料冻结线。
