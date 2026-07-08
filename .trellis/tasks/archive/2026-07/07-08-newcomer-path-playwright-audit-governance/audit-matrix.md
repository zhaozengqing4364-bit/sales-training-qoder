# Playwright 审计矩阵

证据目录：`.trellis/tasks/07-08-newcomer-path-playwright-audit-governance/playwright-audit/screenshots/`

## 通用检查项

每个页面必须检查：

- HTTP 与渲染：页面不是 404、500、白屏、无限 loading。
- 控制台：无未处理 `console.error`，无范围内 API 4xx/5xx 或 request failed。
- 信息架构：有清晰页面标题、当前任务、主操作或明确空状态。
- 状态：loading、empty、error、disabled 或 readonly 不破坏主流程。
- 可访问性基础：表单有 label，图标按钮有 accessible name，焦点和按钮可操作。
- 移动端：390px 宽度无整页水平溢出，关键按钮不重叠。
- 内部字段：不向普通页面展示 `E2E`、`mock`、`seed`、`Prompt`、`traceId`、`workflow`、原始枚举、数据库主键；管理员调试和审计详情除外。
- 截图：桌面和移动端关键页保存 full page 截图。

## 前台学习端

| 编号 | URL | 目标 | 关键断言 |
| --- | --- | --- | --- |
| L-01 | `/sales-trainer` | 新人训练入口与下一步 | 标题可见，路径进度可见，下一步动作清晰 |
| L-02 | `/sales-trainer/learn/hub` | 学习中心 | 已配置学习专题可见，未配置内容不误导展示 |
| L-03 | `/sales-trainer/learning-topics/business-etiquette` | 商务礼仪专题兼容 | 专题、单元、章节层级清晰，得分展示不阻塞后续 |
| L-04 | `/sales-trainer/learn/[unitId]` | 单元学习 | 正确加载章节/材料，完成进度可更新 |
| L-05 | `/sales-trainer/quiz/[unitId]` | 单元考试 | 题目、提交、防重复提交、错误反馈可用 |
| L-06 | `/sales-trainer/quiz/result/[attemptId]` | 考试结果 | 得分、通过状态、下一步清晰 |
| L-07 | `/sales-trainer/audio/[unitId]` | 录音上传 | 材料、上传/录音入口、评分说明清晰 |
| L-08 | `/sales-trainer/audio/result/[submissionId]` | 录音评分结果 | AI 评分、证据、重试/下一步可见 |
| L-09 | `/sales-trainer/business-skills` | 旧学习入口兼容 | 不 404，语义过渡到学习专题 |
| L-10 | `/sales-trainer/business-skills/exam` | 旧考试入口兼容 | 不 404，考试入口可用或有明确引导 |
| L-11 | `/sales-trainer/business-skills/coach` | 旧教练入口兼容 | 不 404，教练/学习引导清晰 |

## 后台管理端

| 编号 | URL | 目标 | 关键断言 |
| --- | --- | --- | --- |
| A-01 | `/admin/sales-trainer` | 后台工作台 | 模块分组清晰，录音管理和学习专题入口明确 |
| A-02 | `/admin/sales-trainer/audio` | 录音管理总览 | 场景、材料、评分标准、提交、结果可在一页理解 |
| A-03 | `/admin/sales-trainer/audio/ppt-explanation` | PPT 讲解录音场景配置 | 场景、材料、评分标准、Prompt、发布状态可同页配置 |
| A-03B | `/admin/sales-trainer/audio/company-product-demo` | 公司产品 Demo 录音场景配置 | 新录音载体可作为同级场景扩展，不和能力模型混淆 |
| A-04 | `/admin/sales-trainer/audio/materials` | 录音材料库 | 列表、上传/新增、空状态、错误可用 |
| A-05 | `/admin/sales-trainer/audio/score-standards` | 录音评分标准归属页 | 明确属于录音管理，能新增/编辑 |
| A-06 | `/admin/sales-trainer/audio/submissions` | 录音提交 | 筛选、详情入口、重评入口清晰 |
| A-07 | `/admin/sales-trainer/audio/results` | 录音评分结果 | 评分、依据、人工复核入口清晰 |
| A-08 | `/admin/sales-trainer/learning-topics` | 学习专题总览 | 商务礼仪只是专题之一，扩展语义清晰 |
| A-09 | `/admin/sales-trainer/learning-topics/business-etiquette` | 商务礼仪专题配置 | 专题、单元、章节、考卷绑定同页完成 |
| A-10 | `/admin/sales-trainer/learning-topics/import` | 学习内容导入 | 导入入口、校验、失败反馈清晰 |
| A-11 | `/admin/sales-trainer/learning-topics/capabilities` | 专题能力配置 | 能力开关或说明清晰 |
| A-12 | `/admin/sales-trainer/learning-topics/questions` | 专题题库 | 列表、搜索、新建、草稿、预览入口清晰 |
| A-13 | `/admin/sales-trainer/learning-topics/questions/new` | 新建题目 | 表单 label、选择优先、校验和保存反馈 |
| A-14 | `/admin/sales-trainer/learning-topics/questions/drafts` | 题目草稿 | 草稿列表和继续编辑可用 |
| A-15 | `/admin/sales-trainer/learning-topics/questions/quiz-preview` | 试题预览 | 预览与返回题库可用 |
| A-16 | `/admin/sales-trainer/learning-topics/papers` | 专题考卷 | 列表、新建、绑定专题语义清晰 |
| A-17 | `/admin/sales-trainer/learning-topics/papers/new` | 新建考卷 | 题目选择、防重复、保存反馈可用 |
| A-18 | `/admin/sales-trainer/paths` | 路径配置 | 路径、模块、发布、版本、前台显示关系清晰 |
| A-19 | `/admin/sales-trainer/units` | 模块单元 | 单元列表、新建、编辑入口可用 |
| A-20 | `/admin/sales-trainer/ai-coach` | AI 教练配置 | Prompt/模型治理可追踪，不泄露给普通学员 |
| A-21 | `/admin/sales-trainer/readiness` | 达标验收 | 验收状态、筛选、详情入口可用 |
| A-22 | `/admin/sales-trainer/training-records` | 训练记录 | 记录类型中文化、详情入口、筛选可用 |
| A-23 | `/admin/sales-trainer/analytics` | Journey 分析 | 指标、趋势、空状态可用 |
| A-24 | `/admin/sales-trainer/settings` | 配置中心 | 诊断、默认值、风险提示清晰 |
| A-25 | `/admin/sales-trainer/operation-logs` | 操作记录 | 审计列表、筛选、敏感信息不泄露 |

## 旧路由兼容

| 编号 | URL | 目标 | 关键断言 |
| --- | --- | --- | --- |
| C-01 | `/admin/sales-trainer/articles` | 旧文章入口 | 不断链，明确指向学习专题 |
| C-02 | `/admin/sales-trainer/materials` | 旧材料入口 | 不断链，明确指向录音材料或通用材料 |
| C-03 | `/admin/sales-trainer/score-standards` | 旧评分标准入口 | 不断链，明确归入录音管理 |
| C-04 | `/admin/sales-trainer/papers` | 旧考卷入口 | 不断链，明确归入学习专题 |
| C-05 | `/admin/sales-trainer/questions` | 旧题库入口 | 不断链，明确归入学习专题 |
| C-06 | `/admin/sales-trainer/audio-submissions` | 旧录音提交入口 | 不断链，明确归入录音管理 |
| C-07 | `/admin/sales-trainer/score-results` | 旧评分结果入口 | 不断链，明确归入录音管理 |
| C-08 | `/admin/sales-trainer/training-tasks` | 旧训练任务入口 | 不断链，明确归入录音管理 |

## 排除校验

Playwright 专项规格不得访问：

- `/training/sales`
- `/practice/*`
- `/admin/business-rules/sales-trainer-phase2`
- 非新人训练相关后台模块
