# TODO 0 Evidence: realtime-it-leader-roleplay-v1

## Scope

- Workdir: `/Users/zhaozengqing/github/销售训练qoder`
- Verified docs only:
  - `.trellis/tasks/06-23-15-v1/prd.md`
  - `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md`
- No PRD, design, or product code edits were made.

## 1. Forbidden Phrase Absence

Command:

```sh
bash -lc 'grep -R "本次任务仍只补文档边界" .trellis/tasks/06-23-15-v1/prd.md docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md; test $? -ne 0'
```

Output:

```text

```

Exit code: `0`

Binary observable: no matching forbidden phrase was printed, and the command succeeded because `grep` returned non-zero before `test $? -ne 0`.

## 2. Required Boundary Terms Present

Command:

```sh
grep -n "平台直练\|sales_trainer\|PracticeTemplate\|roleplay_contract_hash\|state_card_version\|9 段" .trellis/tasks/06-23-15-v1/prd.md docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md
```

Output:

```text
.trellis/tasks/06-23-15-v1/prd.md:21:- v1 入口轨道选择平台直练 `/practice/[sessionId]`，通过 `VoiceRuntimePolicyService` / `voice_policy_snapshot` / StepFun realtime 路径开练；不要接入 `sales_trainer` 新人训练路径中的 realtime 占位，也不要通过 `PracticeTemplate` 课程闭环开练。
.trellis/tasks/06-23-15-v1/prd.md:36:- 观测字段至少记录 `roleplay_contract_hash`、`state_card_version`、`violation_count`、`blocking_violation_count`、`knowledge_timeout_count`、`scoring_confidence`、`quality_flags`。
.trellis/tasks/06-23-15-v1/prd.md:37:- 至少设计 9 段评分回归样本结构，用于后续验证 prompt、模型和知识库调整后的评分稳定性。样本按优秀、普通、较差各 3 段组织，覆盖开场、现状澄清、风险识别、价值说明、可信度回应、下一步推进、隐藏信息防泄漏、知识缺失降级、评分证据绑定；本 PRD 只定义结构，不写完整 transcript。
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:53:v1 入口选择平台直练 `/practice/[sessionId]`：
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:57:- 不接入 `sales_trainer` 新人训练路径中的 realtime 占位。
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:58:- 不通过 `PracticeTemplate` 课程闭环开练。
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:60:该选择用于避免同时引入新人训练路径、课程模板闭环和平台直练三套入口语义。v1 只验证固定样板的实时客户对练能力，后续是否纳入课程闭环应另行设计。
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:82:每次会话必须冻结 `roleplay_contract`，并记录 `roleplay_contract_hash`、revision refs 和生成来源。runtime 禁止 fallback 到 latest assets；配置发布或回滚只影响未来会话，不改变已开始或已完成会话的合同。v1 入口必须可通过配置或 feature flag 关闭。
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:154:| `roleplay_contract_hash` | 确认本次会话使用的冻结角色合同 |
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:155:| `state_card_version` | 排查状态卡乱序、失败和重连恢复 |
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:245:v1 至少准备 9 段评分回归样本结构，不需要在本设计里写完整 transcript。样本按质量分层：
docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md:253:9 段样本合计必须覆盖：开场、现状澄清、风险识别、价值说明、可信度回应、下一步推进、隐藏信息防泄漏、知识缺失降级、评分证据绑定。
```

Exit code: `0`

Binary observable: required boundary terms are present in the verified docs.

## 3. PRD Requirements Slice

Command:

```sh
sed -n '15,60p' .trellis/tasks/06-23-15-v1/prd.md
```

Output:

```text
- 当前系统已有实时语音、Persona、知识库、评分、训练路径、快照等基础概念，v1 应优先收敛和复用。

## Requirements

- 本 PRD 及对应设计文档现在作为后续 v1 implementation scope 的实现依据，不再保留“当前不进入实现阶段，因此不修改代码”的约束；后续实现应按本 PRD/设计拆分最小任务推进。
- 提供一个固定 v1 训练模板：信息化负责人 / 首次拜访 / 石犀平台 / 12-15 分钟。
- v1 入口轨道选择平台直练 `/practice/[sessionId]`，通过 `VoiceRuntimePolicyService` / `voice_policy_snapshot` / StepFun realtime 路径开练；不要接入 `sales_trainer` 新人训练路径中的 realtime 占位，也不要通过 `PracticeTemplate` 课程闭环开练。
- 开练时冻结 `roleplay_contract`，包含客户身份、场景、训练目标、可见知识、隐藏知识、行为规则和禁止行为。
- `roleplay_contract` 必须记录 hash 和 revision refs，runtime 只消费本次冻结快照；禁止 runtime fallback 到 latest assets。发布或回滚只影响未来会话，v1 入口必须能通过配置或 feature flag 关闭。
- 使用轻量 `session_state_card` 管理阶段、客户态度、已确认事实、学员完成动作、缺失动作、已提出异议和下一轮压力。
- 训练分四阶段：开场与来意、现状澄清、方案可信度、下一步推进。四阶段是 roleplay phase/view，不是新的 `SalesStageCapability` stage 枚举，不新增第三套销售 stage。
- 异步状态卡更新必须带 version 或 sequence，乱序更新丢弃；更新失败时保留上一版。重连时从 persisted snapshot / runtime_state 恢复当前合同、阶段、状态卡和必要事实。
- 阶段推进采用半自动策略：默认按时间推进，但可根据学员关键动作完成情况延迟或加压。
- 知识库分为客户背景 KB、产品事实 KB、评分教练 KB，严格区分 AI 客户可见与不可见内容。
- 产品事实缺失或检索超时时，AI 客户应自然追问或表达“需要你们给出可验证材料/PoC 指标”，不得臆测产品能力；同时记录 quality flag。
- 实时语音热路径只放短角色锚点、当前状态卡、最近几轮对话和必要事实。
- 状态卡更新、知识预取、角色漂移检查走旁路异步，不阻塞实时语音。
- 评分采用离线大模型评分 + 规则校验 + 原话证据。v1 使用 6 项 100 分 business rubric 作为版本化 scoring ruleset / report projection；不得破坏现有架构文档里的 5 个教练维度，必要时保留映射说明：6 项用于本样板报告，5 维若存在则作为现有 evaluation 兼容层。
- 提供学员反馈视图和管理员质检视图。
- 管理员视图必须能区分学员能力问题和 AI 角色质量问题。
- 权限默认 fail-closed：learner 只能看总分、分项、建议、学员原话证据；admin/supervisor 可看完整转写、评分 JSON、状态卡、角色合同 hash、AI 质量检查；ops 只能看脱敏日志和指标。
- 观测字段至少记录 `roleplay_contract_hash`、`state_card_version`、`violation_count`、`blocking_violation_count`、`knowledge_timeout_count`、`scoring_confidence`、`quality_flags`。
- 至少设计 9 段评分回归样本结构，用于后续验证 prompt、模型和知识库调整后的评分稳定性。样本按优秀、普通、较差各 3 段组织，覆盖开场、现状澄清、风险识别、价值说明、可信度回应、下一步推进、隐藏信息防泄漏、知识缺失降级、评分证据绑定；本 PRD 只定义结构，不写完整 transcript。

## Acceptance Criteria

- [ ] 设计文档明确 v1 目标、用户画像、训练流程、技术架构、评分体系和暂不做范围。
- [ ] 角色合同样板明确可见知识、隐藏知识、行为规则和禁止行为。
- [ ] 状态卡样板覆盖阶段、态度、事实、动作、异议和下一轮压力。
- [ ] 知识库接入方案明确哪些知识可以给 AI 客户看，哪些只能给评分器或管理员看。
- [ ] 评分方案明确谁评分、怎么评分、如何绑定原话证据、如何规则校验、何时人工复核。
- [ ] 报告方案区分学员反馈视图和管理员质检视图。
- [ ] v1 明确不做多行业自由配置、长期客户记忆、实时教练打断、模型微调和复杂后台配置中心。
- [ ] 后续实现前能基于本 PRD 拆分出最小实现任务。

## Definition of Done

- 方案文档写入 `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md`。
- Trellis 任务 PRD 写入 `.trellis/tasks/06-23-15-v1/prd.md`。
- 方案保持 v1 收敛，没有把长期客户关系、多角色组织博弈、复杂后台配置中心提前纳入 MVP。
- 后续实现基于本 PRD/设计推进，并在实现任务中补充代码级影响面、测试计划、发布与回滚策略。

## Technical Approach

v1 采用热路径、旁路和离线三层架构：
```

Exit code: `0`

## 4. Git Status Before Evidence File Creation

Command:

```sh
git status --short .trellis/tasks/06-23-15-v1/prd.md docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md .omo/evidence/task-0-realtime-it-leader-roleplay-v1.md
```

Output:

```text
?? .trellis/tasks/06-23-15-v1/prd.md
?? docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md
```

Exit code: `0`

Binary observable: the PRD and design docs were already untracked before this evidence file was created; this pass did not edit them.

## 5. Backend Implementation Targets

- `backend/src/sales_bot/services/voice_runtime_policy.py::VoiceRuntimePolicyService._compile_direct_practice_roleplay_contract`
- `backend/src/sales_bot/services/voice_runtime_policy.py::VoiceRuntimePolicyService.build_stepfun_tools`
- `backend/src/sales_bot/services/voice_instruction_compiler.py::VoiceInstructionCompiler`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py::StepFunRealtimeHandler`
- `backend/src/sales_bot/websocket/stepfun_realtime_policy.py` for effective policy / `voice_policy_snapshot` resolution and stale snapshot checks.
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py::_tool_search_internal_knowledge`
- `backend/src/sales_bot/websocket/components/stepfun_tool_helpers.py::build_stepfun_tools_from_policy`
- `backend/src/common/knowledge/internal_searcher.py::search_internal_knowledge`

CodeGraph / repo-search command used to confirm exact symbols:

```sh
rg -n "class VoiceRuntimePolicyService|def _compile_direct_practice_roleplay_contract|class VoiceInstructionCompiler|class StepFunRealtimeHandler|def search_internal_knowledge|def build_stepfun_tools" backend/src backend/tests
```

Output:

```text
backend/src/sales_bot/services/voice_instruction_compiler.py:68:class VoiceInstructionCompiler:
backend/src/sales_bot/services/voice_runtime_policy.py:309:class VoiceRuntimePolicyService:
backend/src/sales_bot/services/voice_runtime_policy.py:950:    def _compile_direct_practice_roleplay_contract(
backend/src/sales_bot/services/voice_runtime_policy.py:980:    def build_stepfun_tools(
backend/src/sales_bot/websocket/stepfun_realtime_handler.py:1158:class StepFunRealtimeHandler(
backend/src/sales_bot/websocket/components/stepfun_tool_helpers.py:8:def build_stepfun_tools_from_policy(
backend/src/common/knowledge/internal_searcher.py:37:async def search_internal_knowledge(
```

Likely existing test files:

- `backend/tests/unit/test_voice_runtime_policy_service.py`
- `backend/tests/unit/test_voice_instruction_compiler.py`
- `backend/tests/unit/prompt_templates/test_instruction_hash_contract.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`
- `backend/tests/unit/test_stepfun_tool_helpers.py`
- `backend/tests/unit/test_stepfun_realtime_upstream.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

Likely new focused test files for later TODOs:

- `backend/tests/unit/test_it_leader_roleplay_v1_assets.py`
- `backend/tests/unit/test_roleplay_state_card.py`
- `backend/tests/unit/test_it_leader_roleplay_scoring.py`
- `backend/tests/unit/test_it_leader_roleplay_report_projection.py`
- `backend/tests/unit/test_it_leader_roleplay_v1_regression.py`

## 6. Forbidden Surfaces

- `sales_trainer` realtime
- `PracticeTemplate` course flow
- new WebSocket runtime

## 7. Adversarial Classes

- `stale_state`: applicable. The evidence uses current command outputs from the two scoped docs and records exact paths.
- `dirty_worktree`: applicable. `git status --short` shows the scoped PRD and design docs were already untracked; this pass only adds the evidence artifact.
- `misleading_success_output`: applicable. The forbidden phrase command is treated as successful only because the final `test $? -ne 0` returned exit code `0`; empty stdout alone is not the claim.
- `prompt_injection`: not applicable. No untrusted external content was used beyond project docs/plans and local CodeGraph/repo search.
- `malformed input`: not applicable. No parser or input handling was added.
- `cancel/resume`: not applicable. This is a short one-shot docs/evidence task.
- `hung commands`: not applicable. Commands were bounded grep/sed/CodeGraph/rg/status checks.
- `flaky tests`: not applicable. No tests were run because no product code changed.
- `repeated interruptions`: not applicable. No interruption occurred.

## 8. Cleanup Receipt

- No long-running resources created.
- No background processes started.
- No temporary files created.
- No PRD/design/product code edits made by this pass.
- `.omo/plans/realtime-it-leader-roleplay-v1.md` TODO 0 is verified/restored as unchecked (`- [ ]`) per task boundary.
- Captured artifact path: `/Users/zhaozengqing/github/销售训练qoder/.omo/evidence/task-0-realtime-it-leader-roleplay-v1.md`

## 9. Git Status After Evidence File Creation

Command:

```sh
git status --short .trellis/tasks/06-23-15-v1/prd.md docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md .omo/evidence/task-0-realtime-it-leader-roleplay-v1.md
```

Output:

```text
?? .omo/evidence/task-0-realtime-it-leader-roleplay-v1.md
?? .trellis/tasks/06-23-15-v1/prd.md
?? docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md
```

Exit code: `0`

Binary observable: this pass created the evidence artifact; the scoped PRD and design docs remain untracked and were not edited by this pass.
