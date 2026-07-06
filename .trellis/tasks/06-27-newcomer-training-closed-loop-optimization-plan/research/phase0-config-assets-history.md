# Phase 0 子代理 E 报告：配置治理、内容资产、历史回放

日期：2026-06-27

范围：`sales_trainer` 路径配置、AI Coach Prompt 绑定与运行时校验、发布影响预览、`fallback_applied/fallback_reason`、provider readiness、Prompt/资产快照与历史回放、资产归档保护、legacy/dead data 诊断。

约束：只读分析；未修改业务代码、未提交 migration、未操作真实数据。

---

## 0. 本次核对依据

已读必需文档：

- `AGENTS.md`
- `CLAUDE.md`
- `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/audit-synthesis.md`
- `docs/api-contract/sales-trainer.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/business-rule-configs.md`

优先使用 CodeGraph CLI 的查询/节点：

- `path_config_service validate publish payload`
- `AI Coach prompt config`
- `material_service archive file access`
- `audio score prompt snapshot`
- `fallback_applied`
- `provider readiness`
- `dead data`
- `asset revision`

---

## 1. 当前配置 / 资产 / 快照代码事实

### 1.1 路径配置治理当前事实

1. `backend/src/sales_trainer/schemas.py`
   - `NewcomerPathConfigPayload` 只有字段定义：`path_key/title/goal_title/description/enabled/modules`。
   - `NewcomerPathModuleConfig` 的 `@model_validator` 只校验：
     - `learning_units` 数量与 `unit_key` 去重
     - `duration_options` 数量、`option_key` 去重、`target_unit_id` 去重
   - **没有**在 schema 层校验：
     - 路径内 `module_key` 唯一
     - 路径内 `order_index` 唯一
     - `path_key` 是否只能是 canonical/alias
     - 顶层 `enabled` 的真实生效语义
     - `completion_rule` 与 `module_type` 的组合约束

2. `backend/src/sales_trainer/services/path_config_service.py#get_config`
   - 若存在 active revision，读取 revision payload。
   - 若不存在 active revision，直接 `_backfill_payload()` 从旧 `Unit.config.path` 反推路径，返回：
     - `source="unit_backfill"`
     - `fallback_reason="active_revision_missing"`
     - `legacy_snapshot_only=true`
   - 这说明 learner/admin 仍允许走 legacy fallback。

3. `path_config_service.py#save_config`
   - 保存时仅 `NewcomerPathConfigPayload.model_validate(...)` 后写 working revision。
   - 没有额外 path-wide 结构校验。

4. `path_config_service.py#publish_config`
   - 发布前会走 `_validate_publish_payload(...)`。
   - 该校验只做“发布时引用完整性”检查，不做“整份 payload 治理一致性”检查。

5. `path_config_service.py#_validate_publish_payload`
   - 对启用模块只检查：
     - `audio_scoring`：已发布 audio unit + 已发布评分 prompt + 已发布材料
     - `audio_scoring_group`：duration option 存在，且每个 target unit 可发布
     - `article_exam`：已发布 learning content + published paper
     - `realtime_placeholder`：必须 disabled，且只能绑已发布占位 unit
   - **没有**检查：
     - `module_key` 重复
     - `order_index` 重复
     - `path_key` alias 写入限制
     - 顶层 `enabled=false` 时整条路径如何 fail-closed
     - `realtime_placeholder` 的 canonical `module_key`

6. `path_config_service.py#rollback_preview`
   - 只有回滚预览，返回 `impact_scope.future_learner_paths_changed` 等字段。
   - **不存在**路径配置发布 impact preview。

7. `path_config_service.py#_diagnostics`
   - 暴露了治理诊断、权限策略、回滚 preview endpoint。
   - `high_risk_actions` 里只有 publish/rollback/regrade。
   - **没有** publish preview endpoint。

8. `backend/src/sales_trainer/services/path_config_models.py`
   - canonical/legacy module key 映射存在：
     - `ppt_explain -> ppt_explanation`
     - `pyramid_speech -> elevator_pitch`
     - `realtime_placeholder -> realtime_roleplay_placeholder`
   - 但 `NewcomerPathModuleConfig` 自身没有把 legacy key 规范化。
   - `path_config_service._backfill_audio_group_options()` 仍在兼容 `pyramid_speech`。

9. 顶层 `enabled` 目前基本是“保存并透传”字段：
   - 会被 `save_config`/`article_binding_service` 保留；
   - 但 `active_projection()`、`_projection_items()`、`resolve_for_unit()` 等核心读取路径并不使用它来屏蔽整条路径。
   - 现状更像“伪配置”。

### 1.2 AI Coach 配置与 Prompt 校验当前事实

1. `backend/src/sales_trainer/schemas.py#AiCoachConfig`
   - `prompt_template_id` / `scoring_prompt_template_id` 只校验 UUID 形状。
   - `short_answer` 时强制 `scoring_prompt_template_id` 必填。
   - `prompt_contract_hash` / `scoring_contract_hash` 会在 schema `before` 阶段被强制清空为 `None`。

2. `backend/src/sales_trainer/ai_coach_admin_api.py#get_ai_coach_config`
   - 从路径配置读取模块 `ai_coach`。
   - 若路径 payload 校验失败或模块读取异常，直接 `except Exception: pass`。
   - 最终无论异常还是缺配置，都返回 `AiCoachConfig()` 默认值。
   - 这是标准 **fail-open GET**。

3. `ai_coach_admin_api.py#save_ai_coach_config`
   - 有字段级 RBAC。
   - 会把 `prompt_contract_hash/scoring_contract_hash` 重置为 `None`。
   - 但对 Prompt 绑定只做：
     - UUID 形状校验（来自 `AiCoachConfig`）
     - 是否触发 `manage_prompts` 权限
   - **没有**在保存前校验：
     - PromptTemplate 是否存在
     - 是否已发布/可用
     - `prompt_type` 是否匹配 generation/scoring
     - `business_purpose` 是否匹配 AI Coach

4. `ai_coach_admin_api.py#publish_ai_coach_config`
   - 复用路径配置发布。
   - 只额外检查“高风险字段 diff 是否需要 `manage_prompts` 权限”。
   - **没有**独立做 Prompt 可用性/用途校验。

5. `backend/src/sales_trainer/services/ai_coach_chat_runtime.py`
   - `module_ai_coach_config(...)`：路径 payload 非法时返回 `[AI_COACH_NOT_CONFIGURED]`。
   - `validate_chat_config(...)`：只检查 `enabled/chat_enabled/prompt_template_id` 是否存在。
   - 不检查 Prompt 是否真实存在。

6. `backend/src/sales_trainer/services/ai_coach_session_service.py`
   - `create_session` / `create_session_v1`：
     - 从当前路径读取 `ai_coach_config`
     - `config_snapshot = ai_coach_config.model_dump(...)`
     - session 表只单独存：
       - `prompt_template_id`
       - `prompt_revision_id`
       - `prompt_contract_hash`
     - scoring prompt 相关 revision/hash 仅留在 `config_snapshot` JSON 内，不是单独列。
   - 这意味着 AI Coach generation 与 scoring 的快照粒度不一致。

7. `backend/src/sales_trainer/services/prompt_template_revision_resolver.py`
   - 没有第一类 `PromptTemplateRevision` 表。
   - revision 解析靠：
     - 当前 head
     - `SystemLog(action="prompt_template.governance_migrate")` 的 `before` 快照重建
   - `resolve(...)` 在 revision 无法命中时会返回 `RESULT_HEAD_USED_AS_FALLBACK`。

8. `ai_coach_session_service.py#generate_interaction`
   - runtime 侧已做 fail-closed：
     - resolver 非 `RESULT_OK` 时直接拒绝生成
     - `RESULT_AUDIT_HISTORY_UNAVAILABLE -> [AI_COACH_PROMPT_REVISION_AUDIT_MISSING]`
     - 其他 fallback -> `[AI_COACH_PROMPT_REVISION_FALLBACK]`
   - 说明前置治理缺口被推迟到运行时才暴露。

9. `ai_coach_session_service.py#score_short_answer`
   - scoring prompt 必须存在；
   - revision 解析非 `RESULT_OK` 直接 `Result.fail("[AI_COACH_SCORING_PROMPT_REVISION_UNRESOLVED:*]")`；
   - 也就是说 scoring runtime 同样 fail-closed，但仍然是“运行时发现配置坏了”。

### 1.3 fallback_applied / fallback_reason 当前事实

1. `backend/src/sales_trainer/services/phase2_policy.py`
   - 已完整实现：
     - `source`
     - `fallback_applied`
     - `fallback_reason`
     - `config_id/config_version/status`
   - 缺失/disabled/db=None 都会给机器可读 fallback 诊断。

2. `backend/src/common/business_rules/service.py`
   - `resolve_active_config(...)` 已支持：
     - `database`
     - `database_previous`
     - `database_disabled`
     - `default`
     - `fallback_reason`

3. 路径配置 `get_config()`
   - 只有 `fallback_reason`，没有 `fallback_applied`。
   - 且只能表达 `active_revision_missing`，不能表达更多治理状态。

4. AI Coach 配置 GET
   - 没有 `fallback_applied/fallback_reason`。
   - 当前是直接吞异常回默认值。

5. learner 路径投影中的文案 fallback
   - 契约要求“缺失使用默认值时必须标明 `fallback_applied=true`”；
   - 当前路径模块 DTO / `path_projection_payloads` 没有对应统一治理字段。

### 1.4 provider readiness 当前事实

1. `backend/src/sales_trainer/api.py#_sales_trainer_settings_payload`
   - 只返回布尔或简单 env 投影：
     - `storage_backend`
     - `direct_upload_supported`
     - `cos_configured/oss_configured`
     - `asr_mode/asr_model`
     - `dashscope_configured`
     - `deucate_configured`
     - `deucate_model`
   - **没有**：
     - provider source（db/env/default）
     - readiness status enum
     - invalid_reason
     - fallback chain / effective config snapshot

2. `backend/src/sales_trainer/services/transcription_service.py`
   - `SALES_TRAINER_ASR_MODE` / remote timeout 直接读 env。
   - 非法配置通过异常码暴露，但没有集中 readiness 视图。

3. `backend/src/sales_trainer/services/deucate_scoring_service.py`
   - `DEUCATE_BASE_URL/API_KEY/MODEL/TIMEOUT_SECONDS` 全部直接读 env。
   - timeout 非法会变成 `[DEUCATE_CONFIG_INVALID]`，但不会出现在统一 provider 健康快照中。

4. `backend/src/sales_trainer/services/ai_coach_model_config.py`
   - AI Coach generation/scoring model 不是 env，而是从 `ConfigManager.get_all_configs(ModelType.LLM)` 找 model_name。
   - 但 settings/readiness API 没有把这部分 readiness 汇总出来。

### 1.5 音频评分 Prompt 快照 / revision 当前事实

1. `backend/src/sales_trainer/services/prompt_revision_service.py`
   - 音频评分 Prompt 已有 asset revision 治理：
     - working revision
     - publish working revision
     - initial published revision

2. `backend/src/sales_trainer/services/prompt_revision_payloads.py`
   - published revision payload 包含：
     - `prompt_id/name/purpose/system_prompt/scoring_template/output_schema/learner_rubric/version/status`

3. `backend/src/sales_trainer/services/material_service.py#resolve_score_scheme`
   - learner/submission 冻结的 `score_scheme_snapshot` 只有：
     - `prompt_id`
     - `name`
     - `purpose`
     - `version`
     - `status`
     - `learner_rubric`
     - `pass_threshold`
   - **没有**：
     - `revision_id/revision_no`
     - `system_prompt/scoring_template/output_schema`
     - `payload_hash`

4. `backend/src/sales_trainer/services/audio_submission_service.py#_score`
   - 首次评分时优先从 `score_scheme_snapshot.prompt_id` 取 prompt id；
   - 然后重新 `db.get(SalesTrainerAudioScorePrompt, prompt_id)` 读取**当前行**；
   - 再用当前 `prompt.system_prompt/scoring_template` 实际评分。
   - 这意味着：
     - 历史 submission 虽然冻结了 `prompt_id/version/hash`，但**首次评分并未按 frozen revision/payload 执行**。

5. `backend/src/sales_trainer/services/deucate_scoring_service.py#score_audio`
   - `prompt_hash` 来源于当前 `prompt.system_prompt + rendered_prompt`。
   - `SalesTrainerAudioScoreResult` 最终只落：
     - `prompt_id`
     - `prompt_version`
     - `prompt_hash`
   - 不落 `prompt_revision_id`。

6. `backend/src/sales_trainer/services/audio_regrade_calculator.py`
   - 历史重评已能从 `SalesTrainerAssetRevision` 恢复完整 prompt payload；
   - 说明“重评路径”比“首次评分路径”更接近 revision-first。

### 1.6 材料归档与历史回放当前事实

1. `backend/src/sales_trainer/services/material_publish_workflow.py`
   - 发布新版本时：
     - 旧 published 版本会自动 `archived`
     - `material.current_version_id` 指向新版本
   - 这是“唯一最新版”模型。

2. `backend/src/sales_trainer/services/material_service.py#freeze_submission_snapshots`
   - submission 会冻结：
     - `material_snapshot.items[].current_version`
     - `confirmed_material_version_id`
     - `frozen_at`
   - 历史记录里已有版本 id 与展示元数据。

3. `material_service.py#resolve_file_access(version_id)`
   - 读取文件时要求：
     - `version` 存在
     - `version.status == "published"`
   - 若版本已归档，即使 submission 的 `material_snapshot` 引用了它，也会返回 `[MATERIAL_VERSION_NOT_PUBLISHED]`。

4. `backend/src/sales_trainer/api.py`
   - learner/admin 文件读取入口只有：
     - `GET /api/v1/sales-trainer/materials/versions/{version_id}/file`
   - 接口不接受“按 submission/material_snapshot 回放历史材料”的参数。

5. 现状结论：
   - 历史 submission 虽冻结了材料版本元数据；
   - 但**一旦该版本因新发布被归档，历史回放无法通过现有 file API 拿到文件**。

6. 额外事实：
   - `get_sales_trainer_material_version_file` 里 `current_user` 只做鉴权，不做对象级授权；
   - `resolve_file_access(version_id)` 也没有 actor/scope 参数。
   - 这不是本报告主结论，但说明历史材料回放未来若开放 archived 只读，还必须同时补对象级授权。

### 1.7 legacy / dead data 诊断当前事实

1. `legacy_snapshot_only`
   - 路径配置：`get_config()` / `active_projection()` / `resolve_for_unit()` / `resolve_for_paper()` 已能在 active revision 缺失时标记 legacy。
   - 音频 submission：`task_brief_snapshot.submission_context` 冻结 `path_revision_id/path_revision_no/module_key/legacy_snapshot_only`。
   - training record / exam paper serializer 读取这些 lineage 字段。

2. 前端已有轻量诊断：
   - `web/src/lib/sales-trainer/operational-diagnostics.ts`
   - 只做：
     - failed task 聚合
     - `legacy_snapshot_only` 计数
     - path module 绑定缺失检查
   - 不具备后端权威 dead-data 扫描能力。

3. 未发现后端已有 API / service：
   - `dead data dashboard`
   - `config health`
   - `dependency graph`
   - `orphan material / archived referenced asset / unresolved prompt revision` 扫描

4. `business_etiquette_release_service.preview_release_impact(...)`
   - 已具备训练包级 impact preview；
   - 会统计章节、题目、AI Coach config、active learners 影响范围。
   - 但这套能力**没有复用到通用 newcomer path config / material / prompt**。

---

## 2. 审计问题映射与根因

### 2.1 `path payload validation` 审计问题

映射：

- `audit-synthesis.md` P1 配置与发布 #1 #2

问题：

- 路径配置保存/发布前缺少 path-wide 治理校验；
- 契约要求的 `module_key` 唯一、`order_index` 唯一、canonical `path_key/module_key`、`fallback_applied` 等没有落地；
- 顶层 `enabled` 仍是伪配置。

根因：

- 校验分散在 schema 与 publish-time ref-check 两层，中间缺少“统一语义校验器”；
- 当前服务更偏“引用存在性校验”，不是“发布契约校验”；
- legacy backfill 仍是生产读路径的一部分，压低了 fail-closed 的动力。

### 2.2 `AI Coach prompt 前置校验` 审计问题

映射：

- `audit-synthesis.md` P1 配置与发布 #3 #5

问题：

- admin 保存时只验 UUID 形状，不验真实 Prompt 资产；
- admin GET 失败时吞异常回默认值；
- 错误被推迟到 session/runtime 阶段才暴露。

根因：

- PromptTemplate 没有第一类 revision 表，当前短期方案依赖 `SystemLog` 重建；
- admin 配置面没有集中 Prompt binding resolver；
- GET 路由为了“页面可打开”采用了 fail-open。

### 2.3 `publish impact preview` 审计问题

映射：

- `audit-synthesis.md` P1 配置与发布 #7

问题：

- newcomer path config 只有 rollback preview，没有 publish impact preview。

根因：

- 路径配置生命周期先补了 save/publish/rollback/rollback-preview；
- 影响分析能力只在 `business_etiquette_release_service` 里单独实现，未抽到共享层。

### 2.4 `fallback_applied/fallback_reason` 审计问题

映射：

- `audit-synthesis.md` P1 配置与发布 #4

问题：

- 只有 `phase2_policy` 遵守了 business-rule-config 治理模式；
- 路径配置、AI Coach 配置、路径文案 fallback 没有统一 `fallback_applied/fallback_reason`。

根因：

- `phase2_policy` 已走 `BusinessRuleConfigService`；
- newcomer path / ai_coach 仍是 asset revision + ad hoc JSON，不在 shared business-rule lifecycle 内。

### 2.5 `provider readiness` 审计问题

映射：

- `audit-synthesis.md` P1 配置与发布 #6

问题：

- settings 只暴露 env 布尔位，不暴露 source/readiness/invalid_reason/fallback；
- AI Coach 模型、ASR、Deucate 分属不同配置源，运维看不到统一权威快照。

根因：

- provider 配置仍以 env + ConfigManager 并存；
- 尚未形成 `RuntimeProviderConfigSnapshot` 一类的统一治理对象。

### 2.6 `prompt snapshot / revision` 审计问题

映射：

- `audit-synthesis.md` P1 内容资产与历史回放 #1

问题：

- 音频 submission 的 `score_scheme_snapshot` 不含 prompt revision/payload；
- 首次评分按当前 prompt 行读取，而不是按 frozen revision/payload；
- AI Coach generation/scoring 的 snapshot 粒度也不一致。

根因：

- 音频评分历史治理先做了 result 级 `prompt_version/hash`，没有把 revision-first 推到 submission 阶段；
- AI Coach 依赖 PromptTemplate head + governance audit 重建，缺第一类 revision 模型。

### 2.7 `历史材料回放 / 资产归档保护` 审计问题

映射：

- `audit-synthesis.md` P1 内容资产与历史回放 #2

问题：

- 新材料版本发布时旧 published 版本直接归档；
- 历史 submission 虽保存 `material_snapshot`，但文件下载仍只接受 `published` 版本；
- 没有“被历史记录引用的 archived version 可只读回放”的保护。

根因：

- Material 生命周期设计目标是“唯一 current version”；
- 文件访问服务以“当前可下载版本”为准，不以“历史证据引用”为准；
- 缺少 history-aware asset reference / archive guard。

### 2.8 `legacy / dead data 诊断` 审计问题

映射：

- `audit-synthesis.md` P1 内容资产与历史回放 #5

问题：

- 已有 `legacy_snapshot_only` 标记，但没有后端权威 dead-data 扫描；
- 没有 API 统计 orphan materials、悬空 prompt、active config 引用 archived asset、不可回放历史记录。

根因：

- 当前诊断只停留在 lineage 字段透传和前端轻量聚合；
- 还没有专门的治理 service / dashboard。

---

## 3. 可执行阶段任务

### E1. 路径配置统一契约校验器

- 文件范围：
  - `backend/src/sales_trainer/schemas.py`
  - `backend/src/sales_trainer/services/path_config_service.py`
  - `backend/src/sales_trainer/services/path_config_models.py`
  - `backend/src/sales_trainer/path_config_api.py`
  - `docs/api-contract/sales-trainer.md`
  - `backend/tests/unit/test_newcomer_training_path_*`
  - `backend/tests/integration/test_newcomer_training_path_config_api.py`
- 成功标准：
  - 保存/发布统一拒绝重复 `module_key`
  - 保存/发布统一拒绝重复 `order_index`
  - `path_key` 只接受 canonical，legacy alias 只读
  - 明确顶层 `enabled`：要么真实生效，要么删除/迁移
  - `fallback_applied` 纳入路径配置响应
- 测试建议：
  - unit：重复 `module_key/order_index`、非法 alias、顶层 `enabled=false`
  - integration：save/publish/rollback 全链路
- 回滚策略：
  - 保留 legacy alias 只读解析，不删读取兼容
  - 新校验先只拦写路径，出问题可回退到旧 save/publish 路由
- 风险等级：P1

### E2. AI Coach Prompt 绑定前置校验 + GET fail-closed

- 文件范围：
  - `backend/src/sales_trainer/ai_coach_admin_api.py`
  - `backend/src/sales_trainer/services/ai_coach_chat_runtime.py`
  - `backend/src/sales_trainer/services/ai_coach_session_service.py`
  - `backend/src/sales_trainer/services/prompt_template_revision_resolver.py`
  - `backend/tests/unit/test_sales_trainer_ai_coach*.py`
  - `backend/tests/integration/test_newcomer_training_path_config_api.py`
- 成功标准：
  - 保存时校验 generation/scoring prompt：
    - 存在
    - 可用
    - `prompt_type` / `business_purpose` 匹配
  - GET 配置接口在 payload 损坏或绑定失效时返回 typed error，不回默认值
  - publish 前再次校验 working payload 中的 prompt 绑定
- 测试建议：
  - 缺 prompt / 归档 prompt / 用途不匹配 / payload 损坏
  - runtime 仍对 unresolved revision fail-closed
- 回滚策略：
  - 先保留只读诊断字段，若线上误伤可短期恢复 GET 默认值，但 save/publish 校验不应回退
- 风险等级：P1

### E3. newcomer path publish impact preview

- 文件范围：
  - `backend/src/sales_trainer/services/path_config_service.py`
  - `backend/src/sales_trainer/path_config_api.py`
  - `backend/src/sales_trainer/schemas.py`
  - `backend/tests/integration/test_newcomer_training_path_config_api.py`
  - `docs/api-contract/sales-trainer.md`
- 成功标准：
  - 新增 publish preview endpoint
  - 至少展示：
    - active/target revision
    - 受影响模块
    - 变更的 unit/material/prompt/article/paper 绑定
    - future-only 说明
    - 是否涉及高风险 AI Coach 字段
  - 与 rollback preview 风格一致
- 测试建议：
  - working revision 存在/不存在
  - backfill 首次发布
  - 高风险字段变更
- 回滚策略：
  - preview 为只读能力，可单独下线，不影响 publish 主路径
- 风险等级：P1

### E4. Runtime provider readiness snapshot

- 文件范围：
  - `backend/src/sales_trainer/api.py`
  - 新建建议：`backend/src/sales_trainer/services/provider_readiness_service.py`
  - `backend/src/sales_trainer/services/transcription_service.py`
  - `backend/src/sales_trainer/services/deucate_scoring_service.py`
  - `backend/src/sales_trainer/services/ai_coach_model_config.py`
  - `backend/tests/unit/test_sales_trainer_services.py`
- 成功标准：
  - 统一返回 provider snapshot：
    - `provider`
    - `source`（env/db/default）
    - `readiness`
    - `fallback_applied`
    - `fallback_reason`
    - `invalid_reason`
  - 覆盖 ASR、Deucate、AI Coach model config、storage backend
- 测试建议：
  - env 缺失、env 非法、db 模型不存在、disabled provider
- 回滚策略：
  - 先新增只读 snapshot，不改变现有 provider 选择逻辑
- 风险等级：P1

### E5. 音频评分 prompt revision-first 化

- 文件范围：
  - `backend/src/sales_trainer/services/material_service.py`
  - `backend/src/sales_trainer/services/audio_submission_service.py`
  - `backend/src/sales_trainer/services/audio_regrade_calculator.py`
  - `backend/src/sales_trainer/schemas.py`
  - `backend/src/sales_trainer/models.py`
  - `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
  - `backend/tests/unit/test_sales_trainer_services.py`
- 成功标准：
  - submission 冻结 `prompt_revision_id` 或完整 prompt payload
  - 首次评分优先读取 frozen revision/payload，而不是当前 prompt 行
  - score result / regrade preview 对齐同一 revision 语义
- 测试建议：
  - 提交后修改 prompt 再评分，结果仍按原 revision
  - archived target revision 重评
- 回滚策略：
  - migration 新字段只追加不替换旧字段；读取逻辑可先“新字段优先，旧字段兼容”
- 风险等级：P1

### E6. 历史材料只读回放 + 归档保护

- 文件范围：
  - `backend/src/sales_trainer/services/material_service.py`
  - `backend/src/sales_trainer/api.py`
  - 可能新增：`backend/src/sales_trainer/services/material_history_access_service.py`
  - `backend/tests/unit/test_newcomer_training_path_material_governance.py`
  - `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
- 成功标准：
  - 被历史 submission 引用的 archived material version 可只读回放
  - archive/publish 前能检测“仍被 active config / history 引用”的版本
  - learner/admin 文件访问补对象级授权
- 测试建议：
  - 发布 v2 后，历史记录仍可读取 v1
  - archived version 被历史引用时允许只读，不允许编辑/重发
  - 无权限用户不可下载他人材料证据
- 回滚策略：
  - 先新增 history-only 下载路径，不改现有 published-only 路径
- 风险等级：P1

### E7. backend dead-data / config-health / dependency-graph

- 文件范围：
  - 新建建议：
    - `backend/src/sales_trainer/services/config_health_service.py`
    - `backend/src/sales_trainer/services/dead_data_service.py`
    - `backend/src/sales_trainer/config_health_api.py`
  - `web/src/app/admin/sales-trainer/settings/*`
  - `backend/tests/unit/*config_health*`
- 成功标准：
  - 至少能发现：
    - `legacy_snapshot_only` 记录数
    - active path 引用 archived/missing material/prompt/content/paper
    - orphan material / orphan prompt revision
    - unresolved AI Coach prompt revision
  - 结果可追溯到具体 `logical_id/version_id/revision_id`
- 测试建议：
  - 构造 archived/missing refs、legacy-only 历史记录、孤儿版本
- 回滚策略：
  - 先只做只读诊断 API，不触发自动修复
- 风险等级：P2

---

## 4. 哪些配置需要后台管理，哪些可 env-only

### 4.1 必须后台管理 / 治理发布

这些配置会直接改变业务语义、学员体验或历史解释口径，必须进入后台治理：

- newcomer path payload：
  - `modules[]`
  - `module_key/module_type/order_index/enabled`
  - `learning_content_id/exam_paper_id/target_unit_id(s)`
  - `disabled_reason`
  - 展示文案/按钮文案/引导文案
- `modules[].ai_coach`：
  - `enabled`
  - `coach_mode`
  - `allowed_interaction_types`
  - `allowed_training_card_types`
  - `generation_timeout_seconds`
  - `retry_policy`
  - `failure_behavior`
  - `prompt_template_id/scoring_prompt_template_id`
  - `generation_model/scoring_model`
- `sales_trainer_audio_score_prompt` 及其 revisions
- `SalesTrainerMaterial` / `SalesTrainerMaterialVersion`
- `sales_trainer.phase2.closed_loop_policy`

原因：

- 都会影响 learner 行为、评分结果、历史可解释性或运营动作；
- 需要 preview/publish/rollback/audit；
- 不适合用 env 修改。

### 4.2 适合 operator-only 系统配置中心，而不是 content admin

- ASR mode / model
- AI Coach LLM model 映射
- Deucate timeout
- 文件 URL 过期时间
- 上传大小上限 / MIME allowlist

原因：

- 它们影响运行时稳定性和基础设施行为；
- 不是内容运营字段；
- 需要审计，但不应交给内容管理员；
- 长期不应继续散落在 env，建议迁移到“系统/运维配置 bundle”。

### 4.3 可保持 env-only 的项

- 对象存储/供应商密钥：
  - `DEUCATE_API_KEY`
  - `DASHSCOPE_API_KEY`
  - `TENCENT_COS_*`
  - `ALI_OSS_*`
- 存储后端与本地路径：
  - `SALES_TRAINER_AUDIO_STORAGE_PATH`
  - `SALES_TRAINER_MATERIAL_STORAGE_PATH`
  - `SALES_TRAINER_AUDIO_STORAGE_BACKEND`
  - `SALES_TRAINER_MATERIAL_STORAGE_BACKEND`
- 公开读开关：
  - `TENCENT_COS_PUBLIC_READ`

原因：

- 属于部署环境/密钥/物理存储边界；
- 变更需要配合运维、权限和回滚，不适合作为业务后台配置；
- 但必须在只读 readiness/config-health API 中暴露“是否就绪、为什么不就绪”，不能继续只靠人工读 env。

---

## 5. 需要迁移 / 历史回填 / 人工确认的项

### 5.1 需要迁移

1. 音频 submission / score result 的 prompt revision 语义
   - 目标：保存 `prompt_revision_id` 或完整 prompt payload snapshot。
   - 现状：只有 `prompt_id/version/hash`。

2. 历史材料访问引用
   - 目标：`material_snapshot` 中补可直接回放的历史引用（如 `storage_key/backend/version_id` 或独立 asset ref）。
   - 现状：只有 `current_version` 元数据展示，下载仍走 live version status。

3. provider readiness 快照
   - 目标：把 env + db config 汇总到统一只读快照结构。
   - 现状：散落于 `_sales_trainer_settings_payload`、transcription/deucate service、ConfigManager。

### 5.2 需要历史回填

1. `legacy_snapshot_only=true` 的路径/录音/考试/训练记录
   - 需要评估哪些能可靠回填 `path_revision_id/path_revision_no/module_key`。

2. AI Coach 历史 session 的 prompt revision
   - 若 `prompt_revision_id` 为 `None`，只能尝试按 `PromptTemplate.updated_at/SystemLog` 重建；
   - 无法重建的必须显式标记 unresolved，不得伪造。

3. 音频评分历史记录
   - 若未来引入 `prompt_revision_id`，旧记录只能部分回填；
   - 没有可审计 revision 的记录要保留 legacy 标记。

### 5.3 需要人工确认

1. 顶层 `newcomer_path.enabled`
   - 是要变成真实总开关，还是删除并迁移为模块级治理。

2. AI Coach prompt `business_purpose` / `prompt_type` 白名单
   - generation 与 scoring 的允许集合需要产品/平台明确。

3. 历史材料回放策略
   - 是允许 archived version 只读下载；
   - 还是额外把历史文件复制到 immutable archive。

4. provider 配置管理边界
   - 哪些仍由 env 持有；
   - 哪些迁移到 operator-only config bundle。

5. dead-data 自动修复范围
   - 第一阶段建议只诊断，不自动修复；
   - 哪些 orphan/legacy 记录允许脚本修复，需要业务 owner 确认。

---

## 6. 现有测试覆盖与缺口

已存在的相关覆盖：

- `backend/tests/integration/test_newcomer_training_path_config_api.py`
  - 覆盖 backfill / publish / rollback preview 基础链路
- `backend/tests/unit/test_newcomer_training_path_config_revision.py`
  - 覆盖 `active_revision_missing` / `legacy_snapshot_only`
- `backend/tests/unit/test_sales_trainer_phase2_projection.py`
  - 覆盖 `phase2_policy.fallback_applied`
- `backend/tests/unit/test_newcomer_training_path_material_governance.py`
  - 覆盖材料发布审计、metadata future-only 审计
- `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
  - 覆盖音频 lineage 与 `score_scheme_snapshot.prompt_id`
- `backend/tests/unit/test_business_etiquette_release_service.py`
  - 覆盖训练包 release impact preview

明确缺口：

- 未发现针对以下问题的现成测试：
  - path payload 重复 `module_key/order_index`
  - AI Coach admin GET fail-open
  - AI Coach prompt binding 存在性 / 用途预校验
  - `PromptTemplateRevisionResolver` fallback 状态对 admin 配置面的影响
  - `MaterialService.resolve_file_access()` 的 archived 历史回放
  - material file endpoint 的对象级授权
  - newcomer path publish impact preview（当前也无实现）

---

## 7. 最高风险结论

当前最高风险不是单一字段遗漏，而是**历史可解释性与当前可运行性脱节**：

- AI Coach 与音频评分在配置面允许保存“形状正确但资产未就绪”的绑定；
- 运行时再 fail-closed；
- 历史音频评分与材料回放又没有完整 revision-first / snapshot-first 落地。

结果是：

- 新配置可能“能保存、不能稳定运行”；
- 历史记录可能“有快照元数据、拿不到原始资产或原始 prompt 语义”；
- 管理端缺统一 impact preview / dead-data scan，无法在发布前看清影响面。

这三个点叠加后，最容易出现“发布成功但历史不可回放、运行时才爆错、回滚也无法解释”的治理失败。
