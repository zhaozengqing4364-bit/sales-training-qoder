# Sales Trainer API 契约

> 状态: 🔨 基础闭环联调契约（2026-05-28）
>
> 后端模块: `backend/src/sales_trainer/`
>
> 基础路径: learner `/api/v1/sales-trainer`；admin `/api/v1/admin/sales-trainer`

## 概览

- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie。
- 响应包裹: 统一为 `{ "success": boolean, "data": ..., "error": ..., "message": ..., "trace_id": "..." }`。
- 字段命名: API 入参与返回字段统一使用 `snake_case`。
- learner 权限: 只能读取已发布训练单元，只能提交、读取本人做题记录和本人音频提交。
- admin 权限: 可管理训练单元、评分提示词、音频提交、评分结果和操作日志，默认可见全部数据。
- 培训负责人权限: 默认由 `SALES_TRAINER_MANAGER_ROLES=support` 配置；可进入销售训练管理后台，跨用户数据按本人 `department` 限定团队范围。
- 团队范围: 培训负责人只能查看同部门学员的音频提交、AI 评分结果和操作日志；无部门时使用空范围兜底，不放大全局权限。

## 联调对齐说明

- 本文按本轮约定端点定义基础闭环契约，主线程后续按实际实现校对。
- 已对齐: learner/admin `/file` 文件读取语义、`source_page`、评分记录 `transcript_snapshot`，以及 multipart 上传时的 `duration_seconds`/`source_page` 表单字段。

## 录音上传边界

- 业务上不设置固定录音时长限制。
- `duration_seconds` 是可选元数据，只用于展示、分析或排查，不参与上传拦截和业务判定。
- 技术保护由可配置项承担: 音频格式、文件大小、存储后端、存储路径或对象 key、转写任务超时、评分任务超时。
- 前端不得基于固定时长拒绝上传；如需提示，应根据后端返回的格式、大小、存储或任务错误展示。

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
  is_correct?: boolean | null;
  score?: number | null;
  created_at: string;
}
```

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
  created_at: string;
}
```

`transcript_snapshot` 是评分记录的转写文本快照。评分结果必须能追溯当次评分使用的文本，即使后续重新转写或重评。

### `AudioScorePrompt`

```typescript
interface AudioScorePrompt {
  prompt_id: string;
  name: string;
  purpose: string;
  system_prompt: string;
  scoring_template: string;
  output_schema: Record<string, unknown>;
  version: number;
  status: "draft" | "published" | "archived";
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
}
```

`scoring_template` 必须包含 `{transcript}`。

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
  auto_process?: boolean;
}
```

Response `data`: `AudioSubmission`

### `GET /api/v1/sales-trainer/audio-submissions/{submission_id}`

查询本人音频提交、转写和最新评分结果。learner 查询他人提交返回 `[ACCESS_DENIED]`。

Response `data`: `AudioSubmission`

### `GET /api/v1/sales-trainer/audio-submissions/{submission_id}/file`

读取本人原始音频文件。

- 本地存储: 返回 `200`，响应体为音频内容，`Content-Type` 使用提交记录的 `content_type`。
- 对象存储: 返回 `302`，`Location` 为短期签名下载 URL。
- 只允许提交本人访问；他人音频返回 `[ACCESS_DENIED]`。

## admin API

所有 admin 接口要求 `admin` 或已配置的销售训练培训负责人角色。非授权角色返回 `[ROLE_REQUIRED]`。

### 训练单元

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/units` | 训练单元列表，支持 `include_archived`、`limit`、`offset` |
| `GET` | `/api/v1/admin/sales-trainer/units/{unit_id}` | 训练单元详情 |
| `POST` | `/api/v1/admin/sales-trainer/units` | 创建训练单元，默认 `draft` |
| `PUT` | `/api/v1/admin/sales-trainer/units/{unit_id}` | 更新 `draft` 训练单元 |
| `POST` | `/api/v1/admin/sales-trainer/units/{unit_id}/publish` | 发布训练单元 |
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

发布门禁:

- `quiz` 单元必须绑定至少 1 道题。
- `audio_scoring` 单元必须配置已发布 `audio.scoring_prompt_id`。
- `audio.pass_threshold` 如存在，必须在 `0-100` 范围内。
- 已归档单元不可发布。

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
| `PUT` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}` | 更新 `draft` 提示词 |
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish` | 发布提示词 |

Create request:

```typescript
interface AudioScorePromptCreate {
  name: string;
  purpose?: string;
  system_prompt: string;
  scoring_template: string;
  output_schema?: Record<string, unknown>;
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
}
```

校验规则:

- `scoring_template` 必须包含 `{transcript}`。
- 已发布或已归档提示词不可直接修改；需要新版本时由后续版本化能力承接。

### 操作日志

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/operation-logs` | 操作日志列表，支持 `actor_id`、`target_type`、`target_id`、`limit`、`offset` |

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
| `[ROLE_REQUIRED]` | 403 | 非 admin/培训负责人访问销售训练 admin 接口 |
| `[ACCESS_DENIED]` | 403 | learner 访问他人做题、音频或文件 |
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
| `[SCORING_PROMPT_NOT_EDITABLE]` | 400 | 修改非 `draft` 提示词 |
| `[SCORING_PROMPT_ARCHIVED]` | 400 | 发布已归档提示词 |
| `[AUDIO_PASS_THRESHOLD_INVALID]` | 400 | 通过线不在 `0-100` 范围 |
| `[DEUCATE_CONFIG_INVALID]` | 500 | Deucate 模型参数配置非法 |
| `[DEUCATE_CONFIG_MISSING]` | 500 | Deucate 配置缺失 |
| `[DEUCATE_TIMEOUT]` | 504 | Deucate 调用超时 |
| `[DEUCATE_REQUEST_FAILED]` | 502 | Deucate 请求失败 |
| `[DEUCATE_RESPONSE_INVALID]` | 502 | Deucate 返回非预期 JSON 或结构非法 |

## 配置项

| 配置项 | 默认值 | 读取位置 | 管理入口 | 校验与兜底 |
|---|---|---|---|---|
| `SALES_TRAINER_AUDIO_ALLOWED_MIME_TYPES` | `audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/webm,audio/mp4,audio/x-m4a` | 音频上传服务 | 环境配置/系统配置 | 缺失使用默认值；不命中返回 `[AUDIO_TYPE_NOT_ALLOWED]` |
| `SALES_TRAINER_AUDIO_MAX_FILE_SIZE_MB` | `200` | 音频上传服务 | 环境配置/系统配置 | 必须为正整数；非法返回 `[AUDIO_SIZE_CONFIG_INVALID]` |
| `SALES_TRAINER_AUDIO_STORAGE_BACKEND` | `local` | 上传 URL、multipart 上传和文件读取服务 | 环境配置/系统配置 | 支持 `local`、`oss`、`cos`；`oss` 缺配置返回 `[OSS_NOT_CONFIGURED]`，`cos` 缺配置返回 `[COS_NOT_CONFIGURED]` |
| `SALES_TRAINER_AUDIO_STORAGE_PATH` | `./data/sales_trainer_audio` | 本地 multipart 上传和文件读取 | 环境配置/系统配置 | 缺失使用默认值；文件不存在返回 `[AUDIO_FILE_NOT_FOUND]` |
| `SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS` | `3600` | 对象存储音频读取/供应商转写 URL | 环境配置/系统配置 | 必须为正整数；非法返回 `[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]` |
| `SALES_TRAINER_AUDIO_REMOTE_DOWNLOAD_TIMEOUT_SECONDS` | `60` | legacy 远程音频下载转写桥接 | 环境配置/系统配置 | 必须为正数；非法返回 `[AUDIO_REMOTE_DOWNLOAD_TIMEOUT_CONFIG_INVALID]`，超时返回 `[AUDIO_REMOTE_DOWNLOAD_TIMEOUT]` |
| `TENCENT_COS_SECRET_ID` / `TENCENT_COS_SECRET_KEY` / `TENCENT_COS_BUCKET` / `TENCENT_COS_REGION` | 无 | COS 签名与服务端上传 | 环境配置/密钥管理 | `SALES_TRAINER_AUDIO_STORAGE_BACKEND=cos` 时必填；缺失返回 `[COS_NOT_CONFIGURED]` |
| `TENCENT_COS_DOMAIN` | 无 | COS 公开读 URL 可选域名 | 环境配置/系统配置 | 仅在 `TENCENT_COS_PUBLIC_READ=true` 时用于返回公开 URL；私有桶默认生成签名 GET URL |
| `TENCENT_COS_PUBLIC_READ` | `false` | COS GET URL 生成 | 环境配置/系统配置 | 默认私有桶签名 URL；只有确认 bucket 公开读时才设为 `true` |
| `SALES_TRAINER_ASR_MODE` | `legacy` | 转写服务 | 环境配置/系统配置 | `file` 时使用 DashScope 录音文件识别，要求音频可通过 HTTP/HTTPS URL 访问 |
| `DASHSCOPE_API_KEY` | 无 | DashScope 文件识别 | 环境配置/密钥管理 | `SALES_TRAINER_ASR_MODE=file` 时必填，缺失返回 `[ASR_API_KEY_REQUIRED]` |
| `SALES_TRAINER_ASR_MODEL` | `fun-asr` | DashScope 文件识别 | 环境配置/系统配置 | `language_hints` 仅在 `paraformer-v2` 时传入 |
| `SALES_TRAINER_MANAGER_ROLES` | `support` | 销售训练后台权限判断 | 环境配置/系统配置 | 逗号分隔角色列表；缺失使用 `support`；团队范围按 `users.department` 过滤 |
| `DEUCATE_BASE_URL` | 无 | Deucate 评分服务 | 环境配置/模型配置 | 缺失返回 `[DEUCATE_CONFIG_MISSING]` |
| `DEUCATE_API_KEY` | 无 | Deucate 评分服务 | 环境配置/模型配置 | 缺失返回 `[DEUCATE_CONFIG_MISSING]` |
| `DEUCATE_MODEL` | `deucate` | Deucate 评分服务 | 环境配置/模型配置 | 缺失使用默认值 |
| `DEUCATE_TIMEOUT_SECONDS` | `30` | Deucate 评分服务 | 环境配置/模型配置 | 必须为正数；非法返回 `[DEUCATE_CONFIG_INVALID]`，超时返回 `[DEUCATE_TIMEOUT]` |
| `unit.config.audio.scoring_prompt_id` | 无 | 训练单元配置 | admin 训练单元管理 | 音频评分单元发布和评分时必须指向已发布提示词 |
| `unit.config.audio.purpose` | `general_audio_scoring` | 训练单元配置与学员上传页面 | admin 训练单元管理 | 必填字符串；缺失时前端使用默认用途 |
| `unit.config.audio.pass_threshold` | `70` | 训练单元配置 | admin 训练单元管理 | 必须在 `0-100`；缺失使用默认值 |
| `unit.config.quiz.pass_threshold` | 无 | 训练单元配置与做题服务 | admin 训练单元管理 | 必须为非负数字；非法返回 `[QUIZ_PASS_THRESHOLD_INVALID]` |

## 更新记录

| 日期 | 变更 | 说明 |
|---|---|---|
| 2026-05-28 | 补充培训负责人团队范围契约 | 默认 `support` 可访问销售训练管理页；跨用户数据按同部门过滤 |
| 2026-05-28 | 补充 COS 私有桶与 DashScope 文件识别契约 | 明确 COS 服务端上传、私有桶签名 GET URL、DashScope `fun-asr` 默认模型和敏感 URL 不落库 |
| 2026-05-28 | 契约初始创建 | 覆盖 sales trainer learner/admin 基础闭环、录音不限固定时长、`source_page`、`transcript_snapshot` 与 `/file` 文件读取语义 |
