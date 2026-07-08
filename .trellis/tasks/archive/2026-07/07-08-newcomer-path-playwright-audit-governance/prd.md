# 新人训练路径 Playwright 全量审计治理 PRD

## 背景

新人训练路径前台和后台已经出现信息架构不清、功能散落、旧入口并存、录音能力与载体混淆、学习文章分类命名过窄、配置跳转过多等问题。用户希望按照 Trellis 全流程完成一次可验证的治理：先审计真实页面，再修复 P0/P1/P2 问题，最后用 Playwright、单测、类型检查和构建闭环。

## 目标

- 只治理新人训练路径前台与后台管理，不涉及销售训练、实时对练、知识库、用户管理等无关模块。
- 管理后台按前台业务任务组织，而不是按数据库表或历史页面堆叠。
- 录音相关能力统一归入“录音管理”，在一个上下文内完成场景、材料、评分标准、AI Prompt、提交记录、评分结果等配置。
- 学习文章从“商务礼仪文章”升级为“学习专题”治理思路，商务礼仪只是一个专题，后续可扩展销售技巧、客户质疑、产品知识等专题。
- 管理员尽量通过选择、快速新建、自动关联完成配置；必须填写时提供标签、帮助文本、校验、失败反馈和审计线索。
- 前台只显示管理员已配置且可用的学习/录音/考试内容；学习专题可给正常得分展示，但不阻塞后续关卡。
- 保留旧路由兼容，避免已有书签、内部链接和历史记录失效。
- 建立 Playwright 审计规格和截图证据，覆盖页面可用性、空/错/权限状态、主操作、控制台错误、网络错误、移动端溢出和内部字段泄露。

## 范围

### 前台学习端

- `/sales-trainer`
- `/sales-trainer/learn/hub`
- `/sales-trainer/learning-topics/business-etiquette`
- `/sales-trainer/learn/[unitId]`
- `/sales-trainer/quiz/[unitId]`
- `/sales-trainer/quiz/result/[attemptId]`
- `/sales-trainer/audio/[unitId]`
- `/sales-trainer/audio/result/[submissionId]`
- 兼容入口：`/sales-trainer/business-skills`、`/sales-trainer/business-skills/exam`、`/sales-trainer/business-skills/coach`

### 后台管理端

- 工作台：`/admin/sales-trainer`
- 录音管理：`/admin/sales-trainer/audio`、`/admin/sales-trainer/audio/[scenarioSlug]`、`/admin/sales-trainer/audio/materials`、`/admin/sales-trainer/audio/score-standards`、`/admin/sales-trainer/audio/submissions`、`/admin/sales-trainer/audio/results`
- 学习专题：`/admin/sales-trainer/learning-topics`、`/admin/sales-trainer/learning-topics/business-etiquette`、`/admin/sales-trainer/learning-topics/import`、`/admin/sales-trainer/learning-topics/capabilities`、`/admin/sales-trainer/learning-topics/questions`、`/admin/sales-trainer/learning-topics/questions/new`、`/admin/sales-trainer/learning-topics/questions/drafts`、`/admin/sales-trainer/learning-topics/questions/quiz-preview`、`/admin/sales-trainer/learning-topics/papers`、`/admin/sales-trainer/learning-topics/papers/new`
- 路径验收：`/admin/sales-trainer/paths`、`/admin/sales-trainer/units`、`/admin/sales-trainer/ai-coach`、`/admin/sales-trainer/readiness`、`/admin/sales-trainer/training-records`、`/admin/sales-trainer/analytics`
- 治理：`/admin/sales-trainer/settings`、`/admin/sales-trainer/operation-logs`
- 旧路由兼容：`/admin/sales-trainer/articles`、`/admin/sales-trainer/materials`、`/admin/sales-trainer/score-standards`、`/admin/sales-trainer/papers`、`/admin/sales-trainer/questions`、`/admin/sales-trainer/audio-submissions`、`/admin/sales-trainer/score-results`、`/admin/sales-trainer/training-tasks`

## 排除范围

- `/training/sales`
- `/practice/*`
- `/admin/business-rules/sales-trainer-phase2`
- 销售训练、实时角色扮演、课程中心、知识库、用户权限管理等非新人训练路径页面
- 后端大规模 schema 重构，除非 Playwright 审计暴露了必须修复的契约问题

## 用户任务

- 管理员打开新人训练后台后，3 秒内知道可管理的模块、当前模块用途、主要操作和下一步。
- 管理员在录音管理内完成“新增录音任务/场景、绑定材料、选择评分标准、配置 AI Prompt、查看提交和结果”。
- 管理员在学习专题内完成“专题、单元、文章章节、题库、考卷、前台展示开关”的闭环配置。
- 学员只看到已经发布并可用的训练路径，能学习、考试、上传录音、查看结果，不看到后台字段或测试数据。

## 成功标准

- 所有范围内页面 Playwright 可访问，不能 404、白屏、无限加载或出现未处理控制台错误。
- 每个页面至少有清晰标题、当前任务说明、主操作或明确空状态、错误恢复入口。
- 移动端 390px 宽度无整页水平溢出。
- 页面不暴露 `E2E`、`mock`、`seed`、`Prompt`、`traceId`、`workflow`、数据库主键、原始枚举等内部字段，除非位于管理员调试或审计详情。
- 录音评分标准不再作为孤立信息架构主入口，后台主导航应体现其属于录音管理。
- 学习专题不再将“商务礼仪文章”作为唯一长期概念，旧入口兼容但新语义清晰。
- P0/P1/P2 findings 全部修复并记录回归验证；P3 可记录为后续事项。
- 运行并记录：Playwright、相关 Vitest、类型检查、lint 或构建；无法运行项必须说明原因。

## 风险等级

本任务整体为 P1：涉及管理后台信息架构、页面路由兼容、前台学习路径、AI 录音评分配置和审计证据。默认不做破坏性数据迁移，所有旧入口需兼容。

## 发布与回滚

- 发布：跟随前端应用发布。若只涉及前端路由和组件，回滚为撤销本次提交。
- 旧入口：保留兼容导航或重定向，不删除历史页面文件，避免线上书签断裂。
- 配置风险：新增或调整配置入口必须使用现有 API 契约和默认值兜底。
- AI 风险：Prompt、评分标准、模型参数必须保持管理员可见、可编辑、可追踪，不把 AI 输出标记为已验证事实。
