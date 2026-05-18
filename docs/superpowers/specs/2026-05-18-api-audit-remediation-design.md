# API 审计修复设计

日期：2026-05-18  
任务源：`docs/api-contract/api-audit-anomaly-report.md`  
策略：A，保守修复

## 目标

把 API 审计报告修正为可信任务源，并基于它完成低风险修复：

1. 修复当前会影响功能的真实缺陷。
2. 修正文档中已确认的误报。
3. 移除明确冗余的前端 API wrapper。
4. 适度丰富已有页面，优先使用已经请求或容易接入的数据。
5. 后端 API 不因“前端未调用”直接删除。

## 非目标

- 不建设新的大型管理页面，例如 Release Verification 或 Config Bundles 全量 UI。
- 不删除有测试、契约文档、router alias、运维语义或潜在外部调用的后端 API。
- 不重构无关页面结构。
- 不提交当前工作区已有改动。

## 删除准则

后端 API 只有同时满足以下条件才允许进入删除候选：

- 无生产前端调用。
- 无后端测试覆盖。
- 无 API 契约文档。
- 无 `router_registry.py` legacy alias 或兼容说明。
- 无 release、governance、admin-only、ops 语义。
- 无外部集成文档或脚本引用。

不满足以上任一条件时，处理方式只能是：保留、文档标记 backlog、或做 deprecated 迁移计划。

## 方案

### 1. 修正文档

更新 `docs/api-contract/api-audit-anomaly-report.md`：

- 标注 `api.featureFlags.get` 已在 `web/src/app/(user)/exam/[sessionId]/page.tsx` 使用。
- 标注 `api.dashboard.getPublicLeaderboard` 和 `api.dashboard.getMyRank` 已在 `web/src/app/(dashboard)/leaderboard/page.tsx` 使用。
- 标注 `api.admin.testModelConfig` 和 `api.admin.testModelConfigInline` 已在 `web/src/app/admin/settings/page.tsx` 使用。
- 修正 `api.dashboard.markNotificationRead`：实际未发现生产页面调用。
- 增加删除准则，避免把“前端未调用”误写成“后端无用”。
- 将大页面建设类条目降级为 backlog，而不是当前缺陷。

### 2. 修复 Admin Users 更新

当前真实缺陷：

- 前端 `api.admin.updateUser` 使用 `PATCH /admin/users/{id}`。
- 后端只注册 `PUT /admin/users/{user_id}`。
- 页面编辑提交 `display_name` 和 `role`。
- 后端普通更新只接受 `name/email/department/is_active/audit_reason`，并拒绝 `role`。

修复：

- 将 `api.admin.updateUser` 改为 `PUT`。
- 将更新 payload 类型收窄为普通资料字段。
- 新增 `api.admin.updateUserRole`，调用 `PUT /admin/users/{id}/role`。
- `web/src/app/admin/users/page.tsx` 普通信息和角色变更分两步提交。

### 3. 前端冗余 wrapper 清理

只删除前端冗余 wrapper，不删后端路由：

- 删除 `api.adminPresentations.*`，页面实际使用 `api.presentations.*`。
- 删除独立 `api.audioSegments.*`，页面实际使用 `api.practice.audioSegments.*`。

其他未调用 client 方法暂保留，因为它们可能对应已实现契约或后续 UI 接入点。

### 4. 适度页面丰富

只做小而有用的 UI 增量：

- `web/src/app/admin/users/page.tsx`：桌面列表增加“部门”列。
- `web/src/app/(dashboard)/page.tsx`：如果当前 `getGrowth()` 数据已加载，展示一个简洁的成就/通知卡片。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`：如果下一步推荐含 `source_session_id`，渲染到源报告的链接。

这些都是 XS/S 改动，避免范围膨胀。

## 数据流

### Admin Users

1. 页面读取编辑表单。
2. 普通资料字段提交到 `api.admin.updateUser(id, { name, email, department })`。
3. 如果角色变化，额外调用 `api.admin.updateUserRole(id, { role })`。
4. 两步都成功后刷新列表并关闭编辑弹窗。
5. 任一步失败时显示错误，不假装成功。

### Growth 卡片

1. Dashboard 已有 `api.dashboard.getGrowth()`。
2. 页面保存 growth 响应。
3. 从 `achievements.unlocked` 和 `notifications` 渲染精简卡片。
4. 不新增目标编辑表单，避免扩大 scope。

### 报告源链接

1. 报告页已有 next recommendation 数据。
2. 若存在 `source_session_id`，显示到 `/practice/{source_session_id}/report` 的链接。
3. 缺失时不显示链接。

## 错误处理

- Admin Users 两步更新中，普通资料成功但角色失败时提示部分失败，并刷新列表以反映真实后端状态。
- Growth 卡片只在数据存在时显示；加载失败不阻塞首页。
- 报告源链接只在字段存在时渲染。
- 删除前端 wrapper 后运行类型检查，确保没有残留引用。

## 测试计划

### 前端单测

- `api.admin.updateUser` 必须使用 `PUT`。
- `api.admin.updateUser` 不接受 `role/display_name`。
- `api.admin.updateUserRole` 必须调用 `PUT /admin/users/{id}/role`。
- Admin 用户页编辑普通资料时调用普通 update。
- Admin 用户页角色变化时调用角色 update。

### 页面验证

- 用户列表展示部门列。
- Dashboard 在有 growth 数据时展示成就/通知卡片。
- 报告页在有 `source_session_id` 时展示源报告链接。

### 静态验证

- `npx tsc --noEmit`。
- 相关 Vitest 测试。
- 搜索 `adminPresentations` 和独立 `api.audioSegments`，确认无残留生产引用。

## 风险

- 当前工作区已有大量未提交改动，实施时必须手术式修改，避免覆盖已有工作。
- 删除前端 wrapper 可能影响测试或未发现的间接引用，必须用全文搜索和类型检查兜底。
- Dashboard growth 响应类型可能与页面展示期望不完全一致，实施时以现有类型为准，不补复杂适配层。

## 成功标准

- 审计报告不再包含已确认误报。
- Admin 用户编辑不会因 PATCH/PUT 或 role payload 返回 405/400。
- 明确冗余前端 wrapper 被移除，后端契约面未被误删。
- 新增 UI 都有清晰降级，不影响核心页面加载。
- 相关测试和类型检查通过，或失败项有明确外部原因记录。
