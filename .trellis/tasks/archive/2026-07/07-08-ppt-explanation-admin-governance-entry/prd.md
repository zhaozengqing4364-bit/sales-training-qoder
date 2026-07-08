# brainstorm: 新人训练后台录音评测能力与管理治理

## Goal

把新人训练后台从“资源表和技术配置平铺”治理成“训练任务清晰、能力复用、资源可绑定、发布可回滚、记录可追溯”的管理系统。关键纠偏：`PPT 讲解录音` 不是最高层能力，它只是“录音上传 + 转写 + AI 评分/判断”能力下的一个训练场景；未来 `公司产品 Demo 讲解`、`金字塔演讲` 等应作为同类录音评测场景接入，而不是继续新增 PPT 专属分支。

## Corrected Domain Model

* **能力层：录音评测能力**
  * 上传录音、文件存储、ASR 转写、评分 Prompt 渲染、AI 判断、评分结果、失败重试、历史重评、审计。
  * 现有落点：`SalesTrainerAudioSubmission`、`SalesTrainerAudioTranscript`、`SalesTrainerAudioScoreResult`、`AudioSubmissionService`、`DeucateScoringService`。
  * 这一层不应出现 PPT、产品 Demo、商务礼仪等业务文案。
* **场景层：录音评测场景**
  * PPT 讲解、公司产品 Demo 讲解、金字塔演讲等。
  * 场景应声明：`scenario_key`、展示名、`purpose_key`、材料策略、评分标准策略、任务说明模板、完成规则、是否阻塞、发布状态、适用路径。
* **载体层：材料 / 任务资料**
  * PPT 文件、产品资料、Demo 脚本、示例音频、讲解要点等。
  * 材料是否必选、是否必须确认最新版本，是场景策略，不是 PPT 特判。
* **路径层：训练任务绑定**
  * 在新人训练路径中，把某个场景绑定到具体单元、材料版本、评分标准、完成规则、展示文案和发布版本。
  * `module_key` 应表达路径位置或兼容 key，不应独自承担场景身份、材料策略和评分策略。
* **学习专题层**
  * `商务礼仪` 只是学习专题之一，未来可扩展 `销售技巧`、`客户常见质疑`、`行业知识`。
  * 学习专题有得分展示，但不阻塞后续关卡；不要混入必修路径状态机。

## What I Already Know

* 用户确认：PPT 讲解录音只是“录音上传 + AI 判断”的一个载体/场景；未来公司产品 Demo 讲解也要通过录音上传和 AI 判断。
* 当前后台问题集中在三个层面：
  * 信息架构：16 个入口平铺，训练任务、资源资产、记录复核、系统诊断混在一层。
  * 领域耦合：PPT、`ppt_pitch`、`ppt_explanation` 被写进后端材料门禁、路径校验、前端模板和默认配置。
  * CRUD 治理：材料、路径、AI Coach、学习专题、AI 草稿等页面把新增、编辑、发布、回滚、诊断塞在一个页面。
* 现有底层录音链路是可复用的，不需要重写：
  * `SalesTrainerAudioSubmission.purpose` 是字符串，表结构没有限定 PPT。
  * 提交时会冻结材料快照、评分方案快照、任务简报和 path lineage。
  * 评分结果记录 `prompt_version`、`prompt_hash`、`deucate_model`、转写快照、维度分、错误码。
* 现有路径和前端配置仍限制新场景：
  * 后端 canonical module 只允许 `ppt_explanation`、`business_skills`、`elevator_pitch`、`realtime_roleplay*`。
  * 前端可编辑音频模块只允许 `ppt_explanation | elevator_pitch`。
  * 新建材料默认 `purpose="ppt_pitch"`，材料类型默认 `ppt_deck`。
  * PPT 材料门禁是 `_require_material_binding_for_ppt`，不是按场景策略判断。
* 权限和治理已有基础：
  * path config 有 working / publish / rollback / diagnostics。
  * 材料和评分标准已有 future-only revision。
  * 操作日志、录音重试、历史重评已有基础能力。
  * 但权限命名和契约有不一致：文档提到 `manage_materials`，代码里没有；评分标准高风险字段当前不完全落在 `manage_prompts`。

## Research References

* [`research/audio-evaluation-domain-audit.md`](research/audio-evaluation-domain-audit.md) — 底层录音评测链路可复用，但场景身份散落在 purpose、module_key、材料、评分标准和 path config 中。
* [`research/admin-ux-crud-route-plan.md`](research/admin-ux-crud-route-plan.md) — 后台应按工作台、训练任务、内容与能力库、学员记录与复核、系统治理重组。
* [`research/governance-permission-release-plan.md`](research/governance-permission-release-plan.md) — 发布、回滚、权限、审计、错误状态和验证计划必须闭环，不能只做入口。
* [`research/international-admin-patterns.md`](research/international-admin-patterns.md) — 成熟后台通常把列表、创建、编辑、导入、发布、诊断、记录拆成不同 surface。
* [`research/current-admin-ia-audit.md`](research/current-admin-ia-audit.md) — 当前导航、文案、记录入口和内部术语泄漏需要治理。
* [`research/current-crud-governance-audit.md`](research/current-crud-governance-audit.md) — God page 集中在 materials、paths、ai-coach、articles/capabilities、questions/drafts、business-etiquette。

## Code Evidence

* 通用录音提交链路：`backend/src/sales_trainer/services/audio_submission_service.py:213` 创建提交，校验 unit、active path、材料快照、评分方案快照。
* PPT 特判：`backend/src/sales_trainer/services/audio_submission_service.py:674` 只在 `resolved_purpose == "ppt_pitch"` 时强制材料绑定，并返回 PPT 专属错误。
* 通用评分链路：`backend/src/sales_trainer/services/audio_submission_service.py:796` 优先使用 submission snapshot 的评分 Prompt，再生成 `SalesTrainerAudioScoreResult`。
* 数据模型已基本通用：`backend/src/sales_trainer/models.py:454` 录音提交表有 `purpose`、材料快照、评分快照、任务快照；`backend/src/sales_trainer/models.py:664` 评分结果表记录 prompt/hash/model/transcript。
* 材料默认仍偏 PPT：`backend/src/sales_trainer/models.py:519` 和 `backend/src/sales_trainer/schemas.py:2837` 默认 `material_type="ppt_deck"`、`purpose="ppt_pitch"`。
* 路径 schema 无场景字段：`backend/src/sales_trainer/schemas.py:66` 与 `backend/src/sales_trainer/schemas.py:1365` 只有 `module_key`、`module_type`、`material_id`、`scoring_prompt_id` 等。
* module key 被写死：`backend/src/sales_trainer/services/path_config_models.py:27` 只允许固定 newcomer module keys，`backend/src/sales_trainer/services/path_config_models.py:369` 只把 `ppt_pitch` 推断成 `ppt_explanation`。
* 前端音频编辑被写死：`web/src/lib/sales-trainer/path-config-editing.ts:11` 只允许两个音频模块；`web/src/components/admin/sales-trainer/unit-module-template.ts:29` 只有 PPT 和金字塔模板。
* 后台导航平铺：`web/src/lib/sales-trainer/routes.ts:46` 定义 16 个同级入口，`web/src/lib/sales-trainer/routes.ts:450` 工作台只取每组第一个链接。

## Requirements

* 后台必须用用户语言组织：训练任务、内容与能力库、学员记录与复核、系统治理，而不是直接暴露内部 module key / purpose / Prompt / raw JSON。
* 新增或重构“录音评测场景”治理能力，PPT 讲解和公司产品 Demo 必须作为同级场景接入。
* 新场景不得靠散落硬编码接入；必须由中心化场景定义 / registry / schema 管理材料策略、评分策略、任务说明和完成规则。
* 管理员在训练任务页内应能完成上下文内配置：
  * 选择已有材料 / 评分标准 / 单元；
  * 快速新建最小必要对象；
  * 自动绑定到当前任务；
  * 保存 working revision；
  * 发布预览、发布、回滚；
  * 查看审计和错误状态。
* “删除”默认应是归档 / 下架 / 停用；不得硬删除会影响历史回放的数据。
* 学习专题应从 `商务技巧文章` 改为可扩展的 `学习专题`，商务礼仪只是一个专题，未来专题可二级进入单元和内容。
* 学习专题得分只展示，不阻塞后续关卡；required path 不依赖学习专题完成。
* 录音评测发布必须保持 future-only：发布、回滚只影响未来提交；历史录音、材料确认、评分结果继续按快照回放。
* 历史重评必须 preview/run 分离，append-only 增加评分结果，不覆盖旧评分。
* 权限必须以后端为准，前端 capability 只控制导航和按钮可见；无权限时不能继续请求敏感数据。
* 普通后台默认不得展示 `module_key`、`ppt_pitch`、`traceId`、`workflow`、`raw JSON`、`prompt hash`、原始枚举等内部字段；技术诊断放 advanced 区域。

## Technical Approach

### Recommended Approach A: 场景治理模型 + 分阶段后台治理

* 新增中心化 `AudioEvaluationScenario` 定义，先代码 registry，后续需要运营自定义时再持久化。
* path module 新增或演进 `scenario_key` / `assessment_scenario_key`，旧 `ppt_explanation -> ppt_pitch` 保持兼容。
* 用场景策略替换 PPT 特判：
  * `material_policy`: `required_confirmed` / `optional` / `none`
  * `prompt_policy`: 是否必填、允许 purpose、schema/rubric 要求
  * `runtime_shape`: `single_audio` / `duration_option_group`
  * `completion_rule`: `scored` / `passed` / `submitted`
* 新增后台 `训练任务` 入口，以任务场景为主线；`录音评测标准库`、`材料库`、`题库`、`考卷`、`学习专题` 作为可复用资产库。
* 新增 `公司产品 Demo 讲解` 场景时，只需要注册场景、创建/绑定材料和评分标准、配置路径发布，不再复制 PPT 专属页面逻辑。

优点：真正解决扩展性和耦合问题，兼容现有快照和发布机制。
缺点：需要改 schema、前后端 DTO、校验、测试，属于 P1 改造。

## Decision (ADR-lite)

**Context**: 用户确认 `PPT 讲解录音` 不是顶层能力，而是录音上传、转写、AI 判断能力下的一个训练场景；后续 `公司产品 Demo 讲解` 也要以同样能力接入。当前代码里 `ppt_pitch` / `ppt_explanation` 已散落在后端校验、路径模型、前端模板、材料默认值和后台导航里，继续硬编码会让每个新录音场景都重复改多处逻辑。

**Decision**: 采用 **Approach A：场景治理模型 + 分阶段后台治理**。先建立受控的录音评测场景 registry / schema，把 PPT 讲解、公司产品 Demo、金字塔演讲作为同级场景；再重组后台信息架构和 CRUD surface，逐步治理材料、评分标准、学习专题、AI Coach、题库草稿和记录中心。

**Consequences**:

* 这是 P1 级改造，需要同步后端 schema、前端 DTO/ViewModel、API contract、权限矩阵、测试和发布回滚说明。
* 短期不重写 ASR/AI 评分能力，不迁移历史提交；历史数据继续按 submission snapshot 回放。
* 旧 `ppt_explanation`、`ppt_pitch`、现有路径配置中心和旧路由必须兼容，不能让已有 PPT 讲解链路中断。
* 新增 `company_product_demo` 时必须通过场景策略接入，不能新增另一套产品 Demo 专属硬编码分支。

### Approach B: 先硬编码新增 product_demo

* 在 canonical module keys、前端模板、purpose options、材料门禁里新增 `company_product_demo`。
* 复用现有路径配置中心和音频绑定编辑器。

优点：最快能让产品 Demo 出现在后台。
缺点：复制 PPT 问题，下一个录音场景还要继续改多处分支；不建议作为主方案。

### Approach C: 只改后台导航和文案

* 改中文名、分组、入口说明，不改领域模型。

优点：风险低。
缺点：无法解决 product demo 可配置接入、PPT 特判、材料策略耦合；只能治标。

## Recommended Information Architecture

### 一级分组

* **新人训练工作台**
  * 风险、缺失配置、待发布、待复核、失败重试、近期发布。
* **训练任务**
  * PPT 讲解
  * 公司产品 Demo
  * 金字塔演讲
  * 商务礼仪学习
  * 后续销售技巧 / 客户异议专题
* **内容与能力库**
  * 材料库
  * 录音评测标准库
  * 题库
  * 小测 / 考卷
  * 学习专题
  * AI 教练策略库
* **学员记录与复核**
  * 训练记录中心
  * 录音记录 tab
  * 评分结果 tab
  * 达标复核
* **系统治理**
  * 高级路径编排 / 发布中心
  * 训练路径分析
  * 配置健康
  * 操作日志

### 命名调整

* `PPT 讲解录音` -> `PPT 讲解`，录音是完成方式。
* `商务技巧文章` / `学习文章` -> `学习专题`。
* `录音评分标准` -> `录音评测标准库`。
* `路径配置` -> `高级路径编排` 或 `发布中心`。
* `Journey 分析` -> `训练路径分析`。
* `学员录音`、`评分结果` 从一级导航降级到记录中心。

## CRUD Surface Plan

| 对象 | 列表页 | 新建 | 编辑 | 删除/下架 | 搜索/筛选 | 发布/回滚 | 诊断 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 录音评测场景 | `/training-tasks/audio` 或 `/training-tasks` | 新场景向导 / registry 配置 | 场景详情 tab | 停用未来展示 | 按状态/场景类型/缺配置 | 场景绑定随 path revision 发布 | 缺材料/缺评分/运行健康 |
| PPT 讲解 | `/training-tasks/ppt-explanation` | 选择/快速创建材料与标准 | 当前任务页内编辑绑定 | 停用模块，不硬删 | 记录和材料筛选 | preview -> publish -> rollback | advanced |
| 公司产品 Demo | `/training-tasks/company-product-demo` | 同 PPT，但材料类型可为产品资料/脚本 | 同上 | 同上 | 同上 | 同上 | 同上 |
| 材料库 | `/materials` | `/materials/new` 或任务页快速创建 shell | `/materials/[id]/edit` | 归档，active 引用阻断 | purpose/type/status | version publish/rollback | 文件和版本诊断 |
| 录音评测标准 | `/score-standards` | `/score-standards/new` | `/score-standards/[id]/edit` | 归档，active 引用阻断 | purpose/scenario/status | prompt revision publish/rollback | schema/rubric/prompt advanced |
| 学习专题 | `/articles` -> `/learning-topics` | 专题向导 | `/learning-topics/[key]` | 停用专题 | topic/status | 专题内容发布/回滚 | 导入/能力点诊断 |
| 题库/考卷 | 现有列表保留 | 独立新建页 | 独立编辑页 | 归档 | 分类/题型/状态 | 发布/回滚 | AI 草稿诊断 |
| AI 教练策略 | 策略总览 | 策略版本 | 分 tab 编辑 | 归档版本 | 模式/状态 | preview/publish/rollback | Prompt/模型 advanced |
| 训练记录 | 记录中心 | 无 | 复核/重评动作 | 不删历史 | 学员/场景/状态 | 重评 append-only | 快照/trace advanced |

Modal / Drawer / Page 规则：

* Modal：发布确认、归档确认、回滚确认、少于 4 字段的快速新建壳对象。
* Drawer：从当前任务选择材料/评分标准/题目，单条草稿审核，缺配置就地修复。
* Page：材料上传、评分标准编辑、AI 生成、导入、路径发布、回滚预览、记录详情、高风险策略。

## Implementation Plan

### Phase 0: 契约校正与现状保护

* 更新 PRD、API contract、领域词表：明确能力/场景/载体/路径绑定四层。
* 冻结当前行为测试清单：PPT 讲解、金字塔演讲、学习专题不阻塞、历史快照。
* 统一权限决策：
  * `manage_modules`: path binding / 场景进入路径。
  * `manage_content`: 材料、题库、文章、考卷。
  * `manage_prompts` 或新增 `manage_audio_scoring_policy`: 录音评测标准高风险字段。
  * `view_records`、`retry_jobs`、`regrade_history`、`view_logs`、`view_settings` 保持隔离。

### Phase 1: 录音评测场景 registry

* 新增后端中心定义：
  * `ppt_explanation`: purpose `ppt_pitch`，材料必须确认，单录音。
  * `company_product_demo`: purpose `company_product_demo`，材料必须确认，单录音。
  * `elevator_pitch`: purpose `elevator_pitch`，材料可选或按配置，多时长组。
* 替换 PPT 特判：
  * `_require_material_binding_for_ppt` 改为按 `scenario.material_policy` 判断。
  * material service 和 path publish validation 改为按场景策略判断。
  * 错误码从 PPT 专属演进为场景化错误，保留旧错误码兼容或错误详情里映射。
* 给 path module 加 `scenario_key` 或兼容投影，不破坏旧 payload。
* 添加 product demo 场景的后端单元/路径/上传/评分/记录测试。

### Phase 2: 前端场景投影与导航重组

* 新增 `AudioEvaluationScenarioViewModel`，由 API DTO 映射，不让 UI 直接读 raw purpose/module key。
* 把 `AudioEditableModuleKey = "ppt_explanation" | "elevator_pitch"` 改为 registry 驱动。
* 把 `unit-module-template.ts` 的 PPT/金字塔 switch 改为场景模板。
* 重组 `/admin/sales-trainer` 导航为五组；旧路由保留兼容。
* 工作台改为风险/待办/缺配置/待复核，而不是资源入口卡片。

### Phase 3: 训练任务页

* 新增 `/admin/sales-trainer/training-tasks` 任务列表。
* 新增 `/training-tasks/ppt-explanation` 与 `/training-tasks/company-product-demo`。
* 任务详情展示：
  * 场景状态、active/working path revision。
  * 绑定单元、材料、材料版本、评分标准、任务说明、完成规则。
  * 发布预览、发布、回滚入口。
  * 最近失败录音、待复核记录、审计入口。
* 缺配置时在当前页面提供选择/快速新建/自动绑定，不要求跳走再回来。

### Phase 4: 材料库与评分标准拆页

* 材料库拆为列表、新建、详情、版本上传、发布预览、历史。
* 评分标准默认展示评分维度、适用场景、版本状态；Prompt、output_schema、raw response 默认收起在 advanced。
* 任务页内只做快速创建 shell 和选择绑定；完整编辑走专页。
* 归档前检查 active/working path 引用，阻止破坏历史回放。

### Phase 5: 学习专题泛化

* 将 `business_skills` 的后台语言改为 `学习专题` / `商务礼仪专题`。
* 支持二级结构：专题列表 -> 专题详情 -> 单元/文章/题目/考卷。
* 明确专题得分展示不阻塞路径；`required=false`、`blocks_next=false`。
* 为销售技巧、客户常见质疑预留同 schema，不新增商务礼仪专属分支。

### Phase 6: AI Coach、题库草稿、记录中心治理

* AI Coach 拆成策略总览、交互规则、恢复话术、模型与 Prompt、发布历史、诊断。
* AI 出题拆成生成任务和草稿审核队列。
* 训练记录中心收束音频记录、评分结果、做题详情；技术字段放 advanced。
* 录音重试和历史重评只在有权限时显示，preview/run 分离。

### Phase 7: 验证与发布

* 后端覆盖：
  * 场景 registry；
  * product demo path publish；
  * 场景化材料策略；
  * submission snapshot；
  * scoring result；
  * training record；
  * RBAC；
  * audit；
  * rollback/regrade。
* 前端覆盖：
  * 导航分组；
  * 任务页 loading/empty/error/permission；
  * 选择绑定；
  * 快速新建；
  * 发布预览/发布/回滚；
  * 不展示内部字段。
* 发布策略：
  * feature flag 或隐藏入口灰度；
  * 旧路由兼容；
  * 无数据迁移或仅 additive schema；
  * 回滚时关闭新入口，底层历史快照不受影响。

## Acceptance Criteria

* [x] 管理员能从工作台进入 `训练任务`，看到 PPT 讲解和公司产品 Demo 是同级录音评测场景。
* [x] 管理员能配置公司产品 Demo：绑定单元、产品资料/脚本、评分标准、任务说明、完成规则，并发布到路径。
* [x] 学员进入产品 Demo 后能上传录音，系统完成转写和 AI 评分，训练记录能显示对应场景。
* [x] PPT 和 product demo 的材料要求都由场景策略控制，不再由 `ppt_pitch` 特判控制。
* [x] 新增、编辑、归档、查找、筛选、发布、回滚、审计、错误状态都有明确页面和后端校验。
* [x] 学习专题可支持商务礼仪以外的专题，专题得分展示但不阻塞后续关卡。
* [x] 历史录音和评分不被新发布覆盖；历史重评必须 append-only。
* [x] 权限不足时前端 fail-closed，后端仍对象级校验。
* [x] 普通后台不展示内部 key、raw JSON、trace、prompt hash、数据库主键和后端枚举。

## Implementation Closure Notes

2026-07-08 完成闭环范围：

* 后端新增 `AudioEvaluationScenario` registry，将 `ppt_explanation`、`company_product_demo`、`elevator_pitch` 统一到场景策略；`ppt_pitch` 保留兼容映射。
* 后端 `audio_submission_service`、`material_service`、`path_config_service`、`path_config_models`、`effective_audio_training_config` 均改为按场景材料策略判断，不再用 PPT 专属分支作为规则源。
* `NewcomerTrainingPathModuleConfig` / path config 增加 additive `scenario_key`；旧路径数据不迁移，新字段通过兼容投影补齐。
* 前端新增 `/admin/sales-trainer/training-tasks` 和场景详情页，管理员可在当前任务内选择单元、材料、录音评测标准，保存 working revision 并发布。
* 前端场景 registry 驱动模板、路径绑定、诊断修复链接和材料配置引导；公司产品 Demo 不再需要复制 PPT 页面逻辑。
* 后台文案从“商务技巧文章/学习文章”收敛为“学习专题/专题内容”；学习专题继续非阻塞。
* API contract、学习专题 ADR 和本 PRD 已同步治理边界、兼容策略、错误码和回滚语义。

## Definition of Done

* API contract、领域词表、必要 ADR 更新。
* 后端 unit/integration/contract tests 覆盖场景、权限、发布、回滚、审计、快照和错误。
* 前端 Vitest、类型检查、lint 覆盖导航、任务页、CRUD 状态和权限。
* 变更支持 feature flag 或旧路由回退。
* 发布说明明确风险、兼容性、回滚方式和未覆盖项。

## Out of Scope

* 不重写 ASR 或 Deucate 评分算法。
* 不迁移历史录音、历史评分、历史材料快照。
* 不把所有资源 CRUD 复制到训练任务页；任务页只做上下文内选择、快速创建和绑定，高风险编辑仍走专页。
* 不让学习专题阻塞主路径。
* 不直接开放管理员自定义任意场景表单；第一阶段先用受控 registry 保证稳定。

## Open Question

* 第一批实现范围是否按 `Phase 0-3` 执行：契约/权限校正、录音评测场景 registry、前端场景投影与导航重组、训练任务页？
