# Research: Phase 7 realtime runtime binding plan

- Query: Phase 7 realtime runtime binding for `sales_trainer`, including runtime binding/read-model plan, module boundaries, backend API/DTO/service/test checklist, pause conditions, and validation commands.
- Scope: internal
- Date: 2026-06-27

## Findings

### 1. 当前代码事实和证据路径

本次先读取了任务要求指定的项目规则与契约文档：`AGENTS.md`、`CLAUDE.md`、`docs/architecture.md`、`docs/api-contract/sales-trainer.md`、`.trellis/spec/backend/index.md`、`.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/prd.md`、`.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/audit-synthesis.md`。

使用 CodeGraph 先行探索了 `sales_trainer`、`sales_bot`、`training_runtime`、`practice_sessions` 的边界与调用链：

- `codegraph explore "sales_trainer realtime roleplay runtime_binding TrainingJourney ModuleOutcome PracticeSession training_runtime sales_bot boundaries"`
- `codegraph explore "PracticeSession creation api service runtime descriptor sales_bot websocket /api/v1/practice/sessions training_runtime dispatch_scenario_plugin"`
- `codegraph explore "sales_trainer permissions capabilities training-records ai_coach realtime_roleplay_session outcome projection"`
- `codegraph node backend/src/common/services/practice_session_service.py`
- `codegraph node backend/src/common/api/practice.py`
- `codegraph node backend/src/training_runtime/plugins.py`
- `codegraph node backend/src/sales_trainer/services/training_journey_service.py`
- `codegraph node backend/src/sales_trainer/services/training_record_service.py`
- `codegraph node backend/src/sales_trainer/schemas.py`

CodeGraph 索引对部分新增 `sales_trainer` 文件不完整，例如 `TrainingJourney` 相关 symbol 未被 `codegraph query` 命中；因此在 CodeGraph 定位边界后，补充使用 `rg`/`sed` 精读目标文件。以下结论以代码事实为准，不把文档愿景视为已实现事实。

#### Runtime/session/outcome 现状

- 实时对练运行时的当前权威入口是通用 practice session，而不是 `sales_trainer`：
  - `backend/src/common/api/practice.py:306` 暴露 `POST /practice/sessions` 创建会话。
  - `backend/src/common/api/practice.py:383` 暴露 `GET /practice/sessions/{session_id}/runtime-preflight`。
  - `backend/src/common/api/practice.py:158` 通过 `_can_read_session` 做 owner/admin 读取控制，后续多个 session endpoint 都复用该检查。
  - `backend/src/common/services/practice_session_service.py:162` 是 `PracticeSessionCreateService.create_session`。
  - `backend/src/common/services/practice_session_service.py:305` 强制 sales 新会话只能走 `stepfun_realtime`。
  - `backend/src/common/services/practice_session_service.py:500` 和 `:531` 创建 sales `PracticeSession`。
- sales realtime terminal outcome 目前已经会回写到 `PracticeSession` 分数字段，但只属于 runtime/session 层，不属于 `sales_trainer` TrainingJourney：
  - `backend/src/common/services/practice_session_service.py:862` `_apply_sales_realtime_score_snapshot_to_session` 将 realtime score snapshot 归一化后写回 `logic_score`、`accuracy_score`、`completeness_score`。
  - `backend/src/common/services/practice_session_service.py:889` `_sync_sales_realtime_terminal_evidence` 优先读 live handler 分数，其次读最后一条 message score snapshot。
  - `backend/src/sales_bot/services/practice_session_contributor.py:29` `finish_sales_practice_session` 在 sales terminal handler 中同步 terminal evidence，并在 `:88` 注册 sales terminal handler。
- `training_runtime` 当前只知道 `sales` 和 `presentation` 两类 scenario plugin：
  - `backend/src/training_runtime/plugins.py:99` 是 `SalesScenarioPlugin`。
  - `backend/src/training_runtime/plugins.py:221` 是 `PresentationScenarioPlugin`。
  - `backend/src/training_runtime/plugins.py:393`、`:394` 注册 sales/presentation。
  - `backend/src/training_runtime/plugins.py:406` 通过 descriptor 分发 plugin。
  - `backend/tests/unit/test_training_runtime_plugins.py:35` 断言 registry 只包含 presentation/sales。
  - `backend/tests/unit/test_training_runtime_plugins.py:138` 断言 sales websocket route 是 `/ws/sales/{session_id}`。
- `PracticeSession` 数据模型在 `backend/src/common/db/models.py` 中，包含 `session_id`、`user_id`、`scenario_id`、`agent_id`、`persona_id`、`voice_mode`、`voice_runtime_profile_id`、`voice_policy_snapshot`、`effectiveness_snapshot`、`practice_template_id`、`curriculum_snapshot`、`runtime_state`、`status`、三类 score 等字段。它是现有 realtime outcome 最现实的初始 read source。

#### `sales_trainer` 当前已有但尚未打通的部分

- `sales_trainer` 已有 realtime binding DTO：
  - `backend/src/sales_trainer/schemas.py:1171` `NewcomerRealtimeProviderReadinessSnapshot`。
  - `backend/src/sales_trainer/schemas.py:1182` `NewcomerRealtimePermissionPolicy`。
  - `backend/src/sales_trainer/schemas.py:1196` `NewcomerRealtimeFailurePolicy`。
  - `backend/src/sales_trainer/schemas.py:1215` `NewcomerRealtimeRollbackPolicy`。
  - `backend/src/sales_trainer/schemas.py:1223` `NewcomerRealtimeRuntimeBinding`。
  - `backend/src/sales_trainer/schemas.py:1245` `NewcomerPathModuleConfig`。
  - `backend/src/sales_trainer/schemas.py:1274` `runtime_binding` 字段。
  - `backend/src/sales_trainer/schemas.py:1300` 校验 `runtime_binding` 只能用于 `realtime_roleplay` module。
- path config 发布校验已有 realtime 分支，但校验较浅：
  - `backend/src/sales_trainer/services/path_config_service.py:917` 对 `realtime_roleplay` 调用 `_validate_realtime_roleplay_module`。
  - `backend/src/sales_trainer/services/path_config_service.py:1034` `_validate_realtime_roleplay_module`。
  - `backend/src/sales_trainer/services/path_config_service.py:1040` 要求 binding 存在。
  - `backend/src/sales_trainer/services/path_config_service.py:1051` 要求 provider readiness ready。
  - `backend/src/sales_trainer/services/path_config_service.py:1055` 禁止 `fallback_to_placeholder`。
  - 当前未看到它校验 `runtime_descriptor_id`、`practice_template_id`、真实 agent/persona/profile 是否存在，也未校验 outcome projection 已可用。
- active revision diff/hash 已把 runtime binding 计入稳定签名：
  - `backend/src/sales_trainer/services/path_config_models.py:278` `_module_refs` 纳入 `_stable_runtime_binding(module.runtime_binding)`。
  - `backend/src/sales_trainer/services/path_config_models.py:334` `_stable_runtime_binding`。
- TrainingJourney DTO 已能表达 realtime outcome，但 service 仍是 fail-closed 占位：
  - `backend/src/sales_trainer/schemas.py:2625` `TrainingJourneyModuleOutcome`。
  - `backend/src/sales_trainer/services/training_journey_service.py:89` `TrainingJourneyService`。
  - `backend/src/sales_trainer/services/training_journey_service.py:317` `_base_module`。
  - `backend/src/sales_trainer/services/training_journey_service.py:333` 识别 `module_type == "realtime_roleplay"`。
  - `backend/src/sales_trainer/services/training_journey_service.py:360` 即便 binding/provider ready，也返回 `[NEWCOMER_REALTIME_OUTCOME_MISSING]`，说明 outcome projection 尚未接入。
  - `backend/src/sales_trainer/services/training_journey_service.py:450` `_outcomes_for_active_revision` 当前采集 audio、quiz、business etiquette quiz、ai coach，未采集 realtime。
  - `backend/src/sales_trainer/services/training_journey_service.py:755` `_outcome_payload` 已可抽象生成 outcome payload。
  - `backend/src/sales_trainer/services/training_journey_service.py:931` `_kind_for_module_type` 已将 realtime module 映射为 realtime roleplay kind。
- TrainingRecordService 仍未接入 realtime：
  - `backend/src/sales_trainer/services/training_record_service.py:64` `get_record` 只分派 `audio_submission`、`quiz_attempt`、`ai_coach_session`。
  - `backend/src/sales_trainer/services/training_record_service.py:95` `_record_window` union 记录窗口。
  - `backend/src/sales_trainer/services/training_record_service.py:163`、`:189`、`:209` 三个 union branch 分别是 audio/quiz/ai coach。
  - `backend/src/sales_trainer/schemas.py:2715` `SalesTrainerTrainingRecordResponse.record_type` 仍只允许 `audio_submission`、`quiz_attempt`、`ai_coach_session`，不含 `realtime_roleplay_session`。

#### 现有边界与测试事实

- 架构文档和 `CLAUDE.md` 均要求 `presentation_coach`、`sales_bot`、`sales_trainer`、`curriculum_practice`、`training_runtime` 独立演进，跨域能力通过 `common/` 中转；`sales_trainer` 不应直接依赖 realtime runtime 内部实现。
- `backend/tests/unit/test_runtime_dependency_contract.py:154` 已禁止 `sales_trainer` import：
  - `sales_bot`
  - `training_runtime`
  - `common.api.practice`
  - `common.services.practice_service`
  - `common.services.practice_session_service`
  - `common.services.runtime_gate`
- `backend/tests/unit/test_newcomer_training_path_boundary.py:67` 还有更严格的历史边界测试，扫描 `backend/src/sales_trainer` 中的字符串并禁止出现 `PracticeSession`、`sales_bot`、`/practice/`。这会影响 Phase 7 的最小方案：即使架构允许经 `common/db/models.py` 只读 `PracticeSession`，该测试当前也会失败，必须先决策是继续通过 neutral adapter 隐藏 `PracticeSession`，还是更新测试为“禁止跨域 runtime/service import，但允许受控只读 projection”。

### 2. 最小可实现的 `sales_trainer` runtime binding/read-model 方案

目标不是让 `sales_trainer` 成为 realtime runtime owner，而是让它拥有“闭环中的绑定关系和结果投影”。

最小方案建议分两条窄链路实现：

1. Start binding：`sales_trainer` learner endpoint 只验证新人训练路径上下文和 binding，不直接构造 runtime 内部细节。
2. Outcome projection：`sales_trainer` read model 从受控 read source 读取已完成 runtime outcome，写入 TrainingJourney/TrainingRecord 响应，不从 WebSocket 前端连接状态推断完成。

#### 建议的后端 start binding 流程

新增一个 `sales_trainer` learner API，例如：

- `POST /api/v1/sales-trainer/realtime-roleplay/sessions`
- 或更明确的 module-scoped 形式：`POST /api/v1/sales-trainer/journey/modules/{module_key}/realtime-session`

请求最小字段：

- `path_key` 或当前 active path implicit。
- `module_key`。
- 可选 `idempotency_key`，用于重复点击/重试保护。

服务端必须做：

- 读取 active path revision，禁止 legacy/draft fallback。
- 校验 module 存在、enabled、`module_type == "realtime_roleplay"`。
- 校验 `runtime_binding` 存在，且 `binding_key`、`runtime_owner`、`scenario_key`、`provider_readiness_snapshot`、`permission_policy`、`failure_policy`、`rollback_policy` 满足契约。
- 校验 learner 是本人；manager/admin 只读，不默认代 learner 创建 runtime。
- 校验对象级权限：learner 必须属于该 path/revision 可见范围，且具备 learner realtime capability。
- 调用一个 neutral/common adapter 创建 runtime session，不能 import `sales_bot`、`training_runtime`、`common.api.practice`、`common.services.practice_session_service`。
- 将 sales_trainer binding context 写入创建出的 session 的 metadata/snapshot，至少包括：
  - `path_key`
  - `path_revision_id`
  - `path_revision_no`
  - `module_key`
  - `binding_key`
  - `runtime_descriptor_id`
  - `runtime_config_revision_id`
  - `roleplay_contract_revision_id`
  - `practice_template_id`
  - `created_by_sales_trainer_user_id`
- 返回 `session_id`、runtime preflight 结果、前端可跳转的 practice path 或 runtime descriptor，不返回可由前端篡改的 agent/persona/profile 组装参数。

#### neutral adapter 的位置选择

优先推荐新增 common 层窄接口，而不是让 `sales_trainer` 直接 import existing practice service：

- 建议：`backend/src/common/services/realtime_runtime_binding_service.py`
- 职责：根据 binding/config 创建 sales realtime `PracticeSession`，并提供只读 outcome projection DTO。
- `sales_trainer` 只依赖这个窄接口或其协议类型。
- 该 adapter 可以在 common 层调用 `PracticeSessionCreateService`/runtime gate/session read 逻辑，因为 common 层是运行时组装权威附近的位置。

如果为了最小改动选择让 `sales_trainer` 直接只读 `common.db.models.PracticeSession`，需要先修改 `backend/tests/unit/test_newcomer_training_path_boundary.py:67` 的历史禁止项，将“禁止出现 `PracticeSession` 字符串”收窄为“禁止 import runtime/service 创建能力，只允许受控只读 projection”。这个选择改动较小，但边界语义不如 neutral adapter 清晰。

#### 最小 read-model projection

`TrainingJourneyService` 增加 `_collect_realtime_outcomes`，数据来源应是以下二选一：

- 首选：common neutral adapter 返回 `RealtimeRoleplayOutcomeProjection`。
- 次选：只读查询 `PracticeSession`，过滤 `user_id`、`voice_mode == "stepfun_realtime"`、`status`、binding context 中的 path/module/revision 信息。

Projection 规则建议：

- `preparing`、`in_progress`、`paused`：只作为 runtime session 状态，不计入完成 outcome；Journey 可显示 pending/in_progress，但不能算通过。
- `completed` 或 runtime terminal 状态，且存在 score snapshot/effectiveness evidence：生成 `TrainingJourneyModuleOutcome(record_type="realtime_roleplay_session", snapshot_ref.type="runtime_outcome_snapshot")`。
- 没有 score/evidence 时，不伪造通过；保留 diagnostic，例如 `[NEWCOMER_REALTIME_OUTCOME_MISSING]`。
- failure 分类必须来自 runtime terminal evidence 或 binding failure policy，不能把 WebSocket 断开一律记为失败。
- 如果业务没有定义 realtime 通过阈值，第一期只应记录 `submitted/scored`，不要把“完成会话”等同于“通过考核”。需要产品/契约补充分数阈值后，才计算 pass/fail。

#### 最小 TrainingRecord 接入

`TrainingRecordService` 增加 `realtime_roleplay_session` 分支：

- `_record_window` union 增加 realtime branch，按 learner、created_at/end_time、active revision binding context 过滤。
- `get_record("realtime_roleplay_session", session_id)` 返回 session/outcome 详情。
- `SalesTrainerTrainingRecordResponse.record_type` 扩展为包含 `realtime_roleplay_session`。
- 响应中新增 `realtime_roleplay_session` payload 或复用通用 `snapshot` 字段，但需要 DTO 明确化，避免前端解析魔法字段。

### 3. 禁止直接跨域 import 的边界

Phase 7 不应让 `sales_trainer` 直接依赖 runtime 内部模块。禁止项应维持或增强：

- 禁止 `backend/src/sales_trainer/**` import `sales_bot.*`。
- 禁止 `backend/src/sales_trainer/**` import `training_runtime.*`。
- 禁止 `backend/src/sales_trainer/**` import `common.api.practice`。
- 禁止 `backend/src/sales_trainer/**` import `common.services.practice_session_service`。
- 禁止 `backend/src/sales_trainer/**` import `common.services.runtime_gate`。
- 禁止 `sales_trainer` 调用 sales WebSocket handler、live handler、score arbiter、prompt/runtime plugin 内部函数。
- 禁止从前端 `/practice/[sessionId]` 连接状态、WebSocket reconnect 状态推断 TrainingJourney 完成。
- 禁止创建无 active revision、无 binding context、无对象级权限快照的 `PracticeSession`。

可接受边界：

- `sales_trainer` 保留自己的 path/revision/permission/TrainingJourney 权威。
- runtime 创建和 preflight 仍归 common practice/runtime 权威。
- 跨域只通过 common 层 narrow adapter、common DTO、或 `common/db/models.py` 的受控只读 projection。若选择 `PracticeSession` 只读 projection，必须同步更新边界测试并写清楚受控例外。

### 4. 后端 API/DTO/服务/测试清单

#### API 清单

- 新增 learner start API：
  - `POST /api/v1/sales-trainer/journey/modules/{module_key}/realtime-session`
  - 成功返回 `session_id`、`practice_url` 或 runtime descriptor、runtime preflight payload、`path_revision_id`、`module_key`、binding snapshot。
  - 错误必须 fail-closed：active revision missing、module missing、binding invalid、provider not ready、permission denied、runtime creation failed。
- 可选新增 learner outcome API：
  - `GET /api/v1/sales-trainer/realtime-roleplay/sessions/{session_id}/outcome`
  - 若 TrainingJourney/TrainingRecord 已覆盖，可后移。
- 管理端不需要单独创建 endpoint；现有 journey/admin training record 读模型扩展后应能看到 outcome。

#### DTO 清单

- 复用并强化：
  - `NewcomerRealtimeRuntimeBinding`
  - `NewcomerRealtimeProviderReadinessSnapshot`
  - `NewcomerRealtimePermissionPolicy`
  - `NewcomerRealtimeFailurePolicy`
  - `NewcomerRealtimeRollbackPolicy`
  - `TrainingJourneyModuleOutcome`
- 新增或扩展：
  - `SalesTrainerRealtimeSessionCreateRequest`
  - `SalesTrainerRealtimeSessionCreateResponse`
  - `SalesTrainerRealtimeOutcomeProjection`
  - `SalesTrainerTrainingRecordResponse.record_type` 增加 `realtime_roleplay_session`
  - `SalesTrainerTrainingRecordResponse.realtime_roleplay_session` payload

#### Service 清单

- `sales_trainer`：
  - `RealtimeRuntimeBindingService` 或 module service：验证 active revision、module、binding、权限和幂等。
  - `TrainingJourneyService._collect_realtime_outcomes`。
  - `TrainingRecordService` 增加 realtime window/detail serializer。
  - `PathConfigService._validate_realtime_roleplay_module` 增加 descriptor/template/config revision 可验证性。
  - 操作日志：learner start realtime session、runtime binding invalid、provider not ready、outcome projection failure。
- `common`：
  - 建议新增 narrow adapter：`RealtimeRuntimeBindingRuntimeService` 或类似名称。
  - 负责从 binding 创建/读取 runtime session，不向 `sales_trainer` 暴露 `sales_bot`/`training_runtime` 内部。
  - 可复用现有 `PracticeSessionCreateService`、runtime preflight、terminal evidence 逻辑。

#### 测试清单

- Boundary tests：
  - 保持 `sales_trainer` 不 import `sales_bot`、`training_runtime`、practice API、practice session service、runtime gate。
  - 若允许 `PracticeSession` 只读 projection，更新 `test_newcomer_training_path_boundary.py` 为明确例外；否则通过 common adapter 避免例外。
- Path config tests：
  - binding missing -> `[NEWCOMER_REALTIME_BINDING_INVALID]`。
  - provider not ready -> `[NEWCOMER_REALTIME_PROVIDER_NOT_READY]`。
  - fallback_to_placeholder true -> invalid。
  - descriptor/template/config revision 不存在或不匹配 -> invalid。
- API tests：
  - learner 创建自己的 realtime session 成功。
  - manager/admin 默认不能代 learner 创建。
  - 非本人、无 path 权限、module disabled、active revision missing 均 fail-closed。
  - 重复提交/idempotency 不创建重复 session。
- Journey tests：
  - binding ready 但无 outcome -> 保持 `[NEWCOMER_REALTIME_OUTCOME_MISSING]`。
  - completed session + score snapshot -> 生成 `realtime_roleplay_session` outcome。
  - failed terminal evidence -> 生成分类 failure，不计为通过。
- TrainingRecord tests：
  - record window 包含 realtime outcome。
  - `get_record("realtime_roleplay_session", session_id)` 权限正确。
  - admin/team scope 与现有 audio/quiz/ai coach 一致。
- Runtime contract tests：
  - 不新增 newcomer scenario plugin，除非 ADR 明确改变运行时模型。
  - sales runtime 仍走 `scenario_type="sales"`、`/ws/sales/{session_id}`、StepFun Realtime。

### 5. 暂停条件

以下任一条件未满足时，不建议继续实现 learner-facing realtime 入口：

- 没有明确 ADR 或任务决策确认：`sales_trainer` 只拥有 binding/read-model，不成为 realtime runtime owner。
- binding 无法确定性映射到现有 sales runtime 创建参数，例如缺少有效 `practice_template_id`、agent、persona、voice runtime profile、runtime config revision。
- provider readiness 没有机器可读来源，或 readiness snapshot 只是人工文案。
- realtime outcome 的完成/通过语义未定义。尤其不能默认“会话 completed = 新人训练通过”。
- 边界测试策略未确认：到底通过 common neutral adapter 隔离 `PracticeSession`，还是允许 `sales_trainer` 只读 `common.db.models.PracticeSession`。
- 对象级权限和 active revision snapshot 无法写入 runtime session metadata。
- 不能在失败时区分 terminal/transient/voluntary，而只能看到 WebSocket 断开。
- 缺少审计方案：谁启动、对应哪个 path revision/module/binding、失败原因是什么。
- 实现需要新增 `training_runtime` newcomer plugin 或让 `sales_trainer` import `training_runtime`，但尚未有 ADR 授权。

### 6. 推荐验证命令

研究阶段未执行测试。Phase 7 实现后建议至少执行：

```bash
cd backend && pytest tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_runtime_dependency_contract.py
```

```bash
cd backend && pytest tests/integration/test_newcomer_training_journey_api.py
```

```bash
cd backend && pytest tests/unit/test_training_runtime_plugins.py tests/unit/test_runtime_preflight_service.py
```

```bash
cd backend && pytest tests/contract/test_sessions.py
```

新增测试后还应执行：

```bash
cd backend && pytest tests/unit/test_sales_trainer_realtime_binding.py tests/integration/test_sales_trainer_realtime_journey.py
```

静态检查建议：

```bash
cd backend && ruff check src tests
```

如实现选择新增 outcome 表或 session binding 表，再执行：

```bash
cd backend && alembic upgrade head
```

## Caveats / Not Found

- CodeGraph 对部分新增 `sales_trainer` read-model 文件索引不完整；已用 `rg`/`sed` 补充确认，结论以实际文件为准。
- 未发现 `sales_trainer` 已实现真正的 realtime session start API。
- 未发现 `sales_trainer` 已实现 `realtime_roleplay_session` TrainingRecord 分支。
- 未发现 `TrainingJourneyService` 已把 completed realtime `PracticeSession` 投影为 journey outcome；当前实现对 ready binding 仍返回 `[NEWCOMER_REALTIME_OUTCOME_MISSING]`。
- 未确认现有 binding 中 `runtime_descriptor_id`、`practice_template_id`、`runtime_config_revision_id` 已能映射到真实 runtime 创建参数；Phase 7 实现前必须补校验或暂停。
- 本文件为只读研究产物，未修改业务代码、测试、迁移，也未运行测试。
