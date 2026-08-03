# 新人销售基础训练 API v2 目标合同

> 状态：Foundation 学员运行时、五类 Activity、持久任务和 ReleasePlan 已实现；2026-07-20 复核重新打开管理员 Authoring 合同。以下标为“目标 Authoring”的端点在进入运行时 OpenAPI 前不得宣称已实现，Seed/路由/资源 options 不能代替 CRUD 证据。

## 1. 命名空间与协议

- 学员：`/api/v1/newcomer-training/**`
- 管理：`/api/v1/admin/newcomer-training/**`
- JSON 字段使用 `snake_case`；时间为带时区 ISO 8601；ID 是 opaque string。
- 浏览器使用 HttpOnly session cookie；非浏览器可用 Bearer。所有授权以后端 capability + organization/object scope 为准。
- 写命令必须携带 `Idempotency-Key`；乐观锁资源使用 `If-Match: W/"<version>"`。同键不同请求返回 409。
- 列表统一 `page`（从 1 开始）、`page_size`（默认 20、最大 100）、稳定 `sort` 和资源专属 allowlist filter；响应含 `items,total,page,page_size,has_more`。

成功：

```json
{"success":true,"data":{},"trace_id":"..."}
```

失败：

```json
{"success":false,"error":"[ERROR_CODE]","message":"用户可理解且可恢复的说明","details":{},"trace_id":"..."}
```

错误矩阵：401 未认证；403 capability 拒绝；404 对象不存在或超出 organization/object scope，且不泄露对象存在性；409 幂等键复用或状态冲突；412 ETag/version 冲突；422 Schema/业务校验；429 限流；503 capability/provider 暂不可用。5xx 不回传异常文本。

### 1.1 列表查询、筛选与排序 allowlist

`sort` 使用 `field` 升序、`-field` 降序；所有排序最后追加 opaque `object_id` 作为稳定 tie-breaker。未知 filter/sort、重复互斥 filter、非法日期范围返回 422 `[QUERY_PARAMETER_INVALID]`，不得静默忽略。权限 scope 在 filter 前由后端施加，不能通过 filter 扩大组织/Team 范围。

| 列表端点 | Filter allowlist | Sort allowlist（首项为默认） |
|---|---|---|
| 学员 `GET /history` | `activity_type`、`outcome_status`、`completed_from`、`completed_to` | `-completed_at`、`completed_at`、`activity_title` |
| 学员 `GET /notifications` | `read_state`、`notification_type`、`created_from` | `-created_at`、`created_at` |
| 管理 `GET /paths` | `status`、`search` | `-updated_at`、`updated_at`、`title` |
| 管理 `GET /cohorts` | `status`、`path_id`、`path_revision_id`、`search` | `-created_at`、`start_at`、`name` |
| 管理 `GET /learners` | `team_id`、`cohort_id`、`enrollment_status`、`dossier_status`、`queue_reason`、`risk_band`、`search` | `due_at`、`-risk_band`、`-updated_at`、`learner_name` |
| 管理 `GET /reviews` | `team_id`、`review_status`、`queue_reason`、`risk_band`、`due_before`、`search` | `due_at`、`-risk_band`、`-updated_at` |
| 管理 `GET /resources` | `resource_type`（必填）、`status`、`search` | `-updated_at`、`updated_at`、`title` |
| 管理 `GET /question-candidates` | `status`、`batch_id`、`source_revision_id`、`question_type`、`risk_level`、`search` | `-created_at`、`risk_level`、`status` |

日期过滤为含起点、不含终点的 UTC 区间。多值枚举使用重复 query key 并按 OR 处理，不接受自由 SQL 字段名或任意 JSON path。每个端点的 OpenAPI 参数、服务查询对象和前端 Query 类型必须由同一 allowlist contract test 锁定。

### 1.2 当前已挂载边界

学员端挂载：`GET /journey`、`GET /activities/{activity_id}`、`POST /activities/{activity_id}/commands`、`GET /notifications`、`GET /tasks`、`GET /tasks/{task_id}`、`POST /tasks/{task_id}/commands/request-cancel`、本地开发存储使用的 `PUT /audio-upload-sessions/{upload_session_id}/parts/{part_number}/content`，以及授权试听 `GET /audio-artifacts/{artifact_id}/playback`。Journey 和 Workspace 的 GET 不写数据库；直接访问 Workspace 仍由后端复核 Enrollment、Stage 进入条件和 Activity 前置条件。通知与任务列表只投影本人业务对象，通知链接回正式 Activity、Dossier 或 Task 结果位置，不复制正式结果。

管理端已挂载统一能力投影与工作台、Path/Cohort/Enrollment、`GET /learners` 与 `GET /learners/{learner_id}` 的 v2 Journey 管理投影、学习资源、题目生成与人工审核、录音处理、Coach 人工帮助、Readiness 复核，以及 `ReleasePlan` 预览、原子发布和回滚。管理 UI 入口统一为 `/admin/newcomer-training`，但各领域状态仍由其公开应用服务持有；工作台不建立跨域 ORM 写入或第二套状态机。学员列表按组织/Team 对象范围在服务端分页和搜索，并以批量 Attempt/Outcome 查询复用 Journey 投影规则，不恢复 Legacy Journey 表或第二套进度算法。

当前 Readiness 队列支持 `state`、`cohort_id`、`competency_key`、`reviewer_id`、`waiting_hours_gte`、`limit`、`offset`，并固定按风险降序、等待时间降序返回。统一工作台的路径、班级、资源、候选题和任务队列各自使用下文已挂载的服务端筛选合同；消费者不得发送未声明的自由查询字段。

## 2. 学员资源与命令

| 方法 | 路径 | 语义 | 权限/并发 |
|---|---|---|---|
| GET | `/journey` | 当前 Enrollment 的 `JourneyProjectionV1` | 仅本人；无 Enrollment 返回明确未分配状态，不自动报名 |
| GET | `/activities/{activity_id}` | `ActivityWorkspaceV1` | 本人 + Enrollment revision 内活动 |
| POST | `/activities/{activity_id}/commands` | 统一执行有类型命令，返回 Attempt/Task/Outcome 引用 | `Idempotency-Key`；命令 Schema 由活动联合决定 |
| GET | `/tasks` | 本人持久任务列表与恢复入口 | 仅本人；服务端分页；不暴露内部任务类型、Lease 或 Provider payload |
| GET | `/tasks/{task_id}` | `TaskStatusV1` | 业务对象本人或获授权管理者 |
| POST | `/tasks/{task_id}/commands/request-cancel` | 协作式取消 | 幂等；终态返回当前结果 |
| PUT | `/audio-upload-sessions/{upload_session_id}/parts/{part_number}/content` | 仅本地存储环境接收一个已声明分片；云存储环境拒绝并要求使用签名直传 URL | 本人 + upload ownership；`X-Audio-Sha256`；流式写入，不把整文件读入 API 内存 |
| GET | `/audio-artifacts/{artifact_id}/playback` | 本地返回文件，云存储返回 5 分钟签名 URL 重定向 | 本人 + organization/object scope；成功、失败和拒绝均留访问审计 |
| GET | `/history` | 分页历史 Outcome 摘要 | 仅本人 |
| GET | `/notifications` | 分页持久通知 | 仅本人 |
| GET | `/dossier` | `EvidenceDossierV1` 学员安全投影 | 仅本人，不含内部诊断/他人校准 |
| POST | `/dossier/appeals` | 提交申诉 | 幂等；冻结目标 evidence/decision version |

`ActivityCommandV1` 公共字段为 `command_type`、`attempt_id?`、`expected_attempt_version?`、`payload`。`payload` 是按活动/命令封闭的 discriminated union；未知命令或字段拒绝。技术重试复用同一 Idempotency-Key，学习重试使用明确 `start_new_attempt` 命令和新键。

首发 `assignment` 的 runner/command union 只表达三段异步客户场景录音：固定三个 segment identity、每段目标/时限、上传/处理任务引用和分段 Outcome；不接受通用文本、任意文件或自由 homework 配置。

Slice 3 的录音命令联合为：

- `start`：冻结当前 Enrollment 的 PathRevision、材料/场景、评分方案、30 分钟/100MB 上限和允许录制方式；
- `create_upload_session`：提交 `segment_id`、录制方式、文件名、媒体类型、声明大小/时长、manifest hash 和分片清单；
- `confirm_upload_part`：服务端 HEAD 校验后登记一个分片的编号、大小和 SHA-256；
- `finalize_upload`：确认全部分片已登记后立即排入持久任务；Worker 再次 HEAD/物化并校验总大小、完整 hash 与组织所有权，上传请求不等待 ASR/评分；
- `retry_stage`：只重试当前失败的 `validation | normalization | transcription | scoring | reconciliation` 阶段，不新建上传；
- `cancel`：结束当前录音 Run；已上传内容按保留策略处理，本地草稿由学员明确删除或退出登录清理。

上传会话状态为 `uploading | finalized | cancelled | expired`。过期/取消会话不产生正式 Submission 结果；运维批任务在数据库外删除其对象分片，并以 fenced cleanup claim 防止并发重复执行。正式处理状态对学员只投影为“校验录音、准备音频、转写录音、分析表现、保存结果”；不得返回内部 Task 类型、Provider payload 或 Prompt。

本地开发存储与云对象存储使用同一 UploadSession/Part 合同，但传输面不同：本地签名结果指向上述受权限保护的流式 `PUT` 路由；OSS/COS 签名结果指向对象存储，浏览器携带服务端返回的 allowlist headers 直接上传。云环境不接受把文件再转发到本地 `PUT` 路由。无论哪种存储，`confirm_upload_part` 和 Worker 都会从服务端重新读取对象 metadata；客户端声明、上传回调和对象 key 都不能单独作为完成依据。

Slice 4 的 `ai_coach` 命令联合为：

- `start`：冻结 ProfileRevision、三个 checkpoint、卡片白名单、掌握/补练策略、Context references、Prompt 与模型路由修订，并排入卡片生成任务；
- `submit_coach_answer`：携带 `card_id`、`client_token` 和有类型 `answer`；先持久化原回答，再由规则评分或排入语言评估任务；
- `continue_coach`：在反馈后进入下一卡、检查点或最多两轮针对性补练；超过上限不再排任务；
- `retry_coach`：从已持久化的 `card_generation | answer_evaluation` 失败阶段重试；
- `request_coach_assistance`：请求 `explain | example`，结果持久化但不改变正式 Coach 状态；
- `cancel`：协作取消在途任务并保留回答、卡片、反馈和血缘历史。

Coach Workspace 的阈值、补练上限、checkpoint、来源、薄弱点、当前卡、正式反馈和可用命令全部来自后端快照。`TaskStatusV1.result_location` 指向 `/api/v1/newcomer-training/activities/{activity_id}`。未知 card type、任意 HTML/脚本、越界来源或非法 AI Schema fail closed；Provider/Schema 失败必须投影 `failed_recoverable` 且 `answer_preserved=true`。

## 3. 管理资源与命令

| 方法 | 路径 | 语义 | 核心控制 |
|---|---|---|---|
| GET | `/capabilities` | 当前管理者的安全能力投影与权限帮助 | 服务端 capability + organization scope；前端不得从角色名推断 |
| GET | `/workspace` | 统一管理首页的可行动队列与导航投影 | 无权限区域不查询敏感数据，不伪装为空列表 |
| GET | `/paths/{path_id}/workspace` | 路径编辑器的三栏工作对象投影 | exact working/published revision + capability |
| GET | `/cohorts/{cohort_id}/workspace` | Cohort、Enrollment 和进度工作对象投影 | organization/object scope |
| GET | `/assessment-tasks` | 评测持久任务运营队列 | Task capability/action flags 与命令权限同源 |
| GET | `/audits` | 新人训练治理审计投影 | System/Training 管理能力；敏感字段脱敏 |
| GET/POST | `/paths` | 路径列表/创建 Path | Training Admin；创建幂等 |
| GET | `/paths/{path_id}` | Path 与 working/published revision 摘要 | capability projection |
| PUT | `/paths/{path_id}/working-revision` | 保存 Stage/ActivityDefinition | `If-Match`；未知字段拒绝 |
| POST | `/paths/{path_id}/commands/validate` | 只读校验 working revision | 不发布、不改 Enrollment |
| POST | `/release-plans/preview` | 为 exact working PathRevision 创建持久 `ReleasePlan` 并冻结依赖、校验和影响 | `Idempotency-Key` + reason；不改变 active 指针 |
| GET | `/release-plans` | 按 Path 查看发布计划、阻塞、依赖、影响和历史 | organization/object scope；稳定顺序 |
| POST | `/release-plans/{release_plan_id}/commands/publish` | 原子发布完整依赖闭包并激活计划 | preview token + impact hash + `If-Match` + 幂等 + audit |
| POST | `/release-plans/{release_plan_id}/rollback-preview` | 预览重新激活已知稳定计划的影响 | reason；只创建短期预览，不改 active 指针 |
| POST | `/release-plans/{release_plan_id}/commands/rollback` | 确认回滚 active 指针 | preview token + impact hash + `If-Match` + 幂等 + audit |
| GET/POST | `/cohorts` | 分页 Cohort / 创建并绑定 published PathRevision | Training Admin |
| POST | `/cohorts/{cohort_id}/commands/change-status` | `active/paused/cancelled` 显式状态流转 | `If-Match` + reason + 幂等 + audit |
| POST | `/cohorts/{cohort_id}/enrollment-imports/preview` | 预览 learner ID/email 批量报名 | 不写 Enrollment；逐项报告可执行/拒绝原因 |
| POST | `/enrollment-imports/commands/confirm` | 按冻结预览执行批量报名 | preview token + impact hash + 幂等；允许真实 partial success |
| GET | `/learners` | `AdminQueueV1` 学员队列 | 服务端筛选/分页；Team/organization scope |
| POST | `/enrollments/{enrollment_id}/revision-migrations/preview` | 迁移差异与影响预览 | 不写数据 |
| POST | `/enrollments/{enrollment_id}/commands/migrate-revision` | 显式迁移冻结修订 | preview token + impact hash + If-Match + reason |
| POST | `/enrollment-revision-migrations/preview` | 多 Enrollment 修订迁移预览 | 服务端逐项鉴权与冲突检查 |
| POST | `/enrollment-revision-migrations/commands/confirm` | 确认批量修订迁移 | preview token + impact hash + reason + 幂等 |
| GET | `/reviews` | `AdminQueueV1` 复核队列 | Training Manager 仅负责范围 |
| GET | `/reviews/{dossier_id}` | `EvidenceDossierV1` 管理投影 | 对象级权限 |
| POST | `/reviews/{dossier_id}/commands/preview-exception` | 冻结例外批准影响 | If-Match、幂等；返回短期 preview token + impact hash，不授予结论 |
| POST | `/reviews/{dossier_id}/commands/record-decision` | 人工决定 | If-Match、reason；例外需 preview/confirm |
| POST | `/reviews/{dossier_id}/commands/assign-retraining` | 在档案内创建补练并绑定证据 | 幂等、审计 |
| POST | `/reviews/{dossier_id}/rebuild` | 从不可变 Outcome/Evidence 重建当前 Snapshot | System Admin；旧 Snapshot/Decision 保留 |
| POST | `/appeals/{appeal_id}/commands` | 受理、请求重评、重开、解决或驳回申诉 | Training Manager；expected version、审计 |
| POST | `/calibration-sessions` | 保存校准样本、决定分布、分歧和行动项 | Training Manager；不自动改写人工决定 |
| POST | `/reviews/{dossier_id}/ai-summaries` | 保存经过 Schema 和 Evidence 引用校验的辅助摘要结果 | 失败不阻塞人工复核 |
| POST | `/evidence/{evidence_id}/invalidation` | 追加 Evidence 失效事件并重投影 Dossier | System Admin；幂等、对象范围、审计 |
| GET | `/reviews/{dossier_id}/export` | 带水印导出管理投影 | System Admin；对象范围、审计 |
| GET | `/resources` | 按类型搜索可绑定已发布修订 | Content/Training capability |
| POST | `/resources/{resource_type}` | 创建逻辑资源与首个 working revision | 幂等；`resource_type` 为封闭联合；就地创建后返回可绑定引用 |
| POST | `/resources/source_document/uploads` | 保存原始文件、创建 pending Source working revision 并排入持久解析任务 | multipart allowlist、签名/hash 校验、幂等；返回持久 Task/result location |
| GET | `/resources/{resource_type}/{resource_id}` | 资源与 working/published revision 摘要 | 对象范围；不返回 Provider secret/raw AI |
| PUT | `/resources/{resource_type}/{resource_id}/working-revision` | 保存有类型 working revision | `If-Match`；未知字段拒绝；published revision 不原地改 |
| GET/POST | `/source-revisions/{revision_id}/anchors` | 查看或就地创建 Source Anchor | 仅 parsed-ready current working 或 published Source；组织范围 |
| POST | `/resources/{resource_type}/{resource_id}/commands/validate` | 校验 working revision | 不发布；返回结构化 object/field issue |
| POST | `/resources/{resource_type}/{resource_id}/commands/archive` | 归档已发布逻辑资源 | `If-Match` + reason；被 Path/Attempt 引用的历史修订保留 |
| GET | `/question-generation-options` | 返回可选的已发布 Source/Unit 和安全 Prompt/模型策略标签 | 不返回 Prompt 正文、Provider/model payload 或可伪造 contract hash |
| GET/POST | `/question-generation-batches` | 查看持久批次或从安全选择创建生成任务 | 服务端严格编译已发布 Prompt 并冻结 contract hash；返回 Task/result location |
| GET | `/question-candidates` | 候选题审核队列 | Content/Training capability + 组织范围 |
| POST | `/question-candidates/bulk-review/preview` | 预览批量批准/拒绝的逐项影响 | reason；不改变候选题状态 |
| POST | `/question-candidates/bulk-review/commands/confirm` | 确认冻结的批量审核 | preview token + impact hash + 幂等；真实 partial success |
| POST | `/question-candidates/{candidate_id}/commands/{begin-review,approve,reject,supersede}` | 候选题人工审核状态机 | `If-Match`；红线/AI 简答题要求 Training Admin capability |
| GET | `/audio-assessments/queue` | 录音处理/失败/待人工处理队列 | `newcomer.audio.review`；组织范围；不含 Provider raw payload |
| POST | `/audio-submissions/{submission_id}/commands/repair` | 从 `failed_recoverable` 或 `reconciling` 的精确失败阶段重放 | `newcomer.audio.review` + reason + `Idempotency-Key`；留审计 |
| POST | `/audio-submissions/{submission_id}/transcript-correction/preview` | 预览更正与评分影响 | `newcomer.audio.transcript.correct`；创建短期 preview，不写 TranscriptRevision |
| POST | `/audio-submissions/{submission_id}/transcript-correction/confirm` | 追加 TranscriptRevision 并排入重评 | preview token + impact hash + reason + `Idempotency-Key` |
| POST | `/audio-submissions/{submission_id}/regrade/preview` | 预览重评或重新转写的目标合同与影响 | `newcomer.audio.regrade`；不覆盖历史版本 |
| POST | `/audio-submissions/{submission_id}/regrade/confirm` | 排入重评/重转写并追加 ScoreOutcomeVersion | preview token + impact hash + reason + `Idempotency-Key` |
| POST | `/audio-submissions/{submission_id}/invalidation/preview` | 预览结果失效影响 | `newcomer.audio.review` + reason |
| POST | `/audio-submissions/{submission_id}/invalidation/confirm` | 失效当前音频结果，保留历史血缘 | preview token + impact hash + reason + `Idempotency-Key` |
| GET | `/coach-sessions/help-queue` | 需要人工帮助的 Coach Session 队列 | `newcomer.coach.review`；组织范围 |
| GET | `/coach-sessions/{session_id}/help-detail` | 回答、卡片、来源、失败/补练历史与追加式人工指导 | capability + 组织范围；跨组织隐藏 404 |
| POST | `/coach-sessions/{session_id}/commands/intervene` | 追加指导、指派学习/录音/重做 Coach 或无需继续 | `If-Match` + `Idempotency-Key` + reason；不改写学员/AI 历史 |
| POST | `/quiz-attempts/{attempt_id}/regrades/preview` | 预览目标 QuizRevision/评分合同与影响 | Regrade capability；只读、不写版本 |
| POST | `/quiz-attempts/{attempt_id}/commands/regrade` | 追加 Outcome/评分版本并触发档案 stale/rebuild | preview token + impact hash + If-Match + reason |
| GET | `/diagnostics` | capability health、任务与 Provider 状态 | System Admin；脱敏、审计 |

`resource_type` 目标 Authoring 联合为 `source_document`、`learning_unit`、`question`、`quiz`、`audio_material`、`scoring_scheme`、`coach_profile`、`scenario`。`prompt` 不属于普通训练资源联合，由 AI 治理端口单独授权；评分/Coach/场景只能引用其已发布 exact revision。当前运行时通用 CRUD 主要覆盖学习域资源，binding options 虽已列出 `audio_material`、`scoring_scheme`、`scenario`、`coach_profile`，但“能列出/绑定 Seed”不等于管理员可新建、保存、比较、归档这些资源。

### 3.1 目标 Authoring 最小闭环

下表是后续切片必须进入领域应用服务和运行时 OpenAPI 的目标合同；在对应端点实际挂载前，状态均为 reopened/planned。

| 领域资源 | List/Search | Create / Get | Working revision | Validate / Compare / Impact | Archive | Release ref |
|---|---|---|---|---|---|---|
| `source_document`、`learning_unit`、`question`、`quiz` | `GET /resources?resource_type=...` | `POST/GET /resources/{type}[/{id}]` | `PUT /resources/{type}/{id}/working-revision` | `/commands/validate`、`/revisions/compare`、`/references` | `/commands/archive` | exact revision 进入 ReleasePlan |
| `audio_material`、`scoring_scheme`、`scenario` | 同一安全查询投影，内部调用 `audio_assessment` authoring port | 同上；不得由路由直接拼 ORM/JSON | 有类型 snapshot + `If-Match` | 领域 Schema、来源/评分/AI 合同与引用影响 | 保留历史 Submission/Attempt | exact revision 进入 ReleasePlan |
| `coach_profile` | 同一安全查询投影，内部调用 `ai_coach` authoring port | 同上；可从受治理模板复制 | 有类型 checkpoint/card/source/policy snapshot | Preview 不写正式 Session/Evidence | 保留历史 Session/Outcome | exact revision 进入 ReleasePlan |

快速新建成功必须返回：`resource_id`、`working_revision_id`、`revision_no`、`status`、`validation_state`、`next_action`、`capabilities`；失败保留客户端输入和 Path 上下文。浏览器不得提交或拼接 storage key、raw snapshot、Prompt 正文、Provider payload 或 contract hash。

统一错误语义：不存在或跨组织不可见为 404；capability 拒绝为 403；状态、幂等键复用或被引用冲突为 409；`If-Match` 版本冲突为 412；Schema/领域校验为 422；限流为 429；解析、AI 或 Provider 能力暂不可用为 503。具体错误码保持 `LEARNING_*`、`AUDIO_*`、`COACH_*`、`NEWCOMER_*` 的领域前缀，管理聚合层不得发明第二套状态机。

Slice 2 曾使用的两个临时直发墓碑 `POST /path-revisions/{revision_id}/commands/publish` 与 `POST /resources/{resource_type}/{resource_id}/commands/publish` 已在消费者与 OpenAPI inventory 通过后删除。正式发布只能走 `ReleasePlan`；不得恢复直发、转发或双写语义。

### 3.2 写命令审计合同

所有成功写命令与被权限/状态/版本规则拒绝的高风险写命令都进入审计真源；业务写、成功审计和 Outbox 同事务。公共审计字段为 `organization_id`、`actor_id`、`capability`、`object_type/object_id`、`command`、`before_version/after_version`、`idempotency_key_hash`（不记录原键）、`expected_version/actual_version`、`reason?`、`preview_token_hash?`、`impact_hash?`、`trace_id`、`result`、`occurred_at`；不得记录 Prompt 正文、完整转写、原始模型输出、音频或 token。

| 写端点/命令族 | 必须审计 | 失败/重试断言 |
|---|---|---|
| 学员 `/activities/{activity_id}/commands` | Activity/Attempt command、冻结 revision refs、Outcome/Task ref | 同键重试只有一份业务结果；不同 payload 为 409 |
| 学员 `/tasks/{task_id}/commands/request-cancel` | cancel requested/acknowledged 或 terminal no-op | 无权限/跨对象拒绝；终态重复请求返回原结果 |
| 学员 `/dossier/appeals` | appeal、目标 evidence/decision/dossier version | 重复提交不新建 Appeal；版本失效为 412 |
| 管理 Path working revision/validate | before/after revision、结构化 issues | validate 不改发布指针；ETag 冲突无写入 |
| 管理 ReleasePlan validate/publish/cancel | dependency set、preview/impact hash、确认与发布结果 | 过期 preview/不同 hash 拒绝；原子发布无部分成功 |
| 管理 Cohort/Enrollment 创建与迁移 | Cohort binding、from/to revision、影响 Attempt | preview/version 失败无写；迁移事件与审计同事务 |
| 管理 ReviewDecision/补练 | dossier/evidence version、决定/补练引用、例外确认 | AI/系统身份不可授予；重复命令不覆盖旧决定 |
| Transcript correction/regrade | old/new revision/version、lineage、影响 dossier | 只追加不覆盖；相同 run 键不重复评分 |

只读 preview/validate 可记录操作日志但不得伪造 `StateTransitionAudited`；最终 confirm 必须引用相同未过期 preview/impact hash。HTTP 5xx 不能宣称命令失败或成功，客户端以原幂等键查询/重试确认。

### 3.3 Slice 2 学习 AI 合同

- 题目生成任务类型：`learning.question_generation.generate`；Schema 为 `question-generation-input-v1` / `question-generation-output-v1`。
- 短答评分任务类型：`learning.quiz.short_answer_score`；Schema 为 `short-answer-input-v1` / `short-answer-output-v1`。
- `prompt_contract_hash` 必须是 `sha256:<64 个小写十六进制字符>`，并与已发布 PromptRevision 的严格编译结果完全一致。
- 题目生成输入必须包含完整的已发布 `LearningUnitRevisionDraft`、`source_revision_id`、`learning_unit_revision_id`、请求数量和至少一个来源 Anchor；不得只传任意字典或对象 ID 后让 Provider 自行读取业务库。
- 短答输入必须包含冻结的题干、参考答案、rubric、分值和学员答案。学员答案是受治理的业务输入，不写入日志、错误消息或公开任务状态。
- Provider 只接收编译后的已发布 Prompt 文本；应用组合根不得追加未版本化 system instruction。输出必须是严格 JSON，并再次通过注册的输出 Schema 校验后才能进入 Candidate 或评分结果。
- Provider 超时、限流、连接失败、空响应或无效 JSON 都保持为可追踪失败/重试状态；短答 Attempt 不得因此被记为零分、通过或完成。

### 3.4 Slice 3 录音 ASR 与评分 AI 合同

- 完整文件 ASR 使用业务目的 `foundation_audio_transcription`、模型路由 `foundation-audio-asr` / `foundation-audio-asr-v1`、Schema `audio-transcript-input-v1` / `audio-transcript-output-v1`。ASR 输入只包含受控 `artifact://` 引用和冻结语言，不携带 PromptTemplate/PromptRevision；Provider 原始响应不进入业务表、事件、日志或普通 UI。
- 语言理解评分使用业务目的 `foundation_audio_scoring`、精确 Prompt `foundation-audio-scoring` / `foundation-audio-scoring-v1`、模型路由 `foundation-audio-scoring` / `foundation-audio-scoring-v1`、Schema `audio-scoring-input-v1` / `audio-scoring-output-v1`。正式调用冻结 Submission、场景/材料、TranscriptRevision、分段、质量摘要、维度/rubric 和允许知识范围。
- 评分 Prompt 的 `prompt_contract_hash` 不是评分方案中的静态常量。应用服务使用本次真实场景、转写和 rubric 变量严格编译已发布 PromptRevision，并把得到的 `sha256:<64 位小写十六进制>` 写入本次 Invocation；编译失败或运行时合同不一致进入可恢复失败，不能绕过治理或退回本地拼接 Prompt。
- AI 输出必须通过封闭 Schema，并且维度集合与冻结 Scorecard 完全一致、每个 evidence span 能在当前 TranscriptRevision 中定位。领域服务再按冻结权重、维度最低分、总通过线和 critical flags 确定 `score/pass`；模型不能直接改变 Attempt、Submission 或 Journey 状态。
- 解码损坏、确定性不支持格式属于终态并要求重新上传；对象存储、ASR/评分 Provider、Prompt 编译和输出 Schema 的暂时失败保留原始录音/转写并进入可恢复状态。低语音占比、低置信度、语言不符、过度静音/削波等得到 `not_scorable/needs_review`，不得写零分或“能力未达标”。
- 自动转写、人工更正和重转写分别追加不可变 TranscriptRevision；首次评分和每次重评分别追加 ScoreOutcomeVersion。每个版本保留音频 artifact、Transcript、Scorecard、Prompt、模型路由和 AI Invocation 血缘；失效只改变有效性，不覆盖历史版本。
- 默认标准包只冻结业务所需的精确 Prompt/模型路由引用，不臆造部署方 Provider 或模型。Slice 6 ReleasePlan 发布前必须验证这些修订已发布、Schema 已注册、Provider 可用并通过校准；条件缺失时 fail closed。

### 3.5 Slice 4 结构化 Coach AI 合同

- 三个任务类型分别为 `ai_coach.cards.generate`、`ai_coach.answer.evaluate`、`ai_coach.assistance.generate`；对应卡片生成、语言答案评估和受限解释，不能用自由消息隐式推进 Session。
- ProfileRevision 冻结三个独立 AI contract：business purpose、Prompt template/revision/hash、model routing profile/revision、input/output Schema、timeout/retry/budget/fallback。历史 Session 永不跟随新修订。
- 每轮只接受 Profile 白名单内 3～5 张有类型训练卡。卡片必须引用当前 Context snapshot 的来源；未知类型、额外字段、任意 HTML/脚本、外部指令、未知来源和空/非法输出均拒绝并进入可恢复路径。
- 选择/排序卡由规则评分，不创建 AI Invocation。语言卡的 AI 输出只提供分数、回答证据、缺失点、误解、反馈、建议与不确定性；最终 `mastered` 由应用按冻结阈值与最大不确定性计算。
- 学员回答和 client token 在任务创建前写入。Provider 超时、非法 Schema、页面刷新或重复响应不能丢失输入或产生重复 Turn、预算、评分。
- 自动补练最多两轮；高不确定性、来源不足或仍未达标进入 `needs_human_help`。三个 checkpoint 全部达标后才写 CoachOutcome/ActivityOutcome；Coach 不授予 `foundation_ready`。

## 4. ViewModel 合同

所有 ViewModel 带 `contract_version`、`generated_at`、`data_freshness`、`capabilities`。前端流程固定为 `API DTO -> Domain Model -> ViewModel -> UI`，不得从跨域原始 DTO 自行计算达标结论。

### `JourneyProjectionV1`

`enrollment{id,status,revision_id,version}`、`path{id,title,revision_label}`、`progress`、`stages[]`、`current_activity`、`background_tasks[]`、`recent_outcomes[]`、唯一 `primary_action`、`status_label/status_reason`。不含 Phase/Module 或 Realtime。

### `ActivityWorkspaceV1`

`activity{id,type,title,objective,steps,success_criteria}`、`attempt`、活动 `runner` 封闭联合、学习者安全的 `resource_snapshots`、`task?`、`outcome?`、`available_commands[]`、`recovery`。不得暴露 Prompt、Provider、raw rubric/AI JSON。

### `TaskStatusV1`

`task_id`、`state`、`state_label`、`progress{current,total,stage,label}`、`can_cancel`、`retry_after?`、`result_location?`、`error{retryable,message}?`、`updated_at`。不返回 Lease owner、内部堆栈或密钥。

### `EvidenceDossierV1`

`learner`、`path`、`dossier_version`、`status`、`summary`、`competencies[]`、`evidence[]`（来源、版本、置信度、验证状态）、`ai_assessment`、`human_decision?`、`retraining[]`、`appeals[]`、`next_actions[]`。事实、规则、推断、建议和人工决定必须分栏标识。

### `AdminQueueV1`

`items[]` 每项包含稳定 `object_id`、对象摘要、`queue_reason`、`risk_band`、证据缺失、负责人、期限、`primary_action` 与 capabilities；带分页、applied_filters、sort 和 freshness。无权限不是空列表。

## 5. 旧 API 退役点

以下仅为排版别名：`NT=/api/v1/newcomer-training`、`NTA=/api/v1/admin/newcomer-training`、`STA=/api/v1/admin/sales-trainer`。花括号中的逗号项表示逐个列出的真实 path alternative，不是 wildcard；清单不使用 `/**` 或“等”。

| Legacy | v2 替代 | 删除时点 |
|---|---|---|
| `GET NTA/path/`；`PUT NTA/path/draft`；`DELETE NTA/path/draft`；`POST NTA/path/{validate,validate-candidate,publish,publish-candidate}`；`GET NTA/path/{revisions,activity-types,coach-profiles,scoring-rubrics}`；`POST NTA/path/revisions/{revision_id}/restore`；`POST NTA/path/scoring-rubrics` | `NTA/paths`、`NTA/paths/{path_id}/working-revision`、`NTA/release-plans`、`NTA/resources` 的显式资源/命令 | 已删除；ReleasePlan 为唯一发布权威 |
| `GET /api/v1/newcomer-training/modules/{module_id}` | `GET /api/v1/newcomer-training/journey` 的 Stage 投影 + `GET /activities/{activity_id}` | Slice 2 |
| `POST NT/activities/{activity_id}/lesson/chapters/{chapter_id}/complete`、`POST NT/activities/{activity_id}/lesson/confirm`、`POST NT/activities/{activity_id}/quiz/attempts`、`POST NT/activities/{activity_id}/audio/submissions`、`POST NT/activities/{activity_id}/ai-coach/sessions`、`POST NT/activities/{activity_id}/ai-coach/sessions/{session_id}/turns`、`POST NT/activities/{activity_id}/ai-coach/sessions/{session_id}/turns/stream`、`POST NT/activities/{activity_id}/assignments` | `POST NT/activities/{activity_id}/commands` 的封闭 `ActivityCommandV1` 联合 | Lesson/Quiz 由 Slice 2；Audio 由 Slice 3；Coach 由 Slice 4；Assignment 三段录音由 Slice 3，建立单写后即删对应旧写 |
| `POST /api/v1/newcomer-training/activities/{activity_id}/realtime/sessions` | 无首发替代 | Slice 2 从新人 Path、OpenAPI、权限、seed 和 renderer union 移除；Realtime 原域保持独立 |
| `GET /api/v1/newcomer-training/papers/{paper_id}`、`POST /api/v1/newcomer-training/paper-attempts` | `ActivityWorkspaceV1` quiz runner + 通用 activity command | Slice 2 |
| `/api/v1/admin/newcomer-training/papers` 的 GET/POST/PUT 与 `{revisions,publish,rollback,archive}`；`/api/v1/admin/newcomer-training/units` 的 GET/POST/PUT 与 `{publish,archive,revisions,rollback}` | `/api/v1/admin/newcomer-training/resources` 的 question/quiz/learning_unit working revision + `/release-plans` | 已删除；资源 working revision + ReleasePlan 为唯一写入/发布路径 |
| `POST NTA/regrades/quiz-attempts/{attempt_id}/{preview,run}` | `NTA/quiz-attempts/{attempt_id}/regrades/preview`、`NTA/quiz-attempts/{attempt_id}/commands/regrade` | Quiz Slice 2 建立追加式版本后 |
| `POST NTA/regrades/audio-submissions/{submission_id}/{preview,run}` | `NTA/audio-submissions/{submission_id}/regrade/preview`、`NTA/audio-submissions/{submission_id}/regrade/confirm`；Transcript 更正与失效分别使用同对象下的 `/transcript-correction/{preview,confirm}`、`/invalidation/{preview,confirm}` | Audio Slice 3 建立追加式版本后 |
| `GET NTA/journeys`、`GET NTA/journeys/{learner_id}`；`GET NTA/readiness/workbench`、`GET NTA/readiness/dossiers/{learner_id}`、`POST NTA/readiness/dossiers/{learner_id}/review-actions` | `NTA/learners`、`NTA/reviews`、`NTA/reviews/{dossier_id}` 与有类型 review commands | Slice 5 建立 Dossier/Decision 单写，Slice 6 切换管理 UI 后 |
| `GET STA/audio-submissions`、`GET STA/audio-submissions/{submission_id}`、`GET STA/audio-submissions/{submission_id}/file`；`POST STA/audio-submissions/{submission_id}/{retry-transcription,retry-scoring}`；`GET STA/score-results`、`GET STA/training-records`、`GET STA/training-records/audio/{submission_id}`、`GET STA/training-records/detail/{record_type}/{record_id}`、`GET STA/training-records/detail/{record_type}/{record_id}/materials/{version_id}/file`、`GET STA/training-records/realtime-roleplay/{session_id}/observations`、`GET STA/quiz-attempts`、`GET STA/quiz-attempts/{attempt_id}` | Activity/Task/History/Review 业务对象入口；下载只经授权短时 URL；重试走 Task/Activity command | Foundation 新人用途入口已删除；其他产品独立路由不属于本合同 |

切换不提供永久 301、转发 Facade 或双写。若需短期观察，只允许只读对比并有 Owner、截止日期和删除测试。
