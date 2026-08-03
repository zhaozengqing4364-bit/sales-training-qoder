# 切片 2：训练路径、学习内容与题库治理

## Goal

建立新人销售基础训练的路径主干、学习内容权威、题目生产治理和测验闭环，让新人从单一入口进入冻结的训练版本，按 Stage 完成 Lesson 与 Quiz，并把结果可靠写入统一 ActivityAttempt、能力证据和 Journey Projection。

本切片同时建立首发标准训练包，替代当前重复路由、简单章节结构和“AI 生成后直接进入题库”的松散链路。

## Dependencies

- 切片 0：领域、API、状态和权限契约。
- 切片 1：短答评分、题目生成、发布检查等持久化任务与 AIInvocationPort。

## Product Scope

- 单一学员入口。
- PathRevision -> Stage -> ActivityDefinition。
- Cohort 固定 PathRevision，Enrollment 默认冻结。
- Lesson 与 Quiz 两类完整 Activity Runtime。
- 原始材料、整理后学习单元、来源锚点。
- AI 候选题、人工审核、正式题库修订、考卷修订。
- 首发标准包和 deterministic seed。

## Requirements

### R1. Path, Revision And Enrollment

- Path 是稳定业务身份；PathRevision 是不可变发布版本。
- PathRevision 内部结构只包含 Stage 和 ActivityDefinition，不恢复 Module 层。
- Stage 定义顺序、标题、目标、进入条件、完成规则和可见性。
- ActivityDefinition 使用有判别字段的类型联合，配置由对应 Runtime 校验。
- Cohort 必须绑定一个已发布 PathRevision。
- Enrollment 创建时保存绑定修订；发布新修订不自动迁移活跃 Enrollment。
- 显式迁移需要 impact preview、逐人/批量选择、能力验证、审计、幂等和失败报告。

### R2. Journey Projection

- 为学员提供统一 Journey Projection：
  - 当前 Stage 和 Activity；
  - 已完成、进行中、被锁定、待复核、需补练、失败可重试状态；
  - 主操作；
  - 预计工作量；
  - 最近结果；
  - 阻塞原因；
  - 下一步。
- Projection 由后端应用服务生成，前端不得自行重算门禁或达标。
- 支持 stale/version conflict 提示和刷新。
- 当缺少必要 Enrollment、材料或配置时，管理员在当前流程中就地选择/快速新建/关联，不要求跳转维护数据表。

### R3. Activity Attempt Core

- Lesson 和 Quiz 共用统一 Attempt 外壳：
  - client token 幂等；
  - enrollment/path/activity revision snapshot；
  - started/submitted/completed/failed/invalidated timestamps；
  - result ref；
  - score/pass projection；
  - evidence status；
  - reconcile status。
- 类型细节保留在各自领域表，不把完整业务数据塞进通用 Attempt JSON。
- 完成后发布 `ActivityOutcomeRecorded`，再更新 Journey 和 Competency Evidence。

### R4. Learning Source And Curated Content

- 区分原始材料 `SourceDocumentRevision` 与整理后的 `LearningUnitRevision`。
- 原始材料保留来源、文件 hash、版本、解析状态、页码/时间段/段落位置。
- LearningUnit 包含面向学员的结构：目标、关键概念、示例、检查点、练习提示和来源锚点。
- 整理内容可以人工编辑；AI 只能生成草稿或建议。
- 发布后的 LearningUnitRevision 不可变；新编辑产生新修订。
- 内容删除必须检查已发布路径、题目和证据引用，默认归档而非物理删除。

### R5. Source Anchors And Traceability

- 每个正式学习要点、题目依据和 AI Coach 知识引用可关联 SourceAnchor。
- Anchor 至少能定位文档修订和局部位置。
- 文档重新解析不能静默篡改历史 Anchor；需产生新 revision 或显式重映射。
- 学员界面展示适量来源说明；内部切片坐标只在管理/审计视图显示。

### R6. Lesson Runtime

- Lesson Workspace 展示目标、内容、来源、学习进度和主操作。
- 学员必须完成定义的检查点或最低阅读行为后才能提交完成。
- Lesson 不用虚假分钟数或滚动到底作为唯一完成依据。
- 支持保存进度、恢复、重复查看、重新学习和管理员失效旧结果。
- 覆盖 loading、empty、error、permission denied、stale、offline/degraded 和保存失败恢复。

### R7. Question Generation Pipeline

- AI 生成链路：
  1. 选择已发布 Source/LearningUnit revision；
  2. 创建 `QuestionGenerationBatch`；
  3. 通过持久化任务生成结构化 `QuestionCandidate`；
  4. 运行 schema、重复、来源、答案、敏感和质量校验；
  5. 人工逐题或批量审核；
  6. 批准后创建正式 QuestionRevision。
- Candidate 不是正式题目，不得被考试抽题。
- 每个 Candidate 保存 prompt revision、model policy、source anchors、generation input hash 和校验结果。
- 支持编辑、拒绝、退回、重新生成和批量处理；所有动作审计。

### R8. Question Governance

- 正式 Question 具有稳定身份和不可变 QuestionRevision。
- 状态至少覆盖 draft、in_review、approved/published、archived、rejected。
- 题型首发支持单选、多选、判断和短答；若现有产品只用部分题型，以契约允许、标准包按实际启用。
- 题目记录难度、能力映射、来源、答案/rubric、解释和适用范围。
- 去重使用确定性指纹 + 相似度建议；人工拥有最终处理权。
- 修改已被 QuizRevision 引用的题目必须创建新修订，不原地改历史试卷。

### R9. Quiz And Exam Revision

- Quiz 是稳定身份，QuizRevision 冻结题目池、抽题规则、通过阈值、尝试策略、反馈策略和时间限制。
- 发布 PathRevision 只能引用已发布 QuizRevision。
- 抽题在 Attempt 开始时生成并冻结 snapshot。
- 单选/多选/判断使用确定性评分。
- 短答通过持久化 AI 任务评分，输出结构化 rubric evidence；AI 失败时 Attempt 为待处理，不伪装成零分或成功。
- 通过阈值、重试间隔、最大尝试等可配置规则不写死在页面。

### R10. Quiz Experience

- 开始前说明题量、规则、通过标准、可重试策略和预计时长。
- 进行中自动保存；重复提交由 client token 和 attempt version 防护。
- 提交后展示用户可理解的结果、错因、来源和下一步；不泄露隐藏题库或完整答案键。
- 未通过时根据能力映射生成补学/补练建议。
- 长耗时短答评分进入任务状态页或当前 Activity Workspace，支持离开后继续处理。

### R11. Standard Training Pack

- 提供一套可发布、可重复 seed 的新人销售基础训练标准包。
- 至少覆盖父任务确认的七类基础能力：
  - 产品知识；
  - 客户理解；
  - 需求发现；
  - 价值表达；
  - 异议处理；
  - 流程与合规；
  - 沟通结构。
- 标准包包含 PathRevision、Stage、Lesson、Quiz、来源、能力映射和默认规则。
- seed 不产生 mock/test/internal 文案到普通用户界面。
- 重复执行 seed 不产生重复业务身份或漂移的已发布修订。

### R12. Clean Cut

- 收口重复的新人学习入口和旧路径写入。
- 删除或禁用已被替代的旧 Path/Phase/Module 写权威、旧题目确认链路和直接创建正式题目的 AI 路径。
- 只保留明确的迁移脚本或只读审计视图；不保留永久兼容 Facade。
- 切片结束时，Lesson/Quiz 新链路是唯一首发权威。

## API Surface

- 学员：
  - 获取我的 Journey；
  - 获取 Activity Workspace；
  - 开始/保存/提交 Lesson Attempt；
  - 开始/保存/提交 Quiz Attempt；
  - 查询异步评分任务与结果。
- 管理：
  - Path/Revision 草稿、校验、预览、发布；
  - Cohort/Enrollment 分配与迁移预览；
  - Source/LearningUnit 修订；
  - GenerationBatch/Candidate 审核；
  - Question/Quiz 修订与发布。

## Acceptance Criteria

- [x] 一个新 Enrollment 固定在指定 PathRevision，发布新版后不自动变化。
- [x] 显式迁移提供影响预览、审计和逐项失败结果。
- [x] 学员从单一入口看到当前任务、主操作、阻塞原因和下一步。
- [x] Lesson 支持保存、恢复、完成、失效和重新学习。
- [x] AI 生成内容只能进入 Candidate，人工批准后才成为正式题目。
- [x] 每道正式题可追溯到来源修订、Anchor、审核人和题目修订。
- [x] Quiz Attempt 开始后题目和规则快照冻结。
- [x] 确定性题型同步评分；短答异步评分失败时不会错误完成 Attempt。
- [x] Quiz 结果通过统一 Outcome 写入 Journey 和能力证据。
- [x] 标准训练包可在干净数据库重复 seed，结果稳定。
- [x] 旧 Lesson/Quiz 写路径和重复学员入口已删除或明确只读。
- [x] 跨组织、未发布修订、无权限和 stale version 均被后端拒绝。

### Acceptance Evidence（2026-07-17）

- 冻结与迁移：`test_enrollment_freeze.py` 证明发布不改 Enrollment，preview/confirm 审计、幂等与权限成立；PostgreSQL 集成测试证明并发版本变化产生逐项失败而非部分伪成功。
- 单入口与纵向闭环：`test_route_contract.py` 锁定唯一 Journey/Workspace/command surface；`test_activity_application.py` 从同一 Journey 完成 Lesson、解锁 Quiz、提交并回到完成投影。
- Journey 状态：`test_journey_projection.py` 覆盖未分配零写、冻结修订、唯一主操作、阻塞与未通过补学；前端 Journey/Workspace 组件测试覆盖用户语言和主操作。
- Lesson：`test_lesson_runtime.py` 覆盖保存/恢复、真实检查点、stale/scope、完成、失效与重新学习；管理失效同时保留历史 Outcome。
- 题目治理：`test_source_question_governance.py` 覆盖来源/Anchor、不可变修订、Candidate-only AI、确定性门禁、编辑/拒绝/替代/批量部分成功、人工批准和人工题目版本化。
- Quiz：`test_quiz_runtime.py` 与 PostgreSQL 集成测试覆盖冻结题目/规则、确定性评分、重复提交、短答答案先保存、Provider 失败不完成、成功后规范化 Outcome。
- 能力衔接：Quiz Outcome 保存来源引用、能力 keys、评分 lineage、confidence，并在同事务追加 `ActivityOutcomeRecorded`；Journey 立即消费 Outcome，Slice 5 以 `outcome_id` 幂等追加正式 CompetencyEvidence，Slice 2 不伪造尚不存在的 Evidence ID。
- 标准包：SQLite 单元和干净 PostgreSQL 隔离 schema 均完成首次安装、重复安装、verify-only，稳定覆盖七项能力且不含 Realtime。
- Clean cut 与安全：OpenAPI contract 证明旧 Module/Lesson/Quiz/Realtime/Path writer 未挂载；前端入口/导航/重定向和 no-legacy-authority 测试证明旧写入口不可达；权限、跨组织、未发布和 stale 测试均由后端拒绝。

## Verification

- 状态机测试：PathRevision、Enrollment、LessonAttempt、QuizAttempt、QuestionCandidate、QuestionRevision。
- PostgreSQL 集成测试：并发开始 Attempt、重复提交、冻结 snapshot、版本迁移。
- AI fake 集成：生成 Candidate、短答评分、schema invalid、Provider 超时。
- 契约测试：OpenAPI、ViewModel、错误映射和权限。
- E2E：首次进入 -> 学习 -> 测验通过；测验未通过 -> 补学 -> 重试。
- seed 幂等和空库启动验证。

## Definition Of Done

- Lesson 和 Quiz 形成可独立上线的首个纵向闭环。
- Path、内容、题库、考卷和 Enrollment 的修订语义一致。
- 所有正式对象都有来源、审核、发布和审计。
- 前端不计算业务门禁，不泄露内部字段。
- 旧权威清理完成，相关文档和 Spec 更新。

## Out Of Scope

- 不实现录音转写与评分。
- 不实现 AI Coach。
- 不实现正式 Readiness 人工复核。
- 不实现 Realtime 客户语音对练。
- 不建设通用 LMS 或任意课程市场。

## Risk And Rollback

- 风险等级：P1。
- 主要风险是路径修订和 Enrollment 绑定语义改变。
- 发布前对开发数据执行 dry-run 转换并输出影响数量。
- 回滚以 PathRevision 和 QuizRevision 不可变快照为基础；新发布失败时旧修订继续有效。
