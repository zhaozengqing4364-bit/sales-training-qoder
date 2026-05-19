# 后端 API 接口全量核查 — 异常清单与修复指引

> **核查范围**：后端 54 个路由模块，共计 315+ REST 端点 + 6 WebSocket 端点
> **核查方式**：三轮共计 9 个子代理地毯式搜索 + 内核源码阅读，覆盖：
>   1. 后端所有 `@router.*` `@app.*` 装饰器 + `app.include_router` 路由注册（包括中间件、流式响应）
>   2. 前端 `client.ts` / `client-domains.ts` 中每个 API 方法的定义
>   3. 前端每个页面/组件文件中对 `api.*` 的实际调用匹配
>   4. 前端绕过 API client 的裸 `fetch` / `axios` / `sendBeacon` 调用
>   5. 前端所有 WebSocket 连接
>   6. 前端动态属性访问（`api[`）、链式调用（`.then(api.`）等隐式模式
> **核查日期**：2026-05-18
> **复核状态**：2026-05-18 二次复核已移除 5 项误报，并记录已修复项（Admin Users HTTP 方法、登录页 API client 绕过）。

---

## 目录

1. [后端定义但前端完全未调用的 API](#一后端定义但前端完全未调用的-api)
2. [前端定义了方法但无页面调用的孤立 API 域](#二前端定义了方法但无页面调用的孤立-api-域)
3. [前后端重复实现与冗余路径](#三前后端重复实现与冗余路径)
4. [前端绕过 API Client 的直接调用](#四前端绕过-api-client-的直接调用)
5. [前后端 HTTP 方法不一致](#五前后端-http-方法不一致)
6. [汇总统计与优先级](#六汇总统计与优先级)

---

## 一、后端定义但前端完全未调用的 API

### 复核纠偏：已确认不是异常的调用

以下条目曾被静态扫描误判为“未使用”，二次复核确认均有生产调用，不应计入孤立 API：

| 方法 | 生产调用位置 | 结论 |
|------|--------------|------|
| `api.sessions.getKnowledgeCheck(sessionId)` | `web/src/app/(user)/practice/[sessionId]/report/page.tsx:1276` | ✅ 报告页加载知识检查诊断数据 |
| `api.sessions.getHighlightReview(sessionId)` | `web/src/app/(user)/practice/[sessionId]/report/page.tsx:1172` | ✅ 报告页拉取高光复习数据 |
| `api.retraining.completeTaskWithSession(taskId, payload)` | `web/src/app/(user)/practice/[sessionId]/report/page.tsx:1009` | ✅ 报告页完成回训任务 |
| `api.admin.createKnowledgeAnswerabilityProfile(...)` | `web/src/components/admin/knowledge-answer/tabs/answerability-tab.tsx:47` | ✅ 管理端可答性 Profile 创建 |
| `api.admin.updateKnowledgeAnswerabilityProfile(...)` / `deleteKnowledgeAnswerabilityProfile(...)` | `web/src/components/admin/knowledge-answer/tabs/answerability-tab.tsx:57,75,90` | ✅ 管理端可答性 Profile 更新/删除 |

Knowledge Answerability Profile 的页面链路为：`admin/knowledge/[id]/page.tsx` / `admin/retrieval-strategies/page.tsx` → `KnowledgeAnswerConsole` → `PipelineTabs` → `AnswerabilityTab`。

### 1.1 发布验证模块（Release Verification）— 9 个端点 ← 优先级最低

**后端文件**：`backend/src/admin/api/release_verification.py`
**所属模块**：Admin → 发布质量门禁
**权限要求**：`RELEASE_VERIFICATION_MANAGE_PERMISSION`（管理员）

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | POST | `/api/v1/admin/release-verification/candidates` | 创建发布候选版本（RC），附带自定义验证检查项（migration/contract/performance/manual） | 新增「发布管理」页面，提供「创建发布候选」按钮与表单 |
| 2 | GET | `/api/v1/admin/release-verification/candidates` | 分页查询发布候选列表，支持按状态筛选 | 同上页面列表区域 |
| 3 | GET | `/api/v1/admin/release-verification/candidates/latest` | 获取最新发布候选版本 | 首页仪表板或发布管理页顶部概览卡片 |
| 4 | GET | `/api/v1/admin/release-verification/candidates/{rc_id}/report` | 获取完整验证报告（摘要统计+各项检查+门禁状态+改进建议） | 列表每行「查看报告」按钮，弹窗展示 |
| 5 | PUT | `/api/v1/admin/release-verification/checks/{record_id}` | 更新单项验证检查结果（pass/fail+详情+耗时+错误信息） | 报告详情中每项检查提供「标记通过/失败」按钮 |
| 6 | POST | `/api/v1/admin/release-verification/candidates/{rc_id}/decision` | 做出人工 Go/No-Go 决策，附带理由 | 报告页底部「发布决策」按钮组 |
| 7 | POST | `/api/v1/admin/release-verification/candidates/{rc_id}/run-verification` | 触发自动化验证流水线（单元测试+集成测试+契约测试+性能基准） | 每个 RC 提供「运行验证」按钮 |
| 8 | GET | `/api/v1/admin/release-verification/candidates/{rc_id}/quality-gate` | 查询质量门禁状态（整体 pass/fail/pending + 阻塞项） | 报告页顶部质量门禁指示灯 |
| 9 | POST | `/api/v1/admin/release-verification/candidates/{rc_id}/auto-decision` | 基于质量门禁结果自动做出 Go/No-Go 决策 | 质量门禁区域「自动决策」按钮 |

**现状**：整个模块（9 个端点）在 `web/src/` 下零匹配，完全无前端页面。该模块实现 FR40（发布门禁检查记录与追踪），但当前只能通过 API 工具手动调用。该功能属于 DevOps 工具链，建议按需决定是否开发管理界面。

---

### 1.2 运行时指标分析 — 4 个端点 ← 中优先级

**后端文件**：`backend/src/admin/api/analytics.py`
**所属模块**：Admin 数据分析 `/api/v1/admin/analytics/` 前缀
**权限要求**：Admin

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/admin/analytics/runtime-metrics` | 运行时指标（FR39）：恢复成功率（目标≥99%）、误触发率（目标<1%）、完整率（目标≥98%）、会话分布与语音模式占比 | 数据分析页新增「运行时监控」Tab 或独立卡片区 |
| 2 | GET | `/api/v1/admin/analytics/policy-effectiveness` | 各 Agent 策略有效性排名对比 | 同上 Tab 内条形图/表格展示 |
| 3 | GET | `/api/v1/admin/analytics/voice-mode-comparison` | StepFun Realtime 与 Legacy 语音模式性能对比 | 同上 Tab 内双柱对比图 |
| 4 | GET | `/api/v1/admin/analytics/fallback-metrics` | TTS/ASR/LLM 各级降级链触发次数与浏览器 TTS 兜底使用率 | 同上 Tab 内流向图+统计表 |

**现状**：前端 `admin/analytics/page.tsx` 已使用 `overview`/`trends`/`agents`/`leaderboard`/`operating-pack`，但以上 4 个端点及对应 `client.ts` 方法（`getRuntimeMetrics`/`getPolicyEffectiveness`/`getVoiceModeComparison`/`getFallbackMetrics`）均未接入任何页面。

---

### 1.3 训练任务终态操作 — 3 个端点 ← 高优先级

**后端文件**：`backend/src/common/api/training_tasks.py`
**所属模块**：训练任务 `/api/v1/training-tasks` 前缀

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | POST | `/api/v1/training-tasks/{task_id}/complete` | 学员完成训练后标记任务完成（关联 session_id+notes） | Dashboard 训练任务列表 → pending 任务提供「完成」按钮 |
| 2 | POST | `/api/v1/training-tasks/{task_id}/cancel` | 管理员取消 pending 状态任务 | 管理端 → 分配任务列表每行「取消」操作 |
| 3 | POST | `/api/v1/training-tasks/{task_id}/expire` | 管理员标记超期任务为过期 | 管理端 → 分配任务列表「标记过期」操作 |

**现状**：后端定义了完整的任务生命周期（create → start → complete/cancel/expire），但前端：

- `api.trainingTasks.*` 域共 7 个方法中仅有 `batchAssign` 在 `admin/users/page.tsx:389` 被使用
- `create`/`list`/`get`/`update`/`startSession` 仅在测试文件中使用
- `complete`/`cancel`/`expire` 三个终态操作在 `client.ts` 中未定义任何方法
- 管理后台 `web/src/app/admin/` 下不存在 `training-tasks` 目录，即缺乏独立的训练任务管理页面
- 回训场景使用 `api.retraining.completeTaskWithSession`（在 report/page.tsx:1009 有调用），但主训练流程的 `complete` 缺失

---

### 1.4 学员画像与自我评估 — 2 个端点 ← 中优先级

**后端文件**：`backend/src/curriculum_practice/api.py`
**所属模块**：学习路径 `/api/v1/curriculum-practice/learning-path` 前缀

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/curriculum-practice/learning-path/me/profile` | 获取学员画像（能力等级、学习偏好、历史趋势），若不存在则自动创建默认档案 | 学习路径页 → 顶部「学习档案」卡片 + 雷达图 |
| 2 | POST | `/api/v1/curriculum-practice/learning-path/me/profile/self-assessment` | 学员自评能力等级，系统记录并更新画像用于校准 | 同上卡片 →「自我评估」按钮弹出等级选择器 |

**现状**：前端 `learning-path/page.tsx` 仅使用 `learning-path/me` 和 `learning-path/me/next-task`。`self-assessment`/`learnerProfiles` 在 `web/src/` 下零匹配。值得注意的是，后端同时暴露了 `/api/v1/admin/curriculum-practice/learner-profiles/{user_id}/override`（管理员覆盖学员画像），前端 `admin/users/[id]/page.tsx` 使用了 `api.admin.overrideLearnerProfile`，但学员端画像查看和自我评估完全缺失。

---

### 1.5 成长中心通知列表与目标设置 — 2 个端点 ← 低优先级

**后端文件**：`backend/src/common/api/growth.py`
**所属模块**：成长中心 `/api/v1/growth` 前缀

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/growth/notifications` | 拉取通知列表（支持 include_read 参数），包含目标达成提醒、新推荐、能力提升提示等 | Dashboard → 通知铃铛 → 点击弹出通知列表下拉面板 |
| 2 | PUT | `/api/v1/growth/goals/current` | 用户设置训练目标（weekly_sessions/monthly_presentations + 数量 + 周期 + 起止日期） | Dashboard →「成长目标」卡片 →「编辑目标」按钮弹出表单 |

**现状**：`api.dashboard.getGrowth` 已在 `dashboard/page.tsx:431` 中用于成长卡片展示，但通知列表拉取和目标设置两个接口在前端完全缺失。

---

### 1.6 管理后台配置验证与审计 — 2 个端点 ← 低优先级

**后端文件**：`backend/src/admin/api/settings.py`
**所属模块**：系统配置 `/api/v1/admin/settings` 前缀
**权限要求**：`ADMIN_SETTINGS_MANAGE_PERMISSION`

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | POST | `/api/v1/admin/settings/{surface}/validate` | 保存前校验配置 JSON 值的合法性，返回归一化值或验证错误（含审计日志写入） | 设置页每个配置编辑表单底部「校验配置」按钮 |
| 2 | GET | `/api/v1/admin/settings/{surface}/audit` | 查询某配置项变更历史审计日志（最近 50 条：操作人、类型、新旧值对比、时间） | 设置页每个配置面板的「审计日志」按钮 → 时间线视图 |

**现状**：前端 `admin/settings/page.tsx` 已使用 `get`/`drafts`/`preview`/`publish`/`rollback` 完整五步流程，但缺少前置验证和事后审计。

---

### 1.7 练习会话诊断与报告 — 3 个端点 ← 低优先级

**后端文件**：`backend/src/common/api/practice.py`

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/practice/sessions/{session_id}/diagnostics` | StepFun Realtime 会话运行时诊断证据链（config_binding、evaluation_run、report_snapshot、knowledge_answer_diagnostics、failure_details） | 演练记录详情页 →「诊断信息」按钮展示完整 JSON |
| 2 | GET | `/api/v1/practice/sessions/{session_id}/comprehensive-report` | 综合评估报告（分维度评分+阶段摘要+优势改进点+推荐），含 report_status 状态检查 | 练习报告页，与现有 `/evaluation/sessions/{id}/report` 统一 |
| 3 | GET | `/api/v1/practice/sessions/{session_id}/report-status` | 轮询异步报告生成进度（current_stage + progress_percent + estimated_remaining_seconds） | 练习结束过渡页 → 进度条轮询，就绪后自动跳转报告页 |

**现状**：前端报告页使用 `POST/GET /evaluation/sessions/{id}/report` 替代 `comprehensive-report`，缺乏报告状态轮询机制。诊断接口无任何页面使用。

---

## 二、前端定义了方法但无页面调用的孤立 API 方法

以下方法在 `client.ts` / `client-domains.ts` 中明确定义且后端有对应端点，但经过全量页面扫描确认，没有任何前端页面或组件调用它们（仅测试文件有使用）。

### 2.1 练习域 `api.practice.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `pauseSession(sessionId)` | `POST /practice/sessions/{id}/lifecycle` | ❌ 无页面调用。lifecycle 统一操作通过 `controlLifecycle(sessionId, "pause")` 实现，但独立 `pauseSession` 包装方法未被使用 |
| `resumeSession(sessionId)` | `POST /practice/sessions/{id}/lifecycle` | ❌ 无页面调用。同上 |

### 2.2 会话消息域 `api.sessions.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `list(params)` | `GET /sessions` | ❌ 无页面调用（用户历史通过 `/users/me/history` 获取） |
| `getEnhancedReport(sessionId)` | `GET /sessions/{id}/enhanced-report` | ❌ 无页面调用 |
| `getMessages(sessionId, params)` | `GET /sessions/{id}/messages` | ❌ 无页面调用（报告页不使用消息级数据） |
| `getMessageDetail(sessionId, msgId)` | `GET /sessions/{id}/messages/{mid}` | ❌ 无页面调用 |

### 2.3 回训域 `api.retraining.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `createTask(params)` | `POST /retraining/tasks` | ❌ 无页面调用 |
| `startTaskSession(taskId, params)` | `POST /retraining/tasks/{id}/start-session` | ✅ 在 `dashboard/page.tsx:514` 使用 |
| `completeTaskWithSession(taskId, params)` | `POST /retraining/tasks/{id}/complete-with-session` | ✅ 在 `report/page.tsx:1009` 使用 |
| `listTasks(params)` | `GET /retraining/tasks` | ✅ 在 `dashboard/page.tsx:408` 使用 |

> 创建回训任务功能缺失。

### 2.4 主管域 `api.supervisor.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `listTeamReports(params)` | `GET /supervisor/team/reports` | ❌ 无页面调用 |
| 其他 8 个方法 | — | ✅ 均在 supervisor-training 和 report 页面使用 |

### 2.5 通用分析域 `api.analyticsOpen.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `getDashboard()` | `GET /analytics/dashboard` | ✅ 在 admin/page.tsx 使用 |
| `getScoreDistribution(params)` | `GET /analytics/score-distribution` | ❌ 无页面调用 |
| `getTrends(params)` | `GET /analytics/trends` | ❌ 无页面调用（admin analytics 使用 `api.analytics.getTrends`） |
| `getPracticeHistory(params)` | `GET /analytics/practice/history` | ❌ 无页面调用 |
| `getStorageStats()` | `GET /analytics/storage` | ❌ 无页面调用 |

### 2.6 Dashboard 域 `api.dashboard.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `markNotificationRead(notificationId)` | `POST /growth/notifications/{id}/read` | ❌ 无页面调用 |
| `getAdaptiveDifficultyDryRun(limit)` | `GET /growth/adaptive-difficulty/dry-run` | ❌ 无页面调用 |
| 其他 6 个方法 | — | ✅ 已在 dashboard/leaderboard 页面使用 |

### 2.7 Admin 域 `api.admin.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `validateSalesCombinationRuleSet(payload)` | `POST /admin/business-rules/sales-combinations/validate` | ❌ 无页面调用 |
| `getPracticeTemplate(templateId)` | `GET /admin/curriculum-practice/templates/{id}` | ❌ 无页面调用 |
| `getExaminerAgent(agentId)` | `GET /admin/curriculum-practice/examiner-agents/{id}` | ❌ 无页面调用 |
| `updateKnowledgeBase(kbId, payload)` | `PUT /admin/knowledge/{kb_id}` | ❌ 无页面调用 |
| `getRagProfile(profileId)` | `GET /admin/rag-profiles/{id}` | ❌ 无页面调用 |
| `getRagProfileKnowledgeBases(profileId)` | `GET /admin/rag-profiles/{id}/knowledge-bases` | ❌ 无页面调用 |
| `getRealtimeEvaluationFeedback(sessionId)` | `GET /evaluation/sessions/{id}/feedback` | ❌ 无页面调用 |
| `previewEffectiveVoicePolicy(agentId)` | `GET /admin/voice-runtime/agents/{id}/effective` | ❌ 无页面调用 |
| `deletePromptTemplate(templateId)` | `DELETE /prompt-templates/{id}` | ❌ 无页面调用（使用 `updatePromptTemplate` 设为停用） |
| `quarantineInvalidPromptTemplates()` | `POST /prompt-templates/governance/quarantine-invalid` | ❌ 无页面调用 |
| `getPromptTemplateForScenario(scenarioType)` | `GET /prompt-templates/by-scenario/{scenario_type}` | ❌ 无页面调用 |

### 2.8 AdminTools 域 `api.adminTools.*`

| 方法 | 后端端点 | 状态 |
|------|----------|------|
| `getSystemLog(logId)` | `GET /admin/system-logs/{id}` | ❌ 无页面调用（复数 `getSystemLogs` 有使用） |
| `getAuditTrail(params)` | `GET /admin/audit-trail` | ❌ 无页面调用 |
| `duplicatePersona(personaId)` | `POST /admin/personas/{id}/duplicate` | ❌ 无页面调用 |
| `previewTTS(payload)` | `POST /admin/model-configs/tts/preview` | ❌ 无页面调用（Blob 版 `previewTTSBlob` 有使用） |
| `exportUsersFile(params)` | `GET /admin/users/export` | ❌ 无页面调用（`api.admin.exportUsers` 有使用） |
| `exportAnalyticsFile(params)` | `GET /admin/analytics/export` | ❌ 无页面调用 |

### 2.9 其他域

| 域 | 方法 | 状态 |
|----|------|------|
| `api.analytics.*` | `getManagerLiteLists(params)` | ❌ 无页面调用 |
| `api.training.*` | `getActiveSalesCombinations()` | ❌ 无页面调用 |
| `api.training.*` | `createSession(payload)` | ❌ 无页面调用（使用 `api.practice.createSession`） |
| `api.scenarios.*` | `getById(scenarioId)` | ❌ 无页面调用 |
| `api.agents.*` | `list(params)` / `get(agentId)` | ❌ 无页面调用（使用 `getList`/`getAgentWithPersonas`/`admin.getAgents`） |
| `api.internal.*` | `searchKnowledge(kbId, query)` | ❌ 无页面调用（使用 `admin.searchKnowledgeBase`） |

### 2.10 Config Bundles / Config Center 域（API 层已定义，UI 全量未使用）

以下 9 个方法在 `client.ts` 中定义，后端 `admin/api/config_bundles.py` / `admin/api/config_center.py` 有完整实现并已注册路由，但无前端页面使用：

`listConfigBundles` / `listConfigBundleVersions` / `createConfigBundleDraft` / `validateConfigBundle` / `previewConfigBundle` / `publishConfigBundle` / `rollbackConfigBundle` / `disableConfigBundle` / `listConfigCenterDomains`

**复核结论**：这不是“client 方法缺失”，而是“后端 + API client 已就绪，但 `web/src/app/admin/` 没有 Config Bundles / Config Center 管理页面”。应作为产品 backlog，而不是删除 API。

---

## 三、前后端重复实现与冗余路径

### 3.1 知识库别名路由 — ~18 个兼容别名端点 ← 待弃用策略

**后端文件**：`backend/src/router_registry.py` → `_build_knowledge_bases_alias_router()`

| 路径前缀 | 说明 |
|----------|------|
| `/api/v1/admin/knowledge-bases/...` | 与 `/api/v1/admin/knowledge/...` 完全镜像，包含 CRUD + 文档管理 + 词典 + 搜索 + RAG 配置 |

**现状**：前端 100% 使用主路径 `/admin/knowledge/...`。别名路由无任何前端引用（`web/src/` 下未搜索到 `knowledge-bases` 带连字符的引用）。该别名由 `_build_knowledge_bases_alias_router()` 动态复制主路由，属于向后兼容桥梁，不是当前 bug；建议记录弃用窗口，确认无外部调用后再移除。

### 3.2 音频分段域的独立包装 — 3 个方法 ← 可清理

| 域 | 定义位置 | 使用情况 |
|----|----------|----------|
| `api.practice.audioSegments.*` | client-domains.ts | ✅ `use-continuous-audio-uploader.ts` 使用 |
| `api.audioSegments.*`（独立） | client.ts 内联 | ❌ 无页面调用 |

### 3.3 adminPresentations 域 — 13 个方法（补充性而非冗余）

**特殊说明**：`api.adminPresentations.*` 对应后端 `admin/api/admin.py` 中的管理员演示文稿管理路由（带 OCR、向量摄取、安全路径校验），与 `api.presentations.*` 对应的用户端路由（带缩略图、进度追踪）功能互补。但前端所有管理页（`admin/presentations/`）使用 `api.presentations.*`（用户端）而非 `api.adminPresentations.*`（管理端），导致：

- 管理员上传 PPT 不走管理端的 OCR + 向量摄取流水线
- `adminPresentations` 域定义的 13 个方法无任何前端页面调用

建议：将管理演示文稿页面迁移到使用 `api.adminPresentations.*`，以利用管理端的安全上传和 OCR 能力。

---

## 四、前端绕过 API Client 的直接调用

以下 HTTP 请求未经过 `api.*` 客户端，而是直接使用裸 `fetch` 或 `navigator.sendBeacon`。

| # | 文件 | 行号 | 方法 | URL | 后端端点 | 评估 |
|---|------|------|------|-----|----------|------|
| 1 | `app/(auth)/login/page.tsx` | 123 | GET | `/auth/providers` | `/api/v1/auth/providers` | ✅ 已迁移到 `api.auth.getProviders()` |
| 2 | `app/(auth)/login/page.tsx` | 203 | POST | 动态 dev-login URL | `/api/v1/auth/dev-login` | ✅ 已迁移到 `api.auth.devLogin()` |
| 3 | `lib/server-auth.ts` | 38 | GET | `/users/me` | `/api/v1/users/me` | ✅ 服务端组件合理绕过 |
| 4 | `hooks/use-continuous-audio-uploader.ts` | 223 | PUT | 预签名 OSS URL | 非后端 API | ✅ 对象存储直接上传，标准做法 |
| 5 | `lib/performance.ts` | 99/115 | POST | `/analytics/{eventType}` | `/api/v1/analytics/{type}` | ✅ 遥测投递，使用 keepalive:true 保证页面关闭时送达 |
| 6 | `lib/performance.ts` | 132 | POST | `/analytics/{eventType}` | `/api/v1/analytics/{type}` | ✅ sendBeacon 备用投递 |

**复核结论**：原需修复项 #1-#2 已收敛到 `api.auth` 域；保留 #3-#6 为合理绕过（服务端会话检查、OSS 直传、遥测 keepalive/sendBeacon）。

---

## 五、前后端 HTTP 方法不一致

| 前端调用 | 后端定义 | 文件 | 状态 |
|----------|----------|------|------|
| `PUT /api/v1/admin/users/{id}` | `PUT /api/v1/admin/users/{user_id}` | 前端：`client.ts:3283`；后端：`admin/api/users.py:905` | ✅ 已一致 |
| `PUT /api/v1/admin/users/{id}/role` | `PUT /api/v1/admin/users/{user_id}/role` | 前端：`client.ts:3289`；后端：`admin/api/users.py:972` | ✅ 角色更新已拆分 |

**复核结论**：原 `PATCH` vs `PUT` 冲突已由 `fix(api): align admin user update client` 与 `fix(admin): split user profile and role updates` 修复，不再计入异常。

---

## 六、汇总统计与优先级

### 6.1 异常条目统计

| 异常类别 | 数量 | 说明 |
|----------|------|------|
| **后端定义但前端完全未调用（孤立端点）** | **25** | 含完整模块 + 单点缺失 |
| ├ 完整模块：Release Verification（9 端点） | 9 | 无管理页面，DevOps 工具链 |
| ├ 运行时指标分析（4 端点） | 4 | analytics 页缺 Tab |
| ├ 训练任务终态（3 端点） | 3 | complete/cancel/expire |
| ├ 学员画像/自评（2 端点） | 2 | 学习路径缺画像卡片 |
| ├ 成长通知/目标（2 端点） | 2 | 通知列表 + 目标设定缺失 |
| ├ 设置验证/审计（2 端点） | 2 | 配置流程缺验证和审计 |
| ├ 会话诊断/报告（3 端点） | 3 | 诊断入口 + 报告轮询缺失 |
| **前端定义但无页面调用的孤立 API 方法** | **35** | 见第二章各项 |
| **多余前端 API 域（备选路径）** | 3 | audioSegments（独立） |
| **知识库别名路由冗余** | ~18 | 可用删除 |
| **前后端 HTTP 方法不一致** | **0** | Admin Users 已统一为 PUT，并拆分角色更新 |
| **前端绕过 API client（需修复）** | **0** | 登录页 2 处已迁移到 `api.auth`；剩余绕过均为合理例外 |

### 6.2 修复优先级

| 优先级 | 内容 | 操作 |
|--------|------|------|
| **P0** | Admin Users PUT vs PATCH 不一致 | ✅ 已完成：前端统一 PUT，角色更新走专用端点 |
| **P1** | Training Tasks 缺少 complete/cancel/expire + 独立管理页面 | 新增终态操作按钮训练任务管理页面 |
| | Retraining 缺少 createTask 入口 | 在 Dashboard 添加「创建回训任务」按钮 |
| **P2** | Settings 欠 validate/audit | 配置表单加校验按钮，面板加审计入口 |
| | Learner profile/self-assessment 缺失 | 学习路径页加画像卡片 + 自评入口 |
| | Admin Analytics 4 端点未接入 | 数据分析页新增运行时监控 Tab |
| | Growth notifications list + goals upsert 缺失 | Dashboard 通知中心 + 目标设定 |
| | Report Status 无轮询 | 报告过渡页加进度条轮询 |
| **P3** | 35 个无调用方 API 方法清理 | 逐条评估：保留（后续使用）或移除（死代码） |
| | Knowledge Bases Alias 路由评估移除 | 确认无历史依赖后删除 |
| | adminPresentations 迁移到 `api.adminPresentations.*` | 管理页使用管理端 API 以利用 OCR 安全上传 |
| | Release Verification 管理界面 | 按需决定是否开发 |
| | 登录页 2 处绕过迁移到 `api.auth` | ✅ 已完成：`getProviders` / `devLogin` 进入 auth domain |
