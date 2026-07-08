# 新人训练专项 Playwright Route Manifest

运行规格：

- `web/tests/e2e/newcomer-training-learner.spec.ts`
- `web/tests/e2e/newcomer-training-admin.spec.ts`
- 代码清单：`web/tests/e2e/newcomer-training-route-manifest.ts`

截图目录：

- `.trellis/tasks/archive/2026-07/07-08-newcomer-path-playwright-audit-governance/playwright-audit/screenshots/`

报告文件：

- `.trellis/tasks/archive/2026-07/07-08-newcomer-path-playwright-audit-governance/playwright-audit/newcomer-training-learner-report.json`
- `.trellis/tasks/archive/2026-07/07-08-newcomer-path-playwright-audit-governance/playwright-audit/newcomer-training-admin-report.json`

## 前台

| 编号 | URL | 页面类型 | 角色 | 关键主操作 | 旧路由兼容 | 需要 seed 数据 | 审计方式 |
|---|---|---|---|---|---|---|---|
| L-01 | `/sales-trainer` | learner 路径首页 | learner | 查看当前训练状态和下一步 | 否 | 是 | smoke + 闭环入口 |
| L-02 | `/sales-trainer/learn/hub` | learner 学习中心 | learner | 查看已发布学习专题 | 否 | 是 | smoke |
| L-03 | `/sales-trainer/learning-topics/business-etiquette` | learner 学习专题 | learner | 进入商务礼仪小单元 | 否 | 是 | smoke |
| L-04 | `/sales-trainer/learn/[unitId]` | learner 单元阅读 | learner | 阅读章节并标记进度 | 否 | 是 | 完整闭环动态路由 |
| L-05 | `/sales-trainer/quiz/[unitId]` | learner 单元小测 | learner | 提交题目答案 | 否 | 是 | 完整闭环动态路由 |
| L-06 | `/sales-trainer/quiz/result/[attemptId]` | learner 小测结果 | learner | 查看分数、通过状态和下一步 | 否 | 是 | 完整闭环动态路由 |
| L-07 | `/sales-trainer/audio/[unitId]` | learner 录音上传 | learner | 查看材料要求并上传录音 | 否 | 是 | 完整闭环动态路由 |
| L-08 | `/sales-trainer/audio/result/[submissionId]` | learner 录音结果 | learner | 查看 AI 评分、建议和下一步 | 否 | 是 | 完整闭环动态路由 |
| L-09 | `/sales-trainer/business-skills` | learner 旧学习入口 | learner | 兼容进入学习专题 | 是 | 是 | smoke |
| L-10 | `/sales-trainer/business-skills/exam` | learner 旧考试入口 | learner | 兼容进入小测 | 是 | 是 | smoke |
| L-11 | `/sales-trainer/business-skills/coach` | learner 旧 AI 教练入口 | learner | 兼容进入 AI 教练训练 | 是 | 是 | smoke |

## 后台

| 编号 | URL | 页面类型 | 角色 | 关键主操作 | 旧路由兼容 | 需要 seed 数据 | 审计方式 |
|---|---|---|---|---|---|---|---|
| A-01 | `/admin/sales-trainer` | 后台工作台 | admin | 查看健康状态、缺口和下一步 | 否 | 是 | smoke |
| A-02 | `/admin/sales-trainer/audio` | 录音管理总览 | admin | 查看录音场景与配套资源 | 否 | 是 | smoke |
| A-03 | `/admin/sales-trainer/audio/ppt-explanation` | 录音场景配置 | admin | 配置 PPT 讲解录音任务 | 否 | 是 | smoke |
| A-03B | `/admin/sales-trainer/audio/company-product-demo` | 录音场景配置 | admin | 配置公司产品 Demo 录音任务 | 否 | 是 | smoke |
| A-04 | `/admin/sales-trainer/audio/materials` | 录音材料库 | admin | 上传或管理录音材料 | 否 | 是 | smoke |
| A-05 | `/admin/sales-trainer/audio/score-standards` | 录音评分标准 | admin | 新建或编辑结构化评分标准 | 否 | 是 | smoke |
| A-06 | `/admin/sales-trainer/audio/submissions` | 录音提交管理 | admin | 查询学员录音和处理状态 | 否 | 是 | smoke |
| A-07 | `/admin/sales-trainer/audio/results` | 录音评分结果 | admin | 查看评分结果与复核入口 | 否 | 是 | smoke |
| A-08 | `/admin/sales-trainer/learning-topics` | 学习专题总览 | admin | 查看和进入专题配置 | 否 | 是 | smoke |
| A-09 | `/admin/sales-trainer/learning-topics/business-etiquette` | 学习专题详情 | admin | 配置文章、小单元、小测和发布 | 否 | 是 | smoke |
| A-10 | `/admin/sales-trainer/learning-topics/import` | 学习内容导入 | admin | 导入并校验学习内容 | 否 | 是 | smoke |
| A-11 | `/admin/sales-trainer/learning-topics/capabilities` | 专题能力配置 | admin | 管理能力点和章节绑定 | 否 | 是 | smoke |
| A-12 | `/admin/sales-trainer/learning-topics/questions` | 专题题库 | admin | 搜索、新建、预览题目 | 否 | 是 | smoke |
| A-13 | `/admin/sales-trainer/learning-topics/questions/new` | 新建题目 | admin | 创建专题小测题目 | 否 | 是 | smoke |
| A-14 | `/admin/sales-trainer/learning-topics/questions/drafts` | 题目草稿 | admin | 继续编辑草稿题目 | 否 | 是 | smoke |
| A-15 | `/admin/sales-trainer/learning-topics/questions/quiz-preview` | 试题预览 | admin | 预览题目和小测展示 | 否 | 是 | smoke |
| A-16 | `/admin/sales-trainer/learning-topics/papers` | 专题考卷 | admin | 管理专题小测考卷 | 否 | 是 | smoke |
| A-17 | `/admin/sales-trainer/learning-topics/papers/new` | 新建考卷 | admin | 选择题目并创建考卷 | 否 | 是 | smoke |
| A-18 | `/admin/sales-trainer/paths` | 路径配置 | admin | 保存、发布或回滚路径修订 | 否 | 是 | smoke |
| A-19 | `/admin/sales-trainer/units` | 模块单元 | admin | 新建和管理训练单元 | 否 | 是 | smoke |
| A-20 | `/admin/sales-trainer/ai-coach` | AI 教练配置 | admin | 管理 Prompt、模型和教练配置 | 否 | 是 | smoke |
| A-21 | `/admin/sales-trainer/readiness` | 达标验收 | admin | 查看达标状态和复核入口 | 否 | 是 | smoke |
| A-22 | `/admin/sales-trainer/training-records` | 训练记录 | admin | 查询训练记录和详情 | 否 | 是 | smoke |
| A-23 | `/admin/sales-trainer/analytics` | Journey 分析 | admin | 查看指标、趋势和模块分析 | 否 | 是 | smoke |
| A-24 | `/admin/sales-trainer/settings` | 配置中心 | admin | 查看配置健康和治理诊断 | 否 | 是 | smoke |
| A-25 | `/admin/sales-trainer/operation-logs` | 操作记录 | admin | 查询审计日志 | 否 | 是 | smoke |

## 旧入口兼容

| 编号 | URL | 页面类型 | 角色 | 关键主操作 | 旧路由兼容 | 需要 seed 数据 | 审计方式 |
|---|---|---|---|---|---|---|---|
| C-01 | `/admin/sales-trainer/articles` | 旧文章入口 | admin | 兼容进入学习专题 | 是 | 是 | smoke |
| C-02 | `/admin/sales-trainer/materials` | 旧材料入口 | admin | 兼容进入录音材料 | 是 | 是 | smoke |
| C-03 | `/admin/sales-trainer/score-standards` | 旧评分标准入口 | admin | 兼容进入录音评分标准 | 是 | 是 | smoke |
| C-04 | `/admin/sales-trainer/papers` | 旧考卷入口 | admin | 兼容进入专题考卷 | 是 | 是 | smoke |
| C-05 | `/admin/sales-trainer/questions` | 旧题库入口 | admin | 兼容进入专题题库 | 是 | 是 | smoke |
| C-06 | `/admin/sales-trainer/audio-submissions` | 旧录音提交入口 | admin | 兼容进入录音提交管理 | 是 | 是 | smoke |
| C-07 | `/admin/sales-trainer/score-results` | 旧评分结果入口 | admin | 兼容进入录音评分结果 | 是 | 是 | smoke |
| C-08 | `/admin/sales-trainer/training-tasks` | 旧训练任务入口 | admin | 兼容进入录音任务治理 | 是 | 是 | smoke |

## 排除范围

- `/training/sales`
- `/practice/*`
- `/admin/business-rules/sales-trainer-phase2`
- 其他非新人训练路径页面
