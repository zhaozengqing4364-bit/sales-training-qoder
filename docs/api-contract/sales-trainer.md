# Sales Trainer API 契约

> 状态: 🔨 材料版本追溯闭环契约（2026-06-01）
>
> 后端模块: `backend/src/sales_trainer/`
>
> 基础路径: learner `/api/v1/sales-trainer`；admin `/api/v1/admin/sales-trainer`

## 产品命名与边界

本契约的用户可见产品名为“新人训练路径”。`sales_trainer`、`/sales-trainer`、`/api/v1/sales-trainer` 和 `/api/v1/admin/sales-trainer` 在第一版只作为兼容技术命名保留，不代表产品应继续对学员或管理员展示为“销售队列”或“销售训练队列”。

新人训练路径负责异步学习闭环：PPT/材料学习、录音上传、AI 转写、AI 评分、Markdown 文章学习、试卷考试、后台配置和审计。AI 实时对练由 `sales_bot`、`practice_sessions`、`training_runtime`、`/practice/[sessionId]` 和 `/api/v1/practice/sessions` 负责，两者在运行时、权限、失败语义和配置来源上保持独立。

模块 4“实时对练”在本版本只允许作为 disabled/coming-soon 占位配置出现，不开发实时对练功能，不创建 `PracticeSession`，不调用 `sales_bot` WebSocket 运行时。未来若接入实时对练，必须另行补充契约、启用开关、权限边界和回退策略。

## 概览

- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie。
- 响应包裹: 统一为 `{ "success": boolean, "data": ..., "error": ..., "message": ..., "trace_id": "..." }`。
- 字段命名: API 入参与返回字段统一使用 `snake_case`。
- learner 权限: 只能读取已发布训练单元，只能提交、读取本人做题记录和本人音频提交。
- 超级管理员权限: `admin` / `super_admin` 可管理内容配置、发布/归档、查看全局记录、查看日志、重试失败任务和显式重评历史成绩。
- 内容管理员权限: `content_admin` / `newcomer_content_admin` 可管理训练单元、文章绑定、题库、考卷、材料和评分提示词；不能查看学员记录、配置健康、操作日志或重试任务。
- 培训负责人权限: `support` / `training_lead` / `training_manager` 可查看本人 `department` 范围内的学员录音、评分结果、做题记录和训练记录；不能修改内容配置、查看系统日志或重试任务。无部门时使用空范围兜底，不放大全局权限。
- 运维人员权限: `operations` / `ops` / `operator` / `sre` 可查看配置健康、操作日志、全局记录，并可重试转写/评分任务、显式重评历史成绩；不能管理文章、题库、考卷、材料等内容配置。
- 销售训练材料单独管理: 销售训练 PPT、逐字稿、示例录音和附件属于 `sales_trainer` 域，不复用 `/admin/presentations` 的业务语义。
- PPT 演练门禁: `unit.config.audio.purpose="ppt_pitch"` 的任务必须绑定已发布材料，学员提交前必须确认当前要求版本；提交记录冻结材料、任务简报和评分方案快照。
- 兼容命名: API 路径和模块目录暂不改名；新增 DTO、后台导航和学员页面文案必须以“新人训练路径”为展示名。

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
  | "realtime_placeholder";

type NewcomerCompletionRule =
  | "audio_scored"
  | "paper_passed"
  | "all_audio_options_scored"
  | "placeholder_disabled";

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
    | "realtime_roleplay_placeholder";
  module_type: NewcomerModuleType;
  display_name: string;
  description: string;
  order_index: number;
  enabled: boolean;
  disabled_reason?: string | null;
  completion_rule: NewcomerCompletionRule;
  target_unit_id?: string | null;
  target_unit_ids?: string[];
  learning_content_id?: string | null;
  exam_paper_id?: string | null;
  material_binding_group?: string | null;
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
```

### 默认模块矩阵

| module_key | 默认名称 | module_type | 默认 enabled | completion_rule | 必要绑定 | 管理入口 | 权限 | audit action |
|---|---|---|---|---|---|---|---|---|
| `ppt_explanation` | `PPT 讲解录音` | `"audio_scoring"` | `true` | `audio_scored` | `target_unit_id`、已发布材料、已发布评分提示词 | admin 新人训练路径模块/材料/评分方案 | `sales_trainer.manage_modules`、`sales_trainer.manage_materials`、`sales_trainer.manage_prompts` | `newcomer_module.ppt_explanation.*` |
| `business_skills` | `商务技巧` | `"article_exam"` | `true` | `paper_passed` | `learning_content_id`、`exam_paper_id` | admin 新人训练路径文章绑定/考卷管理 | `sales_trainer.manage_modules`、`sales_trainer.manage_papers`、`learning_content.manage` | `newcomer_module.business_skills.*` |
| `elevator_pitch` | `电梯演讲` | `"audio_scoring_group"` | `true` | `all_audio_options_scored` | `duration_options[].target_unit_id`、已发布评分提示词 | admin 新人训练路径模块/评分方案 | `sales_trainer.manage_modules`、`sales_trainer.manage_prompts` | `newcomer_module.elevator_pitch.*` |
| `realtime_roleplay_placeholder` | `实时对练` | `"realtime_placeholder"` | `false` | `placeholder_disabled` | 无；只允许 `disabled_reason` | admin 新人训练路径模块配置 | `sales_trainer.manage_modules` | `newcomer_module.realtime_placeholder.*` |

### 校验与兜底

- `path_key` 必填，默认 `newcomer_training_path_v1`；读取历史 `new_seller_modules_v1` 时必须标记为 compatibility alias。
- `module_key` 在同一路径内唯一，`order_index` 必须为正整数且不可重复。
- `display_name`、`description`、`disabled_reason`、按钮文案和空状态文案属于后台可配置展示内容；缺失时服务端可使用安全默认值，但响应必须标明 `fallback_applied=true`。
- `"audio_scoring"` 模块必须绑定一个已发布 `audio_scoring` 单元、至少一个 required 材料绑定和已发布音频评分提示词；缺失返回 `[NEWCOMER_MODULE_BINDING_MISSING]`。
- `"article_exam"` 模块必须绑定已发布 `LearningContent` 和已发布 `ExamPaper`；草稿或归档内容对 learner 返回 `[LEARNING_CONTENT_NOT_PUBLISHED]` 或 `[PAPER_NOT_PUBLISHED]`。
- `"audio_scoring_group"` 模块必须至少有一个 duration option；每个 option 的 `duration_minutes` 必须大于 0，`target_unit_id` 必须指向已发布音频评分单元。
- `"realtime_placeholder"` 默认 disabled；即使 enabled，也只能展示占位和 `disabled_reason`，不得调用 `/api/v1/practice/sessions`。
- 非法 `module_type`、未知 `completion_rule`、重复 `module_key`、重复 `order_index` 或绑定不存在时，后台保存/发布返回 `[NEWCOMER_MODULE_CONFIG_INVALID]` 并写操作日志。
- 配置读取失败或配置缺失时 learner 不展示伪成功；返回空路径、诊断错误或 disabled 模块，由 UI 显示可配置空状态。

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

### `SalesTrainerPath`

Learner 首页使用 `GET /api/v1/sales-trainer/paths` 返回的路径 DTO。`levels[].module_key` 与
`levels[].module_type` 必须来自路径级 active revision 或兼容 backfill 的模块配置；前端只能把
`SalesTrainerUnit.config.path` 当旧数据兜底，不能用旧单元配置覆盖 active revision。

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
  latest_result?: unknown | null;
}
```

`path_revision_id` / `path_revision_no` 来自路径级 active revision；兼容旧 `Unit` 聚合
backfill 时可以为 `null`。学员考试、录音或学习记录需要冻结路径上下文时，应优先保存该
revision lineage；只有旧数据无法可靠匹配时才标记 legacy snapshot，而不能伪造 revision id。

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
  material_snapshot?: Record<string, unknown> | null;
  score_scheme_snapshot?: Record<string, unknown> | null;
  task_brief_snapshot?: Record<string, unknown> | null;
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
```

材料主档表示长期训练材料，例如“公司主胶片”；版本表示具体可下载文件。发布一个版本后，该版本成为 `current_version_id`，同一材料之前的 published 版本自动归档，确保同一材料只有一个当前发布版本。

### `SalesTrainerUnitBrief`

```typescript
interface SalesTrainerUnitBrief {
  unit: SalesTrainerUnit;
  task_brief: Record<string, unknown>;
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
    current_version: SalesTrainerMaterialVersion;
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
```

学员 PPT 演练页必须以该 DTO 为准渲染任务意义、最新版材料、学员可见 rubric 和上传门禁，不得在页面组件里写死 PPT 下载地址、评分维度、通过线或任务说明。

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

查询 learner 可用训练单元。只返回 `published` 状态。

Response `data`:

```typescript
interface SalesTrainerUnitListResponse {
  items: SalesTrainerUnit[];
  total: number;
}
```

### `GET /api/v1/sales-trainer/units/{unit_id}`

查询 learner 可见训练单元详情。未发布或不存在均返回 `[SALES_TRAINER_UNIT_NOT_FOUND]`。

Response `data`: `SalesTrainerUnit`

### `GET /api/v1/sales-trainer/units/{unit_id}/brief`

查询 learner 侧训练任务简报、当前材料版本和学员可见评分方案。未发布或不存在返回 `[SALES_TRAINER_UNIT_NOT_FOUND]`；绑定材料缺失、未发布或无当前版本时返回对应材料错误码。

Response `data`: `SalesTrainerUnitBrief`

### `GET /api/v1/sales-trainer/materials/versions/{version_id}/file`

下载 learner 可见的已发布训练材料版本。

- 本地存储: 返回 `200` 文件内容。
- 对象存储: 返回 `302` 短期签名下载 URL。
- 版本不存在或未发布返回 `[MATERIAL_VERSION_NOT_PUBLISHED]`。

### `POST /api/v1/sales-trainer/quiz-attempts`

提交做题结果。仅允许提交 `quiz` 类型且已发布训练单元。

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

提交已发布考卷答案。服务端按 `paper_id` 找到考卷 active revision 和兼容 quiz 执行单元并复用当前题型评分逻辑。`answers[].question_id` 必须属于该考卷当前 active revision，额外题目返回 `[QUIZ_ANSWER_QUESTION_NOT_IN_UNIT]`。提交成功后，attempt 必须记录当时的 `paper_revision_id`；answer payload 必须冻结题目快照和 `attempt_context`，其中包含提交时命中的 `path_key`、`path_revision_id`、`path_revision_no`、`module_key`、`paper_revision_id`。旧数据无法可靠匹配路径修订时返回 `legacy_snapshot_only=true`，不得从最新路径配置伪造历史 revision。

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

查询新人训练路径模块绑定的 learner 可见 Markdown 文章。默认从已发布模块单元的 `config.path.learning_content_id` 读取绑定；`learning_content_id` 查询参数仅用于兼容调试/显式预览，不是业务真源。实际文章内容、章节、图片 Markdown 仍由现有 `LearningContent` / `LearningChapter` 后台维护。

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
| `auto_process` | boolean | 否 | 默认 `true`，为 `true` 时触发转写和评分 |
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

Response `data`: `{ module_key: string; learning_content_id: string }`。

权限、校验与审计:

- 权限复用新人训练路径内容管理能力：`admin`、`super_admin`、`content_admin`、`newcomer_content_admin`。
- `learning_content_id` 必须指向已发布 `LearningContent`；缺失、草稿、归档或不存在均不写入绑定。
- `module_key` + `path_key` 必须定位到已发布且 enabled 的 `"article_exam"` 模块配置；缺失返回 `[NEWCOMER_MODULE_CONFIG_MISSING]`。
- 成功后写入 `SalesTrainerOperationLog`：`action="newcomer_module.article_binding_changed"`、`target_type="newcomer_training_module"`、`target_id=module_key`，metadata 记录新旧 `learning_content_id` 与 `path_key`。

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
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/archive` | 归档材料 |
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/versions` | 为材料新增版本，默认 `draft` |
| `POST` | `/api/v1/admin/sales-trainer/materials/{material_id}/versions/upload` | 上传文件并为材料新增版本，默认 `draft` |
| `POST` | `/api/v1/admin/sales-trainer/materials/versions/{version_id}/publish` | 发布版本并设为当前版本 |

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

版本发布规则:

- 同一材料同一 `version_label` 唯一。
- 发布版本时，材料主档状态变为 `published`，`current_version_id` 指向该版本。
- 同一材料旧的 published 版本自动归档，保证“最新版”定义唯一。
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
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish` | 发布提示词 |

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

校验规则:

- `scoring_template` 必须包含 `{transcript}`。
- `learner_rubric` 必须是对象；维度、权重、常见扣分点和通过线作为评分方案配置读取，不得散落在页面。
- 已发布提示词编辑必须生成 working revision，并标记为高风险评分规则修改；发布该修订后只影响后续录音评分，历史评分结果继续引用提交时 prompt、rubric 或 hash。
- 已归档提示词不可继续编辑，返回 `[SCORING_PROMPT_NOT_EDITABLE]`。

### 学员训练记录

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/training-records` | 统一训练记录列表，支持 `user_id`、`unit_id`、`material_version_id`、`limit`、`offset` |
| `GET` | `/api/v1/admin/sales-trainer/training-records/audio/{submission_id}` | 录音训练记录详情，聚合材料/录音/转写/评分/操作记录 |

Response `data`:

```typescript
interface SalesTrainerTrainingRecordListResponse {
  items: Array<{
    record_id: string;
    record_type: "audio_submission" | "quiz_attempt";
    path_key?: string | null;
    path_revision_id?: string | null;
    path_revision_no?: number | null;
    module_key?: string | null;
    legacy_snapshot_only: boolean;
    unit_id: string;
    unit_name?: string | null;
    unit_type: "quiz" | "audio_scoring";
    user_id: string;
    user_name?: string | null;
    user_department?: string | null;
    status: string;
    score?: number | null;
    max_score?: number | null;
    passed?: boolean | null;
    submitted_at?: string | null;
    material_snapshot?: Record<string, unknown> | null;
    score_scheme_snapshot?: Record<string, unknown> | null;
    task_brief_snapshot?: Record<string, unknown> | null;
    audio_submission?: AudioSubmission | null;
    quiz_attempt?: QuizAttempt | null;
    operation_logs?: OperationLog[];
  }>;
  total: number;
}
```

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
| `[QUIZ_ANSWER_QUESTION_NOT_IN_UNIT]` | 400 | 提交了不属于该单元的题目 |
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
| `[NEWCOMER_MODULE_CONFIG_INVALID]` | 422 | 新人训练路径模块配置非法，例如未知 `module_type`、重复排序或绑定不存在 |
| `[NEWCOMER_MODULE_BINDING_MISSING]` | 409 | 模块必要绑定缺失，例如文章、考卷、材料、评分提示词或目标单元 |
| `[NEWCOMER_MODULE_DISABLED]` | 409 | learner 尝试进入已停用模块 |
| `[NEWCOMER_REALTIME_PLACEHOLDER_ONLY]` | 409 | 模块 4 仍为占位，不允许创建实时对练会话 |
| `[PAPER_NOT_PUBLISHED]` | 404/409 | 绑定考卷不存在、未发布或已归档 |
| `[LEARNING_CONTENT_NOT_PUBLISHED]` | 404/409 | 绑定学习内容不存在、未发布或已归档 |
| `[MATERIAL_FILE_NOT_FOUND]` | 404 | 材料文件不存在 |
| `[MATERIAL_FILE_ACCESS_DENIED]` | 403 | 本地材料文件不在允许存储目录内 |
| `[MATERIAL_FILE_URL_EXPIRES_CONFIG_INVALID]` | 500 | 材料文件访问链接有效期配置非法 |
| `[TRAINING_RECORD_NOT_FOUND]` | 404 | 训练记录不存在 |

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
| `SALES_TRAINER_MANAGER_ROLES` | `support,training_lead,training_manager` | 培训负责人记录查看能力兼容配置 | 环境配置/系统配置 | 逗号分隔角色列表；缺失使用默认培训负责人角色；只授予团队记录读取能力，不授予内容管理、日志、配置健康或任务重试能力 |
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
| `newcomer_path.modules[].module_type` | 无 | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | 只允许 `"audio_scoring"`、`"article_exam"`、`"audio_scoring_group"`、`"realtime_placeholder"` |
| `newcomer_path.modules[].display_name` | 默认模块矩阵名称 | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | 1-120 字符；缺失使用默认值并标记 `fallback_applied=true` |
| `newcomer_path.modules[].enabled` | 模块 1-3 `true`，模块 4 `false` | learner/admin 新人训练路径聚合服务 | admin 新人训练路径配置 | disabled 模块 learner 只展示停用状态，不允许提交或进入运行时 |
| `newcomer_path.modules[].target_unit_id(s)` | 无 | learner 模块入口、完成状态聚合 | admin 新人训练路径配置 | 必须指向已发布训练单元；缺失返回 `[NEWCOMER_MODULE_BINDING_MISSING]` |
| `newcomer_path.modules[].learning_content_id` | 无 | 商务技巧文章入口 | admin 新人训练路径文章绑定 | 必须指向已发布 `LearningContent`；缺失或草稿返回 `[LEARNING_CONTENT_NOT_PUBLISHED]` |
| `newcomer_path.modules[].exam_paper_id` | 无 | 商务技巧考卷入口 | admin 新人训练路径考卷管理 | 必须指向已发布考卷；缺失或草稿返回 `[PAPER_NOT_PUBLISHED]` |
| `newcomer_path.modules[].duration_options` | `10/20/30` 分钟可由 seed 初始化 | 电梯演讲模块入口 | admin 新人训练路径配置 | 每项必须有正数时长和已发布音频单元；非法返回 `[NEWCOMER_MODULE_CONFIG_INVALID]` |
| `newcomer_path.modules[].audit_events` | `newcomer_module.<module_key>.*` | 操作日志服务 | 系统初始化/后台配置 | 事件名必填；发布、归档、绑定变更必须写 operation log |

## 更新记录

| 日期 | 变更 | 说明 |
|---|---|---|
| 2026-06-03 | 细化新人训练路径 RBAC 与生命周期审计契约 | 区分超级管理员、内容管理员、培训负责人、运维人员、学员；关键日志要求记录 previous/next/status 变更 |
| 2026-05-28 | 补充培训负责人团队范围契约 | `support` 作为培训负责人兼容别名；跨用户记录按同部门过滤 |
| 2026-05-28 | 补充 COS 私有桶与 DashScope 文件识别契约 | 明确 COS 服务端上传、私有桶签名 GET URL、DashScope `fun-asr` 默认模型和敏感 URL 不落库 |
| 2026-05-28 | 契约初始创建 | 覆盖 sales trainer learner/admin 基础闭环、录音不限固定时长、`source_page`、`transcript_snapshot` 与 `/file` 文件读取语义 |
| 2026-06-01 | 新增材料库、任务简报、评分方案 rubric、提交快照和训练记录 read model | 销售训练材料单独管理；PPT 演练下载/确认当前版本后才能上传；历史记录冻结材料/评分/任务快照 |
