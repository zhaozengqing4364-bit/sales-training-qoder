# 新人训练路径后台模块化治理：仓库约束调研

## 结论

当前系统已经有较强的发布治理、审计、材料库、题库、考卷、评分、训练记录和达标档案基础。真正的瓶颈不是“缺页面”，而是训练路径仍由固定模块 key、固定前端模块矩阵和若干业务特例共同驱动。后续要安全扩展，应优先建设“受控模块注册表 + 训练任务模板 + 学习内容通用化”的配置层，而不是为每一种新关卡新增一套后端服务和一级菜单。

## 已确认约束

* `CONTEXT.md` 已定义“新人训练路径”是异步学习、录音上传、AI 评分、文章学习和考卷考试路径，不是 realtime WebSocket 运行时。
* `CONTEXT.md` 已定义“训练任务模板”：管理员可新增或调整系统认识的任务类型下的任务实例，但不能自由创造系统不认识的任务类型。
* `backend/src/sales_trainer/AGENTS.md` 要求 `api.py` 保持薄路由，业务规则进入 service/config，发布、回滚、归档、评分、上传和人工修正必须有审计。
* `web/src/app/admin/sales-trainer/AGENTS.md` 要求后台导航以 `module-nav.tsx`/集中路由源为准，业务配置文案不应散落在页面常量里。
* `docs/adr/2026-06-27-newcomer-training-closed-loop.md` 已冻结：active path revision 是 learner 唯一真源；TrainingJourney 是闭环读模型；历史必须 snapshot-first；realtime 只能通过 runtime binding 接入。
* `docs/api-contract/sales-trainer.md` 已冻结：`newcomer_path.modules[].module_type` 只允许 `audio_scoring`、`article_exam`、`audio_scoring_group`、`realtime_roleplay`、`realtime_placeholder`。
* `docs/api-contract/sales-trainer.md` 已把商务礼仪小单元放在 `NewcomerPathModuleConfig.learning_units`，说明它本质上是路径模块配置，不应该由 learner 页面硬生成。

## 当前耦合点

* 后端固定模块 key：`backend/src/sales_trainer/services/path_config_models.py` 中 `CANONICAL_NEWCOMER_MODULE_KEYS` 和 `CANONICAL_NEWCOMER_MODULE_TYPES` 把 `ppt_explanation`、`business_skills`、`elevator_pitch`、`realtime_roleplay`、`realtime_roleplay_placeholder` 写成固定矩阵。
* 后端发布校验按具体类型集中在 `SalesTrainerPathConfigService._validate_publish_payload`，其中 `business_skills` 还有 AI Coach 必配特例。
* 前端固定模块矩阵：`web/src/lib/sales-trainer/config-center-definitions.ts` 中 `MODULE_DEFINITIONS` 写死标题、描述、补救入口和 learner 预览文案。
* 前端类型也固定模块 key：`web/src/lib/sales-trainer/config-center-types.ts` 中 `NewcomerConfigModuleKey` 是固定 union。
* 文章入口命名耦合：`web/src/lib/sales-trainer/routes.ts` 使用“商务技巧文章”，但底层实际是 `LearningContent` 绑定，未来应改成“学习文章/学习内容”。
* 商务礼仪是强业务特例：`business_etiquette_api.py`、`business_etiquette_learning_service.py`、`business_etiquette_learning_unit_defaults.py`、前端 `business-etiquette-units.ts` 构成专用训练包能力。
* `web/src/lib/sales-trainer/path-config-editing.ts` 的 `defaultAudioModule` 给音频模块也带了 `learning_units: defaultBusinessEtiquetteLearningUnits()`，这是配置形状上的领域泄漏，后续模块增多会放大风险。

## 可复用基础

* `SalesTrainerPathConfigService` 已具备 working revision、active revision、publish preview、rollback preview、future-only 影响范围、operation log。
* `SalesTrainerAssetRevisionService` 可承载路径配置、训练包、Prompt 等可发布资产的修订模型。
* `SalesTrainerMaterial` / `SalesTrainerMaterialVersion` 已支持材料和版本；材料库计划文档已明确 PPT、逐字稿、示例录音、附件都应进入材料库。
* `TrainingJourneyService` 已开始聚合 audio、quiz、business etiquette、AI Coach、realtime outcome，适合作为管理端“训练记录/达标验收/Journey 分析”的读模型基础。
* `SalesTrainerPathConfigPayload.modules[]` 已经能绑定 `material_id`、`material_version_id`、`scoring_prompt_id`、`learning_content_id`、`exam_paper_id`、`duration_options`、`learning_units`、`ai_coach` 和 `runtime_binding`。

## 安全稳定方向

* 不要把“演讲 demo”做成新 module_type；应做成材料库里的 `example_audio` / `demo_video` / `script` 等任务材料绑定。
* 不要把“学习文章”继续绑定到商务礼仪服务名；应保留商务礼仪训练包作为一个内容包/能力包，同时让文章管理入口通用化。
* 不要允许管理员任意创建未知 module_type；系统支持的执行器类型保持有限，模块实例和任务实例可配置。
* 先做读侧和配置中心解耦，再做 DB schema；避免一次性迁移 active revision、训练记录、历史快照和 learner 入口。
* 所有路径发布仍必须走 publish preview、reason、trace_id、operation log、future-only 和 rollback preview。

## 推荐技术路线

1. 第一阶段：命名和配置治理收敛，不改运行时语义。
2. 第二阶段：引入模块注册表读模型，让前端配置中心从后端 registry/active revision 生成模块矩阵。
3. 第三阶段：把 `business_skills` 从“硬编码商务技巧模块”迁移为 `article_exam` 任务实例 + `business_etiquette` 内容包绑定。
4. 第四阶段：建设通用任务材料绑定，让 PPT、录音、演讲 demo、示例稿件都通过材料库绑定。
5. 第五阶段：后台菜单收敛为“配置治理”和“训练结果治理”，旧入口兼容保留。

