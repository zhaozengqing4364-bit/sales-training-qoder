# 石犀销售训练 MVP — 设计方案 v4

> 状态：P0/P1 基础闭环已实现；2026-07-15 起培训负责人使用 `training_manager` 角色，人员范围只由显式 Team leader/membership 关系决定，`User.department` 已退役；录音文件识别已接入 DashScope Paraformer + COS/HTTP URL 路径；真实 COS + DashScope 文件识别 + Deucate 评分端到端 smoke 已通过
> 最后更新：2026-07-15
> 目标：先落地基础训练闭环，不做完整客户模拟系统。

> Migration 口径：本文 2026-05-27/28 的 `070`—`072` 记录是首发前问题与验证历史。自 2026-07-15 起，这些 revision 已只读归档，最终结构由活动首发基线 `20260715_0000_001` 从空 PostgreSQL 一次建立；不得把下文的旧 revision 号理解为当前 Alembic head 或现行升级入口。

---

## 一、范围收敛

本阶段只做三个基础模块：

1. **做题模块**：支持单选题、多选题、判断题、简答题。题库优先复用当前系统已有题库；若当前题库没有对应题型或选项结构，本阶段不新造完整题库体系，后续单独补题库能力。
2. **录音上传原子能力**：用户上传录音文件，后端保存原音频，解析成文字，再把文字交给 AI 评分。
3. **后台留存与查询**：后台可查看每个人的操作记录、每个人上传的音频、AI 对音频的评分结果。

实现状态：

- [x] P0 后端已新增独立 `sales_trainer` 模块，覆盖训练单元、做题提交、音频上传/注册、转写、Deucate 评分、操作记录、后台查询。
- [x] 录音上传不设置固定时长限制；`duration_seconds` 仅作为可选元数据留存，不作为上传拦截条件。
- [x] 单选/多选/判断题通过现有 `QuestionItem.scoring_criteria` 适配；简答题保存答案但 P0 不做复杂 AI 批改。
- [x] 后台已支持操作记录、音频提交、AI 评分结果查询。
- [x] 学员端和管理端前端页面已实现，覆盖训练单元、做题、录音上传、结果查看、音频记录、评分结果、录音评分标准和操作日志。
- [x] 若现有题库缺少稳定选项结构，后台发布/创建 quiz 单元时阻断并写入 `question_type_unsupported` 操作记录；不再静默降级为简答题。
- [x] 录音文件识别选型为 DashScope 录音文件识别；已新增 `SALES_TRAINER_ASR_MODE=file` 配置路径，默认模型为官方示例中的 `fun-asr`，支持通过 COS/OSS/HTTP 音频 URL 提交异步转写任务并下载 `transcription_url` JSON 合并文本；`language_hints` 仅在 `SALES_TRAINER_ASR_MODEL=paraformer-v2` 时传入。
- [x] 后台导航已把“销售训练”升级为一级业务域；`support`/培训负责人只看到销售训练分组，管理员看到销售训练、课程训练、内容与知识、智能体与角色、策略中心、运营分析、组织权限、系统治理等独立分组。
- [x] 销售训练题库已独立成 `/admin/sales-trainer/questions` 入口，底层复用 `QuestionItem` / `QuestionCategory`，通过 `usage_scope=sales_trainer` 与通用题库隔离。
- [x] “评分提示词”在 UI 和主路由中已升级为“录音评分标准”；旧 `/admin/sales-trainer/score-prompts` 路由保留并跳转到 `/admin/sales-trainer/score-standards`。
- [x] 学员录音上传页已优先走浏览器直传：`getAudioUploadUrl -> PUT COS/OSS -> registerAudioSubmission`；后端 multipart 上传只保留为 local/fallback 路径。
- [x] 已新增销售训练配置健康页 `/admin/sales-trainer/settings`，展示存储、ASR、Deucate 和上传限制状态，不展示任何密钥值。

本阶段明确不做：

- 不做复杂客户角色库、行业库、客户追问引擎。
- 不做完整游戏化成长体系。
- 不做实时 WebSocket 对练。
- 不做复杂能力画像和团队智能诊断。
- 不把录音限制为固定时长。业务上只要是录音上传都支持；技术上允许通过配置控制文件大小、格式、存储策略和任务超时。

---

## 二、实现前配置化判断

### 2.1 稳定代码逻辑

以下内容属于稳定代码逻辑，可以写入代码：

- 用户鉴权、权限校验、owner/admin 访问边界。
- 题目读取、答题提交、答案保存、自动判分流程。
- 音频上传、文件元数据保存、音频状态流转。
- 音频转写任务创建、转写结果保存。
- 调用 Deucate 评分、解析评分结果、保存评分记录。
- 操作记录写入。
- 后台分页、筛选、详情查询。
- 错误码、状态机和数据一致性约束。

### 2.2 可配置业务规则

以下内容必须作为配置或数据管理，不写死在业务函数里：

- 录音评分标准。
- 评分维度、分值解释、通过线。
- 录音用途，例如 `ppt_pitch`、`sales_pitch`、`product_intro`。
- 支持的音频格式。
- 上传文件大小上限。
- 音频存储位置。
- 转写供应商和任务超时。
- Deucate 模型参数。
- 评分结果展示字段。
- 后台可见范围和操作权限。

### 2.3 配置项清单

| 配置项 | 用途 | 默认值 | 读取位置 | 管理入口 | 校验规则 | 权限 | 兜底策略 |
|---|---|---|---|---|---|---|---|
| `audio.allowed_mime_types` | 限制可上传音频格式 | `audio/mpeg,audio/wav,audio/webm,audio/mp4,audio/x-m4a` | 音频上传服务 | 系统配置或环境配置 | 非空数组 | admin | 缺失时使用默认值 |
| `audio.max_file_size_mb` | 控制单文件大小 | 按部署环境设置，建议 200MB 起 | 音频上传服务 | 系统配置或环境配置 | 正整数 | admin | 缺失时使用安全默认值 |
| `audio.storage_backend` | 音频保存位置 | 复用现有 `common/storage` 能力 | 音频存储服务 | 系统配置 | 必须是已启用 backend | admin | 配置非法则拒绝上传 |
| `audio.transcription_provider` | 录音转文字供应商 | 复用当前可用 ASR 供应商 | 转写服务 | 系统配置 | 必须可连通 | admin | 失败时标记 `transcription_failed` |
| `audio.transcription_timeout_seconds` | 转写任务超时 | 由运维配置 | 转写服务 | 系统配置 | 正整数 | admin | 超时后标记失败，可后台重试 |
| `audio.scoring_prompt_id` | 指定录音评分标准 | 按训练单元配置 | 录音评分服务 | 后台录音评分标准管理 | 必须是 published | admin/培训负责人 | 缺失则拒绝评分 |
| `audio.purpose` | 指定录音用途 | `general_audio_scoring` | 学员录音上传页面/录音评分服务 | 后台训练单元配置 | 非空字符串 | admin/培训负责人 | 缺失时前端使用默认用途 |
| `audio.scoring_pass_threshold` | 判断录音是否达标 | 70 | 训练单元配置 | 后台训练单元配置 | 0-100 | admin/培训负责人 | 缺失时使用默认值 |
| `audio.file_url_expires_seconds` | 控制授权播放/下载链接有效期 | 3600 | 音频文件读取服务 | 环境配置或系统配置 | 正整数 | admin | 非法则拒绝生成链接 |
| `audio.remote_download_timeout_seconds` | 控制 OSS 远程音频下载转写超时 | 60 | 转写服务 | 环境配置或系统配置 | 正数 | admin | 非法则标记转写失败 |
| `deucate.model_config` | Deucate 调用参数 | 由部署环境配置 | Deucate 评分客户端 | 模型配置 | provider/model 必填 | admin | 配置非法则评分失败并记录 |
| `quiz.enabled_question_types` | 做题模块启用题型 | 当前题库可支持的题型 | 做题服务 | 后台配置 | 只能包含受支持类型 | admin | 不支持题型不展示 |
| `quiz.pass_threshold` | 做题通过线 | 不配置则仅返回分数不判通过 | 做题服务 | 后台训练单元配置 | 非负数字 | admin/培训负责人 | 非法则拒绝保存/发布 |
| `sales_trainer.manager_roles` | 配置销售训练培训负责人角色 | `training_manager` | 销售训练权限模块 | 环境配置或系统配置 | 只接受受信任的培训负责人角色 | admin | 缺失时使用 `training_manager`；对象范围由 Team policy fail closed |

### 2.4 当前无法确认的信息

基于当前提供的代码，暂无法确认现有配置体系是否已经完整覆盖以下内容，需要补充配置模块、后台管理模块、字典表、权限模块或系统设置相关代码：

- 当前题库是否已经有单选题、多选题、判断题的选项结构。
- 当前音频转写供应商是否支持长音频文件转写和远程下载后的文件转写 SLA。
- Deucate 是否已经接入现有 `common/ai` 或模型配置模块。

这些不确定项不能通过硬编码解决，只能通过适配层或后续小步补齐。

---

## 三、模块设计

### 3.1 做题模块

职责：

- 从现有题库读取题目。
- 组织一组题目成为训练单元。
- 支持用户提交答案。
- 自动判单选、多选、判断题。
- 简答题可保存答案，是否 AI 批改由训练单元配置决定；本阶段重点不扩展复杂简答评分。

题型定义：

| 题型 | 说明 | P0 来源策略 |
|---|---|---|
| `single_choice` | 单选题 | 优先复用现有题库；若无选项结构，后续开发 |
| `multiple_choice` | 多选题 | 优先复用现有题库；若无选项结构，后续开发 |
| `true_false` | 判断题 | 优先复用现有题库；若无判断答案字段，后续开发 |
| `short_answer` | 简答题 | 复用现有 `QuestionItem.reference_answer`、`expected_keywords` 等字段 |

做题模块只通过 `QuestionBankAdapter` 读取题库，避免业务代码直接散落引用 `curriculum_practice` 内部实现。

```text
SalesTrainerQuizService
  -> QuestionBankAdapter
      -> existing QuestionItem / QuestionCategory / option data if available
```

如果适配器发现当前题库缺少对应题型数据：

- 后台不允许绑定该题型。
- 学员端不展示不可用题型。
- 操作记录写入 `question_type_unsupported`，方便后续判断是否需要补题库。

实现状态：

- [x] 已实现 `QuestionBankAdapter`，只通过适配层读取现有 `QuestionItem`。
- [x] 已新增 `question_items.usage_scope` 和 `question_categories.usage_scope`，销售训练只默认读取/绑定 `usage_scope=sales_trainer` 且 `status=published` 的题目；通用题库继续保留为全局管理入口。
- [x] 已实现销售训练专属题库 API 和页面，支持分类管理、列表筛选、新建/编辑、发布、归档。
- [x] 已实现业务化题型表单，后台接收单选、多选、判断、简答业务字段并生成 canonical `scoring_criteria`；销售训练表单默认不要求业务人员手写 JSON。
- [x] 已实现单选、多选、判断题自动判分；判断题支持布尔值、`true/false`、`对/错` 等常见提交值。
- [x] 已实现做题提交、答案保存、得分保存和 `quiz_submitted` 操作日志。
- [x] 已实现 `question_type_unsupported` 专项日志；声明为单选/多选/判断但缺少必要选项或正确答案结构时，后台创建/发布 quiz 单元会返回 `[QUESTION_TYPE_UNSUPPORTED]` 并阻断。

### 3.2 录音上传原子能力

录音能力封装为独立原子能力，不绑定具体场景。

同一个能力后续可以通过配置复用于：

- PPT 讲解训练。
- 石犀产品介绍训练。
- 销售话术训练。
- 客户拜访复盘。
- 渠道方案讲解。

录音上传流程：

```text
用户选择训练单元
  -> 上传录音文件
  -> 后端保存音频元数据和文件地址
  -> 写入操作记录 audio_uploaded
  -> 后台任务转写音频
  -> 保存 transcript
  -> 调用 Deucate 执行 AI 评分
  -> 保存评分结果
  -> 学员端/后台查看结果
```

状态机：

| 状态 | 含义 |
|---|---|
| `uploaded` | 音频已上传并留存 |
| `transcribing` | 正在转文字 |
| `transcribed` | 转写成功 |
| `transcription_failed` | 转写失败 |
| `scoring` | 正在调用 Deucate 评分 |
| `scored` | 评分成功 |
| `scoring_failed` | 评分失败 |

业务上不设置固定录音时长限制。技术限制只来自可配置的文件大小、格式、存储和后台任务超时。

实现状态：

- [x] 已实现上传 URL 生成、直接 multipart 上传、音频元数据保存、文件 hash、状态流转和本人/后台查询。
- [x] 已实现 COS/OSS 浏览器直传优先路径：前端先获取预签名 URL，再由浏览器 PUT 到对象存储，最后注册 `cos://`/`oss://` 提交。
- [x] 注册 `cos://`/`oss://` 音频提交时，后端只执行对象存储 HEAD 校验，不下载文件；对象不存在返回 `[AUDIO_OBJECT_NOT_FOUND]`，对象大小不一致返回 `[AUDIO_OBJECT_SIZE_MISMATCH]`。
- [x] 已实现无固定时长限制回归测试：可保存长录音 `duration_seconds` 元数据，上传拦截只看文件格式和文件大小配置。
- [x] 已保留 `duration_seconds` 字段作为展示/分析元数据；不参与业务校验。
- [x] 本地上传默认保存到 `SALES_TRAINER_AUDIO_STORAGE_PATH`，默认 `./data/sales_trainer_audio`。
- [x] 已实现 OSS/远程 key 下载转写桥接：远程 key 生成短期 GET URL，下载到临时文件后复用现有 ASR `transcribe_file`，下载/签名/配置异常会以明确错误码进入 `transcription_failed`。

### 3.3 Deucate 评分模块

评分标准统一通过 AI 提示词调用 Deucate 完成。

本阶段不做复杂规则引擎，不做多模型仲裁，不做实时评分。

输入：

- 训练单元名称。
- 录音用途。
- 转写文本。
- 评分提示词。
- 可选参考材料或评分维度。

输出统一 JSON：

```json
{
  "total_score": 82,
  "passed": true,
  "summary": "表达清楚，产品价值有提到，但案例和下一步行动不足。",
  "strengths": ["结构完整", "能说明核心价值"],
  "improvements": ["补充客户场景", "增加下一步推进动作"],
  "dimension_scores": {
    "content_accuracy": 85,
    "expression_clarity": 80,
    "structure": 78
  }
}
```

如果 Deucate 返回非 JSON：

- 最多重试 1 次。
- 仍失败则记录 `scoring_failed`。
- 不伪造分数。
- 后台允许管理员手动触发重评。

实现状态：

- [x] 已实现最小 `HttpDeucateClient`，使用 `DEUCATE_BASE_URL`、`DEUCATE_API_KEY`、`DEUCATE_MODEL`、`DEUCATE_TIMEOUT_SECONDS`。
- [x] 已实现评分提示词表、发布状态校验、提示词 hash、原始返回、标准化评分结果留存。
- [x] 已实现 Deucate 非 JSON 返回时重试 1 次，仍失败则记录 `[DEUCATE_RESPONSE_INVALID]`。
- [x] 已实现 Deucate timeout 配置校验，`DEUCATE_TIMEOUT_SECONDS` 非法或非正数时返回 `[DEUCATE_CONFIG_INVALID]`，不裸抛运行时异常。
- [x] 已实现后台重试转写和重试评分接口。

### 3.4 后台留存模块

后台必须提供三类数据留存和查询。

#### 操作记录

记录每个人的关键业务操作，不做全量点击埋点。

需要记录：

- 做题提交。
- 录音上传。
- 转写开始、成功、失败。
- 评分开始、成功、失败。
- 管理员修改训练单元。
- 管理员修改评分提示词。
- 管理员重试转写或评分。

#### 音频留存

每条上传音频必须可追溯：

- 上传人。
- 上传时间。
- 原文件名。
- 文件类型。
- 文件大小。
- 存储 key/url。
- 文件 hash。
- 训练单元。
- 上传来源页面。
- 当前处理状态。
- 转写文本。

后台可播放或下载音频，权限仅限 admin/培训负责人/本人。

实现状态：

- [x] 已实现音频提交记录、元数据、状态、转写和最新评分结果查询。
- [x] 已实现 `source_page` 上传来源页面留存；multipart 上传页面写入 `sales_trainer_audio_upload`，对象存储注册接口也支持可选来源。
- [x] 已实现学员端/管理端授权播放与下载 URL；后端验证 owner、平台管理员或负责该显式 Team 的培训负责人后，本地文件返回 `FileResponse`，对象存储文件返回短期签名 URL 重定向。
- [x] P0 权限已覆盖 admin、本人和培训负责人 Team 范围；培训负责人角色为 `training_manager`，缺少有效 leader/membership 关系时 fail closed。

#### AI 评分结果留存

每次 AI 评分都要保存：

- 音频提交 ID。
- 转写文本快照。
- 使用的评分提示词 ID、版本和 hash。
- Deucate 模型配置摘要。
- AI 原始返回 JSON。
- 标准化评分结果。
- 错误码和错误信息。
- 评分耗时。
- 创建时间。

实现状态：

- [x] 已保存评分提示词 ID、版本、hash、Deucate 模型名、AI 原始 JSON、标准化评分、错误码、错误信息、耗时和创建时间。
- [x] 已保存 `transcript_snapshot`，确保评分结果能追溯当次评分使用的转写文本。
- [x] 已新增 `/api/v1/admin/sales-trainer/score-results`，支持按 `user_id`、`submission_id` 查询 AI 评分结果。

---

## 四、数据库设计

### 4.1 实体关系

```text
User
  -> SalesTrainerUnit
      -> QuizAttempt
          -> QuizAttemptAnswer
      -> AudioSubmission
          -> AudioTranscript
          -> AudioScoreResult
  -> OperationLog

SalesTrainerUnit
  -> existing QuestionItem via bindings
  -> AudioScoringPrompt
```

### 4.2 新表清单

| 表名 | 职责 |
|---|---|
| `sales_trainer_units` | 训练单元配置，组合做题或录音能力 |
| `sales_trainer_unit_questions` | 训练单元和现有题库题目的绑定 |
| `sales_trainer_quiz_attempts` | 做题提交记录 |
| `sales_trainer_quiz_answers` | 单题答案记录 |
| `sales_trainer_audio_submissions` | 录音上传记录和处理状态 |
| `sales_trainer_audio_transcripts` | 录音转写结果 |
| `sales_trainer_audio_score_prompts` | 录音评分标准，后端模型名暂保留 prompt 以避免无价值迁移 |
| `sales_trainer_audio_score_results` | AI 评分结果 |
| `sales_trainer_operation_logs` | 用户和管理员操作记录 |

### 4.12 复用题库表的销售训练范围隔离

```sql
ALTER TABLE question_categories
    ADD COLUMN usage_scope VARCHAR(50) NOT NULL DEFAULT 'general';

ALTER TABLE question_items
    ADD COLUMN usage_scope VARCHAR(50) NOT NULL DEFAULT 'general';

CREATE INDEX idx_question_items_scope_status ON question_items(usage_scope, status);
CREATE INDEX idx_question_items_scope_category ON question_items(usage_scope, category_id);
```

实现状态：

- [x] 已新增 Alembic 迁移 `20260528_1600_072_sales_trainer_question_scope.py`，包含两个 `usage_scope` 字段、必要索引和默认销售训练分类 `sales-trainer-default`。
- [x] 旧全局 `/admin/test-bank` 继续作为通用题库；销售训练题库只通过专属 API 读写 `sales_trainer` 范围。

### 4.3 `sales_trainer_units`

```sql
CREATE TABLE sales_trainer_units (
    unit_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(200) NOT NULL,
    description      TEXT,
    unit_type        VARCHAR(30) NOT NULL, -- quiz / audio_scoring
    config           JSONB NOT NULL DEFAULT '{}',
    status           VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by       UUID REFERENCES users(id),
    updated_by       UUID REFERENCES users(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_sales_trainer_unit_type CHECK (unit_type IN ('quiz','audio_scoring')),
    CONSTRAINT ck_sales_trainer_unit_status CHECK (status IN ('draft','published','archived'))
);
```

`config` 示例：

```json
{
  "audio": {
    "scoring_prompt_id": "prompt-uuid",
    "pass_threshold": 70,
    "purpose": "ppt_pitch"
  },
  "quiz": {
    "shuffle_questions": false,
    "enabled_question_types": ["single_choice", "multiple_choice", "true_false", "short_answer"]
  }
}
```

### 4.4 `sales_trainer_unit_questions`

```sql
CREATE TABLE sales_trainer_unit_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id         UUID NOT NULL REFERENCES sales_trainer_units(unit_id) ON DELETE CASCADE,
    question_id     UUID NOT NULL REFERENCES question_items(question_id) ON DELETE RESTRICT,
    order_index     INTEGER NOT NULL DEFAULT 1,
    points          INTEGER NOT NULL DEFAULT 10,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(unit_id, question_id),
    CONSTRAINT ck_sales_trainer_question_order CHECK (order_index >= 1),
    CONSTRAINT ck_sales_trainer_question_points CHECK (points > 0)
);
```

### 4.5 `sales_trainer_quiz_attempts`

```sql
CREATE TABLE sales_trainer_quiz_attempts (
    attempt_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id          UUID NOT NULL REFERENCES sales_trainer_units(unit_id),
    user_id          UUID NOT NULL REFERENCES users(id),
    total_score      NUMERIC(5,2),
    max_score        NUMERIC(5,2),
    passed           BOOLEAN,
    status           VARCHAR(20) NOT NULL DEFAULT 'submitted',
    submitted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_sales_trainer_quiz_status CHECK (status IN ('submitted','scored','failed'))
);
```

### 4.6 `sales_trainer_quiz_answers`

```sql
CREATE TABLE sales_trainer_quiz_answers (
    answer_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id       UUID NOT NULL REFERENCES sales_trainer_quiz_attempts(attempt_id) ON DELETE CASCADE,
    question_id      UUID NOT NULL REFERENCES question_items(question_id),
    question_type    VARCHAR(30) NOT NULL,
    answer_payload   JSONB NOT NULL,
    is_correct       BOOLEAN,
    score            NUMERIC(5,2),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.7 `sales_trainer_audio_submissions`

```sql
CREATE TABLE sales_trainer_audio_submissions (
    submission_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id            UUID REFERENCES sales_trainer_units(unit_id),
    user_id            UUID NOT NULL REFERENCES users(id),
    purpose            VARCHAR(50) NOT NULL DEFAULT 'general_audio_scoring',
    original_filename  VARCHAR(500) NOT NULL,
    content_type       VARCHAR(100) NOT NULL,
    size_bytes         BIGINT NOT NULL,
    storage_key        TEXT NOT NULL,
    file_hash          VARCHAR(128),
    duration_seconds   NUMERIC(10,2),
    source_page        VARCHAR(100),
    status             VARCHAR(40) NOT NULL DEFAULT 'uploaded',
    error_code         VARCHAR(100),
    error_message      TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_sales_trainer_audio_status CHECK (
        status IN (
            'uploaded',
            'transcribing',
            'transcribed',
            'transcription_failed',
            'scoring',
            'scored',
            'scoring_failed'
        )
    )
);
```

### 4.8 `sales_trainer_audio_transcripts`

```sql
CREATE TABLE sales_trainer_audio_transcripts (
    transcript_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id       UUID NOT NULL UNIQUE REFERENCES sales_trainer_audio_submissions(submission_id) ON DELETE CASCADE,
    provider            VARCHAR(50) NOT NULL,
    transcript_text     TEXT NOT NULL,
    raw_payload         JSONB,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.9 `sales_trainer_audio_score_prompts`

```sql
CREATE TABLE sales_trainer_audio_score_prompts (
    prompt_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name               VARCHAR(200) NOT NULL,
    purpose            VARCHAR(50) NOT NULL DEFAULT 'general_audio_scoring',
    system_prompt      TEXT NOT NULL,
    scoring_template   TEXT NOT NULL,
    output_schema      JSONB NOT NULL DEFAULT '{}',
    version            INTEGER NOT NULL DEFAULT 1,
    status             VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by         UUID REFERENCES users(id),
    updated_by         UUID REFERENCES users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_sales_trainer_prompt_status CHECK (status IN ('draft','published','archived'))
);
```

提示词模板变量：

- `{purpose}`：训练用途。
- `{transcript}`：转写文本。
- `{unit_name}`：训练单元名称。
- `{scoring_standard}`：评分标准说明。

### 4.10 `sales_trainer_audio_score_results`

```sql
CREATE TABLE sales_trainer_audio_score_results (
    score_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id        UUID NOT NULL REFERENCES sales_trainer_audio_submissions(submission_id) ON DELETE CASCADE,
    prompt_id            UUID NOT NULL REFERENCES sales_trainer_audio_score_prompts(prompt_id),
    prompt_version       INTEGER NOT NULL,
    prompt_hash          VARCHAR(128) NOT NULL,
    deucate_model        VARCHAR(100),
    transcript_snapshot  TEXT,
    total_score          NUMERIC(5,2),
    passed               BOOLEAN,
    summary              TEXT,
    strengths            JSONB NOT NULL DEFAULT '[]',
    improvements         JSONB NOT NULL DEFAULT '[]',
    dimension_scores     JSONB NOT NULL DEFAULT '{}',
    raw_response         JSONB,
    error_code           VARCHAR(100),
    error_message        TEXT,
    latency_ms           INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.11 `sales_trainer_operation_logs`

```sql
CREATE TABLE sales_trainer_operation_logs (
    log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id        UUID REFERENCES users(id),
    actor_role      VARCHAR(50),
    action          VARCHAR(100) NOT NULL,
    target_type     VARCHAR(50) NOT NULL,
    target_id       UUID,
    request_id      VARCHAR(100),
    ip_address      VARCHAR(100),
    user_agent      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sales_trainer_operation_actor ON sales_trainer_operation_logs(actor_id, created_at DESC);
CREATE INDEX idx_sales_trainer_operation_target ON sales_trainer_operation_logs(target_type, target_id);
```

---

## 五、后端结构

新增独立模块：

```text
backend/src/sales_trainer/
├── __init__.py
├── api.py
├── models.py
├── schemas.py
├── services/
│   ├── quiz_service.py
│   ├── question_bank_adapter.py
│   ├── audio_submission_service.py
│   ├── transcription_service.py
│   ├── deucate_scoring_service.py
│   ├── prompt_service.py
│   ├── operation_log_service.py
│   └── unit_service.py
└── tasks/
    ├── transcribe_audio.py
    └── score_audio.py
```

实现状态：

- [x] 上述后端模块已创建并挂载到 `backend/src/router_registry.py`。
- [x] 未新增 `repositories.py`，因为 P0 服务层逻辑足够薄，直接使用 SQLAlchemy `select()` 更简单。
- [x] 已在 `backend/alembic/env.py` 和测试 `conftest.py` 注册模型元数据。

依赖原则：

- `sales_trainer` 不引用 `sales_bot`。
- `sales_trainer` 不引用实时 WebSocket runtime。
- 做题模块仅通过 `QuestionBankAdapter` 读取现有题库。
- 录音上传、转写、评分、操作记录全部在 `sales_trainer` 内独立建模。
- 存储、鉴权、数据库连接可以复用 `common` 基础设施。

---

## 六、API 设计

### 6.1 学员端 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/sales-trainer/units` | 查询可用训练单元 |
| `GET` | `/api/v1/sales-trainer/units/{unit_id}` | 查询训练单元详情 |
| `POST` | `/api/v1/sales-trainer/quiz-attempts` | 提交做题结果 |
| `GET` | `/api/v1/sales-trainer/quiz-attempts/{attempt_id}` | 查看做题结果 |
| `POST` | `/api/v1/sales-trainer/audio-submissions/upload-url` | 获取音频上传 URL |
| `POST` | `/api/v1/sales-trainer/audio-submissions/upload` | 直接上传音频文件并注册提交 |
| `POST` | `/api/v1/sales-trainer/audio-submissions` | 注册音频上传并触发转写/评分 |
| `GET` | `/api/v1/sales-trainer/audio-submissions/{submission_id}` | 查看本人音频处理和评分结果 |

### 6.2 管理端 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/admin/sales-trainer/units` | 训练单元列表 |
| `POST` | `/api/v1/admin/sales-trainer/units` | 创建训练单元 |
| `PUT` | `/api/v1/admin/sales-trainer/units/{unit_id}` | 更新训练单元 |
| `POST` | `/api/v1/admin/sales-trainer/units/{unit_id}/publish` | 发布训练单元 |
| `POST` | `/api/v1/admin/sales-trainer/units/{unit_id}/archive` | 归档训练单元 |
| `GET` | `/api/v1/admin/sales-trainer/audio-submissions` | 查询所有音频上传记录 |
| `GET` | `/api/v1/admin/sales-trainer/audio-submissions/{submission_id}` | 查看音频、转写和评分详情 |
| `POST` | `/api/v1/admin/sales-trainer/audio-submissions/{submission_id}/retry-transcription` | 重试转写 |
| `POST` | `/api/v1/admin/sales-trainer/audio-submissions/{submission_id}/retry-scoring` | 重试评分 |
| `GET` | `/api/v1/admin/sales-trainer/score-results` | 查询 AI 评分结果 |
| `GET` | `/api/v1/admin/sales-trainer/operation-logs` | 查询操作记录 |
| `GET` | `/api/v1/admin/sales-trainer/question-categories` | 销售训练题库分类列表 |
| `POST` | `/api/v1/admin/sales-trainer/question-categories` | 创建销售训练题库分类 |
| `PUT` | `/api/v1/admin/sales-trainer/question-categories/{category_id}` | 更新销售训练题库分类 |
| `GET` | `/api/v1/admin/sales-trainer/questions` | 销售训练题目列表 |
| `POST` | `/api/v1/admin/sales-trainer/questions` | 创建销售训练题目 |
| `GET` | `/api/v1/admin/sales-trainer/questions/{question_id}` | 查看销售训练题目 |
| `PUT` | `/api/v1/admin/sales-trainer/questions/{question_id}` | 更新销售训练题目 |
| `POST` | `/api/v1/admin/sales-trainer/questions/{question_id}/publish` | 发布销售训练题目 |
| `POST` | `/api/v1/admin/sales-trainer/questions/{question_id}/archive` | 归档销售训练题目 |
| `GET` | `/api/v1/admin/sales-trainer/settings` | 销售训练配置健康状态 |
| `GET` | `/api/v1/admin/sales-trainer/audio-score-prompts` | 录音评分标准列表（后端兼容旧命名） |
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts` | 创建录音评分标准 |
| `PUT` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}` | 更新录音评分标准 |
| `POST` | `/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish` | 发布录音评分标准 |

实现状态：

- [x] 学员端和管理端 P0 API 已实现。
- [x] 后台评分结果列表接口已实现。
- [x] 直接上传接口是 P0 补充能力，用于在没有 OSS 前端直传时完成基础闭环。
- [x] 销售训练题库专属 API、settings 健康 API 和对象存储直传注册 HEAD 校验已实现。

---

## 七、前端页面

### 7.1 学员端

```text
web/src/app/(dashboard)/sales-trainer/
├── page.tsx                         # 训练单元列表
├── quiz/[unitId]/page.tsx            # 做题页面
├── quiz/result/[attemptId]/page.tsx  # 做题结果
├── audio/[unitId]/page.tsx           # 录音上传页面
└── audio/result/[submissionId]/page.tsx # 音频评分结果
```

### 7.2 管理端

```text
web/src/app/admin/sales-trainer/
├── page.tsx                         # 销售训练工作台
├── units/page.tsx                    # 训练单元管理
├── units/[unitId]/edit/page.tsx      # 单元编辑
├── questions/page.tsx                # 销售训练题库
├── questions/new/page.tsx            # 新建销售训练题目
├── questions/[questionId]/edit/page.tsx # 编辑销售训练题目
├── questions/categories/page.tsx     # 销售训练题库分类
├── audio-submissions/page.tsx        # 音频上传记录
├── audio-submissions/[submissionId]/page.tsx # 音频/转写/评分详情
├── score-results/page.tsx            # AI 评分结果查询
├── score-standards/page.tsx          # 录音评分标准
├── score-standards/[id]/edit/page.tsx # 录音评分标准编辑
├── settings/page.tsx                 # 配置健康
└── operation-logs/page.tsx           # 操作记录
```

实现状态：

- [x] 学员端页面已实现：训练单元列表、做题、做题结果、录音上传、音频评分结果。
- [x] 管理端页面已实现：工作台、训练单元列表/新建/编辑、销售题库列表/新建/编辑/分类、音频记录列表/详情、AI 评分结果列表、录音评分标准列表/新建/编辑、配置健康、操作日志。
- [x] 前端通过中心 `api.salesTrainer` / `api.admin.salesTrainer` facade 调用后端，不绕开统一 API 客户端。
- [x] 录音上传页面从 `unit.config.audio.purpose` 读取用途并随 multipart 上传提交；缺失时使用 `general_audio_scoring` 默认值。
- [x] 录音上传页面随 multipart 提交 `source_page`，管理端录音列表和详情展示来源页面。
- [x] 录音上传页面已优先调用 `uploadAudioSubmissionDirect()`，在 COS/OSS 场景走浏览器 PUT 直传；仅 local/fallback 场景走 multipart。
- [x] `AdminSidebar` 已新增销售训练一级分组和 8 个入口；support 用户侧边栏只显示销售训练域。

---

## 八、权限与留存

### 8.1 权限

| 数据 | 学员本人 | 培训负责人 | admin |
|---|---:|---:|---:|
| 自己的做题记录 | 可看 | 可看 | 可看 |
| 他人的做题记录 | 不可看 | 可看 | 可看 |
| 自己的音频 | 可看 | 可看 | 可看 |
| 他人的音频 | 不可看 | 可看 | 可看 |
| AI 评分结果 | 可看自己的 | 可看团队 | 可看全部 |
| 操作记录 | 不可看 | 可看团队 | 可看全部 |
| 评分提示词 | 不可改 | 可管理 | 可管理 |
| 训练单元 | 不可改 | 可管理 | 可管理 |

实现状态：

- [x] P0 已实现本人数据访问边界：学员只能看自己的音频/做题记录。
- [x] P0 已实现 admin 后台访问边界。
- [x] 已实现“培训负责人”角色和团队范围读取：`training_manager` 只通过当前有效的 `TeamLeaderAssignment` 取得 Team，再通过 `TeamMembership` 取得学员范围；后台音频、评分结果和 Journey 共用对象级 Team policy。

### 8.2 留存策略

本阶段必须保存：

- 音频原文件。
- 音频元数据。
- 转写文本。
- AI 评分结果。
- 操作记录。

删除策略不在 P0 做复杂设计。若后续要支持删除，必须同时处理音频文件、转写文本、评分结果和操作日志的审计关系，不能只删一张表。

---

## 九、失败处理

| 场景 | 处理 |
|---|---|
| 上传格式不支持 | 拒绝上传，返回 `[AUDIO_TYPE_NOT_ALLOWED]` |
| 文件超过配置大小 | 拒绝上传，返回 `[AUDIO_FILE_TOO_LARGE]` |
| 存储失败 | 返回 `[AUDIO_STORAGE_FAILED]`，不创建有效提交 |
| 转写失败 | 状态改为 `transcription_failed`，记录错误，可后台重试 |
| 转写为空 | 状态改为 `transcription_failed`，错误码 `[TRANSCRIPT_EMPTY]` |
| OSS 远程音频签名失败 | 状态改为 `transcription_failed`，错误码 `[AUDIO_REMOTE_SIGNING_FAILED]` |
| OSS 远程音频下载失败或超时 | 状态改为 `transcription_failed`，错误码 `[AUDIO_REMOTE_DOWNLOAD_FAILED]` 或 `[AUDIO_REMOTE_DOWNLOAD_TIMEOUT]` |
| COS/OSS 直传对象不存在 | 拒绝注册提交，返回 `[AUDIO_OBJECT_NOT_FOUND]` |
| COS/OSS 直传对象大小不一致 | 拒绝注册提交，返回 `[AUDIO_OBJECT_SIZE_MISMATCH]` |
| Deucate 配置缺失 | 状态改为 `scoring_failed`，错误码 `[DEUCATE_CONFIG_MISSING]` |
| Deucate 配置非法 | 状态改为 `scoring_failed`，错误码 `[DEUCATE_CONFIG_INVALID]` |
| Deucate 超时 | 状态改为 `scoring_failed`，错误码 `[DEUCATE_TIMEOUT]` |
| Deucate 返回非 JSON | 重试 1 次；仍失败则 `[DEUCATE_RESPONSE_INVALID]` |
| 提示词未发布 | 拒绝评分，错误码 `[SCORING_PROMPT_NOT_PUBLISHED]` |

---

## 十、分期交付

| 阶段 | 内容 | 目标 |
|---|---|---|
| P0 | 新建 `sales_trainer` 后端模块、训练单元、做题提交、录音上传、转写、Deucate 评分、操作记录、后台查询 | 基础闭环可用 |
| P1 | 管理端页面补齐：音频详情、评分详情、操作记录、评分提示词管理 | 后台可运营 |
| P2 | 做题模块按现有题库能力补齐单选/多选/判断适配；若当前题库缺少结构，再开发题型扩展 | 题型完整 |
| P3 | 将录音原子能力配置到 PPT 讲解、产品介绍等更多训练单元 | 能力复用 |

P0 的验收闭环：

1. 管理员创建一个 `audio_scoring` 训练单元并绑定已发布评分提示词。
2. 学员上传一段录音。
3. 后端保存音频原文件和上传记录。
4. 后端转写出文字。
5. 后端调用 Deucate 得到评分。
6. 学员能看到评分结果。
7. 后台能看到该学员的操作记录、音频、转写文本和 AI 评分结果。

实现状态：

- [x] P0 后端闭环已完成。
- [x] P1 管理端和学员端基础页面已完成，后台可运营训练单元、录音记录、评分结果、评分提示词和操作日志。
- [x] 架构重设计已完成：销售训练升级为后台一级业务域，新增专属题库、录音评分标准主路由、配置健康页和 COS/OSS 直传优先路径。
- [x] 已补充回归测试覆盖音频处理、无固定时长限制、上传来源留存、评分转写快照、培训负责人团队范围、后台评分结果查询、做题提交、判断题判分、unsupported question audit、OSS 远程 key 下载转写桥接、Deucate 非 JSON 一次重试、Deucate timeout 非法配置、Alembic 单一 head。
- [x] 真实 Deucate/ASR 联调 smoke 测试入口已实现并纳入专项验证命令；自动化集成测试默认仍用 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1` 保护，避免 CI 意外消耗真实供应商额度。
- [x] 已新增真实供应商联调配置预检脚本 `backend/scripts/verify_sales_trainer_real_provider_config.py`，用于在部署环境运行 smoke 测试前检查必填环境变量和真实 ASR 公网音频 URL；脚本读取 `backend/.env` 并允许 shell 环境变量覆盖 `.env`，不打印密钥值，配置缺失时退出码为 2，配置齐全时可通过 `--run-smoke` 直接执行真实供应商 smoke 测试；`--json`/`--json-report` 可输出不含密钥值的机器可读预检结果，包含生成时间、读取的 env 文件、是否请求 smoke、是否实际运行 smoke、smoke 命令和执行后的 smoke 退出码，便于作为联调证据留档。
- [x] 2026-05-28 本地开发环境已用真实 multipart 上传完成端到端 smoke：用户上传小音频后服务端上传腾讯云 COS，生成私有桶签名 GET URL，DashScope 文件识别返回转写，Deucate/DeepSeek 评分落库；验证提交 `e69700b9-0b8e-4790-92d0-158288447aa0` 状态为 `scored`，转写供应商为 `dashscope-paraformer-file`，评分模型为 `deepseek-v4-flash`，且转写 raw payload 未保留 COS/DashScope 签名查询参数。

---

## 十二、实现与测试记录

### 12.1 测试发现的问题与修复

| 所属章节 | 问题 | 修复 |
|---|---|---|
| 4.11 操作记录 | `SalesTrainerOperationLog` 直接使用 `metadata` 作为 ORM 属性，触发 SQLAlchemy Declarative 保留名错误，应用无法导入。 | 数据库列仍叫 `metadata`，Python 属性改为 `metadata_json`，API 输出继续返回 `metadata`。 |
| 6 API 设计 | 路由函数返回类型标注为 `dict | JSONResponse`，FastAPI 导入时尝试生成无效 response field。 | 移除路由函数上的联合返回类型标注，保留运行时返回结构。 |
| 3.1 做题模块 | 判断题用 `bool(answer_payload)` 判分会把字符串 `"false"` 错判为真。 | 新增严格布尔解析，支持 `true/false`、`1/0`、`对/错`。 |
| 3.3 Deucate 评分模块 | 非 JSON 返回未按设计重试。 | Deucate 返回 `[DEUCATE_RESPONSE_INVALID]` 时重试 1 次。 |
| 4 数据库设计 | 当时新增 migration 后 Alembic head 测试仍期望旧 head。 | 2026-05-28 当时把测试更新到 `20260528_1600_072`；该 revision 现已归档，当前活动 head 为首发基线 `20260715_0000_001`。 |
| 10 分期交付 | 只跑销售训练小范围测试时，仓库全局 coverage 阈值按全项目统计，功能断言 8 个全过但 coverage 总值 31% 低于 48%。 | 对本次变更使用 `--no-cov` 复跑范围测试作为功能验证；全量 coverage 应在全仓测试或 CI 中评估。 |
| 3.1 做题模块 | `question_type_unsupported` 未落地，声明为客观题但缺结构时会静默降级为 `short_answer`。 | 新增 `QuestionBankAdapter.unsupported_reason()`，后台创建/发布 quiz 单元时阻断并写 `question_type_unsupported` 操作记录。 |
| 3.2 录音上传原子能力 | 前端已拼接授权文件 URL，但后端缺少 `/file` 文件读取接口，播放/下载无法闭环。 | 新增学员端和管理端音频文件访问接口；owner/admin 授权后本地返回文件，OSS 返回短期签名 URL。 |
| 3.2 录音上传原子能力 | OSS/远程 key 只能明确失败为 `[AUDIO_FILE_NOT_LOCAL]`，无法进入转写闭环。 | 新增远程音频下载转写桥接：签名 URL 下载到临时文件后复用 ASR 文件转写接口，并补 fake signer/fetcher 回归测试。 |
| 3.3 Deucate 评分模块 | `DEUCATE_TIMEOUT_SECONDS` 非法时会在 client 初始化阶段裸抛 `ValueError`。 | 将 timeout 解析封装为可分类配置错误，非法或非正数返回 `[DEUCATE_CONFIG_INVALID]` 并留存评分失败结果。 |
| 5 后端结构 | `UnitService._validate_publishable()` 使用未传入的 `actor` 记录审计，单测触发 `NameError`。 | 将 `actor` 显式传入 `_validate_publishable()`，复跑后端 sales-trainer 专项测试通过。 |
| 7 前端页面 | 学员录音上传未从训练单元配置读取 `audio.purpose`，不同训练用途会退回默认值。 | 管理端训练单元表单新增 `audio.purpose` 配置，学员上传页面读取并提交该用途。 |
| 7 前端页面 | 后台没有独立 AI 评分结果列表页，`/score-results` 后端能力未形成运营入口。 | 新增 `web/src/app/admin/sales-trainer/score-results/page.tsx` 和导航入口，支持按 `user_id`、`submission_id` 查询并跳转录音详情。 |
| 7 前端页面 | 全量 `npm run lint` 发现 sales-trainer 表单同步 props 的 `useEffect` 触发 React 19 `set-state-in-effect` 错误。 | 移除表单内同步 props 的 effect；父页面仅在数据加载完成后挂载表单，创建页使用初始空状态。sales-trainer 目标路径 ESLint 已无 error。 |
| 7 前端页面 | 浏览器打开后台评分结果页时，前端 dev server 因本地后端未启动，`/users/me` server session 请求 `ECONNREFUSED`。 | 启动临时 mock API 覆盖 `/users/me` 和 `/admin/sales-trainer/score-results` 后重载验证，页面可正常渲染评分结果表格与导航。真实联调仍需启动后端服务。 |
| 7 前端页面 | 全量 `npm run lint` 仍存在非 sales-trainer 范围的 `web/src/app/(user)/practice/[sessionId]/page.tsx` React Compiler memoization error。 | 本次未改 practice 页；已用 sales-trainer 目标路径 ESLint、TypeScript 和专项测试验证本次交付范围。该全局 lint 残留需另行修复。 |
| 3.4 后台留存模块 | 设计要求音频留存“上传来源页面”，API 契约也有 `source_page`，但模型、迁移、schema 和前端上传链路未保存该字段。 | 新增 `sales_trainer_audio_submissions.source_page`，multipart 上传和注册接口均支持来源页面；学员录音上传页提交 `sales_trainer_audio_upload`，管理端列表/详情展示来源。 |
| 3.4 AI 评分结果留存 | 设计要求保存“转写文本快照”，API 契约也有 `transcript_snapshot`，但评分结果表未保存当次评分文本。 | 新增 `sales_trainer_audio_score_results.transcript_snapshot`，评分成功或失败记录均保存调用 Deucate 时使用的转写文本，并在 API 返回。 |
| 8.1 权限 | 旧实现曾按 `User.department` 过滤评分结果，既可能生成错误 SQL，也形成第二套授权权威。 | 首发契约移除 `User.department`；列表和详情统一接收 `TeamDataScope`，覆盖本 Team 可见、跨 Team 隐藏、无关系 fail closed。 |
| 8.1 权限 | 培训负责人访问跨 Team 音频详情时，服务层拒绝需要稳定映射为对象级不可见。 | 详情接口统一执行 Team scope 并返回不存在语义，避免泄露对象是否存在；回归测试覆盖跨 Team 访问。 |
| 7 前端页面 | `/admin` 布局只允许 `admin`，导致已授权的培训负责人 `support` 无法进入销售训练管理页。 | 服务端布局允许 `admin/support` 进入；客户端 `AdminShell` 将 `support` 限定到 `/admin/sales-trainer/**`，侧边栏只展示销售训练入口。 |
| 7 前端页面 | 前端测试发现 `admin-sidebar.tsx` 中误用了 Python 风格的命名参数语法 `*, expanded`，导致 TypeScript 解析失败。 | 改为 TypeScript options 参数 `{ expanded?: boolean }`，相关布局测试和 ESLint 通过。 |
| 12.2 验证方式 | 当前沙箱中 `UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest ...` 触发 uv 的 macOS `system-configuration` panic，无法作为测试证据。 | 改用仓库已有 `backend/.venv/bin/python -m pytest ...` 跑同一组后端专项测试，取得 14 passed 的可复现验证结果。 |
| 10 分期交付 | 真实 Deucate/ASR 联调没有可复用 smoke 入口，容易在部署环境仍停留在“人工试一下”。 | 新增 `tests/integration/test_sales_trainer_real_providers.py`，默认跳过；配置 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1`、Deucate 环境变量和真实 ASR 音频路径后可执行真实供应商联调验证。 |
| 10 分期交付 | 2026-05-28 复跑真实供应商 smoke 测试时，当前 shell 未开启 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS`，且缺少 `DEUCATE_BASE_URL`、`DEUCATE_API_KEY`、`SALES_TRAINER_REAL_ASR_AUDIO_PATH`；测试结果为 2 skipped，无法证明真实 Deucate/ASR 已联调通过。 | 不改业务代码；保留默认跳过的 smoke 测试入口，并将真实供应商端到端联调保留为部署环境待执行项。当前可交付范围以 fake ASR/fake scoring 的服务编排、契约、前后端专项测试通过为准。 |
| 12.2 验证方式 | 2026-05-28 扩展执行前端全量 `npx vitest run` 时，非 sales-trainer 的 `src/app/(user)/exam/[sessionId]/page.test.tsx` 36 个用例失败；共同根因是测试 mock 中 `api.practice.getRuntimePreflight` 为 `undefined`。 | 已补齐 exam 测试夹具中的 `getRuntimePreflight` mock，并同步进度面板当前文案断言；复跑 exam 单文件 36 passed，复跑前端全量 Vitest 130 files passed、873 passed、6 skipped。 |
| 12.2 验证方式 | 2026-05-28 扩展执行后端全量 `./.venv/bin/python -m pytest --no-cov` 时，已观察到多处非 sales-trainer 失败，例如 asset governance、curriculum snapshot、practice template、support runtime、training task template binding、voice clone 等用例；随后在性能/外部依赖段长时间无输出，未形成完整全量结果。 | 本次不改这些非 sales-trainer 模块；sales-trainer 后端专项测试、ruff、compileall 已通过。全量后端残留需按对应模块另行诊断，不能作为销售训练模块未通过的证据。 |
| 10 分期交付 | 真实供应商 smoke 测试虽然已存在，但部署环境运行前仍需要人工逐项确认环境变量，容易出现“测试被 skip 却误以为已联调”的风险。 | 新增 `backend/scripts/verify_sales_trainer_real_provider_config.py`，集中检查 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS`、`DEUCATE_BASE_URL`、`DEUCATE_API_KEY`、`SALES_TRAINER_REAL_ASR_AUDIO_PATH`；缺失时退出 2 并输出缺项，配齐后可用 `--run-smoke` 直接执行真实供应商 smoke 测试。 |
| 10 分期交付 | 真实供应商预检脚本初版只读取当前 shell 环境；如果部署人员按项目惯例把配置写入 `backend/.env`，脚本会误报缺参。 | 预检脚本改为读取 `backend/.env`，并允许 shell 环境变量覆盖 `.env`；新增单测覆盖 `.env` 读取和 shell 覆盖优先级。 |
| 10 分期交付 | 真实供应商预检结果初版只有人工可读文本，不方便在部署环境、CI 或文档中留存机器可读联调证据。 | 预检脚本新增 `--json`，输出 `ready`、`messages`、`checked_keys`，不包含密钥值；新增单测确认 JSON 输出不会泄露 `DEUCATE_API_KEY` 的值。 |
| 10 分期交付 | `--json` 只能输出到 stdout，部署或 CI 环境仍需额外重定向才能保留联调证据文件。 | 预检脚本新增 `--json-report <path>`，自动创建目录并写入不含密钥值的 JSON 报告；报告包含预检结果、检查键、smoke 命令和执行后的 smoke 退出码。 |
| 12.2 验证方式 | 手动验证 `--json-report` 时使用 zsh 只读变量名 `status` 保存退出码，导致包装命令失败，容易误读为脚本失败。 | 改用普通变量名 `exit_code` 复跑，确认脚本实际退出码为 2 且成功写入 JSON 报告文件。 |
| 10 分期交付 | 真实供应商 JSON 报告虽然可留档，但缺少生成时间、使用的 env 文件和 smoke 请求/执行状态，部署后审计时难以判断“何时、用哪份配置、是否真的触发 smoke”。 | 预检报告新增 `generated_at`、`env_file`、`smoke_requested`、`smoke_ran`，并用单测固定时间覆盖安全 payload；报告仍只包含键名和命令，不包含密钥值。 |
| 3.2 录音上传原子能力 | Paraformer 录音文件识别不支持直接提交本地文件或二进制流，只支持公网 HTTP/HTTPS 音频 URL；继续沿用旧 `transcribe_file(local_path)` 会误走实时/本地 ASR，不是真实文件识别。 | 新增 `ParaformerFileASRProvider`，通过 `Transcription.async_call + wait` 提交 `file_urls`，下载 `transcription_url` JSON 并合并 `transcripts` 文本；`TranscriptionService` 在 `SALES_TRAINER_ASR_MODE=file` 时支持 HTTP URL 和 COS/OSS signed URL。 |
| 3.2 录音上传原子能力 | 当前音频远程存储只支持阿里云 OSS 签名，用户提供的部署存储为腾讯云 COS，无法生成 Paraformer 可访问的音频 URL。 | 新增 `common.cos.signing` 和 `SALES_TRAINER_AUDIO_STORAGE_BACKEND=cos` 分支，支持 COS 上传 URL、播放/下载 URL 和 Paraformer 读取 URL；密钥只从环境变量读取，未写入代码或文档。 |
| 10 分期交付 | 真实 ASR smoke 仍检查 `SALES_TRAINER_REAL_ASR_AUDIO_PATH` 本地路径，与 Paraformer 文件识别的“公网 URL”要求冲突，容易配置齐但联调失败。 | 预检和真实 smoke 改为检查 `DASHSCOPE_API_KEY`、`SALES_TRAINER_ASR_MODE=file`、`SALES_TRAINER_REAL_ASR_AUDIO_URL`，并要求 URL 为 HTTP/HTTPS。 |
| 3.2 录音上传原子能力 | 用户补充的官方 API 示例使用 `model='fun-asr'`，而初版实现默认 `paraformer-v2` 且默认传 `language_hints`；`language_hints` 仅适用于 `paraformer-v2`，默认传给 `fun-asr` 会有供应商参数不匹配风险。 | 默认模型改为 `fun-asr`，初始化 provider 时设置 `dashscope.api_key`，并只在 `SALES_TRAINER_ASR_MODEL=paraformer-v2` 时传入 `language_hints`。 |
| 3.2 录音上传原子能力 | 本地真实上传测试发现 `backend/.venv` 缺少 `qcloud_cos`，即使依赖已写入 pyproject/lock，运行态仍会报 COS SDK 未配置。 | 在后端虚拟环境安装 `cos-python-sdk-v5`，并用 COS 签名单测覆盖 SDK client 调用路径。 |
| 3.3 Deucate 评分模块 | 本地 `.env` 中 `DEUCATE_BASE_URL` 未带 OpenAI-compatible `/v1` 路径，评分请求会打到错误地址。 | 将本地环境的 Deucate base URL 调整为 `/v1` 结尾；代码仍只读取环境变量，不硬编码供应商地址。 |
| 3.2 录音上传原子能力 | `SALES_TRAINER_AUDIO_STORAGE_BACKEND=cos` 时，multipart 上传初版仍把文件写入本地路径，导致后续 `SALES_TRAINER_ASR_MODE=file` 无法给 DashScope 提供公网 HTTP/HTTPS URL。 | `save_uploaded_file()` 增加 COS 服务端上传分支，保存 `cos://...` storage key；local 分支保留为无 COS 环境的兜底。 |
| 4 数据库设计 | 本地数据库处于旧建表状态，Alembic 版本已到 `070`，但实际表缺少后续追加到 `070` 的 `source_page` 和 `transcript_snapshot` 列，真实上传分别触发 500。 | 新增幂等修复迁移 `20260528_1500_071`，升级时补齐 `sales_trainer_audio_submissions.source_page` 和 `sales_trainer_audio_score_results.transcript_snapshot`，并更新 migration graph 测试 head。 |
| 3.2 录音上传原子能力 | 腾讯云 COS bucket 为私有读；配置了 `TENCENT_COS_DOMAIN` 后旧逻辑直接返回公开域名 URL，DashScope 下载音频时得到 403，转写失败。 | 新增 `TENCENT_COS_PUBLIC_READ=false`，仅当显式配置公开读时才返回公开域名；默认对 COS 生成签名 GET URL，真实端到端上传已通过。 |
| 3.4 AI 评分结果留存 | DashScope raw payload 初版保存了带签名 query 的 COS 音频 URL，虽然有效期短，仍不应进入长期业务数据。 | Paraformer raw payload 对 `file_url`、`url`、`audio_url` 递归去除 query，并移除 `transcription_url`；新增单测覆盖签名参数不落库。 |
| 12.2 验证方式 | 用户要求使用 `chrome-devtools` 全面测试，但当前 `chrome-devtools` MCP 在清理 stale profile 后返回 `Transport closed`，无法继续驱动页面。 | 记录为工具通道阻塞；本轮用后端真实 E2E、专项自动化、健康检查和已保存的浏览器截图补齐产品验证，未把工具故障误判为产品故障。 |
| 4.12 复用题库表的销售训练范围隔离 | 训练单元表单原来从全局题库读取 published 题目，销售训练单元可能绑定通用题库题目。 | 新增 `usage_scope=sales_trainer`，销售训练题库 API 和训练单元依赖加载均只读写销售训练范围；后端绑定校验也只接受已发布销售训练题目。 |
| 7 前端页面 | “销售训练”位于“业务资产”大分组内，support 入口也只是一个子项，业务人员需要在 13 个入口中找训练能力。 | 侧边栏新增“销售训练”一级分组和 8 个入口；support/培训负责人只展示销售训练分组，管理员后台拆分为多个业务域分组。 |
| 7 前端页面 | UI 主入口仍叫“评分提示词”，业务人员理解成本高，且旧路由暴露技术命名。 | 主导航和页面文案改为“录音评分标准”，新主路由为 `/admin/sales-trainer/score-standards`；旧 `/score-prompts` 路由保留兼容跳转。 |
| 3.2 录音上传原子能力 | `SALES_TRAINER_AUDIO_STORAGE_BACKEND=cos` 时前端仍默认走 multipart，生产上传会先消耗业务后端带宽。 | 学员录音上传页改为优先 `getAudioUploadUrl -> 浏览器 PUT COS/OSS -> registerAudioSubmission`；local/fallback 场景才走 multipart。 |
| 3.2 录音上传原子能力 | 直传注册如果只保存 `cos://...`，后端无法确认浏览器是否真的上传成功，后续 ASR 才发现对象不存在。 | 注册 `cos://`/`oss://` 时执行 HEAD 校验，不下载文件；对象不存在返回 `[AUDIO_OBJECT_NOT_FOUND]`，大小不一致返回 `[AUDIO_OBJECT_SIZE_MISMATCH]`。 |
| 6 API 设计 | 配置健康状态只能靠人工看 `.env`，容易泄露密钥或误判真实供应商是否可用。 | 新增 `/api/v1/admin/sales-trainer/settings`，只返回 configured 布尔值、模式、模型和上传限制，不返回密钥值。 |

### 12.2 已执行验证

| 命令 | 结果 |
|---|---|
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_cos_signing_service.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 26 passed，2 warnings；覆盖销售训练题库 API、support 权限、settings 不泄密、COS HEAD 校验、音频/题库服务和 Alembic 单一 head |
| `ruff check src/sales_trainer src/common/cos src/common/oss tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_cos_signing_service.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `npx vitest run --run src/lib/api/sales-trainer.test.ts src/components/admin/sales-trainer/unit-form.test.tsx src/components/layout/admin-sidebar.test.tsx src/app/admin/sales-trainer/units/page.test.tsx src/app/admin/sales-trainer/score-results/page.test.tsx` | 5 files passed，10 tests passed |
| `npx tsc --noEmit` | 通过 |
| `npx eslint src/app/admin/sales-trainer src/components/admin/sales-trainer src/components/layout/admin-sidebar.tsx src/components/layout/admin-sidebar.test.tsx src/lib/api/client-domains.ts src/lib/api/types.ts` | 通过 |
| `ruff check src/sales_trainer tests/unit/test_sales_trainer_services.py tests/integration/test_sales_trainer_api.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `PYTHONPATH=src uv run python -m compileall src/sales_trainer tests/unit/test_sales_trainer_services.py tests/integration/test_sales_trainer_api.py` | 通过 |
| `PYTHONPATH=src uv run pytest tests/unit/test_sales_trainer_services.py tests/integration/test_sales_trainer_api.py --no-cov` | 13 passed |
| `PYTHONPATH=src uv run pytest tests/unit/common/test_alembic_migration_graph.py --no-cov` | 1 passed |
| `npx vitest run 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.test.ts' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/admin/sales-trainer/score-results/page.test.tsx' 'src/components/admin/sales-trainer/unit-form.test.tsx'` | 5 files passed, 13 tests passed |
| `ruff check src/sales_trainer tests/unit/test_sales_trainer_services.py tests/integration/test_sales_trainer_api.py` | 通过 |
| `PYTHONPATH=src uv run python -m compileall src/sales_trainer tests/unit/test_sales_trainer_services.py tests/integration/test_sales_trainer_api.py` | 通过 |
| `npx tsc --noEmit` | 通过 |
| `npx eslint 'src/app/(dashboard)/sales-trainer/**/*.{ts,tsx}' 'src/app/admin/sales-trainer/**/*.{ts,tsx}' 'src/components/admin/sales-trainer/**/*.{ts,tsx}' 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.ts'` | 0 errors, 3 existing hook dependency warnings |
| Browser: `http://localhost:3445/admin/sales-trainer/score-results` + mock API `http://localhost:3444/api/v1` | 通过；页面渲染“销售训练评分结果”、筛选框、模块导航和 `submission-1` 评分行 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py --no-cov` | 14 passed |
| `./.venv/bin/python -m compileall src/sales_trainer tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py` | 通过 |
| `ruff check src/sales_trainer tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py` | 通过 |
| `npx vitest run 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.test.ts' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' 'src/app/admin/sales-trainer/score-results/page.test.tsx' 'src/components/layout/admin-shell.test.tsx' 'src/components/layout/admin-sidebar.test.tsx'` | 7 files passed, 20 tests passed |
| `npx tsc --noEmit` | 通过 |
| `npx eslint 'src/app/admin/layout.tsx' 'src/app/(dashboard)/sales-trainer/**/*.{ts,tsx}' 'src/app/admin/sales-trainer/**/*.{ts,tsx}' 'src/components/layout/admin-shell.tsx' 'src/components/layout/admin-sidebar.tsx' 'src/components/layout/admin-shell.test.tsx' 'src/components/layout/admin-sidebar.test.tsx' 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.ts' 'src/lib/api/client-domains.test.ts' 'src/lib/api/types.ts'` | 0 errors |
| `git diff --check -- 'backend/src/sales_trainer' 'backend/tests/integration/test_sales_trainer_api.py' 'backend/tests/unit/test_sales_trainer_services.py' 'backend/alembic/versions/20260527_1200_070_sales_trainer_mvp.py' 'docs/api-contract/sales-trainer.md' 'web/src/app/(dashboard)/sales-trainer' 'web/src/app/admin/sales-trainer' 'web/src/components/layout/admin-shell.tsx' 'web/src/components/layout/admin-sidebar.tsx' 'web/src/components/layout/admin-shell.test.tsx' 'web/src/components/layout/admin-sidebar.test.tsx' 'web/src/lib/api'` | 通过 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_real_providers.py --no-cov` | 2 skipped；当前环境未开启 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1`，且未配置完整 Deucate/真实 ASR 音频路径 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 15 passed，2 warnings |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_real_providers.py --no-cov` | 2 skipped；当前 shell 未开启 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1`，且缺少 Deucate 地址/密钥和真实 ASR 音频路径 |
| `ruff check src/sales_trainer tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `./.venv/bin/python -m compileall src/sales_trainer tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py` | 通过 |
| `npx vitest run 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.test.ts' 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' 'src/app/admin/sales-trainer/score-results/page.test.tsx' 'src/app/admin/sales-trainer/units/page.test.tsx' 'src/components/admin/sales-trainer/unit-form.test.tsx' 'src/components/layout/admin-shell.test.tsx' 'src/components/layout/admin-sidebar.test.tsx'` | 10 files passed，23 tests passed |
| `npx tsc --noEmit` | 通过 |
| `npx eslint 'src/app/admin/layout.tsx' 'src/app/(dashboard)/sales-trainer/**/*.{ts,tsx}' 'src/app/admin/sales-trainer/**/*.{ts,tsx}' 'src/components/admin/sales-trainer/**/*.{ts,tsx}' 'src/components/layout/admin-shell.tsx' 'src/components/layout/admin-sidebar.tsx' 'src/components/layout/admin-shell.test.tsx' 'src/components/layout/admin-sidebar.test.tsx' 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.ts' 'src/lib/api/client-domains.test.ts' 'src/lib/api/types.ts'` | 通过 |
| `npm run lint` | 通过，0 errors，83 warnings；warnings 分布在非 sales-trainer 页面/组件、coverage 文件及 `web/src/lib/api/client.ts` 的未使用类型导入 |
| `npx vitest run` | 初次失败：129 files passed，1 file failed；837 tests passed，36 failed，6 skipped。失败集中于 `src/app/(user)/exam/[sessionId]/page.test.tsx`，根因是 `api.practice.getRuntimePreflight` mock 缺失 |
| `npx vitest run 'src/app/(user)/exam/[sessionId]/page.test.tsx'` | 修复后通过：1 file passed，36 tests passed |
| `npx vitest run` | 修复后通过：130 files passed，873 tests passed，6 skipped |
| `npx tsc --noEmit` | 修复后通过 |
| `npm run lint` | 修复后通过，0 errors，83 warnings；warnings 均未阻断 lint |
| `./.venv/bin/python -m pytest --no-cov` | 未完成：运行中已观察到多个非 sales-trainer 失败，且在性能/外部依赖段长时间无输出；sales-trainer 相关用例在该全量运行中已通过/真实供应商 smoke 已跳过 |
| `./.venv/bin/python scripts/verify_sales_trainer_real_provider_config.py` | 退出码 2；当前环境缺少真实供应商联调所需配置，脚本明确列出缺少 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS`、`DEUCATE_BASE_URL`、`DEUCATE_API_KEY`、`SALES_TRAINER_REAL_ASR_AUDIO_PATH`，且未打印密钥值 |
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 2 passed |
| `ruff check scripts/verify_sales_trainer_real_provider_config.py tests/unit/test_sales_trainer_real_provider_config.py` | 通过 |
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py --no-cov` | 2 passed，2 skipped；真实供应商 smoke 仍因当前环境未开启/缺参跳过 |
| `./.venv/bin/python -m compileall scripts/verify_sales_trainer_real_provider_config.py tests/unit/test_sales_trainer_real_provider_config.py` | 通过 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 17 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `ruff check src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `./.venv/bin/python -m compileall src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py` | 通过 |
| `./.venv/bin/python scripts/verify_sales_trainer_real_provider_config.py --run-smoke` | 退出码 2；当前环境配置不完整，因此不会继续执行真实供应商 smoke，缺项输出不包含密钥值 |
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 3 passed |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 18 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 5 passed；覆盖缺配置、配置齐全、命令构造、`.env` 读取和 shell 覆盖优先级 |
| `./.venv/bin/python scripts/verify_sales_trainer_real_provider_config.py --run-smoke` | 退出码 2；当前 `backend/.env`/shell 配置仍不完整，因此不会继续执行真实供应商 smoke，缺项输出不包含密钥值 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 20 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `ruff check src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `./.venv/bin/python -m compileall src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py` | 通过 |
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 6 passed；新增覆盖安全 JSON 输出 |
| `./.venv/bin/python scripts/verify_sales_trainer_real_provider_config.py --json` | 退出码 2；输出 `ready=false`、缺项 `messages` 和 `checked_keys`，不包含密钥值 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 21 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `ruff check src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `./.venv/bin/python -m compileall src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py` | 通过 |
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 8 passed；新增覆盖 JSON 报告文件写入和 CLI `--json-report` 不泄露密钥值 |
| `./.venv/bin/python scripts/verify_sales_trainer_real_provider_config.py --json --json-report /private/tmp/sales-trainer-real-provider-preflight.json` | 退出码 2；stdout 和报告文件均输出 `ready=false`、缺项 `messages`、`checked_keys` 和 `smoke_command`，不包含密钥值 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 23 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `ruff check src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `./.venv/bin/python -m compileall src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py` | 通过 |

### 12.3 Goal 持续验收问题记录

#### 问题：学员录音上传页面测试未覆盖直传优先入口

- 发现时间：2026-05-28 17:39:22 CST
- 复现入口：`web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx`
- 复现步骤：运行销售训练前端专项测试 `npx vitest run ... src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx ...`
- 期望结果：学员录音上传页调用当前生产入口 `uploadAudioSubmissionDirect()`，并由 API facade 在 COS/OSS 场景走浏览器 PUT，在 local 场景 fallback multipart。
- 实际结果：测试仍 mock 旧 `uploadAudioSubmission()`，页面调用未 mock 的直传入口后触发真实认证错误，导致断言失败。
- 严重程度：主要级。自动化测试与真实上传链路脱节，会削弱“直传优先 + fallback 可用”的回归保护。
- 根因判断：前端页面已切换到 `uploadAudioSubmissionDirect()`，但测试仍停留在旧 multipart API 断言；API facade 也缺少直传优先和 local fallback 的组合测试。
- 修复方案：页面测试改为 mock `uploadAudioSubmissionDirect()`；补充 `web/src/lib/api/sales-trainer.test.ts` 覆盖 local fallback multipart 和 COS/OSS PUT 后注册。
- 修复状态：已修复。
- 回归验证结果：`npx vitest run 'src/lib/api/sales-trainer.test.ts' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx'` 通过，2 files passed，8 tests passed；`npx eslint 'src/lib/api/sales-trainer.test.ts' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx'` 通过。

#### 历史问题（2026-05-28）：本地后端数据库未升级到销售训练题库 scope migration

- 发现时间：2026-05-28 17:42:11 CST
- 复现入口：`http://localhost:3445/admin/sales-trainer/questions/categories`
- 复现步骤：使用浏览器打开销售训练题库分类页。
- 期望结果：分类页展示 `sales_trainer` 范围分类，默认分类可用于新建题目。
- 实际结果：页面提示“销售训练题目分类读取失败”，新建题目页分类下拉无可用分类。
- 严重程度：阻塞级。分类读取失败会阻断销售训练题库新建题目和训练单元绑定流程。
- 当时根因：3444 后端连接的本地数据库 Alembic 版本停留在 `20260528_1500_071`，尚未应用 `20260528_1600_072_sales_trainer_question_scope.py`，运行库缺少 `question_categories.usage_scope` / `question_items.usage_scope` 及默认销售训练分类。
- 当时修复：对该本地库执行 `./.venv/bin/alembic upgrade head` 并应用 `20260528_1600_072`。首发基线切换后，旧开发库不再原地升级，必须按 launch reset runbook 从空库重建到 `20260715_0000_001`。
- 修复状态：历史问题已关闭；当前由首发 baseline、单一 head 与 schema parity 测试覆盖。
- 回归验证结果：浏览器刷新分类页后展示“销售训练题库”和“Goal验收分类”，无错误提示；随后创建 `Goal验收单选题` 并发布成功。

#### 问题：未配置做题通过线时满分结果显示为“未通过”

- 发现时间：2026-05-28 17:52:30 CST
- 复现入口：`http://localhost:3445/sales-trainer/quiz/6ff4f124-ec0c-4cc2-abc0-4f15289d6d96`
- 复现步骤：创建并发布一个未配置 `quiz.pass_threshold` 的做题训练单元，学员选择正确答案并提交。
- 期望结果：未配置通过线时结果页只展示计分状态，不应把 `passed=null` 当成失败；如果配置通过线，再明确显示已通过/未通过。
- 实际结果：提交后总分 10、满分 10、单题正确，但结果徽标显示“未通过”。
- 严重程度：主要级。会误导学员和运营人员判断训练效果，属于核心结果展示语义错误。
- 根因判断：后端在无 `quiz.pass_threshold` 时返回 `passed=null`，符合“未配置则仅返回分数不判通过”的设计；前端结果页用 truthy 判断把 `null` 和 `false` 都渲染为“未通过”。
- 修复方案：前端结果页区分 `passed === true`、`passed === false` 和 `passed == null`，第三种显示“仅计分”；新增页面测试覆盖 `passed=null` 不显示“未通过”。
- 修复状态：已修复。
- 回归验证结果：浏览器刷新 `http://localhost:3445/sales-trainer/quiz/result/d28c6165-12ea-4ccd-a6dc-c59e87ab7841` 后显示“仅计分”、总分 10、满分 10、单题正确；`npx vitest run 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/lib/api/sales-trainer.test.ts'` 通过，3 files passed，9 tests passed；对应 ESLint 通过。

#### 问题：含待判简答题的做题结果仍显示为“仅计分”

- 发现时间：2026-05-28 18:13:10 CST
- 复现入口：`http://localhost:3445/sales-trainer/quiz/result/1986926a-e7ac-4a85-b4c1-b602eff40609`
- 复现步骤：创建并发布包含单选、多选、判断、简答的训练单元；学员提交答案，其中简答题当前不自动判分。
- 期望结果：如果任一答案仍待人工判定，或总分/满分尚未形成，结果页顶部应显示“待判分”，让学员知道结果还未完成。
- 实际结果：结果页总分和满分展示 `--`，简答题展示“待人工判定”，但顶部徽标仍显示“仅计分”。
- 严重程度：一般级。不会造成数据错误，但会让“未配置通过线”和“尚未完成判分”两种业务状态混淆，影响学员和后台人员理解结果。
- 根因判断：前端顶部徽标只根据 `passed` 判断；`passed=null` 同时覆盖“未配置通过线”和“尚未完成判分”，缺少对 `total_score`、`max_score` 以及答案级 `is_correct/score` 的判定。
- 修复方案：结果页先判断是否存在待判分状态；若总分/满分为空或任一答案未判定/无分数，则显示“待判分”；否则再按 `passed=true/false/null` 显示“已通过/未通过/仅计分”。
- 修复状态：已修复。
- 回归验证结果：浏览器刷新 `http://localhost:3445/sales-trainer/quiz/result/1986926a-e7ac-4a85-b4c1-b602eff40609` 后显示“待判分”，简答题显示“待人工判定”，无控制台错误；`npx vitest run 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx'` 通过，1 file passed，2 tests passed；`npx eslint 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.tsx' 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx'` 通过。

#### 问题：后台录音列表用户列只显示 UUID

- 发现时间：2026-05-28 18:17:20 CST
- 复现入口：`http://localhost:3445/admin/sales-trainer/audio-submissions`
- 复现步骤：完成一次录音上传、转写、评分后，进入后台“学员录音”列表。
- 期望结果：业务人员能直接看到学员姓名、邮箱和当前显式 Team，并保留 `user_id` 作为审计标识。
- 实际结果：“用户”列只显示裸 `user_id` UUID，业务人员需要额外查用户表才能知道是谁上传。
- 严重程度：一般级。功能可用但不够好用，影响后台查询和运营排查效率。
- 根因判断：`AudioSubmissionResponse` 只返回稳定外键 `user_id`，前端也直接渲染该字段，缺少面向后台人员的用户摘要字段。
- 修复方案：后端录音提交响应提供 `user_name`、`user_email` 与 Team 摘要；前端列表和详情页优先显示业务身份与 Team，并保留 `user_id` 小字审计，不再返回 `user_department`。
- 修复状态：已修复。
- 回归验证结果：浏览器刷新 `http://localhost:3445/admin/sales-trainer/audio-submissions` 后用户列显示 `Developer · dev@example.com`，下方保留 `user_id`；`./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py --no-cov` 通过，9 passed，1 warning；`npx eslint 'src/app/admin/sales-trainer/audio-submissions/page.tsx' 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx' 'src/lib/api/types.ts'` 通过；`npx tsc --noEmit --pretty false` 通过。

#### 问题：浏览器直传 COS 被 CORS 拦截时只显示 Failed to fetch

- 发现时间：2026-05-28 18:31:47 CST
- 复现入口：`http://localhost:3445/sales-trainer/audio/74100dac-d1b8-4ce7-971f-5ff34d3a1f6a`
- 复现步骤：使用真实浏览器文件控件选择 `.dev/browser-fixtures/hello_world_female2.wav`，点击“上传并开始评分”；随后查看网络请求。
- 期望结果：浏览器直传失败时应提示管理员/学员下一步动作，例如检查 COS/OSS CORS 配置或临时切换本地上传；网络层应能区分“已拿到预签名 URL”和“浏览器 PUT 被对象存储跨域策略拦截”。
- 实际结果：前端已成功调用 `POST /sales-trainer/audio-submissions/upload-url`，随后浏览器对 COS 预签名 URL 的 `PUT` 失败为 `net::ERR_FAILED`，页面只显示 `Failed to fetch`；同一预签名 PUT 通过非浏览器 curl smoke 可成功，说明问题集中在浏览器跨域直传配置。
- 严重程度：主要级。生产默认路径是浏览器直传 COS/OSS，如果 bucket CORS 未配置，学员上传会失败且原提示不可操作。
- 根因判断：前端 `uploadAudioSubmissionDirect()` 对 `fetch(uploadUrl, PUT)` 的网络异常没有做业务化错误映射，浏览器 CORS/网络失败会直接透出原生 `TypeError: Failed to fetch`。
- 修复方案：保留直传优先策略；在 PUT 抛出非 AbortError 时映射为“对象存储直传失败，请检查 COS/OSS 跨域 CORS 配置，或临时切换为本地上传。”，同时继续由 settings 页展示存储后端和直传启用状态。
- 修复状态：已修复前端提示；当前环境仍需运维配置 COS bucket CORS 后，浏览器 PUT 才会成功。
- 回归验证结果：Playwright 真实文件控件选择 `.dev/browser-fixtures/hello_world_female2.wav` 后，网络记录显示 `POST /sales-trainer/audio-submissions/upload-url` 返回 200、随后浏览器 `PUT https://...cos...` 失败为 `net::ERR_FAILED`；修复后页面显示“对象存储直传失败，请检查 COS/OSS 跨域 CORS 配置，或临时切换为本地上传。”；`npx vitest run 'src/lib/api/sales-trainer.test.ts'` 通过，1 file passed，8 tests passed；`npx eslint 'src/lib/api/client-domains.ts' 'src/lib/api/sales-trainer.test.ts'` 通过。

#### 问题：移动窄屏下销售题库表格被压缩折行

- 发现时间：2026-05-28 18:36:24 CST
- 复现入口：`http://localhost:3445/admin/sales-trainer/questions`
- 复现步骤：使用 Playwright 将视口调整为 `390x844`，打开后台销售题库页并截图。
- 期望结果：后台窄屏下表格应保持可扫描，列宽不应被压缩到分类文字竖向折行；必要时使用横向滚动承载管理表格。
- 实际结果：表格强制适配 390px 宽度，分类等列被挤压为竖向折行，操作列和状态列扫描困难。
- 严重程度：一般级。桌面后台主路径可用，但窄屏巡检不够好用。
- 根因判断：销售题库表格使用 `w-full`，外层 `GlassCard` 为 `overflow-hidden`，缺少横向滚动容器和最小表格宽度。
- 修复方案：为销售题库表格增加 `overflow-x-auto` 包裹层，并设置 `min-w-[760px]`，让窄屏通过横向滚动保持列结构。
- 修复状态：已修复。
- 回归验证结果：Playwright `390x844` 视口下重新打开销售题库并保存截图 `output/playwright/sales-trainer-admin-questions-mobile-after.png`，表格保持列宽并通过横向滚动承载；学员录音上传页截图 `output/playwright/sales-trainer-audio-upload-mobile.png` 未见明显遮挡；`npx eslint 'src/app/admin/sales-trainer/questions/page.tsx'` 通过。

#### 问题：训练单元绑定范围缺少直接回归测试

- 发现时间：2026-05-28 19:02:18 CST
- 复现入口：`backend/tests/unit/test_sales_trainer_services.py`
- 复现步骤：复核销售训练训练单元绑定测试覆盖，确认已有实现通过 `QuestionBankAdapter.get_published_questions()` 限定 `status=published` 且 `usage_scope=sales_trainer`，但自动化没有直接断言“通用题、草稿题、归档题不能绑定”。
- 期望结果：训练单元绑定边界应有直接测试，避免后续改动把通用题库或未发布题目误纳入销售训练单元。
- 实际结果：实现路径正确，但测试只覆盖了正向绑定和题型结构非法，没有把 scope/status 边界作为独立回归样例。
- 严重程度：一般级。当前功能未发现越权绑定，但缺少直接回归保护，后续维护容易漏。
- 根因判断：销售训练题库范围隔离是在适配层集中实现，早期测试更关注业务表单和题型结构，未把绑定边界单独参数化。
- 修复方案：补充 `test_should_reject_quiz_unit_binding_outside_published_sales_scope`，分别覆盖 `usage_scope=general`、`status=draft`、`status=archived`，期望统一返回 `[QUESTION_ITEM_NOT_FOUND_OR_UNPUBLISHED]`。
- 修复状态：已修复。
- 回归验证结果：`./.venv/bin/python -m pytest tests/unit/test_sales_trainer_services.py --no-cov` 通过，14 passed，1 warning；`./.venv/bin/ruff check tests/unit/test_sales_trainer_services.py` 通过；`git diff --check -- backend/tests/unit/test_sales_trainer_services.py docs/design/sales-trainer-system.md` 通过。

#### 问题：浏览器直传 PUT 被拦截后没有自动降级 multipart

- 发现时间：2026-05-28 19:18:42 CST
- 复现入口：`web/src/lib/api/client-domains.ts`
- 复现步骤：复核 `uploadAudioSubmissionDirect()`，确认当前只在 `storage_backend=local` 或 `upload_url=local://...` 时走 multipart fallback；当 COS/OSS 预签名 URL 已返回、但浏览器 `PUT` 被 CORS 或网络策略拦截时，函数直接抛出“对象存储直传失败”错误。
- 期望结果：生产默认路径仍优先尝试 `getAudioUploadUrl -> PUT COS/OSS -> registerAudioSubmission`；如果浏览器 PUT 因 CORS/网络层失败，应自动降级到现有 multipart 上传入口，让当前环境仍能完成录音上传、转写和评分闭环。
- 实际结果：当前环境 COS bucket CORS 未放行浏览器 PUT 时，学员上传停在错误提示，无法通过页面继续完成闭环；这不满足“直传 URL 不可用时仍 fallback 到 multipart”的验收要求。
- 严重程度：主要级。真实浏览器上传路径仍受环境 CORS 配置阻塞，影响学员端核心录音训练闭环。
- 根因判断：API facade 将对象存储网络异常视为终止错误，没有复用已存在的 multipart fallback 上传能力；页面层也没有二次 fallback。
- 修复方案：抽出统一 `buildAudioUploadFormData()`；`uploadAudioSubmissionDirect()` 在 local 预签名路径直接 fallback，在非 AbortError 的 PUT 网络异常时也自动调用 multipart 上传；如果 fallback 也失败，再追加说明“对象存储直传失败后已尝试后端中转上传但仍失败”，保证错误可操作且不隐藏真实失败阶段。
- 修复状态：已修复。
- 回归验证结果：Playwright CLI 真实文件控件上传 `.dev/browser-fixtures/hello_world_female2.wav` 后，网络记录显示 `POST /audio-submissions/upload-url` 200、浏览器 `PUT https://...cos...` 因 CORS 返回 `net::ERR_FAILED`、随后自动 `POST /audio-submissions/upload` 200 并进入学员结果页 `submission_id=5d719409-d19a-4ac8-b6cc-ea0f634a7623`；`npx vitest run 'src/lib/api/sales-trainer.test.ts' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx'` 通过，2 files passed，10 tests passed；`npx eslint 'src/lib/api/client-domains.ts' 'src/lib/api/sales-trainer.test.ts' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.tsx' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx'` 通过；`npx tsc --noEmit --pretty false` 通过。

#### 问题：录音评分失败页只显示错误码且把待重试误读为未通过

- 发现时间：2026-05-28 19:25:31 CST
- 复现入口：`http://localhost:3445/sales-trainer/audio/result/5d719409-d19a-4ac8-b6cc-ea0f634a7623`
- 复现步骤：真实浏览器上传 `.dev/browser-fixtures/hello_world_female2.wav`；前端先尝试 COS PUT，CORS 拦截后自动 fallback 到 multipart；后端上传、转写成功，Deucate 评分超时。
- 期望结果：处理失败时页面应说明下一步，例如“评分服务响应超时，请稍后刷新或联系管理员重试评分”；评分未完成时不应把通过状态显示为“否”。
- 实际结果：页面状态为 `scoring_failed`，只显示 `[DEUCATE_TIMEOUT]`，评分卡片里“通过”显示“否”，容易让学员误以为内容未通过，而不是评分服务未完成。
- 严重程度：主要级。录音训练主链路可以进入结果页，但失败态提示不够可操作，且语义误导学员。
- 根因判断：学员结果页直接渲染后端 `error_message`；评分卡片用 truthy 判断 `passed`，把 `null` 或错误态都渲染为“否”。
- 修复方案：为学员端录音结果页集中增加错误码说明映射；`[DEUCATE_TIMEOUT]` 显示“评分服务响应超时。转写已完成，请稍后刷新结果；如仍未恢复，请联系管理员在后台学员录音中重试评分。”；评分错误或 `passed=null` 时通过状态显示“待重试”或“--”，不再显示“否”。
- 修复状态：已修复。
- 回归验证结果：浏览器刷新 `http://localhost:3445/sales-trainer/audio/result/5d719409-d19a-4ac8-b6cc-ea0f634a7623` 后显示可操作说明“评分服务响应超时。转写已完成，请稍后刷新结果；如仍未恢复，请联系管理员在后台‘学员录音’中重试评分。”，评分卡片“通过”显示“待重试”，不再显示裸 `[DEUCATE_TIMEOUT]`；截图保存为 `output/playwright/sales-trainer-audio-result-timeout-guidance.png`；后台重试评分接口仍返回 `[DEUCATE_TIMEOUT]`，判断为当前 Deucate 上游响应超时/环境状态问题；`npx vitest run 'src/lib/api/sales-trainer.test.ts' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx'` 通过，3 files passed，12 tests passed；对应 ESLint 与 `npx tsc --noEmit --pretty false` 通过。

#### 问题：后台重试评分对 scoring_failed 提交没有真正重试

- 发现时间：2026-05-28 19:33:48 CST
- 复现入口：`POST /api/v1/admin/sales-trainer/audio-submissions/5d719409-d19a-4ac8-b6cc-ea0f634a7623/retry-scoring`
- 复现步骤：在真实浏览器上传后得到 `scoring_failed`、`[DEUCATE_TIMEOUT]` 的音频提交；调用后台重试评分接口；再查询评分结果列表。
- 期望结果：只要音频已有转写文本，管理员/培训负责人点击“重试评分”应重新进入 `audio_scoring_started`，再次调用评分服务，并新增或更新评分结果。
- 实际结果：接口快速返回原 `scoring_failed` 状态，评分结果列表仍只有原一条 `score_result`，没有新评分记录；服务层 `_score()` 在 `submission.status != "transcribed"` 时直接 return，导致 `retry_scoring()` 对 `scoring_failed` no-op。
- 严重程度：主要级。处理失败后的恢复入口不可用，会让一次 Deucate 超时变成无法从后台恢复的卡死状态。
- 根因判断：正常首次评分只允许从 `transcribed` 进入是合理状态机约束，但重试评分没有先把已有转写的失败提交恢复为可评分状态，也没有显式允许 `scoring_failed` 重试。
- 修复方案：`retry_scoring()` 先检查提交是否已有 transcript；若有，则将状态恢复为 `transcribed` 并清空提交级错误，再调用 `score_submission()`；若没有 transcript，则返回明确错误码，避免静默 no-op。补充单测覆盖失败后重试会再次调用评分 client。
- 修复状态：已修复。
- 回归验证结果：`./.venv/bin/python -m pytest tests/unit/test_sales_trainer_services.py --no-cov` 通过，15 passed，1 warning；`./.venv/bin/ruff check src/sales_trainer/services/audio_submission_service.py tests/unit/test_sales_trainer_services.py` 通过；`./.venv/bin/python -m compileall -q src/sales_trainer/services/audio_submission_service.py tests/unit/test_sales_trainer_services.py` 通过；重启本地 3444 后再次调用 `POST /retry-scoring`，接口实际等待约 31 秒并新增第二条评分结果，证明重试入口已重新调用评分服务；当前第二次结果仍为 `[DEUCATE_TIMEOUT]`。临时用 `DEUCATE_TIMEOUT_SECONDS=90` 启动本地服务后再次重试，超过 2 分钟仍未返回，已手动终止请求并恢复 3444 默认启动配置；判断为当前 Deucate 上游响应超时/环境状态问题，不再归因于重试入口代码。
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 9 passed；新增覆盖安全报告中的 `generated_at`、`env_file`、`smoke_requested`、`smoke_ran` 审计字段 |
| `./.venv/bin/python scripts/verify_sales_trainer_real_provider_config.py --json --json-report /private/tmp/sales-trainer-real-provider-preflight.json` | 退出码 2；stdout 和报告文件均输出 `ready=false`、缺项 `messages`、`checked_keys`、`smoke_command`、`generated_at`、`env_file`、`smoke_requested=false`、`smoke_ran=false`，不包含密钥值 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 24 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `ruff check src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py` | 通过 |
| `./.venv/bin/python -m compileall src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py` | 通过 |
| `git diff --check -- backend/scripts/verify_sales_trainer_real_provider_config.py backend/tests/unit/test_sales_trainer_real_provider_config.py docs/design/sales-trainer-system.md` | 通过 |
| `./.venv/bin/python -m pytest tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 25 passed，1 warning；覆盖 COS URL、Paraformer 参数/结果解析、COS 上传 URL、真实联调预检 |
| `./.venv/bin/python scripts/verify_sales_trainer_real_provider_config.py --json --json-report /private/tmp/sales-trainer-real-provider-preflight.json` | 退出码 2；当前环境缺少 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS`、`DEUCATE_BASE_URL`、`DEUCATE_API_KEY`、`SALES_TRAINER_ASR_MODE=file`、`SALES_TRAINER_REAL_ASR_AUDIO_URL`，stdout 和报告文件不包含密钥值 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 31 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `./.venv/bin/python -m compileall src/common/cos src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py` | 通过 |
| `uv lock` | 通过；新增 `cos-python-sdk-v5` 与其依赖 `xmltodict` 到 `backend/uv.lock` |
| `ruff check src/common/cos/signing.py src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/integration/test_sales_trainer_api.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `git diff --check -- backend/src/common/cos backend/src/sales_trainer/services backend/tests/unit/test_cos_signing_service.py backend/tests/unit/test_sales_trainer_paraformer_file_asr.py backend/tests/unit/test_sales_trainer_services.py backend/tests/unit/test_sales_trainer_real_provider_config.py backend/tests/integration/test_sales_trainer_real_providers.py backend/scripts/verify_sales_trainer_real_provider_config.py backend/.env.example backend/requirements.txt backend/pyproject.toml docs/design/sales-trainer-system.md` | 通过 |
| `./.venv/bin/python -m pytest tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py --no-cov` | 26 passed，1 warning；补充覆盖 COS 公开域名读 URL 无需 Secret 的路径 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 32 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `ruff check src/common/cos/signing.py src/sales_trainer scripts/verify_sales_trainer_real_provider_config.py tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/integration/test_sales_trainer_api.py tests/unit/common/test_alembic_migration_graph.py` | 通过 |
| `./.venv/bin/python -m pytest tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/test_sales_trainer_services.py --no-cov` | 24 passed，1 warning；覆盖默认 `fun-asr` 不传 `language_hints`、`paraformer-v2` 才传 `language_hints` |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 33 passed，2 skipped，2 warnings；skipped 为真实供应商 smoke 缺部署环境配置 |
| `ruff check src/sales_trainer/services/paraformer_file_asr.py tests/unit/test_sales_trainer_paraformer_file_asr.py scripts/verify_sales_trainer_real_provider_config.py` | 通过 |
| `./.venv/bin/python -m compileall src/sales_trainer/services/paraformer_file_asr.py` | 通过 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_cos_signing_service.py tests/unit/test_sales_trainer_real_provider_config.py tests/integration/test_sales_trainer_real_providers.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 38 passed，2 skipped，2 warnings；skipped 为受 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1` 保护的真实供应商测试 |
| `npx vitest run 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' 'src/app/admin/sales-trainer/score-results/page.test.tsx' 'src/app/admin/sales-trainer/units/page.test.tsx' 'src/components/admin/sales-trainer/unit-form.test.tsx' 'src/lib/api/sales-trainer.test.ts'` | 7 files passed，11 tests passed |
| `./.venv/bin/python -m compileall -q src/sales_trainer src/common/cos` | 通过 |
| `curl -sS http://127.0.0.1:3444/health` | 通过；`ready=true`，database check 为 `ok` |
| 真实 multipart 上传 smoke：`POST /api/v1/sales-trainer/audio-submissions/upload`，音频 `.dev/browser-fixtures/hello_world_female2.wav`，`auto_process=true` | 通过；返回 `success=true`，`submission_id=e69700b9-0b8e-4790-92d0-158288447aa0`，`status=scored`，`transcript_provider=dashscope-paraformer-file`，`score_model=deepseek-v4-flash`，`total_score=30.0`，无 error code |
| 数据库落库检查：查询 `alembic_version`、submission、transcript、score result | 通过；`alembic_version=20260528_1500_071`，`storage_key=cos://...`，`source_page=sales_trainer_audio_upload`，`transcript_snapshot` 与转写文本一致，raw payload 不含 COS/DashScope 签名查询参数 |
| Browser 截图巡检：`/.dev/browser-screenshots/01-login.png`、`02-home-after-login.png`、`04-audio-upload-page.png` | 已完成登录页、首页和销售训练录音上传页巡检；后续改用 `chrome-devtools` 时工具通道返回 `Transport closed`，未能继续用该工具补图 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/test_cos_signing_service.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 2026-05-28 收口复跑通过，45 passed，2 skipped，2 warnings；skipped 为受 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1` 保护的真实供应商测试 |
| `npx vitest run 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx' 'src/app/admin/sales-trainer/units/page.test.tsx' 'src/components/admin/sales-trainer/unit-form.test.tsx' 'src/app/admin/sales-trainer/score-results/page.test.tsx' 'src/lib/api/sales-trainer.test.ts' 'src/components/layout/admin-sidebar.test.tsx'` | 2026-05-28 收口复跑通过，9 files passed，18 tests passed |
| `npx eslint 'src/app/(dashboard)/sales-trainer/**/*.{ts,tsx}' 'src/app/admin/sales-trainer/**/*.{ts,tsx}' 'src/components/admin/sales-trainer/**/*.{ts,tsx}' 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.ts' 'src/components/layout/admin-sidebar.tsx' 'src/components/layout/admin-sidebar.test.tsx'` | 2026-05-28 收口复跑通过 |
| `npx tsc --noEmit` | 2026-05-28 收口复跑通过 |
| `npx vitest run 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx' 'src/app/admin/sales-trainer/units/page.test.tsx' 'src/components/admin/sales-trainer/unit-form.test.tsx' 'src/app/admin/sales-trainer/score-results/page.test.tsx' 'src/lib/api/sales-trainer.test.ts' 'src/components/layout/admin-sidebar.test.tsx'` | 2026-05-28 fallback 与失败态提示修复后复跑通过，9 files passed，20 tests passed |
| `npx eslint 'src/app/(dashboard)/sales-trainer/**/*.{ts,tsx}' 'src/app/admin/sales-trainer/**/*.{ts,tsx}' 'src/components/admin/sales-trainer/**/*.{ts,tsx}' 'src/lib/api/sales-trainer.test.ts' 'src/lib/api/client-domains.ts' 'src/components/layout/admin-sidebar.tsx' 'src/components/layout/admin-sidebar.test.tsx'` | 2026-05-28 fallback 与失败态提示修复后复跑通过 |
| `./.venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/test_cos_signing_service.py tests/unit/common/test_alembic_migration_graph.py --no-cov` | 2026-05-28 重试评分修复后复跑通过，46 passed，2 skipped，2 warnings；skipped 为受 `SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1` 保护的真实供应商测试 |
| `./.venv/bin/ruff check src/sales_trainer tests/integration/test_sales_trainer_api.py tests/integration/test_sales_trainer_real_providers.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_paraformer_file_asr.py tests/unit/test_sales_trainer_real_provider_config.py tests/unit/test_cos_signing_service.py tests/unit/common/test_alembic_migration_graph.py` | 2026-05-28 重试评分修复后复跑通过 |
| 浏览器访问 `/admin/sales-trainer/score-prompts` | 2026-05-28 收口复核通过；旧路由跳转到 `/admin/sales-trainer/score-standards`，侧栏和页面主标题使用“录音评分标准” |
| `GET /api/v1/admin/sales-trainer/settings` | 2026-05-28 收口复核通过；响应只包含 configured 布尔值、模式、模型和上传限制字段，扫描未出现 `api_key`、`secret_key`、`access_key`、`password`、`bearer` 等密钥信号 |
| `GET /api/v1/sales-trainer/units` | 2026-05-28 收口复核通过；学员端训练单元题目只返回 `question_id/title/stem/question_type/points/order_index/options` 等必要字段，未返回 `correct_answer`、`correct_answers`、`correct_bool`、`scoring_criteria`、`reference_answer`、`usage_scope` 等后台字段 |

---

## 十三、后续待确认

1. Deucate 当前已通过 OpenAI-compatible HTTP 客户端完成真实评分；后续若有官方 SDK 或统一模型配置中心，需要把 `HttpDeucateClient` 迁移到统一客户端，不改变评分服务契约。
2. 当前题库是否已经有单选、多选、判断题的选项和答案结构；如果没有，P0 只启用当前可用题型。
3. 当前生产文件存储已按腾讯云 COS 私有桶路径跑通；部署时仍需确认 bucket 权限策略、签名 URL 有效期、对象生命周期清理和是否需要后台手动清理失败上传对象。
4. 当前 ASR 已切到 DashScope 录音文件识别；长音频仍需用真实销售录音验证队列耗时、说话人分离、时间戳校准和超时策略，但不改变“业务上不限制固定时长”的要求。
