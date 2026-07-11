# API 完整文档 —— 前后端接口全景映射

> 生成时间：2026-06-09
> 说明：本文档覆盖后端所有已实现的 HTTP API、WebSocket 端点，以及前端所有已知的 API 调用点和页面交互。标注了前后端对应关系，以及可能存在的前后端不匹配风险。

---

## 目录

1. [后端 HTTP API 总览](#一后端-http-api-总览)
2. [后端 WebSocket 端点](#二后端-websocket-端点)
3. [前端 API 调用映射](#三前端-api-调用映射)
4. [前端页面路由与交互清单](#四前端页面路由与交互清单)
5. [前后端对应关系矩阵](#五前后端对应关系矩阵)
6. [潜在不匹配与风险](#六潜在不匹配与风险)

---

## 一、后端 HTTP API 总览

### 1.1 认证模块 (auth)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/auth/providers` | GET | 公开 | 获取可用认证源 | `api.auth.getProviders()` |
| `/api/v1/auth/login` | POST | CSRF豁免 | 邮箱密码登录 | `api.auth.login({email,password})` |
| `/api/v1/auth/dev-login` | POST | CSRF豁免 | 开发环境快捷登录 | `api.auth.devLogin()` |
| `/api/v1/auth/logout` | POST | 需登录 | 登出 | `api.auth.logout()` |
| `/api/v1/auth/forgot-password` | POST | CSRF豁免,限流1次/分 | 忘记密码 | `api.auth.forgotPassword()` |
| `/api/v1/auth/reset-password` | POST | CSRF豁免 | 重置密码 | `api.auth.resetPassword()` |
| `/api/v1/auth/wecom/start` | GET | 公开 | 企微OAuth发起 | 直接跳转 |
| `/api/v1/auth/wecom/callback` | GET | 公开 | 企微回调 | 浏览器重定向 |

### 1.2 用户模块 (users)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/users/me` | GET | admin/user | 获取当前用户 | `api.user.getMe()` |
| `/api/v1/users/me` | PATCH | admin/user | 更新用户资料 | `api.user.updateMe()` |
| `/api/v1/users/me/training-preferences` | GET | admin/user | 获取训练偏好 | `api.user.getTrainingPreferences()` |
| `/api/v1/users/me/training-preferences` | PUT | admin/user | 更新训练偏好 | `api.user.updateTrainingPreferences()` |
| `/api/v1/users/me/history` | GET | admin/user | 个人训练历史 | `api.user.getHistory()` |
| `/api/v1/users/me/growth-dashboard` | GET | admin/user | 成长仪表盘 | `api.user.getGrowthDashboard()` |
| `/api/v1/users/me/notifications` | GET | admin/user | 通知列表 | `api.user.getNotifications()` |
| `/api/v1/users/me/notifications/:id/read` | POST | admin/user | 标记已读 | `api.user.markNotificationRead()` |
| `/api/v1/users/me/achievements` | GET | admin/user | 成就列表 | `api.user.getAchievements()` |
| `/api/v1/users/me/goals` | GET | admin/user | 目标列表 | `api.user.getGoals()` |

### 1.3 训练分类 (training)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/training/categories` | GET | admin/user | 训练分类列表 | `api.training.getCategories()` |
| `/api/v1/training/categories/sales/agents` | GET | admin/user | 销售智能体列表 | `api.training.getSalesAgents()` |
| `/api/v1/training/categories/presentation/agents` | GET | admin/user | 演讲智能体列表 | `api.training.getPresentationAgents()` |

### 1.4 场景模块 (scenarios)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/scenarios` | GET | admin/user | 场景列表 | `api.scenarios.getList()` |
| `/api/v1/scenarios/sales/runtime-contract` | GET | admin/user | 销售场景运行时契约 | `api.scenarios.getSalesRuntimeContract()` |
| `/api/v1/scenarios/sales/personas` | GET | admin/user | 销售角色画像选项 | `api.scenarios.getSalesPersonas()` |
| `/api/v1/scenarios/:id` | GET | admin/user | 场景详情 | `api.scenarios.getById()` |

### 1.5 练习会话 (practice)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/practice/sessions` | POST | admin/user | **创建练习会话** | `api.practice.createSession()` |
| `/api/v1/practice/sessions/:id` | GET | admin/user | 获取会话运行时状态 | `api.practice.getSession()` |
| `/api/v1/practice/sessions/:id/runtime-preflight` | GET | admin/user | 运行前预检 | `api.practice.runtimePreflight()` |
| `/api/v1/practice/sessions/:id/lifecycle` | POST | admin/user | 生命周期控制(start/pause/resume/end) | `api.practice.lifecycle()` |
| `/api/v1/practice/sessions/:id/audio-upload-urls` | POST | admin/user | 获取音频分段上传URL | `api.practice.getAudioUploadUrls()` |
| `/api/v1/practice/sessions/:id/audio-segments` | POST | admin/user | 注册音频分段 | `api.practice.registerAudioSegment()` |
| `/api/v1/practice/sessions/:id/audio-segments/failure` | POST | admin/user | 上报音频分段失败 | `api.practice.reportAudioFailure()` |

### 1.6 会话数据与报告 (sessions)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/sessions` | GET | admin/user | 会话列表（分页/排序） | `api.sessions.getList()` |
| `/api/v1/sessions/stats` | GET | admin/user | 会话统计 | `api.sessions.getStats()` |
| `/api/v1/practice/sessions/:id/report` | GET | admin/user | 练习报告 | `api.sessions.getReport()` |
| `/api/v1/practice/sessions/:id/report-trends` | GET | admin/user | 报告趋势 | `api.sessions.getReportTrends()` |
| `/api/v1/practice/sessions/:id/next-recommendation` | GET | admin/user | 下一步推荐 | `api.sessions.getNextRecommendation()` |
| `/api/v1/practice/sessions/:id/knowledge-check` | GET | admin/user | 知识检查诊断 | `api.sessions.getKnowledgeCheck()` |
| `/api/v1/sessions/:id/enhanced-report` | GET | admin/user | 增强报告 | `api.sessions.getEnhancedReport()` |
| `/api/v1/sessions/:id/replay` | GET | admin/user | 回放数据 | `api.sessions.getReplay()` |
| `/api/v1/sessions/:id/messages` | GET | admin/user | 消息列表（分页） | `api.sessions.getMessages()` |
| `/api/v1/sessions/:id/messages/:msgId` | GET | admin/user | 单条消息详情 | `api.sessions.getMessage()` |
| `/api/v1/sessions/:id/highlights` | GET | admin/user | 高光片段 | `api.sessions.getHighlights()` |
| `/api/v1/sessions/:id/highlight-review` | GET | admin/user | 高光复习 | `api.sessions.getHighlightReview()` |
| `/api/v1/sessions/:id/highlight-review` | PUT | admin/user | 保存高光复习 | `api.sessions.saveHighlightReview()` |
| `/api/v1/sessions/:id/highlight-review/shares` | POST | admin/user | 创建分享 | `api.sessions.createShare()` |
| `/api/v1/sessions/:id/highlight-review/shares/:id/revoke` | POST | admin/user | 撤销分享 | `api.sessions.revokeShare()` |
| `/api/v1/sessions/highlight-reviews/shared/:token` | GET | 公开 | 公开分享访问 | 直接URL访问 |
| `/api/v1/sessions/:id/audio/:messageId` | GET | admin/user | 消息音频Blob | 直接 fetch |
| `/api/v1/sessions/:id/audio-segments/:seq` | GET | admin/user | 分段音频Blob | 直接 fetch |

### 1.7 Agent 用户端 (agents)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/agents` | GET | admin/user | 已发布Agent列表 | `api.agents.getList()` |
| `/api/v1/agents/:id` | GET | admin/user | Agent详情 | `api.agents.getById()` |
| `/api/v1/agents/:id/personas` | GET | admin/user | Agent关联Personas | `api.agents.getPersonas()` |
| `/api/v1/personas` | GET | admin/user | 活跃Persona列表 | `api.personas.getList()` |
| `/api/v1/personas/:id` | GET | admin/user | Persona详情 | `api.personas.getById()` |
| `/api/v1/agent-personas` | GET | admin/user | Agent-Persona关联列表 | `api.agentPersonas.getList()` |

### 1.8 PPT 管理 (presentations)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/presentations` | GET | admin/user | PPT列表 | `api.presentations.getList()` |
| `/api/v1/presentations` | POST | admin/user | 上传PPT | `api.presentations.upload()` |
| `/api/v1/presentations/:id` | GET | admin/user | PPT详情 | `api.presentations.getById()` |
| `/api/v1/presentations/:id/replace` | POST | admin | 替换PPT | `api.presentations.replace()` |
| `/api/v1/presentations/:id` | DELETE | admin | 删除PPT | `api.presentations.delete()` |
| `/api/v1/presentations/:id/progress` | GET | admin/user | 阅读进度 | `api.presentations.getProgress()` |
| `/api/v1/presentations/:id/progress` | PUT | admin/user | 保存进度 | `api.presentations.saveProgress()` |
| `/api/v1/presentations/:id/pages` | GET | admin/user | 页面列表 | `api.presentations.getPages()` |
| `/api/v1/presentations/:id/pages/:n/thumbnail` | GET | admin/user | 缩略图Blob | 直接 fetch |
| `/api/v1/presentations/:id/pages/:n/talking-points` | GET | admin/user | 演讲要点 | `api.presentations.getTalkingPoints()` |
| `/api/v1/presentations/:id/pages/:n/talking-points` | POST | admin/user | 添加要点 | `api.presentations.addTalkingPoint()` |
| `/api/v1/presentations/:id/pages/:n/talking-points/:id` | PUT | admin/user | 更新要点 | `api.presentations.updateTalkingPoint()` |
| `/api/v1/presentations/:id/pages/:n/talking-points/:id` | DELETE | admin/user | 删除要点 | `api.presentations.deleteTalkingPoint()` |
| `/api/v1/presentations/:id/forbidden-words` | GET | admin/user | 禁用词 | `api.presentations.getForbiddenWords()` |
| `/api/v1/presentations/:id/forbidden-words` | POST | admin/user | 添加禁用词 | `api.presentations.addForbiddenWord()` |
| `/api/v1/admin/forbidden-words/:id` | DELETE | admin | 删除禁用词 | `api.presentations.deleteForbiddenWord()` |

### 1.9 学习路径 (learning path)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/curriculum-practice/learning-path/me` | GET | admin/user | 我的学习路径 | `api.learningPath.getMyPath()` |
| `/api/v1/curriculum-practice/learning-path/me/next-task` | GET | admin/user | 下一个任务 | `api.learningPath.getNextTask()` |

### 1.10 学习内容 (study)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/curriculum-practice/study/learning-contents/:id` | GET | admin/user | 学习内容详情 | `api.learnerStudy.getContent()` |
| `/api/v1/curriculum-practice/study/learning-contents/:id/chapters/:id/complete` | POST | admin/user | 完成章节 | `api.learnerStudy.completeChapter()` |
| `/api/v1/curriculum-practice/study/learning-contents/:id/start-exam` | POST | admin/user | 开始考试 | `api.learnerStudy.startExam()` |
| `/api/v1/curriculum-practice/study/exam-sessions/:id/report` | GET | admin/user | 考试报告 | `api.learnerStudy.getExamReport()` |

### 1.11 销售训练 — 学员端 (sales-trainer)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/sales-trainer/units` | GET | admin/user | 训练单元列表 | `api.salesTrainer.getUnits()` |
| `/api/v1/sales-trainer/paths` | GET | admin/user | 训练路径列表 | `api.salesTrainer.getPaths()` |
| `/api/v1/sales-trainer/units/:id` | GET | admin/user | 单元详情 | `api.salesTrainer.getUnit()` |
| `/api/v1/sales-trainer/units/:id/brief` | GET | admin/user | 单元简报 | `api.salesTrainer.getUnitBrief()` |
| `/api/v1/sales-trainer/quiz-attempts` | POST | admin/user | 提交做题 | `api.salesTrainer.submitQuiz()` |
| `/api/v1/sales-trainer/quiz-attempts/:id` | GET | admin/user | 做题记录详情 | `api.salesTrainer.getQuizAttempt()` |
| `/api/v1/sales-trainer/audio-submissions/upload-url` | POST | admin/user | 获取音频上传URL | `api.salesTrainer.getAudioUploadUrl()` |
| `/api/v1/sales-trainer/audio-submissions/upload` | POST | admin/user | 音频文件上传 | `api.salesTrainer.uploadAudio()` |
| `/api/v1/sales-trainer/audio-submissions` | POST | admin/user | 注册音频提交 | `api.salesTrainer.registerAudioSubmission()` |
| `/api/v1/sales-trainer/audio-submissions/:id` | GET | admin/user | 音频提交详情 | `api.salesTrainer.getAudioSubmission()` |
| `/api/v1/sales-trainer/audio-submissions/:id/file` | GET | admin/user | 音频文件下载 | 直接 fetch |

### 1.12 新人训练 (newcomer-training)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/newcomer-training/modules/:key/article` | GET | admin/user | 模块文章 | `api.newcomerTraining.getArticle()` |
| `/api/v1/newcomer-training/modules/:key/article-progress` | GET | admin/user | 文章阅读进度 | `api.newcomerTraining.getArticleProgress()` |
| `/api/v1/newcomer-training/modules/:key/article-progress` | POST | admin/user | 完成章节 | `api.newcomerTraining.completeArticleChapter()` |
| `/api/v1/newcomer-training/papers/:id` | GET | admin/user | 试卷详情 | `api.newcomerTraining.getPaper()` |
| `/api/v1/newcomer-training/paper-attempts` | POST | admin/user | 提交试卷 | `api.newcomerTraining.submitPaperAttempt()` |
| `/api/v1/newcomer-training/ai-coach/sessions` | POST | admin/user | **启动AI Coach会话** | `api.newcomerTraining.createAICoachSession()` |
| `/api/v1/newcomer-training/ai-coach/sessions/:id` | GET | admin/user | AI Coach会话状态 | `api.newcomerTraining.getAICoachSession()` |
| `/api/v1/newcomer-training/ai-coach/sessions/:id/turns/:turnId` | POST | admin/user | 提交AI Coach答题 | `api.newcomerTraining.submitAICoachTurn()` |

### 1.13 评估与报告 (evaluation)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/evaluation/sessions/:id/report` | GET | admin/user | 获取已有综合报告 | `api.evaluation.getReport()` |
| `/api/v1/evaluation/sessions/:id/report` | POST | admin/user | AI生成综合报告 | `api.evaluation.generateReport()` |
| `/api/v1/evaluation/sessions/:id/feedback` | GET | admin/user | 实时评估反馈列表 | `api.evaluation.getFeedback()` |

### 1.14 督导模块 (supervisor)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/supervisor/team/reports` | GET | admin | 团队报告列表 | `api.supervisor.getTeamReports()` |
| `/api/v1/supervisor/certification-review-queue` | GET | admin | 认证复核队列 | `api.supervisor.getCertificationQueue()` |
| `/api/v1/supervisor/team/insights` | GET | admin | 团队洞察 | `api.supervisor.getTeamInsights()` |
| `/api/v1/supervisor/team/insights/:learnerId/details` | GET | admin | 学员详情 | `api.supervisor.getLearnerDetails()` |
| `/api/v1/supervisor/reviews` | GET | admin | 督导评审列表 | `api.supervisor.getReviews()` |
| `/api/v1/supervisor/reviews` | POST | admin | 创建评审 | `api.supervisor.createReview()` |
| `/api/v1/supervisor/reviews/:id/decision` | PATCH | admin | 更新评审决策 | `api.supervisor.updateDecision()` |
| `/api/v1/supervisor/reviews/:id/score-calibrations` | POST | admin | 评分校准 | `api.supervisor.createCalibration()` |
| `/api/v1/supervisor/report-view/:sessionId` | GET | admin | 训练报告视图 | `api.supervisor.getReportView()` |
| `/api/v1/retraining/tasks` | GET | admin | 复训任务列表 | `api.retraining.getTasks()` |
| `/api/v1/retraining/tasks` | POST | admin | 创建复训任务 | `api.retraining.createTask()` |
| `/api/v1/retraining/tasks/:id/start-session` | POST | admin | 从复训任务启动会话 | `api.retraining.startSession()` |
| `/api/v1/retraining/tasks/:id/complete-with-session` | POST | admin | 完成复训任务 | `api.retraining.completeTask()` |

### 1.15 支持模块 (support)

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/support/runtime/overview` | GET | admin/support | 运行时健康概览 | `api.support.getRuntimeOverview()` |
| `/api/v1/support/runtime/faults` | GET | admin/support | 运行时故障摘要 | `api.support.getRuntimeFaults()` |

### 1.16 Admin — Agent 管理

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/agents` | GET/POST | admin | Agent列表/创建 | `api.admin.agents.getList()` / `create()` |
| `/api/v1/admin/agents/import` | POST | admin | 导入Agent | `api.admin.agents.import()` |
| `/api/v1/admin/agents/:id` | GET/PUT/DELETE | admin | Agent CRUD | `api.admin.agents.getById()` / `update()` / `delete()` |
| `/api/v1/admin/agents/:id/publish` | POST | admin | 发布Agent | `api.admin.agents.publish()` |
| `/api/v1/admin/agents/:id/archive` | POST | admin | 归档Agent | `api.admin.agents.archive()` |
| `/api/v1/admin/agents/:id/unpublish` | POST | admin | 取消发布 | `api.admin.agents.unpublish()` |
| `/api/v1/admin/agents/:id/personas` | GET/POST | admin | Agent-Persona关联 | `api.admin.agents.managePersonas()` |
| `/api/v1/admin/personas` | GET/POST | admin | Persona列表/创建 | `api.admin.personas.getList()` / `create()` |
| `/api/v1/admin/personas/:id` | GET/PUT/DELETE | admin | Persona CRUD | `api.admin.personas.getById()` / `update()` / `delete()` |
| `/api/v1/admin/personas/:id/clone` | POST | admin | 复制Persona | `api.admin.personas.clone()` |
| `/api/v1/admin/personas/policy-health` | GET | admin | Policy Health审计 | `api.admin.personas.getPolicyHealth()` |
| `/api/v1/admin/personas/batch-audit` | POST | admin | 批量Policy审计 | `api.admin.personas.batchAudit()` |
| `/api/v1/admin/personas/:id/policy` | GET/PUT | admin | Persona Policy读写 | `api.admin.personas.getPolicy()` / `updatePolicy()` |
| `/api/v1/admin/agent-personas` | GET/POST | admin | AgentPersona关联管理 | `api.admin.agentPersonas.getList()` / `create()` |
| `/api/v1/admin/agent-personas/:id` | GET/PUT/DELETE | admin | AgentPersona CRUD | `api.admin.agentPersonas.getById()` / `update()` / `delete()` |

### 1.17 Admin — 知识库管理

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/knowledge-bases` | GET/POST | admin | 知识库列表/创建 | `api.admin.knowledge.getBases()` / `createBase()` |
| `/api/v1/admin/knowledge-bases/:id` | GET/PUT/DELETE | admin | 知识库CRUD | `api.admin.knowledge.getBase()` / `updateBase()` / `deleteBase()` |
| `/api/v1/admin/knowledge-bases/:id/documents` | GET/POST | admin | 文档管理 | `api.admin.knowledge.getDocuments()` / `uploadDocument()` |
| `/api/v1/admin/knowledge-bases/:id/documents/:docId` | GET/DELETE | admin | 文档CRUD | `api.admin.knowledge.getDocument()` / `deleteDocument()` |

### 1.18 Admin — 配置资产管理

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/config-assets/export` | POST | admin | 批量导出 | `api.admin.configAssets.export()` |
| `/api/v1/admin/config-assets/import` | POST | admin | 批量导入 | `api.admin.configAssets.import()` |
| `/api/v1/admin/config-assets/import-preview` | POST | admin | 导入预览 | `api.admin.configAssets.importPreview()` |
| `/api/v1/admin/config-assets/audit-log` | GET | admin | 导入审计日志 | `api.admin.configAssets.getAuditLog()` |
| `/api/v1/admin/config-bundles` | GET/POST | admin | ConfigBundle列表/创建 | `api.admin.configBundles.getList()` / `create()` |
| `/api/v1/admin/config-bundles/:bundleKey` | GET/PUT/DELETE | admin | ConfigBundle CRUD | `api.admin.configBundles.getByKey()` / `update()` / `delete()` |
| `/api/v1/admin/config-bundles/:bundleKey/draft` | POST | admin | 创建Draft | `api.admin.configBundles.createDraft()` |
| `/api/v1/admin/config-bundles/:bundleKey/publish` | POST | admin | 发布 | `api.admin.configBundles.publish()` |
| `/api/v1/admin/config-bundles/:bundleKey/rollback` | POST | admin | 回滚 | `api.admin.configBundles.rollback()` |
| `/api/v1/admin/config-bundles/:bundleKey/disable` | POST | admin | 禁用 | `api.admin.configBundles.disable()` |
| `/api/v1/admin/config-bundles/:bundleKey/preview` | GET | admin | 预览 | `api.admin.configBundles.preview()` |
| `/api/v1/admin/config-bundles/:bundleKey/versions` | GET | admin | 版本历史 | `api.admin.configBundles.getVersions()` |
| `/api/v1/admin/config-bundles/:bundleKey/audit-log` | GET | admin | 审计日志 | `api.admin.configBundles.getAuditLog()` |

### 1.19 Admin — 模型配置

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/model-configs` | GET/POST | admin | AI模型配置列表/创建 | `api.admin.modelConfigs.getList()` / `create()` |
| `/api/v1/admin/model-configs/:id` | GET/PUT/DELETE | admin | 模型配置CRUD | `api.admin.modelConfigs.getById()` / `update()` / `delete()` |
| `/api/v1/admin/model-configs/:id/test` | POST | admin | 连通性测试 | `api.admin.modelConfigs.test()` |
| `/api/v1/admin/model-configs/:id/set-default` | POST | admin | 设为默认 | `api.admin.modelConfigs.setDefault()` |

### 1.20 Admin — 语音运行时

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/voice-runtime-profiles` | GET/POST | admin | 语音运行时预设 | `api.admin.voiceRuntime.getProfiles()` / `createProfile()` |
| `/api/v1/admin/voice-runtime-profiles/:id` | GET/PUT/DELETE | admin | 预设CRUD | `api.admin.voiceRuntime.getProfile()` / `updateProfile()` / `deleteProfile()` |
| `/api/v1/admin/voice-runtime-profiles/:id/set-default` | POST | admin | 设为默认 | `api.admin.voiceRuntime.setDefault()` |

### 1.21 Admin — 评分规则集

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/evaluation/admin/scoring-rulesets` | GET/POST | admin | 评分规则集 | `api.admin.scoringRulesets.getList()` / `create()` |
| `/api/v1/evaluation/admin/scoring-rulesets/:id` | GET/PUT/DELETE | admin | 规则集CRUD | `api.admin.scoringRulesets.getById()` / `update()` / `delete()` |

### 1.22 Admin — 题库管理

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/curriculum/test-bank/categories` | GET/POST | admin | 题目分类 | `api.testBank.getCategories()` / `createCategory()` |
| `/api/v1/curriculum/test-bank/categories/:id` | PUT/DELETE | admin | 分类CRUD | `api.testBank.updateCategory()` / `deleteCategory()` |
| `/api/v1/curriculum/test-bank/questions` | GET/POST | admin | 题目列表/创建 | `api.testBank.getQuestions()` / `createQuestion()` |
| `/api/v1/curriculum/test-bank/questions/:id` | GET/PUT | admin | 题目详情/更新 | `api.testBank.getQuestion()` / `updateQuestion()` |
| `/api/v1/curriculum/test-bank/questions/:id/publish` | POST | admin | 发布题目 | `api.testBank.publishQuestion()` |
| `/api/v1/curriculum/test-bank/questions/:id/archive` | POST | admin | 归档题目 | `api.testBank.archiveQuestion()` |
| `/api/v1/curriculum/test-bank/imports` | POST | admin | 批量导入题目 | `api.testBank.importQuestions()` |
| `/api/v1/curriculum/test-bank/imports/:id` | GET | admin | 导入任务状态 | `api.testBank.getImportStatus()` |
| `/api/v1/curriculum/test-bank/generation/preview` | POST | admin | AI生成题目预览 | `api.testBank.previewGeneration()` |
| `/api/v1/curriculum/test-bank/generation/confirm` | POST | admin | AI生成题目确认 | `api.testBank.confirmGeneration()` |

### 1.23 Admin — 学习内容管理

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/curriculum/learning-contents` | GET/POST | admin | LearningContent列表/创建 | `api.admin.learningContents.getList()` / `create()` |
| `/api/v1/curriculum/learning-contents/:id` | GET/PUT/DELETE | admin | CRUD | `api.admin.learningContents.getById()` / `update()` / `delete()` |
| `/api/v1/curriculum/learning-contents/:id/chapters` | POST | admin | 添加章节 | `api.admin.learningContents.addChapter()` |
| `/api/v1/curriculum/learning-contents/:id/chapters/reorder` | PUT | admin | 重排章节 | `api.admin.learningContents.reorderChapters()` |
| `/api/v1/curriculum/learning-contents/:id/chapters/:chapterId` | PUT/DELETE | admin | 章节CRUD | `api.admin.learningContents.updateChapter()` / `deleteChapter()` |
| `/api/v1/curriculum/learning-contents/:id/publish` | POST | admin | 发布 | `api.admin.learningContents.publish()` |
| `/api/v1/curriculum/learning-contents/:id/archive` | POST | admin | 归档 | `api.admin.learningContents.archive()` |

### 1.24 Admin — 课程练习配置

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/curriculum-practice/templates` | GET/POST | admin | PracticeTemplate列表/创建 | `api.admin.curriculumPractice.getTemplates()` / `createTemplate()` |
| `/api/v1/admin/curriculum-practice/templates/:id` | GET/PUT | admin | 模板CRUD | `api.admin.curriculumPractice.getTemplate()` / `updateTemplate()` |
| `/api/v1/admin/curriculum-practice/templates/:id/publish` | POST | admin | 发布模板 | `api.admin.curriculumPractice.publishTemplate()` |
| `/api/v1/admin/curriculum-practice/templates/:id/archive` | POST | admin | 归档模板 | `api.admin.curriculumPractice.archiveTemplate()` |
| `/api/v1/admin/curriculum-practice/templates/:id/runtime-dossier-preview` | GET | admin | Runtime Dossier预览 | `api.admin.curriculumPractice.getDossierPreview()` |
| `/api/v1/admin/curriculum-practice/examiner-agents` | GET/POST | admin | 考官Agent列表/创建 | `api.admin.curriculumPractice.getExaminerAgents()` / `createExaminerAgent()` |
| `/api/v1/admin/curriculum-practice/examiner-agents/:id` | GET/PUT | admin | 考官CRUD | `api.admin.curriculumPractice.getExaminerAgent()` / `updateExaminerAgent()` |
| `/api/v1/admin/curriculum-practice/examiner-agents/:id/publish` | POST | admin | 发布考官 | `api.admin.curriculumPractice.publishExaminerAgent()` |
| `/api/v1/admin/curriculum-practice/examiner-agents/:id/archive` | POST | admin | 归档考官 | `api.admin.curriculumPractice.archiveExaminerAgent()` |
| `/api/v1/admin/curriculum-practice/examiner-agents/:id/unpublish` | POST | admin | 退回草稿 | `api.admin.curriculumPractice.unpublishExaminerAgent()` |
| `/api/v1/admin/curriculum-practice/examiner-agents/:id/simulate` | POST | admin | 模拟考官行为 | `api.admin.curriculumPractice.simulateExaminerAgent()` |
| `/api/v1/admin/curriculum-practice/examiner-agents/:id/template-references` | GET | admin | 查看引用 | `api.admin.curriculumPractice.getExaminerAgentReferences()` |
| `/api/v1/admin/curriculum-practice/examiner-agents/:id/duplicate` | POST | admin | 复制考官 | `api.admin.curriculumPractice.duplicateExaminerAgent()` |
| `/api/v1/admin/curriculum-practice/case-items` | GET/POST | admin | CaseItem列表/创建 | `api.admin.curriculumPractice.getCaseItems()` / `createCaseItem()` |
| `/api/v1/admin/curriculum-practice/case-items/:id` | GET/PUT | admin | CaseItem CRUD | `api.admin.curriculumPractice.getCaseItem()` / `updateCaseItem()` |
| `/api/v1/admin/curriculum-practice/case-items/:id/publish` | POST | admin | 发布 | `api.admin.curriculumPractice.publishCaseItem()` |
| `/api/v1/admin/curriculum-practice/case-items/:id/archive` | POST | admin | 归档 | `api.admin.curriculumPractice.archiveCaseItem()` |
| `/api/v1/admin/curriculum-practice/role-profiles` | GET/POST | admin | RoleProfile列表/创建 | `api.admin.curriculumPractice.getRoleProfiles()` / `createRoleProfile()` |
| `/api/v1/admin/curriculum-practice/role-profiles/:id` | GET/PUT | admin | RoleProfile CRUD | `api.admin.curriculumPractice.getRoleProfile()` / `updateRoleProfile()` |
| `/api/v1/admin/curriculum-practice/role-profiles/:id/voice-clone` | POST | admin | 声音克隆 | `api.admin.curriculumPractice.cloneVoice()` |
| `/api/v1/admin/curriculum-practice/learner-profiles/:userId` | GET/PUT | admin | 查看/覆盖学员档案 | `api.admin.curriculumPractice.getLearnerProfile()` / `updateLearnerProfile()` |
| `/api/v1/admin/curriculum-practice/roleplay-situation-packs` | GET | admin | 情境包列表 | `api.admin.curriculumPractice.getSituationPacks()` |
| `/api/v1/admin/curriculum-practice/roleplay-situation-packs/:code` | GET | admin | 情境包详情 | `api.admin.curriculumPractice.getSituationPack()` |

### 1.25 Admin — 销售训练管理

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/sales-trainer/units` | GET/POST | admin | 单元列表/创建 | `api.adminSalesTrainer.getUnits()` / `createUnit()` |
| `/api/v1/admin/sales-trainer/units/:id` | PUT | admin | 更新单元 | `api.adminSalesTrainer.updateUnit()` |
| `/api/v1/admin/sales-trainer/units/:id/publish` | POST | admin | 发布单元 | `api.adminSalesTrainer.publishUnit()` |
| `/api/v1/admin/sales-trainer/units/:id/archive` | POST | admin | 归档单元 | `api.adminSalesTrainer.archiveUnit()` |
| `/api/v1/admin/sales-trainer/materials` | GET/POST/PUT | admin | 材料CRUD | `api.adminSalesTrainer.getMaterials()` / `createMaterial()` / `updateMaterial()` |
| `/api/v1/admin/sales-trainer/materials/:id/versions` | POST | admin | 创建材料版本 | `api.adminSalesTrainer.createMaterialVersion()` |
| `/api/v1/admin/sales-trainer/materials/:id/versions/upload` | POST | admin | 上传材料版本文件 | `api.adminSalesTrainer.uploadMaterialVersion()` |
| `/api/v1/admin/sales-trainer/materials/versions/:id/publish` | POST | admin | 发布材料版本 | `api.adminSalesTrainer.publishMaterialVersion()` |
| `/api/v1/admin/sales-trainer/question-categories` | GET/POST/PUT | admin | 题目分类 | `api.adminSalesTrainer.getQuestionCategories()` / `createQuestionCategory()` |
| `/api/v1/admin/sales-trainer/questions` | GET/POST/PUT | admin | 题目管理 | `api.adminSalesTrainer.getQuestions()` / `createQuestion()` |
| `/api/v1/admin/sales-trainer/questions/:id/publish` | POST | admin | 发布题目 | `api.adminSalesTrainer.publishQuestion()` |
| `/api/v1/admin/sales-trainer/questions/:id/archive` | POST | admin | 归档题目 | `api.adminSalesTrainer.archiveQuestion()` |
| `/api/v1/admin/sales-trainer/audio-submissions` | GET | admin | 语音提交列表 | `api.adminSalesTrainer.getAudioSubmissions()` |
| `/api/v1/admin/sales-trainer/audio-submissions/:id/retry-transcription` | POST | admin | 重试转写 | `api.adminSalesTrainer.retryTranscription()` |
| `/api/v1/admin/sales-trainer/audio-submissions/:id/retry-scoring` | POST | admin | 重试评分 | `api.adminSalesTrainer.retryScoring()` |
| `/api/v1/admin/sales-trainer/audio-score-prompts` | GET/POST/PUT | admin | 评分提示词 | `api.adminSalesTrainer.getAudioScorePrompts()` / `createAudioScorePrompt()` |
| `/api/v1/admin/sales-trainer/score-results` | GET | admin | 评分结果 | `api.adminSalesTrainer.getScoreResults()` |
| `/api/v1/admin/sales-trainer/training-records` | GET | admin | 训练记录 | `api.adminSalesTrainer.getTrainingRecords()` |
| `/api/v1/admin/sales-trainer/quiz-attempts` | GET | admin | 做题记录 | `api.adminSalesTrainer.getQuizAttempts()` |
| `/api/v1/admin/sales-trainer/regrades/quiz-attempts/:id/preview` | POST | admin | 重评预览 | `api.adminSalesTrainer.previewRegrade()` |
| `/api/v1/admin/sales-trainer/regrades/quiz-attempts/:id/run` | POST | admin | 执行重评 | `api.adminSalesTrainer.runRegrade()` |
| `/api/v1/admin/sales-trainer/operation-logs` | GET | admin | 操作日志 | `api.adminSalesTrainer.getOperationLogs()` |
| `/api/v1/admin/sales-trainer/settings` | GET/PUT | admin | 销售训练设置 | `api.adminSalesTrainer.getSettings()` / `updateSettings()` |

### 1.26 Admin — 新人训练管理

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/newcomer-training/units` | GET/POST/PUT | admin | 单元管理 | `api.adminNewcomerTraining.getUnits()` / `createUnit()` |
| `/api/v1/admin/newcomer-training/units/:id/revisions` | GET | admin | 版本历史 | `api.adminNewcomerTraining.getUnitRevisions()` |
| `/api/v1/admin/newcomer-training/units/:id/rollback` | POST | admin | 回滚 | `api.adminNewcomerTraining.rollbackUnit()` |
| `/api/v1/admin/newcomer-training/path-config` | GET/PUT/POST | admin | 路径配置 | `api.adminNewcomerTraining.getPathConfig()` / `updatePathConfig()` |
| `/api/v1/admin/newcomer-training/path-config/revisions` | GET | admin | 路径版本历史 | `api.adminNewcomerTraining.getPathConfigRevisions()` |
| `/api/v1/admin/newcomer-training/path-config/rollback` | POST | admin | 路径回滚 | `api.adminNewcomerTraining.rollbackPathConfig()` |
| `/api/v1/admin/newcomer-training/papers` | GET/POST/PUT | admin | 试卷管理 | `api.adminNewcomerTraining.getPapers()` / `createPaper()` |
| `/api/v1/admin/newcomer-training/papers/:id/revisions` | GET | admin | 试卷版本历史 | `api.adminNewcomerTraining.getPaperRevisions()` |
| `/api/v1/admin/newcomer-training/papers/:id/rollback` | POST | admin | 试卷回滚 | `api.adminNewcomerTraining.rollbackPaper()` |
| `/api/v1/admin/newcomer-training/modules/:key/article-binding` | PUT | admin | 文章绑定 | `api.adminNewcomerTraining.bindArticle()` |
| `/api/v1/admin/newcomer-training/modules/:key/ai-coach/config` | GET/PUT | admin | AI Coach配置 | `api.adminNewcomerTraining.getAICoachConfig()` / `updateAICoachConfig()` |
| `/api/v1/admin/newcomer-training/modules/:key/ai-coach/config/publish` | POST | admin | 发布AI Coach配置 | `api.adminNewcomerTraining.publishAICoachConfig()` |

### 1.27 Admin — 提示词模板

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/prompt-templates` | GET/POST | admin | 模板列表/创建 | `api.admin.prompts.getList()` / `create()` |
| `/api/v1/prompt-templates/options` | GET | admin | 编辑器选项 | `api.admin.prompts.getOptions()` |
| `/api/v1/prompt-templates/governance/status` | GET | admin | 治理状态 | `api.admin.prompts.getGovernanceStatus()` |
| `/api/v1/prompt-templates/governance/remediate-invalid` | POST | admin | 禁用无效模板 | `api.admin.prompts.remediateInvalid()` |
| `/api/v1/prompt-templates/governance/quarantine-invalid` | POST | admin | 隔离无效模板 | `api.admin.prompts.quarantineInvalid()` |
| `/api/v1/prompt-templates/governance/migrate-invalid` | POST | admin | 迁移无效历史 | `api.admin.prompts.migrateInvalid()` |
| `/api/v1/prompt-templates/governance/:id/rollback` | POST | admin | 回滚治理迁移 | `api.admin.prompts.rollbackGovernance()` |
| `/api/v1/prompt-templates/by-scenario/:scenarioType` | GET | admin | 按场景解析最佳模板 | `api.admin.prompts.getByScenario()` |
| `/api/v1/prompt-templates/:id` | GET/PUT/DELETE | admin | 模板CRUD | `api.admin.prompts.getById()` / `update()` / `delete()` |
| `/api/v1/prompt-templates/:id/render` | POST | admin | 渲染模板 | `api.admin.prompts.render()` |
| `/api/v1/prompt-templates/:id/set-default` | POST | admin | 设为默认 | `api.admin.prompts.setDefault()` |
| `/api/v1/scenario-prompts` | GET/POST | admin | 场景绑定列表/创建 | `api.admin.scenarioPrompts.getList()` / `create()` |
| `/api/v1/scenario-prompts/:id` | GET/PUT/DELETE | admin | 场景绑定CRUD | `api.admin.scenarioPrompts.getById()` / `update()` / `delete()` |

### 1.28 Admin — 业务规则

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/business-rules/*` | 多 | admin | 业务规则管理 | `api.admin.businessRules.*` |
| `/api/v1/admin/business-rules/ai-coach/*` | 多 | admin | AI Coach规则 | `api.admin.businessRules.aiCoach.*` |
| `/api/v1/admin/business-rules/growth-achievements/*` | 多 | admin | 成就规则 | `api.admin.businessRules.growth.*` |
| `/api/v1/admin/business-rules/next-practice-recommendations/*` | 多 | admin | 推荐规则 | `api.admin.businessRules.recommendations.*` |
| `/api/v1/admin/business-rules/objection-ledger/*` | 多 | admin | 异议台账 | `api.admin.businessRules.objections.*` |
| `/api/v1/admin/business-rules/sales-combinations/*` | 多 | admin | 销售组合 | `api.admin.businessRules.salesCombinations.*` |

### 1.29 Admin — 其他管理端点

| 端点 | 方法 | 权限 | 功能 | 前端对应调用 |
|------|------|------|------|-------------|
| `/api/v1/admin/users` | GET | admin | 用户管理 | `api.admin.users.getList()` |
| `/api/v1/admin/users/export` | GET | admin | 用户导出 | `api.admin.users.export()` |
| `/api/v1/admin/presentations` | GET/POST | admin | PPT管理 | `api.admin.presentations.getList()` / `create()` |
| `/api/v1/admin/presentations/:id` | GET/PUT/DELETE | admin | PPT CRUD | `api.admin.presentations.getById()` / `update()` / `delete()` |
| `/api/v1/admin/analytics/*` | 多 | admin | 数据分析 | `api.admin.analytics.*` |
| `/api/v1/admin/analytics/curriculum/*` | 多 | admin | 课程分析 | `api.admin.analytics.curriculum.*` |
| `/api/v1/admin/records` | GET | admin | 记录管理 | `api.admin.records.getList()` |
| `/api/v1/admin/logs` | GET | admin | 系统日志 | `api.admin.logs.getList()` |
| `/api/v1/admin/settings` | GET/PUT | admin | 系统设置 | `api.admin.settings.get()` / `update()` |
| `/api/v1/admin/presentation-ai/*` | 多 | admin | PPT AI策略 | `api.admin.presentationAi.*` |
| `/api/v1/admin/governance/*` | 多 | admin | 治理 | `api.admin.governance.*` |
| `/api/v1/admin/ai-governance/*` | 多 | admin | AI治理 | `api.admin.aiGovernance.*` |
| `/api/v1/admin/audit-trail` | GET | admin | 审计追踪 | `api.admin.auditTrail.get()` |
| `/api/v1/admin/security/inventory` | GET | admin | 安全清单 | `api.admin.security.getInventory()` |
| `/api/v1/admin/permissions/roles` | GET | admin | 角色权限定义 | `api.admin.permissions.getRoles()` |
| `/api/v1/admin/permissions/check` | POST | admin | 权限检查 | `api.admin.permissions.check()` |
| `/api/v1/admin/dashboard` | GET | admin | 仪表盘数据 | `api.admin.dashboard.get()` |
| `/api/v1/admin/health` | GET | admin | 健康检查 | `api.admin.health.get()` |

---

## 二、后端 WebSocket 端点

### 2.1 WebSocket 端点总表

| 端点 | 处理器 | 场景 | 语音模式 | 权限 | 前端对应Hook |
|------|--------|------|---------|------|-------------|
| `WS /ws/presentation?session_id=&token=` | `PresentationWebSocketHandler` | presentation | legacy / stepfun_realtime | 需JWT+所有权 | `usePracticeWebSocket` |
| `WS /ws/presentation/:session_id?token=` | `PresentationWebSocketHandler` | presentation | legacy / stepfun_realtime | 需JWT+所有权 | `usePracticeWebSocket` |
| `WS /ws/sales?session_id=&token=` | `StepFunRealtimeHandler` | sales | stepfun_realtime (强制) | 需JWT+所有权 | `usePracticeWebSocket` |
| `WS /ws/sales/:session_id?token=` | `StepFunRealtimeHandler` | sales | stepfun_realtime (强制) | 需JWT+所有权 | `usePracticeWebSocket` |
| `WS /ws/curriculum/examiner?session_id=&token=` | `ExaminerWebSocketHandler` | examiner | — | 需JWT+所有权 | `useExaminerWebSocket` |
| `WS /ws/curriculum/examiner/:session_id?token=` | `ExaminerWebSocketHandler` | examiner | — | 需JWT+所有权 | `useExaminerWebSocket` |

### 2.2 WebSocket 消息类型 — 销售/演讲练习

**Inbound（后端→前端）**

| 消息类型 | 说明 | 来源模块 |
|---------|------|---------|
| `status` | 会话状态更新 | all |
| `chat` | AI文本消息 | all |
| `tts_audio` | 完整TTS音频(legacy) | presentation / sales(legacy) |
| `tts_chunk` | 流式TTS分段 | sales(stepfun) |
| `interim_transcript` | 实时转写 | all |
| `sales_stage` | 销售阶段 | sales |
| `score_update` | 实时评分 | sales |
| `action_card` | 动作卡片 | sales |
| `fuzzy_detection` | 模糊表达检测 | sales |
| `slide_update` | PPT幻灯片更新 | presentation |
| `points_covered` | 要点覆盖状态 | presentation |
| `forbidden_words` | 禁用词检测 | presentation |
| `coach_health` | Coach健康状态 | all |
| `interrupted` | 被打断通知 | all |
| `reconnected` | 重连成功 | all |
| `slow_down` / `resume` | 背压控制 | all |
| `live_session_summary` | 实时会话总结 | sales |
| `claim_truth` | 事实核查 | sales |

**Outbound（前端→后端）**

| 消息类型 | 说明 | 目标模块 |
|---------|------|---------|
| `text` | 用户文本输入 | all |
| `audio_chunk` | 音频数据(JSON Base64或binary 0x01) | all |
| `audio_end` | 音频结束标记 | all |
| `interrupt` | 用户打断(binary 0x02) | all |
| `control` (start/pause/resume/end) | 会话生命周期控制 | presentation |
| `page_change` | 换页 | presentation |

### 2.3 WebSocket 消息类型 — 考官考核

**Inbound**

| 消息类型 | 说明 |
|---------|------|
| `exam_init` | 考核初始化数据 |
| `exam_question` | 当前题目 |
| `exam_progress` | 答题进度 |
| `exam_feedback` | 单题评分反馈 |
| `exam_completed` | 考核完成 |

**Outbound**

| 消息类型 | 说明 |
|---------|------|
| `submit_answer` | 提交答案 |

---

## 三、前端 API 调用映射

### 3.1 前端 API 架构

```
页面组件
    │
    ├──▶ useQuery / useMutation (React Query v5)
    │         │
    │         ▼
    │    apiFetch / apiUpload (统一传输层)
    │         │
    │         ├──▶ 认证头注入 (Bearer / Cookie)
    │         ├──▶ CSRF Token 注入
    │         ├──▶ Trace-ID 传播
    │         ├──▶ 错误标准化 (ApiRequestError)
    │         └──▶ 环回地址切换 (fetchWithLoopbackRetry)
    │                   │
    │                   ▼
    │            [后端 FastAPI :3444]
```

### 3.2 前端 API 客户端领域拆分

| 领域对象 | 路径 | 包含端点数 |
|---------|------|-----------|
| `api.auth` | `src/lib/api/client-domains.ts` | 8 |
| `api.user` | `src/lib/api/client-domains.ts` | 10 |
| `api.training` | `src/lib/api/client-domains.ts` | 3 |
| `api.scenarios` | `src/lib/api/client-domains.ts` | 4 |
| `api.agents` | `src/lib/api/client-domains.ts` | 3 |
| `api.practice` | `src/lib/api/client-domains.ts` | 6 |
| `api.sessions` | `src/lib/api/client-domains.ts` | 18 |
| `api.learningPath` | `src/lib/api/client-domains.ts` | 2 |
| `api.learnerStudy` | `src/lib/api/client-domains.ts` | 4 |
| `api.salesTrainer` | `src/lib/api/client-domains.ts` | 11 |
| `api.newcomerTraining` | `src/lib/api/client-domains.ts` | 8 |
| `api.evaluation` | `src/lib/api/client-domains.ts` | 3 |
| `api.supervisor` | `src/lib/api/client-domains.ts` | 10 |
| `api.retraining` | `src/lib/api/client-domains.ts` | 4 |
| `api.support` | `src/lib/api/client-domains.ts` | 2 |
| `api.presentations` | `src/lib/api/client-domains.ts` | 15 |
| `api.testBank` | `src/lib/api/client-domains.ts` | 10 |
| `api.admin.*` | `src/lib/api/client-domains.ts` | 100+ |

---

## 四、前端页面路由与交互清单

### 4.1 认证页面 (auth)

| 路由 | 页面组件 | 主要按钮/交互 | 调用API |
|------|---------|-------------|---------|
| `/login` | `login/page.tsx` | 邮箱输入、密码输入、登录按钮、企微登录按钮、忘记密码链接 | `POST /auth/login`, `GET /auth/wecom/start` |
| `/forgot-password` | `forgot-password/page.tsx` | 邮箱输入、发送重置链接按钮 | `POST /auth/forgot-password` |
| `/reset-password` | `reset-password/page.tsx` | 新密码输入、确认密码、重置按钮 | `POST /auth/reset-password` |

### 4.2 Dashboard 页面

| 路由 | 页面组件 | 主要按钮/交互 | 调用API |
|------|---------|-------------|---------|
| `/` | `page.tsx` | 首页Dashboard、训练入口卡片、通知铃铛 | `GET /users/me`, `GET /users/me/notifications` |
| `/profile` | `profile/page.tsx` | 头像上传、资料编辑、偏好设置 | `GET /users/me`, `PATCH /users/me` |
| `/history` | `history/page.tsx` | 训练历史列表、筛选、分页 | `GET /users/me/history` |
| `/leaderboard` | `leaderboard/page.tsx` | 排行榜、筛选条件 | `GET /leaderboard` |
| `/agents/:agentId` | `agents/[agentId]/page.tsx` | Agent详情、Persona选择、开始训练按钮 | `GET /agents/:id`, `GET /agents/:id/personas` |
| `/training` | `training/page.tsx` | 训练分类入口（销售/演讲） | `GET /training/categories` |
| `/training/sales` | `training/sales/page.tsx` | 销售场景列表、Agent选择 | `GET /training/categories/sales/agents` |
| `/training/presentation` | `training/presentation/page.tsx` | PPT列表、开始演讲按钮 | `GET /presentations` |
| `/support` | `support/page.tsx` | 支持文档、联系客服 | — |
| `/support/runtime` | `support/runtime/page.tsx` | 运行时诊断工具 | `GET /support/runtime/overview` |

### 4.3 用户练习页面 (user)

| 路由 | 页面组件 | 主要按钮/交互 | 调用API |
|------|---------|-------------|---------|
| `/learning-path` | `learning-path/page.tsx` | 学习路径时间线、章节卡片、开始按钮 | `GET /curriculum-practice/learning-path/me` |
| `/study/:learningContentId` | `study/[id]/page.tsx` | 文章内容、章节导航、完成按钮 | `GET /curriculum-practice/study/learning-contents/:id`, `POST .../complete` |
| `/practice/:sessionId` | `practice/[sessionId]/page.tsx` | **核心练习页**：麦克风开关、文本输入、PPT导航、实时评分面板、结束按钮 | `WS /ws/:scenario`, `POST /practice/sessions/:id/lifecycle` |
| `/practice/:sessionId/replay` | `practice/[sessionId]/replay/page.tsx` | 会话回放、时间轴、消息列表 | `GET /sessions/:id/replay` |
| `/practice/:sessionId/report` | `practice/[sessionId]/report/page.tsx` | 练习报告、分数、建议、分享按钮 | `GET /practice/sessions/:id/report` |
| `/exam/:sessionId` | `exam/[sessionId]/page.tsx` | **考官考核页**：题目展示、答案输入、提交、倒计时 | `WS /ws/curriculum/examiner/:id` |
| `/exam/:sessionId/report` | `exam/[sessionId]/report/page.tsx` | 考核报告、分数明细 | `GET /curriculum-practice/study/exam-sessions/:id/report` |

### 4.4 销售训练页面 (sales-trainer)

| 路由 | 页面组件 | 主要按钮/交互 | 调用API |
|------|---------|-------------|---------|
| `/sales-trainer` | `sales-trainer/page.tsx` | 模块网格、路径时间线、进度条 | `GET /sales-trainer/units`, `GET /sales-trainer/paths` |
| `/sales-trainer/learn/:unitId` | `sales-trainer/learn/[unitId]/page.tsx` | 学习内容阅读、章节导航 | `GET /sales-trainer/units/:id` |
| `/sales-trainer/quiz/:unitId` | `sales-trainer/quiz/[unitId]/page.tsx` | 题目展示、选项选择、提交、上一题/下一题 | `GET /sales-trainer/units/:id`, `POST /sales-trainer/quiz-attempts` |
| `/sales-trainer/quiz/result/:attemptId` | `sales-trainer/quiz/result/[attemptId]/page.tsx` | 得分展示、错题回顾、重做按钮 | `GET /sales-trainer/quiz-attempts/:id` |
| `/sales-trainer/audio/:unitId` | `sales-trainer/audio/[unitId]/page.tsx` | 录音按钮、上传按钮、播放预览 | `POST /sales-trainer/audio-submissions/upload-url`, `POST /audio-submissions` |
| `/sales-trainer/audio/result/:submissionId` | `sales-trainer/audio/result/[submissionId]/page.tsx` | 评分结果、反馈、重录按钮 | `GET /sales-trainer/audio-submissions/:id` |
| `/sales-trainer/business-skills` | `sales-trainer/business-skills/page.tsx` | 文章列表、章节卡片 | `GET /newcomer-training/modules/:key/article` |
| `/sales-trainer/business-skills/exam` | `sales-trainer/business-skills/exam/page.tsx` | 考试页面、计时器、提交 | `POST /newcomer-training/paper-attempts` |
| `/sales-trainer/business-skills/coach` | `sales-trainer/business-skills/coach/page.tsx` | AI Coach聊天界面、输入框、发送按钮 | `POST /newcomer-training/ai-coach/sessions`, `POST /turns` |

### 4.5 Admin 管理后台页面

| 路由 | 页面组件 | 主要按钮/交互 | 调用API |
|------|---------|-------------|---------|
| `/admin/` | `admin/page.tsx` | 管理后台首页、统计卡片 | `GET /admin/dashboard` |
| `/admin/users/` | `admin/users/page.tsx` | 用户列表、筛选、导出按钮 | `GET /admin/users` |
| `/admin/agents/` | `admin/agents/page.tsx` | Agent列表、创建按钮、筛选 | `GET /admin/agents` |
| `/admin/agents/:id` | `admin/agents/[id]/page.tsx` | Agent编辑、Persona关联、发布/归档按钮 | `GET /admin/agents/:id`, `PUT /admin/agents/:id` |
| `/admin/personas/` | `admin/personas/page.tsx` | Persona列表、创建按钮、Policy Health | `GET /admin/personas` |
| `/admin/personas/:id` | `admin/personas/[id]/page.tsx` | Persona编辑、Policy编辑、克隆按钮 | `GET /admin/personas/:id`, `PUT /admin/personas/:id/policy` |
| `/admin/presentations/` | `admin/presentations/page.tsx` | PPT列表、上传按钮、替换/删除 | `GET /admin/presentations`, `POST /presentations` |
| `/admin/presentations/:id` | `admin/presentations/[id]/page.tsx` | PPT详情、页面列表、要点管理、禁用词管理 | `GET /presentations/:id` |
| `/admin/knowledge/` | `admin/knowledge/page.tsx` | 知识库列表、创建按钮 | `GET /admin/knowledge-bases` |
| `/admin/knowledge/:id` | `admin/knowledge/[id]/page.tsx` | 知识库详情、文档列表、上传文档 | `GET /admin/knowledge-bases/:id` |
| `/admin/learning-contents/` | `admin/learning-contents/page.tsx` | 学习内容列表、创建按钮 | `GET /curriculum/learning-contents` |
| `/admin/learning-contents/:contentId` | `admin/learning-contents/[contentId]/page.tsx` | 内容编辑、章节管理、发布/归档 | `GET /curriculum/learning-contents/:id` |
| `/admin/prompts/` | `admin/prompts/page.tsx` | 提示词模板列表、创建按钮、治理状态 | `GET /prompt-templates` |
| `/admin/prompts/:id` | `admin/prompts/[id]/page.tsx` | 模板编辑、渲染测试、设为默认 | `GET /prompt-templates/:id`, `POST /render` |
| `/admin/prompts/bindings` | `admin/prompts/bindings/page.tsx` | 场景绑定列表、创建/解绑 | `GET /scenario-prompts` |
| `/admin/settings/` | `admin/settings/page.tsx` | 系统设置表单、保存按钮 | `GET /admin/settings`, `PUT /admin/settings` |
| `/admin/analytics/` | `admin/analytics/page.tsx` | 数据图表、筛选器 | `GET /admin/analytics/*` |
| `/admin/analytics/curriculum/` | `admin/analytics/curriculum/page.tsx` | 课程分析图表 | `GET /admin/analytics/curriculum/*` |
| `/admin/records/` | `admin/records/page.tsx` | 训练记录列表、详情 | `GET /admin/records` |
| `/admin/logs/` | `admin/logs/page.tsx` | 系统日志列表、筛选 | `GET /admin/system-logs` |
| `/admin/voice-runtime/` | `admin/voice-runtime/page.tsx` | 语音预设列表、创建/编辑 | `GET /admin/voice-runtime-profiles` |
| `/admin/presentation-ai/` | `admin/presentation-ai/page.tsx` | PPT AI策略配置 | `GET /admin/presentation-ai/*` |
| `/admin/scoring-rulesets/` | `admin/scoring-rulesets/page.tsx` | 评分规则集列表、编辑 | `GET /admin/scoring-rulesets` |
| `/admin/business-rules/` | `admin/business-rules/page.tsx` | 业务规则网格、编辑 | `GET /admin/business-rules/*` |
| `/admin/business-rules/ai-coach/` | `admin/business-rules/ai-coach/page.tsx` | AI Coach规则配置 | `GET/PUT /admin/business-rules/ai-coach/*` |
| `/admin/curriculum-practice/` | `admin/curriculum-practice/page.tsx` | 练习模板列表、创建 | `GET /admin/curriculum-practice/templates` |
| `/admin/curriculum-practice/templates` | `admin/curriculum-practice/templates/page.tsx` | 模板管理、发布/归档 | `GET/POST /admin/curriculum-practice/templates` |
| `/admin/curriculum-practice/case-items/` | `admin/curriculum-practice/case-items/page.tsx` | 案例项管理 | `GET/POST /admin/curriculum-practice/case-items` |
| `/admin/curriculum-practice/examiner-agents/` | `admin/curriculum-practice/examiner-agents/page.tsx` | 考官Agent管理 | `GET/POST /admin/curriculum-practice/examiner-agents` |
| `/admin/curriculum-practice/role-profiles/` | `admin/curriculum-practice/role-profiles/page.tsx` | 角色画像管理、声音克隆 | `GET/POST /admin/curriculum-practice/role-profiles` |
| `/admin/curriculum-practice/roleplay-situation-packs/` | `admin/curriculum-practice/roleplay-situation-packs/page.tsx` | 情境包管理 | `GET /admin/curriculum-practice/roleplay-situation-packs` |
| `/admin/test-bank/` | `admin/test-bank/page.tsx` | 题库列表、导入、AI生成 | `GET /curriculum/test-bank/questions` |
| `/admin/sales-trainer/` | `admin/sales-trainer/page.tsx` | 销售训练管理首页 | `GET /admin/sales-trainer/units` |
| `/admin/sales-trainer/units/` | `admin/sales-trainer/units/page.tsx` | 训练单元列表、创建/编辑 | `GET/POST /admin/sales-trainer/units` |
| `/admin/sales-trainer/questions/` | `admin/sales-trainer/questions/page.tsx` | 题目列表、创建/编辑 | `GET/POST /admin/sales-trainer/questions` |
| `/admin/sales-trainer/questions/categories/` | `admin/sales-trainer/questions/categories/page.tsx` | 题目分类管理 | `GET/POST /admin/sales-trainer/question-categories` |
| `/admin/sales-trainer/papers/` | `admin/sales-trainer/papers/page.tsx` | 试卷管理、版本历史 | `GET/POST /admin/newcomer-training/papers` |
| `/admin/sales-trainer/quiz-attempts/` | `admin/sales-trainer/quiz-attempts/page.tsx` | 做题记录列表、重评 | `GET /admin/sales-trainer/quiz-attempts` |
| `/admin/sales-trainer/audio-submissions/` | `admin/sales-trainer/audio-submissions/page.tsx` | 语音提交列表、重试转写/评分 | `GET /admin/sales-trainer/audio-submissions` |
| `/admin/sales-trainer/score-prompts/` | `admin/sales-trainer/score-prompts/page.tsx` | 评分提示词管理 | `GET/POST /admin/sales-trainer/audio-score-prompts` |
| `/admin/sales-trainer/score-results/` | `admin/sales-trainer/score-results/page.tsx` | 评分结果查看 | `GET /admin/sales-trainer/score-results` |
| `/admin/sales-trainer/score-standards/` | `admin/sales-trainer/score-standards/page.tsx` | 评分标准管理 | — |
| `/admin/sales-trainer/training-records/` | `admin/sales-trainer/training-records/page.tsx` | 训练记录管理 | `GET /admin/sales-trainer/training-records` |
| `/admin/sales-trainer/materials/` | `admin/sales-trainer/materials/page.tsx` | 材料管理、版本上传 | `GET/POST /admin/sales-trainer/materials` |
| `/admin/sales-trainer/paths/` | `admin/sales-trainer/paths/page.tsx` | 路径配置、版本回滚 | `GET/PUT /admin/newcomer-training/path-config` |
| `/admin/sales-trainer/articles/` | `admin/sales-trainer/articles/page.tsx` | 文章绑定管理 | `PUT /admin/newcomer-training/modules/:key/article-binding` |
| `/admin/sales-trainer/operation-logs/` | `admin/sales-trainer/operation-logs/page.tsx` | 操作日志查看 | `GET /admin/sales-trainer/operation-logs` |
| `/admin/sales-trainer/settings/` | `admin/sales-trainer/settings/page.tsx` | 销售训练设置 | `GET/PUT /admin/sales-trainer/settings` |

---

## 五、前后端对应关系矩阵

### 5.1 核心业务流程对应

| 业务流程 | 前端页面 | 前端按钮/交互 | 后端API | 后端服务 | 数据库表 |
|---------|---------|-------------|---------|---------|---------|
| 用户登录 | `/login` | 登录按钮 | `POST /auth/login` | `auth/service.py` | `users` |
| 创建练习会话 | `/training/sales` 或 `/training/presentation` | 开始训练按钮 | `POST /practice/sessions` | `PracticeSessionCreateService` | `practice_sessions` |
| 销售实时对话 | `/practice/:sessionId` | 麦克风按钮 | `WS /ws/sales` | `StepFunRealtimeHandler` | `conversation_messages` |
| 演讲实时反馈 | `/practice/:sessionId` | 麦克风按钮 | `WS /ws/presentation` | `PresentationWebSocketHandler` | `interruption_events` |
| 考官考核 | `/exam/:sessionId` | 提交答案按钮 | `WS /ws/curriculum/examiner` | `ExaminerWebSocketHandler` | `practice_sessions` |
| 生成报告 | `/practice/:sessionId/report` | 查看报告按钮 | `GET /evaluation/:id/report` | `ComprehensiveReportService` | `comprehensive_reports` |
| PPT上传 | `/admin/presentations/` | 上传PPT按钮 | `POST /presentations` | `PresentationUploadService` | `presentations`, `pages` |
| Agent创建 | `/admin/agents/` | 创建Agent按钮 | `POST /admin/agents` | `AgentService` | `agents` |
| Persona创建 | `/admin/personas/` | 创建Persona按钮 | `POST /admin/personas` | `PersonaService` | `personas` |
| 知识库上传 | `/admin/knowledge/:id` | 上传文档按钮 | `POST /admin/knowledge-bases/:id/documents` | `KnowledgeDocumentService` | `knowledge_documents` |
| 配置导出 | `/admin/config-assets/` | 导出按钮 | `POST /admin/config-assets/export` | `ConfigAssetExportService` | 多表 |
| 配置导入 | `/admin/config-assets/` | 导入按钮 | `POST /admin/config-assets/import` | `ConfigAssetImportService` | 多表 |
| 题目创建 | `/admin/test-bank/` | 创建题目按钮 | `POST /curriculum/test-bank/questions` | `QuestionItemService` | `question_items` |
| 学习内容创建 | `/admin/learning-contents/` | 创建内容按钮 | `POST /curriculum/learning-contents` | `LearningContentService` | `learning_contents` |
| 销售训练单元创建 | `/admin/sales-trainer/units/` | 创建单元按钮 | `POST /admin/sales-trainer/units` | `SalesTrainerUnitService` | `sales_trainer_units` |
| AI Coach交互 | `/sales-trainer/business-skills/coach` | 发送答案按钮 | `POST /newcomer-training/ai-coach/sessions/:id/turns` | `AICoachTurnService` | `sales_trainer_ai_coach_turns` |
| 督导评审 | `/admin/supervisor-training/` | 创建评审按钮 | `POST /supervisor/reviews` | `SupervisorService` | `supervisor_reviews` |
| 复训任务 | `/admin/supervisor-training/` | 创建复训任务按钮 | `POST /retraining/tasks` | `RetrainingTaskService` | `retraining_tasks` |

---

## 六、潜在不匹配与风险

### 6.1 高风险（前后端可能不一致）

| 前端调用 | 后端状态 | 风险说明 |
|---------|---------|---------|
| `POST /newcomer-training/ai-coach/sessions` | **开发中** | Git有未提交的Alembic迁移文件，AI Coach功能正在落地，需验证后端完整实现 |
| `POST /newcomer-training/ai-coach/sessions/:id/turns/:turnId` | **开发中** | 同上，前后端对齐需重点验证 |
| `GET /newcomer-training/ai-coach/sessions/:id` | **开发中** | 同上 |
| `PUT /admin/newcomer-training/modules/:key/ai-coach/config` | **开发中** | AI Coach配置保存，需确认后端完整实现 |
| `POST /admin/newcomer-training/modules/:key/ai-coach/config/publish` | **开发中** | AI Coach配置发布，需确认后端完整实现 |
| `POST /sales-trainer/audio-submissions/upload` | **需谨慎** | multipart上传有fallback到直传路径，但需确认后端multipart支持 |

### 6.2 中低风险（可能存在默认值兜底或边缘情况）

| 前端调用 | 风险说明 |
|---------|---------|
| `POST /practice/sessions/:id/audio-upload-urls` | 音频分段上传URL，属于持续上传特性，需确认OSS/COS配置 |
| `POST /practice/sessions/:id/audio-segments` | 音频分段注册 |
| `POST /practice/sessions/:id/audio-segments/failure` | 音频分段失败上报 |
| `GET /sessions/:id/audio/:messageId` | 消息音频Blob，直接fetch，需确认CDN/对象存储配置 |
| `GET /sessions/:id/audio-segments/:seq` | 分段音频Blob |
| `POST /curriculum/test-bank/generation/preview` | AI题目生成预览 |
| `POST /curriculum/test-bank/generation/confirm` | AI题目生成确认 |
| `GET /admin/sales-trainer/settings` | 销售训练设置，可能存在默认值兜底 |

### 6.3 WebSocket 版本兼容风险

| 语音模式 | 状态 | 说明 |
|---------|------|------|
| `legacy` | **逐步停用** | Presentation仍支持，但Sales已强制stepfun_realtime |
| `stepfun_realtime` | **主推** | 销售场景独占，Presentation可选 |

---

*文档结束。本文档基于 2026-06-09 的代码快照，未修改任何源代码。*
