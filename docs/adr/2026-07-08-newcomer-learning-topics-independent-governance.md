# ADR-2026-07-08：新人训练学习专题独立治理

## Status

Accepted. 本 ADR 冻结“学习专题”从新人训练路径必修模块中拆出的治理边界，作为后续后台页面、Journey 投影、达标验收、AI Coach 和历史记录解释的依据。

## 背景

早期实现把 `business_skills` 同时承担三类职责：

- 新人训练路径中的必修关卡。
- 商务礼仪文章、小单元、小测和 AI 教练的内容配置。
- learner 首页和达标验收中的阻断依据。

这造成两个长期问题：第一，“商务技巧文章”不是稳定信息架构，未来还会有销售技巧、客户常见质疑等学习专题；第二，商务礼仪规范更像学习证据和补练入口，不应因为未完成而阻塞 PPT 演讲、后续演讲 demo 或达标验收主流程。

## 决策

### 1. 新增逻辑资产，不新增业务表

学习专题使用现有 `SalesTrainerAssetRevision`：

- `resource_type = "newcomer_learning_topics"`
- `logical_id = "newcomer_learning_topics_v1"`
- `schema_version = "newcomer_learning_topics_v1"`

不新增业务表，不做 migration。保存、发布、回滚、历史列表和影响预览沿用 governed revision 语义。

### 2. 学习专题与路径配置解耦

`newcomer_path` 继续负责必修训练任务顺序、录音、演讲、realtime gate 等主路径。专题内容、小单元、小测规则和商务礼仪 AI Coach 进入 `newcomer_learning_topics_v1.topics[]`。

第一版支持两类专题形态：

- `topic_key = "business_etiquette"`
- `source_module_key = "business_skills"`，仅表示从旧配置生成草稿的兼容来源。
- `topic_key = "customer_faq"`
- `source_module_key = "customer_faq"`，表示客户常见问答卡片库专题，不对应必修路径关卡。

`business_skills` 和 `customer_faq` 不再计入 required modules、overall completion 或下一关阻断。

### 3. 后台入口保留，用户语言调整

`/admin/sales-trainer/articles` 路由保留，用户可见命名改为“学习专题”。第一层展示学习专题，第一版只有“商务礼仪规范”。点击专题后再进入专题内容绑定、7 个小单元、章节映射、能力点、小测规则和 AI Coach 配置。

后台可从 active path 旧 `business_skills` 生成商务礼仪规范 working draft；该动作不自动发布，也不让 learner 可见。已有 working revision 时必须预览或显式覆盖。

### 4. Learner 展示非阻塞学习证据

`GET /api/v1/sales-trainer/journey` 新增 `learning_topics[]`。它和 `modules[]` 并列：

- `modules[]` 表示必修训练任务。
- `learning_topics[]` 表示非阻塞学习证据。

学习专题只在 active learning topic revision 发布且 topic enabled 后展示。未发布时不展示；前端不得硬编码显示商务礼仪规范。

小单元得分只复用 quiz attempt 的 `total_score`、`max_score`、`passed`，不引入积分、计费或奖励语义。

### 5. AI Coach 可选且 fail-closed

商务礼仪 AI Coach 是学习专题的可选配置：

- `enabled=false` 时专题可发布。
- `enabled=true` 时 Prompt、模型、输出 schema、字段级 RBAC 必须 fail-closed。
- AI Coach 结果可作为学习证据和弱项线索，但不替代人工达标确认，不阻塞主路径。

## 取舍

采用逻辑资产而不是新表，牺牲一部分查询便利性，换取零 migration、低风险回滚和与现有发布治理一致的历史解释。

保留 `/sales-trainer/business-skills` 和 `/admin/sales-trainer/articles`，避免破坏旧链接；新增 `/sales-trainer/learning-topics/business-etiquette` 和 `/sales-trainer/learning-topics/customer-faq` 作为更准确的新入口。

专题不是通用 CMS。新增销售技巧、客户质疑等专题时，应按同一 payload 扩展 topic key、内容形态和发布校验，而不是复制一套路径模块。

客户问答专题采用 `content_kind="faq_cards"`：材料先解析为受审核问答卡片、重复问题组、案例证据和禁答边界，再由后台生成学习小单元。PPT 讲解、公司产品 Demo、客户问答口播都属于“上传录音并由 AI 评分”的能力；PPT 或客户问答只是载体/场景，不应作为能力层级。

## 影响

### API

- Admin 新增 `/api/v1/admin/newcomer-training/learning-topics/*` 配置、生成草稿、发布、回滚和 revisions 端点。
- 客户问答新增 `/api/v1/admin/newcomer-training/learning-topics/customer-faq/parse` 和 `/generate-draft`；learner 读取 `/api/v1/newcomer-training/customer-faq/topic`。
- Learner Journey 新增 `learning_topics[]`。
- 商务礼仪文章、小单元、小测和 AI Coach 运行时读取 active learning topic revision。
- `/sales-trainer/business-skills` 保持兼容，读取同一个 published learning topic projection。

### 数据

- 无 migration。
- 发布/回滚只移动 learning topics active pointer，只影响未来 learner 展示。
- 历史 quiz attempt、AI Coach session、训练记录、阅读进度不被回写。

### 权限与审计

- 普通学习专题配置需要 `sales_trainer.manage_modules`。
- AI Coach 高风险字段仍需 `sales_trainer.manage_prompts`。
- 保存、生成草稿、发布、回滚都必须写操作日志，包含 before/after revision、reason、trace_id 和 `impact_scope="future_learners_only"`。

### 达标验收与分析

- Readiness Dossier 不把学习专题未完成算作未达标。
- Journey Analytics 单独统计 `learning_topic_summaries`。
- 商务礼仪小测和 AI Coach 结果可进入 evidence，但不得污染 required module funnel。

## 回滚

业务回滚优先回滚 `newcomer_learning_topics_v1` active revision 或停用 topic。该回滚只影响未来 learner 展示，不改写历史记录。

如果学习专题治理整体需要暂停，可隐藏 `/admin/sales-trainer/articles` 的专题发布入口，并保持旧 `/sales-trainer/business-skills` 直链返回未配置状态；不得把旧 `business_skills` 重新计入 required modules。
