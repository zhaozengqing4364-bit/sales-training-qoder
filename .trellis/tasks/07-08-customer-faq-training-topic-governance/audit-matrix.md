# 审计矩阵

| 区域 | 必做能力 | 现有复用点 | 实现策略 | 验证 |
| --- | --- | --- | --- | --- |
| 学习专题 revision | customer_faq 草稿/发布/回滚/future-only | `NewcomerLearningTopicConfigService`、`sales_trainer_asset_revisions` | 已扩展 topic key 和 payload，保留非阻塞规则 | 后端 pytest 通过；API 契约已更新 |
| 问答卡片库 | 导入、解析、去重、编辑、新增、归档、筛选 | 学习专题 payload、operation log | 已新增卡片 schema、解析工具、parse/generate API 和后台页 | pytest parser/service 通过；Playwright 环境阻塞 |
| 前台专题 | 首页、卡片列表、搜索筛选、单元学习 | `LearningTopicProjectionService`、业务礼仪前台模式 | 已新增 customer_faq learner API/page | tsc/build 通过；Playwright 环境阻塞 |
| 小测/题库/考卷 | 卡片生成题目、绑定来源卡片、组卷 | question bank、paper API | 已提供题库/考卷快捷入口和 `source_card_keys`；自动从卡片出题未在本轮实现 | 现有题库/考卷测试未扩大；残余事项记录 |
| AI 教练 | 已发布卡片边界、依据追踪、高风险提醒 | AI Coach prompt/config/session | 已提供基于已发布卡片的轻量教练入口；完整 LLM Prompt 运行时未在本轮实现 | tsc/build 通过；后续需补 AI runtime 测试 |
| 口播录音 | 客户问答口播演练、评分维度、结果建议 | `audio_evaluation_scenarios`、audio page、score prompts | 已新增 `customer_faq_oral_drill` 场景并接入录音管理入口 | pytest audio scenario 通过；build 路由通过 |
| 后台一页式治理 | 一个主入口内完成配置，选择优先 | learning topics/admin pages | 已新增 customer-faq 一页式页面，内嵌导入、卡片、单元、AI/录音/题库入口和发布操作 | tsc/build 通过；Playwright 环境阻塞 |
| 权限安全 | 后端权限权威、raw JSON/prompt 高级可见 | admin permission、operation log | 所有写入 API 校验权限并审计 | rbac pytest、Playwright fail-closed |
| 文档 | API/数据/发布/回滚契约 | `docs/api-contract/sales-trainer.md` | 更新新增专题契约和 ADR 需要时补充 | 文档 diff 审查 |
| 测试 | tsc/lint/build/vitest/playwright/pytest/codegraph impact | 现有测试体系 | 已跑 CodeGraph affected、ruff、pytest、eslint、tsc、vitest、build；Playwright 受系统依赖阻塞 | 记录命令和结果 |
