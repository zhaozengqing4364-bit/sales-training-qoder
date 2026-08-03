# 切片 3：录音评测持久化处理闭环

## Goal

把新人录音讲解和异步客户场景回答从“请求内或临时后台处理”升级为可恢复的持久化评测流水线，完整覆盖录制/上传、校验、标准化、转写、质量分析、评分、证据写入、结果对账、重评和人工介入。

首发只处理完整录音文件，不实现实时音频流或实时客户对练。

## Dependencies

- 切片 0：Audio、Attempt、Outcome、Evidence、权限和状态契约。
- 切片 1：持久化任务、Outbox、AI/ASR Provider Port、对象存储和任务状态。
- 切片 2：Path/Activity/Enrollment、Journey Projection 和能力映射。

## Current Gap

- 部分提交链路会在请求内读取完整文件并同步处理。
- 旧 API 使用进程内 BackgroundTask，发布或崩溃后不可恢复。
- Transcript 主要表现为可变单行记录，缺少分段、置信度和修订。
- 评分结果与 ActivityAttempt、通过结论和 Evidence 的对账不完整。
- 浏览器录制可能长期持有全部 chunks，缺少可靠本地草稿、续传和恢复。

## Product Scope

- Audio Explanation：新人讲解知识/方案。
- Async Customer Scenario：新人对预设客户场景录音回答。
- 两类活动共用 AudioSubmission 流水线，但评分方案、上下文和能力映射分别配置。

## Requirements

### R1. Audio Activity Contract

- ActivityDefinition 冻结：
  - 场景/题目修订；
  - 允许录音方式；
  - 时长与大小限制；
  - 语言；
  - ASR policy；
  - scorecard revision；
  - 通过规则；
  - 能力映射；
  - 最大尝试与重试策略。
- Attempt 开始时保存上述快照，后续规则发布不影响历史提交。
- 首发默认最大 30 分钟、100MB；最终数值必须通过规则配置并校验，不在页面散落。

### R2. Recording And Local Draft

- 浏览器支持录音、暂停/继续、试听、删除重录和文件上传。
- 录制数据分块写入本地草稿存储，避免长录音全部驻留内存。
- 页面刷新或短暂离线后可恢复未完成草稿。
- 本地草稿显示录制时间、估算大小、可恢复状态和删除动作。
- 本地数据保留期可配置；退出登录或超期后安全清理。
- 不把本地草稿误标为“已上传”。

### R3. Upload Session

- 使用 `AudioUploadSession` 协调直传对象存储。
- 服务端创建上传会话前校验：
  - 用户和 Enrollment；
  - Activity 与 Attempt 状态；
  - 文件类型、大小、时长政策；
  - 组织范围；
  - 幂等键和配额。
- 支持 multipart/chunk 上传、断点续传、取消和过期。
- 上传完成必须由服务端验证对象 metadata、hash、实际大小和所有权，不能只信客户端回调。
- 未完成上传自动过期清理，不污染正式 Submission。

### R4. Audio Artifact Integrity

- 原始音频保存不可变 artifact reference、hash、媒体类型、duration、sample rate 和创建者。
- 标准化产生新 artifact，不覆盖原始文件。
- 对象存储路径按组织和业务对象隔离，禁止用户控制完整 key。
- 下载和试听使用短期签名 URL，并做对象级权限校验。
- 录音和 transcript 按安全文档设定保留、删除和审计策略。

### R5. Submission State Machine

- 状态至少覆盖：
  - `draft`；
  - `uploading`；
  - `uploaded`；
  - `validating`；
  - `normalizing`；
  - `transcribing`；
  - `scoring`；
  - `reconciling`；
  - `completed`；
  - `partially_completed`；
  - `failed_recoverable`；
  - `failed_terminal`；
  - `cancelled`；
  - `invalidated`。
- 每个步骤由 DurableTask 执行并支持幂等重试。
- UI 只展示用户可理解的投影，不暴露内部 task type 或原始错误码。

### R6. Validation And Normalization

- 校验媒体头、格式、时长、采样率、声道、空音频和明显损坏。
- 文件扩展名与实际媒体不一致时拒绝或安全标准化。
- 标准化失败保留原始 artifact，并提供重新处理或重新上传路径。
- 不在数据库事务内执行 ffmpeg、对象存储或 Provider IO。
- 标准化输出和工具版本可追溯。

### R7. Transcript Revision

- Transcript 使用不可变 `TranscriptRevision`。
- 保存分段、起止时间、文本、置信度、说话人（若可用）、语言和 Provider metadata 摘要。
- 自动转写、人工修订和重新转写产生新修订，不覆盖历史。
- 评分绑定明确 TranscriptRevision 和 Audio Artifact。
- 低置信度、无语音、语言不符等形成 Quality Flag，不静默进入正式评分。
- 学员可在允许范围内查看和申诉；是否允许编辑由活动策略决定。

### R8. ASR Routing

- ASR 通过受治理 Provider Port 调用。
- 路由策略支持主 Provider、fallback、timeout、rate limit 和预算。
- Provider 临时失败进入重试；确定性不支持格式进入终态并提示重新上传。
- Provider 原始返回只存受控 artifact 或摘要，不在日志输出完整敏感文本。
- Fake Provider 可 deterministic 返回分段和置信度。

### R9. Audio Quality Report

- 在评分前生成确定性质量报告：
  - 有效语音占比；
  - 静音/截断；
  - 音量过低/失真；
  - 时长；
  - ASR 置信度；
  - 语言匹配；
  - 是否足以评分。
- 质量阈值配置化。
- “无法评分”与“能力未达标”必须分开。
- 无法评分不得写零分或正式未通过证据；给出重录或人工处理动作。

### R10. Scorecard And Scoring

- ScorecardRevision 冻结维度、权重、rubric、能力映射、通过规则和模型策略。
- 确定性指标先计算，再按需通过 AIInvocationPort 做语言理解评分。
- AI 输入包含场景、允许知识范围、TranscriptRevision、必要音频质量摘要和 rubric，不默认发送无关个人数据。
- AI 输出必须符合结构化 schema：
  - 维度得分；
  - evidence spans；
  - missing points；
  - uncertainty；
  - feedback；
  - recommended remediation。
- 最终 `ScoreOutcomeVersion` 由应用服务基于有效 schema 和确定性规则生成，模型不能直接改 Attempt 状态。

### R11. Outcome Reconciliation

- 评分完成后进入独立 reconcile 步骤：
  - 校验 Submission/Attempt/Enrollment/Activity revision；
  - 防止重复结果；
  - 写入 Outcome Version；
  - 投影 score/pass；
  - 写 Competency Evidence；
  - 发布领域事件；
  - 更新 Journey。
- 任一步失败必须可重跑。
- 任务成功但业务结果未写入时，状态显示“结果同步中/需修复”，不能显示完整成功。
- 提供管理员对账队列和安全重放命令。

### R12. Regrade And Invalidation

- Scorecard、Prompt 或模型策略更新时，可创建 Regrade Plan。
- Regrade 支持 preview 影响数量、dry-run、分批执行、取消和失败报告。
- 新评分创建新的 OutcomeVersion，不覆盖历史。
- Readiness 使用“最新有效版本 + 趋势”，但历史决策保持可追溯。
- 管理员可因音频损坏、作弊、错误关联等失效某个 Outcome，并记录原因和审计。

### R13. Learner Experience

- Workspace 清晰显示题目/场景、准备提示、录制主操作和规则。
- 上传与处理阶段展示具体步骤、可离开说明、取消/重试和结果位置。
- 失败文案说明什么失败、哪些内容已保留、下一步怎么做。
- 处理完成展示：
  - 总体结论；
  - 各维度表现；
  - 引用 transcript 证据；
  - 音频质量提示；
  - 下一步补练。
- 不把 AI 建议标记成已验证事实，不展示内部 Prompt、模型或原始 JSON。

### R14. Admin Experience

- 管理员可查看队列、Submission 状态、失败原因分类、重试和对账。
- 培训负责人可查看学员结果和证据，但不能查看无权限组织或敏感 Provider payload。
- 高风险重评、失效和人工覆盖需要 capability、原因、确认和审计。

### R15. Clean Cut

- 删除请求内全文件处理、进程内 BackgroundTask 作为正式流水线、Transcript 原地覆盖和“任务成功即结果成功”的旧逻辑。
- 删除或封存旧提交 API 的写能力。
- 新 AudioSubmission 流水线成为两类录音活动唯一权威。

## Acceptance Criteria

- [x] 30 分钟/100MB 边界按配置执行，前后端均校验，后端为权威。
- [x] 长录音不会全部常驻浏览器内存；刷新后可恢复本地草稿。
- [x] multipart 上传可中断、续传、取消和过期清理。
- [x] 上传完成前服务端校验对象 hash、大小和所有权。
- [x] API/Worker 重启后转写和评分任务能恢复。
- [x] Transcript 自动、人工和重转写均保留不可变修订。
- [x] 无法评分与能力未达标明确分离。
- [x] AI schema invalid、ASR 超时、对象存储失败均产生可恢复状态，不伪装成功。
- [x] Outcome reconcile 可幂等重跑且不重复写 Evidence。
- [x] Regrade 创建新版本，历史结果和原复核结论可追溯。
- [x] 跨组织访问、越权试听、越权重评被后端拒绝并审计。
- [x] 旧同步/临时后台写链路已移除。

## Verification

- 浏览器 E2E：录制、暂停、恢复、刷新、试听、上传、离开、返回查看结果。
- 上传集成：断点续传、重复 complete、伪造 key、大小不一致、过期 session。
- Worker 故障注入：标准化、ASR、评分、reconcile 各步骤崩溃恢复。
- Provider contract：正常、超时、429、空 transcript、低置信度、schema invalid。
- 数据测试：Outcome/Evidence 幂等、Regrade 版本、失效和历史查询。
- 性能：大文件不经 API 内存转发；任务查询和列表有索引证据。

## Definition Of Done

- 两类录音活动共享一套稳定流水线和 Activity Runtime。
- 所有耗时步骤可恢复、可观察、可取消或可人工修复。
- 学员输入不因可恢复失败丢失。
- 正式分数和证据可追溯到音频、Transcript、Scorecard、Prompt 和模型策略。
- 运维 Runbook、告警、数据保留和回滚说明齐全。

## Out Of Scope

- 不实现实时 WebSocket 音频、实时转写、实时打断或 AI 客户扮演。
- 不做语音克隆、声纹识别或情绪诊断。
- 不允许 AI 自动作出正式 Readiness 决策。

## Risk And Rollback

- 风险等级：P1。
- 主要风险是大文件、Provider 波动和异步状态错配。
- 按 Activity Type feature flag 启用；旧链路只在切换验证窗口内只读保留。
- 回滚停止新任务、保留已上传 artifact 和任务状态，切回旧只读结果；不得删除用户录音。
