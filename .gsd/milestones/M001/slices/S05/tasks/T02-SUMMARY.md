---
id: T02
parent: S05
milestone: M001
provides:
  - persona_policy 现在会稳定标准化并保留 sales-focus 扩展键，voice runtime 会把这些字段编译成真实销售追问契约，并让价格/竞品/证据类 query 继续复用现有 StepFun 检索调优入口
key_files:
  - backend/src/agent/services/persona_policy.py
  - backend/src/sales_bot/services/voice_instruction_compiler.py
  - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
  - backend/tests/unit/test_voice_instruction_compiler.py
  - backend/tests/unit/test_stepfun_knowledge_helpers.py
  - backend/tests/unit/test_voice_runtime_policy_service.py
key_decisions:
  - D025: 把 sales-focus persona 扩展字段集中标准化在 persona_policy，并继续通过现有 voice instruction contract + stepfun_knowledge_helpers 落地，而不是新增第二条 materials/read path
patterns_established:
  - 价格/竞品/ROI 证据类问题统一复用 stepfun_knowledge_helpers 的 widened entity-query tuning，而不是分叉新的 retrieval contract
observability_surfaces:
  - backend/src/agent/services/persona_policy.py
  - backend/src/sales_bot/services/voice_instruction_compiler.py
  - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
  - voice_policy_snapshot.persona_policy / instruction_contract_hash
  - none for manual runtime in this task
duration: 1h24m
verification_result: passed
completed_at: 2026-03-23T22:02:00+08:00
blocker_discovered: false
---

# T02: 用 persona policy 与知识库绑定编译真实销售追问契约

**Compiled sales-focus persona policy into customer objection prompts and widened price/competitor/proof KB retrieval tuning on the existing StepFun authority line.**

## What Happened

我按计划先写红测试，再只在既有 authority line 上补实现，没有新开第二条材料读取入口，也没有顺手去改 admin persona schema。

这次落地有三块核心改动：

1. `backend/src/agent/services/persona_policy.py`
   - 给 `sales_focus`、`value_axes`、`objection_axes`、`expected_customer_questions` 加了最小标准化。
   - 这些字段现在会统一做 trim / 去重，并在 persona policy 里稳定存在：`sales_focus` 默认空字符串，三个 list 字段默认空数组。
   - 现有 `system_prompt`、`knowledge_base_ids`、`tool_policy` 的兼容逻辑没动；未知扩展键仍然原样保留，避免把这条链过度 schema 化。

2. `backend/src/sales_bot/services/voice_instruction_compiler.py`
   - 在原来的“角色核心设定 / 行为准则 / 执行约束”之间新增了 `【销售追问焦点】` 编译段。
   - 如果 persona policy 带了 sales-focus 扩展字段，编译后的客户契约会明确要求：持续把话题拉回客户收益、商业价值和异议验证；当销售只说功能点或空泛承诺时，继续追问 ROI、预算、价格、竞品差异、实施风险和案例证据。
   - `expected_customer_questions` 现在会作为示例追问进入 base contract，同时继续保留“一轮最多一个问题句”和 KB lock / coach mode 规则。

3. `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
   - 没有新增新的 retrieval mode，而是扩展了现有 query 分类：价格 / ROI / 竞品 / 案例证据类问题现在走 widened entity-query path。
   - 这类 query 的默认检索参数会放宽到更适合销售异议场景的范围：更大的 `top_k`、更宽的 snippet、以及更高的 keyword candidate limit。
   - 这样 knowledge-check 和 runtime retrieval 仍只看既有 helper 输出，不会多出第二套语义。

测试侧我补了三组锁定：

- `backend/tests/unit/test_voice_instruction_compiler.py`
  - 锁住 sales-focus 字段如何进入 compiled base contract；断言价值翻译、客户收益、ROI、预算、价格、竞品、实施风险、案例证据和示例追问都真正进入指令文本。
- `backend/tests/unit/test_stepfun_knowledge_helpers.py`
  - 锁住价格 / 竞品 / 证据 query 会触发 widened retrieval params 和更长 snippet，而不是还停留在旧的 5/360 基线。
- `backend/tests/unit/test_voice_runtime_policy_service.py`
  - 锁住 effective policy 会返回标准化后的 sales-focus 字段，并把这些字段编译进最终 `instructions`；同时补了一个 snapshot stale 回归断言，避免冻结策略线对扩展字段变化视而不见。

## Verification

先跑 task plan 的三文件 backend suite，确认新断言在改实现前按预期失败；实现完成后同一组命令重新跑绿。

然后按任务计划再跑一遍 `-k 'sales or objection or kb'` 的 focused 子集，确认销售追问 / objection / KB 锁定断言都命中通过。

按 slice 级 gate 我还补跑了两条更大范围的检查：

- slice backend command 仍失败，但原因不是 T02 回归，而是 `tests/integration/test_sales_value_training_flow.py` 还不存在；这条 proof 明确属于 T03。
- slice web command 仍返回 0，但当前只实际跑到了已存在的 websocket/report 两个文件；`ScorePanel.test.tsx` 还没落地，因此它还不能证明 live score 面已经完成销售语义对齐，这同样是 T03 的范围。

另外我用仓库内直接脚本验证了本任务的 observability 信号：

- `normalize_persona_policy(...)` 会输出标准化后的 sales-focus 字段；
- `VoiceInstructionCompiler.compile_base_contract(...)` 会产出新的 `instruction_contract_hash`，并且指令正文确实包含“价值翻译”和 ROI 示例追问；
- `resolve_retrieval_params(...)` / `resolve_grounding_context_limits(...)` 对竞品+价格+证据 query 会返回 widened tuning（`top_k=7`、snippet 420、keyword limit 48）。

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p pytest tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_voice_runtime_policy_service.py` | 0 | ✅ pass | 9.67s |
| 2 | `cd backend && /usr/bin/time -p pytest tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_voice_runtime_policy_service.py -k 'sales or objection or kb'` | 0 | ✅ pass | 9.06s |
| 3 | `cd backend && /usr/bin/time -p pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py` | 4 | ❌ fail | 7.20s |
| 4 | `cd web && /usr/bin/time -p npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 1.31s |
| 5 | `cd backend && PYTHONPATH=src /usr/bin/time -p venv/bin/python - <<'PY' ...`（直接检查 normalized sales-focus policy / compiled contract / widened retrieval params） | 0 | ✅ pass | 0.64s |

## Diagnostics

后续 agent 可以用这些面快速确认本任务输出仍然成立：

- `backend/src/agent/services/persona_policy.py`
  - `sales_focus / value_axes / objection_axes / expected_customer_questions` 的标准化结果
  - 兼容字段与未知扩展键是否仍保留
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
  - `【销售追问焦点】` 是否仍被编译进 base contract
  - `instruction_contract_hash` 是否随 persona sales-focus 变化而变化
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
  - 竞品 / 价格 / 证据 query 的 `top_k / similarity_threshold / keyword_candidate_limit / snippet` 是否仍走 widened tuning
- `backend/tests/unit/test_voice_instruction_compiler.py`
  - 编译文本必须包含销售价值 / objection 语义与示例追问
- `backend/tests/unit/test_voice_runtime_policy_service.py`
  - effective policy 必须返回标准化后的 sales-focus 字段
  - snapshot stale 断言可帮助排查冻结策略线是否吃掉扩展字段变化

## Deviations

- 为了把“冻结策略线不会忽略 sales-focus 变化”也放进本任务的验证面，我在 `test_voice_runtime_policy_service.py` 里直接调用了 `StepFunRealtimeHandler._is_policy_snapshot_stale(...)` 做断言，而不是再扩一条额外的 handler test 文件。这是局部验证面的适配，不改变切片方向。

## Known Issues

- slice backend 验证仍会因为 `tests/integration/test_sales_value_training_flow.py` 缺失而失败；这条 integration proof 属于 T03，不是 T02 残留回归。
- slice web 验证当前仍只覆盖现有的 websocket/report 两个文件；`src/components/practice/ScorePanel.test.tsx` 还没创建，因此 live score 面的销售语义还没有被 focused web suite 真正锁住，这同样要等 T03。
- 本任务没有做真实绑定 KB 的 runtime/browser 验收；`/practice/sessions/{id}/knowledge-check` 的 query 状态、live score_update 和最终 report 语义，还要在 T03 完成消费面对齐后再做端到端 UAT。

## Files Created/Modified

- `backend/src/agent/services/persona_policy.py` — 给 sales-focus 扩展键加最小标准化，并继续保留未知扩展字段
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — 把 sales-focus/value_axes/objection_axes/expected_customer_questions 编译进客户 base contract
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — 扩大价格 / 竞品 / ROI 证据 query 的 retrieval tuning，但仍复用现有 helper 路径
- `backend/tests/unit/test_voice_instruction_compiler.py` — 锁住 sales-focus 字段如何进入 compiled contract
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — 锁住 objection query 的 widened retrieval params 和 snippet 策略
- `backend/tests/unit/test_voice_runtime_policy_service.py` — 锁住 effective policy 的 sales-focus 标准化与 snapshot stale 回归
- `.gsd/DECISIONS.md` — 追加 D025，记录 sales-focus persona 扩展与 retrieval tuning 继续沿用单一 authority line
- `.gsd/KNOWLEDGE.md` — 记录 objection query 现在走 widened entity-query path 的 gotcha
- `.gsd/milestones/M001/slices/S05/tasks/T02-SUMMARY.md` — 记录本任务实现与验证证据
