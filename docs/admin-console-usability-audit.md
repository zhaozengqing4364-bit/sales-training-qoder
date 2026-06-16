# 后台管理控制台可用性审计报告

> 分析日期：2026-06-15  
> 分析范围：`web/src/app/admin/**`、`web/src/components/admin/**`、`web/src/lib/admin/**`  
> 分析视角：完全不了解系统的运营人员首次使用  
> 约束：只读分析，未修改任何代码

---

## 1. 执行摘要

本次审计启用 8 个并行 Agent，对销售训练、学习内容、业务规则、角色/提示词/RAG、课程练习、知识库/检索策略、演示/分析、通用 Admin 共 8 个后台模块进行了只读代码审查。重点关注以下四类问题：

1. **显性 Bug**：运行时错误、状态异常、竞态条件、空值未保护等。
2. **交互设计陷阱**：危险操作无确认、表单校验缺失、筛选/分页行为反直觉、未保存离开无拦截等。
3. **数据流动与绑定问题**：URL 状态未同步、缓存策略缺失、乐观更新无回滚、父子页面状态不一致等。
4. **运营人员认知负担**：术语无解释、错误提示技术化、空/加载/错误状态引导不足、导航层级深等。

### 1.1 关键发现（P0 / 必须立即处理）

| 模块 | 问题 | 对运营人员的影响 |
|------|------|------------------|
| 学习内容 | `QuestionGenerationPanel` 未导出且 JSX 语法错误（`>` 未转义），学习内容详情页在章节区域直接崩溃 | 无法查看/编辑任何学习内容详情 |
| 销售训练 | 录音详情页 `retry()` 成功后未重置 `isOperating`，按钮永久禁用 | 重试成功后页面“卡死”，必须刷新 |
| 销售训练 | 工作台 `dashboard?.summary["record_count"]` 未做空值保护，summary 缺失时白屏 | 后端异常时工作台无法打开 |
| 业务规则 | 销售组合规则发布/回滚后，旧生效版本未加入历史列表，回滚目标消失 | 误以为数据丢失，无法回退到上一版本 |
| 业务规则 | 确认弹窗在 `isLoading` 时仍可通过遮罩/Esc 关闭 | 发布中关闭弹窗后看不到状态，可能重复提交 |
| 通用 Admin | 智能体详情页“删除”按钮未绑定任何事件 | 危险入口无效，反复点击造成焦虑 |
| 演示/分析 | PPT 列表分页逻辑完全失效，翻页内容不变 | 超过 10 条 PPT 后无法查看后续数据 |
| 演示/分析 | Analytics 部分接口失败被静默吞掉，直接显示 0 或空 | 无法区分“无数据”和“接口故障” |

---

## 2. 各模块详细发现

### 2.1 销售训练后台（sales-trainer）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `audio-submissions/[submissionId]/page.tsx` → `retry()` | 成功分支未 `setIsOperating(false)`，按钮持续禁用 | 重试成功后页面像“卡死” | `setIsOperating(false)` 放 `finally` |
| `page.tsx` 第 86/91/98 行 | `dashboard?.summary["record_count"]`，未保护 `summary` | 后端异常时工作台白屏 | 改为 `dashboard?.summary?.["record_count"]` |
| `training-records/[recordType]/[recordId]/page.tsx` 第 287 行 | 直接渲染 `record.operation_logs.length` | 部分记录详情页打不开 | 改为 `record.operation_logs?.length` |
| `score-results/page.tsx` 第 356 行 | 渲染 `v{item.prompt_version}`，未处理空值 | 列表出现 “vundefined” | `v{item.prompt_version ?? "--"}` |
| `articles/import/page.tsx` → `publishRelease()` | 未校验 `releaseImpact` 是否已加载即可发布 | 在不清楚影响范围时误发训练包 | 发布前强制加载影响范围并二次确认 |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `paths/page.tsx` + `path-config-center.tsx` | 保存/发布/回滚路径均无二次确认 | 误触会改变全局训练路径 | 增加 ConfirmDialog，复述影响范围 |
| `material-detail-panel.tsx` | 材料版本“发布为最新版”无确认 | 学员端立即绑定新版本 | 弹窗确认并说明历史记录保留快照 |
| `articles/page.tsx` → `bindContent()` | 绑定新文章直接覆盖 `pendingBinding` | 待发布修订被无声替换 | 若已有待发布绑定，提示是否覆盖 |
| `ai-coach/page.tsx` | 保存/发布完整配置无确认 | 复杂参数误改影响学员会话 | 发布前弹窗摘要关键变更 |
| `question-form.tsx` | 单选题选项为空被过滤，可提交 0 个选项 | 后端报错或学员端异常 | 校验选项非空且正确答案在选项中 |
| `question-form.tsx` | 简答题参考答案允许空字符串 | AI 评分缺少参考 | 简答题参考答案必填 |
| `questions/drafts/page.tsx` | JSON 选项编辑无即时校验 | 格式错误反复猜测 | 即时 JSON 校验并高亮错误 |
| `unit-path-config-section.tsx` | `unlockAfterUnitIds` 为手填文本，无 ID 存在性校验 | 解锁逻辑异常 | 改为多选下拉或校验 ID 存在 |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `questions/page.tsx` | 题库筛选条件仅存 state | 刷新后丢失筛选 | 用 `useSearchParams` 持久化 |
| `training-records/page.tsx`、`score-results/page.tsx`、`audio-submissions/page.tsx` | 筛选未同步 URL | 刷新/分享丢失上下文 | 统一持久化到 URL query |
| 多个列表页 | 硬编码 limit=100，无分页/搜索 | 数据多时找不到记录 | 接入分页与搜索 |
| `units/[unitId]/edit/page.tsx` | 从 limit=100 列表中 `find` 单元 | 超过 100 条时可能找不到 | 单独调用 `getUnit(unitId)` |
| `questions/drafts/page.tsx` | 操作成功后仅局部更新 state | 并发审核时状态不一致 | 操作成功后重新加载 |
| `paths/page.tsx` | 绑定更新直接改本地 `data`，保存失败则状态丢失 | “明明改过了”的困惑 | 保存成功后再写回或失败回滚 |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `training-records/[recordType]/[recordId]/page.tsx` | 英文字段直接展示 | 非技术人员不理解 | 提供中文标签/工具提示 |
| `score-results/page.tsx` | 错误码直接显示 `ASR_TIMEOUT` 等 | 需自行理解 | 增加错误码 → 中文说明映射 |
| `ai-coach/page.tsx` | 字段名为英文 key | 门槛高、易误配 | 标签用中文，key 作为小字备注 |
| 多个页面 | 错误时仅顶部横幅，无重试入口 | 出错后不知下一步 | 错误状态卡片增加“重新加载” |
| `paths/page.tsx` | 加载失败时缺少引导 | 不知该刷新还是联系开发 | 错误卡片提供刷新按钮 + 文案 |
| `ai-coach/page.tsx` | 缺少模块内导航 | 无法快速切回题库/材料库 | 加入 `<SalesTrainerAdminModuleNav />` |
| `module-nav.tsx` | 单菜单页面隐藏导航 | 必须从工作台绕路 | 即使一项也显示导航 |
| `articles/page.tsx` | 创建文章后跳转到其他模块 | 难以返回继续绑定 | 新标签页打开或提供返回链接 |
| `articles/capabilities/page.tsx` | 保存快照未提示“还需发布训练包” | 误以为保存即生效 | toast 明确下一步 |
| `papers/new/page.tsx` | 创建成功后未高亮新考卷 | 返回列表需重新寻找 | 高亮新行或提供编辑链接 |

---

### 2.2 学习内容、记录与日志（learning-and-records）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `learning-contents/[contentId]/page.tsx` | 引用未导出的 `QuestionGenerationPanel`，且 `question-generation-panel.tsx` 有 JSX 语法错误（`>` 未转义） | 学习内容详情页崩溃 | 实现匹配的组件或修正导出/语法 |
| `records/page.tsx:86-88` | 删除前先 `setRecords(filter)`，失败无回滚 | 删除失败但记录已消失 | API 成功后再更新状态 |
| `learning-contents/page.tsx:51-52` | 同上，乐观删除无回滚 | 误以为删除成功 | API 成功后再更新 |
| `records/page.tsx:437` | “下一页”禁用条件为 `records.length < PAGE_SIZE`，无 total | 可能进入空页 | 返回 total 计算 maxPage |
| `logs/page.tsx:15-16` | `getStatusBadgeVariant` 对 `status` 直接 `.trim()` | 单条异常日志导致日志页白屏 | `(status ?? "").trim()` |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `learning-contents/[contentId]/page.tsx:556-564` | “重置”元数据无二次确认 | 未保存修改被覆盖 | dirty 检测 + 确认框 |
| `learning-contents/[contentId]/page.tsx:786-813` | “添加章节”在标题/正文为空时 disabled，无提示 | 不知如何激活按钮 | 加必填标识 + inline 错误 |
| `records/page.tsx:135-179` | “导出记录”弹窗为纯占位，无实际导出请求 | 误以为已提交导出 | 接入真实 API 或移除入口 |
| `records/page.tsx:364-401` | “查看详情”弹窗展示硬编码数据，下载/查看按钮无处理 | 信息不可信、操作无响应 | 使用真实字段或移除占位项 |
| `records/page.tsx:208-213` | 评分范围滑块未绑定 value/onChange | 拖动无效果 | 增加状态并传入 API |
| `records/page.tsx:196-239` | 筛选对话框“即选即生效”，取消无法还原 | 误选后无法回退 | 弹窗内临时状态，确认后生效 |
| `records/page.tsx` | 无空数据状态 | 无法区分无数据/加载中 | 增加区分场景的空状态 |
| `learning-contents/page.tsx:97-102` | 提示不会自动消失 | 旧反馈长期占用 | 3-5 秒后自动清除或提供关闭 |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `learning-contents/page.tsx`、`records/page.tsx`、`logs/page.tsx` | 搜索/筛选/分页未同步 URL | 刷新/分享丢失状态 | 使用 `useSearchParams` |
| `records/page.tsx:79,103-105,187-193` | 搜索无防抖，每次按键都请求 | 请求风暴、列表闪烁 | 300ms debounce |
| `learning-contents/[contentId]/page.tsx:96,220,256,404` | 章节操作共用同一 loading 标志 | 删除章节时添加/保存按钮也 loading | 为不同操作定义独立 loading |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `logs/page.tsx:221-230` | 诊断上下文只显示值，不显示键 | 看到零散文本无法理解 | 显示 `key: value` |
| `logs/page.tsx:235-237` | `details` JSON 全文展开 | 长 JSON 淹没页面 | 默认折叠，按 policy 脱敏 |
| `learning-contents/[contentId]/page.tsx:531-546` | “安全标记”无解释 | 不清楚影响 | 增加 tooltip 或帮助链接 |
| `learning-content-create-form.tsx:81-91` | “来源”等业务术语无解释 | 首次使用困惑 | 增加说明 |
| `learning-contents/[contentId]/page.tsx:826-839` | 发布门禁错误直接展示 `reason_code` | 非技术人员不友好 | 中文映射或仅展示 message |
| `learning-contents/page.tsx` | 列表缺少搜索与状态筛选 | 定位困难 | 增加搜索框与状态筛选 |
| `learning-content-create-form.tsx:26-31` | 新建表单校验过于简单 | 超长标题、长摘要体验差 | 增加长度校验、textarea、未保存提示 |

---

### 2.3 业务规则后台（business-rules）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `sales-combinations/page.tsx` → `handlePublish` / `handleRollback` | 乐观更新后旧生效版本未加入 history | 回滚目标消失 | 手动塞入 history 或重新拉取 |
| `sales-combinations/page.tsx` | 当前生效版本仍可点击“回滚到此版本” | 产生无意义操作 | disabled 当前生效项 |
| `_components/governed-business-rule-page.tsx` | 切换版本下拉框会静默丢弃未保存编辑 | 配置丢失 | 检测 dirty 并提示确认 |
| `components/ui/confirm-dialog.tsx` | `isLoading` 时仍可通过遮罩/Esc 关闭 | 中断操作反馈 | loading 时禁止关闭 |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `sales-combinations/page.tsx` | 发布/回滚无二次确认 | 极易误触生产规则 | 引入 ConfirmDialog |
| `sales-combinations/page.tsx` | 发布按钮文案固定为“发布当前草稿”，与选中项可能不符 | 误发历史版本 | 动态文案 + 非 draft 提示 |
| `_components/governed-business-rule-page.tsx` | 保存草稿无确认，频繁误点导致版本膨胀 | 历史记录膨胀 | 提示覆盖/保存为新草稿 |
| `_components/governed-business-rule-page.tsx` | 发布按钮仅依据 draft 存在性启用，选中历史版本时仍可能发布 draft | 发布非预期内容 | 仅 `status === "draft"` 时启用 |
| `sales-combinations/page.tsx` | 未调用后端校验 API | 复杂错误发布时才暴露 | 增加“后端校验”按钮或发布前自动校验 |
| `sales-combinations/page.tsx` | `can_mutate` 未实际使用但显示徽章 | 看到权限文案却找不到对应功能 | 基于权限控制真实功能或移除文案 |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `_components/governed-business-rule-page.tsx`、`sales-combinations/page.tsx` | 选中版本、原因、JSON 草稿未持久化 URL | 刷新后丢失上下文 | `useSearchParams` 持久化 |
| `sales-combinations/page.tsx` | 发布/回滚后不回源刷新 | 状态可能与后端不一致 | 乐观更新后静默刷新 |
| `sales-combinations/page.tsx` | `DEFAULT_PERMISSIONS` 默认全部 true | 权限缺失时错误展示完整权限 | 默认 false 或提示权限未加载 |
| `_components/governed-business-rule-page.tsx` | JSON 编辑内容仅存内存 | 意外离开丢失工作 | localStorage 自动保存/恢复 |
| `sales-combinations/page.tsx` | `<option>` 使用 index 作为 key | 顺序变化时选择可能跳回 | 使用稳定 `rule_set_id` |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| 两页均存在 | 业务术语与技术标识未解释 | 非技术人员难理解 | 中文映射 + tooltip |
| 两页均存在 | 缺少版本对比/差异视图 | 无法判断改了什么 | 增加 diff 视图 |
| 两页均存在 | 成功/失败反馈位置在按钮下方，可能被忽略 | 重复点击 | 反馈置顶或使用 Toast |
| `PolicyPageShell` | 无返回导航 | 只能依赖浏览器返回 | 增加面包屑/返回链接 |
| 两页 | 空状态/加载状态简陋 | 不知可以做什么 | 骨架屏 + 引导链接 |
| 两页 | 审计日志纯文本展示，无时间列 | 难定位某次操作 | 表格展示，列：时间/操作人/动作/版本变化/原因 |
| 两页 | `formatDateTime` 缺少年份 | 跨年无法区分 | 增加年份 |
| `_components/governed-business-rule-page.tsx` | 权限仅后端校验，前端无提示 | 编辑后才发现无权限 | 前端即时禁用并说明 |

---

### 2.4 角色、提示词、RAG（personas-prompts-rag）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `personas/page.tsx` | 筛选弹窗只有 UI、无实际过滤逻辑 | 点了筛选列表无变化 | 增加过滤状态并传给 API |
| `personas/page.tsx` | 搜索无防抖，存在请求竞态 | 快速输入时列表闪烁 | 增加 debounce / AbortController |
| `personas/page.tsx:233-235` | `sample_issues` 按 `persona_id` 去重，丢失多个 issue | 问题展示不全 | 按 `persona_id` 聚合 issue_types |
| `personas/page.tsx:654-657` | 分页“下一页”依赖当前页条数 | 可能错误禁用 | 使用 `page * page_size >= total` |
| `personas/[id]/page.tsx:1341-1346` | TTS 试听停止未释放 ObjectURL | 内存泄漏 | `URL.revokeObjectURL` |
| `personas/[id]/page.tsx` + `persona-role-anchor.ts` | role_anchor 启用后 bottom_line 为空仍可保存 | 后端可能拒绝 | 客户端校验必填 |
| `prompts/[id]/edit/page.tsx` | `effectivePromptType` 可能静默变更模板类型 | 模板用途错误 | 不匹配时高亮提示或确认 |
| `prompts/new/page.tsx` / `[id]/edit/page.tsx` | 变量提取正则只支持 ASCII | 中文变量无法识别 | 放宽正则或明确提示 |
| `prompts/page.tsx:110-112` | 治理迁移未防御后端结构 | 可能白屏 | `result?.data?.remediated ?? 0` |
| `rag-profiles/page.tsx` | `chunk_overlap` 可大于 `chunk_size` | 非法参数 | 交叉校验 |
| `prompts/scenario-bindings-panel.tsx` | `prompt_type` 与所选模板类型可能不一致 | 运行时取错模板 | 锁定或校验一致性 |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `personas/page.tsx` | 启用/停用无二次确认 | 误触影响实时对练 | 增加 ConfirmDialog |
| `rag-profiles/page.tsx` | 设为默认无确认 | 默认配置被静默切换 | 弹出确认 |
| `prompts/page.tsx`、`prompts/new/page.tsx` | 设为默认无冲突提示 |  unaware 覆盖现有默认 | 提示替换确认 |
| `prompts/[id]/edit/page.tsx` | 系统模板仍可编辑名称/内容/设为默认 | 误改系统提示词 | 系统模板默认只读 |
| `personas/[id]/page.tsx` | 知识库增删未提示“需点击保存” | 误以为已保存 | dirty 状态提示 |
| `rag-profiles/page.tsx` | 取消直接重置，不确认是否丢弃 | 误点取消丢失配置 | dirty 检查 + 确认 |
| `personas/[id]/page.tsx` | 返回/后退未拦截未保存变更 | 编辑丢失 | `beforeunload` + 路由守卫 |
| `prompts/[id]/edit/page.tsx` | 测试渲染错误关闭后无法回看 | 需重新填写变量 | 保留最近一次结果 |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `personas/page.tsx`、`prompts/page.tsx` | 搜索/筛选/分页未同步 URL | 刷新后丢失 | `useSearchParams` |
| `personas/page.tsx` | 搜索未重置页码 | 第 3 页搜索可能空列表 | 搜索词变化重置 page=1 |
| 三个模块 | 无统一缓存/失效策略 | 多标签页数据陈旧 | 引入 SWR/React Query |
| `personas/[id]/page.tsx` | 保存失败无回滚提示 | 无法区分本地/已落库 | 增加 loading 与失败回滚 |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `personas/[id]/page.tsx` | 术语高度技术化 | 不敢修改 | tooltip/glossary |
| `prompts/scenario-bindings-panel.tsx` | `scenario_id` 自由文本，无解释 | 不知道填什么 | 提供选择器或说明 |
| `rag-profiles/page.tsx` | 关联知识库数字无进一步说明 | 误删被使用的配置 | 删除确认中提示影响数量 |
| `prompts/new/page.tsx` | 缺少模板语法示例与实时校验 | 不熟悉 Jinja2 | 示例 + 高亮 + 实时校验 |
| `persona-ref-picker.tsx` / `asset-ref-picker.tsx` | 已选但禁用 Persona 提示不足 | 保存引用已停用配置 | 显示警告并阻止提交 |
| `rag-profiles/page.tsx` | 页面已弃用但 Cohere 无 API Key 输入 | 不知如何配置密钥 | 隐藏无法配置字段或提供密钥管理入口 |

---

### 2.5 课程练习后台（curriculum-practice）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `content-asset-index.tsx` | “全部”状态 `all` 原样传给后端 API | 列表可能为空/报错 | `all` 时不传 `status` |
| `content-asset-utils.ts` | CSV 用 `split(",")` 拆分，不支持含逗号字段 | 真实业务文本常带逗号，导入失败 | 使用标准 CSV 解析 |
| `examiner-agents/examiner-agent-form-page.tsx` | 默认评分策略加载失败只 `debug.warn` | 保存时被后端拒绝 | 显示可操作的错误提示 |
| `roleplay-situation-packs/page.tsx` | JSON 格式错误时静默回退为空对象 | 数据丢失且不自知 | 保留原文本并提示错误 |
| `template-form.tsx` | 未暴露 `scenario_type`、`mode`、`voice_mode` 控件 | 无法创建其他场景类型 | 补充选择控件 |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `content-asset-index.tsx`、`examiner-agent-index.tsx`、`roleplay-situation-packs/page.tsx` | 复制为新草稿无确认 | 误触产生大量副本 | 增加确认或撤销 |
| 多个 index/list | 行级操作按钮密集且无明显区分 | 易把发布点成归档 | 按危险程度分组样式 |
| `template-form.tsx`、`case-item-form.tsx`、`role-profile-form.tsx`、`examiner-agent-form.tsx` | 必填项无统一标识 | 反复提交摸索 | 标签加 `*` + 即时提示 |
| `roleplay-situation-packs/page.tsx` | 切换 pack 丢弃未保存编辑 | 误切丢失修改 | dirty 检测 + 离开确认 |
| `roleplay-situation-packs/page.tsx` | 标记归档无确认 | 误归档 | 增加确认 |
| `template-form.tsx` | 移除 Stage 无确认 | 阶段配置立即消失 | 增加确认或撤销 |
| `content-asset-index.tsx` | 搜索无防抖 | 请求风暴 | 300ms debounce |
| `content-asset-form-page.tsx` | 声音克隆提交无确认、无独立状态 | 与保存混淆 | 单独 loading + 确认说明 |
| `examiner-agents/examiner-agent-utils.ts` | 基础校验缺失 | 可提交空名称/空策略 | 补充必填/范围校验 |
| `template-form.tsx`、`examiner-agent-form.tsx` | 数字输入框无 min/max | 可输入负数/极大值 | 设置合理范围 |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `content-asset-index.tsx`、`examiner-agent-index.tsx`、`roleplay-situation-packs/page.tsx` | 搜索/筛选/选中未同步 URL | 刷新丢失 | `useSearchParams` |
| 所有列表页 | 无 SWR/React Query | 数据陈旧 | 引入缓存库 |
| `content-asset-form-page.tsx`、`examiner-agents/examiner-agent-form-page.tsx`、`template-form.tsx` | 保存成功后立即跳转，提示几乎不可见 | 不确定是否生效 | toast 或列表页一次性提示 |
| `content-asset-import-wizard.tsx` | CSV 导入无逐行进度 | 不知还剩多少 | 显示进度/取消按钮 |
| `content-asset-index.tsx` → `handleArchive` | 归档前未检查引用关系 | 已发布模板引用失效 | 归档前查询引用并提示 |
| `template-form.tsx` | “引用资产已变更”横幅只监控 case/role | 更换 agent 等无提醒 | 纳入所有核心引用 |
| `template-form.tsx` | Stage asset_id / hash 是手填文本 | 极易填错 | 使用资产选择器 |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `roleplay-situation-packs/page.tsx`、`template-form.tsx`、`examiner-agent-form-page.tsx` | 大量英文术语无中文解释 | 配置错误率高 | tooltip/字段说明 |
| `roleplay-situation-packs/page.tsx`、`template-form.tsx` | 后端字段路径直接展示 | 难以定位输入框 | 映射为中文标签 + 跳转 |
| 全模块 | 成功/失败反馈位置不一致 | 容易漏看 | 统一 toast + 一次性提示 |
| `template-list.tsx`、`examiner-agent-index.tsx` | 空状态简陋 | 引导弱 | 统一 EmptyState |
| `curriculum-config-checklist.tsx` | Persona/RoleProfile/客户角色库概念混淆 | 新手易混 | 增加说明 |
| `template-runtime-dossier-preview.tsx` | 标题固定为 “CIO runtime dossier” | 误以为只针对 CIO | 动态标题 |
| `role-profile-form.tsx` | 声音克隆需手动填 Base64/URL | 不知如何生成 | 文件上传自动转 Base64 |

---

### 2.6 知识库与检索策略（knowledge-retrieval）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `knowledge/page.tsx`、`knowledge-detail-context.tsx` | 乐观删除未回滚 | 失败后出现“幽灵删除” | API 成功后再更新或回滚 |
| `knowledge-detail-context.tsx`、`knowledge/[id]/layout.tsx` | `params.id` 直接类型断言 | 异常路由可能发 `undefined` | 空值检查 |
| `knowledge/page.tsx` | 移动端“更多”按钮为纯占位 | 窄屏无法管理 | 绑定菜单或移除 |
| `knowledge-documents-panel.tsx` | pending 文档也可点击重试 | 重复提交 | 仅 failed 显示重试 |
| `knowledge-answer/shared/number-field.tsx` | 数字输入未校验范围 | 可提交越界值 | onChange/onBlur 时 clamp |
| `knowledge-answer/shared/weight-editor.tsx` | 权重允许空键名 | 产生无意义条目 | 保存前校验 |
| `knowledge-detail-context.tsx` | 上传队列 ID 可能重复 | 渲染错乱 | 加入 UUID/时间戳 |
| `knowledge-answer/run-history/run-history.tsx` | 筛选标签显示原始枚举值 | 不清楚含义 | 复用 label map |
| 11 处 effect 内 setState | ESLint `react-hooks/set-state-in-effect` 报错 | 级联渲染/竞态 | 迁移到 React Query |
| `knowledge-detail-shared.tsx` | 大量未使用导入 | 构建噪音 | 清理 |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `knowledge-dictionary-panel.tsx` | 词典发布/归档/删除均无确认 | 误触失效 | 删除加确认，发布/归档轻量确认 |
| `knowledge-rag-profile-section.tsx` | RAG Profile 切换即时生效 | 误改分块配置 | 增加保存按钮或确认 |
| `knowledge-answer/version-manager.tsx` | 版本激活即时生效 | 影响所有知识库 | 激活前确认 |
| `knowledge-answer/knowledge-answer-console.tsx` | 全局配置保存缺少影响确认 | 误改全局策略 | 二次确认 |
| `knowledge/page.tsx` | 删除知识库未要求输入名称确认 | 高影响删除风险 | 输入名称确认 |
| `knowledge/page.tsx` | “应用筛选”按钮仅为关闭 | 语义不符 | 改为临时状态，确认后生效 |
| `knowledge-detail-shared.tsx` | 批量上传并发数无提示 | 以为系统卡住 | 提示并发限制 |
| `knowledge-detail-context.tsx` | 上传进度为模拟进度 | 大文件长时间停留 90% | 真实进度或明确文案 |
| 多个策略 Tab | 保存前无表单校验 | 反复点击才报错 | 必填校验 + 高亮 |
| `knowledge-answer/debug-panel/debug-panel.tsx` | 调试面板默认折叠 | 不知如何验证 | 首次使用自动展开 |
| `knowledge-answer/knowledge-answer-console.tsx` | 只读模式禁用调试与运行记录 | 无法调试本库 | 仅禁用编辑 |
| `knowledge/page.tsx` | 创建弹窗关闭后表单未重置 | 再次打开看到旧数据 | 关闭时重置 |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| 整个模块 | 未使用 React Query/SWR，全手动 effect | 无统一缓存/重试/失效 | 迁移到 `@tanstack/react-query` |
| `knowledge/page.tsx`、`run-history/run-history.tsx` | 筛选/分页/搜索未写入 URL | 刷新丢失 | `useSearchParams` |
| `knowledge-detail-context.tsx` | 文档处理状态轮询无可见开关 | 网络敏感环境持续请求 | 显示开关 |
| `knowledge-detail-context.tsx` | 上传队列状态不持久 | 切换 Tab 丢失 | 提升到后台任务/session storage |
| `kb-multi-ref-picker.tsx` | 多选回显依赖全量加载（上限 200） | 超过 200 名称不显示 | 分页或按 ID 单独查询 |
| `knowledge-answer/debug-panel/debug-kb-picker.tsx` | 选择知识库后无持久化 | 反复调试需重复选择 | localStorage 缓存 |
| `knowledge-answer/shared/profile-list-detail.tsx` | 草稿未深拷贝 | 嵌套对象共享引用 | 深拷贝 |
| `knowledge/page.tsx` | 列表未接入后端分页 | 数据量大时卡顿 | 接入分页 |
| `run-history/run-history.tsx` | 运行详情展开状态未保留 | 刷新后折叠 | 同步到 URL |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| 检索策略各 Tab | 专业术语缺乏解释 | 不敢修改 | ℹ️ tooltip/帮助文档 |
| `knowledge/[id]/page.tsx`、运行记录、多选下拉 | 状态标签中英文混合 | 需要中英对照 | 统一中文标签 |
| `knowledge-detail-shared.tsx` | 文档失败原因缺少“下一步”指引 | 知道原因不知去哪 | 嵌入设置/配置链接 |
| `knowledge-documents-panel.tsx` | 空状态缺少行动指引 | 新用户不知上传 | 空状态增加上传按钮 |
| `[id]/settings`、`retrieval-strategies/page.tsx` | 全局/本库配置关系缺少对比视图 | 调试时来回切换 | 本库页展示全局版本摘要 |
| `run-history/run-history.tsx` | “全局”提示不够醒目 | 误将全局记录当本库 | 警告色横幅 |

---

### 2.7 演示、AI 演示与数据分析（presentations-analytics）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `presentations/page.tsx` | 分页逻辑完全失效，未传 page/offset | 翻页内容不变 | 传 offset 或客户端 slice |
| `presentations/page.tsx` → `getStatusStyle` | 未知状态 fallback 为“处理中” | 新增状态被掩盖 | fallback 为“未知” |
| `presentations/[id]/page.tsx` | 替换 PPT 后未刷新 talkingPoints/forbiddenWords | 配置与材料版本不一致 | 替换成功后重新加载 |
| `presentations/[id]/page.tsx` → `loadTalkingPoints` | 快速切换页码存在竞态 | 当前页显示其他页要点 | AbortController/过期标志 |
| `analytics/page.tsx` | 部分接口失败被静默吞掉 | 无法区分无数据/接口故障 | 显示错误提示与重试 |
| `analytics/page.tsx` → `handleExport` | 导出报表未触发下载 | 点击后无文件 | 转 Blob 触发下载 + toast |
| `analytics/page.tsx` → `handleManagerRemind` | 提醒无成功/失败反馈 | 不确定是否发送 | 增加 toast |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `presentations/[id]/page.tsx` | 删除要点/禁忌词无二次确认 | 误触即删除 | ConfirmDialog |
| `presentations/[id]/page.tsx` | 替换标准 PPT 无二次确认 | 误覆盖标准材料 | 确认弹窗 |
| `presentations/page.tsx` | 筛选对话框状态与应用时机不一致 | 页码可能无效 | 临时状态，应用后生效 |
| `presentations/page.tsx` | 搜索无防抖且触发无意义请求 | 输入时反复 loading | 从 effect deps 移除或 debounce |
| `presentation-ai/page.tsx` | 未保存离开无提示 | 高级参数丢失 | `beforeunload` + 路由守卫 |
| `manager-lite-panel.tsx` | 主管“一键提醒”无确认 | 误触发送通知 | 轻量确认 + toast |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `presentations/page.tsx`、`analytics/page.tsx`、`analytics/curriculum/page.tsx` | 筛选/搜索/分页未与 URL 同步 | 刷新丢失 | `useSearchParams` |
| `presentations/page.tsx` | 搜索仅覆盖前端已加载数据（最多 20 条） | 目标不在 20 条内搜索不到 | 服务端搜索或加载全部 |
| `presentation-ai/page.tsx` | 策略加载失败仍显示可编辑默认值 | 可能用默认值覆盖真实策略 | 加载失败禁用保存并提示 |
| `analytics/page.tsx` | 多接口存在竞态 | 旧响应覆盖新数据 | abort/过期标志 |
| `presentations/[id]/page.tsx` | 替换 PPT 后返回列表未自动刷新 | 仍看到旧版本 | SWR 或返回时刷新 |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| 演示/AI/分析各页 | 业务术语缺少解释 | 首次使用难以理解 | hover tooltip |
| `analytics/page.tsx`、`presentation-ai/page.tsx` | 部分失败无页面内错误提示 | 面对空白不知所措 | 统一错误态 + 重试 |
| `presentation-ai/page.tsx` | 高级参数只有 label | 调参凭猜测 | 说明文案、取值范围、推荐值 |
| `analytics/page.tsx` | 导出/提醒成功无反馈 | 不确定是否完成 | 明确 toast |

---

### 2.8 通用 Admin（布局、导航、错误处理、全局组件、公共 lib）

#### 显性 Bug

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `agents/[id]/page.tsx` | “删除”按钮未绑定任何点击事件 | 危险入口无效 | 实现删除确认流程 |
| `agents/page.tsx` | 搜索无防抖，存在请求竞争 | 列表闪烁 | debounce + AbortController |
| `agents/page.tsx` | 筛选弹窗“应用筛选”名不副实 | 点选时已生效 | 临时状态 + 确认后生效 |
| `manager-lite-panel.tsx` | 一键提醒失败时没有任何提示 | 误以为成功 | 补全 catch + toast |

#### 交互设计陷阱

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `agents/page.tsx` | 发布/归档/草稿切换无二次确认 | 误触影响线上训练 | ConfirmDialog |
| `agents/[id]/page.tsx` | 设为默认角色无确认 | 误改默认角色 | 确认 + 撤销能力 |
| `agents/[id]/page.tsx` | 删除按钮无功能 | 看起来像可点 | 实现或禁用 |
| `agents/page.tsx` → `handleCreate` | 创建表单校验简陋 | 错误难定位 | 增加长度/字符校验，字段级错误 |
| `manager-lite-panel.tsx` | 一键提醒缺少确认 | 误触发送通知 | 确认 + toast |
| `agents/[id]/page.tsx` | 离开时不提示未保存 | 编辑丢失 | dirty 检测 + 路由拦截 |
| `agents/page.tsx` | 分页“下一页”无法判断尾页 | 可能进入空页 | 返回 total/has_more |
| `page.tsx` | 全局搜索框未实际生效 | 搜索形同虚设 | 实现过滤或禁用 |

#### 数据流动与绑定问题

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `agents/page.tsx` | 筛选/分页/搜索未同步 URL | 刷新丢失 | `useSearchParams` |
| `governance/page.tsx` | 标签/会话 ID 未持久化 | 刷新后需重新输入 | URL query |
| `page.tsx` → `loadLiveMetrics` | 核心指标请求失败静默显示 0% | 可能误判业务 | 失败提示 + 重试 |
| `agents/[id]/page.tsx` | 当前模型/运行时配置可能不在 active 选项中 | 保存后覆盖为默认 | 失效引用单独显示 |
| `agents/page.tsx` | 删除成功后未刷新全量数据 | 总数/分页不同步 | 删除后调用 `loadData()` |

#### 运营人员认知负担

| 位置 | 问题 | 影响 | 建议 |
|------|------|------|------|
| `governance/page.tsx` | 大量技术术语与 JSON 块 | 非技术运营难理解 | tooltip + 中文标签 |
| `agents/[id]/page.tsx` | “Industry Pack 运行合同”难懂 | 不知与智能体关系 | 中文卡片说明 |
| `agents/page.tsx` | 状态含义无说明 | 不确定归档是否下线 | tooltip 说明 |
| `agents/page.tsx` | 列表缺少空状态/加载状态 | 无法区分加载/无数据 | 骨架屏 + 引导 |
| `governance/page.tsx` | 错误提示可能暴露后端 message | 难以定位 | 中文友好提示 |
| `page.tsx` | 待接入卡片与真实卡片视觉一致 | 误把占位当真实 | 明显不同样式或折叠 |

---

## 3. 跨模块共性问题汇总

以下问题在多个模块反复出现，建议优先统一治理。

### 3.1 URL 状态未同步（影响所有列表页）

几乎所有后台列表页都将搜索、筛选、分页、选中项保存在组件 `useState` 中，未写入 URL query。对运营人员的主要影响：

- 刷新页面后筛选条件丢失。
- 无法通过链接分享特定视图给同事。
- 浏览器前进/后退无法恢复状态。
- 排查问题时无法保留上下文。

**建议**：统一使用 `useSearchParams` + `useRouter` 将关键状态双向绑定到 URL；若状态复杂，可封装为通用 hook。

### 3.2 危险操作缺少二次确认

以下操作在当前实现中多为一次点击即生效：

- 发布/回滚业务规则、路径配置、材料版本、训练包、知识库版本。
- 归档/删除知识库、词典、内容资产、智能体、角色、考卷、PPT。
- 设为默认（RAG Profile、角色、提示词、智能体）。
- 一键提醒、声音克隆、替换标准 PPT。

**建议**：建立统一的“危险操作清单”，所有清单内操作必须通过 `ConfirmDialog`；影响范围大的操作还需复述影响摘要。

### 3.3 乐观更新无回滚

多处删除/更新操作先改本地 state 再调 API，失败时本地状态不会恢复：

- `learning-contents/page.tsx`、`records/page.tsx`、`knowledge/page.tsx` 的删除。
- `sales-combinations/page.tsx` 的发布/回滚乐观补丁。
- `paths/page.tsx` 的本地绑定更新。

**建议**：要么 API 成功后更新状态，要么实现乐观回滚（失败时恢复并提示）。

### 3.4 搜索无防抖

`personas`、`agents`、`presentations`、`records`、`content-asset-index` 等页面搜索框直接绑定 state 并触发 effect，每输入一个字符都请求后端。

**建议**：统一为搜索增加 300ms debounce，必要时配合 AbortController 丢弃过期响应。

### 3.5 分页不可靠

大量页面使用 `items.length < PAGE_SIZE` 判断是否有下一页，或完全不传 page 参数。这会导致：

- 最后一页恰好满页时仍可翻页，进入空页。
- 翻页时内容不变化（PPT 列表）。
- 无法跳转到指定页码。

**建议**：后端返回 `total` 或 `has_more`；前端统一分页组件。

### 3.6 未保存离开无拦截

`agents/[id]`、`personas/[id]`、`presentation-ai`、`roleplay-situation-packs` 等表单页面缺少 dirty 检测与离开确认。

**建议**：统一使用 `beforeunload` + Next.js 路由守卫，在存在未保存修改时提示用户。

### 3.7 术语与错误提示技术化

后台页面普遍存在直接展示英文 key、后端字段路径、reason_code、error_code、JSON 块的现象。

**建议**：建立领域术语中文映射表与错误码友好文案表；调试信息默认折叠，运营可见信息优先使用中文。

### 3.8 缓存与状态管理策略缺失

目前几乎完全依赖 `useEffect + useState` 手动加载，未使用 SWR/React Query。这导致：

- 多标签页数据陈旧。
- 保存成功后需要手动刷新。
- 竞态处理依赖大量 `cancelled` flag。
- 加载/错误/重试语义不统一。

**建议**：引入 `@tanstack/react-query`（项目已安装），统一缓存、失效、重试策略。

---

## 4. 修复优先级建议

### P0（立即修复，否则运营人员无法正常使用）

1. 修复学习内容详情页 `QuestionGenerationPanel` 未导出/JSX 语法错误。
2. 修复销售训练录音详情页重试按钮永久禁用 bug。
3. 修复销售训练工作台 `summary` 空值保护。
4. 修复业务规则确认弹窗 loading 时可关闭问题。
5. 修复通用 Admin 智能体详情页删除按钮无响应。
6. 修复 PPT 列表分页完全失效问题。
7. 修复 Analytics 部分接口失败静默显示 0/空的问题。
8. 修复训练记录页、学习内容列表页乐观删除无回滚。

### P1（本周修复，显著降低误操作与挫败感）

1. 为发布/回滚/归档/删除/设为默认/一键提醒/替换 PPT 等危险操作统一增加二次确认。
2. 为所有列表页增加 URL 状态同步（搜索、筛选、分页、选中项）。
3. 为搜索框统一增加防抖。
4. 修复分页尾页判断（使用 total/has_more）。
5. 修复业务规则发布/回滚后旧生效版本从历史列表消失。
6. 修复治理型规则页切换版本丢弃未保存编辑。
7. 为未保存离开增加拦截（agents、personas、presentation-ai、roleplay packs）。
8. 修复筛选对话框“应用筛选”名不副实的问题（agents、presentations、knowledge）。

### P2（迭代优化，提升专业感与效率）

1. 列表统一接入分页、搜索、空状态、加载状态。
2. 表单必填项统一标识与即时校验。
3. 术语与错误码统一中文映射。
4. 增加版本对比/diff 视图（业务规则、PPT、材料）。
5. 增加上传/导入进度与结果追踪。
6. 治理页、智能体详情页增加中文说明卡片。
7. 错误状态统一增加重试按钮与“联系管理员”文案。

### P3（架构升级，长期收益）

1. 引入 SWR/TanStack Query 统一管理数据获取与缓存失效。
2. 抽象通用列表 hook（URL 同步、分页、搜索、筛选、刷新）。
3. 建立统一 ConfirmDialog 危险操作封装。
4. 建立统一空状态/错误状态/加载状态组件库。

---

## 5. 附录：分析方法

- **并行审查**：启用 8 个 Agent，每个负责一个后台子域，独立只读审查代码。
- **验证方式**：部分 Agent 运行了对应模块的测试与 TypeScript 检查，结果已在各模块内注明。
- **约束**：本次分析未修改任何源代码；所有结论基于实际读到的代码与测试输出。
- **未覆盖范围**：后端实现细节、浏览器兼容性、性能基准、安全漏洞专项审计。
