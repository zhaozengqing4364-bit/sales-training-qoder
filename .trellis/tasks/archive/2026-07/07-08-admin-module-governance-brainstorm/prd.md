# brainstorm: 新人训练后台模块治理

## Goal

把新人训练后台从“资源表/配置表导航”调整为“以前台训练模块为中心的治理后台”。管理员进入一个前台模块后，应在同一上下文中完成任务配置、材料、评分标准、记录、发布与审计，不再在多个孤立页面之间跳转。

## What I already know

* 用户希望“场景治理”不要作为后台显性模块名，录音类能力应叫“录音管理”。
* PPT 讲解、公司产品 Demo、金字塔演讲等是录音评测能力的不同载体/场景，不应和“录音上传 + AI 判断”能力层级混淆。
* 录音评分标准、学员录音、评分结果应收敛到录音管理内，而不是顶层独立入口。
* 学习专题应包含文章、单元、小测/考卷等配套内容；“考卷管理”不应作为顶层孤立入口。
* 只有管理员配置并发布后，前台才显示学习专题；学习专题得分展示但不阻塞后续关卡。

## Assumptions (temporary)

* 本轮先做信息架构与实施计划，不修改业务代码。
* 默认保留现有后端 API 和数据表，先通过前端后台 IA、路由兼容层和 ViewModel 编排完成治理收敛。
* 旧入口需要兼容或重定向，避免已有书签、权限测试和运维路径断裂。

## Open Questions

* 是否允许旧顶层入口在过渡期仍可访问，但从主导航隐藏并重定向到新模块内页面。

## Requirements (evolving)

* 录音后台主入口改为“录音管理”，下钻后管理录音任务/场景、材料、评分标准、录音记录、评分结果。
* 学习后台主入口改为“学习专题”，下钻后管理专题文章、专题单元、小测/考卷、AI 教练、发布治理。
* 后台导航以用户任务命名，隐藏 `scenario_key`、`purpose`、`module_key` 等工程字段。
* 创建、编辑、删除、查找、发布、回滚均在模块上下文内完成，符合上下文内完成原则。

## Acceptance Criteria (evolving)

* [ ] 新人训练后台顶层不再出现孤立的“录音评分标准”“学员录音”“评分结果”“考卷管理”等资源入口。
* [ ] 管理员从“录音管理”可以进入 PPT 讲解、公司产品 Demo、金字塔演讲，并在同一模块内完成材料和评分标准配置。
* [ ] 管理员从“学习专题”可以进入商务礼仪、销售技巧、客户常见质疑等专题，并在专题内管理文章、单元和考卷。
* [ ] 旧 URL 有兼容策略，不因 IA 调整造成 404 或权限绕过。
* [ ] 权限、发布、回滚、审计和快照机制不弱化。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 本轮分析不直接改代码。
* 不优先做数据库大迁移。
* 不把共享资源库彻底删除，只调整默认后台入口和上下文组织方式。

## Technical Notes

* `web/src/lib/sales-trainer/routes.ts` 当前顶层有 `trainingTasks`、`scoreStandards`、`articles`、`papers`、`materials`、`audioSubmissions`、`scoreResults` 等平铺入口。
* `web/src/app/admin/sales-trainer/training-tasks/page.tsx` 当前标题是“训练任务”，已列出录音评测场景和学习专题，但入口语义仍过泛。
* `web/src/app/admin/sales-trainer/training-tasks/[scenarioSlug]/page.tsx` 当前可在任务详情中绑定单元、材料和录音评测标准，但仍通过“快速进入对应管理页创建”跳出当前任务。
* `web/src/lib/sales-trainer/audio-evaluation-scenarios.ts` 已有录音场景注册：`ppt_explanation`、`company_product_demo`、`elevator_pitch`。
* `web/src/app/admin/sales-trainer/articles/page.tsx` 当前标题仍是“学习文章”，但实际管理的是学习专题配置。
* `web/src/app/admin/sales-trainer/papers/page.tsx` 当前为独立“商务技巧考卷管理”，未收敛到学习专题上下文。
* `docs/api-contract/sales-trainer.md` 已把默认模块矩阵中的录音场景必要绑定写清楚：单元、材料、已发布评分提示词；这适合变成“录音管理”页面内的配置健康状态。
* 现有 API 已支持材料、评分提示词、录音提交、评分结果、学习专题配置、考卷 CRUD；优先做后台页面编排与路由收敛，不必先做数据库迁移。
