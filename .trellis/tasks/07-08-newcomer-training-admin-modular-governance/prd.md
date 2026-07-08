# brainstorm: 新人训练路径后台模块化治理

## Goal

为当前新人训练路径后台制定一套安全、稳定、可扩展的模块化治理方案：既保持现有 PPT 讲解录音、学习文章/商务礼仪、金字塔演讲、AI 教练、材料库、达标验收和训练记录闭环可用，又能支持后续“演讲 demo”等新训练资产或新任务实例接入，避免每新增一个业务内容就复制一套服务、页面、枚举和硬编码。

## What I already know

* 用户明确要求先分析和计划，不修改业务代码。
* 当前后台入口包括工作台、模块单元、路径配置、AI 教练配置、题库、录音评分标准、文章、考卷、材料库、达标验收、训练记录、学员录音、评分结果、Journey 分析、配置、操作记录。
* 用户已指出“商务技巧文章”未来应更名或升级为“学习文章”，商务技巧只是学习内容的一部分。
* 用户已指出第一关 PPT 演讲/录音，以及未来可能新增“演讲 demo”，需要考虑后台如何管理。
* `CONTEXT.md` 已明确：新人训练路径的具体训练内容、材料、评分标准或关卡绑定不能写死在页面或服务逻辑里。
* `CONTEXT.md` 已明确：训练任务模板是后台配置的训练关卡业务模板；管理员可以新增或调整系统认识的任务类型下的任务实例，但不能自由创造系统不认识的任务类型。
* 当前后端路径配置的发布、回滚、审计、future-only 生效机制较成熟，应复用而不是重建。
* 当前模块层仍存在明显耦合：固定 module_key、固定前端模块矩阵、商务礼仪专用服务、文章入口命名、音频模块和商务礼仪 learning_units 形状混杂。

## Assumptions (temporary)

* 第一阶段目标不是立即平台化所有训练类型，而是先减少新增模块时的硬编码和命名耦合。
* 后续仍保留 `sales_trainer` 技术命名和 `/admin/sales-trainer/*` 路由以保持兼容，用户可见命名逐步切换为“新人训练路径”语言。
* 系统支持的执行类型应保持有限集合，例如录音评分、文章学习+考试、录音组、AI 补练、realtime binding；扩展发生在任务实例、材料绑定、内容包和发布配置层。
* 商务礼仪可以继续作为专用训练包存在，但不应继续代表整个“学习文章”能力。

## Open Questions

* 暂无阻塞问题；下一步可进入最终方案确认与实施拆解。

## Requirements (evolving)

* 后台模块必须区分“系统认识的执行器类型”和“业务可配置的训练任务实例”。
* 学习文章入口应通用化，商务礼仪作为学习内容/训练包的一种，而不是文章模块的唯一语义。
* PPT 讲解录音、金字塔演讲、未来演讲 demo 应通过训练任务模板 + 材料库 + 评分方案组合管理，不新增一套独立业务域。
* 演讲 demo 应优先作为任务材料绑定，例如示例录音、示例视频、示例稿、评分参考，而不是 module_type。
* 路径配置仍以 active revision 为 learner 真源；发布、回滚只影响未来学员/新提交，不改历史记录。
* 历史 attempt、submission、score result、AI Coach session 和 business etiquette quiz attempt 必须 snapshot-first。
* 管理端缺材料、缺考卷、缺学习内容、缺评分方案时，应在当前配置页面提供就地选择/快速新建/补齐引导，符合上下文内完成原则。
* 所有高风险配置发布必须保留 reason、trace_id、preview、audit log、rollback preview。
* 前端展示不得继续依赖页面散落的模块标题、业务规则、评分阈值、材料 URL 或 Prompt 信息。
* 已确认采用 Approach A：渐进式解耦。第一阶段应优先保留现有 API、数据库形状、active revision 和历史快照语义，把模块语义逐步从硬编码页面/常量迁入受控配置层。
* 已确认第一阶段范围采用 Phase 0-2：文档/ADR + 后台命名收敛 + 模块注册表读模型骨架；不做 DB migration，不删除旧入口，不破坏旧 API。
* 已确认模块注册表第一版以“后端代码常量注册表”为真源：集中到 registry service，通过 API 输出给前端；不进入 ConfigBundle/数据库，不从 active path revision 单独派生。
* 已确认“商务技巧文章”升级为“学习文章/学习内容”时，第一阶段保留旧路由 `/admin/sales-trainer/articles`，只改用户可见命名和页面结构，避免破坏旧链接与权限导航。
* 学习文章页面第一层应先展示文章专题/内容包，例如“商务礼仪规范”“销售技巧文章”“客户常见质疑文章”；商务礼仪只是其中一个专题，不再代表整个文章入口。
* 商务礼仪规范点进去后再展示现有 7 个小单元；也就是“学习文章列表 -> 商务礼仪规范 -> 7 个单元 -> 具体章节/内容”的两到三层结构。
* 已确认学习文章第一层只展示后端管理员已配置到新人训练路径/学习专题注册表中的专题；未配置的“销售技巧文章”“客户常见质疑文章”等不在前端显示。
* 已确认“积分”不是独立积分/计费/激励体系，而是现有考试正常得分展示：每个单元通过考试后显示实际得分和可得分。
* 已确认学习专题属于非阻塞学习部分：可以显示小测得分/通过状态，但不阻塞后续下一关，不参与 journey 必过判定。
* 学习专题显示必须后端配置驱动：前端不得因为代码里有默认专题就展示；只有 active/working 配置或后端 registry 标记启用后才出现。
* 学习专题默认 `required=false`、`blocks_next=false`，阅读完成或小测结果只产出 learning progress / score evidence，不影响后续关卡解锁。
* 已确认小单元“可得分/实际得分”第一阶段直接复用现有小测结果：`total_score / max_score / passed`，不新增独立分值配置。
* 已确认 learner 前端布局采用主路径旁的“学习专题”区：PPT、演讲等必修训练任务仍作为主路径；商务礼仪规范、销售技巧、客户常见质疑等非阻塞专题放在旁侧/下方学习专题区，显示进度和小测分数但不锁关。
* 已确认第一阶段从必修 path modules 拆出 `learning_topics` projection：后端兼容旧 `business_skills` 配置，但 learner/API 输出时把它归为非阻塞学习专题，不计入必过模块。
* 已确认学习专题第一阶段采用独立配置源，不继续塞在新人路径 active path modules 里；商务礼仪规范、销售技巧文章、客户常见质疑文章应作为学习专题配置项被管理员启用后才显示。
* 已确认学习专题配置采用独立发布：学习专题有自己的保存、发布、回滚、预览和审计，不跟随新人路径一起发布，也不保存即生效。
* 已确认旧 `business_skills` 兼容迁移采用“生成待发布草稿”：从现有路径配置提取学习内容、小单元、小测/AI Coach 等绑定生成 learning topics working revision，但不自动展示；管理员确认并发布后 learner 才显示“商务礼仪规范”。
* 已确认学习专题后台第一版只支持从现有 `business_skills` 生成、编辑、发布“商务礼仪规范”；暂不支持管理员从零新增任意学习专题，也不预置销售技巧/客户质疑模板。
* 已确认商务礼仪规范第一版允许管理员编辑标题、绑定学习文章、7 个小单元配置和小测规则；不是只读确认发布。
* 已确认现有 AI Coach 配置迁入商务礼仪规范学习专题，作为可选非阻塞能力保留；AI Coach 训练结果可以作为学习证据，但不阻塞下一关。
* AI Coach 若启用，Prompt 绑定、模型配置、输出契约和治理校验必须 fail-closed；若禁用，不影响学习专题发布。
* 已确认 learner 端路由保留旧 `/sales-trainer/business-skills`，同时新增或内部映射到 `/sales-trainer/learning-topics/business-etiquette`；旧链接继续可用，新语义逐步收敛到 learning topic。

## Acceptance Criteria (evolving)

* [ ] 给出当前模块职责、耦合点和风险分级。
* [ ] 给出目标领域模型：路径、模块、任务模板、材料、学习内容、考卷、评分方案、AI 教练、训练证据、达标档案的关系。
* [ ] 给出分阶段实施计划，每阶段说明改动范围、兼容策略、验证方式、回滚方式。
* [ ] 给出“商务技巧文章”升级为“学习文章”的兼容命名与 API 策略。
* [ ] 给出“PPT 演讲/录音/演讲 demo”如何用通用材料和任务模板管理的方案。
* [ ] 标明不建议做的方案和原因。
* [ ] 明确哪些旧入口保留、聚合、改名或后续下线。
* [ ] 模块注册表第一版由后端 registry service 输出，前端不再维护第二份模块定义矩阵。
* [ ] 学习文章后台形成两层以上信息架构：第一层专题/内容包，第二层专题内单元编排，第三层才是具体章节或内容编辑。
* [ ] 未被管理员配置启用的学习专题不展示在 learner 前端，也不作为后台路径配置中的默认启用项。
* [ ] 学习专题完成状态和小测得分不会阻塞下一关；TrainingJourney/达标档案必须能区分 required task 与 optional learning evidence。
* [ ] 小单元得分展示复用现有 `BusinessEtiquetteUnitQuizAttemptResponse.total_score/max_score/passed`，不新增积分或单元分值配置。
* [ ] learner 前端必须清晰区分“必修训练路径”和“非阻塞学习专题”，非阻塞专题不得在视觉上暗示卡住下一关。
* [ ] `business_skills` 在 learner/Journey 投影中归入 `learning_topics`，不再计入 required modules、overall required completion 或下一关阻断。
* [ ] 学习专题有独立配置源，未被管理员启用的专题不进入 learner API，也不在前端预置展示。
* [ ] 学习专题配置具备独立 working/active revision、publish preview、rollback preview、reason、trace_id 和 operation log。
* [ ] 旧 `business_skills` 只生成 learning topics working revision，不自动发布、不自动 learner 可见；发布前能预览从旧配置迁出的绑定和小单元。
* [ ] 第一版学习专题后台只覆盖“商务礼仪规范”迁移、编辑、发布和回滚；销售技巧文章、客户常见质疑文章只作为后续扩展，不进入第一版 UI。
* [ ] 商务礼仪规范第一版支持编辑专题标题、学习内容绑定、7 个小单元、章节映射、能力点、小测题量、通过线、重测规则和题型权重。
* [ ] 商务礼仪规范第一版迁入 AI Coach 配置；AI Coach enabled 且配置非法时发布失败，disabled 时专题可发布。
* [ ] AI Coach 结果不参与下一关阻断，也不把 AI 初评当作人工确认达标结论。
* [ ] learner 端旧 `/sales-trainer/business-skills` 路由保持兼容，新 learning topic 路由/别名可访问同一专题体验。

## Definition of Done (team quality bar)

* 计划能解释现有代码和文档约束，而不是只给抽象最佳实践。
* 计划不要求一次性破坏 active revision、历史快照、现有 learner 路径和后台菜单。
* 涉及 API/DTO/权限/发布治理的阶段必须列出测试和回归路径。
* 涉及长期模型决策的阶段必须建议更新 ADR 和 `docs/api-contract/sales-trainer.md`。
* 所有新增配置都必须有默认值、校验、缺失诊断和操作日志。

## Out of Scope (explicit)

* 本轮不修改业务代码。
* 本轮不做数据库 migration。
* 本轮不接入新的 realtime runtime。
* 本轮不删除旧后台入口。
* 本轮不把商务礼仪训练包完全抽象成通用内容包平台。

## Technical Notes

* `backend/src/sales_trainer/services/path_config_models.py`：固定 `CANONICAL_NEWCOMER_MODULE_KEYS` 和 key/type 映射，是当前模块可扩展性的主要限制。
* `backend/src/sales_trainer/services/path_config_service.py`：路径发布治理能力成熟，但校验职责过重，后续适合按 module_type/task executor 拆分 validator。
* `backend/src/sales_trainer/schemas.py`：`NewcomerPathModuleConfig` 已具备多种绑定字段，但 `module_type` 是固定 Literal，适合作为受控执行器类型，不适合作为无限业务类型。
* `web/src/lib/sales-trainer/config-center-definitions.ts`：前端固定模块标题、顺序、描述和补救入口，后续应改为由后端 registry/active revision 输出。
* `web/src/lib/sales-trainer/path-config-editing.ts`：`defaultAudioModule` 包含商务礼仪 `learning_units`，暴露了配置形状耦合。
* `web/src/lib/sales-trainer/routes.ts`：`articles` 当前展示为“商务技巧文章”，应逐步改为“学习文章”或“学习内容”。
* `backend/src/sales_trainer/services/business_etiquette_learning_service.py`：强绑定 `BUSINESS_SKILLS_MODULE_KEY = "business_skills"`，说明商务礼仪目前是专用训练包服务。
* `docs/adr/2026-06-27-newcomer-training-closed-loop.md`：已明确 active path revision、TrainingJourney、snapshot-first、runtime binding 边界。
* `docs/api-contract/sales-trainer.md`：已列出路径模块配置、学习内容绑定、商务礼仪小单元、AI Coach、材料等契约。

## Research References

* [`research/repo-constraints.md`](research/repo-constraints.md) — 当前仓库已有治理基础较强，推荐走“受控模块注册表 + 训练任务模板 + 学习内容通用化”的渐进路线。

## Feasible Approaches

### Approach A：渐进式解耦（推荐）

先保留现有 API 和数据库形状，把模块语义从硬编码页面/常量迁入“模块注册表读模型”和路径 active revision；同时把“商务技巧文章”用户可见命名升级为“学习文章”，把商务礼仪保留为内容包特例。

优点：风险低，兼容现有发布治理和历史记录；能先解决新增 demo、文章命名、后台入口混乱的问题。

缺点：短期仍会保留一些旧 key，例如 `business_skills`、`ppt_explanation`。

### Approach B：直接抽象训练任务平台

新增 DB 级 `training_task_template`、`module_registry`、`content_package`、`task_material_binding` 等实体，把路径模块完全迁到新模型。

优点：长期模型最干净。

缺点：需要 migration、回填、双写/双读、历史数据解释、前后端大范围改造；当前风险过高。

### Approach C：只改菜单和文案

把“商务技巧文章”改名“学习文章”，把部分入口合并或重命名，不动模块模型。

优点：最快。

缺点：不能解决新任务、新 demo、新文章类型扩展问题，后续还会继续复制硬编码。

## Preliminary Plan

### Phase 0：冻结术语与边界

* 目标：统一团队语言，避免把“模块”“单元”“任务”“文章”“材料”“demo”混用。
* 产出：
  * 更新或新增 ADR：新人训练路径后台模块化治理。
  * 更新 `CONTEXT.md`：补充“学习内容”“内容包”“训练任务模板”“任务材料绑定”“演讲示例材料”。
  * 更新 `docs/api-contract/sales-trainer.md`：声明“学习文章”是 `LearningContent` 管理入口，商务礼仪是内容包/训练包。
* 风险：低。
* 回滚：文档 revert。

### Phase 1：后台入口与命名收敛

* 目标：减少用户理解成本，不破坏 API。
* 建议：
  * 保留 `/admin/sales-trainer/articles` 旧 route，菜单和页面标题从 `商务技巧文章` 改为 `学习文章` 或 `学习内容`。
  * 页面第一层展示学习专题/内容包卡片，而不是直接展示商务技巧文章列表。
  * 第一层至少支持“商务礼仪规范”，后续可扩展“销售技巧文章”“客户常见质疑文章”等专题。
  * 第一层专题卡片只展示后端已配置启用的专题；未配置专题不预置展示，避免前端泄漏未来规划或测试数据。
  * 点击“商务礼仪规范”进入第二层，展示 7 个商务礼仪小单元，并保留资料导入、能力点、题目草稿、路径绑定状态等治理入口。
  * 学习专题在路径中标记为非阻塞：完成后沉淀小测得分、通过状态和学习证据，但不阻塞下一关入口，不让 `completion_satisfied=false` 影响整体 journey passed。
  * 具体章节编辑仍可复用 `/admin/learning-contents/{learning_content_id}`，但应从第二层提供就地跳转/抽屉入口，避免用户为了补数据离开主流程后迷路。
  * `录音评分标准` 后续逐步升级为 `评分方案`，包含 learner rubric + AI scoring prompt。
  * `学员录音`、`评分结果` 后续并入 `训练记录` 的筛选视图，迁移期保留旧入口。
* 验证：
  * 导航权限矩阵。
  * 旧 URL 可访问或重定向。
  * 页面空/错/无权限状态。
  * “商务礼仪规范”能进入 7 个小单元视图；未绑定学习内容、缺章节、缺小单元时在当前页面给出补齐入口。
  * 未配置专题不出现在 learner 前端；已配置专题显示小测得分、通过状态和学习进度，但不影响下一关可进入状态。
* 风险：P2。
* 回滚：保留原 label 和 route 常量即可回退。

### Phase 2：模块注册表读模型

* 目标：把固定前端 `MODULE_DEFINITIONS` 和后端 canonical key 矩阵收敛到统一后端 registry。
* 建议：
  * 新增后端只读 registry service，输出模块 key、显示名、执行器类型、默认动作、材料需求、可绑定对象、治理能力、默认 remediation href。
  * 第一版 registry 由后端代码常量生成，作为唯一真源；前端不再自行维护第二份模块矩阵。
  * 暂不把 registry 放入 ConfigBundle/数据库，避免第一阶段引入坏配置、发布回滚和迁移风险。
  * path active revision 覆盖 registry 的 title、description、order、enabled、bindings。
  * 保持 module_type allowlist，不允许未知执行器类型发布。
* 验证：
  * 路径配置中心能从 registry + active revision 构建模块卡片。
  * 未知 module_key 发布失败；旧兼容 key 仍提示迁移。
  * publish preview 仍能列出 changed_module_keys。
* 风险：P1。
* 回滚：前端可临时回退旧 `MODULE_DEFINITIONS`，后端 registry 不影响 active revision 数据。

### Phase 3：学习文章通用化

* 目标：让文章能力服务于多个学习内容，而不是只服务商务技巧。
* 建议：
  * 管理端 `/articles` 改为通用 `LearningContent` 管理壳，展示绑定到新人训练路径的学习内容。
  * 商务礼仪导入、能力点、小单元、AI 出题仍保留在“商务礼仪训练包”专区。
  * `article_exam` module 只关心 `learning_content_id`、`exam_paper_id`、`learning_units`、AI coach policy，不关心内容是否叫商务礼仪。
  * 新增学习内容时支持就地选择/快速新建/绑定到当前路径模块。
* 验证：
  * 商务礼仪旧流程不变。
  * 新学习内容可被路径模块绑定。
  * 草稿/归档内容发布校验 fail-closed。
* 风险：P1。
* 回滚：旧商务礼仪 API 和路由保留，通用入口仅作为壳层撤回。

### Phase 4：音频任务与演讲 demo 材料化

* 目标：支持 PPT 演讲、金字塔演讲和未来演讲 demo，不新增 module_type。
* 建议：
  * `PPT 讲解录音` 和 `金字塔演讲` 都视为 `audio_scoring` / `audio_scoring_group` 执行器下的任务实例。
  * 材料库支持材料类型：PPT、逐字稿、示例录音、示例视频、评分参考、附件。
  * 任务材料绑定支持 purpose、required、learner_visible、confirmation_required、version_policy、display_order。
  * 演讲 demo 作为示例材料绑定在任务上，可选要求学员观看/确认，不作为独立关卡，除非未来产品明确它是可评分提交任务。
* 验证：
  * 缺必需 PPT/评分方案时发布失败。
  * 示例 demo 缺失不阻塞发布，除非配置为 required。
  * 学员提交冻结材料版本和评分方案版本。
* 风险：P1。
* 回滚：只撤回新材料类型/绑定 UI，不影响原音频提交。

### Phase 5：validator 按执行器拆分

* 目标：降低 `SalesTrainerPathConfigService` 过重职责。
* 建议：
  * 保留 publish orchestration 在 `SalesTrainerPathConfigService`。
  * 抽出 `PathModuleValidator` 接口：audio、audio_group、article_exam、realtime。
  * 高风险 AI Coach、材料、评分方案、学习内容、考卷校验分别复用已有 service。
  * 所有 validator 返回 typed diagnostic，不直接拼散落文案。
* 验证：
  * 现有 path config unit/integration tests 全部通过。
  * 每种 module_type 覆盖缺绑定、草稿绑定、归档绑定、非法 capability、重复 order。
* 风险：P1。
* 回滚：保持原 service 方法可恢复，拆分前先加 characterization tests。

### Phase 6：记录与达标治理收敛

* 目标：让后台从“技术流水页面”转向“训练证据和达标档案”。
* 建议：
  * `训练记录` 成为主入口，学员录音、评分结果、商务礼仪小测、AI Coach session、realtime outcome 作为筛选。
  * `达标验收` 读取 TrainingJourney 和 readiness dossier，不重新推断状态。
  * `Journey 分析` 聚合模块、能力项、材料版本和失败原因。
* 验证：
  * 历史记录 snapshot-first。
  * 权限按培训负责人团队范围收口。
  * AI 建议不被标记为已验证达标事实。
* 风险：P1。
* 回滚：保留旧列表入口为只读视图。

## Recommended MVP

本任务建议 MVP 选择 Approach A，并把第一轮实施范围限制在 Phase 0-2 的计划确认与小步落地：先统一术语、命名和 registry 读模型，再处理学习文章和演讲 demo 的深层数据模型。这样能最大限度复用现有发布治理，避免过早 migration。

## Confirmed MVP Scope

第一阶段锁定 Phase 0-2：

* Phase 0：冻结术语与边界，补 ADR / `CONTEXT.md` / API 契约说明。
* Phase 1：后台入口与命名收敛，把“商务技巧文章”升级为“学习文章/学习内容”，商务礼仪保留为专区能力。
* Phase 2：建设模块注册表读模型骨架，让后端成为模块定义唯一来源，前端配置中心从 registry + active revision 构建展示。
* 模块注册表第一版真源：后端代码常量 registry service；后续如确有运营自定义模块定义需求，再迁入 ConfigBundle/数据库治理。
* 学习文章路由策略：保留 `/admin/sales-trainer/articles` 旧 route，只调整用户可见命名与页面结构。
* 学习文章信息架构：第一层专题/内容包，第二层小单元/专题治理，第三层具体章节或内容编辑。
* 学习专题显示策略：只显示管理员已配置启用的专题。
* 学习专题进度策略：非阻塞，有小测得分/学习证据，不阻塞下一关。
* 学习专题得分策略：第一阶段复用现有小测 `total_score / max_score / passed`，不新增独立积分或分值配置。
* learner 布局策略：主路径旁展示“学习专题”区，必修训练关卡和非阻塞专题分区展示。
* `business_skills` 承接策略：保留旧配置兼容，但 API/read model 投影为 `learning_topics`，从必修路径模块里剥离。
* 学习专题配置源：新增独立学习专题配置，不继续依赖 active path modules 作为专题启用真源。
* 学习专题发布策略：独立发布、独立回滚、独立审计；不与新人路径配置发布耦合。
* 旧配置迁移策略：从 `business_skills` 生成待发布 learning topics 草稿，由管理员确认发布后生效。
* 学习专题后台范围：第一版只支持 `business_etiquette`/“商务礼仪规范”从旧配置生成、编辑、发布；不开放任意 topic 新增。
* 商务礼仪规范编辑范围：标题、绑定文章、7 个单元、小测规则可编辑；发布后进入 active learning topics revision。
* AI Coach 承接策略：从旧 `business_skills` 迁入商务礼仪规范学习专题，保留入口和配置，但作为 optional non-blocking learning evidence。
* learner 路由兼容策略：保留 `/sales-trainer/business-skills`，新增或内部映射 `/sales-trainer/learning-topics/business-etiquette`。

明确不包含：

* 不新增 DB 表。
* 不迁移历史数据。
* 不删除旧 route。
* 不改 learner 主流程语义。
* 不把商务礼仪训练包完全抽象成通用内容包平台。
* 独立学习专题配置优先复用既有 `SalesTrainerAssetRevision` 治理能力；除非后续确认必须查询优化或复杂筛选，第一阶段仍避免新增业务表。

## Decision (ADR-lite)

**Context**: 当前新人训练路径已有发布治理、材料、题库、评分、训练记录和达标档案基础，但模块扩展仍由固定 module_key、前端固定模块矩阵和商务礼仪专用链路共同驱动。直接平台化会触发 migration、历史回填、双读双写和 learner 主流程回归风险。

**Decision**: 采用 Approach A：渐进式解耦。先保留现有 API 和数据库形状，通过术语冻结、后台命名收敛、模块注册表读模型和配置中心唯一来源，逐步把“业务模块实例”从硬编码中解耦出来。

**Consequences**: 短期继续保留 `business_skills`、`ppt_explanation`、`elevator_pitch` 等兼容 key；长期通过 registry、任务模板、材料绑定和学习内容通用化降低新增训练任务成本。该方案牺牲部分短期模型洁净度，换取更低发布风险和更强历史兼容性。

### Decision：模块注册表第一版真源

**Context**: 当前前后端各维护一份模块矩阵。若第一阶段直接使用 ConfigBundle/数据库配置，会额外引入配置发布、权限、坏配置兜底和迁移成本；若只从 active path revision 派生，缺失默认能力、可绑定对象和配置诊断。

**Decision**: 第一版模块注册表采用后端代码常量 registry service，作为模块定义唯一真源；前端通过 API 读取 registry，并用 active/working path revision 覆盖具体标题、启停、顺序和绑定。

**Consequences**: 第一阶段无 migration，回滚简单；管理员暂时不能自由新增系统不认识的模块类型。后续如需要运营可配置模块定义，再把 registry 迁入 ConfigBundle/数据库并补发布治理。

### Decision：学习文章入口与商务礼仪层级

**Context**: 当前 `/admin/sales-trainer/articles` 直接以“商务技巧文章”为页面语义，并过滤 `sales_trainer_business_skills` 来源内容。未来学习内容会扩展到商务礼仪规范、销售技巧、客户常见质疑等多个专题；如果继续把商务礼仪作为文章入口，会误导后台管理模型。

**Decision**: 第一阶段保留 `/admin/sales-trainer/articles` route 和权限入口，但用户可见命名改为“学习文章/学习内容”。页面第一层展示学习专题/内容包卡片；点击“商务礼仪规范”后进入第二层，展示现有 7 个商务礼仪小单元和该训练包的导入、能力点、绑定、发布治理。具体章节编辑继续复用学习内容详情页，但必须从专题内提供清晰入口。

**Consequences**: 用户多了一层“专题选择”，但换来可扩展的信息架构；后续新增“销售技巧文章”“客户常见质疑文章”不会挤在商务礼仪页面里。第一阶段不改 route、不做 DB migration，通过 `LearningContent.source`、路径绑定和后端 registry 组合出专题视图；未来再补正式 content package 字段或配置治理。

### Decision：学习专题显示与阻塞策略

**Context**: 学习文章未来包含商务礼仪、销售技巧、客户常见质疑等专题，但这些专题不是每条新人训练路径都必须启用。如果前端预置展示，会造成未配置内容、测试数据或未来规划泄漏。用户也明确学习专题只是学习部分，展示的是现有小测正常得分，不是独立积分或计费体系，也不应阻塞下一关。

**Decision**: 学习专题必须由后端管理员配置后才显示。学习专题默认作为 optional learning evidence，具备小测 `total_score/max_score/passed` 和学习进度展示，但 `required=false`、`blocks_next=false`，不参与下一关解锁阻断，也不作为 TrainingJourney 必过项。

**Consequences**: 现有 TrainingJourney 当前把 active path modules 都标记为 `required=True`，后续实现需要引入“必修训练任务”和“可选学习专题/得分证据”的分层，或在 module registry 中新增 `required` / `blocks_next` / `score_display_policy` 元数据。第一阶段可先在计划和 registry 骨架中预留字段，避免直接改动 learner 主流程。

### Decision：学习专题得分来源

**Context**: 用户澄清“积分”是口误，不是计费、积分账户或学习激励体系，而是小单元通过考试后展示正常得分。

**Decision**: 第一阶段直接复用现有商务礼仪小测结果字段 `total_score / max_score / passed` 作为小单元得分展示来源。不新增独立积分、兑换、防刷、积分流水或单元满分配置。

**Consequences**: 实现复杂度低，历史小测记录可直接展示。若未来要支持“阅读得分”“AI 教练加分”或跨专题积分，再另起配置模型和 ADR。

### Decision：learner 前端学习专题布局

**Context**: 学习专题由管理员配置后才展示，且不阻塞下一关。如果把它插入主路径，学员容易理解成必须完成才能继续；如果完全独立成学习中心，又会削弱与新人训练路径的关系。

**Decision**: learner 前端采用主路径旁的“学习专题”区。必修训练任务仍以主路径展示；学习专题作为旁侧或下方区域展示进度、小测得分和继续学习入口，明确标注为非阻塞学习内容。

**Consequences**: 学员能看到学习专题与新人训练路径相关，但不会误以为它卡住下一关。实现上需要 TrainingJourney 或 learner path API 区分 `required_modules` 与 `learning_topics`，前端按区渲染。

### Decision：`business_skills` 承接方式

**Context**: 现有 `business_skills` 已经在 active path modules 中，且 `TrainingJourneyService` 当前会把 active path modules 标记为 `required=True`。这与“商务礼仪规范是非阻塞学习专题”的产品语义冲突。

**Decision**: 第一阶段采用投影拆分：后端继续兼容旧 `business_skills` 配置和绑定，但 learner/Journey API 输出时把它投影到 `learning_topics`，不计入 required modules、overall required completion 或下一关阻断。

**Consequences**: 不需要第一阶段迁移历史配置，但需要更新 read model 语义和前端渲染分区。达标验收和 Journey 分析也必须区分必修训练任务与学习专题证据，避免把学习专题未完成误判为训练未达标。

### Decision：学习专题配置源

**Context**: 如果继续把学习专题放在 active path modules 里，会把非阻塞学习内容和必修训练关卡混在同一个模型中；如果只靠 registry 默认启用，又违背“后端管理员配置后才显示”。

**Decision**: 新增独立学习专题配置源。学习专题配置声明 topic_key、标题、启用状态、展示顺序、绑定 learning_content、可选小单元配置、非阻塞策略、score display policy 和治理入口。learner API 只返回已启用且发布生效的学习专题。

**Consequences**: 语义更清晰，但范围从单纯 Phase 0-2 扩大，需要新增 service/API/契约测试和发布治理。第一阶段应优先复用现有 `SalesTrainerAssetRevision` 做 logical_id/revision，不急于新增业务表，降低 migration 风险。

### Decision：学习专题发布治理

**Context**: 学习专题是非阻塞内容，不应重新绑回新人路径发布；但保存即生效会绕过当前系统对配置发布、回滚、影响预览和审计的治理底线。

**Decision**: 学习专题配置独立发布。第一阶段优先复用 `SalesTrainerAssetRevision`：`resource_type="newcomer_learning_topics"`、`logical_id="newcomer_learning_topics_v1"`。保存生成 working revision，发布移动 active pointer，回滚只影响未来 learner 展示。

**Consequences**: 学习专题的发布/回滚不影响必修训练路径，风险边界更清楚。需要新增独立 publish preview、rollback preview、operation log action 和契约测试。

### Decision：旧 `business_skills` 迁移兼容

**Context**: 现有 `business_skills` 中已经沉淀了学习内容绑定、商务礼仪 7 个小单元、小测配置和 AI Coach 配置。完全不迁移会浪费已有配置；自动发布迁移又会绕过“管理员配置后才显示”的产品要求。

**Decision**: 采用“生成待发布草稿”。系统从现有 `business_skills` path module 读取可迁移配置，生成 `newcomer_learning_topics_v1` 的 working revision，默认不 active、不 learner 可见。管理员在学习专题配置页确认、调整并发布后，才显示“商务礼仪规范”。

**Consequences**: 兼容已有配置，同时保留人工确认和发布治理。实现需要迁移预览、重复生成幂等策略、草稿覆盖确认和 operation log，避免多次生成造成重复专题。

### Decision：学习专题后台第一版范围

**Context**: 长期会有销售技巧文章、客户常见质疑文章等专题，但第一版直接开放任意专题新增会引入 topic_key 冲突、内容绑定、空专题治理、校验和前端展示规则。

**Decision**: 第一版只支持“商务礼仪规范”专题，从现有 `business_skills` 生成 working revision 后进行编辑、发布和回滚。销售技巧文章、客户常见质疑文章只保留在术语和扩展设计中，不进入第一版 UI 或默认配置。

**Consequences**: 第一版范围可控，能先验证独立学习专题配置、发布治理和 learner 非阻塞展示。后续新增通用专题创建时，再扩展 topic template、topic_key 校验和空专题工作流。

### Decision：商务礼仪规范第一版编辑范围

**Context**: 如果学习专题后台只允许确认发布，管理员发现旧 `business_skills` 配置不合理时仍要回到路径配置里修，无法形成专题内闭环。用户确认第一版应允许真实治理。

**Decision**: 商务礼仪规范第一版允许编辑专题标题、绑定学习文章、7 个小单元、章节映射、能力点、小测题量、通过线、重测规则和题型权重。编辑保存到 learning topics working revision，发布后才 learner 可见。

**Consequences**: 第一版 UI 和校验范围扩大，但仍限定在商务礼仪规范，不开放任意新专题。需要复用现有 `BusinessEtiquetteTrainingUnitConfig` 校验，避免新旧配置规则分叉。

### Decision：商务礼仪 AI Coach 承接方式

**Context**: 现有 `business_skills` 已包含 AI Coach 配置和训练入口。学习专题不阻塞下一关，但 AI 功能仍必须满足 prompt/version/model/output contract 治理，不能静默用坏配置。

**Decision**: AI Coach 配置迁入“商务礼仪规范”学习专题，作为可选非阻塞训练能力。若 AI Coach disabled，专题可发布；若 AI Coach enabled，则 Prompt 绑定、模型配置和输出契约校验必须通过，否则学习专题发布失败。AI Coach 结果只作为学习证据和补练建议，不阻塞下一关，也不替代人工达标确认。

**Consequences**: 保留现有 AI Coach 投资，同时符合非阻塞学习专题语义。实现上需要把 `business_skills` 相关 AI Coach 读取从 path module 迁到 learning topic config，并保持旧记录 snapshot-first 展示。

### Decision：learner 路由兼容

**Context**: 旧 learner 路由 `/sales-trainer/business-skills` 已被现有入口、记录和用户习惯引用；直接切换到新 learning topic 路由会增加回归风险。但长期语义应从 business-skills 收敛到 learning-topics。

**Decision**: 保留旧 `/sales-trainer/business-skills` 路由，同时新增或内部映射 `/sales-trainer/learning-topics/business-etiquette`。两个入口读取同一个 published learning topic projection，旧路由作为兼容入口，新入口作为长期语义入口。

**Consequences**: 兼容风险最低。需要保证埋点、记录来源、面包屑和返回路径不会分裂；文案逐步使用“商务礼仪规范”而不是“商务技巧文章”。

## Final Requirements

* 后台保留 `/admin/sales-trainer/articles` route，但用户可见命名改为“学习文章/学习内容”。
* 学习文章后台第一层展示已配置学习专题；第一版只展示并治理“商务礼仪规范”。
* “商务礼仪规范”由现有 `business_skills` 生成待发布草稿，不自动 learner 可见。
* 学习专题配置独立于新人训练路径配置，独立保存、发布、回滚和审计。
* 学习专题第一阶段复用 `SalesTrainerAssetRevision`，避免新增业务表和 migration。
* 商务礼仪规范可编辑标题、绑定学习文章、7 个小单元、章节映射、能力点、小测题量、通过线、重测规则、题型权重和可选 AI Coach 配置。
* 学习专题在 learner 端位于主路径旁的“学习专题”区，不插入必修路径，不阻塞下一关。
* 小单元得分展示复用现有小测 `total_score / max_score / passed`。
* AI Coach 是可选非阻塞能力；enabled 时配置必须通过治理校验，disabled 时不影响专题发布。
* 旧 `/sales-trainer/business-skills` learner 路由保留，新 `/sales-trainer/learning-topics/business-etiquette` 读取同一专题投影。
* TrainingJourney、达标验收和 Journey 分析必须区分 required modules 与 learning topics，不把学习专题未完成算作训练未达标。

## Technical Approach

### 后端配置模型

新增 logical asset：

```text
resource_type = newcomer_learning_topics
logical_id = newcomer_learning_topics_v1
```

建议 payload 结构：

```json
{
  "schema_version": "newcomer_learning_topics_v1",
  "topics": [
    {
      "topic_key": "business_etiquette",
      "source_module_key": "business_skills",
      "enabled": true,
      "title": "商务礼仪规范",
      "description": "...",
      "order_index": 1,
      "learning_content_id": "...",
      "learning_units": [],
      "ai_coach": null,
      "required": false,
      "blocks_next": false,
      "score_display_policy": "quiz_attempt_score"
    }
  ]
}
```

### 后端服务边界

* `LearningTopicConfigService`：读取 active/working revision，保存草稿，发布，回滚，生成发布预览。
* `LearningTopicMigrationService`：从 active path revision 的 `business_skills` 生成 working revision，必须幂等。
* `LearningTopicProjectionService`：给 learner/Journey 输出已发布专题、学习进度、小测得分、AI Coach 状态。
* `TrainingJourneyService`：保留 required modules 聚合，同时新增或透传 `learning_topics`，不把 topic 纳入 `required` completion。

### 前端后台结构

```text
/admin/sales-trainer/articles
  学习文章/学习内容首页
  -> 商务礼仪规范专题卡

/admin/sales-trainer/articles/business-etiquette
  专题治理页
  -> 文章绑定
  -> 7 个小单元
  -> 小测规则
  -> AI Coach
  -> 保存草稿 / 发布预览 / 发布 / 回滚
```

旧入口保留：

```text
/admin/sales-trainer/articles/import
/admin/sales-trainer/articles/capabilities
```

但它们应作为“商务礼仪规范”专题内治理入口展示，而不是学习文章一级导航的平铺能力。

### Learner 结构

```text
新人训练路径主区
  -> PPT 讲解录音
  -> 金字塔演讲
  -> 后续真实对练

学习专题区
  -> 商务礼仪规范
     -> 7 个单元
     -> 小测得分
     -> 可选 AI Coach
```

## Implementation Plan

### PR1：文档与契约

* 新增 ADR：新人训练路径学习专题独立治理。
* 更新 `CONTEXT.md`：补充“学习专题”“非阻塞学习证据”“必修训练任务”。
* 更新 `docs/api-contract/sales-trainer.md`：新增 learning topics payload、发布 API、learner projection 契约。
* 验证：文档审阅，无代码行为变化。

### PR2：后端 learning topics 配置服务

* 新增 payload schema 和 service。
* 复用 `SalesTrainerAssetRevisionService` 管理 working/active revision。
* 新增 save、get、list revisions、publish preview、publish、rollback preview、rollback。
* 增加 operation log action。
* 测试：保存草稿、发布、回滚、非法 payload、权限拒绝、缺 reason/trace_id。

### PR3：旧 `business_skills` 生成草稿

* 从 active path revision 提取 `business_skills` 的文章绑定、learning_units、AI Coach 配置。
* 生成 `business_etiquette` topic working revision。
* 重复生成必须幂等；已有 working revision 时需要预览差异或要求确认覆盖。
* 测试：无 `business_skills`、已有 working、重复生成、非法旧配置、AI Coach disabled/enabled。

### PR4：后台学习文章 UI

* `/admin/sales-trainer/articles` 改为学习专题首页。
* 第一版只显示已生成/已发布的“商务礼仪规范”专题。
* 增加专题治理页，支持编辑标题、文章绑定、7 个单元、小测规则、AI Coach。
* 接入发布预览、发布、回滚。
* 测试：权限、空状态、草稿状态、发布状态、回滚入口、旧 URL 可访问。

### PR5：learner projection 与路由兼容

* learner/Journey API 增加 `learning_topics`。
* 从 required modules 中剥离 `business_skills` 的必过语义。
* 保留 `/sales-trainer/business-skills`，新增或映射 `/sales-trainer/learning-topics/business-etiquette`。
* 学习专题区展示进度、小测分数和 AI Coach 入口，不影响下一关。
* 测试：未发布不显示、发布后显示、未完成不锁关、旧路由可访问、新路由可访问。

### PR6：达标验收与分析修正

* readiness dossier 不把学习专题未完成算作未达标。
* Journey 分析区分 required module outcome 与 learning topic evidence。
* 训练记录详情保留商务礼仪小测和 AI Coach 证据。
* 测试：学习专题失败/未完成不影响整体 passed；小测得分可展示；AI Coach 不替代人工确认。

## Test Strategy

* 后端单测：payload 校验、revision 发布回滚、旧配置生成草稿、AI Coach 校验、非阻塞 completion。
* 后端集成测试：admin save/publish/rollback API、learner `learning_topics` projection、旧路由兼容。
* 前端测试：学习专题首页、商务礼仪规范治理页、发布预览、无权限、空状态、learner 分区渲染。
* 回归测试：新人路径必修模块 completion、达标验收、Journey 分析、训练记录详情、AI Coach session 旧记录。

## Rollout And Rollback

* 发布前：只上线后台草稿生成，不自动 active，不 learner 可见。
* 灰度：先生成 working revision，由管理员确认发布。
* 回滚：learning topics rollback 只移动 `newcomer_learning_topics_v1` active pointer，不影响新人路径 active revision。
* 紧急关闭：发布一个空 topics active revision 或禁用 `business_etiquette.enabled=false`。
* 旧路径兜底：`/sales-trainer/business-skills` 保留兼容入口，直到新 learning topic 路由稳定。

## Residual Risks

* 当前 `TrainingJourneyService` 把 active path modules 设为 `required=True`，实现时必须有 characterization tests 防止非阻塞专题继续影响 overall stage。
* 学习专题独立发布会增加一个配置面，需要权限、审计和错误提示完整，否则管理员会难以理解“路径已发布但专题未显示”。
* AI Coach 从 path module 迁到 learning topic 后，旧 session 的 snapshot 和新配置读取必须分清，不能从 latest 配置重建历史解释。
