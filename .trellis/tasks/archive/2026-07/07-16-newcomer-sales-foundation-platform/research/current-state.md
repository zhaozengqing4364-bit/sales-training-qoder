# 当前仓库事实与设计约束

## 1. CodeGraph Evidence

本任务讨论期间已使用 CodeGraph 检查新人路径、题目生成、录音提交、ASR、评分、重评、Activity Attempt 和前端录音链路。

### 已有可复用能力

- 新人训练 Path Revision 和统一 Activity Registry。
- ActivityAttempt 幂等 `client_token`。
- Lesson、Quiz、Audio、AI Coach、Assignment Handler。
- 材料和评分方案修订快照。
- 录音对象存储签名访问。
- ASR Provider Interface。
- 录音评分结果追加记录和历史重评审计。
- PromptTemplateService、Prompt 修订和 Contract Hash。
- 正式题库 Draft/Published/Archived 和题目修订。
- 前端录音、试听、文件上传和错误映射。
- 管理员 Journey、训练记录、Readiness 和资源快速创建的部分页面。

## 2. Product / Route Duplication

- 新人训练、旧 Sales Trainer、Learning Path、自由 Practice 等入口存在重叠。
- 部分学员和管理员页面仍按技术模块组织。
- 当前后台同时存在录音、评分结果、训练记录等分离入口，管理者需要拼结论。
- 路径编辑、内容维护、题库和 Prompt 之间仍需要跳转。

## 3. Architecture Findings

- 当前后端历史上存在多包 SCC，模块责任和 Adapter 边界仍需收口。
- `sales_trainer` 承载过多路径、题库、音频、AI Coach、Readiness 和治理职责。
- Journey 读模型已有批量优化，但 Handler/Service 仍有旧直连和双权威。
- 当前 Trellis Spec 仍定义 `Path -> Phase -> Module -> Activity`，与本任务确认的简化模型冲突。
- 当前 Spec 的发布行为会把活动 Enrollment 同步到新 Revision，与本任务的 Revision Freeze 冲突。
- 当前 Activity Union 包含 Realtime Roleplay，与首发延后范围冲突。

Slice 0 必须先通过 ADR 和 Spec 更新解决这些冲突，不允许实现阶段默默偏离。

## 4. Question Generation Findings

当前 `QuestionGenerationService`：

- 直接构建硬编码 Prompt；
- 通过 `get_llm_service().generate()` 调用模型；
- 没有使用 PromptTemplateService 编译合同；
- 单次只生成 3～5 道；
- Preview 结果不持久化；
- Confirm 直接创建 `QuestionItem` draft；
- 只保存来源 LearningContent / Chapter ID；
- 缺少来源片段、资料修订、模型、Prompt、Contract Hash、批次和审核状态；
- 没有独立 Candidate、拒绝原因、替代关系和批量任务。

前端正式题库页面已有“AI 出题审核”和“小测预览”链接，但对应路由/工作台没有形成完整实现。

## 5. Learning Content Findings

当前 LearningContent：

- 有 Draft/Published/Archived、Version、Hash 和 Working Revision 状态；
- Chapter 本身仍是简单 title/content/order；
- 没有明确区分原始资料、精编训练内容和来源片段；
- 内容详情页把章节编辑和 AI 出题描述放在同一区域，但实际出题工作台缺失；
- 当前 Source 主要是字符串，不足以表达资料修订和授权来源。

## 6. Audio Findings

当前新人 Audio Activity：

- `AudioAssessmentActivityHandler.submit_file()` 先创建 Attempt；
- 调用 `AudioSubmissionService.save_uploaded_file(auto_process=True)`；
- `save_uploaded_file()` 一次性 `await file.read()` 读取完整文件；
- 本地存储使用同步 `Path.write_bytes()`；
- `create_submission()` 在 `auto_process=True` 时直接调用 `process_submission()`；
- 新人 Activity API 没有像旧 Sales Trainer API 一样放入 BackgroundTask；
- 因此上传请求可能等待完整 ASR 和评分。

当前旧 Audio API 虽使用 FastAPI BackgroundTask，但它是进程内任务，不具备持久化、租约和跨进程恢复。

当前 AudioAttempt 回流：

- Handler 只在同步返回 `scored` 时把 Attempt 标记 completed；
- 未把 score、max_score、passed 写入 Attempt；
- `refresh_attempt()` 是 no-op；
- 没有发现评分完成事件自动 reconcile Attempt；
- 异步化后若不新增标准 Outcome 回流，Attempt 会长期停在 in_progress。

## 7. Transcript / Scoring Findings

当前 Transcript：

- 一个 Submission 只有一行唯一 Transcript；
- 重试会覆盖同一行；
- 保存完整文本和 raw payload；
- 没有分段时间、置信度、语言和修订原因。

当前评分：

- `DeucateScoringService` 直接调用 OpenAI-compatible endpoint；
- 没有经过统一 AI Invocation Module；
- 温度固定为 0；
- Response Invalid 时重试一次；
- 主要从模型结果读取 total_score、summary、strengths、improvements、dimension_scores；
- Passed 只用 total_score 与 threshold 比较；
- 没有严格执行输出 Schema、关键维度最低线、Evidence Span、Confidence 和红线。

当前重评已经具备：

- Preview；
- 使用已发布评分修订；
- 追加新 ScoreResult；
- 不覆盖旧分；
- 审计和 Trace。

该能力应保留语义并迁移到新的 Audio Outcome Version。

## 8. Browser Recording Findings

当前新人录音 Hook：

- 使用一个 MediaStream 和 MediaRecorder；
- 录音结束后把所有 Blob Chunk 合成一个 Blob/File；
- 文件保存在内存；
- 支持试听、重录和文件上传；
- 不支持本地持久草稿、分片直传和断点续传；
- 没有前置输入电平、静音或削波检查；
- 页面离开时停止 Track。

旧 Practice 模块另有连续分片上传 Hook，但属于 Realtime/Practice 场景，不能直接成为新人 Audio Authority；可以提取无业务语义的浏览器录音基础能力。

## 9. Task Runtime Findings

- 当前存在若干 Task Wrapper 和 TrainingTask 业务表。
- Audio BackgroundTask、Knowledge BackgroundTask 等仍有各自实现。
- 未发现满足本任务 lease、retry_wait、dead_letter、cancel_requested、outbox 和 worker 独立进程要求的统一 Task Runtime。
- 本任务必须先建设平台任务能力，不能让 Audio、Question、Coach 各自再造任务状态机。

## 10. Frontend Findings

- 当前 Activity Shell 和封闭 Renderer Registry 可复用。
- 新人 Activity 页已有 processing 轮询，但 Activity 投影状态与 Audio Submission 状态没有可靠 reconcile。
- Audio Runner 已覆盖准备材料、评分重点、录音、试听、重录和文件上传。
- 页面在 Attempt in_progress 时会进入结果模式并隐藏 Runner，无法覆盖完整后台处理、取消、续传和恢复。
- 大量页面仍为 Client Component，服务端数据获取和 Query Cache 可继续收口。
- 当前视觉基础可复用，但卡片和技术入口数量偏多。

## 11. Existing Docs And Assets

可复用内容：

- `docs/content/ppt-explanation-training-material.md`
- `docs/content/ppt-scenario-reference.md`
- `docs/lujingshuji/商务礼仪-新人的第一本职业素养手册-完整版.md`
- `backend/scripts/seed_materials/presales_cio_first_visit/`
- `docs/plans/2026-06-14-business-etiquette-training-pack-prd.md`
- `docs/product/newcomer-training-v0.9-usable-loop.md`

这些资料包含示例公司事实、案例、数字和产品承诺。进入正式训练前必须由内容负责人审核；不能因为文件在仓库中就自动视为当前有效事实。

## 12. Existing Task Conflicts

现有 `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan`：

- 把 Realtime 纳入首版完整闭环；
- 保留 Phase/Module 层级；
- 对 Enrollment 发布同步有不同决策。

本任务依据用户后续明确决定：

- 首发 Realtime 延后；
- 路径层级简化；
- Enrollment Revision Freeze；
- 开发期允许干净切换。

因此新任务在 Slice 0 完成 ADR/Spec 更新后成为该产品范围的新实施权威。旧任务保留历史证据，不直接删除。

## 13. Dirty Worktree Constraint

当前工作区存在大量用户和其他任务改动，包括数据库首发 Baseline、Team、账号、UI、API 和测试。

实施要求：

- 不使用 `git reset --hard`、`git checkout --` 或类似破坏操作；
- 每个子任务开始前重新检查 Git 状态和活跃任务；
- 避免覆盖其他任务创建的首发 Baseline 和资源编辑能力；
- 重叠文件必须先读当前内容和调用者；
- 无法安全合并时停止并请求用户协调。
