# Sales Trainer API 契约

> 状态: 🔨 新人训练闭环契约冻结（2026-06-27）
>
> 后端模块: `backend/src/sales_trainer/`
>
> 基础路径: learner `/api/v1/sales-trainer`；admin `/api/v1/admin/sales-trainer`

## 产品命名与边界

本契约的用户可见产品名为“新人训练路径”。`sales_trainer`、`/sales-trainer`、`/api/v1/sales-trainer` 和 `/api/v1/admin/sales-trainer` 在第一版只作为兼容技术命名保留，不代表产品应继续对学员或管理员展示为“销售队列”或“销售训练队列”。

新人训练路径负责完整训练闭环：PPT/材料学习、录音上传、AI 转写、AI 评分、Markdown 文章学习、试卷考试、AI Coach、实时对练入口投影、后台配置、训练记录、管理看板和审计。实时语音运行时仍由 `sales_bot`、`practice_sessions`、`training_runtime`、`/practice/[sessionId]` 和 `/api/v1/practice/sessions` 等运行时权威负责；`sales_trainer` 只能通过 runtime binding 和 outcome projection 纳入闭环，不得直接创建、修改或修复 realtime 会话。

旧语义“模块 4 只能作为 disabled/coming-soon placeholder，且永不接入实时运行时”自 2026-06-27 起被本契约 supersede。实时对练可以纳入新人训练路径，但 learner 入口开放前必须同时满足 runtime binding、对象级权限、配置健康、provider readiness、TrainingJourney outcome projection、审计和 active revision rollback 语义。缺任一条件时模块必须 fail-closed，返回 typed diagnostic 或 disabled 状态；不得用占位成功、前端隐藏或 WebSocket 重连掩盖配置错误。

## 概览

- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie。
- 响应包裹: 统一为 `{ "success": boolean, "data": ..., "error": ..., "message": ..., "trace_id": "..." }`。
- 字段命名: API 入参与返回字段统一使用 `snake_case`。
- learner 权限: 只能读取已发布训练单元，只能提交、读取本人做题记录和本人音频提交。
- 超级管理员权限: `admin` / `super_admin` 可管理内容配置、发布/归档、查看全局记录、查看日志、重试失败任务和显式重评历史成绩。
- 内容管理员权限: `content_admin` / `newcomer_content_admin` 可管理训练单元、文章绑定、题库、考卷、材料和录音评分标准；不能查看学员记录、配置健康、操作日志或重试任务。AI Coach 高风险字段仍需 `sales_trainer.manage_prompts`。
- 培训负责人权限: `support` / `training_lead` / `training_manager` 可查看本人 `department` 范围内的学员录音、评分结果、做题记录和训练记录；当前后端同时保留题库维护兼容能力 `sales_trainer.manage_questions`；不能修改其他内容配置、查看系统日志或重试任务。无部门时使用空范围兜底，不放大全局权限。
- 运维人员权限: `operations` / `ops` / `operator` / `sre` 可查看配置健康、操作日志、全局记录，并可重试转写/评分任务、显式重评历史成绩；不能管理文章、题库、考卷、材料等内容配置。
- 销售训练材料单独管理: 销售训练 PPT、逐字稿、示例录音和附件属于 `sales_trainer` 域，不复用 `/admin/presentations` 的业务语义。
- PPT 演练门禁: `unit.config.audio.purpose="ppt_pitch"` 的任务必须绑定已发布材料，学员提交前必须确认当前要求版本；提交记录冻结材料、任务简报和评分方案快照。
- 兼容命名: API 路径和模块目录暂不改名；新增 DTO、后台导航和学员页面文案必须以“新人训练路径”为展示名。

### Admin Capability Projection

前端后台导航不得复制角色字符串矩阵。进入新人训练路径后台后，客户端应调用 `GET /api/v1/admin/sales-trainer/capabilities` 获取当前用户的机器可读能力，再按能力展示入口。该接口只投影 `sales_trainer.permissions` 中的现有权限权威，不新建独立权限配置源。

```typescript
type SalesTrainerAdminCapabilityKey =
  | "admin_full_access"
  | "manage_content"
  | "manage_questions"
  | "manage_modules"
  | "manage_prompts"
  | "view_records"
  | "view_global_records"
  | "retry_jobs"
  | "regrade_history"
  | "view_logs"
  | "view_settings";

interface SalesTrainerAdminCapabilities {
  role: string;
  role_label: string;
  capabilities: Record<SalesTrainerAdminCapabilityKey, boolean>;
  capability_keys: SalesTrainerAdminCapabilityKey[];
}
```

默认值与兜底:

- 未登录或 learner 角色调用由认证层拒绝或返回全部 `false` 能力；前端 fail-closed，不展示受限入口。
- `role_label` 由后端权限模块统一生成；前端只可在 capability 缺失时展示保守默认文案。
- `SALES_TRAINER_MANAGER_ROLES` 仍是培训负责人兼容角色来源；缺失/空值使用默认 `support,training_lead,training_manager`；显式配置只保留 allowlist 中的 `support`、`training_lead`、`training_manager`，混入非法值会记录诊断，全非法配置 fail-closed 为无培训负责人角色。
- 该接口不写审计日志，因为它只读取当前会话权限；真实操作仍由具体 admin API 写操作日志。

前端约束:

- `/admin/sales-trainer` workbench 根页也属于受限后台入口，必须先用共享 route capability 判断确认当前路径可访问。未授权、capability 加载失败或尚未确认前，不得请求 manager dashboard、不得渲染指标卡、风险学员或 workbench link。
- workbench dashboard API 失败时必须展示可重试错误态，不得把失败吞成空指标、空风险学员或“暂无数据”。
- sidebar、workbench card、module nav、按钮和直链页必须消费同一 capability projection；前端隐藏只能作为体验层，不能替代后端 API 权限校验。

## 联调对齐说明

- 本文按本轮约定端点定义基础闭环契约，主线程后续按实际实现校对。
- 已对齐: learner/admin `/file` 文件读取语义、`source_page`、评分记录 `transcript_snapshot`，以及 multipart 上传时的 `duration_seconds`/`source_page` 表单字段。

## 录音上传边界

- 业务上不设置固定录音时长限制。
- `duration_seconds` 是可选元数据，只用于展示、分析或排查，不参与上传拦截和业务判定。
- 技术保护由可配置项承担: 音频格式、文件大小、存储后端、存储路径或对象 key、转写任务超时、评分任务超时。
- 前端不得基于固定时长拒绝上传；如需提示，应根据后端返回的格式、大小、存储或任务错误展示。

## 新人训练路径模块配置契约

模块配置是新人训练路径首页、后台模块管理、文章/考卷/材料绑定和完成状态聚合的 source of truth。前端 `web/src/lib/sales-trainer/module-path.ts` 只能作为兼容适配层读取后端 DTO，不得继续把模块标签、排序、启停、目标单元、文章、试卷或提示词作为唯一真源硬编码。

`path_key` 第一版默认使用 `newcomer_training_path_v1`；历史 `new_seller_modules_v1` 允许作为兼容 alias 读取，但新 seed 和后台保存必须写入 `newcomer_training_path_v1`。缺少模块配置时 learner 首页返回空路径和 `[NEWCOMER_PATH_CONFIG_MISSING]` 诊断；非法配置在后台保存/发布时返回 `[NEWCOMER_MODULE_CONFIG_INVALID]`，不得由前端猜测兜底。

```typescript
type NewcomerModuleType =
  | "audio_scoring"
  | "article_exam"
  | "audio_scoring_group"
  | "realtime_roleplay"
  | "realtime_placeholder";

type NewcomerCompletionRule =
  | "audio_scored"
  | "paper_passed"
  | "all_audio_options_scored"
  | "realtime_outcome_recorded"
  | "placeholder_disabled";

// v1 wire compatibility: backend and persisted path config still use the
// legacy three-value rule. The canonical names above are governance semantics,
// not additional request values until a versioned API migration is introduced.
type NewcomerPathCompletionRule = "passed" | "scored" | "submitted";
const NEWCOMER_COMPLETION_RULE_COMPATIBILITY = {
  audio_scored: "scored",
  paper_passed: "passed",
  all_audio_options_scored: "scored",
  realtime_outcome_recorded: "submitted",
  placeholder_disabled: "submitted",
} satisfies Record<NewcomerCompletionRule, NewcomerPathCompletionRule>;

interface NewcomerTrainingPathConfig {
  path_key: "newcomer_training_path_v1";
  display_name: "新人训练路径";
  description?: string | null;
  enabled: boolean;
  modules: NewcomerTrainingPathModuleConfig[];
}

interface NewcomerTrainingPathModuleConfig {
  module_key:
    | "ppt_explanation"
    | "business_skills"
    | "elevator_pitch"
    | "realtime_roleplay"
    | "realtime_roleplay_placeholder";
  module_type: NewcomerModuleType;
  display_name: string;
  description: string;
  order_index: number;
  enabled: boolean;
  disabled_reason?: string | null;
  completion_rule: NewcomerPathCompletionRule;
  target_unit_id?: string | null;
  target_unit_ids?: string[];
  learning_content_id?: string | null;
  exam_paper_id?: string | null;
  material_binding_group?: string | null;
  runtime_binding?: RealtimeRuntimeBinding | null;
  duration_options?: Array<{
    option_key: string;
    display_name: string;
    duration_minutes: number;
    target_unit_id: string;
    order_index: number;
  }>;
  admin_permissions: string[];
  audit_events: {
    created: string;
    updated: string;
    published: string;
    archived: string;
    binding_changed?: string;
  };
  validation: {
    required_bindings: string[];
    missing_behavior: string;
    illegal_behavior: string;
  };
}

interface RealtimeRuntimeBinding {
  binding_key: "newcomer_realtime_roleplay_v1";
  runtime_owner: "training_runtime";
  runtime_descriptor_id: string;
  scenario_key: string;
  practice_template_id?: string | null;
  runtime_config_revision_id: string;
  roleplay_contract_revision_id?: string | null;
  provider_readiness_snapshot: {
    provider: "stepfun_realtime" | "legacy" | "mock";
    ready: boolean;
    checked_at: string;
    config_revision_id?: string | null;
    failure_code?: string | null;
    failure_message?: string | null;
  };
  permission_policy: {
    learner_enter: "sales_trainer.enter_realtime";
    admin_configure: "sales_trainer.manage_modules";
    admin_provider_health: "sales_trainer.view_settings";
  };
  failure_policy: {
    terminal_codes: string[];
    transient_codes: string[];
    voluntary_codes: string[];
    terminal_retry_allowed: false;
  };
  rollback_policy: {
    rollback_via_active_revision: true;
    disable_module_on_invalid_binding: true;
    fallback_to_placeholder: false;
  };
}
```

### 实时 Provider Registry

`sales_trainer.realtime_provider.registry` 是实时对练 provider 启停、readiness、回滚和审计的当前治理真源。它通过现有 ConfigBundle/BusinessRuleConfig lifecycle 管理，支持 draft、validate、publish、rollback、disable，并写入 `ConfigBundleAuditLog`。默认配置必须 disabled 且 not ready；缺失、停用或非法时 learner start fail-closed，不得沿用 path revision 中的旧 readiness snapshot 放行。

密钥边界：registry、path `runtime_binding`、发布预览、active revision snapshot、TrainingJourney、runtime outcome projection 和 operation log 均不得保存真实 `STEPFUN_API_KEY`、Authorization header、Cookie、JWT、LLM provider key 或完整上游 payload。配置面只能保存 provider、model、runtime profile 引用、readiness、masked/configured 状态和失败分类；日志只允许记录 `trace_id`、`session_id`、`runtime_descriptor_id`、`model_name`、`error_code`、redacted endpoint 和 operator-facing reason。

```typescript
interface SalesTrainerRealtimeProviderRegistry {
  version: string;
  enabled: boolean;
  descriptors: Array<{
    descriptor_id: string; // 必须匹配 RealtimeRuntimeBinding.runtime_descriptor_id
    label: string;
    provider: "stepfun_realtime" | "phase4_local_stepfun" | "mock";
    runtime_owner: "training_runtime" | "sales_bot";
    enabled: boolean;
    runtime_profile_id?: string | null;
    config_revision_id: string;
    rollback_to_descriptor_id?: string | null;
    readiness: {
      ready: boolean;
      checked_at?: string | null;
      failure_code?: string | null;
      failure_message?: string | null;
    };
  }>;
}
```

启动实时对练时必须同时校验：

- registry 顶层 `enabled=true`。
- `descriptors[]` 存在与 path runtime binding 相同的 `runtime_descriptor_id`。
- descriptor `enabled=true`。
- descriptor `readiness.ready=true`。

失败时返回 `[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]`、`[NEWCOMER_REALTIME_PROVIDER_DESCRIPTOR_MISSING]`、`[NEWCOMER_REALTIME_PROVIDER_DISABLED]` 或 `[NEWCOMER_REALTIME_PROVIDER_NOT_READY]`。成功创建 session 时，`voice_policy_snapshot.external_binding.runtime_registry` 必须冻结 registry 的 `config_id`、`version`、`source`、`status` 和命中的 descriptor，用于历史回放和审计。

StepAudio 2.5 provider migration 语义：

- apply：`20260702_1100_088_stepfun_default_model_stepaudio25` 只更新 `voice_runtime_profiles` 的默认模型和 server default，不创建 secret、不写 registry 密钥、不修改非默认 profile。
- rollback：downgrade 只把默认 `stepfun_realtime` profile 从 `stepaudio-2.5-realtime` 回退到 `step-audio-2.3`，不覆盖管理员显式选择的其他模型。
- registry 发布/回滚：ConfigBundle rollback 只能移动 provider registry 的 active descriptor/config pointer；已冻结在历史 `voice_policy_snapshot.external_binding.runtime_registry` 的回放证据不可被回写。
- readiness：迁移 apply 后若控制台未授权 `stepaudio-2.5-realtime`，learner start 必须 fail-closed 为 provider readiness/auth diagnostic，不得 fallback 到 legacy/local provider 伪成功。

### 默认模块矩阵

| module_key | 默认名称 | module_type | 默认 enabled | completion_rule | 必要绑定 | 管理入口 | 权限 | audit action |
|---|---|---|---|---|---|---|---|---|
| `ppt_explanation` | `PPT 讲解录音` | `"audio_scoring"` | `true` | `passed` | `target_unit_id`、已发布材料、已发布评分提示词 | admin 新人训练路径模块/材料/评分方案 | `sales_trainer.manage_modules`、`sales_trainer.manage_materials`、`sales_trainer.manage_prompts` | `newcomer_module.ppt_explanation.*` |
| `business_skills` | `商务技巧` | `"article_exam"` | `true` | `passed` | `learning_content_id`、`exam_paper_id` | admin 新人训练路径文章绑定/考卷管理 | `sales_trainer.manage_modules`、`sales_trainer.manage_papers`、`learning_content.manage` | `newcomer_module.business_skills.*` |
| `elevator_pitch` | `金字塔演讲` | `"audio_scoring_group"` | `true` | `passed` | `duration_options[].target_unit_id`、已发布评分提示词；材料可按企业训练包选配 | admin 新人训练路径模块/评分方案 | `sales_trainer.manage_modules`、`sales_trainer.manage_prompts` | `newcomer_module.elevator_pitch.*` |
| `realtime_roleplay` | `实时对练` | `"realtime_roleplay"` | `false` | `submitted` | `runtime_binding`、provider readiness、已发布 runtime config、权限策略、outcome projection、rollback policy | admin 新人训练路径模块配置 + 运行时健康页 | `sales_trainer.manage_modules`、`sales_trainer.view_settings` | `newcomer_module.realtime_roleplay.*` |
| `realtime_roleplay_placeholder` | `实时对练（旧占位）` | `"realtime_placeholder"` | `false` | `submitted` | 仅兼容历史 disabled 配置；不得作为新的 active revision 正式模块发布 | admin 新人训练路径模块配置 | `sales_trainer.manage_modules` | `newcomer_module.realtime_placeholder.*` |

兼容说明：上表的 `completion_rule` 是 v1 API 入参与持久化值；canonical 治理语义通过 `NEWCOMER_COMPLETION_RULE_COMPATIBILITY` 映射：`audio_scored -> scored`、`paper_passed -> passed`、`all_audio_options_scored -> scored`、`realtime_outcome_recorded -> submitted`、`placeholder_disabled -> submitted`。未知 `completion_rule` 或直接把 canonical 值提交给 v1 path config API 时，后端仍按非法配置拒绝。

### 校验与兜底

- `path_key` 必填，默认 `newcomer_training_path_v1`；读取历史 `new_seller_modules_v1` 时必须标记为 compatibility alias。
- `module_key` 在同一路径内唯一，`order_index` 必须为正整数且不可重复。
- `display_name`、`description`、`disabled_reason`、按钮文案和空状态文案属于后台可配置展示内容；缺失时服务端可使用安全默认值，但响应必须标明 `fallback_applied=true`。
- `"audio_scoring"` 模块必须绑定一个已发布 `audio_scoring` 单元、至少一个 required 材料绑定和已发布音频评分提示词；缺失返回 `[NEWCOMER_MODULE_BINDING_MISSING]`。
- `"article_exam"` 模块必须绑定已发布 `LearningContent` 和已发布 `ExamPaper`；草稿或归档内容对 learner 返回 `[LEARNING_CONTENT_NOT_PUBLISHED]` 或 `[PAPER_NOT_PUBLISHED]`。
- `"audio_scoring_group"` 模块必须至少有一个 duration option；每个 option 的 `duration_minutes` 必须大于 0，`target_unit_id` 必须指向已发布音频评分单元。
- `"realtime_roleplay"` 默认 disabled；启用并发布前必须通过 runtime binding 校验、provider readiness 校验和 rollback preview。learner start 时还必须读取 `sales_trainer.realtime_provider.registry` 当前 active 配置再次校验 provider 未被停用、descriptor 未被回滚替换且 readiness 仍然通过。任一校验失败返回 `[NEWCOMER_REALTIME_BINDING_INVALID]`、`[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]`、`[NEWCOMER_REALTIME_PROVIDER_DESCRIPTOR_MISSING]`、`[NEWCOMER_REALTIME_PROVIDER_DISABLED]`、`[NEWCOMER_REALTIME_PROVIDER_NOT_READY]` 或更具体错误，learner 不得进入实时运行时。
- 已完成实时会话只有在 runtime authority 冻结 `voice_policy_snapshot.external_binding` 后才可进入 TrainingJourney。该 binding 至少包含 `owner="sales_trainer"`、`path_revision_id`、`path_revision_no`、`module_key` 和 `binding_key`；缺少这些字段时，`sales_trainer` 不得从 WebSocket 状态、前端 URL 或最新 active revision 反推完成结果。
- `"realtime_placeholder"` 只作为历史 disabled 配置兼容读取；不得作为新的 active revision 正式发布，也不得调用 `/api/v1/practice/sessions`。
- 非法 `module_type`、未知 `completion_rule`、重复 `module_key`、重复 `order_index` 或绑定不存在时，后台保存/发布返回 `[NEWCOMER_MODULE_CONFIG_INVALID]` 并写操作日志。
- 配置读取失败或配置缺失时 learner 不展示伪成功；返回空路径、诊断错误或 disabled 模块，由 UI 显示可配置空状态。

## 发布治理修订契约

新人训练路径的可配置内容采用统一发布治理语言。第一阶段允许保留 `sales_trainer` 现有表和兼容 API，但新增或改造的写路径必须向以下语义收敛：

| 字段 / 概念 | 契约 |
|---|---|
| `logical_id` | 业务对象稳定身份，例如路径配置、商务技巧考卷、题目、评分标准或文章绑定。 |
| `revision_id` | 不可变内容修订。已发布 revision 的 payload 不允许原地修改。 |
| `working_revision_id` | 管理员保存修改后生成的待发布修订。保存不影响 learner。 |
| `active_revision_id` | 当前只对未来 learner 请求生效的修订指针。发布和回滚只移动该指针。 |
| `binding_revision` | 模块绑定文章/考卷/材料、考卷绑定题目等引用关系的修订。 |
| `snapshot` | attempt、audio submission、score result 创建时冻结的内容副本。 |
| `legacy_snapshot_only` | 旧历史记录无法可靠回填 revision lineage 时的显式标记。 |
| `audit_event` | 发布、回滚、归档、绑定变更、重评必须记录 actor、action、target、before、after、reason、trace_id 和影响范围。 |
| `regrade_run` | 高风险历史重评动作。发布或回滚不得自动改写历史成绩。 |

### Future-only 规则

- 编辑已发布对象时，API 必须返回 working revision 或等价待发布对象，不得直接覆盖 active revision payload。
- 发布新 revision 后，只影响新创建的 path view、paper attempt、audio submission、score result 或 AI Coach session。
- 回滚只移动 `active_revision_id` 指针，只影响未来请求。
- 历史 attempt/submission/result/session 只读取创建时冻结的 snapshot 或 revision refs；不得从 latest asset 重新拼装展示。
- 对只有历史 snapshot、没有 revision refs 的记录，响应应标记 `legacy_snapshot_only=true`，不得伪造 revision。

### 高风险动作

以下字段或动作必须被视为高风险，不允许通过配置降级：

- 正确答案、分值、通过线、题目 AI 评分 prompt。
- 音频评分 prompt、评分维度、模型、重试/超时策略。
- 路径模块绑定、考卷题目组成、学习内容绑定。
- 历史重评、批量回滚、归档仍被 active 配置引用的资产。

高风险发布必须返回影响范围预览；高风险重评必须走独立 `regrade_run`，写入 before/after、reason、trace_id，并保留原始结果。

### AI Coach 模块配置

`modules[].ai_coach` 是商务技巧 AI 教练的可选配置。它只控制 chatbot 训练模式，不替代固定试卷考试、后端评分记录或掌握状态聚合。

默认值：

- `enabled=false`
- `chat_enabled=true`
- `streaming_enabled=true`
- `entry_resume_policy="latest_active_or_new"`；可选 `"latest_active_or_new" | "latest_in_progress" | "new"`。缺省会话创建请求必须读取该配置。
- `generation_timeout_seconds=120`，范围 `5..120`
- `coach_mode="mixed_drill"`
- `allowed_interaction_types=["single_choice","multiple_choice"]`；裸配置安全默认不启用简答，因为简答必须绑定评分 Prompt。商务礼仪 seed/admin 默认绑定评分 Prompt，并启用 `["single_choice","multiple_choice","short_answer"]`。
- `allowed_training_card_types=["scenario_judgment"]`；可选 `"scenario_judgment" | "expression_rewrite" | "role_response"`。安全默认只开启场景判断卡；启用改写卡或角色回应卡时必须同时启用 `"short_answer"` 并绑定 `scoring_prompt_template_id`。商务礼仪 seed/admin 默认启用三类训练卡。
- `allowed_ui_event_types=["quiz_card","explanation_card","summary_card","followup_prompt"]`
- `max_cards_per_message=1`
- `proactive_coaching_enabled=false`；demo/local seed 为 `true`
- `session_start_behavior="welcome_only"`；可选 `"welcome_only" | "plan_then_wait" | "plan_and_first_card"`，demo/local seed 为 `"plan_then_wait"`
- `auto_advance_enabled=false`；demo/local seed 为 `true`，但每次下一步生成仍最多只允许 1 张练习卡
- `max_auto_steps_per_session=5`，范围 `1..10`；每轮仍最多生成 1 张练习卡，提交后可连续推进到下一步或阶段总结
- `correct_streak_to_increase_difficulty=2`，范围 `1..10`
- `incorrect_streak_to_remediate=1`，范围 `1..10`
- `incorrect_streak_to_pause=2`，范围 `1..10` 且必须 `>= incorrect_streak_to_remediate`
- `remediation_strategy="explain_then_retry"`；可选 `"explain_then_retry" | "ask_user_choice" | "simplify_then_retry"`
- `summary_when_mastery_reached=true`
- `allowed_next_actions=["continue_drill","increase_difficulty","remediate","switch_scenario","summarize","ask_user_choice","end_session"]`
- `chat_welcome_message="你好，我是商务技巧 AI 教练。你可以先说想练什么；需要验证时，我会在对话里放一张单选、多选或简答练习卡。"`
- `empty_response_recovery_message="我没有拿到可操作的训练卡片。你可以继续下一题、换个场景，或先总结本轮。"`
- `empty_response_recovery_prompts=["继续下一题","换个场景","总结本轮"]`，范围 `1..4` 个非空字符串
- `generation_failure_recovery_message="我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。"`
- `generation_failure_recovery_prompts=["重试下一题","换主题","总结一下"]`，范围 `1..4` 个非空字符串；用于下一步动作生成失败或答题后流式生成超时的可恢复 followup。
- `min_turns=3`
- `max_turns=10`
- `mastery_threshold=80`
- `output_schema_version="ai_coach_interaction_v1"`
- `prompt_contract_hash`、`scoring_contract_hash` 是运行时审计字段。admin 配置请求中的值会被忽略，模块配置中保持为 `null`；真实 hash 在会话生成/评分时由后端根据已渲染 prompt contract 计算并记录。
- `retry_policy={"max_retries":1,"retry_backoff":1.0}`；默认只允许 1 次重试，避免多轮 LLM 不合约时让学员等待过久。管理员可按模型稳定性调高，但仍受 `generation_timeout_seconds` 总预算约束。

Learner 工作台 UI 配置：

- 商务礼仪 AI 教练页面必须是 Chat-First 工作台：AI 文本、学员消息、单选/多选/简答/改写/角色回应卡都在同一条对话时间线中渲染。练习卡是教练按需调用的工具结果，不是每轮强制主流程。
- 页面首屏只保留轻量标题、当前小单元和训练状态；“教练判断/完整结论”不得常驻首屏，只有提交卡片后在卡片附近展示简短反馈，结束总结时通过 `summary_card` 展示完整结论。
- `web/src/app/(dashboard)/sales-trainer/business-skills/coach/coach-workbench-config.ts` 是 Slice 7 的前端集中配置来源，包含页面文案、按钮文案、训练状态标签、是否展示自由追问、是否允许跳过当前卡片。
- 默认 `showFreeFollowup=true`，自由追问只调用 chat message stream；它可以解释、追问和生成可选练习卡，但正式训练进度只根据已提交训练卡和总结推进。
- 默认 `allowSkipActiveCard=false`，存在 active pending `quiz_card` 时“继续下一题”命令禁用；如未来放开，必须迁移为后端 `modules[].ai_coach` 配置并纳入 `sales_trainer.manage_modules` 权限、配置发布和操作日志。
- 页面文案/按钮文案当前由前端集中配置治理；若需要运营后台调整，必须新增 `modules[].ai_coach.workbench_copy` 或等价配置对象，并定义字段校验、默认值、回滚和审计。

简答题配置：

- 当 `allowed_interaction_types` 包含 `"short_answer"` 时，`scoring_prompt_template_id` 必填。
- 当 `allowed_training_card_types` 包含 `"expression_rewrite"` 或 `"role_response"` 时，`allowed_interaction_types` 必须包含 `"short_answer"`，且 `scoring_prompt_template_id` 必填。
- 单选/多选训练不要求 scoring prompt。
- `prompt_template_id` 用于生成互动卡片；`scoring_prompt_template_id` 只用于简答评分，两者独立治理。
- `prompt_template_id` 和 `scoring_prompt_template_id` 必须是 `PromptTemplate` UUID；非法格式保存或运行时解析返回 `[AI_COACH_PROMPT_CONFIG_INVALID]`。

权限：

- 平台 PromptTemplate CRUD、默认模板、场景绑定和治理修复属于 `/admin/prompts` 平台治理面，只允许平台 `admin` / `super_admin`。销售训练 `content_admin` / `newcomer_content_admin` 不能直接修改平台模板正文，只能在销售训练配置中绑定已治理的模板。
- 查看/普通模块配置需要 `sales_trainer.manage_modules` 对应角色。
- 修改普通开关、进入后行为或自动推进步数需要 `sales_trainer.manage_modules` 对应角色。
- 修改 `coach_mode`、`allowed_interaction_types`、`allowed_training_card_types`、`chat_enabled`、`streaming_enabled`、`entry_resume_policy`、`generation_timeout_seconds`、`allowed_ui_event_types`、`max_cards_per_message`、`chat_welcome_message`、`empty_response_recovery_message`、`empty_response_recovery_prompts`、`generation_failure_recovery_message`、`generation_failure_recovery_prompts`、`min_turns`、`max_turns`、`mastery_threshold`、连续答对/答错阈值、补救策略、总结策略、`allowed_next_actions`、prompt 绑定、模型、重试策略或失败策略等高风险字段，需要 `sales_trainer.manage_prompts` 对应角色。
- 通用 `/admin/newcomer-training/path-config` 保存也必须执行同一字段级 RBAC；权限 diff 失败时返回 `[AI_COACH_CONFIG_RBAC_CHECK_FAILED]`，不得 fail-open 保存。
- learner 创建 AI Coach session 时，客户端传入的 `coach_mode` / `interaction_type` 必须落在模块 `allowed_interaction_types` 允许范围内；否则返回 `[AI_COACH_INTERACTION_TYPE_NOT_ALLOWED]`。

公开投影与入口：

- Learner 展示 AI Coach 入口必须以 `GET /api/v1/sales-trainer/journey` 的 `modules[].next_action` 为唯一运行真源；`action_key` / `target_path` / `disabled` / `disabled_reason` 由后端 TrainingJourney 统一投影。
- `GET /api/v1/sales-trainer/paths` 的 `levels[].ai_coach_availability` 仅作为 legacy 兼容读面，不得作为 learner 页面、考试结果页或商务技巧页展示 AI Coach 入口的权威来源。
- `ai_coach_availability` 只包含 `enabled`、`configured`、`available`、`coach_path`、`disabled_reason`、`allowed_interaction_types`，不得携带 prompt、评分、answer key 或路径配置快照。
- Learner `SalesTrainerUnit.config.path` 不返回完整 `ai_coach` 配置；不得暴露 `prompt_template_id`、`prompt_revision_id`、`prompt_contract_hash`、`scoring_prompt_template_id`、`scoring_prompt_revision_id`、answer key、rubric、interaction snapshot 或 path/config snapshot。
- `enabled=false`、缺少生成 Prompt、配置非法或未发布时，TrainingJourney 必须不给可执行 AI Coach `next_action` 或返回 disabled action；learner 首页、商务技巧页和结果页不得前端合成入口。直达 `/sales-trainer/business-skills/coach` 必须显示明确不可用错误。
- 考试结果页只在 TrainingJourney 返回可执行 AI Coach `next_action` 时展示 AI 教练入口；不得只因 legacy `ai_coach_availability.available=true` 展示入口。

管理入口与路由：

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| `GET` | `/api/v1/admin/newcomer-training/modules/{module_key}/ai-coach/config` | 读取模块 AI 教练配置 | `sales_trainer.manage_modules` |
| `PUT` | `/api/v1/admin/newcomer-training/modules/{module_key}/ai-coach/config` | 保存 AI 教练配置到路径待发布修订 | 普通字段 `sales_trainer.manage_modules`；高风险字段和 Prompt 绑定 `sales_trainer.manage_prompts` |
| `POST` | `/api/v1/admin/newcomer-training/modules/{module_key}/ai-coach/config/publish` | 发布包含 AI 教练配置的路径修订 | `sales_trainer.manage_modules`；若待发布修订涉及高风险字段还需 `sales_trainer.manage_prompts` |
| `POST` | `/api/v1/admin/newcomer-training/path-config/publish/preview` | 预览当前 working revision 发布后的影响范围，不移动 active pointer | `sales_trainer.manage_modules`；若待发布修订涉及高风险字段还需 `sales_trainer.manage_prompts` |
| `GET` | `/api/v1/admin/newcomer-training/path-config/dead-data-diagnostics` | 只读扫描 active/working path revision 与历史训练记录中的缺失、归档、legacy 快照问题 | `sales_trainer.manage_modules` |
| `POST` | `/api/v1/admin/newcomer-training/path-config/rollback/preview` | 预览路径修订回滚影响范围，不移动 active pointer | `sales_trainer.manage_modules`；若涉及 AI 教练高风险字段还需 `sales_trainer.manage_prompts` |
| `POST` | `/api/v1/admin/newcomer-training/path-config/rollback` | 回滚路径修订，包含 AI 教练配置回滚 | `sales_trainer.manage_modules`；若回滚涉及高风险字段还需 `sales_trainer.manage_prompts` |

`GET/PUT/POST /api/v1/admin/newcomer-training/path-config*` 的 `data` 必须包含治理诊断字段：

```typescript
interface NewcomerPathConfigResponse {
  source: "active_revision" | "legacy_migration_snapshot";
  fallback_reason?: "active_revision_missing" | null;
  legacy_snapshot_only: boolean;
  management_entry: "/admin/newcomer-training/path-config";
  permission: "sales_trainer.manage_modules";
  path: NewcomerPathConfigPayload;
  active_revision_id?: string | null;
  active_revision_no?: number | null;
  active_revision_snapshot?: Record<string, unknown> | null;
  working_revision_id?: string | null;
  working_revision_no?: number | null;
  has_unpublished_revision: boolean;
  diagnostics: {
    surface_key: "newcomer_training_path_v1";
    resource_type: "newcomer_training_path";
    source: "active_revision" | "legacy_migration_snapshot";
    legacy_snapshot_only: boolean;
    fallback_applied: boolean;
    fallback_reason?: "active_revision_missing" | null;
    realtime_provider_readiness: Array<{
      module_key: "realtime_roleplay" | "realtime_roleplay_placeholder";
      module_type: "realtime_roleplay" | "realtime_placeholder";
      title: string;
      enabled: boolean;
      runtime_descriptor_id?: string | null;
      provider_readiness_snapshot?: {
        provider: "stepfun_realtime" | "legacy" | "mock";
        ready: boolean;
        checked_at: string;
        config_revision_id?: string | null;
        failure_code?: string | null;
        failure_message?: string | null;
      } | null;
      ready: boolean;
      failure_code?: string | null;
      failure_message?: string | null;
    }>;
    permission_policy: {
      view: "sales_trainer.manage_modules";
      save: "sales_trainer.manage_modules";
      publish: "sales_trainer.manage_modules";
      rollback: "sales_trainer.manage_modules";
      high_risk_ai_coach: "sales_trainer.manage_prompts";
      regrade: "sales_trainer.regrade_history";
    };
    high_risk_actions: {
      publish: { requires_reason: true; requires_trace_id: true; audit_action: "newcomer_path_config.publish"; impact_scope: "future_learners_only"; preview_endpoint: "/api/v1/admin/newcomer-training/path-config/publish/preview" };
      rollback: { requires_reason: true; requires_trace_id: true; audit_action: "newcomer_path_config.rollback"; impact_scope: "future_learners_only"; preview_endpoint: "/api/v1/admin/newcomer-training/path-config/rollback/preview" };
      regrade: { requires_reason: true; requires_trace_id: true; audit_action: "historical_regrade.completed"; impact_scope: "append_only_history"; history_overwrite: false };
    };
  };
}
```

active revision 是 learner 路径、TrainingJourney、模块入口和训练记录上下文的唯一真源。无 active revision 时，learner API 必须返回 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]` 或空 journey 诊断，不得从旧 `SalesTrainerUnit.config.path` 生成正式路径、正式模块入口或正式训练状态。

旧 `SalesTrainerUnit.config.path` / `unit_backfill` 只允许在管理端迁移、诊断或历史回放说明中以 `source="legacy_migration_snapshot"` 暴露，且必须返回 `legacy_snapshot_only=true`、`fallback_reason="active_revision_missing"`、`active_revision_snapshot=null`。一旦发布路径配置，管理端与学员端均以 active revision 为真源，返回 `legacy_snapshot_only=false`，不得再从 latest unit 配置重新拼接已发布路径。

Legacy fallback 只读语义：

- `legacy_migration_snapshot` 是管理端迁移/诊断读面，不是 learner fallback。它不得提供可点击 learner module action，不得触发 `/api/v1/practice/sessions`，不得生成 realtime outcome。
- `realtime_roleplay_placeholder` 只兼容历史 disabled 配置；新 active revision 不得把 placeholder 当作可运行 realtime 模块发布。
- 历史记录无法绑定 active/path revision 时只能返回 `legacy_snapshot_only=true` 或 `regrade_unavailable=true`；不得从 latest active revision 伪造历史 `path_revision_id`、`module_key` 或 roleplay contract hash。

Dead data 诊断 Response:

```typescript
interface NewcomerDeadDataDiagnosticsResponse {
  mode: "dry_run";
  mutates_history: false;
  requires_manual_approval: true;
  permission: "sales_trainer.manage_modules";
  generated_at: string;
  summary: {
    total: number;
    error: number;
    warning: number;
    info: number;
  };
  scanned: {
    active_revision_id?: string | null;
    working_revision_id?: string | null;
    revisions: Array<{
      source: "active_revision" | "working_revision";
      revision_id: string;
      revision_no: number;
      status: "working" | "published" | "archived";
    }>;
    audio_submissions: {
      scanned: number;
      total: number;
    };
    materials: {
      materials: number;
      versions: number;
      total_materials: number;
      total_versions: number;
      limit: number;
      truncated: boolean;
    };
    audio_scan_limit: number;
    material_scan_limit: number;
  };
  issues: Array<{
    severity: "info" | "warning" | "error";
    code:
      | "TARGET_UNIT_NOT_PUBLISHED"
      | "LEARNING_CONTENT_BINDING_MISSING"
      | "LEARNING_CONTENT_NOT_PUBLISHED"
      | "EXAM_PAPER_BINDING_MISSING"
      | "EXAM_PAPER_NOT_PUBLISHED"
      | "MATERIAL_NOT_ACTIVE"
      | "MATERIAL_VERSION_NOT_PUBLISHED"
      | "MATERIAL_VERSION_MISMATCH"
      | "AUDIO_SCORING_PROMPT_MISSING"
      | "AUDIO_SCORING_PROMPT_NOT_PUBLISHED"
      | "ACTIVE_REVISION_MISSING"
      | "PATH_REVISION_PAYLOAD_INVALID"
      | "AUDIO_PROMPT_SNAPSHOT_MISSING"
      | "AUDIO_SCORE_SCHEME_SNAPSHOT_MISSING"
      | "AUDIO_SCORE_RESULT_MISSING"
      | "AUDIO_SCORE_TRANSCRIPT_SNAPSHOT_MISSING"
      | "AUDIO_SCORE_PROMPT_REVISION_MISSING"
      | "AUDIO_SCORE_PROMPT_REVISION_NOT_FOUND"
      | "AUDIO_SUBMISSION_LINEAGE_MISSING"
      | "AUDIO_SUBMISSION_PATH_REVISION_NOT_FOUND"
      | "HISTORICAL_MATERIAL_REPLAY_MISSING_REFERENCE"
      | "HISTORICAL_MATERIAL_REPLAY_MISSING_FILE"
      | "MATERIAL_SNAPSHOT_MISSING"
      | "MATERIAL_CURRENT_VERSION_MISSING"
      | "MATERIAL_CURRENT_VERSION_NOT_PUBLISHED"
      | "ORPHAN_MATERIAL"
      | "ORPHAN_MATERIAL_VERSION"
      | "LEARNING_CONTENT_CHAPTERS_MISSING";
    source:
      | "path_config"
      | "active_revision"
      | "working_revision"
      | "audio_submission"
      | "material_inventory";
    revision_id?: string | null;
    revision_no?: number | null;
    module_key?: string | null;
    resource_type: string;
    resource_id?: string | null;
    message: string;
    metadata: Record<string, unknown>;
  }>;
  candidate_actions: Array<{
    issue_code: string;
    source: string;
    resource_type: string;
    resource_id?: string | null;
    action:
      | "repair_path_revision_before_publish"
      | "restore_or_replace_asset_reference"
      | "preserve_read_only_replay_and_mark_legacy"
      | "repair_material_inventory"
      | "review_archive_candidate"
      | "manual_review_required";
    reason: string;
    mutates_history: false;
    safe_to_apply_automatically: false;
    requires_manual_approval: true;
  }>;
  manual_decisions: Array<{
    decision_key:
      | "legacy_history_backfill_policy"
      | "orphan_asset_retention_policy"
      | "active_path_repair_policy";
    owner: "product_ops" | "training_admin" | string;
    required_before:
      | "production_backfill"
      | "archive_or_delete_assets"
      | "next_publish_or_learner_release"
      | string;
    issue_codes: string[];
    reason: string;
  }>;
  rollback_plan: {
    required: false;
    reason: "diagnostics_only_no_mutation";
    apply_endpoint: null;
    rollback_endpoint: null;
  };
}
```

该接口是只读诊断，禁止自动归档、自动回填、自动重评或修改 active pointer。`AUDIO_PROMPT_SNAPSHOT_MISSING`、`AUDIO_SCORE_PROMPT_REVISION_MISSING`、`AUDIO_SCORE_PROMPT_REVISION_NOT_FOUND`、`AUDIO_SUBMISSION_LINEAGE_MISSING` 与 `AUDIO_SUBMISSION_PATH_REVISION_NOT_FOUND` 必须携带 `legacy_snapshot_only=true` 或 `regrade_unavailable=true`，提示历史重评、Journey 回放或 Prompt 复盘只能按 legacy 只读证据处理；`HISTORICAL_MATERIAL_REPLAY_MISSING_REFERENCE` 表示历史材料快照里存在 version，但训练记录缺少 `confirmed_material_version_id`，对象级历史回放必须 fail-closed 并进入人工回填决策；`HISTORICAL_MATERIAL_REPLAY_MISSING_FILE` 表示本地材料文件不存在，历史回放会 fail-closed。材料历史回放仍以训练记录冻结的 `confirmed_material_version_id` 为准。
材料库存诊断按 `updated_at desc` 做 newest-first 限量扫描，默认 `material_scan_limit=1000`。当 `scanned.materials.truncated=true` 时，`ORPHAN_MATERIAL` / `ORPHAN_MATERIAL_VERSION` 只能作为采样预览，生产归档或回填审批前必须调大 `material_scan_limit` 或分批导出；服务必须额外解析已扫描历史提交中的 `confirmed_material_version_id`，避免引用版本落在扫描切片外时误报 `ORPHAN_MATERIAL`。
`candidate_actions` 仅作为 dry-run 处置建议，所有项必须返回 `mutates_history=false`、`safe_to_apply_automatically=false`、`requires_manual_approval=true`。生产回填、资产归档或 active path 修复前必须先处理 `manual_decisions`，并保留独立审批、影响条数和回滚证据。

发布预览 Response:

```typescript
interface NewcomerPathPublishPreviewResponse {
  action: "newcomer_path_config.publish";
  permission: "sales_trainer.manage_modules";
  requires_reason: true;
  requires_trace_id: true;
  future_only: true;
  risk_level: "low" | "medium" | "high";
  risk_reasons: string[];
  change_class: "non_semantic" | "semantic" | "binding" | "scoring_high_risk";
  target_revision_id: string;
  target_revision_no: number;
  target_revision_status: "working";
  impact_scope: {
    active_revision_id?: string | null;
    working_revision_id: string;
    will_change_active_revision: boolean;
    future_learner_paths_changed: boolean;
    historical_attempts_changed: false;
    historical_submissions_changed: false;
    historical_regrade_required: false;
    affected_module_keys: string[];
    changed_module_keys: string[];
    path_fields_changed: Array<"title" | "goal_title" | "description">;
    changed_ai_coach_high_risk_fields: string[];
    realtime_provider_readiness: Array<{
      module_key: "realtime_roleplay" | "realtime_roleplay_placeholder";
      module_type: "realtime_roleplay" | "realtime_placeholder";
      title: string;
      enabled: boolean;
      runtime_descriptor_id?: string | null;
      provider_readiness_snapshot?: {
        provider: "stepfun_realtime" | "legacy" | "mock";
        ready: boolean;
        checked_at: string;
        config_revision_id?: string | null;
        failure_code?: string | null;
        failure_message?: string | null;
      } | null;
      ready: boolean;
      failure_code?: string | null;
      failure_message?: string | null;
    }>;
    rollback_available: boolean;
  };
  before_snapshot?: Record<string, unknown> | null;
  after_snapshot: Record<string, unknown>;
  audit_event: {
    action: "newcomer_path_config.publish";
    target_type: "newcomer_path_config";
    target_id: "newcomer_training_path_v1";
    required_fields: Array<"actor_id" | "reason" | "trace_id" | "before_revision_id" | "after_revision_id" | "impact_scope">;
  };
  rollback_hint: {
    available: boolean;
    preview_endpoint?: "/api/v1/admin/newcomer-training/path-config/rollback/preview" | null;
    target_revision_id?: string | null;
    target_revision_no?: number | null;
    message: string;
  };
}
```

发布预览约束：

- 预览只读取当前 `working revision`，不得写操作日志、不得移动 active pointer、不得伪造 publish 成功。
- 无 `working revision` 时返回 `[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]`，message 固定说明“必须先保存待发布修订，禁止从 legacy backfill 直接发布/预览发布”。
- 预览必须复用真实发布前校验：坏 payload、失效 PromptTemplate 绑定、非法 realtime placeholder/runtime binding、缺失已发布单元/材料/考卷/学习内容等都必须 typed fail。
- 实时模块 provider readiness 必须在配置诊断和发布预览影响范围里结构化投影。`ready=false` 仍然必须 fail-closed，返回 `[NEWCOMER_REALTIME_PROVIDER_NOT_READY]`，管理端不得把失败降级成 placeholder 成功。
- `after_snapshot` 表示即将被发布的 working revision 当前快照；真正 publish 后仍沿用该 revision_id，只是状态从 `working` 变为 `published`。
- `rollback_available=true` 仅表示当前存在可作为“上一版”的 active published revision；管理端如需回退，必须先调用 rollback preview，再提交 rollback reason。

回滚预览 Response:

```typescript
interface NewcomerPathRollbackPreviewResponse {
  action: "newcomer_path_config.rollback";
  permission: "sales_trainer.manage_modules";
  requires_reason: true;
  requires_trace_id: true;
  future_only: true;
  target_revision_id: string;
  target_revision_no: number;
  target_revision_status: "published";
  impact_scope: {
    active_revision_id?: string | null;
    target_revision_id: string;
    will_change_active_revision: boolean;
    future_learner_paths_changed: boolean;
    historical_attempts_changed: false;
    historical_submissions_changed: false;
    historical_regrade_required: false;
  };
  before_snapshot?: Record<string, unknown> | null;
  after_snapshot: Record<string, unknown>;
  audit_event: {
    action: "newcomer_path_config.rollback";
    target_type: "newcomer_path_config";
    target_id: "newcomer_training_path_v1";
    required_fields: Array<"actor_id" | "reason" | "trace_id" | "before_revision_id" | "after_revision_id" | "impact_scope">;
  };
}
```

Learner AI 教练会话路由：

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/newcomer-training/ai-coach/chat/sessions` | 创建或恢复 Chatbot 式 AI 教练 session，返回训练局 snapshot |
| `POST` | `/api/v1/newcomer-training/ai-coach/chat/sessions/stream` | 创建或恢复 Chatbot 式 AI 教练 session，以 SSE 返回阶段状态和 session snapshot |
| `GET` | `/api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}` | 读取本人 AI 教练 chat session、messages 和 ui_events |
| `POST` | `/api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}/messages` | 发送自由文本或标准训练命令，后端生成 assistant 文本和白名单 UI events |
| `POST` | `/api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}/messages/stream` | 发送自由文本或标准训练命令，以 SSE 返回保存、生成和 session snapshot |
| `POST` | `/api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}/events/{event_id}/answer` | 提交某张 quiz_card 的答案；后端评分、更新 `coach_state`，并在允许时自动生成一个 `next_coach_action` 对应的 assistant message + UI events，返回更新后的 session snapshot |
| `POST` | `/api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}/events/{event_id}/answer/stream` | 提交某张 quiz_card 的答案，以 SSE 先返回 `answer_scored` snapshot，再返回下一步生成状态和最终 snapshot |
| `POST` | `/api/v1/newcomer-training/ai-coach/sessions` | 兼容旧逐题 session；不作为商务技巧 Chatbot 页面主入口 |
| `GET` | `/api/v1/newcomer-training/ai-coach/sessions/{session_id}` | 兼容旧逐题 session 和 public turns |
| `POST` | `/api/v1/newcomer-training/ai-coach/sessions/{session_id}/turns/{turn_id}/submit` | 兼容旧逐题提交 |

Chatbot runtime 输出契约：

```ts
type AiCoachTrainingCardTypeV1 =
  | "scenario_judgment"   // 场景判断卡：判断做法是否合适
  | "expression_rewrite"  // 改写卡：改写不专业表达，必须 short_answer
  | "role_response";      // 角色回应卡：写出对客户/领导/同事的回应，必须 short_answer

type AiCoachInteractionPublicV1 = {
  schema_version: "ai_coach_interaction_public_v1";
  interaction_id: string;
  session_id: string;
  turn_number: number;
  training_card_type: AiCoachTrainingCardTypeV1;
  interaction_type: "single_choice" | "multiple_choice" | "short_answer";
  stem: string;
  options?: Array<{ option_id: string; text: string }> | null;
  answer_constraints: Record<string, number>;
  capability_keys: string[];
  source_chapter_orders: number[];
};

type AiCoachStructuredFeedbackV1 = {
  did_well: string[];
  main_issue: string;
  why_inappropriate: string;
  suggested_response: string;
  next_step: string;
};

type AiCoachChatResponseInternalV1 = {
  schema_version: "ai_coach_chat_response_v1";
  assistant_text: string;
  ui_events: Array<{
    type: "quiz_card" | "explanation_card" | "summary_card" | "followup_prompt";
    payload: unknown;
  }>;
};
```

Chat-First 运行时语义：

- 后端提示词必须让 AI 先判断本轮动作：自然聊天、解释、追问、调用练习工具、批改后反馈或结束总结。普通聊天允许只返回 `assistant_text`，不得为了推进流程强行生成题。
- AI 教练生成链路必须在调用 LLM 时传入 OpenAI-compatible `response_format={"type":"json_object"}`，这是调用级约束，不写入全局模型配置，避免影响报告、普通文本生成等非 JSON 消费方。
- `quiz_card` 是工具调用结果，不是固定下一步。需要检测概念理解时可生成 `scenario_judgment` 单选/多选；需要表达训练时可生成 `expression_rewrite` 或 `role_response` 简答卡。
- 每个 assistant turn 最多 1 张 `quiz_card`；如果 active pending `quiz_card` 已存在，AI 应优先解释当前卡或回答问题，除非用户明确换题或后端动作要求切换。
- `mixed_drill` 表示“由教练判断是否调用练习工具”，不等同于随机出选择题。
- 简答卡提交必须调用 `scoring_prompt_template_id` 对应的评分 Prompt 和模型；不得使用前端规则、文本长度或静态答案直接冒充 AI 评分。

Learner public projection:

- 创建 session 请求：
  - `module_key: string`
  - `resume_strategy?: "latest_active_or_new" | "latest_in_progress" | "new" | null`；未传或传 `null` 时后端读取模块配置 `entry_resume_policy`。商务技巧学员页默认显式传 `latest_active_or_new`，只恢复仍有 active pending `quiz_card` 的训练局；总结态、已结束态或无可答题卡的旧会话必须新开。
  - 点击“继续当前局”传 `latest_in_progress`；点击“新开一局”传 `new`。新开或继续期间前端必须保留旧页面状态并渲染流式进度，不得清空成无反馈等待。
- 发送 message 请求：
  - 自由文本：`content: string`
  - 标准训练命令：`command: "continue" | "explain" | "switch_scenario" | "summarize" | "end" | "retry"`，可附 `event_id`。
  - `command` 存在时，后端按确定性 `next_coach_action` 分支推进，不把按钮文案当自然语言意图猜测。
- `messages[]` 只包含 `message_id`、`role`、`content`、`order_index`、`created_at`。
- `ui_events[]` 只包含 `event_id`、`message_id`、`type`、`status`、public `payload`、`answer_payload`、`score_result`、`order_index`、`created_at`。
- `score_result` 的 `score/max_score` 是后端状态机使用的内部掌握度数值；学员选择题界面不得裸展示为 `100 / 100` 考试分。后端必须同时返回 `mastery_threshold` 与 `mastered`（旧历史数据可缺失），前端以“答对/未掌握/达到掌握标准”解释结果。
- `coach_state` 只包含 `session_phase`、`active_event_id`、`auto_step_count`、`answered_card_count`、`correct_streak`、`incorrect_streak`、`current_focus`、`difficulty`、`last_action`、`can_auto_advance`、`stopped_reason`，以及商务礼仪模块可选的 `business_etiquette_progress`。不得返回内部分数累计、prompt、answer key、scoring rubric 或配置快照。
- `session_phase` 由后端 projection 派生，取值为 `"starting" | "answering" | "reviewing" | "choosing" | "summarizing" | "completed"`。
- `active_event_id` 只指向当前可操作的 pending `quiz_card`；没有待答题卡时为 `null`。前端可用第一张 pending `quiz_card` 做兼容兜底，但不得把多张 pending 题卡同时作为主流程展示。
- `quiz_card.payload.interaction` 使用 `AiCoachInteractionPublicV1`，不得暴露 `answer_key`、`scoring_rubric`、`source_evidence`、Prompt ID、revision、hash 或内部 snapshot。
- `quiz_card.payload.interaction.training_card_type` 必须落在 `allowed_training_card_types` 白名单内；不允许值返回 `[AI_COACH_TRAINING_CARD_TYPE_NOT_ALLOWED]`。
- `expression_rewrite` 和 `role_response` 只能使用 `short_answer`，否则运行时 schema 校验失败并返回 `[AI_COACH_INTERACTION_INVALID:*]`。
- Prompt 编译变量必须包含 `allowed_training_card_types`、`training_card_contract`、`feedback_schema`、当前模块 `learning_units` 与能力点 key。业务服务只传上下文给 PromptTemplateService，不直接拼接裸 prompt 或绕过 contract hash。
- `score_result.structured_feedback` 可按 `AiCoachStructuredFeedbackV1` 返回结构化反馈；若旧历史数据缺失，前端可退回展示 `feedback` 字符串。新 prompt 的评分反馈必须覆盖“你做对了什么、主要问题、为什么不合适、可以怎么说、下一步”五段。
- `summary_card.payload` 除 `title`、`items` 外，可包含 `score_percent`、`mastered`、`strengths`、`weaknesses`、`next_steps`。
- 商务礼仪工作台前端必须调用 `GET /api/v1/newcomer-training/business-etiquette/learning-units` 读取小单元和能力点配置，并用 active/最近训练卡的 `capability_keys` 与 `source_chapter_orders` 匹配当前小单元。匹配不到时只显示“商务礼仪综合训练”兜底，不在前端生成能力点或伪造单元配置。
- 工作台反馈区优先展示最近已评分训练卡的 `score_result.structured_feedback`；结束面板优先展示 `summary_card.payload.mastered / weaknesses / next_steps`，没有 summary 时退回最近评分卡的掌握状态和下一步建议。
- 后端只接受 `allowed_ui_event_types` 中的事件类型；未知类型返回 `[AI_COACH_UI_EVENT_TYPE_NOT_ALLOWED]` 或 `[AI_COACH_INTERACTION_INVALID:*]`。
- 单轮 `quiz_card` 数量超过 `max_cards_per_message` 时返回 `[AI_COACH_INTERACTION_INVALID]`。
- `next_coach_action` 生成结果还必须满足动作级 UI 约束；不匹配时返回或记录 `[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]`：
  - `continue_drill` / `increase_difficulty`：最多生成 1 张 `quiz_card`，可附 1 个 `followup_prompt`；也允许只用 `assistant_text` 解释或追问。
  - `remediate`：最多生成 1 张 `explanation_card` 和 1 张 `quiz_card`，可附 1 个 `followup_prompt`。
  - `switch_scenario`：最多生成 1 张 `quiz_card` 或 1 张 `explanation_card`，可附 1 个 `followup_prompt`。
  - `summarize`：必须生成 1 张 `summary_card`，可附 1 个 `followup_prompt`，不得生成新题。
  - `ask_user_choice`：必须只生成 1 个 `followup_prompt`。
  - `end_session`：必须只生成 1 张 `summary_card`。
- `plan_and_first_card` 作为兼容旧配置仍可用，但也必须满足 `continue_drill` 的动作级 UI 约束，只生成 1 张首题卡。商务礼仪默认使用 `plan_then_wait`，先欢迎和对话，再按需调用练习工具。
- 提交 `quiz_card` 答案时，后端先持久化答案、评分和 `ai_coach_chat_card_submitted_v1` 操作日志，再调用 LLM 生成下一步，避免 LLM 调用期间持有评分事务。
- `failure_behavior="abort"` 时，下一步生成失败会记录 `sales_trainer_ai_coach_coach_actions.status="failed"` 和 `ai_coach_chat_next_action_failed_v1` 操作日志，并向 API 调用方返回 typed error；`skip_turn` / `continue_with_fallback` 时，评分保留，追加安全 `followup_prompt`，同样记录 failed action 和 error_code。
- `chat_enabled=false`、`enabled=false`、缺少生成 Prompt、配置非法或 prompt revision 不可用时，直达 chat URL 显示明确不可用/不可重试错误；前端不得展示旧考试页替代。

SSE 流式响应契约：

- 以上三个 `*/stream` 端点返回 `Content-Type: text/event-stream`。
- 每个 frame 的 `event` 与 JSON `data.type` 一致，取值为 `"status" | "reasoning_text_delta" | "assistant_text_delta" | "ui_event_delta" | "session_snapshot" | "error"`。
- `status` frame：
  - `phase: "resolving_session" | "creating_session" | "session_ready" | "saving_user_message" | "scoring_answer" | "answer_scored" | "deciding_next_action" | "generating_first_card" | "generating_next_card" | "completed" | "failed"`
  - `message: string`
  - `session_id?: string | null`
- `reasoning_text_delta` frame：
  - 仅用于透传模型供应商显式返回的推理文本。DeepSeek OpenAI-compatible 流式响应读取 `chunk.choices[0].delta.reasoning_content`；不得用前端假步骤、`assistant_text` 或 raw prompt 冒充。
  - `text` 是 reasoning 增量文本；前端可以折叠或限制高度展示，不能当作可提交训练证据，也不能写入最终 assistant message。
- `assistant_text_delta` frame：
  - 用于流式预览 AI 教练正文，通常出现在 `phase="generating_first_card"` 或 `phase="generating_next_card"`。
  - `text` 是当前已可公开展示的 `assistant_text` 增量快照，可包含 Markdown；前端必须按安全 Markdown 渲染，不能执行 HTML、JSX、脚本或组件树。
  - `assistant_text_delta` 是最终回复预览，不是思考过程；前端不得把它标记为「思考过程」。
- `ui_event_delta` frame：
  - 用于 AI 教练生成中可渲染预览，只能出现在 `phase="generating_first_card"` 或 `phase="generating_next_card"`。
  - 商务技巧 AI 教练默认可以不发送 `ui_event_delta`；当模型输出仍待后端完整 JSON 解析与契约校验时，后端必须等待最终 `session_snapshot`，不得把半截题卡草稿展示给学员。
  - `event_type="quiz_card"`，`status="streaming"`，`delta_id` 在同一次生成内稳定。
  - `payload.interaction` 使用 `ai_coach_interaction_public_draft_v1`，只允许公开渲染字段：`training_card_type`、`interaction_type`、`stem`、`options.option_id`、`options.text`、`answer_constraints`、`capability_keys`、`source_chapter_orders`、`is_complete=false`。
  - `ui_event_delta` 不代表已持久化事件，前端必须禁用作答、提交、评分；只有最终 `session_snapshot.ui_events[].event_id` 才能作为提交答案的目标。
  - `ui_event_delta` 严禁携带 `answer_key`、`scoring_rubric`、`source_evidence`、raw prompt、raw model output 或任意可执行组件树。
- `session_snapshot` frame：
  - `phase` 使用同一 phase 集合。
  - `session` 等同普通 JSON 接口返回的 `AiCoachChatSessionPublicV1`。
- `error` frame：
  - `phase="failed"`
  - `error_code: string`
  - `message: string`
  - `recoverable: boolean`
- 答题流必须先提交并持久化评分，再发送 `phase="answer_scored"` 的 `session_snapshot`。当 `proactive_coaching_enabled && auto_advance_enabled` 同时为 `true` 时，才允许进入 `deciding_next_action` / `generating_next_card`；默认手动节奏下应直接返回 `phase="completed"`，由学员点击“继续下一题 / 讲解一下 / 换个场景 / 总结本轮”后再触发下一次生成。
- 当 LLM 自由文本回复没有返回任何白名单 `ui_events` 时，后端必须追加配置化 `followup_prompt`，`prompts` 来自 `empty_response_recovery_prompts`；若 `assistant_text` 为空，则使用 `empty_response_recovery_message`。不得让页面停在只有“开始一道题目”但没有题卡或动作的状态。
- 答题已评分后，如果下一步动作生成超过 `generation_timeout_seconds`，后端必须回滚被取消的生成事务并通过 AI Coach 服务层记录失败 action。随后返回 `phase="completed"` 的 `session_snapshot`，其中包含来自 `generation_failure_recovery_message` / `generation_failure_recovery_prompts` 的可恢复 followup；不得只返回红色 error frame 让学员卡在当前局。
- 当 `streaming_enabled=false` 时，SSE 端点返回 `error` frame，`error_code="[AI_COACH_STREAMING_DISABLED]"`；普通 JSON 端点保持兼容。

## 统一响应

成功:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "message": null,
  "trace_id": "trace-xxx"
}
```

失败:

```json
{
  "success": false,
  "data": null,
  "error": "[ERROR_CODE]",
  "message": "Human readable message",
  "trace_id": "trace-xxx"
}
```

## 核心 DTO

### `SalesTrainerUnit`

```typescript
interface SalesTrainerUnit {
  unit_id: string;
  name: string;
  description?: string | null;
  unit_type: "quiz" | "audio_scoring";
  config: {
    audio?: {
      scoring_prompt_id?: string;
      pass_threshold?: number;
      purpose?: string;
    };
    task_brief?: {
      enabled?: boolean;
      title?: string | null;
      purpose?: string | null;
      scenario?: string | null;
      instructions?: string[];
      success_criteria?: string[];
      common_mistakes?: string[];
      upload_guidance?: string | null;
    };
    materials?: {
      require_latest_confirmation?: boolean;
      bindings?: Array<{
        material_id: string;
        required?: boolean;
        confirmation_required?: boolean;
        version_policy?: "current_published" | "locked_version";
        locked_version_id?: string | null;
        display_order?: number;
        learner_note?: string | null;
      }>;
    };
    quiz?: {
      shuffle_questions?: boolean;
      enabled_question_types?: QuestionType[];
    };
    [key: string]: unknown;
  };
  status: "draft" | "published" | "archived";
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
  questions: UnitQuestion[];
}

interface UnitRevision {
  revision_id: string;
  revision_no: number;
  status: "working" | "published" | "archived";
  change_class: "non_semantic" | "semantic" | "binding" | "scoring_high_risk";
  title?: string | null;
  question_count: number;
  is_active: boolean;
  is_working: boolean;
  source_revision_id?: string | null;
  payload_hash: string;
  reason?: string | null;
  trace_id?: string | null;
  created_by?: string | null;
  published_by?: string | null;
  created_at: string;
  published_at?: string | null;
}
```

### `UnitQuestion`

```typescript
interface UnitQuestion {
  question_id: string;
  order_index: number;
  points: number;
  question_type?: QuestionType;
  prompt?: string;
  options?: Array<{
    option_id: string;
    label: string;
    text: string;
  }>;
}

type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "short_answer";
```

## 新人训练闭环聚合契约

TrainingJourney 是新人训练 learner 首页、模块详情、训练记录、管理看板和 realtime/AI Coach outcome projection 的统一读模型。第一阶段可以实现为 read model projection；无论是否新增表，API 响应都必须以 active path revision 为唯一真源，不允许前端从目录、旧 unit config 或局部记录自行拼状态。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| `GET` | `/api/v1/sales-trainer/journey` | 当前登录学员的新人训练完整 journey | learner 本人 |
| `GET` | `/api/v1/admin/sales-trainer/journeys` | 管理端 journey 列表，支持部门、训练阶段、模块、学员等级筛选；学员等级由 `sales_trainer.learner_level.policy` 投影生成 | `sales_trainer.view_records` / `sales_trainer.view_global_records` |
| `GET` | `/api/v1/admin/sales-trainer/journeys/analytics` | 管理端 journey 聚合分析，返回完成漏斗、模块通过率、历史趋势、学员等级分布、角色 scope 分布、风险学员和 realtime additive observation 诊断聚合；支持按训练阶段、模块、学员等级和角色等级过滤 | `sales_trainer.view_records` / `sales_trainer.view_global_records` |
| `GET` | `/api/v1/admin/sales-trainer/journeys/{learner_id}` | 单个学员 journey 详情和历史证据 | 部门范围或全局记录权限 |
| `GET` | `/api/v1/admin/sales-trainer/readiness/workbench` | 达标验收工作台，按待复核、未达标、需重练、已达标、配置异常、训练中分组 | `sales_trainer.view_records` / `sales_trainer.view_global_records` |
| `GET` | `/api/v1/admin/sales-trainer/readiness/dossiers/{learner_id}` | 单个新人训练达标档案，聚合训练提交证据、AI/规则初评、复核动作、重练任务和 realtime gate | 部门范围或全局记录权限 |
| `POST` | `/api/v1/admin/sales-trainer/readiness/dossiers/{learner_id}/review-actions` | 创建复核动作：确认达标、要求重练或标记人工跟进；动作写入操作日志并作为当前 V0.9 状态源 | 培训负责人 / 全局记录管理员 |

`GET /api/v1/admin/sales-trainer/journeys` query:

```typescript
interface TrainingJourneyListQuery {
  department?: string;
  training_stage?: TrainingStage;
  module_key?: string;
  learner_level?: string; // 精确匹配 TrainingJourney.learner_level.level_key；空字符串按未传处理
  role_level?: string; // 精确匹配 TrainingJourney.role_level.level_key；空字符串按未传处理
  limit?: number; // 1..100, default 50
  offset?: number; // default 0
}

interface TrainingJourneyListResponse {
  items: TrainingJourney[];
  total: number;
  limit: number;
  offset: number;
}
```

`GET /api/v1/admin/sales-trainer/journeys/analytics` query:

```typescript
interface TrainingJourneyAnalyticsQuery {
  department?: string;
  training_stage?: TrainingStage;
  module_key?: string;
  learner_level?: string; // 精确匹配 TrainingJourney.learner_level.level_key；空字符串按未传处理
  role_level?: string; // 精确匹配 TrainingJourney.role_level.level_key；空字符串按未传处理
  limit?: number; // 1..1000, default 500
}

interface TrainingJourneyAnalyticsResponse {
  generated_at: string;
  summary: {
    learner_count: number;
    loaded_learner_count: number;
    passed_learner_count: number;
    risk_learner_count: number;
    pass_rate: number;
  };
  funnel: Array<{
    stage: TrainingStage;
    learner_count: number;
    rate: number;
  }>;
  module_summaries: Array<{
    module_key: string;
    title: string;
    kind: NewcomerModuleType;
    learner_count: number;
    passed_count: number;
    failed_count: number;
    status_counts: Record<string, number>;
    pass_rate: number;
    average_score?: number | null;
  }>;
  weakness_heatmap: Array<{
    heatmap_key: string; // `${module_key}:${kind}`，避免同一 module_key 下文章考卷与 AI Coach 被混聚
    module_key: string;
    title: string;
    kind?: NewcomerModuleType | string | null;
    module_type?: NewcomerModuleType | string | null;
    learner_count: number;
    risk_count: number;
    passed_count: number;
    status_counts: Record<string, number>;
    risk_rate: number | null;
    pass_rate: number | null;
    average_score?: number | null;
  }>;
  trend_data: Array<{
    date: string; // YYYY-MM-DD，取 completed_at，缺失时取 submitted_at
    outcome_count: number;
    passed_outcome_count: number;
    risk_outcome_count: number;
    active_learner_count: number;
    pass_rate: number | null;
    average_score?: number | null;
  }>;
  learner_level_summaries: Array<{
    key: string;
    label: string;
    learner_count: number;
    passed_count?: number;
    pass_rate?: number;
    source?: LearnerLevelSource | string | null;
  }>;
  role_level_summaries: Array<{
    key: string;
    label: string;
    learner_count: number;
    passed_count?: number;
    pass_rate?: number;
    source?: LearnerLevelSource | string | null;
  }>;
  risk_learners: Array<{
    learner_id: string;
    learner_name?: string | null;
    department?: string | null;
    training_stage: TrainingStage;
    risk_reasons: string[];
    risk_module_count: number;
    risk_module_keys?: string[];
  }>;
  additive_observation: {
    storage_ready: boolean;
    migration_applied: boolean;
    session_count: number;
    observed_session_count: number;
    observation_count: number;
    source_counts: Record<string, number>;
    status_counts: Record<string, number>;
    top_signal_keys: Array<{
      key: string;
      count: number;
    }>;
    high_risk_session_count: number;
    latest_observed_at?: string | null;
  };
  filters: {
    department?: string | null;
    training_stage?: TrainingStage | null;
    module_key?: string | null;
    learner_level?: string | null;
    role_level?: string | null;
    limit: number;
  };
}
```

首个后端切片约束：

- 部门 scope 后端 fail-closed：部门经理即使传入其他部门，也只返回空列表，不泄露跨部门学员。
- `limit` 是 analytics 聚合加载上限：后端不得先构建全量 Journey 再截断。`summary.learner_count` 表示部门/基础候选总数；`summary.loaded_learner_count` 表示本次实际加载并参与图表聚合的 Journey 数。
- `training_stage`、`module_key`、`learner_level` 和 `role_level` 是 read-model 过滤；过滤存在时 `summary.learner_count` 表示本次已加载数据的过滤结果，后续如需全量精确计数应下推到独立投影表。
- `learner_level` 来自后端 `TrainingJourney.learner_level.level_key`，由 `sales_trainer.learner_level.policy` 发布配置投影生成；前端不得本地伪造等级或匹配中文 label。配置缺失、停用或非法时后端必须返回默认 `unassigned`，并暴露 `fallback_applied/fallback_reason`。
- `learner_level_summaries` 当前来自 `TrainingJourney.learner_level`；后端必须返回 `source`，前端不得本地伪造等级。
- `role_level` 来自后端 `TrainingJourney.role_level.level_key`，由 `sales_trainer.role_level.policy` 发布配置投影生成；权限仍由 `role_capabilities` 表达，前端不得把 capability scope 当角色等级。
- `role_level_summaries` 当前来自 `TrainingJourney.role_level`；后端必须返回 `source`，前端不得本地伪造等级。
- 当请求包含 `module_key` 时，`module_summaries`、`weakness_heatmap`、`trend_data` 和 `risk_learners` 必须只基于该模块的 Journey module outcome 聚合；`summary/funnel/level_summaries` 仍表示匹配该模块条件的学员集合。
- `additive_observation` 是附加诊断块，不得替换现有 analytics 字段。它必须只基于 `TrainingJourneyService` 已授权并已加载的 learner/session scope 聚合，禁止裸扫全表后再由前端过滤。
- `additive_observation.session_count` 表示当前已加载 learner scope 下、`voice_policy_snapshot.external_binding.owner="sales_trainer"` 且属于当前 active path revision 的 realtime session 数；`observed_session_count`/`observation_count` 只统计这些 session 的 observation sidecar 行。
- 当请求包含 `module_key` 且不等于 `realtime_roleplay` 时，`additive_observation` 仍返回诊断字段，但 `session_count`、`observed_session_count`、`observation_count`、`top_signal_keys` 和 `high_risk_session_count` 必须为 0。
- `additive_observation.storage_ready=false` 表示 observation sidecar 读取失败或当前环境不可用；`migration_applied=false` 表示 `sales_trainer_roleplay_observations` 表尚未存在。两种情况下主 analytics 仍需返回其他字段，不得因为附加诊断失败而整体报错。
- `additive_observation.top_signal_keys` 按 signal key 出现次数降序返回，key 来自 observation `signals[].key`，兼容旧记录时可回退 `signal_type`。
- `additive_observation.high_risk_session_count` 当前表示至少命中过一次 `severity="high"` 或 `manual_review_required` signal 的 session 数；前端不得自行发明新的高风险判定。
- `risk_learners[].risk_reasons` 由后端基于同一批风险模块生成，当前格式为 `<module_key>:not_passed` 或 `<module_key>:status:<status>`；前端不得用 `risk_module_keys` 冒充风险原因。`risk_module_keys` 仅作为兼容/定位字段保留。
- `weakness_heatmap` 当前由后端基于同一批 Journey module outcome 派生，暴露原始 `risk_count/risk_rate/status_counts/pass_rate/average_score`；风险等级阈值不是本契约的一部分，前端不得本地发明高/中/低业务分层。
- `trend_data` 由后端基于同一批 Journey module outcome 的 `completed_at/submitted_at` 按日聚合，暴露 outcome 事件数、通过事件数、风险事件数、活跃学员数、通过率和平均分；前端不得从单次快照本地反推趋势。

### 训练达标档案 Readiness Dossier

Readiness Dossier 是“每个新人都有一份可信训练达标档案”的 V0.9 聚合读面。它不替代 TrainingJourney、训练记录、素材快照或操作日志；它负责把这些证据按验收任务翻译成：练过什么、提交了什么证据、AI/规则按什么结果初评、哪些能力达标/未达标、是否复核、没达标后是否要求重练。

```typescript
type ReadinessDossierStatus =
  | "not_started"
  | "in_training"
  | "ai_evaluating"
  | "needs_remediation"
  | "pending_review"
  | "approved"
  | "rejected"
  | "manual_follow_up"
  | "blocked_by_config";

type ReadinessReviewDecision =
  | "approve"
  | "require_retraining"
  | "mark_manual_follow_up";

type ReadinessWorkbenchGroupKey =
  | "pending_review"
  | "not_passed"
  | "needs_retraining"
  | "approved"
  | "config_exception"
  | "in_training";

interface ReadinessWorkbenchResponse {
  contract_version: "readiness_dossier_v1";
  generated_at: string;
  groups: Record<ReadinessWorkbenchGroupKey, {
    group_key: ReadinessWorkbenchGroupKey;
    label: string;
    count: number;
    items: Array<{
      learner: { learner_id: string; name?: string | null; department?: string | null };
      status: ReadinessDossierStatus;
      status_label: string;
      status_reason: string;
      weak_capability_keys: string[];
      weak_capability_labels: string[];
      evidence_count: number;
      latest_review_action?: ReadinessDossierReviewAction | null;
      next_action?: ReadinessDossierNextAction | null;
      target_path?: string | null;
    }>;
  }>;
  summary: {
    learner_count: number;
    loaded_learner_count: number;
    pending_review_count: number;
    not_passed_count: number;
    needs_retraining_count: number;
    approved_count: number;
    config_exception_count: number;
    in_training_count: number;
  };
  filters: { department?: string | null; limit: number; offset: number };
}

interface ReadinessDossierResponse {
  contract_version: "readiness_dossier_v1";
  learner: { learner_id: string; name?: string | null; department?: string | null };
  path: {
    path_key?: string | null;
    path_revision_id?: string | null;
    path_revision_no?: number | null;
    source?: string | null;
  };
  status: ReadinessDossierStatus;
  status_label: string;
  status_reason: string;
  summary: {
    total_modules: number;
    completed_modules: number;
    passed_modules: number;
    failed_modules: number;
    needs_remediation_modules: number;
    evidence_count: number;
    review_action_count: number;
    weak_capability_count: number;
    retraining_task_count: number;
    completed_retraining_task_count: number;
    review_state_source: "operation_log";
  };
  modules: Array<{
    module_key?: string | null;
    title?: string | null;
    kind?: string | null;
    module_type?: string | null;
    status?: string | null;
    passed?: boolean | null;
    score?: number | null;
    max_score?: number | null;
    required?: boolean | null;
    completion_satisfied?: boolean | null;
    locked?: boolean | null;
    block_reason?: string | null;
    capability_keys: string[];
    evidence_ids: string[];
    next_action?: { label?: string | null; target_path?: string | null; disabled: boolean; disabled_reason?: string | null } | null;
  }>;
  competencies: Array<{
    capability_key: string;
    display_name: string;
    status: "not_trained" | "ai_passed" | "ai_failed" | "needs_retraining" | "pending_review" | "approved" | "rejected" | "blocked_by_config";
    score?: number | null;
    max_score?: number | null;
    weak: boolean;
    evidence_ids: string[];
    latest_evidence_id?: string | null;
    review_decision?: string | null;
    reason?: string | null;
  }>;
  evidence: Array<{
    evidence_id: string;
    evidence_type: string;
    source_record_id: string;
    record_type: string;
    module_key?: string | null;
    module_title?: string | null;
    capability_keys: string[];
    status?: string | null;
    score?: number | null;
    max_score?: number | null;
    passed?: boolean | null;
    submitted_at?: string | null;
    completed_at?: string | null;
    target_path?: string | null;
    material_snapshot?: Record<string, unknown> | null;
    scoring_snapshot?: Record<string, unknown> | null;
    task_brief_snapshot?: Record<string, unknown> | null;
    snapshot_ref?: Record<string, unknown> | null;
    result_summary?: string | null;
  }>;
  review_actions: ReadinessDossierReviewAction[];
  latest_review_action?: ReadinessDossierReviewAction | null;
  retraining_tasks: ReadinessDossierRetrainingTask[];
  realtime_gate: {
    module_key?: string | null;
    status?: string | null;
    locked: boolean;
    reason?: string | null;
    training_gate_status: ReadinessDossierStatus;
    provider_readiness?: Record<string, unknown> | null;
  };
  diagnostics: TrainingJourneyDiagnostic[];
  next_actions: ReadinessDossierNextAction[];
  generated_at: string;
}

interface ReadinessDossierRetrainingTaskComparison {
  before_evidence_ids: string[];
  after_evidence_ids: string[];
  after_status?: string | null;
  after_passed?: boolean | null;
  after_score?: number | null;
  after_max_score?: number | null;
}

interface ReadinessDossierRetrainingTask {
  task_id: string;
  status: "pending" | "in_progress" | "completed" | string;
  source?: "operation_log" | string | null;
  capability_keys: string[];
  source_evidence_ids: string[];
  target_learner_id?: string | null;
  completed_at?: string | null;
  completed_evidence_ids?: string[];
  comparison?: ReadinessDossierRetrainingTaskComparison | null;
}

interface ReadinessDossierReviewAction {
  action_id: string;
  audit_log_id: string;
  decision: ReadinessReviewDecision;
  decision_label: string;
  reason?: string | null;
  capability_keys: string[];
  source_evidence_ids: string[];
  reviewer_id?: string | null;
  reviewer_role?: string | null;
  created_at: string;
  retraining_task?: ReadinessDossierRetrainingTask | null;
  state_storage: "operation_log";
}

interface ReadinessDossierReviewActionCreateRequest {
  decision: ReadinessReviewDecision;
  reason: string;
  capability_keys?: string[];
  source_evidence_ids?: string[];
}

interface ReadinessDossierNextAction {
  action_key: string;
  label: string;
  target_path?: string | null;
  primary: boolean;
  capability_keys: string[];
}
```

语义约束：

- `readiness_dossier_v1` 第一版为 read-model 聚合；复核状态与重练任务当前采用 `SalesTrainerOperationLog` append-only 存储，`state_storage="operation_log"` 必须显式返回。未来如果迁移到专表，旧日志仍是审计真源。
- `pending_review` 表示前置关键训练证据已齐且 AI/规则初评通过，但尚未人工确认；它不是自动达标。
- `approved` 只能由有复核权限的人工动作产生。`approve` 仅允许在档案状态为 `pending_review` 且 `summary.evidence_count>0` 时提交；未完成训练、证据为空、仍在 AI 评分、需重练或人工跟进时必须返回 `[READINESS_DOSSIER_NOT_READY]`，存在非 realtime 配置阻断时必须返回 `[READINESS_DOSSIER_CONFIG_BLOCKED]`。
- `require_retraining` 必须生成可追踪 `retraining_task` 元数据；任务处于 `pending` 或 `in_progress` 时在 workbench 归入 `needs_retraining` 分组，不得只写一段备注。
- 新人被要求重练后，如产生晚于该复核动作且匹配相关能力项/证据来源的新证据，`retraining_task.status` 必须更新为 `in_progress`（新证据仍在评分）或 `completed`（新证据已可判定）。`completed` 后工作台不再继续归入 `needs_retraining`，而是按新证据回到 `pending_review` 或 `not_passed`；`comparison` 必须给出前后证据数量和重练后通过/得分状态，管理页面只展示用户语言，不展示 raw evidence id。
- realtime 对练是下一阶段 gate：realtime provider 或 runtime binding 异常不得覆盖前置训练档案的达标判断，但 `realtime_gate.locked` 必须解释下一阶段是否仍不可进入。
- `evidence[]` 只展示已授权 scope 内的训练证据，且必须保留材料、评分、任务简报或 path revision 的可追溯快照引用；普通管理页面不得展示 Prompt 原文、模型密钥、trace raw payload。
- `competencies[]` 第一版能力项采用固定代码集合；每个训练模块覆盖哪些固定能力项由 `newcomer_path.modules[].capability_keys` 配置和 active revision 快照决定。缺失旧数据可使用后端兼容映射，但新增/发布配置不得依赖前端按模块名推断能力项。通过线、评分结果、模块启停、题库、材料和 AI Coach 行为必须继续来自后台配置与训练记录，不得由前端写死。
- `source_evidence_ids` 和 `capability_keys` 如传入未知值，后端必须返回 typed error；省略时后端可以基于当前档案选择默认证据和能力项。

```typescript
type LearnerLevelSource =
  | "user_profile"
  | "org_rule"
  | "admin_assignment"
  | "training_projection";

interface LearnerLevel {
  level_key: string;
  label: string;
  source: LearnerLevelSource;
  rank: number;
  effective_from?: string | null;
  effective_to?: string | null;
  config_revision_id?: string | null;
  description?: string | null;
  fallback_applied?: boolean;
  fallback_reason?: string | null;
  policy_key?: string | null;
  policy_version?: string | null;
  management_entry?: string | null;
}

type TrainingStage =
  | "not_started"
  | "in_progress"
  | "waiting_upload"
  | "processing"
  | "scored"
  | "passed"
  | "failed"
  | "needs_remediation"
  | "manual_review"
  | "disabled"
  | "archived"
  | "error_terminal"
  | "error_transient";

interface RoleCapability {
  capability_key:
    | SalesTrainerAdminCapabilityKey
    | "learner_enter"
    | "learner_submit"
    | "learner_view_own_records"
    | "sales_trainer.enter_realtime";
  allowed: boolean;
  scope: "own" | "department" | "global" | "none";
  reason_code?: string | null;
}

type ModuleOutcomeRecordType =
  | "audio_submission"
  | "quiz_attempt"
  | "business_etiquette_quiz_attempt"
  | "ai_coach_session"
  | "realtime_roleplay_session"
  | "remediation"
  | "regrade";

interface ModuleOutcome {
  outcome_id: string;
  record_type: ModuleOutcomeRecordType;
  source_record_id: string;
  module_key: string;
  module_type: NewcomerModuleType;
  status: TrainingStage;
  score?: number | null;
  max_score?: number | null;
  passed?: boolean | null;
  failure_type?: "terminal" | "transient" | "voluntary" | null;
  failure_code?: string | null;
  submitted_at?: string | null;
  completed_at?: string | null;
  path_revision_id: string;
  path_revision_no: number;
  snapshot_ref: {
    snapshot_type: "path_revision" | "submission_snapshot" | "attempt_snapshot" | "session_snapshot" | "runtime_outcome_snapshot";
    legacy_snapshot_only: boolean;
    regrade_unavailable?: boolean;
  };
}

interface ModuleProgress {
  module_key: string;
  module_type: NewcomerModuleType;
  display_name: string;
  order_index: number;
  target_unit_id?: string | null;
  target_unit_ids?: string[];
  learning_content_id?: string | null;
  exam_paper_id?: string | null;
  enabled: boolean;
  stage: TrainingStage;
  completion_rule: NewcomerPathCompletionRule;
  completion_satisfied: boolean; // 完成规则是否满足；不等同于 passed。realtime completion_rule="submitted" 时可为 true 且 passed=null。
  learner_level_required?: string[] | null;
  unmet_reasons: Array<{
    code: string;
    message: string;
    terminal: boolean;
  }>;
  next_action?: {
    action_key:
      | "start_audio_submission"
      | "retry_audio_submission"
      | "start_quiz_attempt"
      | "retry_quiz_attempt"
      | "start_ai_coach"
      | "continue_ai_coach"
      | "start_realtime_roleplay";
    label: string;
    target_path?: string | null;
    disabled: boolean;
    disabled_reason?: string | null;
  } | null;
  latest_outcome?: ModuleOutcome | null;
  outcome_history: ModuleOutcome[];
}

interface TrainingJourneyRetrainingRequest {
  request_id: string; // 稳定 key；普通 learner UI 不展示
  task_id: string; // 重练任务内部追踪 key；普通 learner UI 不展示
  status: string;
  reason?: string | null;
  capability_keys: string[]; // 稳定能力 key；UI 优先展示 capability_labels
  capability_labels: string[];
  source_evidence_count: number;
  target_modules: Array<{
    module_key?: string | null;
    title?: string | null;
    kind?: string | null;
    module_type?: string | null;
    status?: string | null;
    action_label?: string | null;
    target_path?: string | null;
    disabled: boolean;
    disabled_reason?: string | null;
  }>;
  primary_target_path?: string | null;
  created_at: string;
}

interface TrainingJourney {
  journey_id: string;
  learner_id: string;
  learner_name?: string | null;
  department?: string | null;
  path_key: "newcomer_training_path_v1";
  path_revision_id: string;
  path_revision_no: number;
  source: "active_revision";
  legacy_snapshot_only: false;
  role_capabilities: RoleCapability[];
  learner_level: LearnerLevel;
  role_level: LearnerLevel;
  training_stage: TrainingStage;
  modules: ModuleProgress[];
  overall_progress: {
    total_modules: number;
    completed_modules: number;
    passed_modules: number;
    failed_modules: number;
    needs_remediation_modules: number;
  };
  retraining_requests: TrainingJourneyRetrainingRequest[];
  diagnostics: Array<{
    code: string;
    message: string;
    severity: "info" | "warning" | "error";
    terminal: boolean;
  }>;
  generated_at: string;
}
```

约束:

- 权限由 `RoleCapability` 表达，控制谁能看、配、审、重试、重评、看日志和进入 realtime；前端不得复制角色字符串矩阵。
- `target_unit_id` / `target_unit_ids` / `learning_content_id` / `exam_paper_id` 必须来自 active path revision，是 learner 文章学习、考试、AI Coach 上下文的唯一运行绑定真源。`module_key="business_skills"` 会同时出现 `kind="quiz_attempt"` 和 `kind="ai_coach"` 两类模块；前端读取文章/考卷绑定时必须锁定 `kind="quiz_attempt"`，读取 AI Coach 入口时必须使用 `kind="ai_coach"` 的 `next_action`。不得从 `/paths`、`SalesTrainerUnit.config.path` 或 catalog fallback 回填这些运行绑定。
- 角色等级由 `role_level` 表达，来源为 `sales_trainer.role_level.policy`，用于展示、筛选和分析，不等价于权限 scope。
- 学员等级由 `LearnerLevel` 表达，影响内容可见性、模块启用、推荐训练和管理筛选。首版等级来源未冻结时，后端必须在 `source` 和 `config_revision_id` 中暴露来源，不得由前端本地推断。`modules[].learner_level_required` 是后端执行字段：TrainingJourney 必须把不匹配等级的模块置为 locked 并返回 `[NEWCOMER_LEARNER_LEVEL_NOT_ALLOWED]`；learner `/paths` 只能展示同一 locked 状态；直链 unit detail/brief、audio submit、quiz submit 必须复用后端 Journey 判定 fail-closed。
- 训练阶段等级由 `TrainingStage` 表达，前端只渲染后端状态和 `unmet_reasons`，不得自行把 `passed=null` 推断为失败。
- `completion_satisfied` 表示该模块的完成规则是否满足，独立于考核通过语义。`completion_rule="passed"` 必须 `passed=true`；`completion_rule="submitted"` 只要求有受治理的 outcome 记录。前端不得用本地规则重算该字段。
- `ModuleOutcome` 必须覆盖录音、普通试卷、商务礼仪小测、AI Coach、realtime、补救、重评。历史展示 snapshot-first：优先读取记录创建时冻结的 snapshot/revision refs；旧数据只能标记 `legacy_snapshot_only=true`，不得从 latest active revision 伪造历史解释。
- 重评必须以 append-only `ModuleOutcome(record_type="regrade", snapshot_ref.snapshot_type="regrade_snapshot")` 进入对应 audio/quiz 模块的 `outcome_history`。`source_record_id` 指向被重评的原始训练记录，`evidence.record_id` 指向 `sales_trainer_regrade_runs.run_id`；原始 audio/quiz outcome 必须继续保留在 history 中，不得被重评结果覆盖或改写。重评失败或 `after_snapshot.error_code` 存在时 outcome 为 `error_terminal`，成功重评分数按 `after_snapshot.total_score/max_score/passed` 投影。
- `retraining_requests[]` 是管理员达标复核动作对 learner 端的只读投影。来源仍是 `ReadinessDossier` 的 operation-log-backed review state，但 learner UI 只能展示用户语言：补练能力、负责人原因、关联证据数量、可进入的训练模块和入口；不得展示 `operation_log`、审计日志 ID、raw evidence id、Prompt、trace 或模型调试字段。若复核引用了具体证据，`target_modules` 必须优先定位产生该证据的模块；能力项匹配只作为补充。
- PPT 录音、商务技巧考卷、AI Coach 和 realtime 模块都必须通过 `modules[].next_action` 暴露 learner 入口或锁定原因；前端不得回退读取 `/paths`/catalog 来拼接入口。
- AI Coach 是首版完整闭环必过模块。若 active revision 声明 `require_ai_coach=true`，TrainingJourney 必须返回 AI Coach `ModuleProgress` 和达标 outcome；缺 Prompt、坏配置或模型不可用必须返回 typed terminal/transient 状态，不得静默默认通过。
- realtime outcome 只能来自 runtime binding 的 outcome projection。`sales_trainer` 不直接消费 WebSocket 中间态作为通过依据，不从前端连接状态推断完成。
- 首版 outcome projection 从 completed practice session 的 `voice_policy_snapshot.external_binding` 读取冻结路径上下文，并把结果写入 `ModuleOutcome(record_type="realtime_roleplay_session", snapshot_ref.snapshot_type="runtime_outcome_snapshot")`。分数可来自 runtime 写回的会话分数字段；未定义通过阈值时 `passed` 必须保持 `null`，不得把“完成实时会话”伪装成“通过考核”。

### 实时对练 learner start

`POST /api/v1/sales-trainer/realtime-roleplay/start`

请求:

```typescript
interface RealtimeRoleplayStartRequest {
  module_key?: "realtime_roleplay";
}
```

响应:

```typescript
interface RealtimeRoleplayStartResponse {
  session_id: string;
  module_key: "realtime_roleplay";
  path_key: "newcomer_training_path_v1";
  path_revision_id: string;
  path_revision_no: number;
  practice_url: string;
  runtime_descriptor_id: string;
  runtime_registry: RealtimeRoleplayRuntimeRegistrySnapshot;
  provider_readiness_snapshot: {
    provider: "stepfun_realtime" | "legacy" | "mock";
    ready: boolean;
    checked_at: string;
    config_revision_id?: string | null;
    failure_code?: string | null;
    failure_message?: string | null;
  };
  external_binding: RealtimeRoleplayExternalBindingSnapshot;
}

interface RealtimeRoleplayRuntimeRegistrySnapshot {
    registry_key: "sales_trainer.realtime_provider.registry";
    config_id?: string | null;
    version?: number | null;
    source: string;
    status?: string | null;
    fallback_reason?: string | null;
    descriptor: {
      descriptor_id: string;
      label?: string | null;
      provider: "stepfun_realtime" | "phase4_local_stepfun" | "mock";
      runtime_owner: "training_runtime" | "sales_bot";
      enabled: boolean;
      runtime_profile_id?: string | null;
      config_revision_id?: string | null;
      rollback_to_descriptor_id?: string | null;
      readiness: {
        ready: boolean;
        checked_at?: string | null;
        failure_code?: string | null;
        failure_message?: string | null;
      };
    };
}

interface RealtimeRoleplayExternalBindingSnapshot {
  owner: "sales_trainer";
  path_key: "newcomer_training_path_v1";
  path_revision_id: string;
  path_revision_no: number;
  module_key: "realtime_roleplay";
  binding_key: "newcomer_realtime_roleplay_v1";
  runtime_descriptor_id: string;
  scenario_key: string;
  runtime_config_revision_id: string;
  runtime_registry: RealtimeRoleplayRuntimeRegistrySnapshot;
  roleplay_contract_revision_id?: string | null;
  practice_template_id: string;
  provider_readiness_snapshot: {
    provider: "stepfun_realtime" | "legacy" | "mock";
    ready: boolean;
    checked_at: string;
    config_revision_id?: string | null;
    failure_code?: string | null;
    failure_message?: string | null;
  };
  failure_policy: {
    terminal_codes: string[];
    transient_codes: string[];
    voluntary_codes: string[];
    terminal_retry_allowed: false;
  };
  started_by_user_id: string;
  started_at: string;
}
```

约束:

- 该接口只允许具备 `sales_trainer.enter_realtime` 的 active learner 调用；admin、manager、ops 可以查看训练记录和 Journey，但不得替 learner 启动 realtime session。
- learner 还必须命中 active TrainingJourney 中同一 `realtime_roleplay` module 的 module access gate；模块不存在、停用、`learner_level_required` 不匹配或 Journey 因配置错误进入 locked/error_terminal 时返回 404 `[SALES_TRAINER_UNIT_NOT_FOUND]`，不得创建 PracticeSession。
- 接口必须读取 active path revision 的 `realtime_roleplay` module，不得接受前端传入的 runtime binding，也不得从 legacy unit fallback 伪造入口。
- 成功时必须调用 common session 创建权威创建真实 realtime session，并在创建时冻结 `voice_policy_snapshot.external_binding`；不得让前端直接调用 `/practice/sessions` 后再补业务上下文。
- 缺 active revision 返回 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`；缺 binding 或 binding 非法返回 `[NEWCOMER_REALTIME_BINDING_INVALID]`；path snapshot 或 registry readiness 未通过返回 `[NEWCOMER_REALTIME_PROVIDER_NOT_READY]`；registry 停用、缺 descriptor 或 descriptor 停用分别返回 `[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]`、`[NEWCOMER_REALTIME_PROVIDER_DESCRIPTOR_MISSING]`、`[NEWCOMER_REALTIME_PROVIDER_DISABLED]`；权限不足返回 `[NEWCOMER_REALTIME_PERMISSION_DENIED]`。
- `runtime_binding.practice_template_id` 是首版 start API 必需运行条件。若未来希望不用 practice template 启动，必须新增 ADR 扩展 runtime identity 契约。

### `SalesTrainerPath`

Learner 首页使用 `GET /api/v1/sales-trainer/paths` 返回的路径 DTO。`levels[].module_key` 与
`levels[].module_type` 必须来自路径级 active revision。`SalesTrainerPath` 是 legacy 兼容读面；新看板和管理分析应优先使用 `TrainingJourney`。前端不得把 `SalesTrainerUnit.config.path` 当正式兜底，也不能用旧单元配置覆盖 active revision。

```typescript
interface SalesTrainerPath {
  path_key: string;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  title: string;
  goal_title?: string | null;
  total_levels: number;
  completed_levels: number;
  current_level_id?: string | null;
  next_level_id?: string | null;
  levels: SalesTrainerPathLevel[];
  goal_context: SalesTrainerGoalContext;
}

interface SalesTrainerPathLevel {
  unit_id: string;
  name: string;
  description?: string | null;
  unit_type: "quiz" | "audio_scoring";
  module_key?: string | null;
  module_type?: NewcomerModuleType | null;
  learning_content_id?: string | null;
  exam_paper_id?: string | null;
  order_index: number;
  level_title: string;
  level_description?: string | null;
  locked: boolean;
  lock_reason?: string | null;
  status: "locked" | "available" | "in_progress" | "completed";
  completion_rule: "passed" | "scored" | "submitted";
  primary_action_label: string;
  retry_action_label: string;
  review_action_label: string;
  target_path: string;
  ai_coach_availability?: AiCoachAvailability | null;
  latest_result?: unknown | null;
}

type AiCoachInteractionType =
  | "single_choice"
  | "multiple_choice"
  | "short_answer";

interface AiCoachAvailability {
  enabled: boolean;
  configured: boolean;
  available: boolean;
  coach_path?: string | null;
  disabled_reason?: string | null;
  allowed_interaction_types: AiCoachInteractionType[];
}
```

`learning_content_id` 与 `exam_paper_id` 是 article/exam 类新人训练模块的 learner 运行时绑定真源，必须来自 active path revision。learner 前端不得从 `SalesTrainerUnit.config.path`、catalog units 或其他单元配置回填文章/考卷绑定；缺绑定时必须 fail-closed 并展示配置诊断。管理端全量单元配置仍通过 admin path config / units API 治理。

`path_revision_id` / `path_revision_no` 必须来自路径级 active revision。无 active revision 时 learner path API 返回 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]` 或空诊断，不得返回由旧 `Unit` 聚合 backfill 拼出的正式路径。学员考试、录音、AI Coach 或 realtime outcome 需要冻结路径上下文时，必须保存该 revision lineage；只有旧历史数据无法可靠匹配时才标记 legacy snapshot，而不能伪造 revision id。

训练单元发布治理语义：

- `unit_id` 是训练单元 logical id，代表一个长期业务对象。
- 初次发布生成不可变 `unit_revision_id`，并写入 active pointer。
- 管理员编辑已发布训练单元时，`PUT /admin/.../units/{unit_id}` 保存 working revision，不直接改变 learner active 内容。
- 再次调用 `POST /admin/.../units/{unit_id}/publish` 时，working revision 变为 published revision，active pointer 指向新 revision，只影响之后进入训练、考试或录音的学员。
- `GET /admin/.../units/{unit_id}/revisions` 返回历史版本列表，支持管理端“查看历史 / 回滚到此版本”入口；回滚按钮只对非 active 的 published revision 展示，并必须提交原因。
- 回滚训练单元时必须移动 active pointer、应用该 revision payload 到未来读取的单元配置，并写审计事件；不得改写历史 attempt、submission、answer snapshot、material snapshot 或历史评分。

### `QuizAttempt`

```typescript
interface QuizAttempt {
  attempt_id: string;
  unit_id: string;
  user_id: string;
  total_score?: number | null;
  max_score?: number | null;
  passed?: boolean | null;
  status: "submitted" | "scored" | "failed";
  submitted_at: string;
  answers: QuizAnswer[];
}

interface QuizAnswer {
  answer_id: string;
  question_id: string;
  question_type: QuestionType;
  answer_payload: unknown;
  question_title?: string | null;
  question_stem?: string | null;
  question_revision_id?: string | null;
  question_payload_hash?: string | null;
  attempt_context?: Record<string, unknown> | null;
  is_correct?: boolean | null;
  score?: number | null;
  created_at: string;
}
```

### `ExamPaper`

```typescript
interface ExamPaper {
  paper_id: string;
  paper_key: string;
  title: string;
  description?: string | null;
  module_key: string;
  unit_id: string;
  pass_threshold?: number | null;
  status: "draft" | "published" | "archived";
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
  questions: ExamPaperQuestion[];
  active_revision_id?: string | null;
  active_revision_no?: number | null;
  working_revision_id?: string | null;
  working_revision_no?: number | null;
  has_unpublished_revision?: boolean;
}

interface ExamPaperQuestion {
  question_id: string;
  order_index: number;
  points: number;
  question_revision_id?: string | null;
  question_payload_hash?: string | null;
  legacy_snapshot_only?: boolean | null;
  question_type?: QuestionType;
  title?: string | null;
  stem?: string | null;
  options: Array<Record<string, unknown>>;
}

interface PaperAttempt {
  paper_id: string;
  paper_title: string;
  paper_revision_id?: string | null;
  path_key?: string | null;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  module_key?: string | null;
  legacy_snapshot_only?: boolean;
  attempt_id: string;
  unit_id: string;
  user_id: string;
  total_score?: number | null;
  max_score?: number | null;
  passed?: boolean | null;
  status: "submitted" | "scored" | "failed";
  submitted_at: string;
  answers: QuizAnswer[];
}

interface ExamPaperRevision {
  revision_id: string;
  revision_no: number;
  status: "working" | "published" | "archived";
  change_class: "non_semantic" | "semantic" | "binding" | "scoring_high_risk";
  title?: string | null;
  question_count: number;
  is_active: boolean;
  is_working: boolean;
  source_revision_id?: string | null;
  payload_hash: string;
  reason?: string | null;
  trace_id?: string | null;
  created_by?: string | null;
  published_by?: string | null;
  created_at: string;
  published_at?: string | null;
}
```

考卷是一等管理对象，题目引用 `QuestionItem`，不得要求管理员直接编辑通用 quiz unit。第一版允许 `ExamPaper.unit_id` 绑定一个兼容 `quiz` 执行单元以复用现有评分和答题快照，但管理员入口和 API DTO 必须呈现为 paper 语义。

发布治理语义：

- `paper_id` 是考卷 logical id，代表“商务技巧考卷”这个长期业务对象。
- 初次发布生成不可变 `paper_revision_id`，并写入 active pointer。
- 管理员编辑已发布考卷时，`PUT /admin/.../papers/{paper_id}` 保存 working revision，不直接改变 learner active 内容。
- `ExamPaper.active_revision_id` / `working_revision_id` 是管理端治理摘要，用于展示“当前生效版本”和“待发布修订”；普通管理员 UI 不应展示 raw id，只展示“第 N 版”和状态。
- 再次调用 `POST /admin/.../papers/{paper_id}/publish` 时，working revision 变为 published revision，active pointer 指向新 revision，只影响之后打开考卷或提交考试的学员。
- `GET /admin/.../papers/{paper_id}/revisions` 返回历史版本列表，支持管理端“查看历史 / 回滚到此版本”入口；回滚按钮只对非 active 的 published revision 展示，并必须提交原因。
- 历史 `PaperAttempt` 保存提交时的 `paper_revision_id`；结果页优先使用该 revision payload 展示 `paper_title`，题目仍使用 answer payload 内的 `question_snapshot`，不得从最新考卷或最新题库重建历史记录。
- 回滚考卷时必须移动 active pointer 并写审计事件；不得改写历史 attempt、answer snapshot 或历史得分。

### `AudioSubmission`

```typescript
interface AudioSubmission {
  submission_id: string;
  unit_id?: string | null;
  user_id: string;
  purpose: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  file_hash?: string | null;
  duration_seconds?: number | null;
  source_page?: string | null;
  confirmed_material_version_id?: string | null;
  confirmed_material_at?: string | null;
  material_snapshot?: TrainingRecordMaterialSnapshot | null;
  score_scheme_snapshot?: TrainingRecordScoreSchemeSnapshot | null;
  task_brief_snapshot?: TrainingRecordTaskBriefSnapshot | null;
  path_key?: string | null;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  module_key?: string | null;
  legacy_snapshot_only: boolean;
  status:
    | "uploaded"
    | "transcribing"
    | "transcribed"
    | "transcription_failed"
    | "scoring"
    | "scored"
    | "scoring_failed";
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  transcript?: AudioTranscript | null;
  score_result?: AudioScoreResult | null;
}
```

`source_page` 用于记录上传来源页面，例如 `sales_trainer_audio_upload`。缺失时允许为 `null`，不得影响上传、转写或评分。

### `AudioTranscript`

```typescript
interface AudioTranscript {
  transcript_id: string;
  provider: string;
  transcript_text: string;
  raw_payload?: Record<string, unknown> | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}
```

### `AudioScoreResult`

```typescript
interface AudioScoreResult {
  score_id: string;
  submission_id: string;
  prompt_id: string;
  prompt_version: number;
  prompt_hash: string;
  deucate_model?: string | null;
  total_score?: number | null;
  passed?: boolean | null;
  summary?: string | null;
  strengths: unknown[];
  improvements: unknown[];
  dimension_scores: Record<string, unknown>;
  transcript_snapshot?: string | null;
  raw_response?: Record<string, unknown> | null;
  error_code?: string | null;
  error_message?: string | null;
  latency_ms?: number | null;
  path_key?: string | null;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  module_key?: string | null;
  legacy_snapshot_only: boolean;
  created_at: string;
}
```

`transcript_snapshot` 是评分记录的转写文本快照。评分结果必须能追溯当次评分使用的文本，即使后续重新转写或重评。
评分结果响应中的路径修订字段来自对应 `AudioSubmission.task_brief_snapshot.submission_context`；旧结果无法可靠匹配路径修订时返回 `legacy_snapshot_only=true`，不得从最新路径配置伪造历史 revision。

### `AudioScorePrompt`

```typescript
interface AudioScorePrompt {
  prompt_id: string;
  name: string;
  purpose: string;
  system_prompt: string;
  scoring_template: string;
  output_schema: Record<string, unknown>;
  learner_rubric: {
    visible_to_learner?: boolean;
    pass_threshold?: number | null;
    criteria?: Array<{
      key: string;
      label: string;
      description?: string | null;
      weight?: number | null;
      excellent?: string | null;
      passable?: string | null;
      needs_work?: string | null;
    }>;
    common_mistakes?: string[];
  };
  version: number;
  status: "draft" | "published" | "archived";
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
}

interface AudioScorePromptRevision {
  revision_id: string;
  revision_no: number;
  status: "working" | "published" | "archived";
  change_class: "non_semantic" | "semantic" | "binding" | "scoring_high_risk";
  name?: string | null;
  purpose?: string | null;
  is_active: boolean;
  is_working: boolean;
  source_revision_id?: string | null;
  payload_hash: string;
  reason?: string | null;
  trace_id?: string | null;
  created_by?: string | null;
  published_by?: string | null;
  created_at: string;
  published_at?: string | null;
}

interface AudioScorePromptRollbackPreviewResponse {
  action: "audio_score_prompt.rollback";
  permission: "sales_trainer.manage_modules";
  requires_reason: true;
  future_only: true;
  mutates_history: false;
  target_prompt_id: string;
  current_revision_id?: string | null;
  target_revision: AudioScorePromptRevision;
  changed_fields: string[];
  historical_submissions_changed: false;
  historical_regrade_required: false;
  rollback_plan: {
    apply_endpoint: string;
    rollback_endpoint: string;
    strategy: "activate_existing_published_revision";
  };
}
```

`scoring_template` 必须包含 `{transcript}`。

### `SalesTrainerMaterial`

```typescript
interface SalesTrainerMaterial {
  material_id: string;
  material_key: string;
  name: string;
  material_type: "ppt_deck" | "script" | "example_audio" | "attachment";
  description?: string | null;
  purpose: string;
  status: "draft" | "published" | "archived";
  current_version_id?: string | null;
  current_version?: SalesTrainerMaterialVersion | null;
  versions: SalesTrainerMaterialVersion[];
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
}

interface SalesTrainerMaterialVersion {
  version_id: string;
  material_id: string;
  version_label: string;
  title: string;
  file_name: string;
  content_type: string;
  file_size_bytes: number;
  storage_key: string;
  file_hash?: string | null;
  release_notes?: string | null;
  status: "draft" | "published" | "archived";
  published_at?: string | null;
  published_by?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

interface SalesTrainerMaterialVersionRollbackPreviewResponse {
  action: "material_version.rollback";
  permission: "sales_trainer.manage_modules";
  requires_reason: true;
  future_only: true;
  mutates_history: false;
  target_material_id: string;
  current_version_id?: string | null;
  target_version: SalesTrainerMaterialVersion;
  future_material_current_version_changed: boolean;
  historical_submissions_changed: false;
  historical_replay_preserved: true;
  active_or_working_path_refs: Array<{
    source: "active_revision" | "working_revision";
    revision_id: string;
    revision_no: number;
    module_key: string;
    material_id?: string | null;
    material_version_id?: string | null;
  }>;
  rollback_plan: {
    apply_endpoint: string;
    rollback_endpoint: string;
    strategy: "restore_existing_material_version_as_current";
  };
}
```

材料主档表示长期训练材料，例如“公司主胶片”；版本表示具体可下载文件。发布一个版本后，该版本成为 `current_version_id`，同一材料之前的 published 版本自动归档，确保同一材料只有一个当前发布版本。

### `SalesTrainerUnitBrief`

```typescript
interface SalesTrainerUnitBrief {
  unit: SalesTrainerUnit;
  task_brief: SalesTrainerTaskBrief;
  materials: Array<{
    material_id: string;
    material_key: string;
    name: string;
    material_type: string;
    description?: string | null;
    purpose: string;
    required: boolean;
    confirmation_required: boolean;
    learner_note?: string | null;
    display_order: number;
    current_version: SalesTrainerLearnerMaterialVersion;
  }>;
  score_scheme?: {
    prompt_id: string;
    name: string;
    purpose: string;
    version: number;
    status: string;
    learner_rubric: Record<string, unknown>;
    pass_threshold: number;
  } | null;
}

interface SalesTrainerLearnerMaterialVersion {
  version_id: string;
  material_id: string;
  version_label: string;
  title: string;
  file_name: string;
  content_type: string;
  file_size_bytes: number;
  file_hash?: string | null;
  release_notes?: string | null;
  status: string;
  published_at?: string | null;
}

interface SalesTrainerTaskBrief {
  enabled: boolean;
  title?: string | null;
  purpose?: string | null;
  scenario?: string | null;
  instructions: string[];
  success_criteria: string[];
  common_mistakes: string[];
  upload_guidance?: string | null;
}
```

学员 PPT 演练页必须以该 DTO 为准渲染任务意义、最新版材料、学员可见 rubric 和上传门禁，不得在页面组件里写死 PPT 下载地址、评分维度、通过线或任务说明。`SalesTrainerLearnerMaterialVersion` 不暴露 `storage_key`；文件读取必须通过材料文件下载 API 的后端对象级授权完成，不能把存储路径下发给 learner 页面。

### `OperationLog`

```typescript
interface OperationLog {
  log_id: string;
  actor_id?: string | null;
  actor_role?: string | null;
  action: string;
  target_type: string;
  target_id?: string | null;
  request_id?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}
```

## learner API

### `GET /api/v1/sales-trainer/units`

查询 learner 当前 TrainingJourney 中可用的训练单元。该接口不是全量 published catalog：后端必须先读取 active TrainingJourney，只返回未 locked 的 module target unit，且 unit 必须已发布；无 active revision 时返回空列表，不得回退到 `UnitService.list_units(published_only=true)`、旧 active projection 全量 enabled unit 或旧 `unit.config.path`。`modules[].learner_level_required` 不匹配、模块停用、配置错误进入 locked/error_terminal 时不得出现在列表里。列表响应只承载单元基础信息和 learner 安全配置，`questions` 可为空；需要题目详情的页面必须继续调用详情、brief、quiz 或学习单元专用 API。管理端需要查看全量单元时只能使用 `/api/v1/admin/sales-trainer/units` 或 `/api/v1/admin/newcomer-training/units`。

Response `data`:

```typescript
interface SalesTrainerUnitListResponse {
  items: SalesTrainerUnit[];
  total: number;
}
```

### `GET /api/v1/sales-trainer/units/{unit_id}`

查询 learner 可见训练单元详情。未发布、不存在、无 active revision、active path 外或当前 level locked 均返回 `[SALES_TRAINER_UNIT_NOT_FOUND]`。后台管理角色需要全量读取单元详情时必须走 admin API，不能借 learner 路由绕过 active path 对象级授权。

Response `data`: `SalesTrainerUnit`

### `GET /api/v1/sales-trainer/units/{unit_id}/brief`

查询 learner 侧训练任务简报、当前材料版本和学员可见评分方案。未发布、不存在、无 active revision、active path 外或当前 level locked 均返回 `[SALES_TRAINER_UNIT_NOT_FOUND]`；绑定材料缺失、未发布或无当前版本时返回对应材料错误码。

Response `data`: `SalesTrainerUnitBrief`

### `GET /api/v1/sales-trainer/materials/versions/{version_id}/file`

下载 learner 可见的已发布训练材料版本。

- Query:
  - `disposition?: "attachment" | "inline"`，默认 `attachment`。学员页在线预览音频、视频、PDF、Markdown 等材料时使用 `inline`；下载按钮使用默认下载语义。
- 权限与对象级范围：
  - learner 必须命中当前 active path revision 中自己可进入模块绑定出的材料版本；不在 active path、模块锁定、未绑定或历史不可回放版本均 fail-closed。
  - 非授权 learner 返回 `404 [MATERIAL_FILE_NOT_FOUND]`，不得泄露材料是否存在。
  - `support` / `training_lead` / `training_manager` 的记录查看权限不自动授予材料文件访问。
- 本地存储: 返回 `200` 文件内容。
- 对象存储: 返回 `302` 短期签名下载 URL。
- 版本不存在或未发布返回 `[MATERIAL_VERSION_NOT_PUBLISHED]`。

### `POST /api/v1/sales-trainer/quiz-attempts`

提交做题结果。仅允许提交 `quiz` 类型且已发布训练单元。`answers[].question_id` 必须属于该训练单元；缺少任一题答案、单选/判断为空、多选为空或简答为空时返回 422 `[QUIZ_ANSWER_INCOMPLETE]`，message 固定为 `请完成全部题目后再提交。`，不得创建 attempt、不得评分。

Request:

```typescript
interface QuizAttemptCreate {
  unit_id: string;
  answers: Array<{
    question_id: string;
    answer_payload: unknown;
  }>;
}
```

Response `data`: `QuizAttempt`

### `GET /api/v1/sales-trainer/papers/{paper_id}`

查询已发布考卷。草稿或归档考卷对 learner 不可见，返回 `[PAPER_NOT_PUBLISHED]`；不存在返回 `[PAPER_NOT_FOUND]`。

Response `data`: `ExamPaper`

### `POST /api/v1/sales-trainer/paper-attempts`

提交已发布考卷答案。服务端按 `paper_id` 找到考卷 active revision 和兼容 quiz 执行单元并复用当前题型评分逻辑。`answers[].question_id` 必须属于该考卷当前 active revision，额外题目返回 `[QUIZ_ANSWER_QUESTION_NOT_IN_UNIT]`；缺少任一题答案、单选/判断为空、多选为空或简答为空时返回 422 `[QUIZ_ANSWER_INCOMPLETE]`，message 固定为 `请完成全部题目后再提交。`，不得创建 attempt、不得评分。如果当前新人训练路径把该考卷或 backing unit 绑定为 `article_exam`，提交前必须完成当前绑定文章的全部章节阅读；未完成返回 403 `[NEWCOMER_ARTICLE_PROGRESS_REQUIRED]`，不得进入评分。提交成功后，attempt 必须记录当时的 `paper_revision_id`；answer payload 必须冻结题目快照、`question_revision_id` 或 legacy `question_payload_hash`，以及 `attempt_context`，其中包含提交时命中的 `path_key`、`path_revision_id`、`path_revision_no`、`module_key`、`paper_revision_id`。旧数据无法可靠匹配路径修订时返回 `legacy_snapshot_only=true`，不得从最新路径配置伪造历史 revision。简答题 AI 批改依赖外部模型配置；外部模型鉴权、连接、超时或重试失败时，服务端必须保存本次提交与答案快照，返回 `status="submitted"`、简答题 `score=null`，不得因批改服务不可用让整张考卷提交失败。

Request:

```typescript
interface PaperAttemptCreate {
  paper_id: string;
  answers: Array<{
    question_id: string;
    answer_payload: unknown;
  }>;
}
```

Response `data`: `PaperAttempt`

### newcomer-training 兼容别名

以下 learner 别名与 `/sales-trainer` paper 端点语义完全一致，用于新人训练路径新前端：

| 方法 | 路径 | 等价端点 |
|---|---|---|
| `GET` | `/api/v1/newcomer-training/papers/{paper_id}` | `/api/v1/sales-trainer/papers/{paper_id}` |
| `POST` | `/api/v1/newcomer-training/paper-attempts` | `/api/v1/sales-trainer/paper-attempts` |

### `GET /api/v1/newcomer-training/modules/{module_key}/article`

查询新人训练路径模块绑定的 learner 可见 Markdown 文章。默认绑定必须来自 active path revision 的 `levels[].learning_content_id`；`learning_content_id` 查询参数仅用于兼容调试/显式预览，不是业务真源。不得从已发布模块单元的旧 `config.path.learning_content_id`、catalog units 或其他单元配置回填。实际文章内容、章节、图片 Markdown 仍由现有 `LearningContent` / `LearningChapter` 后台维护。

Query:

```typescript
interface NewcomerArticleQuery {
  learning_content_id?: string;
}
```

Response:

```typescript
interface NewcomerArticle {
  module_key: string;
  learning_content_id: string;
  title: string;
  summary?: string | null;
  owner?: string | null;
  source?: string | null;
  chapters: Array<{
    chapter_id: string;
    title: string;
    content: string;
    order_index: number;
  }>;
}
```

错误语义:

- learner 读取文章或读写 `/modules/{module_key}/article-progress` 前必须复用 active TrainingJourney 模块准入：无 active revision、无模块、模块停用或 `learner_level_required` 不匹配时 fail-closed，返回 404 `[SALES_TRAINER_UNIT_NOT_FOUND]`；不得允许猜测 `module_key` 或旧 content id 绕过 Journey locked 状态。
- 模块未绑定已发布内容、内容为草稿或已归档: `[LEARNING_CONTENT_NOT_PUBLISHED]`。
- 显式传入的 `learning_content_id` 不存在: `[LEARNING_CONTENT_NOT_FOUND]`。
- Markdown 图片按普通 Markdown 渲染；不得通过该接口透传不受控 HTML。

### `GET /api/v1/sales-trainer/quiz-attempts/{attempt_id}`

查询本人做题结果。learner 查询他人记录返回 `[ACCESS_DENIED]`。

Response `data`: `QuizAttempt`

### `POST /api/v1/sales-trainer/audio-submissions/upload-url`

生成音频上传 URL。用于对象存储直传或本地存储占位。

Request:

```typescript
interface AudioUploadUrlRequest {
  filename: string;
  content_type: string;
}
```

Response `data`:

```typescript
interface AudioUploadUrlResponse {
  upload_url: string;
  storage_key: string;
  expires_at: string;
  content_type: string;
  storage_backend: "local" | "oss" | string;
}
```

### `POST /api/v1/sales-trainer/audio-submissions/upload`

multipart 直接上传音频并注册提交，适用于没有前端直传对象存储的基础闭环。

Content-Type: `multipart/form-data`

Form fields:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | 音频文件 |
| `unit_id` | string | 否 | 已发布 `audio_scoring` 训练单元 |
| `purpose` | string | 否 | 默认 `general_audio_scoring` |
| `duration_seconds` | number | 否 | 可选元数据；不作为上传限制 |
| `source_page` | string | 否 | 可选来源页面 |
| `auto_process` | boolean | 否 | 默认 `true`，为 `true` 时在响应返回后调度转写和评分后台任务 |
| `confirmed_material_version_id` | string | 否 | PPT 演练等要求确认材料版本时必填 |

Response `data`: `AudioSubmission`

### `POST /api/v1/sales-trainer/audio-submissions`

注册已上传音频并触发后续处理。用于 `upload-url` 后的对象存储直传闭环。

Request:

```typescript
interface AudioSubmissionCreate {
  unit_id?: string | null;
  purpose?: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
  file_hash?: string | null;
  duration_seconds?: number | null;
  source_page?: string | null;
  confirmed_material_version_id?: string | null;
  auto_process?: boolean;
}
```

Response `data`: `AudioSubmission`

提交规则:

- `auto_process=true` 时，learner API 必须先返回 `status="uploaded"` 的提交记录，再调度后台转写和评分；结果页通过 `GET /audio-submissions/{submission_id}` 轮询 `transcribing -> transcribed -> scoring -> scored` 或失败状态。不得让上传请求同步等待完整 ASR/评分流程。
- `auto_process=false` 只登记提交，不调度后台任务；主要用于测试、排障或管理员手动处理。
- 非 PPT 普通录音沿用旧闭环，未绑定材料时仍可提交。
- `purpose` 或训练单元配置解析为 `ppt_pitch` 时，训练单元必须绑定至少一个 required 且 confirmation_required 的已发布材料，否则返回 `[PPT_MATERIAL_BINDING_REQUIRED]`。
- 绑定材料要求确认时，`confirmed_material_version_id` 必须匹配当前要求版本，否则返回 `[MATERIAL_VERSION_CONFIRMATION_REQUIRED]` 或 `[MATERIAL_VERSION_CONFIRMATION_OUTDATED]`。
- 提交成功后冻结 `material_snapshot`、`score_scheme_snapshot`、`task_brief_snapshot`，后续材料或评分方案变更不得改写历史提交解释依据。
- 当提交命中新人训练路径 active revision 时，`task_brief_snapshot.submission_context` 必须冻结 `path_key`、`path_revision_id`、`path_revision_no`、`module_key`、`module_type` 和 `legacy_snapshot_only=false`；响应顶层字段从该历史快照读取。旧提交无法可靠匹配路径修订时返回 `legacy_snapshot_only=true`，不得从最新路径配置伪造历史 revision。

### `GET /api/v1/sales-trainer/audio-submissions/{submission_id}`

查询本人音频提交、转写和最新评分结果。learner 查询他人提交返回 `[ACCESS_DENIED]`。

Response `data`: `AudioSubmission`

### `GET /api/v1/sales-trainer/audio-submissions/{submission_id}/file`

读取本人原始音频文件。

- 本地存储: 返回 `200`，响应体为音频内容，`Content-Type` 使用提交记录的 `content_type`。
- 对象存储: 返回 `302`，`Location` 为短期签名下载 URL。
- 只允许提交本人访问；他人音频返回 `[ACCESS_DENIED]`。

## admin API

admin 接口按角色能力分级，而不是只有 `admin/support` 两档大权限。内容配置类接口要求超级管理员或内容管理员；学员记录类接口允许超级管理员、培训负责人和运维人员读取，其中培训负责人只看同部门数据；配置健康、操作日志和重试任务只允许超级管理员或运维人员。非授权角色返回 `[ROLE_REQUIRED]`。

| 能力 | 允许角色 | 数据范围 |
|---|---|---|
| 内容配置、发布、归档 | `admin`、`super_admin`、`content_admin`、`newcomer_content_admin` | 全局内容资产 |
| 学员录音、评分结果、做题记录、训练记录 | `admin`、`super_admin`、`support`、`training_lead`、`training_manager`、`operations`、`ops`、`operator`、`sre` | 超级管理员/运维全局；培训负责人按 `department` |
| 转写/评分失败重试 | `admin`、`super_admin`、`operations`、`ops`、`operator`、`sre` | 全局 |
| 配置健康、操作日志 | `admin`、`super_admin`、`operations`、`ops`、`operator`、`sre` | 全局 |

### 训练单元

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/capabilities` | 当前用户新人训练路径后台 capability projection，前端导航和页面入口以此为准 |
| `GET` | `/api/v1/admin/sales-trainer/units` | 训练单元列表，支持 `include_archived`、`limit`、`offset` |
| `GET` | `/api/v1/admin/sales-trainer/units/{unit_id}` | 训练单元详情 |
| `POST` | `/api/v1/admin/sales-trainer/units` | 创建训练单元，默认 `draft` |
| `PUT` | `/api/v1/admin/sales-trainer/units/{unit_id}` | `draft` 单元直接更新；已发布单元保存为 working revision，active learner 内容不变 |
| `GET` | `/api/v1/admin/sales-trainer/units/{unit_id}/revisions` | 查看训练单元历史修订，返回 active/working 标记和影响摘要 |
| `POST` | `/api/v1/admin/sales-trainer/units/{unit_id}/publish` | 初次发布训练单元或发布最新 working revision，并移动 active pointer，只影响未来学员 |
| `POST` | `/api/v1/admin/sales-trainer/units/{unit_id}/rollback` | 回滚到指定 published revision，必须提交原因；只影响未来学员并写审计 |
| `POST` | `/api/v1/admin/sales-trainer/units/{unit_id}/archive` | 归档训练单元 |

Create request:

```typescript
interface SalesTrainerUnitCreate {
  name: string;
  description?: string | null;
  unit_type: "quiz" | "audio_scoring";
  config?: SalesTrainerUnit["config"];
  questions?: Array<{
    question_id: string;
    order_index?: number;
    points?: number;
  }>;
}
```

Update request:

```typescript
interface SalesTrainerUnitUpdate {
  name?: string;
  description?: string | null;
  config?: SalesTrainerUnit["config"];
  questions?: Array<{
    question_id: string;
    order_index?: number;
    points?: number;
  }>;
}
```

Response `data`: `SalesTrainerUnit`；列表返回 `{ items: SalesTrainerUnit[], total: number }`。

Revision list response:

```typescript
interface UnitRevisionListResponse {
  items: UnitRevision[];
  total: number;
}
```

Rollback request:

```typescript
interface UnitRollbackRequest {
  target_revision_id: string;
  reason: string;
}
```

发布门禁:

- `quiz` 单元必须绑定至少 1 道题。
- `audio_scoring` 单元必须配置已发布 `audio.scoring_prompt_id`。
- `audio.pass_threshold` 如存在，必须在 `0-100` 范围内。
- `audio.purpose="ppt_pitch"` 时必须配置 `materials.bindings`，且至少一个绑定项 `required=true`、`confirmation_required=true`。
- 材料绑定项必须指向已发布材料；`current_published` 要求材料存在当前发布版本；`locked_version` 要求锁定版本已发布且属于该材料。
- `task_brief`、`materials`、`learner_rubric` 等可调整业务内容必须通过配置结构或评分方案管理，不得硬编码在学员页面。
- 已归档单元不可发布。

`/api/v1/admin/newcomer-training/units`、`/api/v1/admin/newcomer-training/units/{unit_id}/revisions`、`/publish`、`/rollback` 和 `/archive` 是新人训练路径 admin 主入口。`/api/v1/admin/sales-trainer/units` 作为技术兼容入口保留；普通管理页面应优先使用 newcomer-training 命名入口。

### 商务技巧文章绑定管理

文章正文和章节继续由 `/api/v1/admin/curriculum/learning-contents` 及其章节接口管理；新人训练路径后台只负责把已发布 `LearningContent` 绑定到 `business_skills` 等 `article_exam` 模块。

| 方法 | 路径 | 说明 |
|---|---|---|
| `PUT` | `/api/v1/admin/newcomer-training/modules/{module_key}/article-binding` | 绑定/重绑模块文章，保存为新人训练路径待发布修订 |
| `GET` | `/api/v1/admin/newcomer-training/learning-contents/{content_id}/binding-impact` | 查询学习内容被 active/working 新人训练路径引用的影响范围 |

Request:

```typescript
interface NewcomerArticleBindingUpdate {
  learning_content_id: string;
  path_key?: string; // 默认 newcomer_training_path_v1
  reason?: string; // 绑定变更原因，写入审计日志
}
```

Response `data`:

```typescript
interface NewcomerArticleBinding {
  module_key: string;
  learning_content_id: string;
  path_key: string;
  active_revision_id: string | null;
  active_revision_no: number | null;
  working_revision_id: string;
  working_revision_no: number;
  has_unpublished_revision: true;
  impact_scope: "future_learners_only";
}
```

绑定接口不得直接修改 `SalesTrainerUnit.config.path.learning_content_id`。它必须基于当前路径配置生成 working revision；管理员随后在“新人训练路径配置中心”发布，发布后只影响后续学员。历史学习、考试、录音与评分记录继续引用当时快照。

绑定影响 Response `data`:

```typescript
interface LearningContentBindingUnitImpact {
  unit_key: string;
  title: string;
  source_chapter_orders: number[];
  ai_coach_remediation_chapter_orders: number[];
  capability_keys: string[];
  require_quiz: boolean;
  require_ai_coach: boolean;
}

interface LearningContentPathBindingImpact {
  source: "active_revision" | "working_revision";
  path_key: string;
  module_key: string;
  module_title: string;
  revision_id: string;
  revision_no: number;
  learner_effective: boolean;
  learning_units: LearningContentBindingUnitImpact[];
  impacted_chapter_orders: number[];
}

interface LearningContentBindingImpactResponse {
  learning_content_id: string;
  active_bindings: LearningContentPathBindingImpact[];
  working_bindings: LearningContentPathBindingImpact[];
  has_active_binding: boolean;
  has_working_binding: boolean;
  is_bound_to_business_skills: boolean;
  can_archive: boolean;
  archive_block_reason: string | null;
  management_entries: Record<"article_binding" | "path_config" | "question_drafts", string>;
}
```

`LearningContent` 详情响应必须包含 `revision_state`，用于前端区分“草稿记录”“待发布修订”和“已归档锁定”。已发布内容保存元数据或章节时写入 working revision，不直接改 active revision；只有再次调用发布接口后 learner 才读取新内容。`published + has_unpublished_revision=true` 时前端必须显示“发布修订”并允许提交；`published + has_unpublished_revision=false` 时显示“当前无待发布修订”并禁用。

```typescript
interface LearningContentRevisionState {
  active_revision_id: string | null;
  active_revision_no: number | null;
  working_revision_id: string | null;
  working_revision_no: number | null;
  has_unpublished_revision: boolean;
  edit_target: "draft_record" | "working_revision" | "archived_locked";
  publish_label: "发布" | "发布修订" | "当前无待发布修订" | "已归档";
  save_result_copy: string;
}
```

归档保护:

- `POST /api/v1/curriculum/learning-contents/{content_id}/archive` 在文章被 active 或 working 新人训练路径引用时必须返回 409 `[LEARNING_CONTENT_BOUND_TO_NEWCOMER_PATH]`，不得只依赖前端禁用按钮。
- 运营必须先到文章绑定或路径配置替换引用，并发布路径配置，才允许归档。
- 章节排序和删除仍按现有 `source_chapter_orders` 序号绑定工作；本轮不迁移到稳定 `chapter_id`。前端在排序/删除前必须基于 binding impact 提示受影响小单元、章节序号和 AI 教练补救章节。

权限、校验与审计:

- 权限复用新人训练路径内容管理能力：`admin`、`super_admin`、`content_admin`、`newcomer_content_admin`。
- `learning_content_id` 必须指向已发布 `LearningContent`；缺失、草稿、归档或不存在均不写入绑定。
- `module_key` + `path_key` 必须定位到已发布且 enabled 的 `"article_exam"` 模块配置；缺失返回 `[NEWCOMER_MODULE_CONFIG_MISSING]`。
- 成功后写入 `SalesTrainerOperationLog`：`action="newcomer_module.article_binding_changed"`、`target_type="newcomer_training_module"`、`target_id=module_key`，metadata 记录新旧 `learning_content_id` 与 `path_key`。

### 商务礼仪训练包资料导入

商务礼仪训练包 v1 使用专用资料导入入口。它只生成 `LearningContent(draft)`、8 个 `LearningChapter` 和 `sales_trainer_asset_revisions(status="working")`，不得直接发布 learner 可见文章，也不得覆盖已发布训练包 revision。管理员仍需在章节编辑、文章绑定和路径配置中心完成后续审核/发布。

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/imports` | 上传 Markdown 并生成商务礼仪训练包资料草稿版本 |

Request: `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | `UploadFile` | 是 | Markdown 文件。格式、大小由后端导入配置校验。 |
| `training_pack_key` | `string` | 否 | 默认 `business_etiquette_v1`。 |
| `allow_overwrite_draft` | `boolean` | 否 | 默认由导入配置决定；为 `false` 且已有 working revision 时返回 `[BUSINESS_ETIQUETTE_DRAFT_EXISTS]`。 |
| `reason` | `string` | 否 | 写入 revision reason 和操作日志。 |

Response `data`:

```typescript
interface BusinessEtiquetteImportResponse {
  training_pack_key: string;
  learning_content_id: string;
  learning_content_status: "draft";
  working_revision_id: string;
  working_revision_no: number;
  active_revision_id: string | null;
  active_revision_no: number | null;
  has_unpublished_revision: true;
  source_filename: string;
  content_type: string | null;
  file_size_bytes: number;
  content_hash: string;
  imported_at: string;
  allow_overwrite_draft: boolean;
  ai_suggestions_enabled: false;
  book_title: string;
  original_chapter_count: number;
  micro_chapter_count: number;
  knowledge_point_count: number;
  chapters: Array<{
    title: string;
    order_index: number;
    line_number: number;
    content_hash: string;
    micro_chapters: Array<{
      title: string;
      order_index: number;
      line_number: number;
      knowledge_points: Array<{
        title: string;
        order_index: number;
        line_number: number;
      }>;
    }>;
  }>;
}
```

权限、校验与审计:

- 权限复用新人训练路径内容管理能力：`admin`、`super_admin`、`content_admin`、`newcomer_content_admin`。
- 后端导入配置必须集中定义：默认训练包 key、支持格式、最大文件大小、是否允许覆盖草稿、期望原始章节数。
- 系统必须先完整解析 Markdown 标题树，再写入数据库；解析失败不得生成半成品 `LearningContent`、`LearningChapter` 或 asset revision。
- 原文全书 H1 后的 8 个 H1 保存为原始章节；H2 保存为微章节；H3 保存为知识点/出题依据；章节正文进入 `LearningChapter.content`。
- 缺少导入 prompt 或解析配置时，导入只能做结构解析，不做 AI 建议，`ai_suggestions_enabled=false`。
- 成功后写入 `SalesTrainerOperationLog`：`action="business_etiquette_training_pack.markdown_imported"`、`target_type="business_etiquette_training_pack"`、`target_id=training_pack_key`，metadata 记录 `learning_content_id`、working/active revision、来源文件、内容 hash、章节统计、是否覆盖草稿和 `trace_id`。

### 商务礼仪能力点快照

商务礼仪能力点第一版归属于 `business_etiquette_training_pack` 训练包版本快照，不建立独立全局能力点目录。能力点名称、描述、达标线、掌握等级、证据规则和章节绑定都保存到训练包 `sales_trainer_asset_revisions.payload.capability_snapshot`；训练包发布后冻结该快照，后续题目、小测、AI 教练、训练记录和卡点视图只能引用已发布快照。

默认种子包含 8 个主能力点：`respect_boundaries`、`professional_image`、`meeting_social_actions`、`business_communication`、`reception_visit_execution`、`meeting_negotiation_order`、`dining_social_boundary`、`repair_reflection_internalization`。默认种子只由后端返回给管理页初始化，learner 页面不得自行生成能力点。

```typescript
type BusinessEtiquetteCapabilityStatus = "draft" | "published" | "archived";

interface BusinessEtiquetteMasteryLevelConfig {
  level_key: string;
  display_name: string;
  min_score: number; // 0..100
  description?: string | null;
}

interface BusinessEtiquetteEvidenceRuleConfig {
  evidence_type:
    | "quiz_question"
    | "ai_coach_card"
    | "coach_feedback"
    | "reading_progress"
    | "manual_review";
  weight: number; // 0..10
  required: boolean;
  description?: string | null;
}

interface BusinessEtiquetteCapabilityConfig {
  capability_key: string;
  display_name: string;
  description?: string | null;
  mastery_levels: BusinessEtiquetteMasteryLevelConfig[];
  default_threshold: number; // 0..100
  evidence_rules: BusinessEtiquetteEvidenceRuleConfig[];
  owner_scope: "business_etiquette_training_pack";
  status: BusinessEtiquetteCapabilityStatus;
}

interface BusinessEtiquetteChapterCapabilityBinding {
  chapter_order: number; // 原始章节 order_index
  capability_keys: string[];
}

interface BusinessEtiquetteCapabilitySnapshotResponse {
  training_pack_key: string;
  source: "working_revision" | "active_revision" | "default_seed";
  working_revision_id: string | null;
  working_revision_no: number | null;
  active_revision_id: string | null;
  active_revision_no: number | null;
  has_unpublished_revision: boolean;
  schema_version: number;
  capabilities: BusinessEtiquetteCapabilityConfig[];
  chapter_bindings: BusinessEtiquetteChapterCapabilityBinding[];
  original_chapter_count: number | null;
  needs_save: boolean;
  management_entry: "/admin/sales-trainer/articles/capabilities";
  permission: "sales_trainer.manage_modules";
  effective_timing: "training_pack_revision_publish_time";
}
```

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/newcomer-training/business-etiquette/capabilities` | 读取当前 working/active 训练包能力点快照；缺失时返回后端默认种子并标记 `needs_save=true` |
| `PUT` | `/api/v1/admin/newcomer-training/business-etiquette/capabilities` | 保存能力点、掌握等级、证据规则和章节绑定，生成新的 working revision |
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/capabilities/{capability_key}/publish` | 将单个能力点状态标记为 `published`，生成新的 working revision |
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/capabilities/{capability_key}/archive` | 将单个能力点状态标记为 `archived`，生成新的 working revision |

`PUT` request:

```typescript
interface BusinessEtiquetteCapabilitySnapshotSaveRequest {
  training_pack_key?: string | null; // 默认 business_etiquette_v1
  capabilities: BusinessEtiquetteCapabilityConfig[];
  chapter_bindings: BusinessEtiquetteChapterCapabilityBinding[];
  reason?: string | null;
}
```

`publish/archive` request:

```typescript
interface BusinessEtiquetteCapabilityActionRequest {
  training_pack_key?: string | null;
  reason?: string | null;
}
```

权限、校验与审计:

- 权限复用新人训练路径内容管理能力：`admin`、`super_admin`、`content_admin`、`newcomer_content_admin`；普通学员保存、发布或归档返回 `[ROLE_REQUIRED]`。
- 保存能力点前必须已有训练包 working 或 active revision；缺失返回 `[BUSINESS_ETIQUETTE_TRAINING_PACK_REVISION_MISSING]`，不得创建脱离资料版本的全局能力点。
- `capability_key` 在快照内唯一；`owner_scope` 只能是 `"business_etiquette_training_pack"`。
- `mastery_levels` 必须非空、`level_key` 唯一，并按 `min_score` 升序；`default_threshold` 与 `min_score` 范围均为 `0..100`。
- `evidence_rules` 必须非空，`weight` 范围 `0..10`，`evidence_type` 必须在白名单内。
- 章节绑定只能引用未归档且存在的能力点；引用不存在原文章节返回 `[BUSINESS_ETIQUETTE_CAPABILITY_BINDING_INVALID]`。
- 保存成功写入 `business_etiquette_training_pack.capabilities_saved`；发布/归档分别写入 `business_etiquette_training_pack.capability_published` / `business_etiquette_training_pack.capability_archived`。
- 已发布训练包 revision 不允许被原地修改；任何能力点调整都生成新的 working revision，后续训练包发布时冻结新版能力点快照。

### 商务礼仪 AI 出题草稿箱

商务礼仪 AI 出题只允许生成 `sales_trainer_business_etiquette_question_drafts(status="pending_review")`。AI 不得直接创建、发布或绑定学员可见题目；管理员审批后，后端调用销售训练题库服务创建正式 `QuestionItem(status="draft")`，后续仍需题库发布/组卷流程控制学员可见性。

出题运行时必须通过 `PromptTemplateService.get_template()` 和 `PromptTemplateService.compile_runtime_prompt_contract()` 编译 Prompt 合同。草稿必须记录 `prompt_template_id`、`prompt_contract_hash`、`prompt_contract_version`、`prompt_rendered_hash`、`model_config`、`raw_generation`、来源章节、来源片段、能力点建议、生成批次和审核记录。不得在 service 内绕过 PromptTemplateService 拼接裸 prompt。

```typescript
type BusinessEtiquetteQuestionDraftType =
  | "single_choice"
  | "multiple_choice"
  | "short_answer";

type BusinessEtiquetteQuestionDraftStatus =
  | "pending_review"
  | "approved"
  | "rejected"
  | "converted";

interface BusinessEtiquetteQuestionDraftOption {
  value: string;
  label: string;
}

interface BusinessEtiquetteQuestionDraftGenerateRequest {
  training_pack_key?: string | null; // 默认 business_etiquette_v1
  chapter_order: number; // 原始章节 order_index
  prompt_template_id: string;
  question_types: BusinessEtiquetteQuestionDraftType[];
  draft_count?: number; // 1..10，默认 3
  capability_keys?: string[]; // 缺省读取章节能力点绑定
  model_config?: {
    model_config_id?: string; // 可选，指向 /admin/model-configs 下 active LLM 配置
    extra_config?: Record<string, unknown>; // 可选，本批次高级覆盖参数
    [key: string]: unknown;
  };
  reason?: string | null;
}

interface BusinessEtiquetteQuestionDraft {
  draft_id: string;
  batch_id: string;
  training_pack_key: string;
  training_pack_revision_id: string | null;
  training_pack_revision_no: number | null;
  learning_content_id: string | null;
  chapter_id: string | null;
  chapter_order: number;
  chapter_title?: string | null;
  source_excerpt: string | null;
  question_type: BusinessEtiquetteQuestionDraftType;
  title: string;
  stem: string;
  options: BusinessEtiquetteQuestionDraftOption[];
  correct_answer: string | null;
  correct_answers: string[];
  reference_answer: string | null;
  explanation: string | null;
  difficulty: "easy" | "medium" | "hard";
  capability_keys: string[];
  status: BusinessEtiquetteQuestionDraftStatus;
  prompt_template_id: string;
  prompt_template_name: string | null;
  prompt_contract_hash: string;
  prompt_contract_version: string;
  prompt_rendered_hash: string;
  model_config: Record<string, unknown>;
  raw_generation: Record<string, unknown>;
  review_notes: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  question_id: string | null;
  created_at: string;
  updated_at: string;
}
```

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/question-drafts/generate` | 基于章节、能力点和 Prompt 模板生成题目草稿批次 |
| `GET` | `/api/v1/admin/newcomer-training/business-etiquette/question-drafts` | 按章节、题型、能力点、状态、批次筛选草稿箱 |
| `PUT` | `/api/v1/admin/newcomer-training/business-etiquette/question-drafts/{draft_id}` | 编辑待审核草稿 |
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/question-drafts/{draft_id}/approve` | 审批通过并创建正式题库 draft 题目 |
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/question-drafts/{draft_id}/reject` | 拒绝待审核草稿 |
| `GET` | `/api/v1/admin/newcomer-training/business-etiquette/learning-units` | 管理员读取 active path revision 的商务礼仪小单元配置、对应原文章节和能力点；不读取任何学员阅读进度，所有 progress 字段按未完成返回 |
| `GET` | `/api/v1/admin/newcomer-training/business-etiquette/learning-units/{unit_key}/quiz-preview` | 管理员按学员端真实组卷规则预览当前小单元会抽到的已发布题目，不写入作答记录 |

审批 request:

```typescript
interface BusinessEtiquetteQuestionDraftApproveRequest {
  category_id: string; // 必须是 sales_trainer scope 的题库分类
  review_notes?: string | null;
}

interface BusinessEtiquetteQuestionDraftRejectRequest {
  review_notes: string;
}
```

权限、校验与审计:

- 权限复用新人训练路径内容管理能力：`admin`、`super_admin`、`content_admin`、`newcomer_content_admin`；普通学员生成、编辑、审批或拒绝返回 `[ROLE_REQUIRED]`。
- 生成前必须存在训练包 working 或 active revision；缺失返回 `[BUSINESS_ETIQUETTE_TRAINING_PACK_REVISION_MISSING]`。
- 生成前必须已保存能力点快照；`needs_save=true` 时返回 `[BUSINESS_ETIQUETTE_CAPABILITY_SNAPSHOT_MISSING]`。
- `question_types` 只能包含单选、多选、简答；`draft_count` 范围 `1..10`；能力点必须存在且未归档。
- Prompt 模板不存在、停用、ID 非法、用途不匹配、schema 不匹配或编译失败，分别返回 `[BUSINESS_ETIQUETTE_QUESTION_PROMPT_NOT_FOUND]`、`[BUSINESS_ETIQUETTE_QUESTION_PROMPT_INACTIVE]`、`[BUSINESS_ETIQUETTE_QUESTION_PROMPT_INVALID]`、`[BUSINESS_ETIQUETTE_QUESTION_PROMPT_PURPOSE_MISMATCH]`、`[BUSINESS_ETIQUETTE_QUESTION_PROMPT_SCHEMA_MISMATCH]` 或 `[BUSINESS_ETIQUETTE_QUESTION_PROMPT_COMPILE_FAILED:*]`。
- `business_purpose="business_etiquette_question_generation"` 的模板仍必须满足题目草稿生成 contract；如果模板正文或变量明显属于 `ai_coach_interaction_v1` 互动卡片 contract，后端必须拒绝，不能进入 LLM 调用。
- 题目草稿生成 LLM 调用必须声明 OpenAI 兼容 `response_format={"type":"json_object"}`；模板可以承载出题方法论、难度分布和质量检查，但最终输出仍必须是 `drafts`/`questions` JSON，不得输出 Markdown/HTML 页面或绕过 `draft_count` 批量生成。
- 管理端学习内容详情页必须以下拉方式选择 Prompt 模板；模板配置入口为 `/admin/prompts`。可选模板必须优先按 `business_purpose="business_etiquette_question_generation"` 精确筛选；旧数据缺少 `business_purpose` 时，仅允许来自 `category="business_etiquette"`、`category="sales_trainer_ai_coach"` 或历史 `category="sales_trainer"` 且明显为题目生成用途的启用模板作为兼容回退。不得回退展示所有启用模板，不得把销售总结、欢迎词、PPT 提取或 `business_purpose="ai_coach_conversation_generation"` 的 AI 对话教练系统提示词混入题目生成下拉，不得要求运营手填 `PromptTemplate` UUID。
- 管理端学习内容详情页必须以下拉方式选择 LLM 模型配置；模型配置入口为 `/admin/settings` 的「模型配置」标签。`model_config.model_config_id` 只能指向 active LLM 配置；不存在、停用或非 LLM 分别返回 `[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_NOT_FOUND]`、`[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_INACTIVE]`、`[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_INVALID]`。
- AI 输出必须是 JSON，顶层包含 `drafts` 或 `questions` 数组；任一题结构非法时整批失败，返回 `[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_SCHEMA]`，不得写入部分草稿。
- 单选/多选必须有选项且正确答案命中选项；简答必须有 `reference_answer`。
- 只有 `pending_review` 草稿可编辑、审批或拒绝；其他状态返回 `[BUSINESS_ETIQUETTE_QUESTION_DRAFT_NOT_EDITABLE]`。
- 审批创建的正式题状态为 `draft`，标签包含 `business_etiquette`、`chapter:{order}`、`draft:{draft_id}`、`batch:{batch_id}` 和 `capability:{key}`；不自动发布。
- 管理端小测预览必须复用学员端选题规则：仅返回 `status="published"`、`usage_scope="sales_trainer"`、未安全拦截且能力点命中当前小单元的题目；预览不得创建 `BusinessEtiquetteUnitQuizAttempt`，不得检查或消耗当前管理员的学员作答次数。
- 学习内容详情页的 AI 出题入口只能调用本节商务礼仪草稿接口。不得从该页面调用 `/curriculum/test-bank/generation/preview` 或 `/confirm`，不得直接写入通用题库、发布题目、组卷或发布路径配置。
- 操作日志 action：`business_etiquette_question_drafts.generated`、`business_etiquette_question_draft.updated`、`business_etiquette_question_draft.approved`、`business_etiquette_question_draft.rejected`。

### 商务礼仪训练小单元

商务礼仪训练小单元归属于新人训练路径 `business_skills` 模块配置，字段为 `NewcomerPathModuleConfig.learning_units`。它是后台可配置业务规则，不得由学员页面硬生成。缺失时 learner endpoint 返回 `[BUSINESS_ETIQUETTE_LEARNING_UNITS_MISSING]`。

```typescript
interface BusinessEtiquetteTrainingUnitConfig {
  unit_key: string;
  title: string;
  description?: string | null;
  order_index: number;
  enabled: boolean;
  source_chapter_orders: number[]; // 指向原始章节 order_index
  capability_keys: string[];
  unlock_after_unit_keys: string[];
  require_reading: boolean;
  require_quiz: boolean;
  require_ai_coach: boolean;
  ai_coach_required_capability_keys: string[]; // 默认等于 capability_keys
  ai_coach_pass_mastery_level_key: string; // 默认 "basic_mastery"
  ai_coach_ready_mastery_level_key: string; // 默认 "field_ready"
  ai_coach_max_remediation_attempts: number; // 1..20，默认 3
  ai_coach_manual_review_after_max_attempts: boolean; // 默认 true
  ai_coach_block_next_until_passed: boolean; // 默认 true
  ai_coach_remediation_chapter_orders: number[]; // 默认等于 source_chapter_orders
  quiz_question_count: number; // 1..50，默认 5
  quiz_pass_threshold?: number | null; // 0..100；为空时按能力点阈值判断
  quiz_allow_retake: boolean; // 默认 true
  quiz_max_attempts?: number | null; // 1..100；为空不限次数
  quiz_question_type_weights: Partial<Record<
    "single_choice" | "multiple_choice" | "short_answer",
    number
  >>; // 值 >= 0；为空时按题库更新时间取题
  allow_skip_reading: boolean;
  block_next_until_complete: boolean;
  empty_state_message?: string | null;
}
```

当 `require_quiz=true` 或 `require_ai_coach=true` 时，`capability_keys` 必须非空。小单元只保存能力点 key；展示名、阈值、掌握等级和证据规则由训练包能力点快照提供。题量、通过线、是否允许重测、最大次数、题型权重、AI 教练达标等级、可上场等级、补救次数、人工复盘和阻断策略均归属于路径配置中心，不得写死在 learner 页面、测验 service 或 AI 教练组件中。

默认业务配置为 7 个小单元，但默认值只能作为后台初始化/编辑默认，不是 learner 页兜底真源：

1. 职业信任底座：第 1-2 原始章节。
2. 初次见面社交：第 3 原始章节。
3. 商务沟通专业感：第 4 原始章节。
4. 接待与拜访执行：第 5 原始章节。
5. 会议洽谈秩序：第 6 原始章节。
6. 餐饮应酬边界：第 7 原始章节。
7. 综合内化与补救：第 8 原始章节。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/newcomer-training/business-etiquette/learning-units` | 读取当前发布路径下的商务礼仪小单元、对应原文章节和本人阅读进度 |

Response `data`:

```typescript
interface BusinessEtiquetteLearningUnitsResponse {
  module_key: "business_skills";
  learning_content_id: string;
  path_revision_id: string | null;
  path_revision_no: number | null;
  units: Array<BusinessEtiquetteTrainingUnitConfig & {
    capabilities: BusinessEtiquetteCapabilityConfig[]; // 仅来自已发布训练包能力点快照
    chapters: Array<{
      chapter_id: string;
      title: string;
      order_index: number;
      completed: boolean;
    }>;
    progress: {
      completed_chapter_ids: string[];
      total_chapters: number;
      completed_chapters: number;
      is_completed: boolean;
    };
  }>;
}
```

校验与失败语义:

- learner 读取 `/learning-units` 前必须复用 active TrainingJourney 模块准入：无 active revision、无 `business_skills` 模块、模块停用或 `learner_level_required` 不匹配时 fail-closed，返回 404 `[SALES_TRAINER_UNIT_NOT_FOUND]`；不得只靠前端隐藏入口。
- `business_skills` 模块必须存在、启用且为 `"article_exam"`，否则返回 `[BUSINESS_ETIQUETTE_MODULE_CONFIG_MISSING]` 或 `[BUSINESS_ETIQUETTE_MODULE_DISABLED]`。
- 模块必须绑定已发布 `LearningContent`；复用文章绑定错误码 `[LEARNING_CONTENT_NOT_PUBLISHED]`、`[LEARNING_CONTENT_NOT_FOUND]`、`[LEARNING_CONTENT_CHAPTERS_MISSING]`。
- enabled 小单元必须至少绑定一个有效原文章节；配置引用不存在的章节时返回 `[BUSINESS_ETIQUETTE_UNIT_CHAPTERS_MISSING]`。
- `ai_coach_required_capability_keys` 为空时使用 `capability_keys`；非空时必须是 `capability_keys` 子集。`ai_coach_pass_mastery_level_key` / `ai_coach_ready_mastery_level_key` 必须命中能力点快照中的 `mastery_levels[].level_key`，且可上场等级分值不得低于达标等级。
- 阅读进度仍由现有 `LearningProgressService` 和 `/modules/{module_key}/article-progress` 写入；本接口只聚合当前小单元视图。

### 商务礼仪小单元测验

商务礼仪小测由 `BusinessEtiquetteTrainingUnitConfig` 驱动组卷，只允许使用已发布、`usage_scope="sales_trainer"`、未安全拦截且命中小单元能力点的题目。测验提交后冻结路径 revision、训练包能力点快照、题目快照、答案快照和能力点得分，后续配置变更不回写历史尝试。

```typescript
interface BusinessEtiquetteQuizQuestion {
  question_id: string;
  title: string;
  stem: string;
  question_type: "single_choice" | "multiple_choice" | "short_answer";
  points: number;
  order_index: number;
  options: Array<{ value: string; label: string }>;
  capability_keys: string[];
  chapter_orders: number[];
}

interface BusinessEtiquetteUnitQuiz {
  training_pack_key: string;
  learning_unit_key: string;
  learning_unit_title: string;
  path_revision_id: string | null;
  path_revision_no: number | null;
  training_pack_revision_id: string;
  training_pack_revision_no: number;
  question_count: number;
  pass_threshold: number | null;
  allow_retake: boolean;
  max_attempts: number | null;
  capabilities: BusinessEtiquetteCapabilityConfig[];
  questions: BusinessEtiquetteQuizQuestion[];
}

interface BusinessEtiquetteUnitQuizAttemptCreateRequest {
  answers: Array<{
    question_id: string;
    answer_payload: unknown;
  }>;
}

interface BusinessEtiquetteCapabilityScore {
  capability_key: string;
  display_name: string;
  score: number | null;
  max_score: number;
  normalized_score: number | null;
  threshold: number;
  mastered: boolean | null;
  mastery_level_key: string | null;
  mastery_level_name: string | null;
}

interface BusinessEtiquetteUnitQuizAttempt {
  attempt_id: string;
  training_pack_key: string;
  learning_unit_key: string;
  learning_unit_title: string;
  user_id: string;
  user_name?: string | null;
  user_department?: string | null;
  path_revision_id: string | null;
  path_revision_no: number | null;
  training_pack_revision_id: string;
  training_pack_revision_no: number;
  status: "submitted" | "scored" | "failed";
  total_score: number | null;
  max_score: number | null;
  passed: boolean | null;
  capability_scores: BusinessEtiquetteCapabilityScore[];
  weak_capability_keys: string[];
  recommended_chapter_orders: number[];
  answers: Array<{
    question_id: string;
    question_type: "single_choice" | "multiple_choice" | "short_answer";
    answer_payload: unknown;
    is_correct: boolean | null;
    score: number | null;
    max_score: number;
    capability_keys: string[];
    question_snapshot: Record<string, unknown>;
    analysis: string | null; // 提交时固化的逐题解析；简答题优先来自 AI 评分反馈，客观题来自题目解析
    scoring_source:
      | "rule_answer_key"
      | "ai_llm"
      | "ai_llm_pending"
      | "ai_llm_failed"
      | "local_empty_answer"
      | string
      | null;
    scoring_provider: string | null; // AI 评分供应商；规则判分为空
    scoring_model: string | null; // AI 评分模型；规则判分为空
    scoring_latency_ms: number | null; // AI 评分耗时；规则判分为空
  }>;
  submitted_at: string;
}
```

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/newcomer-training/business-etiquette/learning-units/{unit_key}/quiz` | 读取当前小单元测验题目；会校验重测次数 |
| `POST` | `/api/v1/newcomer-training/business-etiquette/learning-units/{unit_key}/quiz-attempts` | 提交当前小单元测验答案并生成能力点得分 |
| `GET` | `/api/v1/newcomer-training/business-etiquette/learning-units/{unit_key}/quiz-attempts?limit=20&offset=0` | 学员查看本人当前小单元的历史小测记录，返回每次提交冻结的答案、得分、能力点诊断和逐题解析 |
| `GET` | `/api/v1/admin/newcomer-training/business-etiquette/quiz-attempts` | 管理端按用户、小单元分页查看测验尝试 |

校验与失败语义:

- learner 读取 quiz、提交 quiz-attempt 或读取本人 quiz-attempt 列表前必须复用 active TrainingJourney 模块准入：无 active revision、无 `business_skills` 模块、模块停用或 `learner_level_required` 不匹配时 fail-closed，返回 404 `[SALES_TRAINER_UNIT_NOT_FOUND]`；不得允许猜测 `unit_key` 绕过 Journey locked 状态。
- `require_quiz=false` 返回 `[BUSINESS_ETIQUETTE_UNIT_QUIZ_DISABLED]`；小单元、模块或训练包未发布时返回对应 Terminal 错误，不允许前端盲目重试。
- 组卷只引用训练包 active revision 中未归档能力点；小单元绑定不存在或已归档能力点返回 `[BUSINESS_ETIQUETTE_UNIT_CAPABILITY_INVALID]`。
- 题库没有可用题时返回 `[BUSINESS_ETIQUETTE_UNIT_QUIZ_QUESTIONS_MISSING]`；不会降级为无能力点题目。
- `quiz_allow_retake=false` 且已有尝试返回 `[BUSINESS_ETIQUETTE_UNIT_QUIZ_RETAKE_NOT_ALLOWED]`；达到 `quiz_max_attempts` 返回 `[BUSINESS_ETIQUETTE_UNIT_QUIZ_ATTEMPT_LIMIT_REACHED]`。
- 提交答案包含非当前测验题目返回 `[BUSINESS_ETIQUETTE_QUIZ_QUESTION_NOT_IN_UNIT]`。
- 单选/多选由题库 `QuestionBankAdapter` 自动判分；`answers[].scoring_source="rule_answer_key"`，前端应展示为“题目解析 / 规则判分”，不得冒充 AI 实时解析。
- 简答题走 `ShortAnswerScoringService`；除空答案 `local_empty_answer` 外，非空答案必须调用 LLM，由模型根据 prompt 中的硬性规则判断玩笑、寒暄、过短、重复或无关答案是否为 0 分。
- 简答题 AI 评分成功时使用 AI 评分反馈作为 `answers[].analysis`，并固化 `answers[].scoring_source="ai_llm"`、`scoring_provider`、`scoring_model`、`scoring_latency_ms`，用于学员端展示和后续审计。
- 简答题 AI 评分失败或无法立即评分时 `status="submitted"`、`passed=null`、`answers[].scoring_source="ai_llm_failed"`，保留后续人工或异步评分空间。
- 管理端查询权限复用新人训练路径内容管理能力；普通学员访问 admin endpoint 返回 `[ROLE_REQUIRED]`。
- 提交成功写入 `business_etiquette_unit_quiz.submitted` 操作日志，metadata 记录 `learning_unit_key`、`training_pack_key`、题量、薄弱能力点和是否通过。

### 商务礼仪 AI 教练达标与补救流

商务礼仪 AI 教练达标流只读取已持久化的白名单 `quiz_card` 事件、`score_result` 和训练局冻结的 `path_config_snapshot.learning_units`。它不得从前端状态、自由追问文本或当前后台草稿配置推断达标结果。每次训练卡提交评分后，后端更新 `coach_state.business_etiquette_progress`、`SalesTrainerAiCoachSession.mastery_state` 和操作日志；流式答题端点的 `answer_scored` snapshot 必须已经包含最新 progress。

```typescript
type BusinessEtiquetteAiCoachProgressStatus =
  | "not_started"
  | "in_progress"
  | "not_mastered"
  | "mastered"
  | "ready"
  | "manual_review";

interface BusinessEtiquetteAiCoachProgress {
  session_id: string;
  module_key: "business_skills";
  learning_unit_key: string;
  learning_unit_title: string;
  status: BusinessEtiquetteAiCoachProgressStatus;
  passed: boolean;
  ready_for_field: boolean;
  manual_review_required: boolean;
  block_next: boolean;
  answered_card_count: number;
  scored_card_count: number;
  remediation_attempt_count: number;
  max_remediation_attempts: number;
  pass_mastery_level_key: string;
  ready_mastery_level_key: string;
  weak_capability_keys: string[];
  recommended_chapter_orders: number[];
  recommended_training_card_types: AiCoachTrainingCardTypeV1[];
  next_step_code:
    | "start_training"
    | "continue_remediation"
    | "manual_review"
    | "mastered"
    | "ready";
  next_step: string;
  capability_scores: BusinessEtiquetteCapabilityScore[];
}
```

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/newcomer-training/business-etiquette/ai-coach/progress?session_id={session_id}&unit_key={unit_key?}` | 读取本人商务礼仪 AI 教练训练局的当前小单元达标、补救、阻断和人工复盘状态 |

规则:

- `unit_key` 未传时，后端按最新 `quiz_card.public_interaction.capability_keys/source_chapter_orders` 匹配小单元；匹配不到时使用当前 session 快照中的第一个 enabled 小单元。
- 达标能力点取 `ai_coach_required_capability_keys`，为空时取 `capability_keys`。每个能力点按训练卡 `score_result.score/max_score` 聚合为 0..100，再映射能力点快照中的 `mastery_levels`。
- `passed=true` 要求所有达标能力点达到 `ai_coach_pass_mastery_level_key`；`ready_for_field=true` 要求所有达标能力点达到 `ai_coach_ready_mastery_level_key`。
- 未达标训练卡次数达到 `ai_coach_max_remediation_attempts` 且 `ai_coach_manual_review_after_max_attempts=true` 时，`status="manual_review"` 且 `manual_review_required=true`。
- `block_next` 由 `ai_coach_block_next_until_passed && !passed` 计算；前端不得自行降低阻断要求。
- `recommended_chapter_orders` 优先使用 `ai_coach_remediation_chapter_orders`，为空时回落到小单元 `source_chapter_orders`。
- `recommended_training_card_types` 来自 session 冻结的 `config_snapshot.allowed_training_card_types`，缺失时安全默认 `["scenario_judgment"]`。
- `next_step` 默认由后端安全兜底文案返回；如需运营调整，应使用 `modules[].guidance_templates.ai_coach_*` 或后续等价后台配置，不得散落在页面组件。

失败语义:

- 非本人 session 返回 `[ACCESS_DENIED]`；session 不存在返回 `[AI_COACH_SESSION_NOT_FOUND]`。
- session 不属于 `business_skills` 返回 `[BUSINESS_ETIQUETTE_AI_COACH_SESSION_INVALID]`。
- session 冻结路径配置非法、没有小单元或等级 key 不存在返回 `[BUSINESS_ETIQUETTE_AI_COACH_CONFIG_INVALID]` / `[BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND]`。
- 能力点快照缺失返回 `[BUSINESS_ETIQUETTE_AI_COACH_CAPABILITY_CONFIG_MISSING]`。
- 训练卡公开互动快照或评分结果损坏返回 `[BUSINESS_ETIQUETTE_AI_COACH_EVENT_INVALID]` / `[BUSINESS_ETIQUETTE_AI_COACH_SCORE_INVALID]`。

### 商务礼仪训练包发布与重练治理

商务礼仪训练包发布是高影响内容治理动作，不等同于把 working revision 标记为 published。发布前必须先生成影响分析，覆盖原文章节、路径小单元、正式题、AI 出题草稿、能力点快照、AI 教练配置和旧学员记录。已存在的阅读进度、测验尝试、AI 教练训练局和评分记录不得被新版本覆盖；重练只能创建新的训练局或后续记录。

```typescript
type BusinessEtiquetteReleaseStrategy =
  | "future_learners_only"
  | "allow_voluntary_switch"
  | "assign_retraining";

interface BusinessEtiquetteReleaseImpactResponse {
  training_pack_key: string;
  active_revision_id?: string | null;
  active_revision_no?: number | null;
  target_revision_id: string;
  target_revision_no: number;
  target_revision_status: "working" | "published" | "archived";
  strategy_options: BusinessEtiquetteReleaseStrategy[];
  config: {
    default_strategy: BusinessEtiquetteReleaseStrategy;
    allow_voluntary_switch: boolean;
    allow_assigned_retraining: boolean;
    max_assigned_retraining_users: number;
    notification_template: string;
    large_change_chapter_threshold: number;
    management_entry: string;
  };
  summary: {
    changed_chapter_count: number;
    impacted_learning_unit_count: number;
    impacted_question_count: number;
    impacted_question_draft_count: number;
    impacted_capability_count: number;
    impacted_ai_coach_config_count: number;
    active_learner_count: number;
    recommended_retraining_user_count: number;
    is_large_change: boolean;
  };
  chapter_changes: Array<{
    chapter_order: number;
    title: string;
    change_type: "added" | "changed" | "removed";
    previous_content_hash?: string | null;
    target_content_hash?: string | null;
  }>;
  impacted_learning_units: Array<{
    unit_key: string;
    title: string;
    source_chapter_orders: number[];
    capability_keys: string[];
    impacted_chapter_orders: number[];
    impacted_capability_keys: string[];
    require_quiz: boolean;
    require_ai_coach: boolean;
  }>;
  impacted_questions: Array<{
    question_id: string;
    draft_id: string;
    title: string;
    question_type: BusinessEtiquetteQuestionDraftType;
    chapter_order: number;
    capability_keys: string[];
  }>;
  impacted_question_drafts: Array<{
    draft_id: string;
    title: string;
    question_type: BusinessEtiquetteQuestionDraftType;
    status: BusinessEtiquetteQuestionDraftStatus;
    chapter_order: number;
    capability_keys: string[];
  }>;
  impacted_capabilities: Array<{
    capability_key: string;
    display_name: string;
    change_type: "added" | "changed" | "removed";
    previous_status?: "draft" | "published" | "archived" | null;
    target_status?: "draft" | "published" | "archived" | null;
  }>;
  impacted_ai_coach_configs: Array<{
    unit_key: string;
    title: string;
    prompt_template_id?: string | null;
    scoring_prompt_template_id?: string | null;
    allowed_training_card_types: AiCoachTrainingCardTypeV1[];
    affected_reason: string;
  }>;
  active_learners: Array<{
    user_id: string;
    user_name?: string | null;
    department?: string | null;
    source_record_types: Array<"quiz_attempt" | "ai_coach_session">;
    latest_path_revision_no?: number | null;
    latest_training_pack_revision_no?: number | null;
    has_active_ai_coach_session: boolean;
  }>;
  recommended_retraining_user_ids: string[];
}
```

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| `GET` | `/api/v1/admin/newcomer-training/business-etiquette/release-impact?training_pack_key={key}&target_revision_id={revision_id?}` | 预览 working/指定训练包修订的发布影响分析 | `sales_trainer.manage_modules` |
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/release` | 发布 working 训练包 revision，并按策略记录影响范围 | `sales_trainer.manage_modules` |
| `POST` | `/api/v1/admin/newcomer-training/business-etiquette/retraining-assignments` | 管理员/培训负责人/运维为指定学员创建新版重练训练局 | `sales_trainer.view_records` 或 `sales_trainer.view_global_records`；内容管理员无权指派人群 |
| `POST` | `/api/v1/newcomer-training/business-etiquette/retraining-sessions` | 学员自愿切换新版并创建新的 AI 教练训练局 | learner 本人 |

发布请求:

```typescript
interface BusinessEtiquetteReleasePublishRequest {
  training_pack_key?: string | null;
  strategy: BusinessEtiquetteReleaseStrategy;
  assigned_user_ids?: string[];
  reason?: string | null;
}

interface BusinessEtiquetteReleasePublishResponse {
  training_pack_key: string;
  active_revision_id: string;
  active_revision_no: number;
  previous_revision_id?: string | null;
  strategy: BusinessEtiquetteReleaseStrategy;
  impact_summary: BusinessEtiquetteReleaseImpactSummaryResponse;
  created_session_ids: string[];
}
```

重练请求:

```typescript
interface BusinessEtiquetteRetrainingStartRequest {
  reason?: string | null;
}

interface BusinessEtiquetteRetrainingAssignmentRequest {
  user_ids: string[];
  reason?: string | null;
}

interface BusinessEtiquetteRetrainingAssignmentResponse {
  created_session_ids: string[];
  skipped_user_ids: string[];
}
```

规则:

- 默认发布策略为 `future_learners_only`：仅移动 active pointer，旧学员继续按旧记录和旧 snapshot 查看，不自动创建新训练局。
- `allow_voluntary_switch` 允许 learner 端显示“重练新版”入口；点击后调用 learner 重练端点并创建 `resume_strategy="new"` 的 AI 教练训练局。后端必须先复用 active TrainingJourney module gate：无 active revision、`business_skills` 模块不存在/停用/locked、`learner_level_required` 不匹配或 path binding 缺失时返回 404 `[SALES_TRAINER_UNIT_NOT_FOUND]`，不得创建 session。
- `assign_retraining` 只允许管理员、运维或具备学员记录查看权限的培训负责人显式传入 `assigned_user_ids`；内容管理员只能治理内容和训练包，不得指定学员重练。人数不得超过 `max_assigned_retraining_users`。系统为每个指定用户创建新的训练局，不修改旧训练局。
- 指定重练的每个目标用户必须是 active learner（`role in {"user","learner"}`），且目标用户本人必须通过 active TrainingJourney `business_skills` module gate；service 层必须复查目标用户对象，不得只相信 route 权限。
- `summary.is_large_change` 由影响分析按 `large_change_chapter_threshold` 判断；`recommended_retraining_user_ids` 只给出候选旧学员，不自动改变发布策略。
- 影响分析读取 working revision；没有 working revision 时可回落 active revision 用于诊断，但发布必须有 working revision。
- 发布成功写入 `business_etiquette_training_pack.released` 操作日志，metadata 记录 `training_pack_key`、`active_revision_id`、`strategy`、`impact_summary`、`created_session_ids` 和 `trace_id`。
- 学员自愿重练写入 `business_etiquette_training_pack.voluntary_retraining_started`；管理员指定重练写入 `business_etiquette_training_pack.retraining_assigned`。
- 通知模板、策略默认值、指定重练人数上限和大变更阈值必须来自 `BusinessEtiquetteReleaseSettings` 或后续后台配置，不得散落在页面组件中。

失败语义:

- 无 working revision 发布返回 `[BUSINESS_ETIQUETTE_TRAINING_PACK_REVISION_MISSING]`。
- 非法发布策略或策略被配置禁用返回 `[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_INVALID]`。
- 指定重练缺少用户或超过人数上限返回 `[BUSINESS_ETIQUETTE_RETRAINING_ASSIGNMENT_INVALID]`。
- learner 自愿重练在配置禁用时返回 `[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_INVALID]`。
- 内容管理员或其他无学员记录权限账号调用指定重练返回 403 `[ROLE_REQUIRED]`。
- 指定重练目标用户不存在返回 404 `[BUSINESS_ETIQUETTE_RETRAINING_USER_NOT_FOUND]`；目标用户非 active learner 返回 422 `[BUSINESS_ETIQUETTE_RETRAINING_TARGET_INVALID]`；目标用户当前不可进入商务礼仪模块返回 404 `[BUSINESS_ETIQUETTE_RETRAINING_TARGET_NOT_ALLOWED]`。

### 考卷管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/papers` | 考卷列表，支持 `include_archived`、`limit`、`offset` |
| `POST` | `/api/v1/admin/sales-trainer/papers` | 创建考卷，默认 `draft`，同步创建兼容 quiz 执行单元 |
| `PUT` | `/api/v1/admin/sales-trainer/papers/{paper_id}` | `draft` 考卷直接更新；已发布考卷保存为 working revision，active learner 内容不变 |
| `GET` | `/api/v1/admin/sales-trainer/papers/{paper_id}/revisions` | 查看考卷历史修订，返回 active/working 标记和影响摘要 |
| `POST` | `/api/v1/admin/sales-trainer/papers/{paper_id}/publish` | 初次发布考卷或发布最新 working revision，并移动 active pointer，只影响未来学员 |
| `POST` | `/api/v1/admin/sales-trainer/papers/{paper_id}/rollback` | 回滚到指定 published revision，必须提交原因；只影响未来学员并写审计 |
| `POST` | `/api/v1/admin/sales-trainer/papers/{paper_id}/archive` | 归档考卷，并停用绑定执行单元 |

Create request:

```typescript
interface ExamPaperCreate {
  paper_key: string;
  title: string;
  description?: string | null;
  module_key?: string;
  pass_threshold?: number | null;
  questions: Array<{
    question_id: string;
    order_index?: number;
    points?: number;
  }>;
}
```

Response `data`: `ExamPaper`；列表返回 `{ items: ExamPaper[], total: number }`；历史版本返回 `{ items: ExamPaperRevision[], total: number }`。

`/api/v1/admin/newcomer-training/papers`、`/api/v1/admin/newcomer-training/papers/{paper_id}/revisions`、`/publish`、`/rollback` 和 `/archive` 是新人训练路径 admin 别名，语义与 `/admin/sales-trainer/papers` 一致。

回滚 Request:

```typescript
interface PaperRollbackRequest {
  target_revision_id: string;
  reason: string;
}
```

回滚成功返回 `ExamPaper` 当前 active 投影；审计事件必须记录 `exam_paper_revision_rolled_back`、`before_revision_id`、`after_revision_id`、`reason` 和 `future_only=true`。

### 训练材料库

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/materials` | 材料列表，支持 `include_archived`、`limit`、`offset` |
| `POST` | `/api/v1/admin/sales-trainer/materials` | 创建材料主档，默认 `draft` |
| `PUT` | `/api/v1/admin/sales-trainer/materials/{material_id}` | 更新未归档材料主档元数据；已发布材料记录 before/after 审计，影响后续提交解释 |
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/archive` | 归档材料；若 active/working 新人训练路径仍引用该材料或其版本，返回 `[MATERIAL_ARCHIVE_ACTIVE_REFERENCE]` |
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/versions` | 为材料新增版本，默认 `draft` |
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/versions/upload` | 上传文件并为材料新增版本，默认 `draft` |
| `POST` | `/api/v1/admin/sales-trainer/materials/versions/{version_id}/publish` | 发布版本并设为当前版本 |
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/versions/rollback/preview` | 预览恢复指定历史版本为当前版本；不修改历史提交 |
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/versions/rollback` | 恢复指定已发布/已归档版本为当前版本；只影响后续提交 |
| `GET` | `/api/v1/admin/sales-trainer/materials/versions/{version_id}/file` | 后台读取已发布材料版本文件，仅 `admin` / `super_admin` / `content_admin` / `newcomer_content_admin` / `ops` / `operator` / `operations` / `sre` |

后台材料文件读取同样只允许 `published` 版本；`draft` / `archived` 返回 `[MATERIAL_VERSION_NOT_PUBLISHED]`。历史提交引用的 archived 材料版本不得通过上述 learner/admin 当前版本文件接口伪装回放，必须走训练记录历史回放接口，且只能读取该记录冻结引用的材料版本。

Create material request:

```typescript
interface SalesTrainerMaterialCreate {
  material_key: string;
  name: string;
  material_type?: "ppt_deck" | "script" | "example_audio" | "attachment";
  description?: string | null;
  purpose?: string;
}
```

Create version request:

```typescript
interface SalesTrainerMaterialVersionCreate {
  version_label: string;
  title: string;
  file_name: string;
  content_type: string;
  file_size_bytes: number;
  storage_key: string;
  file_hash?: string | null;
  release_notes?: string | null;
}
```

Upload version request:

```typescript
// multipart/form-data
interface SalesTrainerMaterialVersionUpload {
  version_label: string;
  title: string;
  release_notes?: string | null;
  file: File;
}
```

Version rollback request:

```typescript
interface SalesTrainerMaterialVersionRollbackRequest {
  target_version_id: string;
  reason: string;
}
```

版本发布规则:

- 同一材料同一 `version_label` 唯一。
- 发布版本时，材料主档状态变为 `published`，`current_version_id` 指向该版本。
- 同一材料旧的 published 版本自动归档，保证“最新版”定义唯一。
- 材料版本 rollback 只能恢复同一材料下 `published` 或 `archived` 历史版本为当前版本；必须提供 reason，写 `material_version_rolled_back` 操作日志，返回 `historical_submissions_changed=false` 与 `historical_replay_preserved=true`。
- 更新已发布材料主档只修改名称、用途、描述等元数据，不覆盖历史提交中冻结的 `material_snapshot`；审计事件为 `material_metadata_updated`，必须包含 `before`、`after`、`changed_fields`、`trace_id`、`future_only` 和 `impact_scope="future_submissions_only"`。
- 管理员可通过 multipart 上传文件生成草稿版本；系统自动记录 `file_name`、`content_type`、`file_size_bytes`、`storage_key`、`file_hash`，并写 `material_version_uploaded` 操作日志。发布仍需调用发布接口，避免上传草稿直接影响学员端。
- multipart 上传第一版支持 `local` 和 `cos` 服务端落库；`oss` 或其他对象存储暂走元数据登记接口，避免后台静默把文件保存到错误位置。
- 保留元数据登记接口用于已有对象存储文件迁移或运维补录；普通管理员页面默认使用上传接口。

### 音频提交

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/audio-submissions` | 音频提交列表，支持 `user_id`、`limit`、`offset` |
| `GET` | `/api/v1/admin/sales-trainer/audio-submissions/{submission_id}` | 音频提交详情 |
| `GET` | `/api/v1/admin/sales-trainer/audio-submissions/{submission_id}/file` | 读取原始音频文件 |
| `POST` | `/api/v1/admin/sales-trainer/audio-submissions/{submission_id}/retry-transcription` | 重试转写 |
| `POST` | `/api/v1/admin/sales-trainer/audio-submissions/{submission_id}/retry-scoring` | 重试评分 |

`/file` 响应语义与 learner `/file` 一致；`admin` 访问范围为所有提交，培训负责人仅限同部门提交。

### AI 评分结果

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/score-results` | 评分结果列表，支持 `user_id`、`submission_id`、`limit`、`offset` |

Response `data`:

```typescript
interface AudioScoreResultListResponse {
  items: AudioScoreResult[];
  total: number;
}
```

### 评分提示词

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/audio-score-prompts` | 提示词列表，支持 `include_archived` |
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts` | 创建提示词，默认 `draft` |
| `PUT` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}` | `draft` 直接更新；已发布提示词保存为待发布修订，当前评分依据不变 |
| `GET` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/revisions` | 列出 Prompt 历史修订，标记 active/working |
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish` | 发布提示词 |
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/rollback/preview` | 预览回滚到目标 published revision 的影响；不修改历史评分 |
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/rollback` | 回滚当前 Prompt 到目标 published revision；只影响后续评分 |

Create request:

```typescript
interface AudioScorePromptCreate {
  name: string;
  purpose?: string;
  system_prompt: string;
  scoring_template: string;
  output_schema?: Record<string, unknown>;
  learner_rubric?: Record<string, unknown>;
}
```

Update request:

```typescript
interface AudioScorePromptUpdate {
  name?: string;
  purpose?: string;
  system_prompt?: string;
  scoring_template?: string;
  output_schema?: Record<string, unknown>;
  learner_rubric?: Record<string, unknown>;
}
```

Rollback request:

```typescript
interface AudioScorePromptRollbackRequest {
  target_revision_id: string;
  reason: string;
}
```

校验规则:

- `scoring_template` 必须包含 `{transcript}`。
- `learner_rubric` 必须是对象；维度、权重、常见扣分点和通过线作为评分方案配置读取，不得散落在页面。
- 已发布提示词编辑必须生成 working revision，并标记为高风险评分规则修改；发布该修订后只影响后续录音评分，历史评分结果继续引用提交时 prompt、rubric 或 hash。
- Prompt rollback 只能回滚到同一 Prompt 下已发布 revision；必须提供 reason，记录 `audio_score_prompt_revision_rolled_back` 操作日志，且返回 `historical_submissions_changed=false`。
- 已归档提示词不可继续编辑，返回 `[SCORING_PROMPT_NOT_EDITABLE]`。

### 学员训练记录

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/training-records` | 统一训练记录列表，支持 `user_id`、`unit_id`、`material_version_id`、`training_stage`、`module_key`、`learner_level`、`role_level`、`status`、`limit`、`offset` |
| `GET` | `/api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}` | 统一训练记录详情，`record_type` 只允许 `audio_submission`、`quiz_attempt`、`ai_coach_session`、`business_etiquette_quiz_attempt`、`realtime_roleplay_session` |
| `GET` | `/api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}/materials/{version_id}/file` | 历史材料只读回放；当前仅 `audio_submission.confirmed_material_version_id` 支持 archived/published 版本读取，并复用记录查看权限与部门 scope；非音频记录类型返回 `[TRAINING_RECORD_MATERIAL_REPLAY_UNSUPPORTED]`/400 |
| `GET` | `/api/v1/admin/sales-trainer/training-records/audio/{submission_id}` | 录音训练记录详情兼容入口；内部委托统一详情接口 |
| `GET` | `/api/v1/admin/sales-trainer/training-records/realtime-roleplay/{session_id}/observations` | 实时对练角色一致性旁路观测，只读返回 `roleplay_observation_v1` 记录；复用训练记录查看权限与部门 scope |
| `GET` | `/api/v1/admin/sales-trainer/manager-dashboard` | 阶段 2 管理者看板，聚合完成率、通过率、风险学员、弱项维度和干预建议 |
| `GET` | `/api/v1/admin/sales-trainer/readiness/workbench` | 达标验收工作台，按验收状态分组聚合学员 |
| `GET` | `/api/v1/admin/sales-trainer/readiness/dossiers/{learner_id}` | 单个学员训练达标档案，聚合证据、能力项、复核记录和下一阶段 gate |
| `POST` | `/api/v1/admin/sales-trainer/readiness/dossiers/{learner_id}/review-actions` | 创建复核动作并写入操作日志，支持确认达标、要求重练和人工跟进 |

Response `data`:

```typescript
interface SalesTrainerTrainingRecordListResponse {
  items: Array<{
    record_id: string;
    record_type: "audio_submission" | "quiz_attempt" | "ai_coach_session" | "business_etiquette_quiz_attempt" | "realtime_roleplay_session";
    path_key?: string | null;
    path_revision_id?: string | null;
    path_revision_no?: number | null;
    module_key?: string | null;
    legacy_snapshot_only: boolean;
    training_stage?: TrainingStage | null;
    learner_level?: LearnerLevel | null;
    role_level?: LearnerLevel | null;
    unit_id: string;
    unit_name?: string | null;
    unit_type: "quiz" | "audio_scoring" | "ai_coach" | "business_etiquette_quiz" | "realtime_roleplay";
    user_id: string;
    user_name?: string | null;
    user_department?: string | null;
    status: string;
    score?: number | null;
    max_score?: number | null;
    passed?: boolean | null;
    submitted_at?: string | null;
    material_snapshot?: TrainingRecordMaterialSnapshot | null;
    score_scheme_snapshot?: TrainingRecordScoreSchemeSnapshot | null;
    task_brief_snapshot?: TrainingRecordTaskBriefSnapshot | null;
    audio_submission?: AudioSubmission | null;
    quiz_attempt?: QuizAttempt | null;
    ai_coach_session?: TrainingRecordAiCoachSessionSnapshot | null;
    business_etiquette_quiz_attempt?: TrainingRecordBusinessEtiquetteQuizAttemptSnapshot | null;
    realtime_roleplay_session?: TrainingRecordRealtimeRoleplaySessionSnapshot | null;
    operation_logs?: TrainingRecordOperationLog[];
    effective_score?: TrainingRecordEffectiveScore | null;
    latest_regrade?: TrainingRecordLatestRegradeSnapshot | null;
    score_explanation?: TrainingRecordScoreExplanationSnapshot | null;
    ability_profile?: TrainingRecordAbilityProfileSnapshot | null;
    remediation?: TrainingRecordRemediationSnapshot | null;
  }>;
  total: number;
}

interface TrainingRecordEffectiveScore {
  score?: number | null;
  max_score?: number | null;
  passed?: boolean | null;
  source: "original_record" | "latest_regrade";
  original_score?: number | null;
  original_max_score?: number | null;
  original_passed?: boolean | null;
  score_delta?: number | null;
  latest_regrade_run_id?: string | null;
  latest_regrade_error_code?: string | null;
  history_overwrite: false;
}

interface TrainingRecordLatestRegradeSnapshot {
  regrade_run_id: string;
  target_type: string;
  target_revision_id?: string | null;
  status: string;
  reason?: string | null;
  trace_id?: string | null;
  created_at?: string | null;
  before_snapshot?: Record<string, unknown> | null;
  after_snapshot?: Record<string, unknown> | null;
}

interface TrainingRecordScoreExplanationItem {
  type?: string | null;
  key?: string | null;
  label?: string | null;
  text?: string | null;
  score?: number | null;
  max_score?: number | null;
  is_weak?: boolean | null;
  [key: string]: unknown;
}

interface TrainingRecordScoreExplanationSnapshot {
  basis: string;
  summary?: string | null;
  dimensions: TrainingRecordScoreExplanationItem[];
  evidence: TrainingRecordScoreExplanationItem[];
  strengths?: string[];
  issues: TrainingRecordScoreExplanationItem[];
  next_actions: TrainingRecordScoreExplanationItem[];
  [key: string]: unknown;
}

interface TrainingRecordAbilityProfileSnapshot {
  basis: "sales_trainer_phase2_projection_v1";
  overall_score?: number | null;
  overall_passed?: boolean | null;
  dimensions: TrainingRecordScoreExplanationItem[];
  weak_dimensions: TrainingRecordScoreExplanationItem[];
  evidence_count: number;
  [key: string]: unknown;
}

interface TrainingRecordRemediationSnapshot {
  needed: boolean;
  reason: string;
  action_label: string;
  target_path: string;
  priority: "low" | "medium" | "high";
  weak_dimension_keys?: string[];
  [key: string]: unknown;
}

interface TrainingRecordMaterialSnapshot {
  version?: number | null;
  items: Record<string, unknown>[];
  confirmed_material_version_id?: string | null;
  frozen_at?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordScoreSchemePromptSnapshot {
  prompt_id?: string | null;
  name?: string | null;
  purpose?: string | null;
  system_prompt?: string | null;
  scoring_template?: string | null;
  output_schema: Record<string, unknown>;
  learner_rubric: Record<string, unknown>;
  version?: number | null;
  status?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordScoreSchemeSnapshot {
  prompt_id?: string | null;
  name?: string | null;
  purpose?: string | null;
  version?: number | null;
  status?: string | null;
  learner_rubric: Record<string, unknown>;
  pass_threshold?: number | null;
  prompt_snapshot?: TrainingRecordScoreSchemePromptSnapshot | null;
  [key: string]: unknown;
}

interface TrainingRecordTaskBriefSnapshot {
  enabled?: boolean | null;
  title?: string | null;
  purpose?: string | null;
  scenario?: string | null;
  instructions: unknown[];
  success_criteria: unknown[];
  common_mistakes: unknown[];
  upload_guidance?: string | null;
  submission_context?: Record<string, unknown> | null;
  [key: string]: unknown;
}

interface TrainingRecordOperationLog extends OperationLog {
  // 只在训练记录详情/记录回放上下文中附加；不会改写原始 operation log metadata。
  training_context?: {
    path_key?: string | null;
    path_revision_id?: string | null;
    path_revision_no?: number | null;
    training_stage?: TrainingStage | null;
    learner_level?: LearnerLevel | null;
    role_level?: LearnerLevel | null;
  };
}

interface TrainingRecordBusinessEtiquetteCapabilitySnapshot {
  capabilities: unknown[];
  chapter_bindings: unknown[];
  [key: string]: unknown;
}

interface TrainingRecordBusinessEtiquetteQuestionSnapshot {
  question_id?: string | null;
  title?: string | null;
  stem?: string | null;
  question_type?: string | null;
  options?: unknown[];
  reference_answer?: string | null;
  explanation?: string | null;
  scoring_dimensions?: string[];
  tags?: string[];
  points?: number | null;
  order_index?: number | null;
  version?: number | null;
  content_hash?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordBusinessEtiquetteAnswerSnapshot {
  question_id?: string | null;
  question_type?: string | null;
  answer_payload?: unknown;
  is_correct?: boolean | null;
  score?: number | null;
  max_score?: number | null;
  capability_keys?: string[];
  question_snapshot?: TrainingRecordBusinessEtiquetteQuestionSnapshot | null;
  analysis?: string | null;
  scoring_source?: string | null;
  scoring_provider?: string | null;
  scoring_model?: string | null;
  scoring_latency_ms?: number | null;
  [key: string]: unknown;
}

interface TrainingRecordBusinessEtiquetteCapabilityScoreSnapshot {
  capability_key: string;
  display_name?: string | null;
  score?: number | null;
  max_score?: number | null;
  normalized_score?: number | null;
  threshold?: number | null;
  mastered?: boolean | null;
  mastery_level_key?: string | null;
  mastery_level_name?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordBusinessEtiquetteQuizAttemptSnapshot {
  attempt_id: string;
  training_pack_key: string;
  learning_unit_key: string;
  learning_unit_title: string;
  user_id: string;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  training_pack_revision_id?: string | null;
  training_pack_revision_no?: number | null;
  capability_snapshot: TrainingRecordBusinessEtiquetteCapabilitySnapshot;
  question_snapshots: TrainingRecordBusinessEtiquetteQuestionSnapshot[];
  answers: TrainingRecordBusinessEtiquetteAnswerSnapshot[];
  capability_scores: TrainingRecordBusinessEtiquetteCapabilityScoreSnapshot[];
  weak_capability_keys: string[];
  recommended_chapter_orders: number[];
  total_score?: number | null;
  max_score?: number | null;
  passed?: boolean | null;
  status: string;
  submitted_at?: string | null;
}

interface TrainingRecordAiCoachSessionSnapshot {
  session_id: string;
  module_key?: string | null;
  path_key?: string | null;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  article_snapshot?: TrainingRecordAiCoachArticleSnapshot | null;
  path_config_snapshot?: TrainingRecordAiCoachPathConfigSnapshot | null;
  config_snapshot?: TrainingRecordAiCoachConfigSnapshot | null;
  coach_state?: TrainingRecordAiCoachStateSnapshot | null;
  prompt_template_id?: string | null;
  prompt_revision_id?: string | null;
  prompt_contract_hash?: string | null;
  mastery_state?: string | null;
  total_score?: number | null;
  max_score?: number | null;
  status: string;
  trace_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface TrainingRecordAiCoachArticleSnapshot {
  title?: string | null;
  chapters?: Array<{ title?: string | null; [key: string]: unknown }>;
  [key: string]: unknown;
}

interface TrainingRecordAiCoachPathConfigSnapshot {
  module_key?: string | null;
  module_type?: string | null;
  title?: string | null;
  learning_content_id?: string | null;
  exam_paper_id?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordAiCoachConfigSnapshot {
  enabled?: boolean | null;
  chat_enabled?: boolean | null;
  min_turns?: number | null;
  max_turns?: number | null;
  mastery_threshold?: number | null;
  prompt_template_id?: string | null;
  prompt_revision_id?: string | null;
  scoring_prompt_template_id?: string | null;
  scoring_prompt_revision_id?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordAiCoachStateSnapshot {
  session_phase?: string | null;
  active_event_id?: string | null;
  answered_card_count?: number | null;
  correct_streak?: number | null;
  incorrect_streak?: number | null;
  current_focus?: string | null;
  difficulty?: string | null;
  last_action?: string | null;
  can_auto_advance?: boolean | null;
  stopped_reason?: string | null;
  business_etiquette_progress?: Record<string, unknown> | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeBindingSnapshot {
  owner: "sales_trainer";
  path_key?: string | null;
  path_revision_id?: string | null;
  path_revision_no?: number | null;
  module_key?: string | null;
  binding_key?: string | null;
  runtime_descriptor_id?: string | null;
  scenario_key?: string | null;
  runtime_config_revision_id?: string | null;
  runtime_registry?: TrainingRecordRealtimeRuntimeRegistrySnapshot | null;
  roleplay_contract_revision_id?: string | null;
  practice_template_id?: string | null;
  provider_readiness_snapshot?: TrainingRecordRealtimeProviderReadinessSnapshot | null;
  failure_policy?: TrainingRecordRealtimeFailurePolicySnapshot | null;
  started_by_user_id?: string | null;
  started_at?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeRegistryReadinessSnapshot {
  ready?: boolean | null;
  checked_at?: string | null;
  failure_code?: string | null;
  failure_message?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeRegistryDescriptorSnapshot {
  descriptor_id?: string | null;
  label?: string | null;
  provider?: string | null;
  runtime_owner?: string | null;
  enabled?: boolean | null;
  runtime_profile_id?: string | null;
  config_revision_id?: string | null;
  rollback_to_descriptor_id?: string | null;
  readiness?: TrainingRecordRealtimeRegistryReadinessSnapshot | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeRuntimeRegistrySnapshot {
  registry_key?: string | null;
  config_id?: string | null;
  version?: number | null;
  source?: string | null;
  status?: string | null;
  fallback_reason?: string | null;
  descriptor?: TrainingRecordRealtimeRegistryDescriptorSnapshot | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeProviderReadinessSnapshot {
  provider?: string | null;
  ready?: boolean | null;
  checked_at?: string | null;
  config_revision_id?: string | null;
  failure_code?: string | null;
  failure_message?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeFailurePolicySnapshot {
  terminal_codes?: string[];
  transient_codes?: string[];
  voluntary_codes?: string[];
  terminal_retry_allowed?: boolean | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeScoresSnapshot {
  logic_score?: number | null;
  accuracy_score?: number | null;
  completeness_score?: number | null;
}

interface TrainingRecordRealtimeVoicePolicySnapshot {
  external_binding?: TrainingRecordRealtimeBindingSnapshot | null;
  voice_mode?: string | null;
  runtime_profile_id?: string | null;
  model_name?: string | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeEffectivenessSnapshot {
  summary?: string | null;
  evaluable?: boolean | null;
  main_issue?: Record<string, unknown> | null;
  dimension_scores?: Record<string, unknown> | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeRuntimeStateSnapshot {
  state?: string | null;
  session_status?: string | null;
  ai_state?: string | null;
  turn_count?: number | null;
  [key: string]: unknown;
}

interface TrainingRecordRealtimeRuntimeOutcomeSnapshot {
  external_binding: TrainingRecordRealtimeBindingSnapshot;
  voice_policy_snapshot: TrainingRecordRealtimeVoicePolicySnapshot;
  effectiveness_snapshot: TrainingRecordRealtimeEffectivenessSnapshot;
  runtime_state: TrainingRecordRealtimeRuntimeStateSnapshot;
  scores: TrainingRecordRealtimeScoresSnapshot;
}

interface TrainingRecordRealtimeRoleplaySessionSnapshot {
  session_id: string;
  module_key?: string | null;
  status: string;
  score?: number | null;
  max_score?: number | null;
  passed?: boolean | null;
  submitted_at?: string | null;
  completed_at?: string | null;
  external_binding: TrainingRecordRealtimeBindingSnapshot;
  snapshot: TrainingRecordRealtimeRuntimeOutcomeSnapshot;
}

type SalesTrainerTrainingRecordDetailResponse =
  SalesTrainerTrainingRecordListResponse["items"][number];
```

顶层 `score`、`max_score`、`passed` 是原始记录分，必须来自原始 `AudioScoreResult`、`SalesTrainerQuizAttempt`、AI Coach session summary 或 realtime runtime outcome projection；历史重评不得覆盖这些字段。`effective_score` 是面向管理和学员反馈的当前有效分投影。若存在最近一次成功历史重评且 `after_snapshot` 形成可用分数，则 `source="latest_regrade"`，`score` / `passed` 取重评结果；否则取原始记录。能力画像、补救动作和管理者看板必须使用 `effective_score`。

列表分页必须由数据库层统一窗口负责：audio、quiz、AI Coach、business etiquette quiz、realtime 五类记录使用 `UNION ALL` 后按 `submitted_at DESC` 全局排序，再执行 `limit/offset`。`total` 必须使用同一套 union 查询。筛选语义固定为：`user_id` 五类记录都过滤；`unit_id` 只命中 audio/quiz，AI Coach、business etiquette quiz 和 realtime 当前无 `unit_id` 时排除；`material_version_id` 只命中 audio 的 `confirmed_material_version_id`，quiz/AI Coach/business etiquette quiz/realtime 排除；`team_department` 五类记录都通过 `User.department` 限定。

`module_key`、`training_stage`、`learner_level`、`role_level` 属于 TrainingJourney 上下文筛选。后端必须先按基础权限和对象范围取统一记录窗口，再用 active path revision 的 Journey 投影补齐 `training_stage`、`learner_level`、`role_level`，最后执行筛选和分页；不得让前端从 raw id 或局部记录自行推断等级。`training_stage` 表示 learner 当前整体训练阶段，不等同于单条记录 `status`。`status` 表示单条训练记录原始状态，用于管理端按提交、评分、完成、失败等记录状态过滤。无权限、无 active path revision 或 Journey 投影失败时，不得扩大数据范围；匹配结果为空即可返回 `items=[]`、`total=0`。

`realtime_roleplay_session` 记录必须由 runtime outcome projection 只读提供：只接受 completed `stepfun_realtime` session，且 `voice_policy_snapshot.external_binding.owner="sales_trainer"`。详情返回 `realtime_roleplay_session.snapshot.external_binding`、运行时策略快照、效果快照、runtime_state 和三项 runtime scores；`sales_trainer` 不得直接创建或变更 runtime session。实时对练当前没有材料版本，材料文件回放接口不得为该类型伪造材料访问。

角色一致性旁路观测契约：

```typescript
type RoleplayComplianceMode = "record_only";
type RoleplayMainChainEffect = "none";
type RoleplayObservationSource = "heuristic" | "llm_evaluator";
type RoleplayObservationStatus = "pending" | "completed" | "failed" | "ignored";
type RoleplayComplianceAction =
  | "record_signal"
  | "next_turn_soft_steering";
type RetiredRoleplayComplianceAction =
  | "cancel_current_turn"
  | "regenerate_current_turn"
  | "repair_audio";

interface RoleplayObservation {
  observation_id: string;
  session_id: string;
  source_record_id: string;
  source: RoleplayObservationSource;
  turn_index: number;
  evaluator_status: RoleplayObservationStatus;
  compliance_mode: RoleplayComplianceMode;
  main_chain_effect: RoleplayMainChainEffect;
  dimensions: Array<Record<string, unknown>>;
  signals: Array<Record<string, unknown>>;
  next_turn_soft_steering?: {
    action: "next_turn_soft_steering";
    blocking: false;
    target_turn_index: number;
    suggestion_summary: string;
    consumed_by_next_turn?: boolean | null;
  } | null;
  retired_action?: RetiredRoleplayComplianceAction | null;
  error?: { code?: string | null; message?: string | null; [key: string]: unknown } | null;
  trace_id?: string | null;
  created_at: string;
  updated_at: string;
}

interface RoleplayObservationSessionResponse {
  session_id: string;
  source_record_id: string;
  total: number;
  latest_turn_index?: number | null;
  source_counts: Record<string, number>;
  status_counts: Record<string, number>;
  items: RoleplayObservation[];
}
```

- `roleplay_observation_v1` 固定为 `record_only`，`compliance_mode` 必须为 `"record_only"`，`main_chain_effect` 和 `dimensions[].main_chain_effect` 必须为 `"none"`；该链路只记录风险 signal，不得改变实时会话状态、不得触发 learner 弹窗、不得阻断、取消、重生成或修复 StepAudio 2.5 realtime 输出。
- capture sink 只在 `voice_policy_snapshot.external_binding.owner="sales_trainer"` 的 session 注入；写入使用独立 DB session 和 `append_observation(non_blocking=true)`。sink、evaluator 或 DB 写入异常只记录 warning，不向 WebSocket 主链路抛出。
- observation policy 的当前冻结来源是 `voice_policy_snapshot.roleplay_observation_policy`；缺失或非法时使用 bundled default：`heuristic.enabled=true`、`llm.enabled=false`、`compliance_mode="record_only"`。该 policy 只影响旁路观测和可选 next-turn soft steering，不得改变 runtime admission、WS close code、当前 turn 输出或 learner 可见反馈。
- `source="heuristic"` 表示同步轻量规则检查；若 policy 开启 `llm.enabled=true`，capture sink 先同步写 heuristic，再 fire-and-forget 触发 `evaluate_background()`，并把结果写成单独的 `source="llm_evaluator"` observation。LLM `success` 写 `completed`；`timeout`、`failed`、`invalid_json`、`not_configured` 写 `failed` observation；所有情况都保持 warning-only，不阻断 WS。
- `signals` 可包含 `prompt_leak_risk`、`coach_mode_keywords`、`early_close_keywords`、`kb_fact_without_evidence`、`stage_keyword_conflict`、`too_many_questions` 等风险 key；这些 key 均是后台复盘线索，不是实时拦截结论。
- `next_turn_soft_steering` 只允许表达下一轮非阻断提示建议，不能取消当前 turn、不能重写当前 transcript、不能触发同步 regenerate/repair audio、不能影响当前或下一轮 admission。若下一轮指令编译消费该建议，必须在 observation 或 runtime diagnostic 中留下 `consumed_by_next_turn=true`、source observation id 和 `trace_id`；未消费或消费失败不得升级为错误。
- `retired_action` 仅用于审计发现旧数据或旧配置字段；新写入记录不得设置该字段为非空。`cancel_current_turn`、`regenerate_current_turn`、`repair_audio` 已正式退役，任何隐藏配置、环境变量或未登记 policy 字段都不得把它们重新变为运行时动作。恢复阻断/中断/同步修复能力必须另起 ADR，不能靠配置开关暗中开启。
- `dimensions` 可保存 capture metadata，例如 `speaker`、`source_event_type`、`response_id`、`turn_id`、`template_stage_key`、`instruction_contract_hash`、安全 grounding 摘要和 `trace_id`。不得保存 StepFun thinking、secret、API key、Authorization、Cookie 或完整内部 payload。
- secret hygiene：观测表 `sales_trainer_roleplay_observations.dimensions/signals/error` 只能保存脱敏后的短文本证据、风险 key 和诊断码；不得保存真实密钥、Authorization/Cookie/JWT、StepFun raw event、完整 prompt、完整上游 payload 或 provider request/response。日志同样只能输出 warning 事件名、`trace_id/session_id/turn_index/source/error_code`，不得输出观测文本原文中的 secret。
- 权限：只有具备训练记录查看能力的 admin/support/training lead/ops 可读取；培训负责人仍受 department scope 限制。对象级授权必须先通过统一训练记录详情能力确认该 `session_id` 对当前 viewer 可见，再读取 observations。无权限返回 `[ROLE_REQUIRED]`，不在对象范围内返回 `[TRAINING_RECORD_NOT_FOUND]`，不得通过 observation endpoint 泄露 session 是否存在。
- migration apply：`20260702_1530_089_sales_trainer_roleplay_observations` 只新增 append-only sidecar 表、唯一去重约束和查询索引；不回填历史 turns，不修改 `practice_sessions`，不改变 training record 详情主响应。
- migration rollback：downgrade 仅删除 observation sidecar 表和索引；不删除或改写 realtime session、TrainingJourney、runtime outcome projection 或 operation log。非空 observation 表 downgrade 默认拒绝执行；只有完成导出/审批并显式设置 `ALLOW_SALES_TRAINER_ROLEPLAY_OBSERVATION_DESTRUCTIVE_DOWNGRADE=1` 后，才允许破坏性删除该 append-only 审计数据。业务回滚优先停止注入 sink 或隐藏后台 observation 读取入口。
- 回滚：停止注入 observation sink 即可关闭新写入；已写 observation 行保留为历史审计，前端可降级展示训练记录 runtime snapshot。

统一详情接口返回单条 `SalesTrainerTrainingRecordDetailResponse`，必须包含当前有效分、原始分、最近重评、评分解释、能力画像、补救动作、原始记录摘要和可见操作日志。详情回放必须用 active path revision 的 TrainingJourney 投影补齐顶层 `training_stage`、`learner_level`、`role_level`；可见 `operation_logs[]` 在序列化回放时必须附加同源 `training_context`，让审计记录能解释当时查看的路径版本、训练阶段、学员等级和角色等级。该字段是回放 DTO 扩展，不允许静默改写历史 operation log 的原始 `metadata`。非法 `record_type` 返回 `[TRAINING_RECORD_TYPE_INVALID]`，不存在或不在 `_team_scope` 内返回 `[TRAINING_RECORD_NOT_FOUND]`。

管理者看板响应:

```typescript
interface SalesTrainerManagerDashboard {
  generated_at: string;
  policy: {
    key: "sales_trainer.phase2.closed_loop_policy";
    version: string;
    enabled: boolean;
    low_score_threshold: number;
    repeat_practice_threshold: number;
    dashboard_record_limit: number;
    source: "database" | "database_previous" | "default";
    config_id?: string | null;
    config_version?: number | null;
    status?: string | null;
    fallback_applied: boolean;
    fallback_reason?: string | null;
    management_entry: "/admin/business-rules/sales-trainer-phase2";
    permission: "admin_publish_only";
    effective_timing: "request_time";
  };
  summary: {
    record_count: number;
    loaded_record_count: number;
    learner_count: number;
    completed_record_count: number;
    completion_rate?: number | null;
    pass_rate?: number | null;
    low_score_record_count: number;
    repeat_practice_learner_count: number;
  };
  module_summaries: ManagerDashboardModuleSummary[];
  weak_dimensions: ManagerDashboardWeakDimension[];
  risk_learners: ManagerDashboardRiskLearner[];
  intervention_suggestions: ManagerDashboardInterventionSuggestion[];
}

interface ManagerDashboardModuleSummary {
  module_key: string;
  module_name: string;
  record_count: number;
  completed_count: number;
  pass_rate?: number | null;
  average_score?: number | null;
  weak_record_count: number;
}

interface ManagerDashboardWeakDimension {
  dimension_key: string;
  dimension_label: string;
  record_count: number;
  learner_count: number;
  average_score?: number | null;
}

interface ManagerDashboardRiskLearner {
  user_id: string;
  user_name?: string | null;
  user_department?: string | null;
  risk_reasons: string[];
  latest_submitted_at?: string | null;
  lowest_score?: number | null;
  record_count: number;
  suggested_action: string;
  suggested_action_code: string;
  priority: "low" | "medium" | "high";
}

interface ManagerDashboardInterventionSuggestion {
  user_id: string;
  user_name?: string | null;
  priority: "low" | "medium" | "high";
  action: string;
  reason_codes: string[];
}
```

看板阈值、主管动作和补救动作不是页面常量，也不再读取阶段 2 专用环境变量。运行时通过 `BusinessRuleConfigService` 读取 `sales_trainer.phase2.closed_loop_policy` 的 published 配置；缺失、非法或 disabled 时使用 bundled default，并在 `policy` / `settings.phase2_policy` 返回 `fallback_applied=true` 和原因。发布、回滚、禁用、预览和审计全部走现有 business-rule 生命周期。

阶段 2 闭环策略配置:

```typescript
interface SalesTrainerPhase2ClosedLoopPolicyConfig {
  version: string; // 默认 "sales_trainer_phase2_closed_loop_policy_v1"
  enabled: boolean; // 默认 true
  low_score_threshold: number; // 0..100，默认 70
  repeat_practice_threshold: number; // 1..20，默认 2
  dashboard_record_limit: number; // 1..5000，默认 500
  manager_actions: Array<{
    code: "not_passed" | "low_score" | "repeated_practice" | "fallback";
    label: string;
    priority: "low" | "medium" | "high";
  }>;
  remediation_actions: Array<{
    record_type:
      | "audio_submission"
      | "quiz_attempt"
      | "ai_coach_session"
      | "default"
      | "no_action";
    action_label: string;
    reason_template: string;
    target_path_template: string;
    priority: "low" | "medium" | "high";
  }>;
}
```

校验规则: action code / record_type 不得重复，且必须覆盖默认集合；`label`、`action_label`、`reason_template`、`target_path_template` 必须是非空字符串；`priority` 只能是 `low | medium | high`。治理入口是 `/admin/business-rules/sales-trainer-phase2`，settings 页只展示摘要、source/version/fallback 状态和治理入口，不作为只读 env 管理页。

### 历史成绩重评

历史重评是高风险补偿动作，不等同于 `retry-scoring`。`retry-scoring` 只用于失败任务重试；重评用于管理员明确选择某条历史记录，以某个已发布修订重新计算结果，并追加一条 `regrade_run`。重评不得覆盖原始 attempt、answer snapshot、audio submission 或原始 score result。

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/admin/sales-trainer/regrades/quiz-attempts/{attempt_id}/preview` | 预览历史考试重评影响范围 |
| `POST` | `/api/v1/admin/sales-trainer/regrades/quiz-attempts/{attempt_id}/run` | 执行历史考试重评，必须填写原因 |
| `POST` | `/api/v1/admin/sales-trainer/regrades/audio-submissions/{submission_id}/preview` | 预览历史录音评分重评影响范围 |
| `POST` | `/api/v1/admin/sales-trainer/regrades/audio-submissions/{submission_id}/run` | 执行历史录音评分重评，必须填写原因 |
| `POST` | `/api/v1/admin/newcomer-training/regrades/quiz-attempts/{attempt_id}/preview` | 新人训练路径命名下的兼容预览端点 |
| `POST` | `/api/v1/admin/newcomer-training/regrades/quiz-attempts/{attempt_id}/run` | 新人训练路径命名下的兼容执行端点 |
| `POST` | `/api/v1/admin/newcomer-training/regrades/audio-submissions/{submission_id}/preview` | 新人训练路径命名下的录音重评预览端点 |
| `POST` | `/api/v1/admin/newcomer-training/regrades/audio-submissions/{submission_id}/run` | 新人训练路径命名下的录音重评执行端点 |

Request:

```typescript
interface RegradePreviewRequest {
  target_revision_id?: string | null;
}

interface RegradeRunRequest extends RegradePreviewRequest {
  reason: string;
}
```

Response:

```typescript
interface RegradePreviewResponse {
  target_type: "quiz_attempt" | "audio_submission";
  target_id: string;
  target_revision_id: string;
  impact_scope: {
    record_count: number;
    affected_attempt_ids?: string[];
    affected_submission_ids?: string[];
    source_score_result_ids?: string[];
    future_records_changed: false;
    history_overwrite: false;
    requires_reason: true;
  };
  before_snapshot: Record<string, unknown>;
  after_snapshot: Record<string, unknown>;
}

interface RegradeRunResponse extends RegradePreviewResponse {
  regrade_run_id: string;
  status: "completed" | "failed";
  reason: string;
  trace_id: string;
  created_at: string;
}
```

约束:

- 仅 `admin`、`super_admin`、`operations`、`ops`、`operator`、`sre` 可预览或执行历史重评。
- `run` 必须填写 `reason`；空原因返回 422，不得落库。
- `target_revision_id` 缺省时，服务端使用该 attempt 所属考卷 logical id 的当前 active published revision；显式传入时必须属于同一考卷 logical id。
- 录音重评的 `target_revision_id` 指向 `sales_trainer_audio_score_prompt` published revision；缺省时使用该历史评分 `prompt_id` 的当前 active published prompt revision。
- `target_revision_id` 必须是 published revision；草稿、归档、其他资源类型或其他 logical id 的 revision 返回重评错误码。
- 执行后只新增 `sales_trainer_regrade_runs` 和 `historical_regrade.completed` 操作日志，不覆盖 `SalesTrainerQuizAttempt.total_score`、`SalesTrainerQuizAnswer.answer_payload` 或历史题目快照。
- 录音重评不得覆盖原始 `SalesTrainerAudioScoreResult`；`before_snapshot` 必须包含原始 `score_id`、`prompt_id`、`prompt_version`、`prompt_hash`、`transcript_snapshot`、`total_score`，`after_snapshot` 必须包含目标 prompt revision、目标 `prompt_hash` 和重新评分结果或错误码。
- 操作日志 metadata 必须包含 `regrade_run_id`、`target_revision_id`、`reason`、`impact_scope`、`before_snapshot`、`after_snapshot`、`trace_id`、`append_only=true`、`history_overwrite=false`。

### 操作日志

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/operation-logs` | 操作日志列表，支持 `actor_id`、`target_type`、`target_id`、`limit`、`offset` |

权限与审计要求:

- 仅 `admin`、`super_admin`、`operations`、`ops`、`operator`、`sre` 可读取操作日志。
- 关键生命周期事件的 metadata 必须包含 `previous`、`next`、`changed_fields`；发布/归档事件还必须包含 `previous_status`、`next_status`。
- 考卷生命周期日志还必须记录 `paper_key`、`module_key`、`unit_id`、`previous_unit_status`、`next_unit_status`，用于定位哪次发布或归档影响学员端。
- 重评日志必须记录 `reason`、影响范围和 before/after，不得只记录“已重新评分”。

Response `data`:

```typescript
interface OperationLogListResponse {
  items: OperationLog[];
  total: number;
}
```

## 主要错误码

| 错误码 | HTTP 状态 | 场景 |
|---|---:|---|
| `[ROLE_REQUIRED]` | 403 | 当前角色缺少对应 admin 能力，例如内容管理员访问日志、培训负责人重试任务或学员访问后台 |
| `[ACCESS_DENIED]` | 403 | learner 访问他人做题、音频或文件 |
| `[BUSINESS_ETIQUETTE_IMPORT_CONFIG_INVALID]` | 500 | 商务礼仪导入配置缺失或非法，例如默认 key、格式白名单、文件大小上限或期望章节数 |
| `[BUSINESS_ETIQUETTE_IMPORT_FILE_INVALID]` | 400 | 商务礼仪导入文件名为空或无法识别 |
| `[BUSINESS_ETIQUETTE_IMPORT_FORMAT_UNSUPPORTED]` | 415 | 商务礼仪导入文件扩展名或 content type 不在允许列表 |
| `[BUSINESS_ETIQUETTE_IMPORT_FILE_EMPTY]` | 400 | 商务礼仪导入文件为空 |
| `[BUSINESS_ETIQUETTE_IMPORT_FILE_TOO_LARGE]` | 413 | 商务礼仪导入文件超过后台配置大小 |
| `[BUSINESS_ETIQUETTE_IMPORT_ENCODING_INVALID]` | 415 | 商务礼仪 Markdown 不是 UTF-8 编码 |
| `[BUSINESS_ETIQUETTE_IMPORT_STRUCTURE_INVALID]` | 422 | 商务礼仪 Markdown 标题树不符合全书 + 8 个原始章节 + H2 微章节结构 |
| `[BUSINESS_ETIQUETTE_DRAFT_EXISTS]` | 409 | 商务礼仪训练包已有 working revision 且当前请求不允许覆盖草稿 |
| `[BUSINESS_ETIQUETTE_TRAINING_PACK_REVISION_MISSING]` | 409 | 保存能力点快照前未找到商务礼仪训练包 working 或 active revision |
| `[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]` | 400/409/422 | 能力点 key、掌握等级、达标线、证据规则或快照结构非法 |
| `[BUSINESS_ETIQUETTE_CAPABILITY_BINDING_INVALID]` | 422 | 章节能力点绑定为空、重复、引用不存在章节或引用不存在/已归档能力点 |
| `[BUSINESS_ETIQUETTE_CAPABILITY_NOT_FOUND]` | 404 | 发布或归档的能力点 key 不存在 |
| `[BUSINESS_ETIQUETTE_MODULE_CONFIG_MISSING]` | 404 | 商务礼仪 `business_skills` 模块配置不存在或不是文章考试模块 |
| `[BUSINESS_ETIQUETTE_MODULE_DISABLED]` | 409 | 商务礼仪模块已停用 |
| `[BUSINESS_ETIQUETTE_LEARNING_UNITS_MISSING]` | 409 | 商务礼仪模块缺少后台配置的小单元 |
| `[BUSINESS_ETIQUETTE_UNIT_CHAPTERS_MISSING]` | 409 | 商务礼仪 enabled 小单元没有绑定有效原文章节 |
| `[BUSINESS_ETIQUETTE_PROGRESS_UNAVAILABLE]` | 500 | 商务礼仪小单元阅读进度读取失败 |
| `[BUSINESS_ETIQUETTE_QUESTION_PROMPT_INVALID]` | 400 | 商务礼仪题目生成 Prompt 模板 ID 非法 |
| `[BUSINESS_ETIQUETTE_QUESTION_PROMPT_NOT_FOUND]` | 404 | 商务礼仪题目生成 Prompt 模板不存在 |
| `[BUSINESS_ETIQUETTE_QUESTION_PROMPT_INACTIVE]` | 409 | 商务礼仪题目生成 Prompt 模板已停用 |
| `[BUSINESS_ETIQUETTE_QUESTION_PROMPT_PURPOSE_MISMATCH]` | 409 | 商务礼仪题目生成 Prompt 模板用途不匹配 |
| `[BUSINESS_ETIQUETTE_QUESTION_PROMPT_COMPILE_FAILED:*]` | 502 | 商务礼仪题目生成 Prompt 编译失败 |
| `[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_INVALID]` | 400 | 商务礼仪题目生成模型配置 ID 非法，或选择了非 LLM 配置 |
| `[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_NOT_FOUND]` | 404 | 商务礼仪题目生成模型配置不存在 |
| `[BUSINESS_ETIQUETTE_QUESTION_MODEL_CONFIG_INACTIVE]` | 409 | 商务礼仪题目生成模型配置已停用 |
| `[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_JSON]` | 502 | AI 题目生成结果不是合法 JSON |
| `[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_SCHEMA]` | 502 | AI 题目生成结果结构非法，未写入部分草稿 |
| `[BUSINESS_ETIQUETTE_QUESTION_GENERATION_FAILED]` | 502 | AI 题目生成调用失败 |
| `[BUSINESS_ETIQUETTE_AI_COACH_SESSION_INVALID]` | 409 | AI 教练训练局不属于商务礼仪模块 |
| `[BUSINESS_ETIQUETTE_AI_COACH_CONFIG_INVALID]` | 409 | AI 教练达标配置非法，例如冻结路径快照损坏、等级 key 不存在或可上场等级低于达标等级 |
| `[BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND]` | 404/409 | AI 教练 progress 指定小单元不存在，或 session 快照缺少小单元 |
| `[BUSINESS_ETIQUETTE_AI_COACH_CAPABILITY_CONFIG_MISSING]` | 409 | AI 教练达标能力点在训练包能力快照中不存在 |
| `[BUSINESS_ETIQUETTE_AI_COACH_EVENT_INVALID]` | 409 | AI 教练训练卡公开互动快照缺失或非法，无法作为达标证据 |
| `[BUSINESS_ETIQUETTE_AI_COACH_SCORE_INVALID]` | 409 | AI 教练训练卡评分结果缺失或非法，无法作为达标证据 |
| `[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_INVALID]` | 400/409 | 商务礼仪训练包发布策略非法、被配置禁用，或 learner 自愿重练未开启 |
| `[BUSINESS_ETIQUETTE_RETRAINING_ASSIGNMENT_INVALID]` | 400/422 | 指定重练用户为空、超过人数上限或请求结构非法 |
| `[BUSINESS_ETIQUETTE_RETRAINING_USER_NOT_FOUND]` | 404 | 指定重练目标用户不存在 |
| `[BUSINESS_ETIQUETTE_RETRAINING_TARGET_INVALID]` | 422 | 指定重练目标用户不是 active learner |
| `[BUSINESS_ETIQUETTE_RETRAINING_TARGET_NOT_ALLOWED]` | 404 | 指定重练目标用户当前不可进入商务礼仪模块 |
| `[REGRADING_TARGET_NOT_FOUND]` | 404 | 历史重评目标记录不存在 |
| `[REGRADING_TARGET_REVISION_NOT_FOUND]` | 404 | 未找到可用于重评的已发布修订 |
| `[REGRADING_TARGET_REVISION_INVALID]` | 409 | 重评目标修订不是新人训练路径考卷修订 |
| `[REGRADING_TARGET_REVISION_NOT_PUBLISHED]` | 409 | 重评目标修订不是已发布状态 |
| `[REGRADING_TARGET_REVISION_MISMATCH]` | 409 | 重评目标修订不属于该历史记录的考卷 logical id |
| `[SALES_TRAINER_UNIT_NOT_FOUND]` | 404 | 训练单元不存在、未发布或不可见 |
| `[SALES_TRAINER_UNIT_TYPE_MISMATCH]` | 400 | 对错误类型训练单元执行做题或音频操作 |
| `[SALES_TRAINER_UNIT_NOT_EDITABLE]` | 400 | 修改非 `draft` 训练单元 |
| `[SALES_TRAINER_UNIT_ARCHIVED]` | 400 | 发布已归档训练单元 |
| `[SALES_TRAINER_QUIZ_REQUIRES_QUESTIONS]` | 400 | 发布 quiz 单元但未绑定题目 |
| `[SALES_TRAINER_QUIZ_HAS_NO_QUESTIONS]` | 400 | learner 提交没有题目的 quiz 单元 |
| `[QUIZ_PASS_THRESHOLD_INVALID]` | 400 | 做题通过线配置非法 |
| `[QUIZ_ATTEMPT_NOT_FOUND]` | 404 | 做题记录不存在 |
| `[QUIZ_ANSWER_QUESTION_NOT_IN_UNIT]` | 422 | 提交了不属于该单元的题目 |
| `[QUIZ_ANSWER_INCOMPLETE]` | 422 | 提交考卷缺题或存在空答案 |
| `[SHORT_ANSWER_AI_SCORING_FAILED]` | 无 HTTP 错误；提交成功并保持 `submitted` | 简答题外部 AI 批改鉴权、连接、超时或重试失败，答案已保存但该题未评分 |
| `[QUESTION_TYPE_UNSUPPORTED]` | 422 | 当前题型或题库结构不支持自动判分或展示 |
| `[AUDIO_TYPE_NOT_ALLOWED]` | 422 | 音频格式不在允许列表 |
| `[AUDIO_FILE_TOO_LARGE]` | 413 | 音频超过配置的文件大小上限 |
| `[AUDIO_FILE_EMPTY]` | 422 | multipart 上传文件为空 |
| `[AUDIO_SIZE_CONFIG_INVALID]` | 500 | 文件大小配置非法 |
| `[OSS_NOT_CONFIGURED]` | 503 | OSS 对象存储签名配置缺失或非法 |
| `[COS_NOT_CONFIGURED]` | 503 | COS 对象存储配置或 SDK 缺失 |
| `[COS_UPLOAD_FAILED]` | 502 | multipart 上传转存 COS 失败 |
| `[AUDIO_FILE_NOT_FOUND]` | 404 | 本地音频文件不存在 |
| `[AUDIO_FILE_ACCESS_DENIED]` | 403 | 本地音频文件不在允许的存储目录内 |
| `[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]` | 500 | 音频文件访问链接有效期配置非法 |
| `[AUDIO_REMOTE_SIGNING_FAILED]` | 500 | 远程音频转写生成下载签名失败 |
| `[AUDIO_REMOTE_DOWNLOAD_TIMEOUT]` | 504 | 远程音频下载超时 |
| `[AUDIO_REMOTE_DOWNLOAD_FAILED]` | 502 | 远程音频下载失败或下载后文件不可用 |
| `[AUDIO_REMOTE_DOWNLOAD_TIMEOUT_CONFIG_INVALID]` | 500 | 远程音频下载超时配置非法 |
| `[AUDIO_SUBMISSION_NOT_FOUND]` | 404 | 音频提交不存在 |
| `[TRANSCRIPTION_FAILED]` | 500 | 转写任务失败 |
| `[TRANSCRIPT_EMPTY]` | 422 | 转写成功但文本为空 |
| `[SCORING_PROMPT_REQUIRED]` | 400 | 音频评分缺少提示词配置 |
| `[SCORING_PROMPT_NOT_FOUND]` | 404 | 评分提示词不存在 |
| `[SCORING_PROMPT_NOT_PUBLISHED]` | 400 | 评分提示词未发布 |
| `[SCORING_PROMPT_NOT_EDITABLE]` | 409 | 修改已归档评分提示词；已发布提示词编辑应生成待发布修订 |
| `[SCORING_PROMPT_ARCHIVED]` | 400 | 发布已归档提示词 |
| `[NEWCOMER_ARTICLE_PROGRESS_REQUIRED]` | 403 | 文章考试模块提交考卷前未完成当前绑定文章阅读 |
| `[AI_COACH_PROMPT_TEMPLATE_MISSING]` | 409 | AI 教练会话缺少互动卡片生成 Prompt 绑定 |
| `[AI_COACH_PROMPT_CONFIG_INVALID]` | 409 | AI 教练 Prompt 配置非法，例如 template id 不是 UUID |
| `[AI_COACH_PROMPT_REVISION_NOT_FOUND]` | 404 | AI 教练 Prompt 模板或指定修订不可用 |
| `[AI_COACH_PROMPT_REVISION_AUDIT_MISSING]` | 409 | AI 教练指定 Prompt revision 缺少可审计历史，运行时拒绝回退 |
| `[AI_COACH_PROMPT_REVISION_FALLBACK]` | 409 | AI 教练未按已发布 Prompt revision 渲染，运行时拒绝使用 head fallback |
| `[AI_COACH_TRAINING_CARD_TYPE_NOT_ALLOWED]` | 502 | AI 教练生成了未在 `allowed_training_card_types` 白名单内的 ABD 训练卡 |
| `[AUDIO_PASS_THRESHOLD_INVALID]` | 400 | 通过线不在 `0-100` 范围 |
| `[DEUCATE_CONFIG_INVALID]` | 500 | Deucate 模型参数配置非法 |
| `[DEUCATE_CONFIG_MISSING]` | 500 | Deucate 配置缺失 |
| `[DEUCATE_TIMEOUT]` | 504 | Deucate 调用超时 |
| `[DEUCATE_REQUEST_FAILED]` | 502 | Deucate 请求失败 |
| `[DEUCATE_RESPONSE_INVALID]` | 502 | Deucate 返回非预期 JSON 或结构非法 |
| `[MATERIAL_KEY_EXISTS]` | 409 | 材料业务标识重复 |
| `[MATERIAL_KEY_INVALID]` | 422 | 材料业务标识格式非法 |
| `[SALES_TRAINER_MATERIAL_NOT_FOUND]` | 404 | 训练材料不存在 |
| `[SALES_TRAINER_MATERIAL_NOT_PUBLISHED]` | 409 | 训练任务绑定的材料未发布 |
| `[SALES_TRAINER_MATERIAL_ARCHIVED]` | 409 | 已归档材料或版本不能继续编辑/发布 |
| `[MATERIAL_ARCHIVE_ACTIVE_REFERENCE]` | 409 | 材料仍被 active 或 working 新人训练路径引用，禁止归档 |
| `[MATERIAL_VERSION_LABEL_EXISTS]` | 409 | 同一材料下版本号重复 |
| `[MATERIAL_VERSION_REQUIRED]` | 409 | 训练任务绑定材料缺少可用当前版本 |
| `[MATERIAL_VERSION_NOT_FOUND]` | 404 | 材料版本不存在 |
| `[MATERIAL_VERSION_NOT_PUBLISHED]` | 404/409 | 材料版本不存在、未发布或锁定版本不可用 |
| `[MATERIAL_VERSION_CONFIRMATION_REQUIRED]` | 409 | 学员提交前未确认要求的材料版本 |
| `[MATERIAL_VERSION_CONFIRMATION_OUTDATED]` | 409 | 学员确认版本不是当前要求版本，需要重新确认 |
| `[PPT_MATERIAL_BINDING_REQUIRED]` | 409/422 | PPT 演练任务未绑定 required 且 confirmation_required 的已发布材料 |
| `[SALES_TRAINER_MATERIAL_BINDING_INVALID]` | 422 | 训练任务材料绑定配置结构非法 |
| `[SALES_TRAINER_TASK_BRIEF_INVALID]` | 422 | 训练任务简报配置结构非法 |
| `[LEARNER_RUBRIC_INVALID]` | 422 | 学员可见评分标准配置结构非法 |
| `[MATERIAL_FILE_EMPTY]` | 422 | 上传材料文件为空 |
| `[MATERIAL_FILE_TYPE_NOT_ALLOWED]` | 422 | 上传材料文件格式不在允许列表内 |
| `[MATERIAL_FILE_TOO_LARGE]` | 413 | 上传材料文件超过配置大小上限 |
| `[MATERIAL_SIZE_CONFIG_INVALID]` | 500 | 上传材料文件大小上限配置非法 |
| `[MATERIAL_UPLOAD_FAILED]` | 500 | 上传材料文件保存失败 |
| `[MATERIAL_UPLOAD_BACKEND_UNSUPPORTED]` | 503 | 当前材料 multipart 上传不支持该存储后端 |
| `[NEWCOMER_PATH_CONFIG_MISSING]` | 404/409 | 新人训练路径配置缺失或未启用 |
| `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]` | 409 | learner 路径、journey、AI Coach 或实时对练运行入口缺少 active revision；不得使用 unit backfill 或默认配置伪成功 |
| `[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]` | 409 | 发布或发布预览前缺少 working revision；不得从 legacy backfill 直接发布或预览发布 |
| `[NEWCOMER_MODULE_CONFIG_INVALID]` | 422 | 新人训练路径模块配置非法，例如未知 `module_type`、重复排序或绑定不存在 |
| `[NEWCOMER_MODULE_BINDING_MISSING]` | 409 | 模块必要绑定缺失，例如文章、考卷、材料、评分提示词或目标单元 |
| `[NEWCOMER_MODULE_DISABLED]` | 409 | learner 尝试进入已停用模块 |
| `[NEWCOMER_REALTIME_PLACEHOLDER_ONLY]` | 409 | 旧错误码，仅用于历史 disabled placeholder 兼容；新接入必须使用 runtime binding 相关错误码 |
| `[NEWCOMER_REALTIME_BINDING_INVALID]` | 409/422 | realtime 模块缺少 runtime binding、binding 指向不可用 runtime descriptor，或 outcome projection/rollback policy 不完整 |
| `[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]` | 503 | `sales_trainer.realtime_provider.registry` 缺失、停用或 fallback 到默认 disabled registry，learner 不得进入运行时 |
| `[NEWCOMER_REALTIME_PROVIDER_DESCRIPTOR_MISSING]` | 503 | provider registry 不包含 path runtime binding 引用的 `runtime_descriptor_id` |
| `[NEWCOMER_REALTIME_PROVIDER_DISABLED]` | 503 | provider registry 中对应 descriptor 已停用 |
| `[NEWCOMER_REALTIME_PROVIDER_NOT_READY]` | 503 | realtime provider readiness 不通过，learner 不得进入运行时 |
| `[NEWCOMER_REALTIME_PERMISSION_DENIED]` | 403 | 当前用户无权进入该 path/module 的 realtime 训练 |
| `[NEWCOMER_REALTIME_OUTCOME_MISSING]` | 409 | runtime session 结束后缺少可写入 TrainingJourney 的 outcome projection |
| `[PAPER_NOT_PUBLISHED]` | 404/409 | 绑定考卷不存在、未发布或已归档 |
| `[LEARNING_CONTENT_NOT_PUBLISHED]` | 404/409 | 绑定学习内容不存在、未发布或已归档 |
| `[LEARNING_CONTENT_BOUND_TO_NEWCOMER_PATH]` | 409 | 学习内容被 active 或 working 新人训练路径引用，归档被服务端硬阻止 |
| `[MATERIAL_FILE_NOT_FOUND]` | 404 | 材料文件不存在 |
| `[MATERIAL_FILE_ACCESS_DENIED]` | 403 | 本地材料文件不在允许存储目录内 |
| `[MATERIAL_HISTORY_REFERENCE_NOT_FOUND]` | 404 | 训练记录未冻结引用该材料版本，禁止历史回放 |
| `[TRAINING_RECORD_MATERIAL_REPLAY_UNSUPPORTED]` | 400 | 当前训练记录类型没有可回放材料文件 |
| `[MATERIAL_FILE_URL_EXPIRES_CONFIG_INVALID]` | 500 | 材料文件访问链接有效期配置非法 |
| `[ASR_ACCOUNT_ARREARS]` | 402/502 | ASR 供应商账户欠费或不可用，需要管理员处理账户状态后重试 |
| `[ASR_AUTH_FAILED]` | 401/403/502 | ASR API Key 或供应商鉴权失败 |
| `[ASR_RATE_LIMITED]` | 429/502 | ASR 供应商限流，需要稍后重试 |
| `[ASR_FILE_DOWNLOAD_FAILED]` | 502 | ASR 供应商无法下载提交音频，需检查对象存储签名 URL、权限或文件可访问性 |
| `[ASR_TASK_SUBMIT_FAILED]` | 502 | ASR 任务提交失败，未命中更具体供应商错误 |
| `[ASR_TASK_WAIT_FAILED]` | 502 | ASR 任务轮询失败，未命中更具体供应商错误 |
| `[ASR_TASK_FAILED]` | 502 | ASR 任务执行失败，未命中更具体供应商错误 |
| `[TRAINING_RECORD_TYPE_INVALID]` | 400 | 统一训练记录详情的 `record_type` 不是 `audio_submission`、`quiz_attempt`、`ai_coach_session`、`business_etiquette_quiz_attempt` 或 `realtime_roleplay_session` |
| `[TRAINING_RECORD_NOT_FOUND]` | 404 | 训练记录不存在 |
| `[ROLEPLAY_OBSERVATION_SESSION_NOT_FOUND]` | 404 | 旁路观测写入目标实时会话不存在；sink 必须 warning-only，不影响实时链路 |
| `[ROLEPLAY_OBSERVATION_SESSION_MODE_INVALID]` | 409 | 旁路观测目标不是 `stepfun_realtime` 会话；sink 必须 warning-only |
| `[ROLEPLAY_OBSERVATION_SESSION_SCOPE_INVALID]` | 409 | 旁路观测目标不属于 `sales_trainer` external binding；sink 必须 warning-only |
| `[ROLEPLAY_OBSERVATION_STORE_FAILED]` | 500 | 旁路观测写入失败；只影响后台复盘，不影响 WebSocket 主链路 |

## 配置项

| 配置项 | 默认值 | 读取位置 | 管理入口 | 校验与兜底 |
|---|---|---|---|---|
| `SALES_TRAINER_AUDIO_ALLOWED_MIME_TYPES` | `audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/webm,audio/mp4,audio/x-m4a` | 音频上传服务 | 环境配置/系统配置 | 缺失使用默认值；不命中返回 `[AUDIO_TYPE_NOT_ALLOWED]` |
| `SALES_TRAINER_AUDIO_MAX_FILE_SIZE_MB` | `200` | 音频上传服务 | 环境配置/系统配置 | 必须为正整数；非法返回 `[AUDIO_SIZE_CONFIG_INVALID]` |
| `SALES_TRAINER_AUDIO_STORAGE_BACKEND` | `local` | 上传 URL、multipart 上传和文件读取服务 | 环境配置/系统配置 | 支持 `local`、`oss`、`cos`；`oss` 缺配置返回 `[OSS_NOT_CONFIGURED]`，`cos` 缺配置返回 `[COS_NOT_CONFIGURED]` |
| `SALES_TRAINER_AUDIO_STORAGE_PATH` | `./data/sales_trainer_audio` | 本地 multipart 上传和文件读取 | 环境配置/系统配置 | 缺失使用默认值；文件不存在返回 `[AUDIO_FILE_NOT_FOUND]` |
| `SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS` | `3600` | 对象存储音频读取/供应商转写 URL | 环境配置/系统配置 | 必须为正整数；非法返回 `[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]` |
| `SALES_TRAINER_MATERIAL_STORAGE_BACKEND` | `local` | 材料文件读取服务 | 环境配置/系统配置 | 支持 `local`、`oss`、`cos`；对象存储缺配置返回对应配置错误 |
| `SALES_TRAINER_MATERIAL_STORAGE_PATH` | `./data/sales_trainer_materials` | 本地材料文件读取服务 | 环境配置/系统配置 | 缺失使用默认值；文件不存在返回 `[MATERIAL_FILE_NOT_FOUND]` |
| `SALES_TRAINER_MATERIAL_FILE_URL_EXPIRES_SECONDS` | `3600` | 对象存储材料下载 URL | 环境配置/系统配置 | 必须为正整数；非法返回 `[MATERIAL_FILE_URL_EXPIRES_CONFIG_INVALID]` |
| `SALES_TRAINER_MATERIAL_ALLOWED_MIME_TYPES` | PPT/PDF/Word/Markdown/图片/常见音频 | 材料上传格式白名单 | 环境配置/系统配置 | 缺失使用默认值；不命中返回 `[MATERIAL_FILE_TYPE_NOT_ALLOWED]` |
| `SALES_TRAINER_MATERIAL_MAX_FILE_SIZE_MB` | `300` | 材料上传大小上限 | 环境配置/系统配置 | 必须为正整数；非法返回 `[MATERIAL_SIZE_CONFIG_INVALID]` |
| `SALES_TRAINER_AUDIO_REMOTE_DOWNLOAD_TIMEOUT_SECONDS` | `60` | legacy 远程音频下载转写桥接 | 环境配置/系统配置 | 必须为正数；非法返回 `[AUDIO_REMOTE_DOWNLOAD_TIMEOUT_CONFIG_INVALID]`，超时返回 `[AUDIO_REMOTE_DOWNLOAD_TIMEOUT]` |
| `TENCENT_COS_SECRET_ID` / `TENCENT_COS_SECRET_KEY` / `TENCENT_COS_BUCKET` / `TENCENT_COS_REGION` | 无 | COS 签名与服务端上传 | 环境配置/密钥管理 | `SALES_TRAINER_AUDIO_STORAGE_BACKEND=cos` 时必填；缺失返回 `[COS_NOT_CONFIGURED]` |
| `TENCENT_COS_DOMAIN` | 无 | COS 公开读 URL 可选域名 | 环境配置/系统配置 | 仅在 `TENCENT_COS_PUBLIC_READ=true` 时用于返回公开 URL；私有桶默认生成签名 GET URL |
| `TENCENT_COS_PUBLIC_READ` | `false` | COS GET URL 生成 | 环境配置/系统配置 | 默认私有桶签名 URL；只有确认 bucket 公开读时才设为 `true` |
| `SALES_TRAINER_ASR_MODE` | `legacy` | 转写服务 | 环境配置/系统配置 | `file` 时使用 DashScope 录音文件识别，要求音频可通过 HTTP/HTTPS URL 访问 |
| `DASHSCOPE_API_KEY` | 无 | DashScope 文件识别 | 环境配置/密钥管理 | `SALES_TRAINER_ASR_MODE=file` 时必填，缺失返回 `[ASR_API_KEY_REQUIRED]` |
| `SALES_TRAINER_ASR_MODEL` | `fun-asr` | DashScope 文件识别 | 环境配置/系统配置 | `language_hints` 仅在 `paraformer-v2` 时传入 |
| `SALES_TRAINER_MANAGER_ROLES` | `support,training_lead,training_manager` | 培训负责人记录查看能力兼容配置 | 环境配置/系统配置 | 逗号分隔角色列表；缺失/空值使用默认培训负责人角色；显式配置只保留 allowlist 合法角色，混入非法值记录诊断，全非法配置 fail-closed 为空角色集合；只授予团队记录读取能力，不授予内容管理、日志、配置健康或任务重试能力 |
| `sales_trainer.phase2.closed_loop_policy` | `sales_trainer_phase2_closed_loop_policy_v1`、`enabled=true`、`low_score_threshold=70`、`repeat_practice_threshold=2`、`dashboard_record_limit=500`、默认主管动作与补救动作 | 阶段 2 训练记录投影、能力画像、补救动作、管理者看板和 settings 策略摘要 | `/admin/business-rules/sales-trainer-phase2`，复用 `BusinessRuleConfig` 发布/回滚/禁用/审计 | 阈值范围 `0..100`、`1..20`、`1..5000`；action code/record_type 必须覆盖且不重复；文案/模板非空；缺失、非法或 disabled 使用 bundled default，并返回 `phase2_policy.fallback_applied=true` |
| `modules[].ai_coach.allowed_training_card_types` | 裸默认 `["scenario_judgment"]`；商务礼仪 seed/admin 默认 `["scenario_judgment","expression_rewrite","role_response"]` | 新人训练路径 active/working revision 的 `business_skills.ai_coach` | `/admin/sales-trainer/ai-coach` | 至少 1 项，只允许 `scenario_judgment`、`expression_rewrite`、`role_response`；改写/角色回应必须同时启用 `short_answer` 并绑定评分 prompt；非法保存返回 Pydantic 校验错误，运行时输出不命中返回 `[AI_COACH_TRAINING_CARD_TYPE_NOT_ALLOWED]` |
| `BUSINESS_SKILLS_COACH_WORKBENCH_COPY` | 页面标题、聊天工作台、教练反馈、结束面板、按钮和空状态文案 | `web/src/app/(dashboard)/sales-trainer/business-skills/coach/coach-workbench-config.ts` | 当前为前端集中配置；未来运营可调时迁移到 `/admin/sales-trainer/ai-coach` | 必须非空、语义与 Chat-First 教练工作台一致；缺失会在构建/类型检查阶段暴露；当前不支持后台热更新 |
| `BUSINESS_SKILLS_COACH_WORKBENCH_RULES.showFreeFollowup` | `true` | 同上 | 当前为前端集中配置；未来迁移到 `modules[].ai_coach` | `true` 时自由追问只走 chat message stream；`false` 时隐藏输入框；不得替代训练卡提交 |
| `BUSINESS_SKILLS_COACH_WORKBENCH_RULES.allowSkipActiveCard` | `false` | 同上 | 当前为前端集中配置；未来迁移到 `modules[].ai_coach`，由 `sales_trainer.manage_modules` 管理 | `false` 时 active pending 训练卡存在则禁用“继续下一题”；如配置为 `true` 必须确认不会破坏达标状态机 |
| `DEUCATE_BASE_URL` | 无 | Deucate 评分服务 | 环境配置/模型配置 | 缺失返回 `[DEUCATE_CONFIG_MISSING]` |
| `DEUCATE_API_KEY` | 无 | Deucate 评分服务 | 环境配置/模型配置 | 缺失返回 `[DEUCATE_CONFIG_MISSING]` |
| `DEUCATE_MODEL` | `deucate` | Deucate 评分服务 | 环境配置/模型配置 | 缺失使用默认值 |
| `DEUCATE_TIMEOUT_SECONDS` | `30` | Deucate 评分服务 | 环境配置/模型配置 | 必须为正数；非法返回 `[DEUCATE_CONFIG_INVALID]`，超时返回 `[DEUCATE_TIMEOUT]` |
| `unit.config.audio.scoring_prompt_id` | 无 | 训练单元配置 | admin 训练单元管理 | 音频评分单元发布和评分时必须指向已发布提示词 |
| `unit.config.audio.purpose` | `general_audio_scoring` | 训练单元配置与学员上传页面 | admin 训练单元管理 | 必填字符串；缺失时前端使用默认用途 |
| `unit.config.audio.pass_threshold` | `70` | 训练单元配置 | admin 训练单元管理 | 必须在 `0-100`；缺失使用默认值 |
| `unit.config.quiz.pass_threshold` | 无 | 训练单元配置与做题服务 | admin 训练单元管理 | 必须为非负数字；非法返回 `[QUIZ_PASS_THRESHOLD_INVALID]` |
| `unit.config.task_brief` | 按训练单元名称/描述兜底 | learner brief API、提交快照 | admin 训练单元管理 | 必须为对象；缺失使用安全默认简报 |
| `unit.config.materials` | 空绑定 | learner brief API、提交快照 | admin 训练单元管理 | PPT 演练必须至少绑定一个确认材料；非法返回 `[SALES_TRAINER_MATERIAL_BINDING_INVALID]` |
| `audio_score_prompt.learner_rubric` | `{}` | learner brief API、提交快照、结果页 | admin 评分方案管理 | 必须为对象；缺失使用 `{}` 并由通过线兜底 |
| `newcomer_path.path_key` | `newcomer_training_path_v1` | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | 必填；兼容读取 `new_seller_modules_v1`；缺失返回 `[NEWCOMER_PATH_CONFIG_MISSING]` |
| `newcomer_path.modules[].module_key` | 见默认模块矩阵 | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | 同一路径内唯一；重复或未知返回 `[NEWCOMER_MODULE_CONFIG_INVALID]` |
| `newcomer_path.modules[].module_type` | 无 | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | 只允许 `"audio_scoring"`、`"article_exam"`、`"audio_scoring_group"`、`"realtime_roleplay"`、`"realtime_placeholder"`；`realtime_placeholder` 仅兼容历史 disabled 配置 |
| `newcomer_path.modules[].display_name` | 默认模块矩阵名称 | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | 1-120 字符；缺失使用默认值并标记 `fallback_applied=true` |
| `newcomer_path.modules[].enabled` | 模块 1-3 `true`，模块 4 `false` | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | disabled 模块 learner 只展示停用状态，不允许提交或进入运行时 |
| `newcomer_path.modules[].target_unit_id(s)` | 无 | learner 模块入口、完成状态聚合 | admin 新人训练路径配置 | 必须指向已发布训练单元；缺失返回 `[NEWCOMER_MODULE_BINDING_MISSING]` |
| `newcomer_path.modules[].learning_content_id` | 无 | 商务技巧文章入口 | admin 新人训练路径文章绑定 | 必须指向已发布 `LearningContent`；缺失或草稿返回 `[LEARNING_CONTENT_NOT_PUBLISHED]` |
| `newcomer_path.modules[].exam_paper_id` | 无 | 商务技巧考卷入口 | admin 新人训练路径考卷管理 | 必须指向已发布考卷；缺失或草稿返回 `[PAPER_NOT_PUBLISHED]` |
| `newcomer_path.modules[].duration_options` | `10/20/30` 分钟可由 seed 初始化 | 金字塔演讲模块入口 | admin 新人训练路径配置 | 每项必须有正数时长和已发布音频单元；非法返回 `[NEWCOMER_MODULE_CONFIG_INVALID]` |
| `newcomer_path.modules[].capability_keys` | seed 写入 V0.9 固定新人能力 key | 达标档案 evidence/competency 映射、重练目标模块匹配、workbench 弱项归因 | admin 新人训练路径配置 | 必须命中 V0.9 固定能力模型且不得重复；发布配置非法返回 `[NEWCOMER_PATH_CONFIG_INVALID]`；缺失旧数据只允许后端兼容映射，不得由前端按标题推断 |
| `newcomer_path.modules[].learner_level_required` | 空数组 | 模块内容可见性、Journey 状态、learner `/paths` 展示和直链 unit/audio/quiz 授权 | admin 新人训练路径配置 + `sales_trainer.learner_level.policy` | 空数组表示所有学员等级可见；非空时必须匹配 `TrainingJourney.learner_level.level_key`，不匹配返回 locked/disabled 与 `[NEWCOMER_LEARNER_LEVEL_NOT_ALLOWED]`，不得仅靠前端隐藏 |
| `newcomer_path.modules[].runtime_binding` | `null` | realtime 模块入口、TrainingJourney outcome projection、发布校验 | admin 新人训练路径配置 + 运行时健康页 | `module_type="realtime_roleplay"` 且 enabled 时必填；必须引用可用 runtime descriptor、已发布 runtime config、provider readiness snapshot、权限策略、failure policy 和 rollback policy；非法返回 `[NEWCOMER_REALTIME_BINDING_INVALID]` |
| `newcomer_path.modules[].runtime_binding.provider_readiness_snapshot` | 无 | realtime 发布前校验和 learner 入口预检 | 运行时健康页 / support runtime status | `ready=false` 时发布预览必须提示影响范围；learner 入口返回 `[NEWCOMER_REALTIME_PROVIDER_NOT_READY]`，不得自动降级为 placeholder 成功 |
| `sales_trainer.realtime_provider.registry` | 顶层 `enabled=false`、默认 descriptor `ready=false`；不包含真实 `STEPFUN_API_KEY` | realtime learner start、配置中心、ConfigBundle lifecycle、历史 external binding 回放 | `/admin/config-bundles/sales_trainer.realtime_provider.registry` | 必须校验唯一 descriptor、provider/runtime_owner allowlist、readiness 失败原因和 rollback descriptor 引用；缺失、非法、停用或 fallback 默认值必须 fail-closed，不得沿用 path snapshot 放行；publish/rollback/disable 写 `ConfigBundleAuditLog`；日志和响应只暴露 masked/configured 状态 |
| `newcomer_path.modules[].audit_events` | `newcomer_module.<module_key>.*` | 操作日志服务 | 系统初始化/后台配置 | 事件名必填；发布、归档、绑定变更必须写 operation log |
| `sales_trainer.learner_level.policy` | `unassigned` 默认等级、空 rules | TrainingJourney learner level 投影、admin list/analytics 筛选和分布 | `/admin/business-rules/sales-trainer-learner-level` | 必须校验 default_level、levels 唯一性、rules 引用和阈值范围；缺失/非法/停用必须 fail-visible 回落默认等级并返回 `fallback_applied/fallback_reason`；真实等级枚举由后台配置发布，不由前端硬编码 |
| `sales_trainer.role_level.policy` | `learner` 默认等级、`role_in=["user"]` 默认规则 | TrainingJourney role level 投影、admin list/analytics 筛选和分布 | `/admin/business-rules/sales-trainer-role-level` | 必须校验 default_level、levels 唯一性、rules 引用和阈值范围；缺失/非法/停用必须 fail-visible 回落默认等级并返回 `fallback_applied/fallback_reason`；角色等级不等同于权限 capability scope |
| `business_etiquette_import.settings` | `business_etiquette_v1`、Markdown 格式、2MB、8 个原始章节、允许覆盖草稿 | 商务礼仪资料导入 API | 后端导入配置 / 资料导入页 | 文件格式、大小、章节数必须校验；解析失败不落库 |
| `business_etiquette_training_pack.capability_snapshot.capabilities[]` | 后端 8 个主能力点 seed | 商务礼仪能力点、学员小单元展示、后续题目/AI 教练/卡点引用 | `/admin/sales-trainer/articles/capabilities` | key 唯一；阈值 0..100；等级/证据规则非空；缺失时管理端返回 `default_seed` 且 `needs_save=true`，learner 不在前端生成 |
| `business_etiquette_training_pack.capability_snapshot.chapter_bindings[]` | 第 1-8 章分别绑定默认主能力点 | 学员小单元能力点展示、后续题源和补救建议 | `/admin/sales-trainer/articles/capabilities` | 章节必须存在；能力点必须存在且未归档；非法返回 `[BUSINESS_ETIQUETTE_CAPABILITY_BINDING_INVALID]` |
| `business_etiquette_release.settings.default_strategy` | `future_learners_only` | 商务礼仪训练包发布 API 和导入发布页 | 后端 `BusinessEtiquetteReleaseSettings`；后续可迁移后台配置 | 必须是 `future_learners_only`、`allow_voluntary_switch`、`assign_retraining` 之一；非法返回 `[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_INVALID]` |
| `business_etiquette_release.settings.allow_voluntary_switch` | `true` | learner 自愿重练入口和重练 session 创建 | 后端发布配置 / 后续后台配置 | false 时 learner 重练端点返回 `[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_INVALID]`，前端不展示自愿重练入口 |
| `business_etiquette_release.settings.allow_assigned_retraining` | `true` | 管理员指定人群重练 | 后端发布配置 / 后续后台配置 | false 时发布策略 `assign_retraining` 和指定重练端点返回 `[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_INVALID]` |
| `business_etiquette_release.settings.max_assigned_retraining_users` | `100` | 管理员指定人群重练批量上限 | 后端发布配置 / 后续后台配置 | 范围 `1..1000`；超过上限返回 `[BUSINESS_ETIQUETTE_RETRAINING_ASSIGNMENT_INVALID]` |
| `business_etiquette_release.settings.notification_template` | `商务礼仪训练包已更新，你可以选择重练新版。` | 发布影响分析、后续通知或 learner 重练提示 | 后端发布配置 / 后续后台配置 | 非空字符串；缺失使用安全默认值，不影响发布主流程 |
| `business_etiquette_release.settings.large_change_chapter_threshold` | `2` | 发布影响分析建议策略 | 后端发布配置 / 后续后台配置 | 正整数；非法时使用默认值并在影响分析配置中返回兜底值 |
| `newcomer_path.modules[].learning_units[]` | 7 个商务礼仪小单元 seed | 商务礼仪 learner 首页、小单元详情、阅读进度 | admin 新人训练路径配置 | 标题、顺序、章节、能力点、开放/跳过/阻断规则均可配置；缺失返回 `[BUSINESS_ETIQUETTE_LEARNING_UNITS_MISSING]` |
| `newcomer_path.modules[].learning_units[].ai_coach_required_capability_keys` | `capability_keys` | 商务礼仪 AI 教练 progress service、训练局冻结快照 | `/admin/sales-trainer/paths` 商务技巧绑定区 | 为空时使用 `capability_keys`；非空必须是 `capability_keys` 子集；缺失用 Pydantic 默认补齐 |
| `newcomer_path.modules[].learning_units[].ai_coach_pass_mastery_level_key` | `basic_mastery` | 商务礼仪 AI 教练达标判断 | `/admin/sales-trainer/paths` 商务技巧绑定区 | 必须命中能力点 `mastery_levels[].level_key`；非法返回 `[BUSINESS_ETIQUETTE_AI_COACH_CONFIG_INVALID]` |
| `newcomer_path.modules[].learning_units[].ai_coach_ready_mastery_level_key` | `field_ready` | 商务礼仪 AI 教练可上场判断 | `/admin/sales-trainer/paths` 商务技巧绑定区 | 必须命中能力点等级，且 min_score 不低于达标等级 |
| `newcomer_path.modules[].learning_units[].ai_coach_max_remediation_attempts` | `3` | 商务礼仪 AI 教练人工复盘阈值 | `/admin/sales-trainer/paths` 商务技巧绑定区 | 范围 `1..20`；达到且未达标时进入 `manual_review` |
| `newcomer_path.modules[].learning_units[].ai_coach_manual_review_after_max_attempts` | `true` | 商务礼仪 AI 教练人工复盘状态 | `/admin/sales-trainer/paths` 商务技巧绑定区 | false 时不自动进入人工复盘，但仍返回弱项和补救建议 |
| `newcomer_path.modules[].learning_units[].ai_coach_block_next_until_passed` | `true` | 商务礼仪 AI 教练后续小单元阻断 | `/admin/sales-trainer/paths` 商务技巧绑定区 | `block_next = 配置值 && !passed`；前端不得自行降低阻断要求 |
| `newcomer_path.modules[].learning_units[].ai_coach_remediation_chapter_orders` | `source_chapter_orders` | 商务礼仪 AI 教练补救章节建议 | `/admin/sales-trainer/paths` 商务技巧绑定区 | 为空时回落到小单元章节；必须为正整数且不重复 |

## 更新记录

| 日期 | 变更 | 说明 |
|---|---|---|
| 2026-07-06 | 收紧达标档案确认与模块能力映射契约 | `approve` 只能在 `pending_review` 且有证据时提交；`newcomer_path.modules[].capability_keys` 成为达标档案能力映射配置源 |
| 2026-07-06 | 新增 V0.9 训练达标档案与达标验收工作台契约 | `/readiness/workbench`、`/readiness/dossiers/{learner_id}`、`/review-actions` 聚合 journey、训练记录和 operation log；复核动作采用 operation-log-backed 状态 |
| 2026-07-03 | 冻结 StepFun roleplay compliance record-only 契约 | `roleplay_observation_v1` 全局 `record_only`，current turn `main_chain_effect=none`；next-turn soft steering 非阻断且可审计；旧同步 cancel/regenerate/repair audio 退役，恢复阻断必须另起 ADR |
| 2026-07-02 | 同步 StepAudio 2.5 安全/迁移契约 | 明确 provider migration apply/rollback、secret 不入库不入日志、legacy fallback 只读、observation 对象级授权 |
| 2026-07-02 | 新增实时角色一致性旁路观测契约 | `roleplay_observation_v1` 固定 record-only（旧称 `observe_only`）/ `main_chain_effect=none`，admin endpoint 只读展示，不阻断 StepAudio 2.5 realtime |
| 2026-07-02 | 扩展管理端 Journey Analytics additive observation 契约 | `/journeys/analytics` 新增 `additive_observation`，复用已授权 learner/session scope 聚合 observation storage/migration 诊断、session/observation 计数与 top signal keys |
| 2026-06-27 | 新增管理端 Journey Analytics 历史趋势契约 | `/journeys/analytics` 返回 `trend_data` 日期桶，基于可追溯 outcome 时间聚合，并随 `module_key` 等筛选收口 |
| 2026-06-27 | 扩展管理端 Journey Analytics 过滤契约 | `/journeys/analytics` 支持 `training_stage`、`module_key`、`learner_level`、`role_level` 与部门联合过滤，filters 必须回显生效条件 |
| 2026-06-27 | 新增角色等级治理投影契约 | `sales_trainer.role_level.policy` 成为 TrainingJourney role level 的配置来源；admin journey list/analytics 支持 `role_level` 精确过滤，并与权限 capability scope 解耦 |
| 2026-06-27 | 新增学员等级治理投影契约 | `sales_trainer.learner_level.policy` 成为 TrainingJourney learner level 的配置来源；admin journey list/analytics 支持 `learner_level` 精确过滤，并暴露 fallback 元数据 |
| 2026-06-27 | 新增实时对练 Provider Registry 治理契约 | `sales_trainer.realtime_provider.registry` 成为 realtime learner start 的 provider 启停/readiness/回滚真源；path runtime binding 的旧 snapshot 不再能单独放行 learner 入口 |
| 2026-06-27 | 冻结新人训练完整闭环契约 | 新增 TrainingJourney、ModuleProgress、ModuleOutcome、LearnerLevel、TrainingStage、RoleCapability；active revision 成为 learner 唯一真源；realtime 从 placeholder supersede 为 runtime binding；AI Coach 纳入必过闭环 |
| 2026-06-17 | AI 教练停止流式展示未校验题卡草稿 | 题卡必须等完整 JSON 解析、schema 校验和持久化后的 `session_snapshot` 展示；重试修复过程不向前端流 reasoning |
| 2026-06-17 | AI 教练默认生成超时调整为 120 秒并新增 `reasoning_text_delta` | DeepSeek reasoning 走 `delta.reasoning_content` 原始流；前端不得用最终回复或假步骤冒充思考 |
| 2026-06-17 | 明确新人训练路径音频组与实时占位发布契约（已被 2026-06-27 realtime runtime binding 契约 supersede） | `audio_scoring_group` 必须通过 `duration_options[]` 展开每个录音入口；`realtime_placeholder` 仅保留历史 disabled 配置兼容，不再代表实时模块的目标形态 |
| 2026-06-16 | 新增 AI 教练 `assistant_text_delta` 流式正文契约 | 教练正文可先按 Markdown 流式预览；思考态只展示公开处理状态，不展示模型内部推理链 |
| 2026-06-16 | AI 教练 LLM 调用增加 JSON response_format 约束 | Chat/下一步生成仍使用可选模型配置，但运行时强制 JSON object，减少模型自然语言输出导致的契约失败 |
| 2026-06-16 | AI 教练改为 Chat-First 工具调用式契约 | 教练可先聊天/追问/解释，按需生成最多 1 张练习卡；商务礼仪默认启用单选、多选、简答、改写和角色回应，简答必须真实调用评分 Prompt |
| 2026-06-15 | 新增 AI 教练 `ui_event_delta` 流式渲染契约 | 生成题卡时 SSE 可先返回公开题干/选项草稿；草稿不可提交且不得携带答案、评分规则或原始模型输出 |
| 2026-06-14 | 新增商务礼仪训练包发布与重练治理契约 | 发布前影响分析覆盖章节、小单元、题目、草稿、能力点、AI 教练配置和旧学员；支持未来学员、自愿切换和指定重练三种策略 |
| 2026-06-14 | 新增商务礼仪 AI 教练达标与补救流契约 | AI 教练训练卡写入能力点进度，按小单元配置判断达标、可上场、阻断和人工复盘 |
| 2026-06-14 | 新增商务礼仪训练包导入、小单元和能力点快照契约 | 明确能力点属于训练包版本快照，不建立全局目录；learner 小单元返回能力点摘要 |
| 2026-06-12 | 补充阶段 2 训练闭环契约 | 统一训练记录有效分投影、评分解释、能力画像、管理者看板和策略配置诊断 |
| 2026-06-03 | 细化新人训练路径 RBAC 与生命周期审计契约 | 区分超级管理员、内容管理员、培训负责人、运维人员、学员；关键日志要求记录 previous/next/status 变更 |
| 2026-05-28 | 补充培训负责人团队范围契约 | `support` 作为培训负责人兼容别名；跨用户记录按同部门过滤 |
| 2026-05-28 | 补充 COS 私有桶与 DashScope 文件识别契约 | 明确 COS 服务端上传、私有桶签名 GET URL、DashScope `fun-asr` 默认模型和敏感 URL 不落库 |
| 2026-05-28 | 契约初始创建 | 覆盖 sales trainer learner/admin 基础闭环、录音不限固定时长、`source_page`、`transcript_snapshot` 与 `/file` 文件读取语义 |
| 2026-06-01 | 新增材料库、任务简报、评分方案 rubric、提交快照和训练记录 read model | 销售训练材料单独管理；PPT 演练下载/确认当前版本后才能上传；历史记录冻结材料/评分/任务快照 |
