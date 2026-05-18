# 后端 API 接口全量核查 — 异常清单与修复指引

> **核查范围**：后端 54 个路由模块，共计 315+ REST 端点 + 6 WebSocket 端点
> **核查方式**：多轮地毯式搜索，覆盖：
>   1. 后端所有 `@router.*` `@app.*` 装饰器 + `app.include_router` 路由注册
>   2. 前端 `client.ts` / `client-domains.ts` 中每个 API 方法的定义
>   3. 前端每个页面/组件文件中对 `api.*` 的实际调用匹配
>   4. 前端绕过 API client 的裸 `fetch` / `axios` / `sendBeacon` 调用
>   5. 前端所有 WebSocket 连接
> **核查日期**：2026-05-18

---

## 目录

1. [后端定义但前端完全未调用的 API](#一后端定义但前端完全未调用的-api)
2. [前端定义了方法但无页面调用的孤立 API 域](#二前端定义了方法但无页面调用的孤立-api-域)
3. [前后端同名路径冗余（重复实现）](#三前后端同名路径冗余重复实现)
4. [前端走 user API 而非 admin API 的路径偏差](#四前端走-user-api-而非-admin-api-的路径偏差)
5. [前端绕过 API client 的直接调用](#五前端绕过-api-client-的直接调用)
6. [前后端 HTTP 方法不一致](#六前后端-http-方法不一致)
7. [汇总统计与优先级](#七汇总统计与优先级)

---

## 一、后端定义但前端完全未调用的 API

### 1.1 发布验证模块（Release Verification）— 9 个端点

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

**现状**：整个模块（9 个端点）在 `web/src/` 下零匹配，完全无前端页面。该模块实现 FR40（发布门禁检查记录与追踪），但当前只能通过 API 工具手动调用。

---

### 1.2 运行时指标分析 — 4 个端点

**后端文件**：`backend/src/admin/api/analytics.py`
**所属模块**：Admin 数据分析 `/api/v1/admin/analytics/` 前缀
**权限要求**：Admin

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/admin/analytics/runtime-metrics` | 运行时指标（FR39）：恢复成功率（目标≥99%）、误触发率（目标<1%）、完整率（目标≥98%）、会话分布与语音模式占比 | 数据分析页新增「运行时监控」Tab 或独立卡片区 |
| 2 | GET | `/api/v1/admin/analytics/policy-effectiveness` | 各 Agent 策略有效性排名对比（7d/30d/90d） | 同上 Tab 内条形图/表格展示 |
| 3 | GET | `/api/v1/admin/analytics/voice-mode-comparison` | StepFun Realtime 与 Legacy 语音模式性能对比 | 同上 Tab 内双柱对比图 |
| 4 | GET | `/api/v1/admin/analytics/fallback-metrics` | TTS/ASR/LLM 各级降级链触发次数与浏览器 TTS 兜底使用率 | 同上 Tab 内流向图+统计表 |

**现状**：前端 `admin/analytics/page.tsx` 已使用 `overview`/`trends`/`agents`/`leaderboard`/`operating-pack`，但以上 4 个端点及对应 `client.ts` 方法（`getRuntimeMetrics`/`getPolicyEffectiveness`/`getVoiceModeComparison`/`getFallbackMetrics`）均未接入任何页面。

---

### 1.3 训练任务终态操作 — 3 个端点

**后端文件**：`backend/src/common/api/training_tasks.py`
**所属模块**：训练任务 `/api/v1/training-tasks` 前缀

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | POST | `/api/v1/training-tasks/{task_id}/complete` | 学员完成训练后标记任务完成（关联 session_id+notes） | Dashboard 训练任务列表 → pending 任务提供「完成」按钮 |
| 2 | POST | `/api/v1/training-tasks/{task_id}/cancel` | 管理员取消 pending 状态任务 | 管理端 → 分配任务列表每行「取消」操作 |
| 3 | POST | `/api/v1/training-tasks/{task_id}/expire` | 管理员标记超期任务为过期 | 管理端 → 分配任务列表「标记过期」操作 |

**现状**：前端 `client-domains.ts` 定义了 `create`/`list`/`get`/`update`/`startSession`/`batchAssign`，但来自页面组件调用的实际使用只有 `batchAssign`（在 `admin/users/page.tsx:389`）。其余方法仅在测试文件中使用。`complete`/`cancel`/`expire` 三个终态操作未在 `client.ts` 中定义任何方法。

---

### 1.4 学员画像与自我评估 — 2 个端点

**后端文件**：`backend/src/curriculum_practice/api.py`
**所属模块**：学习路径 `/api/v1/curriculum-practice/learning-path` 前缀

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/curriculum-practice/learning-path/me/profile` | 获取学员画像（能力等级、学习偏好、历史趋势），若不存在则自动创建默认档案 | 学习路径页 → 顶部「学习档案」卡片 + 雷达图 |
| 2 | POST | `/api/v1/curriculum-practice/learning-path/me/profile/self-assessment` | 学员自评能力等级，系统记录并更新画像用于校准 | 同上卡片 →「自我评估」按钮弹出等级选择器 |

**现状**：前端 `learning-path/page.tsx` 仅使用 `learning-path/me` 和 `learning-path/me/next-task`。`self-assessment`/`learnerProfiles` 在 `web/src/` 下零匹配。值得注意的是，后端同时暴露了 `/api/v1/admin/curriculum-practice/learner-profiles/{user_id}/override`（管理员覆盖学员画像），前端 `admin/users/[id]/page.tsx` 使用了 `api.admin.overrideLearnerProfile`，但学员端自画像和自我评估完全缺失。

---

### 1.5 成长中心通知列表与目标设置 — 2 个端点

**后端文件**：`backend/src/common/api/growth.py`
**所属模块**：成长中心 `/api/v1/growth` 前缀

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/growth/notifications` | 拉取通知列表（支持 include_read 参数），包含目标达成提醒、新推荐、能力提升提示等 | Dashboard → 通知铃铛 → 点击弹出通知列表下拉面板 |
| 2 | PUT | `/api/v1/growth/goals/current` | 用户设置训练目标（weekly_sessions/monthly_presentations + 数量 + 周期 + 起止日期） | Dashboard →「成长目标」卡片 →「编辑目标」按钮弹出表单 |

**修正后现状**：`api.dashboard.getGrowth` 已在 `web/src/app/(dashboard)/page.tsx:431` Dashboard 成长卡片中使用。
`api.dashboard.markNotificationRead` / `api.dashboard.getAdaptiveDifficultyDryRun` 仅在 API client 中定义，当前未发现生产页面调用。通知列表与已读操作应作为 Dashboard 通知中心 backlog 处理，而不是已接入能力。通知列表查询和目标设置两个接口在前端完全缺失。

---

### 1.6 管理后台配置验证与审计 — 2 个端点

**后端文件**：`backend/src/admin/api/settings.py`
**所属模块**：系统配置 `/api/v1/admin/settings` 前缀
**权限要求**：`ADMIN_SETTINGS_MANAGE_PERMISSION`

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | POST | `/api/v1/admin/settings/{surface}/validate` | 保存前校验配置 JSON 值的合法性，返回归一化值或验证错误（含审计日志写入） | 设置页每个配置编辑表单底部「校验配置」按钮 |
| 2 | GET | `/api/v1/admin/settings/{surface}/audit` | 查询某配置项变更历史审计日志（最近 50 条：操作人、类型、新旧值对比、时间） | 设置页每个配置面板的「审计日志」按钮 → 时间线视图 |

**现状**：前端 `admin/settings/page.tsx` 已使用 `get`/`drafts`/`preview`/`publish`/`rollback` 完整五步流程，但缺少前置验证和事后审计。用户无法在 UI 上验证配置合法性，变更后也无法追溯。

---

### 1.7 练习会话诊断与报告 — 3 个端点

**后端文件**：`backend/src/common/api/practice.py`

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/practice/sessions/{session_id}/diagnostics` | StepFun Realtime 会话运行时诊断证据链（config_binding、evaluation_run、report_snapshot、knowledge_answer_diagnostics、failure_details） | 演练记录详情页 →「诊断信息」按钮展示完整 JSON |
| 2 | GET | `/api/v1/practice/sessions/{session_id}/comprehensive-report` | 综合评估报告（分维度评分+阶段摘要+优势改进点+推荐），含 report_status 状态检查 | 练习报告页，与现有 `/evaluation/sessions/{id}/report` 统一 |
| 3 | GET | `/api/v1/practice/sessions/{session_id}/report-status` | 轮询异步报告生成进度（current_stage + progress_percent + estimated_remaining_seconds） | 练习结束过渡页 → 进度条轮询，就绪后自动跳转报告页 |

**现状**：前端 `client.ts` 定义了 `api.practice.getSession`，但以上 3 个端点均无任何页面使用。报告页当前使用 `POST/GET /evaluation/sessions/{id}/report` 替代 `comprehensive-report`，缺乏报告状态轮询机制。

---

### 1.8 功能开关查询 — 1 个端点

**后端文件**：`backend/src/common/api/feature_flags.py`

| # | 方法 | 完整路径 | 接口功能 | 前端应接入位置 |
|---|------|----------|----------|---------------|
| 1 | GET | `/api/v1/feature-flags` | 列出所有功能开关及其启用状态（如 examiner 功能开关） | 考核页面等需要按功能开关决定是否显示 |

**修正后现状**：`api.featureFlags.get()` 已在 `web/src/app/(user)/exam/[sessionId]/page.tsx` 中用于读取 examiner 开关，因此不属于孤立 API。该端点保留，不进入删除或补 UI 清单。

---

## 二、前端定义了方法但无页面调用的孤立 API 域

以下 API 域在前端 `client.ts` / `client-domains.ts` 中明确定义了方法，且后端有对应端点，但没有任何页面或组件文件实际调用这些方法。

### 2.1 功能开关域 `api.featureFlags.*`

| 方法 | 后端确认 |
|------|----------|
| `api.featureFlags.get` → `GET /feature-flags` | ✅ 存在 |

**修正后现状**：`api.featureFlags.get()` 已在 `web/src/app/(user)/exam/[sessionId]/page.tsx` 使用，应从孤立 API 清单移除。

### 2.2 领导榜单域 `api.dashboard.*`

| 方法 | 后端确认 | 现状 |
|------|----------|------|
| `api.dashboard.getGrowth` → `GET /growth/dashboard` | ✅ 存在 | **修正后现状**：已在 `web/src/app/(dashboard)/page.tsx:431` Dashboard 成长卡片中使用 |
| `api.dashboard.getAdaptiveDifficultyDryRun` → `GET /growth/adaptive-difficulty/dry-run` | ✅ 存在 | 仅定义，无页面调用 |
| `api.dashboard.getPublicLeaderboard` → `GET /analytics/leaderboard` | ✅ 存在 | **修正后现状**：已在 `web/src/app/(dashboard)/leaderboard/page.tsx` 使用，应从孤立清单移除 |
| `api.dashboard.getMyRank` → `GET /analytics/leaderboard/my-rank` | ✅ 存在 | **修正后现状**：已在 `web/src/app/(dashboard)/leaderboard/page.tsx` 使用，应从孤立清单移除 |

### 2.3 主管报表域 `api.supervisor.*`

| 方法 | 后端确认 | 现状 |
|------|----------|------|
| `api.supervisor.listTeamReports` → `GET /supervisor/team/reports` | ✅ 存在 | 仅定义，无页面调用 |

### 2.4 回训任务域 `api.retraining.*`

| 方法 | 后端确认 | 现状 |
|------|----------|------|
| `api.retraining.createTask` → `POST /retraining/tasks` | ✅ 存在 | 仅定义 |
| `api.retraining.completeTaskWithSession` → `POST /retraining/tasks/{id}/complete-with-session` | ✅ 存在 | 仅定义 |

**说明**：`api.retraining.listTasks` 和 `api.retraining.startTaskSession` 在 Dashboard 页面有调用，但创建和完结操作缺失。

### 2.5 通用分析域 `api.analyticsOpen.*`

| 方法 | 后端确认 | 现状 |
|------|----------|------|
| `api.analyticsOpen.getScoreDistribution` → `GET /analytics/score-distribution` | ✅ 存在 | 仅定义 |
| `api.analyticsOpen.getTrends` → `GET /analytics/trends` | ✅ 存在 | 仅定义 |
| `api.analyticsOpen.getPracticeHistory` → `GET /analytics/practice/history` | ✅ 存在 | 仅定义 |
| `api.analyticsOpen.getStorageStats` → `GET /analytics/storage` | ✅ 存在 | 仅定义 |

**说明**：`api.analyticsOpen.getDashboard` 在 `admin/page.tsx` 和 `admin/analytics/page.tsx` 有使用，但以上 4 个更细化的分析接口未接入。

### 2.6 场景域 `api.scenarios.*`

| 方法 | 后端确认 | 现状 |
|------|----------|------|
| `api.scenarios.getById` → `GET /scenarios/{scenario_id}` | ✅ 存在 | 仅定义 |
| `api.scenarios.getSalesPersonas` → `GET /scenarios/sales/personas` | ✅ 存在（在训练页使用） | 已使用，无误 |

### 2.7 会话消息播放相关 `api.sessions.*`

| 方法 | 后端确认 | 现状 |
|------|----------|------|
| `api.sessions.list` → `GET /sessions` | ✅ 存在 | 仅定义 |
| `api.sessions.getKnowledgeCheck` → `GET /practice/sessions/{id}/knowledge-check` | ✅ 存在 | 仅定义 |
| `api.sessions.getEnhancedReport` → `GET /sessions/{id}/enhanced-report` | ✅ 存在 | 仅定义 |
| `api.sessions.getMessages` → `GET /sessions/{id}/messages` | ✅ 存在 | 仅定义（report 页使用 apiFetch 直接调用） |
| `api.sessions.getMessageDetail` → `GET /sessions/{id}/messages/{mid}` | ✅ 存在 | 仅定义 |
| `api.sessions.getHighlightReview` → `GET /sessions/{id}/highlight-review` | ✅ 存在 | 仅定义 |

---

## 三、前后端同名路径冗余（重复实现）

后端存在两套同名但路径级别不同的 API，前端混合使用导致其中一套完全无效。

### 3.1 演示文稿管理 — 冗余的双路径

| 区分 | 用户路径（被前端使用） | 管理路径（未被前端使用） |
|------|----------------------|----------------------|
| 后端路由 | `/api/v1/presentations/...` | `/api/v1/admin/presentations/...` |
| 后端文件 | `presentation_coach/api/presentations.py` | `admin/api/admin.py` |
| 前端调用 | `api.presentations.*`（client-domains.ts:542） | `api.adminPresentations.*`（client.ts:4464） |
| 页面使用 | ✅ 所有管理/用户演示文稿页均使用此路径 | ❌ 未在任何页面中被调用 |

**受影响的方法**：`list`/`create`/`upload`/`get`/`delete`/`getPages`/`updatePage`/`getTalkingPoints`/`addTalkingPoint`/`deleteTalkingPoint`/`getForbiddenWords`/`addForbiddenWord`/`deleteForbiddenWord` 共计 **13 个方法**。

### 3.2 知识库别名路由 — 冗余镜像

| 区分 | 主路径（被前端使用） | 别名路径（未被前端使用） |
|------|---------------------|----------------------|
| 路径 | `/api/v1/admin/knowledge/...` | `/api/v1/admin/knowledge-bases/...` |
| 后端文件 | `common/knowledge/api.py` | `router_registry.py`（`_build_knowledge_bases_alias_router()`） |
| 说明 | 完整 CRUD + 文档管理 + 词典 + 搜索 + RAG 配置 | 完全镜像，含 ~18 个子路由 |

**说明**：别名路由是为了兼容历史路径而创建。前端 100% 使用主路径，别名无任何调用。

### 3.3 音频分段域 — 冗余的双定义

| 区分 | 通过 practice 域（被前端使用） | 独立域（未被前端使用） |
|------|-----------------------------|----------------------|
| 前端调用 | `api.practice.audioSegments.*` | `api.audioSegments.*`（client.ts 内联） |
| 端点 | `POST /practice/sessions/{id}/audio-upload-urls` 等 | 同样端点 |
| 页面使用 | ✅ `use-continuous-audio-uploader.ts` 使用 | ❌ 未在任何页面中使用 |

**受影响的方法**：`createUploadUrl`/`register`/`registerFailure` 共计 **3 个方法**。

---

## 四、前端走 User API 而非 Admin API 的路径偏差

此类别与第三类不同：后端 Admin 路由和 User 路由是不同实现，但前端统一使用 User 路由。

### 4.1 管理后台配置包（Config Bundles）— 8 个端点

**后端文件**：`backend/src/admin/api/config_bundles.py`
**后端端点**：`/api/v1/admin/config-bundles/...`

| 方法 | 前端 `client.ts` 调用 | 页面使用 |
|------|----------------------|----------|
| `listConfigBundles` | ✅ 已定义 | ❌ 无页面使用 |
| `listConfigBundleVersions` | ✅ 已定义 | ❌ 无页面使用 |
| `createConfigBundleDraft` | ✅ 已定义 | ❌ 无页面使用 |
| `validateConfigBundle` | ✅ 已定义 | ❌ 无页面使用 |
| `previewConfigBundle` | ✅ 已定义 | ❌ 无页面使用 |
| `publishConfigBundle` | ✅ 已定义 | ❌ 无页面使用 |
| `rollbackConfigBundle` | ✅ 已定义 | ❌ 无页面使用 |
| `disableConfigBundle` | ✅ 已定义 | ❌ 无页面使用 |
| `listConfigCenterDomains` | ✅ 已定义 | ❌ 无页面使用 |

**说明**：前端 `admin/settings/page.tsx` 使用 `api.admin.getAdminSettingsSurface` 等走 `settings/{surface}` 路径的接口，但 `config-bundles` 独立路径的接口完全无页面接入。

### 4.2 管理后台 Model Configs 测试 — 2 个端点

| 方法 | `client.ts` 调用 | 页面使用 |
|------|------------------|----------|
| `api.admin.testModelConfig` → `POST /admin/model-configs/{id}/test` | ✅ 已定义 | ✅ 已在 `admin/settings/page.tsx` 使用 |
| `api.admin.testModelConfigInline` → `POST /admin/model-configs/test` | ✅ 已定义 | ✅ 已在 `admin/settings/page.tsx` 使用 |

**修正后现状**：`api.admin.testModelConfig` 与 `api.admin.testModelConfigInline` 已在 `web/src/app/admin/settings/page.tsx` 使用，不属于未接入 API。该项应从异常清单移除。

### 4.3 语音运行时策略预览 — 1 个端点

| 方法 | `client.ts` 调用 | 页面使用 |
|------|------------------|----------|
| `api.admin.previewEffectiveVoicePolicy` → `GET /admin/voice-runtime/agents/{id}/effective` | ✅ 已定义 | ❌ 无页面使用 |

### 4.4 提示词模板管理 — 2 个端点

| 方法 | `client.ts` 调用 | 页面使用 |
|------|------------------|----------|
| `api.admin.deletePromptTemplate` → `DELETE /prompt-templates/{id}` | ✅ 已定义 | ❌ 无页面使用 |
| `api.admin.quarantineInvalidPromptTemplates` → `POST /prompt-templates/governance/quarantine-invalid` | ✅ 已定义 | ❌ 无页面使用 |
| `api.admin.getPromptTemplateForScenario` → `GET /prompt-templates/by-scenario/{scenario_type}` | ✅ 已定义 | ❌ 无页面使用 |

**说明**：模板管理页使用 `updatePromptTemplate`（设为停用）而非 `deletePromptTemplate`。

### 4.5 管理后台评估相关 — 1 个端点

| 方法 | `client.ts` 调用 | 页面使用 |
|------|------------------|----------|
| `api.admin.getRealtimeEvaluationFeedback` → `GET /evaluation/sessions/{id}/feedback` | ✅ 已定义 | ❌ 无页面使用 |

---

## 五、前端绕过 API Client 的直接调用

以下 HTTP 请求未经过 `api.*` 客户端，而是直接使用裸 `fetch` 或 `navigator.sendBeacon`。

| # | 文件 | 行号 | 方法 | URL | 后端端点 | 说明 |
|---|------|------|------|-----|----------|------|
| 1 | `app/(auth)/login/page.tsx` | 123 | GET | `/auth/providers` | `/api/v1/auth/providers` | 使用本地 `buildApiUrl()` 拼接，无 `api.*` 的错误处理/超时机制 |
| 2 | `app/(auth)/login/page.tsx` | 203 | POST | provider 返回的动态 URL（指向 `/auth/dev-login`） | `/api/v1/auth/dev-login` | 开发登录功能，未使用 `api.auth.login` 或 `api.auth.devLogin` |
| 3 | `lib/server-auth.ts` | 38 | GET | `/users/me` | `/api/v1/users/me` | 服务端组件中运行，无法使用浏览器端 `api.*`，属于合理绕过 |
| 4 | `hooks/use-continuous-audio-uploader.ts` | 223 | PUT | 预签名 OSS URL | 非后端 API | 直接上传音频到对象存储，属于标准做法 |
| 5 | `hooks/use-continuous-audio-uploader.ts` | 144 | POST | 预签名失败回退 URL | 同上 | 回退路径，标准做法 |
| 6 | `lib/performance.ts` | 99/115 | POST | `/analytics/{eventType}` | `/api/v1/analytics/{type}` | 遥测投递，使用 `keepalive: true` 保证页面关闭时送达 |
| 7 | `lib/performance.ts` | 132 | POST | `/analytics/{eventType}` | `/api/v1/analytics/{type}` | 备用 `sendBeacon` 投递，比 fetch 更可靠 |

**评估**：7 处绕过中：
- #1-#2：登录页绕过，缺少 `api.*` 的错误处理（无 CSRF token、无统一错误提示）
- #3：服务端合理绕过
- #4-#5：OSS 上传，标准做法
- #6-#7：遥测投递，有意为之

---

## 六、前后端 HTTP 方法不一致

| 前端调用 | 后端定义 | 文件 | 影响 |
|----------|----------|------|------|
| `PATCH /api/v1/admin/users/{id}` | `PUT /api/v1/admin/users/{user_id}` | 前端：`client.ts:3400`；后端：`admin/api/users.py` | FastAPI 严格区分 HTTP 方法，PATCH 请求可能被 405 拒绝 |
| `api.pauseSession` 和 `api.resumeSession` 定义为独立方法但无页面调用 | `POST /practice/sessions/{id}/lifecycle`（统一生命周期接口） | 前端的 pause/resume 可能通过统一 `transition` 实现 | 不匹配但无功能影响 |

---

### 删除准则

后端 API 不能仅因"前端未调用"删除。只有同时满足以下条件，才允许进入删除候选：无生产前端调用、无后端测试、无 API 契约文档、无 `router_registry.py` 兼容别名、无 release/governance/admin-only/ops 语义、无外部集成文档或脚本引用。

不满足任一条件时，应选择保留、标记 backlog，或走 deprecated 迁移计划。

---

## 七、汇总统计与优先级

### 7.1 异常条目统计

| 异常类别 | 数量 | 说明 |
|----------|------|------|
| **后端定义但前端完全未调用（孤立端点）** | **32** | 含完整模块 + 单点缺失（功能开关已修正为非异常） |
| ├ 完整模块：Release Verification | 9 | 无管理页面 |
| ├ 运行时指标（4 端点） | 4 | 有管理页面但未接入 |
| ├ 训练任务终态（3 端点） | 3 | 生命周期的 complete/cancel/expire |
| ├ 学员画像/自评（2 端点） | 2 | 学习路径缺少画像卡片 |
| ├ 成长通知/目标（2 端点） | 2 | 通知铃铛无列表/无目标设定 |
| ├ 设置验证/审计（2 端点） | 2 | 配置流程缺少验证和审计 |
| ├ 会话诊断/报告（3 端点） | 3 | 缺少诊断入口和报告轮询 |
| ├ ~~功能开关~~（1 端点，已修正） | 0 | 已在 `exam/[sessionId]/page.tsx` 正常使用 |
| └ 其他单点缺失 | 7 | 见各域统计 |
| **前端定义但无页面调用的冗余域** | **30+** | |
| ├ 演示文稿管理域（adminPresentations） | 13 | 与 presentations.* 重复 |
| ├ 知识库别名路由（knowledge-bases） | ~18 | 与 knowledge/* 完全重复 |
| ├ 音频分段独立域（audioSegments） | 3 | 与 practice.audioSegments 重复 |
| **前端页面级未使用的 API 方法** | **39** | client.ts 中定义但 app/components 未使用（testModelConfig x 2 已修正为非异常） |
| **前后端 HTTP 方法不一致** | **1** | Admin Users PUT vs PATCH |
| **前端绕过 API client 的调用** | **4**（需修复） | 登录页 2 处 + 遥测 URL 拼接 |

### 7.2 修复优先级

#### P0 — 影响功能正确性

| 异常 | 影响 | 操作 |
|------|------|------|
| Admin Users PATCH vs PUT 不一致 | 用户更新操作可能 405 | 统一为 PATCH（语义更匹配）或改为 PUT |
| Training Tasks 终态操作缺失 | 任务生命周期无法完结 | 前端新增 complete/cancel/expire 调用 |
| `api.practice.pauseSession/resumeSession` 未使用 | 会话暂停/恢复功能不可用 | 确认是否通过 lifecycle 统一接口实现，或将 pause/resume 接入页面 |

#### P1 — 影响管理效率

| 异常 | 影响 | 操作 |
|------|------|------|
| Report status 无轮询 | 报告生成完成前用户看到空态 | 报告过渡页添加进度轮询 |
| Settings validate/audit 缺失 | 配置错误保存前无法发现，变更无法追溯 | 配置表单添加校验按钮和审计入口 |
| Growth notifications/goals 缺失 | 通知无列表、目标不能自主设定 | Dashboard 添加通知中心与目标卡片 |
| Learner profile/self-assessment 缺失 | 学员画像无展示、自评无入口 | 学习路径页添加画像卡片 |
| ~~Feature flags 未调用~~ | 已修正：`exam/[sessionId]/page.tsx` 已使用 `api.featureFlags.get()` | 无需操作 |

#### P2 — 重复代码清理

| 异常 | 操作 |
|------|------|
| adminPresentations 域（13 方法） | 前端改为使用此域或移除冗余定义 |
| Knowledge Bases Alias 路由（~18 端点） | 评估后移除或保留，前端使用主路径不变 |
| audioSegments 独立域（3 方法） | 移除或重定向到 practice.audioSegments |
| 其他 39 个已定义但无调用方的方法 | 逐条评估：保留（后续使用）或移除（死代码） |

#### P3 — 低优先级 / 新功能

| 异常 | 操作 |
|------|------|
| Release Verification 模块 | 按需决定是否开发管理界面 |
| Admin Analytics 4 个细化端点 | 数据分析页新增监控 Tab |
| Config Bundles 8 个端点 | 按需决定是否接入配置管理页 |
| Sessions diagnostics/report 端点 | 统一报告生成入口 |
