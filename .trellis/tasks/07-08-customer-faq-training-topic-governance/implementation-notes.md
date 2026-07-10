# Implementation Notes

## 约束

- 中文交付。
- CodeGraph First：理解链路先用 `codegraph explore/node/search/impact/affected`，再用 `rg`/`sed` 精读。
- 不涉及非新人训练路径模块。
- 前台体验轻，后台治理稳；缺失数据优先在当前页面选择/快速新建/自动关联。
- 问答材料不能作为普通长文章导入。

## 已读规范

- AGENTS.md
- web/AGENTS.md
- web/src/app/admin/sales-trainer/AGENTS.md
- backend/AGENTS.md
- backend/src/sales_trainer/AGENTS.md
- docs/api-contract/sales-trainer.md
- .trellis/spec frontend/backend/guides 相关文档

`docs/uiux.md`、`docs/domain-glossary.md`、`docs/ai-governance.md` 当前不存在，后续按实际文档结构补充。

## CodeGraph 已完成

- 学习专题与商务礼仪实现：`NewcomerLearningTopicConfigService`、`LearningTopicProjectionService`、`BusinessEtiquetteLearningService`
- 题库/考卷/测验链路：`QuizService`、`ExamPaperService` 相关 blast radius
- AI Coach 配置与 prompt：`AiCoachChatPromptCompiler`、prompt revision resolver、model config
- 录音评分场景：`audio_evaluation_scenarios`、`DeucateScoringService`、audio submission polling
- 路径投影与发布治理：`SalesTrainerPathConfigService`
- 审计与 Playwright 入口：operation log、newcomer e2e 文件

## 子 agent 状态

用户要求最多 3 个子 agent。当前会话通过 `tool_search` 搜索 subagent/multi-agent 工具无结果，因此无法真正启动子 agent。替代执行为主 agent 内部按三个轨道审计：

1. 材料结构、重复项、风险口径、卡片拆分。
2. 前台学习体验、卡片、小测、AI 教练、录音演练复用。
3. 后台治理、权限、发布回滚、审计、API、测试风险。

## 已实现

1. 扩展学习专题 schema：新增 `customer_faq` topic、`content_kind="faq_cards"`、FAQ card/duplicate/evidence 字段、`source_card_keys`、录音场景和考卷引用字段，保持旧 `business_etiquette` 兼容。
2. 新增材料解析器：解析客户常见问答材料，输出卡片、重复组、案例证据、高风险/需售前确认标记和禁答边界；本地材料验证为 100 张卡片、8 组重复、22 个案例证据、20 个高风险/升级项。
3. 新增后台 API：`customer-faq/parse`、`customer-faq/generate-draft`；复用学习专题保存、发布预览、发布、回滚和 operation log。
4. 新增 learner API/page：`/newcomer-training/customer-faq/topic`、`/sales-trainer/learning-topics/customer-faq`、`/sales-trainer/learning-topics/customer-faq/coach`。
5. 新增后台一页式治理页：`/admin/sales-trainer/learning-topics/customer-faq`，支持导入解析、卡片搜索/筛选、编辑、新增、归档、单元概览、AI/录音/题库快捷入口、发布和回滚。
6. 新增录音场景：`customer_faq_oral_drill`，并接入前后端 audio scenario、路径配置编辑能力和 E2E 路由清单。
7. 更新旅程投影：active learning topic 的 `source_module_key` 不再重复出现在 `TrainingJourney.modules`，学习专题只进入 `learning_topics` 和 `learning_topic_summaries`，不阻塞主路径。
8. 更新入口语义：学习专题管理入口统一为 `/admin/sales-trainer/learning-topics`，旧 `/articles` 保持兼容。
9. 更新 ADR、API contract 和 Trellis backend spec。
10. 修复学习专题总览只显示已配置 topic 的问题：新增 starter 模板合并视图，未导入 `customer_faq` 时也显示“客户常见问答”入口和“待导入卡片”状态。

## 验证记录

- `backend/.venv/bin/ruff check ...`：通过。
- `backend/.venv/bin/pytest tests/unit/test_newcomer_learning_topic_config_service.py tests/unit/test_audio_evaluation_scenarios.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_learning_content_api.py -q --no-cov`：37 passed，1 个 passlib/crypt warning。
- `backend/.venv/bin/mypy <本次后端变更文件>`：本次相关文件通过；剩余既有债务 `src/common/ai/config_manager.py:279`。
- `web npx eslint <相关文件>`：通过。
- `web npm run lint`：通过，存在 81 个既有 warning，未扩大处理。
- `web npx tsc --noEmit`：通过。
- `web npx vitest run ...`：相关 6 文件 59 tests passed；额外新人训练入口相关 5 文件 28 tests passed。
- `web npx vitest run src/app/admin/sales-trainer/articles/page.test.tsx`：4 tests passed，覆盖未配置 `customer_faq` 也显示入口。
- `web npm run build`：通过，新增 `/admin/sales-trainer/learning-topics/customer-faq`、`/sales-trainer/learning-topics/customer-faq`、`/coach` 路由进入构建输出。
- Playwright 新人训练前后台专项审计已尝试运行，但 Chromium 启动缺少系统库 `libnspr4.so`；`npx playwright install-deps chromium` 因当前用户无 sudo 密码失败，记录为环境阻塞。

## 偏差记录

- 当前会话未暴露 subagent 工具，无法按用户期望真正开启 3 个 agent；已按三个分析轨道在主 agent 内执行并记录。
- Playwright 未能完成页面截图/交互审计，原因是系统依赖缺失且无 sudo；代码侧已补 route manifest，待环境补齐后运行同一命令即可审计。
- 本次先实现客户问答卡片学习、草稿生成、发布治理、前台卡片学习、轻量 AI 教练入口和录音场景入口；题目/考卷的“从卡片自动生成题”仍复用现有题库/考卷入口，未新增自动出题闭环。
