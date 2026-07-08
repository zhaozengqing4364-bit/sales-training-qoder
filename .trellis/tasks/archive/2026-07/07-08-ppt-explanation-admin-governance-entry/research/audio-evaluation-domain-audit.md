# Research: audio evaluation domain audit

- Query: 审查 `SalesTrainerAudioSubmission`、录音评分 Prompt、材料、路径配置、unit/module type/purpose，以及 `PPT/ppt_pitch/ppt_explanation/business_skills` 相关 API、服务、DB 模型和测试，判断当前后端是否已支持“多个录音评测场景”，并识别应抽象为 audio evaluation capability / scenario / task template 的边界。
- Scope: internal
- Date: 2026-07-08

## Findings

### 结论

当前后端已经有一条相对通用的“录音上传 -> 转写 -> AI 评分 -> 结果/记录/快照”执行链路，可以承载不止 PPT 的录音评分。例如现有 seed 和测试同时出现 `ppt_pitch` 与 `elevator_pitch`，运行时也把 `purpose` 当字符串传入评分 Prompt。

但当前还没有一等公民的“录音评测场景”或“录音任务模板”模型。场景身份被拆散在 `unit.config.audio.purpose`、`SalesTrainerAudioSubmission.purpose`、`SalesTrainerMaterial.purpose`、`SalesTrainerAudioScorePrompt.purpose`、`NewcomerPathModuleConfig.module_key`、`task_brief.scenario` 等位置。PPT 相关规则又通过 `ppt_pitch` / `ppt_explanation` 硬编码在服务、路径校验、seed、前端配置中心里。新增“公司产品 Demo 讲解”这类场景，按当前模型无法只靠后台配置完成，至少需要改代码放开 module key、材料策略、前端可编辑音频模块和 seed/校验逻辑。

正确的领域方向应是：`audio_scoring` 保持为底层执行能力；“PPT 讲解录音”“公司产品 Demo 讲解”“金字塔演讲”是录音评测场景；路径里发布给学员的一步是 task template / scenario binding，负责绑定场景、材料策略、评分 Prompt、任务简报、通过线和完成规则。

### Files Found

- `backend/src/sales_trainer/models.py` - 录音提交、材料、评分 Prompt、评分结果 ORM 模型。
- `backend/src/sales_trainer/schemas.py` - unit type、module type、path config、task brief、material binding、audio submission、score prompt DTO。
- `backend/src/sales_trainer/services/audio_submission_service.py` - 录音上传、快照冻结、转写、评分、重试、序列化主服务。
- `backend/src/sales_trainer/services/material_service.py` - 学员任务简报、材料绑定、材料确认、评分方案快照。
- `backend/src/sales_trainer/services/effective_audio_training_config.py` - active path revision 合并为录音运行时有效配置。
- `backend/src/sales_trainer/services/path_config_models.py` - 新人路径 module key/type 的 canonical 限定和 legacy 推断。
- `backend/src/sales_trainer/services/path_config_service.py` - path 发布前的音频模块、音频组模块、Prompt、材料校验。
- `backend/src/sales_trainer/services/deucate_scoring_service.py` - AI 录音评分 Prompt 渲染与结果解析。
- `backend/src/sales_trainer/api.py` - learner/admin 录音、材料、评分 Prompt、评分结果 API。
- `backend/src/sales_trainer/services/training_record_service.py` - 录音提交进入训练记录的序列化。
- `backend/scripts/seed_newcomer_training_path.py` - 新人路径默认模块、PPT 材料/Prompt/rubric、PPT 与金字塔演讲 E2E seed。
- `web/src/lib/sales-trainer/config-center-audio.ts` - 前端配置中心音频模块诊断。
- `web/src/lib/sales-trainer/path-config-editing.ts` - 前端可编辑音频模块与默认绑定。
- `backend/tests/unit/test_newcomer_training_path_audio_lineage.py` - active path、材料确认、Prompt 绑定、音频组等录音链路测试。
- `backend/tests/unit/test_newcomer_training_path_score_prompts.py` - 录音评分 Prompt future-only revision 与模板变量测试。
- `backend/tests/contract/test_sales_trainer_phase2_contract.py` - 录音提交、快照和训练记录契约测试。
- `docs/api-contract/sales-trainer.md` - sales trainer API 与路径配置契约。

### Code Patterns

#### 1. 通用录音评分执行链路已经存在

- `SalesTrainerAudioSubmission` 是相对通用的提交表：`unit_id` 可空，`purpose` 是字符串，记录文件元数据、`source_page`、材料确认版本、材料/评分方案/任务简报快照，以及 uploaded/transcribing/scoring/scored 等状态；没有把表名限定成 PPT。证据：`backend/src/sales_trainer/models.py:454` 到 `:516`。
- 评分结果表只绑定 submission 与 prompt，存 prompt 版本/hash、转写快照、总分、通过状态、维度分、原始响应和错误；没有单独 PPT 字段。证据：`backend/src/sales_trainer/models.py:664` 到 `:697`。
- learner 上传 API 接受 `purpose` 表单字段，默认 `general_audio_scoring`；metadata 注册 API 使用 `AudioSubmissionCreate`，同样允许任意短字符串 purpose。证据：`backend/src/sales_trainer/api.py:667` 到 `:735`、`backend/src/sales_trainer/schemas.py:2821` 到 `:2834`。
- `AudioSubmissionService.create_submission` 的主链路是：校验文件，加载已发布 `audio_scoring` unit，解析 active path config，校验路径访问，冻结材料/评分/任务简报快照，写入提交并可自动处理。证据：`backend/src/sales_trainer/services/audio_submission_service.py:213` 到 `:334`。
- 评分时先从提交快照取 Prompt，否则回退当前有效 config 的 `audio.scoring_prompt_id`；阈值先取快照，否则取当前有效 config；再调用通用 scoring service。证据：`backend/src/sales_trainer/services/audio_submission_service.py:796` 到 `:943`。
- `DeucateScoringService.score_audio` 只依赖 submission、prompt、transcript、unit_name 和 pass_threshold；Prompt 渲染支持 `{purpose}`、`{transcript}`、`{unit_name}`、`{scoring_standard}`，并解析统一 JSON 评分结果。证据：`backend/src/sales_trainer/services/deucate_scoring_service.py:136` 到 `:227`。
- 训练记录序列化把录音作为 `record_type="audio_submission"`，从提交快照投影 lineage、score、material snapshot、score scheme snapshot、task brief snapshot；这也是通用记录模型。证据：`backend/src/sales_trainer/services/training_record_service.py:469` 到 `:517`。

判断：底层 capability 已经基本成立，可以复用给“公司产品 Demo 讲解”。不要重写上传、ASR、评分、结果表和记录表。

#### 2. 场景身份不是一等模型，而是多处字段拼出来

- schema 只定义 `SalesTrainerUnitType = Literal["quiz", "audio_scoring"]`，这适合作为 capability 类型；路径 module type 有 `audio_scoring` 和 `audio_scoring_group`，也适合表达执行形态。证据：`backend/src/sales_trainer/schemas.py:11` 到 `:20`。
- `SalesTrainerPathConfig` 只有 `module_key`、`module_type`、`target_unit_id`、`material_id`、`material_version_id`、`scoring_prompt_id`、`capability_keys`、`runtime_binding` 等字段；没有 `scenario_key` 或 `task_template_key`。证据：`backend/src/sales_trainer/schemas.py:66` 到 `:95`。
- task brief 有 `purpose` 和 `scenario` 文案字段，但它是展示配置，不是可校验的场景身份。证据：`backend/src/sales_trainer/schemas.py:158` 到 `:168`。
- `SalesTrainerMaterial` 有 `purpose`，默认值却是 `ppt_pitch`；`SalesTrainerAudioScorePrompt` 也有 `purpose`，默认值是 `general_audio_scoring`。这两个 purpose 没有通过统一场景注册表关联。证据：`backend/src/sales_trainer/models.py:519` 到 `:552`、`:631` 到 `:661`。
- `SalesTrainerMaterialCreate` 默认 `material_type="ppt_deck"`、`purpose="ppt_pitch"`；这会让后台新建材料天然偏向 PPT。证据：`backend/src/sales_trainer/schemas.py:2837` 到 `:2844`。
- `AudioScorePromptCreate` / `Update` 只校验 `scoring_template` 包含 `{transcript}`，没有校验场景所需变量、rubric 维度或 output schema 与某个 scenario 的一致性。证据：`backend/src/sales_trainer/schemas.py:4504` 到 `:4542`。

判断：`purpose` 当前是自由字符串和 UI 筛选标签，不是受治理的 scenario identity。未来产品 Demo 如果只新增 `purpose="product_demo"`，服务可能能跑，但路径配置、材料门禁、后台入口、发布校验、报表归类和测试都会失去统一约束。

#### 3. path config 已能合并材料和 Prompt，但只支持单材料绑定和有限模块

- active path config 会覆盖 unit config 的 scoring prompt，并把 path 的 material_id/material_version_id 合成一个 required + confirmation_required 的材料 binding。证据：`backend/src/sales_trainer/services/effective_audio_training_config.py:43` 到 `:125`。
- `path_config_audio_refs.audio_refs_from_unit` 只读取第一个材料 binding 作为 path module 的 material ref。证据：`backend/src/sales_trainer/services/path_config_audio_refs.py:16` 到 `:45`。
- `NewcomerPathModuleConfig` 支持 `material_id`、`material_version_id`、`scoring_prompt_id`、`duration_options` 等绑定字段，说明 task template 的雏形已经在 path module 里。证据：`backend/src/sales_trainer/schemas.py:1365` 附近的 `NewcomerPathModuleConfig`（CodeGraph 已定位）。
- 但 `validate_path_payload_for_write` 把 module key 限死在 `ppt_explanation`、`business_skills`、`elevator_pitch`、`realtime_roleplay`、`realtime_roleplay_placeholder`，且 module_key 与 module_type 一一固定。证据：`backend/src/sales_trainer/services/path_config_models.py:27` 到 `:47`、`:81` 到 `:154`。
- legacy 推断把 `audio.purpose == "ppt_pitch"` 映射成 `ppt_explanation`，把 `pyramid_speech/elevator_pitch` 前缀映射成 `elevator_pitch`；未知 audio purpose 无法推断为合法模块。证据：`backend/src/sales_trainer/services/path_config_models.py:350` 到 `:384`。

判断：当前 path module 是“任务模板”的临时承载体，但 key 空间写死在新人路径 v1。新增产品 Demo 讲解无法作为新的 path module 或可治理场景进入 active path，除非改 canonical module key 代码和前端枚举。

#### 4. PPT 被硬编码成“必须有材料确认”的唯一特殊音频场景

- `AudioSubmissionService._require_material_binding_for_ppt` 只在 `resolved_purpose == "ppt_pitch"` 时要求材料 binding，错误码也是 `[PPT_MATERIAL_BINDING_REQUIRED]`。证据：`backend/src/sales_trainer/services/audio_submission_service.py:674` 到 `:698`。
- `validate_unit_material_and_brief_config` 同样只在 `purpose == "ppt_pitch"` 时要求 required + confirmation_required 材料绑定。证据：`backend/src/sales_trainer/services/material_service.py:950` 到 `:982`。
- path 发布校验 `_validate_audio_materials` 的 `requires_material` 条件是 `module.module_key == "ppt_explanation"` 或 `purpose == "ppt_pitch"` 或显式配置了 `module.material_id`。证据：`backend/src/sales_trainer/services/path_config_service.py:1220` 到 `:1278`。
- API 契约也写明 “PPT 演练门禁：`unit.config.audio.purpose="ppt_pitch"` 的任务必须绑定已发布材料，学员提交前必须确认当前要求版本”。证据：`docs/api-contract/sales-trainer.md:29` 到 `:31`。

判断：材料要求实际是 scenario policy，不应由 `ppt_pitch` 特判决定。产品 Demo 讲解大概率也需要公司产品资料/话术/演示脚本确认，当前没有配置化方式表达“这个新场景也必须确认材料”。

#### 5. 现有默认路径支持两个音频场景，但不是开放式场景模型

- seed 默认模块只有 `ppt_explanation`、`business_skills`、`elevator_pitch` 和 realtime placeholder；能力键也按这些模块写死。证据：`backend/scripts/seed_newcomer_training_path.py:101` 到 `:168`。
- PPT seed 新建材料时 `purpose="ppt_pitch"`，材料描述、版本标题、文件名全部写死为 PPT 讲解任务。证据：`backend/scripts/seed_newcomer_training_path.py:758` 到 `:823`。
- PPT E2E 提交使用 `AudioSubmissionCreate(... purpose="ppt_pitch", confirmed_material_version_id=...)`；金字塔演讲 E2E 提交使用 `purpose="elevator_pitch"` 且无材料确认。证据：`backend/scripts/seed_newcomer_training_path.py:2200` 到 `:2287`、`:2290` 到 `:2355`。
- seed 验证强制 `ppt_explanation` 的 audio purpose 是 `ppt_pitch`、Prompt purpose 是 `ppt_pitch`、rubric criterion 数量是 6、必须有 required + confirmation_required 材料绑定。证据：`backend/scripts/seed_newcomer_training_path.py:3765` 到 `:3824`。

判断：已有多个音频评分实例，但新增场景不是“插一条配置”级别，而是需要把 module key、purpose、材料政策、Prompt、rubric 和验证逻辑一起编码。

#### 6. `business_skills` 不是录音评测场景，不能拿来承载产品 Demo

- 后端规范明确 first version 只支持 `topic_key="business_etiquette"` 且来源 `source_module_key="business_skills"`；`required` 和 `blocks_next` 必须保持 false；required path 不能依赖 learning topic 完成。证据：`.trellis/spec/backend/sales-trainer-learning-topic-governance.md:39` 到 `:47`、`:65` 到 `:91`。
- API 默认模块矩阵也把 `business_skills` 标为 `"article_exam"` 和“兼容源模块”，不是录音评分。证据：`docs/api-contract/sales-trainer.md:247` 到 `:255`。
- path model 中 `business_skills` 固定对应 `"article_exam"`。证据：`backend/src/sales_trainer/services/path_config_models.py:36` 到 `:42`。

判断：未来“公司产品 Demo 讲解”应作为 audio evaluation scenario/task template 建模，不应复用或扩展 `business_skills` 语义。

#### 7. 前端配置中心也把音频治理限定在 PPT 与金字塔演讲

- `AudioModuleKey = "ppt_explanation" | "elevator_pitch"`，缺 Prompt 和材料时对两个音频模块都报缺材料；这和后端“金字塔演讲材料可选”的语义还有不一致风险。证据：`web/src/lib/sales-trainer/config-center-audio.ts:11` 到 `:55`。
- `AudioEditableModuleKey` 同样只允许 `ppt_explanation` 与 `elevator_pitch`；默认 order、moduleType、primaryActionLabel 写死。证据：`web/src/lib/sales-trainer/path-config-editing.ts:11` 到 `:63`。

判断：即使后端放开 product demo，当前后台配置中心也无法自然编辑一个新录音评测场景。

#### 8. API surface 是资源型，不是场景/任务模板型

- learner API 有 unit brief、材料文件、录音上传、录音列表/详情；admin API 有材料 CRUD、录音提交/重试、score results、score prompts 等资源接口。证据：`backend/src/sales_trainer/api.py:545` 到 `:587`、`:648` 到 `:735`、`:1364` 到 `:1529`，以及材料/Prompt admin 路由 `backend/src/sales_trainer/api.py:900` 到 `:1097`、`:1911` 到 `:2044`。
- `SalesTrainerUnitBrief` DTO 已经适合支撑任务页：返回 task brief、materials、score_scheme；契约要求学员 PPT 页不得写死 PPT 下载地址、评分维度、通过线或任务说明。证据：`docs/api-contract/sales-trainer.md:2198` 到 `:2256`。

判断：API 能支撑“某个录音任务页”的读取和绑定，但缺一个以 scenario/task template 为入口的后端聚合 API/DTO。若 UI 继续围绕 `/paths?module=ppt_explanation` 做专页，会把 PPT 误当最高层概念。

#### 9. 测试覆盖了当前 PPT/金字塔路径，但没有覆盖开放式多场景策略

- `test_newcomer_training_path_audio_lineage.py` 覆盖 active path 缺失 fail-closed、unit 不在 active path 拒绝、提交时冻结 path revision、使用 path audio bindings、材料确认必填/过期、unit brief fail-closed、audio group duration options 等。证据：`backend/tests/unit/test_newcomer_training_path_audio_lineage.py:167`、`:223`、`:319`、`:411`、`:529`、`:701`、`:1011` 等。
- score prompt 测试覆盖已发布 Prompt 编辑为 future revision，以及缺 `{transcript}` 的模板非法。证据：`backend/tests/unit/test_newcomer_training_path_score_prompts.py:27` 到 `:104`。
- contract 测试中的录音快照仍以 `purpose="ppt_pitch"` 为主。证据：`backend/tests/contract/test_sales_trainer_phase2_contract.py:448` 到 `:488`、`:630` 到 `:639`。
- 全仓测试搜索未发现 `product_demo`、`demo_explanation`、`audio_evaluation` 或 `task_template` 覆盖；只看到 realtime 的 `scenario_key` 和现有 `ppt_pitch/elevator_pitch`。证据：`rg -n "product_demo|demo_explanation|audio_evaluation|scenario_key|task_template|ppt_pitch|elevator_pitch" backend/tests/unit backend/tests/contract backend/tests/integration`。

判断：测试足以保护现有 PPT/金字塔链路，但不能证明新增录音评测场景可配置、可发布、可提交、可评分、可回放。

### Related Specs

- `.trellis/workflow.md` - 研究必须持久化到 task research 文件，不能只在对话里给结论。
- `.trellis/spec/backend/index.md:24` 到 `:29` - 后端不可中断用户体验、场景要模块化、关键路径可观测。
- `.trellis/spec/backend/directory-structure.md:26` 到 `:43`、`:102` 到 `:105` - `common/` 不放单场景逻辑；`sales_trainer` 是独立 REST domain。
- `backend/src/sales_trainer/AGENTS.md:29` 到 `:50` - API thin、service 管 workflow、材料/Prompt/路径是业务管理数据，不应散落魔法字符串；音频失败要可分类。
- `backend/src/sales_trainer/AGENTS.md:52` 到 `:59` - `sales_trainer` 是异步录音提交/评分，不是 realtime runtime。
- `.trellis/spec/backend/database-guidelines.md:278` 到 `:293` - 稳定 logical key 迁移时要保护历史提交，不重写旧 score snapshots。
- `.trellis/spec/backend/prompt-template-governance.md:120` 到 `:149`、`:171` 到 `:185` - AI 评分必须走受治理 Prompt/模型/JSON 结果，不可本地伪评分。
- `.trellis/spec/backend/sales-trainer-learning-topic-governance.md:39` 到 `:47` - `business_skills` 是学习专题兼容源，不能阻塞 required path。
- `docs/api-contract/sales-trainer.md:84` 到 `:88` - path config 是后台模块管理和 learner 首页 source of truth，前端兼容层不得把标签/排序/绑定当唯一真源。
- `docs/api-contract/sales-trainer.md:247` 到 `:270` - 当前默认模块矩阵和校验规则仍按 `ppt_explanation/elevator_pitch/business_skills` 固定。

### Target Model

建议把当前概念拆成三层：

1. **Audio Evaluation Capability（执行能力）**
   - 含义：上传录音、存储、ASR、Prompt 渲染、AI 评分、结果持久化、重试/重评、快照、训练记录。
   - 现有落点：`SalesTrainerAudioSubmission`、`SalesTrainerAudioTranscript`、`SalesTrainerAudioScoreResult`、`AudioSubmissionService`、`DeucateScoringService`。
   - 建议：保持通用，不要引入 PPT 或产品 Demo 文案。

2. **Audio Evaluation Scenario（业务场景）**
   - 含义：这段录音要评什么，例如 `ppt_explanation`、`company_product_demo`、`elevator_pitch`。
   - 应包含：`scenario_key`、展示名、适用角色/路径、默认 material policy、默认 score prompt policy、默认 task brief、默认 rubric/schema、completion rule、capability keys、是否支持 duration options、发布状态/版本。
   - 现有近似字段：`purpose`、`module_key`、`task_brief.scenario`，但都不能单独承担权威身份。

3. **Task Template / Path Binding（发布给学员的一步）**
   - 含义：在某条路径中，把一个 scenario 绑定到具体 unit、材料版本策略、评分 Prompt、任务文案、通过线和完成规则。
   - 现有落点：`NewcomerPathModuleConfig` + `SalesTrainerPathConfig` + active path revision。
   - 建议：新增或演进 `scenario_key` / `task_template_key`，让 `module_key` 只作为路径内位置或兼容 key，不再负责表达全部场景语义。

建议字段/策略：

- `scenario_key`: 稳定业务 key，例如 `ppt_explanation`、`company_product_demo_explanation`、`elevator_pitch`。
- `capability_type`: `audio_evaluation`，映射到底层 `unit_type="audio_scoring"`。
- `runtime_shape`: `single_audio` / `duration_option_group`，映射现有 `audio_scoring` / `audio_scoring_group`。
- `purpose_key`: 兼容当前 `purpose` 字段，默认可等于 scenario key；历史 `ppt_explanation -> ppt_pitch` 保持映射。
- `material_policy`: `required`、`optional`、`none`；是否 `confirmation_required`；允许材料类型；版本策略。
- `score_prompt_policy`: 是否必填、允许 prompt purpose、output schema/rubric 版本约束。
- `task_brief_template`: 学员可见任务说明。
- `lineage_policy`: 提交时必须冻结 scenario_key/task_template_key、path revision、material snapshot、score scheme snapshot、task brief snapshot。

### Migration / Compatibility Advice

1. **短期不迁移历史数据**
   - 保留 `SalesTrainerAudioSubmission.purpose="ppt_pitch"`、历史 snapshots 和 score results。
   - 历史记录继续通过 task brief snapshot/path lineage 回放，遵守“不重写旧 score snapshots”的数据库规范。

2. **先引入中心化 scenario registry / policy，不急于建表**
   - 在后端集中定义 `ppt_explanation -> purpose=ppt_pitch, material_policy=required_confirmed, runtime_shape=single_audio`。
   - 定义 `elevator_pitch -> purpose=elevator_pitch, material_policy=optional, runtime_shape=duration_option_group`。
   - 预留 `company_product_demo_explanation -> purpose=company_product_demo_explanation, material_policy=required_confirmed, runtime_shape=single_audio`。
   - 替换 `_require_material_binding_for_ppt` 和 `validate_unit_material_and_brief_config` 里的 PPT 特判为“按 scenario/material_policy 判断”。

3. **演进 path config，而不是扩大 PPT 页面**
   - 新增 `scenario_key` 或 `task_template_key` 时要注意 `SalesTrainerPathConfig` / `NewcomerPathModuleConfig` 当前 `extra="forbid"`，需要明确版本化 schema 或迁移字段。
   - 旧 `module_key="ppt_explanation"` 继续兼容映射到 `scenario_key="ppt_explanation"`。
   - 新产品 Demo 如果进入新人路径，应能新增一个 task template，而不是把它塞进 `ppt_explanation` 或 `business_skills`。

4. **后台入口应命名为“录音评测任务/场景治理”，PPT 是其中一个场景**
   - 第一阶段可以仍落地一个“PPT 讲解录音”聚焦页，但页面背后的领域模型和路由设计不要把 PPT 当最高层。
   - 更合理的信息架构是：录音评测任务列表 -> PPT 讲解录音详情；未来同级新增“公司产品 Demo 讲解”。
   - 详情页复用当前材料、评分 Prompt、path publish/revision、录音记录接口，缺资源时提供 in-flow 选择/快速创建/自动绑定。

5. **测试建议**
   - 参数化 material policy：`ppt_pitch` 与 `company_product_demo_explanation` 都要求材料确认，`elevator_pitch` 默认不要求。
   - 参数化 scenario registry：未知 scenario 发布失败；legacy `ppt_pitch` 仍兼容。
   - 新增产品 Demo 场景的最小闭环测试：path publish -> unit brief -> audio submission -> freeze snapshots -> score -> training record。
   - 前端配置中心测试应从 `AudioEditableModuleKey = "ppt_explanation" | "elevator_pitch"` 改成基于后端 scenario/task template 投影。

## Caveats / Not Found

- `python3 ./.trellis/scripts/task.py current --source` 返回 `Current task: (none)` / `Source: none`；本文件按用户显式指定的任务目录写入。
- 本次只读代码、规范和测试，未修改产品代码，未运行测试。
- `.codegraph/` 存在，已先使用 `codegraph explore` / `codegraph node` 理解链路；本地 `codegraph search` 子命令不可用，因此定位补充使用了 `rg` 和 `sed`。
- 未发现 `product_demo` / `company_product_demo` / `audio_evaluation` / `task_template` 作为 sales trainer 录音评测场景的现有后端模型或测试覆盖。
- 未浏览外部资料；External references: none。
