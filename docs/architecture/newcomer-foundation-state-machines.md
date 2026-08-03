# 新人销售基础训练状态机合同

> 状态：Accepted target contract；切片 0 不实现状态机。所有转移由 Domain/Application 命令集中管理，Controller、React 页面和 Provider Adapter 不得直接写状态。

## 通用规则

- 每个命令携带 `organization_id`、Actor、`idempotency_key`、`expected_version`（适用时）及 trace/correlation 信息。
- 相同幂等键和同一规范化输入返回原结果；同键不同输入返回 409 `[IDEMPOTENCY_KEY_REUSED]`。
- 乐观锁冲突不改数据，返回 412 `[RESOURCE_VERSION_CONFLICT]`。
- 业务写、审计与 Outbox 同事务；外部 IO 不持有业务事务。
- “失败”必须保留可恢复位置；不存在的记录不能通过写一个 `failed` 行伪造。

## 状态与转移

### PathRevision

`draft`（初始） -> `validating` -> `ready | blocked` -> `publishing` -> `published`（不可变）；发布事务未生效时 `publishing -> blocked`；`draft|blocked|ready -> discarded`；`published -> archived`。

- 命令：`SavePathRevision`、`ValidatePathRevision`、`PublishReleasePlan`、`DiscardPathRevision`、`ArchivePathRevision`。
- 前置：发布必须由 ready ReleasePlan 驱动，依赖均为已发布修订且无 Realtime。
- 幂等：命令以 `(organization_id, path_revision_id, command, idempotency_key)` 去重；发布还复用 ReleasePlan 的 impact hash，重复确认返回同一 published revision。
- 失败/重试：校验或发布失败进入 `blocked` 并保留结构化问题；修正 working content 后重复 `ValidatePathRevision`，发布只通过原 ReleasePlan 同键重试或创建新计划。
- 取消：`DiscardPathRevision` 是工作修订的业务取消路径；进入原子 `publishing` 后不可协作取消，只能等待成功或回到 `blocked`。
- 过期：N/A。PathRevision 不按时间自动失效；依赖或预览过期由 ReleasePlan 阻断，已发布修订只能显式归档。
- 人工介入：有权限的训练管理员修正 blocked revision、重新校验、丢弃或归档；不得直接把状态改为 ready/published。
- 终态：`discarded`、`archived`；`published` 内容终态但可归档。
- 审计：`PathRevisionDraftSaved`、`PathRevisionValidated/Blocked`、`PathRevisionPublished`、`PathRevisionDiscarded`、`PathRevisionArchived`；公开影响由 Release/Journey 事件表达。

### Enrollment

`assigned`（初始） -> `active` -> `completed`；`assigned|active|paused -> cancelled|expired`；`active -> paused -> active`。

- 命令：`EnrollLearner`、`ActivateEnrollment`、`PauseEnrollment`、`ResumeEnrollment`、`CancelEnrollment`、`MigrateEnrollmentRevision`。
- 完成/过期命令：`CompleteEnrollment` 只在必修 Gate 均有有效 Outcome 时执行；`ExpireEnrollment` 只按冻结 Cohort/Enrollment 政策和 expected_version 执行，禁止读路径时顺手过期。
- 迁移不是自动状态：在 `assigned|active|paused` 保持生命周期状态，原子替换冻结 revision、递增 version 并发出 `EnrollmentRevisionMigrated`。
- 前置：目标 revision 已发布；预览 token、差异哈希和 expected_version 匹配；不存在进行中的不兼容操作。
- 幂等：分配按 `(organization_id, cohort_id, learner_id)` 业务唯一键及命令幂等键去重；生命周期命令按 Enrollment/version/幂等键返回原结果，同键异参冲突。
- 失败/重试：权限、版本、Gate 或迁移预览失败不改变 Enrollment；修正前置条件后以新 expected_version 重试，网络结果未知时复用原键。
- 取消：`CancelEnrollment` 进入 `cancelled`，保留历史 Attempt/Outcome，不删除证据。
- 过期：`ExpireEnrollment` 进入 `expired`；它是显式、可审计的政策命令，不由 Journey 查询隐式触发。
- 人工介入：训练管理员可暂停/恢复/取消或执行 revision 迁移；迁移必须 preview + confirm + reason，不能替代学员完成状态。
- 终态：`completed`、`cancelled`、`expired`。
- 审计：`EnrollmentAssigned`、`EnrollmentActivated/Paused/Resumed/Completed/Cancelled/Expired`、`EnrollmentRevisionMigrated`。

### ActivityAttempt

`created`（初始） -> `in_progress` -> `submitted` -> `processing` -> `completed`；`submitted|processing -> processing_failed -> processing`；`submitted|processing|processing_failed -> needs_review -> processing|completed`；任一非终态可到 `cancelled|expired`。

- 命令：`StartActivity`、`StartNewAttempt`、`ExecuteActivityCommand`、`SubmitActivity`、`BeginActivityProcessing`、`MarkActivityProcessingFailed`、`ReconcileActivityOutcome`、`RetryActivityProcessing`、`RequestActivityReview`、`ResolveActivityReview`、`CancelActivityAttempt`、`ExpireActivityAttempt`。
- 前置：Attempt 必须属于 Actor 可访问的冻结 Enrollment/ActivityDefinition；expected_version 匹配；`completed` 必须收到同 Attempt、同冻结合同且 schema 有效的 ActivityOutcome；人工 Resolve 也不能绕过 Outcome。
- 幂等：同一 Attempt 的技术命令复用原幂等键；Outcome consumer 以 `(producer, outcome_id, schema_version)` 去重；重复 reconcile 返回同一 Outcome pointer。
- 技术重试复用 Attempt；学习重试仅从终态通过 `StartNewAttempt` 创建 `attempt_no + 1`。
- 失败/重试：可恢复技术失败进入 `processing_failed`，记录失败阶段和 retry policy；`RetryActivityProcessing` 回到原阶段对应的 `processing`，不得新建 Attempt 或伪造分数。
- 取消：`CancelActivityAttempt` 协作取消关联 Task 后进入 `cancelled`；已完成 Outcome 不可取消。
- 过期：`ExpireActivityAttempt` 仅按冻结活动时限执行；进行中的外部任务先请求取消，历史输入仍保留。
- 人工介入：低置信度、Provider 非重试失败或活动合同要求人工审核时进入 `needs_review`；授权 Reviewer 可请求重跑或提交有效人工 Outcome。
- `completed` 必须引用 ActivityOutcome；不得由前端或 Provider 回调直接标记。
- 终态：`completed`、`cancelled`、`expired`；`processing_failed` 非终态。
- 审计：`ActivityAttemptStarted/Submitted/ProcessingFailed/Retried/ReviewRequested/ReviewResolved/Cancelled/Expired`、`ActivityOutcomeRecorded`、`JourneyProgressChanged`。

### DurableTask

`queued`（初始） -> `running` -> `succeeded`；`running -> retry_wait -> queued`；`queued|running|retry_wait -> cancel_requested -> cancelled`；`running|retry_wait -> dead_letter`。

- 命令：`EnqueueTask`、`ClaimTaskLease`、`RenewTaskLease`、`CompleteTask`、`FailTaskAttempt`、`ReleaseRetryWait`、`ReapExpiredTaskLease`、`RequestTaskCancel`、`AcknowledgeTaskCancel`、`RedriveDeadLetter`（创建新 Task，旧行不变）。
- 前置：claim/renew 必须匹配 task version、lease token 和 owner；complete/fail 必须匹配当前 attempt；业务结果先以其业务幂等键落库，再完成 Task。
- 幂等：enqueue 以 `(organization_id, task_type, business_idempotency_key)` 去重；complete/fail/cancel/reap 以 task/version/attempt/命令键去重。
- 失败/重试：`FailTaskAttempt` 按冻结 retry policy 进入 `retry_wait` 或 `dead_letter`；`retry_wait` 到期后由 `ReleaseRetryWait` 重新入队，不覆盖 attempt history。
- 取消：`RequestTaskCancel` 只写 `cancel_requested`；Worker 在安全点 `AcknowledgeTaskCancel`，已完成任务返回原结果。
- 过期：Lease 到期由 `ReapExpiredTaskLease` 幂等进入 `retry_wait`。Task 本身没有通用 `expired` 终态；业务 deadline 到期按冻结策略走 `dead_letter`，原因必须是 `deadline_expired`，避免丢失可恢复位置。
- 人工介入：授权 Operator 只能查看脱敏诊断、请求取消或 `RedriveDeadLetter` 创建新 Task；不得把旧 dead-letter 行改回 queued。
- 终态：`succeeded`、`dead_letter`、`cancelled`。
- 审计：`DurableTaskEnqueued`、`TaskLeaseClaimed/Renewed/Expired`、`TaskAttemptFailed`、`TaskRetryScheduled`、`TaskCancelRequested/Acknowledged`、`TaskDeadLettered/Redriven/Succeeded`。

### AudioSubmission

`uploading`（初始） -> `uploaded` -> `validating` -> `transcribing` -> `transcript_ready` -> `scoring` -> `finalizing` -> `completed`。

旁路：`validating|transcribing|scoring|finalizing -> processing_failed`；可重试错误回到失败阶段，非重试错误进入 `needs_review`；低置信度 `transcribing -> needs_review`；任一非终态可协作取消到 `cancelled`；未确认上传到 `expired`。

- 命令：`CreateAudioUploadSession`、`FinalizeAudioUpload`、`RecordAudioValidation`、`BeginAudioTranscription`、`RecordTranscriptRevision`、`BeginAudioScoring`、`RecordScoreOutcomeVersion`、`FinalizeAudioOutcome`、`MarkAudioStageFailed`、`RetryAudioStage`、`RequestAudioReview`、`ResolveAudioReview`、`FlagTranscriptCorrection`、`ApproveTranscriptCorrection`、`RegradeAudioSubmission`、`CancelAudioSubmission`、`ExpireAudioUpload`。
- 前置：finalize 必须匹配 upload token、对象 metadata/hash、冻结 Attempt/Activity/Enrollment 和 expected_version；各阶段命令只接受上游不可变 artifact ref；complete 必须引用有效 Outcome。
- 幂等：上传会话按业务命令键去重；finalize 以 `(submission_id, object_hash, idempotency_key)` 去重；Transcript/Score 版本和阶段 Task 均有唯一业务键。
- 失败/重试：可重试错误进入 `processing_failed` 并冻结 failed_stage/retry policy；`RetryAudioStage` 从该阶段继续。非重试错误或低置信度进入 `needs_review`，绝不把技术失败计为能力失败。
- 取消：`CancelAudioSubmission` 请求关联 Task 协作取消后进入 `cancelled`；原始对象按留存策略处理，不覆盖既有修订。
- 过期：未 finalize 的上传会话由 `ExpireAudioUpload` 进入 `expired`；已进入处理链路不按上传 TTL 过期。
- 人工介入：授权角色可 `ResolveAudioReview`、追加 TranscriptCorrection 或发起 Regrade；每次都生成新 revision/version 和 lineage，禁止覆盖原结果。
- 原始文件不可变；更正生成 TranscriptRevision；重评生成 ScoreOutcomeVersion。
- 终态：`completed`、`cancelled`、`expired`；`needs_review` 是人工可恢复状态。
- 审计：`AudioUploadCreated/Finalized/Expired`、`AudioValidationRecorded`、`AudioStageFailed/Retried/Cancelled`、`AudioReviewRequested/Resolved`、`TranscriptRevisionRecorded/CorrectionApproved`、`AudioScoreVersionRecorded/RegradeRequested`。

### QuestionCandidate

`pending_quality_gate`（初始） -> `pending_review | quality_blocked`；`quality_blocked -> pending_quality_gate` 仅在规则/来源修正后重跑；`pending_review -> under_review -> approved | rejected`；来源变化使非终态或 approved 候选进入 `stale`；被替代进入 `superseded`。

- 命令：`GenerateQuestionCandidates`、`RunCandidateQualityGate`、`RetryCandidateQualityGate`、`BeginCandidateReview`、`ApproveCandidate`、`RejectCandidate`、`MarkCandidateStale`、`SupersedeCandidate`。
- 前置：候选冻结来源 revision、生成合同和 provenance；审核 Actor 具备对象范围；红线/AI 简答题遵循更高确认权限。
- 幂等：生成批次以 source revision + generation contract + business key 去重；quality/review 命令按 candidate/version/命令键去重。
- 失败/重试：生成技术失败只体现在 DurableTask，不创建半成品 Candidate；确定性质量失败进入 `quality_blocked`。规则或来源修正后可重跑 Gate，否则生成新 Candidate 并 supersede 旧项。
- 取消：N/A。Candidate 不是进行中的用户执行；业务撤销使用 `RejectCandidate` 或 `SupersedeCandidate`，两者均保留原因和历史。
- 过期：N/A。Candidate 不按墙钟过期；来源、Prompt 或规则变化时显式 `MarkCandidateStale`。
- 人工介入：`BeginCandidateReview`、Approve/Reject 是人工路径；人工不得跳过 quality gate 或把 approved 直接当 published。
- `approved` 只允许生成 Question working revision，不等于发布。
- 终态：`rejected`、`superseded`；`stale` 需重新生成/验证，不可发布。
- 审计：`CandidateGenerated/QualityBlocked/QualityRetried/ReviewStarted/Approved/Rejected/MarkedStale/Superseded`。

### QuestionRevision

`working`（初始） -> `validating` -> `ready | blocked`；`ready -> published` 仅由 ReleasePlan；`working|blocked|ready -> discarded`；`published -> archived`；来源更新后 `working|blocked|ready -> stale -> working`。

- 命令：`SaveQuestionWorkingRevision`、`ValidateQuestionRevision`、`IncludeInReleasePlan`、`PublishReleasePlan`、`DiscardQuestionRevision`、`ArchiveQuestionRevision`、`MarkQuestionRevisionStale`、`RefreshQuestionRevision`。
- 发布只能由 ReleasePlan；红线题和 AI 简答题需训练管理员确认。
- 前置：working payload、答案/评分合同、来源 lineage 和 expected_version 有效；发布时依赖闭包及所需人工确认均通过。
- 幂等：save/validate/discard/archive 按 revision/version/命令键去重；发布复用 ReleasePlan idempotency 与 impact hash。
- 失败/重试：验证失败进入 `blocked` 并保留 field/object issue；修正后重新验证。发布失败停留 ready 或由 ReleasePlan 标记 blocked，不产生半发布题目。
- 取消：`DiscardQuestionRevision` 是未发布修订的取消路径；published 不可取消，只能归档并发布替代修订。
- 过期：N/A。修订不按时间过期；来源/规则变化进入 `stale`，published 历史仍不可变。
- 人工介入：内容编辑可修正 working/blocked，训练管理员确认红线/AI 简答题并通过 ReleasePlan 发布；禁止直接改状态。
- 终态：`discarded`、`archived`；published 内容不可变。
- 审计：`QuestionWorkingRevisionSaved`、`QuestionRevisionValidated/Blocked/MarkedStale/Refreshed/Discarded/Published/Archived`。

### AiCoachSession

`created`（初始） -> `preparing` -> `awaiting_answer` -> `evaluating|feedback_ready`；`feedback_ready -> awaiting_answer`；轮次完成后进入 `checkpoint_mastered|remediation_required|needs_human_help`；`checkpoint_mastered -> preparing|completed`；`remediation_required -> preparing|needs_human_help`；Provider/Schema 可恢复失败进入 `failed_recoverable -> preparing|evaluating`；任一未完成状态可 `cancelled`。

- 命令：`start`、`submit_coach_answer`、`continue_coach`、`retry_coach`、`request_coach_assistance`、`cancel`；人工侧使用有版本的 `intervene` 追加指导或后续动作。
- 前置：Session 冻结 Enrollment、PathRevision、Activity、Profile、三个 checkpoint、Context references、Prompt/model/schema/card/remediation policy；提交必须属于当前卡且 `expected_detail_version` 匹配。
- 幂等：start/continue/retry/cancel 使用命令键；回答额外以 client token + answer hash 去重。相同 token/相同回答恢复原结果，不同回答冲突，禁止重复 Turn、Invocation、预算或评分。
- 生成：每个 checkpoint/cycle 一次生成 3～5 张白名单卡；模型输出必须通过有类型 Schema、来源范围和安全内容校验，不能生成任意 HTML/组件/脚本。
- 评分：学员响应先写入再进入 `evaluating`；确定性卡不用模型，语言卡只经 `AIInvocationPort`。模型 `mastered` 不改变状态，应用按冻结分数阈值与最大不确定性计算。
- 失败/重试：卡片生成或答案评估失败进入 `failed_recoverable`，保留失败阶段和已提交回答；`retry_coach` 复用该记录。非法结构化输出不得完成评分。
- 补练与人工：一个 checkpoint 最多两轮自动补练；高不确定性、证据不足或超限进入 `needs_human_help`。Reviewer 只能追加指导/指派动作和审计，不能改写回答或 AI 历史。
- 受限讲解：`request_coach_assistance` 生成持久化解释/示例，但不推进或绕过正式 Session 状态机。
- 取消：`cancel` 协作取消运行 Task 后进入 `cancelled`，已持久化 Cycle/Turn/Card/Response/Assistance 仍可审计。
- 终态：`completed`、`cancelled`；`needs_human_help` 是可见阻塞和人工队列，不是失败完成。
- 审计：Activity command audit、AI Invocation lineage、Coach command audit、人工 intervention 与 normalized ActivityOutcome 共同保留完整链路。

### ReadinessDossier

`projecting`（初始） -> `incomplete | ready_for_review` -> `under_review` -> `decided`；新有效证据或重评使 `ready_for_review|under_review|decided -> stale -> projecting`；投影失败进入 `projection_failed -> projecting`。

- 命令：`BuildDossier`、`RequestReadinessReview`、`StartReadinessReview`、`RecordReviewDecision`、`RebuildDossier`。
- 辅助命令：`MarkDossierProjectionFailed`、`MarkDossierStale` 由受信事件 consumer 触发，仍经过同一状态机和版本校验。
- 前置：投影只消费本组织、当前 Enrollment 和可验证 lineage 的 Evidence；开始复核要求 completeness Gate 与 dossier version 匹配。
- 幂等：Build/Rebuild 以 `(organization_id, enrollment_id, evidence_set_hash)` 去重；事件 consumer 以 event id/schema version 去重；重复决定引用原 ReviewDecision。
- 失败/重试：投影技术失败进入 `projection_failed` 并保留上一个安全投影；修复后 `RebuildDossier` 回到 `projecting`。证据不足进入 `incomplete`，不是技术失败。
- 取消：N/A。Dossier 是 Enrollment 的派生档案，不是可取消执行；停止训练应取消/关闭 Enrollment，档案历史仍保留。
- 过期：N/A。档案不按时间删除或过期；证据有效性、重评或新 Evidence 通过 `MarkDossierStale` 进入重建。
- 人工介入：培训负责人显式请求/开始复核并记录决定；AI assessment 只能作为分栏证据，不能直接进入 `decided`。
- `ready_for_review` 要求证据完整性 Gate；低置信度/降级证据不能单独满足。
- 已决定档案被新证据影响时保留旧决定并重新开放复核，绝不静默覆盖。
- 终态：永久终态 N/A；Dossier 是可随新证据重建的版本化投影，`decided` 是稳定业务状态但仍可变 stale，旧 dossier version 保留为不可变历史。
- 审计：`DossierProjected/ProjectionFailed/Rebuilt/MarkedIncomplete/MarkedStale`、`ReadinessReviewRequested/Started`；正式决定审计由 ReviewDecision 负责。

### ReviewDecision

持久化对象初始即 `recorded`（不可变）；后续合法新决定将旧决定标记 `superseded`；仅审计纠错命令可标记 `voided`，且必须创建替代决定。事务失败不写“failed decision”。

- 命令：`RecordReviewDecision`、`SupersedeReviewDecision`、`VoidErroneousDecision`。
- 决定类型：`foundation_ready`、`retraining_required`、`exception_approved`、`evidence_required`。
- 前置：培训负责人有对象范围、档案版本匹配、理由完整；例外批准需预览与二次确认。
- 幂等：record 以 `(organization_id, dossier_id, dossier_version, idempotency_key)` 去重；同一 active decision 的 supersede/void 按 version/命令键返回原结果。
- 失败/重试：事务失败不写任何 Decision；结果未知时复用原键，前置冲突修正后必须用新 dossier version/新键重试。
- 取消：N/A。正式决定不可取消或删除；业务改变用新决定 supersede，审计纠错用 void + replacement。
- 过期：N/A。Decision 不按时间过期；证据失效只会使 Dossier stale 并要求新的决定，不改旧记录。
- 人工介入：所有决定均由有对象范围的人工 Reviewer 发出；AI、Provider、事件 consumer 都没有此命令权限。
- 终态：`superseded`、`voided`；active `recorded` 不可变，只能被新记录替代。
- 审计：`ReviewDecisionRecorded/Superseded/Voided`；重练同时产生 `RetrainingAssigned`，void 必须记录 replacement id。

### ReleasePlan

`draft`（初始） -> `validating` -> `ready | blocked` -> `publishing` -> `published | failed`；preview token/impact hash 过期使 `ready -> blocked`；`draft|blocked|ready -> cancelled`；`failed -> validating`（修复后重试）。

- 命令：`CreateReleasePlan`、`ValidateReleasePlan`、`PreviewReleaseImpact`、`MarkReleasePreviewExpired`、`PublishReleasePlan`、`MarkReleasePublicationFailed`、`RetryReleasePlan`、`CancelReleasePlan`。
- 前置：依赖闭包、权限、Provider/Task capability、能力映射和影响预览通过；确认时差异哈希仍一致。
- 幂等：create/validate/preview/cancel 按 plan/version/命令键去重；publish 还绑定 exact dependency set、impact hash 和 expected_version，重复确认返回同一发布结果。
- 失败/重试：校验问题进入 `blocked`；原子发布失败且无业务写生效时进入 `failed`，保留结构化原因；修复后 `RetryReleasePlan` 回到 validating，禁止跳回 ready。
- 取消：`CancelReleasePlan` 仅在 draft/blocked/ready 生效；进入 publishing 后不可协作取消，以免产生不确定发布权威。
- 过期：preview token 或 impact hash 到期由 `MarkReleasePreviewExpired` 使 ready 回到 blocked，必须重新 preview；ReleasePlan 本身无通用 expired 终态，避免丢失发布审计。
- 人工介入：训练管理员修复依赖、重新校验/预览并带 reason + confirm 发布；不得直接修改 PathRevision active pointer。
- 发布是同库原子写；外部刷新通过 Outbox 后置，失败不得产生部分业务生效。
- 终态：`published`、`cancelled`；`failed` 可修复重试且保留审计。
- 审计：`ReleasePlanCreated`、`ReleasePlanValidated/Blocked`、`ReleaseImpactPreviewed/Expired`、`ReleasePublishRequested/Published/Failed/Retried/Cancelled`。

## 审计事件矩阵

每个成功状态命令都追加 `StateTransitionAudited` 基础审计（对象、from/to、command、actor、reason、idempotency、expected/actual version、trace）；失败命令记录拒绝原因但不得伪造状态转移。下表是各状态机还必须记录的业务审计事件：

| 状态机 | 必须审计的业务事件 |
|---|---|
| PathRevision | `PathRevisionDraftSaved`、`PathRevisionValidated/Blocked`、`PathRevisionPublished/Discarded/Archived` |
| Enrollment | `EnrollmentAssigned`、`EnrollmentActivated/Paused/Resumed/Completed/Cancelled/Expired`、`EnrollmentRevisionMigrated` |
| ActivityAttempt | `ActivityAttemptStarted/Submitted/ProcessingFailed/Retried`、`ActivityReviewRequested/Resolved`、`ActivityOutcomeRecorded`、`ActivityAttemptCancelled/Expired` |
| DurableTask | `DurableTaskEnqueued`、`TaskLeaseClaimed/Renewed/Expired`、`TaskAttemptFailed/RetryScheduled`、`TaskCancelRequested/Acknowledged`、`TaskDeadLettered/Redriven/Succeeded` |
| AudioSubmission | `AudioUploadCreated/Finalized/Expired`、`AudioValidationRecorded`、`AudioStageFailed/Retried/Cancelled`、`AudioReviewRequested/Resolved`、`TranscriptRevisionRecorded/CorrectionApproved`、`AudioScoreVersionRecorded/RegradeRequested` |
| QuestionCandidate | `CandidateGenerated/QualityBlocked/QualityRetried`、`CandidateReviewStarted/Approved/Rejected`、`CandidateMarkedStale/Superseded` |
| QuestionRevision | `QuestionWorkingRevisionSaved`、`QuestionRevisionValidated/Blocked/MarkedStale/Refreshed`、`QuestionRevisionDiscarded/Published/Archived` |
| AiCoachSession | `CoachSessionStarted`、`LearnerResponseRecorded`、`CoachInvocationRequested/Failed/Retried`、`CoachRemediationStarted`、`CoachEscalated/Resolved`、`CoachSessionCompleted/Cancelled/Expired` |
| ReadinessDossier | `DossierProjected/ProjectionFailed/Rebuilt`、`DossierMarkedIncomplete/Stale`、`ReadinessReviewRequested/Started` |
| ReviewDecision | `ReviewDecisionRecorded/Superseded/Voided`、`RetrainingAssigned` |
| ReleasePlan | `ReleasePlanCreated`、`ReleasePlanValidated/Blocked`、`ReleaseImpactPreviewed/Expired`、`ReleasePublishRequested/Published/Failed/Retried/Cancelled` |
