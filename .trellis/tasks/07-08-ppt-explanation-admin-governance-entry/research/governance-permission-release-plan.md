# Research: governance permission release plan

- Query: PPT 讲解录音后台治理入口的权限、发布、回滚、审计、CRUD 校验、错误状态与分阶段测试计划审查
- Scope: mixed
- Date: 2026-07-08

## Findings

### 0. 调研边界与 CodeGraph 状态

- 已按要求先执行当前任务检查与 CodeGraph 检查：`python3 ./.trellis/scripts/task.py current --source` 返回当前任务为空，当前工作树根目录未发现 `.codegraph/`，因此本轮按仓库规则跳过 CodeGraph，不自行创建索引。
- 本文只读代码与文档，未修改产品代码；唯一写入为本 research 文件。
- 结论聚焦 `/admin/sales-trainer/paths?module=ppt_explanation` 现有路径配置中心，以及拟新增或强化的 PPT 讲解录音治理入口。建议把新入口做成“任务场景治理页/聚合页”，不要新建一套独立数据真源。

### 1. Files found

#### 业务契约与规格

- `docs/api-contract/sales-trainer.md`：新人训练路径的 API、权限、PPT 材料门禁、path config 发布治理、future-only、dead-data diagnostics、发布/回滚预览和错误响应契约。关键产品边界在 `docs/api-contract/sales-trainer.md:13`，角色权限在 `docs/api-contract/sales-trainer.md:25`，capability projection 在 `docs/api-contract/sales-trainer.md:33`，PPT 门禁在 `docs/api-contract/sales-trainer.md:30`。
- `.trellis/spec/frontend/admin-console-patterns.md`：后台页面按用户意图拆分，列表/详情/编辑/导入/诊断不可混在一个 god page；治理入口应是单一任务面，复杂发布门禁需要稳定 URL。见 `.trellis/spec/frontend/admin-console-patterns.md:9`、`.trellis/spec/frontend/admin-console-patterns.md:30`、`.trellis/spec/frontend/admin-console-patterns.md:85`。
- `.trellis/spec/backend/error-handling.md`：业务失败应返回统一 envelope 与 `trace_id`，前端不能暴露栈；需区分 `error` 与 `fallback` 路径。见 `.trellis/spec/backend/error-handling.md:9`、`.trellis/spec/backend/error-handling.md:48`、`.trellis/spec/backend/error-handling.md:74`。
- `.trellis/spec/backend/logging-guidelines.md`：结构化日志自动带 `trace_id`，不得泄露 token/cookie/email 等敏感字段，admin 日志面只暴露 allowlist。见 `.trellis/spec/backend/logging-guidelines.md:9`、`.trellis/spec/backend/logging-guidelines.md:69`。
- `.trellis/spec/backend/prompt-template-governance.md`：平台 PromptTemplate 的治理边界；PPT 录音评分标准不是平台 PromptTemplate，但“高风险 prompt 字段必须可审计、可预览、可回滚”的原则一致。见 `.trellis/spec/backend/prompt-template-governance.md:42`、`.trellis/spec/backend/prompt-template-governance.md:52`。
- `.trellis/spec/backend/business-rule-configs.md`：可调阈值/策略必须进入统一 business-rule 生命周期，不应散落在 env、页面常量或服务本地字典。见 `.trellis/spec/backend/business-rule-configs.md:7`、`.trellis/spec/backend/business-rule-configs.md:154`。
- `.trellis/spec/backend/quality-guidelines.md`：测试结构、ruff/mypy、contract 测试要求；API shape 改动必须同步 contract。见 `.trellis/spec/backend/quality-guidelines.md:15`、`.trellis/spec/backend/quality-guidelines.md:105`、`.trellis/spec/backend/quality-guidelines.md:126`。
- `AGENTS.md`、`backend/AGENTS.md`、`backend/src/sales_trainer/AGENTS.md`、`web/src/app/admin/sales-trainer/AGENTS.md`：仓库要求 CodeGraph first、上下文内完成、后端权限为准、发布/回滚/归档/评分/上传/人工修正必须留操作日志，前端必须通过 API facade 与 capability gating。

#### 后端实现

- `backend/src/sales_trainer/permissions.py`：销售训练后台能力权威，定义 `manage_content`、`manage_modules`、`manage_prompts`、`view_records`、`retry_jobs`、`regrade_history`、`view_logs`、`view_settings` 等能力。能力键在 `backend/src/sales_trainer/permissions.py:23`，模块管理在 `backend/src/sales_trainer/permissions.py:98`，Prompt 管理在 `backend/src/sales_trainer/permissions.py:103`，记录查看和团队范围在 `backend/src/sales_trainer/permissions.py:108`、`backend/src/sales_trainer/permissions.py:154`，capability projection 在 `backend/src/sales_trainer/permissions.py:177`。
- `backend/src/sales_trainer/api.py`：admin/learner 主路由；capabilities、材料 CRUD、评分标准 CRUD、录音上传、录音列表、重试、设置、操作日志都在这里。capability endpoint 在 `backend/src/sales_trainer/api.py:398`，录音 upload-url/upload/register 在 `backend/src/sales_trainer/api.py:648`、`backend/src/sales_trainer/api.py:667`、`backend/src/sales_trainer/api.py:709`，材料 CRUD 在 `backend/src/sales_trainer/api.py:900`、评分标准 CRUD 在 `backend/src/sales_trainer/api.py:1910`，操作日志查询在 `backend/src/sales_trainer/api.py:2084`。
- `backend/src/sales_trainer/path_config_api.py`：`/api/v1/admin/newcomer-training/path-config*` 读写、发布预览、发布、回滚、dead-data diagnostics 的 API 层。保存与字段级 RBAC 在 `backend/src/sales_trainer/path_config_api.py:109`，发布预览/发布在 `backend/src/sales_trainer/path_config_api.py:169`、`backend/src/sales_trainer/path_config_api.py:204`，回滚预览/回滚在 `backend/src/sales_trainer/path_config_api.py:536`、`backend/src/sales_trainer/path_config_api.py:578`。
- `backend/src/sales_trainer/services/path_config_service.py`：新人训练路径 active/working revision 的 source of truth。保存 working revision 在 `backend/src/sales_trainer/services/path_config_service.py:144`，发布在 `backend/src/sales_trainer/services/path_config_service.py:198`，发布预览在 `backend/src/sales_trainer/services/path_config_service.py:232`，回滚在 `backend/src/sales_trainer/services/path_config_service.py:316`，发布校验准备在 `backend/src/sales_trainer/services/path_config_service.py:516`，音频 prompt/material 校验在 `backend/src/sales_trainer/services/path_config_service.py:1199`、`backend/src/sales_trainer/services/path_config_service.py:1220`。
- `backend/src/sales_trainer/services/asset_revision_service.py`：通用 asset revision 指针服务；working/published/active/rollback 语义已实现。保存 working 在 `backend/src/sales_trainer/services/asset_revision_service.py:38`，active pointer 读取在 `backend/src/sales_trainer/services/asset_revision_service.py:133`，rollback 只允许 published revision 在 `backend/src/sales_trainer/services/asset_revision_service.py:175`，publish working 在 `backend/src/sales_trainer/services/asset_revision_service.py:209`。
- `backend/src/sales_trainer/services/material_service.py` 与 `material_publish_workflow.py`：材料、版本、发布、归档、回滚、历史文件访问和提交快照冻结。材料创建/更新/归档/版本创建在 `backend/src/sales_trainer/services/material_service.py:118`、`:151`、`:186`、`:216`，版本回滚预览/执行在 `backend/src/sales_trainer/services/material_service.py:289`、`:325`，提交快照冻结在 `backend/src/sales_trainer/services/material_service.py:558`，发布版本 future-only 操作在 `backend/src/sales_trainer/services/material_publish_workflow.py:25`。
- `backend/src/sales_trainer/services/prompt_service.py`、`prompt_revision_service.py`、`prompt_revision_payloads.py`：录音评分标准的 future revision、发布、回滚、high-risk change class。已发布 prompt 的更新保存为 future revision 在 `backend/src/sales_trainer/services/prompt_service.py:144`，发布在 `backend/src/sales_trainer/services/prompt_service.py:190`，working revision 保存/发布/回滚预览/回滚在 `backend/src/sales_trainer/services/prompt_revision_service.py:40`、`:90`、`:208`、`:252`，高风险字段在 `backend/src/sales_trainer/services/prompt_revision_payloads.py:13`。
- `backend/src/sales_trainer/services/audio_submission_service.py`：录音上传、active path 校验、材料确认、快照冻结、ASR、AI 评分、重试状态。创建提交在 `backend/src/sales_trainer/services/audio_submission_service.py:213`，active path/effective config 校验在 `backend/src/sales_trainer/services/audio_submission_service.py:237`，材料快照冻结在 `backend/src/sales_trainer/services/audio_submission_service.py:260`，submission 创建与审计在 `backend/src/sales_trainer/services/audio_submission_service.py:287`、`:309`，序列化 lineage 在 `backend/src/sales_trainer/services/audio_submission_service.py:623`，PPT 材料绑定强校验在 `backend/src/sales_trainer/services/audio_submission_service.py:674`，ASR/评分状态机在 `backend/src/sales_trainer/services/audio_submission_service.py:711`、`:796`。
- `backend/src/sales_trainer/services/deucate_scoring_service.py`、`transcription_service.py`：录音 AI 判断能力依赖 DashScope/Paraformer 转写与 Deucate 评分。Deucate 配置/超时/请求/响应错误在 `backend/src/sales_trainer/services/deucate_scoring_service.py:58`，评分调用、prompt hash、JSON 校验在 `backend/src/sales_trainer/services/deucate_scoring_service.py:136`、`:157`、`:171`。
- `backend/src/sales_trainer/regrade_api.py`：历史重评的 preview/run API，权限来自 `regrade_history`，按部门 scope 过滤。见 `backend/src/sales_trainer/regrade_api.py:57`、`backend/src/sales_trainer/regrade_api.py:118`。
- `backend/src/sales_trainer/services/operation_log_service.py`：统一操作日志写入和查询，记录 actor、role、action、target、request_id、ip/user_agent、metadata。见 `backend/src/sales_trainer/services/operation_log_service.py:16`、`:43`。

#### 前端实现

- `web/src/lib/api/domains/sales-trainer.ts`：前端销售训练 API facade；capabilities、材料、评分标准、录音、记录等都通过这里调用。capability 方法在 `web/src/lib/api/domains/sales-trainer.ts:300`，材料 CRUD/upload/publish 在 `web/src/lib/api/domains/sales-trainer.ts:348`、`:400`、`:450`，录音列表/重试在 `web/src/lib/api/domains/sales-trainer.ts:540`、`:561`，评分标准 CRUD 在 `web/src/lib/api/domains/sales-trainer.ts:579`。
- `web/src/lib/api/domains/newcomer-training.ts`：path config/revision/publish/rollback API facade 所在域；现有路径配置中心通过 `api.admin.newcomerTraining` 使用。
- `web/src/lib/sales-trainer/routes.ts`：admin 路由与能力映射；`scoreStandards`、`materials`、`paths` 已在内容/模块能力下暴露。路由定义在 `web/src/lib/sales-trainer/routes.ts:46`，capability nav 在 `web/src/lib/sales-trainer/routes.ts:172`，路径访问判断在 `web/src/lib/sales-trainer/routes.ts:272`。
- `web/src/lib/sales-trainer/use-admin-route-access.ts`：页面进入前先取 capability，失败或无权限时 fail-closed，避免继续请求受限数据。见 `web/src/lib/sales-trainer/use-admin-route-access.ts:20`、`:54`。
- `web/src/app/admin/sales-trainer/paths/page.tsx`：现有新人训练路径配置中心；支持 `?module=ppt_explanation` 聚焦 PPT 模块，并渲染音频绑定编辑器。见 `web/src/app/admin/sales-trainer/paths/page.tsx:22`、`:44`、`:65`、`:121`。
- `web/src/app/admin/sales-trainer/paths/use-path-config-center-workflow.ts`：保存 working revision、发布、回滚的前端工作流；变更说明必填，成功文案明确只影响后续学员。见 `web/src/app/admin/sales-trainer/paths/use-path-config-center-workflow.ts:109`、`:136`、`:159`。
- `web/src/app/admin/sales-trainer/paths/page-data.ts`：路径配置中心一次性拉取 units、pathConfig、revisions、papers、materials、scorePrompts、settings 与 publishPreview。见 `web/src/app/admin/sales-trainer/paths/page-data.ts:32`。
- `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx`：音频模块只允许选择已发布材料和已发布评分标准，并链接到材料库/评分标准页。见 `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:33`、`:34`、`:37`、`:48`。
- `web/src/lib/sales-trainer/path-config-editing.ts`：`ppt_explanation` 与 `elevator_pitch` 的绑定编辑模型；PPT 默认 `module_type="audio_scoring"`、`completion_rule="passed"`、主操作“上传录音”。见 `web/src/lib/sales-trainer/path-config-editing.ts:25`、`:77`、`:139`。
- `web/src/lib/sales-trainer/config-center.ts`、`config-center-audio.ts`：前端治理模型与音频绑定诊断；对缺失评分标准/材料生成 issue。见 `web/src/lib/sales-trainer/config-center.ts:54`、`:173`、`:276`、`:338`，以及 `web/src/lib/sales-trainer/config-center-audio.ts:19`、`:58`。

#### 后端 tests

- `backend/tests/integration/test_newcomer_training_path_config_api.py`：覆盖 path config publish/rollback、diagnostics、future-only 和 learner active revision。发布回滚测试从 `backend/tests/integration/test_newcomer_training_path_config_api.py:220` 开始，诊断字段断言在 `backend/tests/integration/test_newcomer_training_path_config_api.py:246`。
- `backend/tests/integration/test_newcomer_training_path_rbac_api.py`：覆盖 content_admin、training_manager/support、ops、learner 的设置/记录/日志访问边界。见 `backend/tests/integration/test_newcomer_training_path_rbac_api.py:40`。
- `backend/tests/unit/test_newcomer_training_path_material_governance.py` 与 `backend/tests/integration/test_newcomer_training_path_material_api.py`：覆盖材料发布 future-only 审计、元数据变更 before/after、active path 引用时禁止归档、材料版本回滚预览与文件上传。见 `backend/tests/unit/test_newcomer_training_path_material_governance.py:52`、`:101`、`:164`，以及 `backend/tests/integration/test_newcomer_training_path_material_api.py:177`、`:252`、`:392`。
- `backend/tests/integration/test_newcomer_training_path_score_prompt_api.py`：覆盖评分标准 contract 校验、已发布 prompt 更新为 future revision、revision 列表/预览/回滚和审计。见 `backend/tests/integration/test_newcomer_training_path_score_prompt_api.py:30`、`:64`、`:129`。
- `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`：覆盖无 active path fail-closed、active path scope、提交时冻结 path revision lineage、材料确认与评分标准快照。见 `backend/tests/unit/test_newcomer_training_path_audio_lineage.py:166`、`:318`、`:410`。
- `backend/tests/integration/test_newcomer_training_path_audio_regrade_api.py`：覆盖历史录音重评必须显式 preview/run、按部门 scope、content_admin 禁止、原 score_result 保留、append-only 审计。见 `backend/tests/integration/test_newcomer_training_path_audio_regrade_api.py:75`、`:205`、`:252`。
- `backend/tests/unit/test_newcomer_training_path_audit_logs.py`：覆盖 unit/paper 的 before/after、publish/archive 状态转换日志。见 `backend/tests/unit/test_newcomer_training_path_audit_logs.py:73`、`:146`、`:187`。

#### 前端 tests

- `web/src/app/admin/sales-trainer/paths/page.test.tsx`：覆盖路径配置中心渲染、诊断、保存 working revision、变更说明必填、发布、预览失败、回滚、capability fail-closed。见 `web/src/app/admin/sales-trainer/paths/page.test.tsx:128`、`:236`、`:265`、`:285`、`:296`、`:311`、`:334`。
- `web/src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx`：覆盖 `?module=ppt_explanation` 下选择已发布材料和评分标准后保存到 path working revision。见 `web/src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx:119`。
- `web/src/lib/api/sales-trainer.test.ts`：覆盖 API facade，包括 completion_rule 兼容映射、音频上传不增加固定时长字段、presigned upload registration。见 `web/src/lib/api/sales-trainer.test.ts:23`、`:148`、`:188`。

### 2. 现状判断：PPT 治理入口应聚合已有真源，不应重建模型

现有系统已经具备 PPT 讲解录音治理所需的三类真源：

1. 任务场景与模块绑定：`newcomer_training_path_v1` active/working revision，管理 `ppt_explanation` 的 `target_unit_id`、`material_id`、`material_version_id`、`scoring_prompt_id`、完成规则、展示文案和 future-only 发布指针。保存/发布/回滚链路在 `path_config_service` 与 `asset_revision_service` 中已成型。
2. 材料文件与版本：`SalesTrainerMaterial` + `SalesTrainerMaterialVersion` 管理 PPT/附件材料，发布只移动当前版本指针，历史提交通过冻结快照和确认版本读取。
3. AI 判断能力：`SalesTrainerAudioScorePrompt` + `SalesTrainerAssetRevision` 管理录音评分标准；录音提交时冻结评分方案快照，AI 评分使用提交时快照而不是 latest prompt。

因此新入口的正确产品形态不是“PPT CRUD 大表”，而是“PPT 讲解录音任务场景治理页”：

- 首页任务：一屏看清当前 PPT 讲解录音是否可发布、绑定了哪个材料版本、哪个评分标准版本、当前 active revision/working revision、ASR/AI 评分健康、未发布变更、发布/回滚入口、审计入口。
- 写操作：仍调用现有 `path-config`、`materials`、`audio-score-prompts` API；如果后续新增聚合 API，也应是读模型或薄编排，不应绕开现有 service。
- 数据语义：所有发布/回滚只影响未来学员；历史 submission/result/record 读取创建时 snapshot 或显式 `legacy_snapshot_only`，不得从最新配置反推。

### 3. 录音上传 AI 判断能力的版本发布与兼容方案

#### 3.1 当前链路

录音判断链路是“上传 -> 冻结上下文 -> ASR 转写 -> Deucate 评分 -> score_result”：

- learner 上传前端支持后端中转和 presigned registration，表单字段包括 `unit_id`、`purpose`、`source_page`、`confirmed_material_version_id`、`auto_process`，见 `web/src/lib/api/domains/sales-trainer.ts:87`、`:169`、`:180`。
- 后端创建 submission 时先验证音频格式/大小、unit、active path、learner 是否可访问该 unit；PPT 场景必须有材料绑定并确认版本，见 `backend/src/sales_trainer/services/audio_submission_service.py:213`、`:237`、`:260`、`:674`。
- `freeze_submission_snapshots` 冻结材料、评分方案和 task brief；提交序列化时返回 `path_revision_id`、`path_revision_no`、`module_key`、`legacy_snapshot_only` 等 lineage，见 `backend/src/sales_trainer/services/material_service.py:558`、`backend/src/sales_trainer/services/audio_submission_service.py:623`。
- 评分时优先从 `score_scheme_snapshot` 读取 prompt；如果没有 snapshot 才退回当前 prompt row，并标记来源。见 `backend/src/sales_trainer/services/audio_submission_service.py:796`、`:823`。
- Deucate 评分保存 `prompt_id`、`prompt_version`、`prompt_hash`、`deucate_model`、`transcript_snapshot`，用于审计与历史复盘。见 `backend/src/sales_trainer/services/audio_submission_service.py:900`。

#### 3.2 版本发布原则

PPT 录音 AI 判断能力的发布不应只是“发布一个 prompt”。完整发布包至少包含：

- Path revision：`ppt_explanation` 模块绑定哪个 unit、材料、材料版本、评分标准、任务简报和完成规则。
- Material version：学员必须确认的当前 PPT/材料版本。
- Audio score prompt revision：评分标准正文、rubric、output schema、通过线或 learner_rubric 中的高风险评分字段。
- Runtime/provider config：ASR 模式、ASR 模型、Deucate endpoint/model/timeout 是否配置。当前这部分通过 settings/环境暴露，不属于 path revision；入口只能显示健康状态和错误，不应把 provider secret 或 runtime 参数写入 path snapshot。

发布语义建议：

- 保存：生成 working revision，不影响 learner。
- 发布：预览通过后移动 active pointer，只影响未来 learner 的路径展示、材料确认、录音提交和评分快照。
- 回滚：只移动 active pointer 或 current material/prompt pointer，未来生效；不得回写历史 submission/result。
- 历史兼容：历史录音默认继续展示提交时 snapshot；需要按新版评分重判时，必须走 regrade preview/run，append-only 增加新 score_result，不删除旧 score_result。

#### 3.3 兼容细节与必要展示字段

治理页必须展示并在 API DTO 中有可追踪字段：

- 当前 active path revision：`active_revision_id`、`active_revision_no`、`source`、`fallback_reason`、`legacy_snapshot_only`。
- Working revision：`working_revision_id`、`working_revision_no`、`has_unpublished_revision`。
- PPT 绑定：`module_key=ppt_explanation`、`module_type=audio_scoring`、`target_unit_id`、`material_id`、`material_version_id`、`scoring_prompt_id`。
- 材料状态：material `published/archived/draft`，current_version 是否存在且 published，是否与 path 绑定的 locked/current version 一致。
- 评分标准状态：prompt 是否 published，version/revision 是否 active，是否存在 working revision，是否有高风险字段变更。
- 录音历史：submission 的 `path_revision_id/no`、`module_key`、`material_snapshot`、`score_scheme_snapshot`、`score_result.prompt_hash`、`score_result.legacy_snapshot_only`。
- 运行健康：ASR mode/model、DashScope configured、Deucate configured/model。前端现有运维诊断已读取 settings 并展示 ASR/AI 评分服务，见 `web/src/lib/sales-trainer/config-center.ts:276`。

如果治理入口新增“发布新版 AI 判断能力”按钮，应分清三种动作：

- 修改 path 绑定到另一个已发布评分标准：`PUT /admin/newcomer-training/path-config` -> `publish/preview` -> `publish`。
- 修改评分标准正文/rubric/schema：`PUT /admin/sales-trainer/audio-score-prompts/{id}` 保存 working prompt revision -> `POST /publish` -> 再按需更新 path 绑定或继续使用同一 prompt active revision。
- 对历史录音使用新版评分重判：`POST /admin/newcomer-training/regrades/audio-submissions/{id}/preview` -> `run`，必须 reason、trace_id、append-only。

不得把上述三者合成一个“发布后自动重判历史”的按钮。

### 4. 任务场景如何管理

PPT 讲解录音的“任务场景”建议定义为：

- 稳定业务键：`path_key=newcomer_training_path_v1` + `module_key=ppt_explanation`。
- 模块类型：`audio_scoring`。
- 运行目标：`target_unit_id` 指向已发布 `audio_scoring` unit。
- 学员动作：`primary_action_label="上传录音"`。
- 业务目的：`purpose=ppt_pitch`。
- 必要绑定：已发布材料、材料当前/锁定版本、已发布录音评分标准。
- 学员提交快照：材料、任务简报、评分方案、path revision lineage。

管理方式：

1. `path-config` 是任务场景真源。新增治理页应先读取 `GET /api/v1/admin/newcomer-training/path-config`，聚焦 `modules[].module_key === "ppt_explanation"`。
2. 材料和评分标准是可绑定资产。治理页只筛选 `purpose=ppt_pitch` 且 `status=published` 的候选项，不应让草稿/归档资产被绑定。现有前端音频绑定编辑器已经这样过滤，见 `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:34`、`:37`。
3. “缺配置”必须上下文内完成。当前编辑器给出链接去材料库/评分标准页；如果要满足更强的 in-flow completion，应在 PPT 治理页内提供轻量抽屉：
   - 选择已有已发布材料/评分标准；
   - 快速新建材料 shell + 上传版本；
   - 快速创建评分标准 draft 或从模板复制；
   - 自动回填当前模块绑定；
   - 保存为 working revision；
   - 发布前预览影响范围。
4. 快速新建的边界：材料上传可以是抽屉或 dedicated upload flow；完整 prompt/rubric/schema 编辑属于高风险长表单，建议跳到评分标准详情页或专门编辑页，只在治理页做“创建最小草稿 + 继续编辑/发布”的引导。
5. 不建议把 task scenario 独立存表。现有 `SalesTrainerAssetRevision` 已承担 path revision；额外存表会制造双真源，增加发布/回滚与历史快照冲突。

### 5. 哪些 API/权限需要统一

#### 5.1 Capability projection 是前端唯一导航权威，但不是授权

前端必须继续使用 `GET /api/v1/admin/sales-trainer/capabilities` 控制导航与页面加载；后端 API 仍逐个校验。现有路径页在 capability 失败时不会继续请求 path config，见 `web/src/app/admin/sales-trainer/paths/page.test.tsx:334`，符合 fail-closed。

新增 PPT 入口如果为 `/admin/sales-trainer/tasks/ppt-explanation` 或 `/admin/sales-trainer/ppt-explanation`：

- 导航可挂在 `manage_modules` 下，因为它编辑的是 path module binding。
- 如果同页内提供材料创建/上传，则还需要 `manage_content` 或后续明确的 `manage_materials`。
- 如果同页内提供评分标准正文/rubric/schema 编辑、发布、回滚，则需要 `manage_prompts` 或一个明确新能力 `manage_audio_scoring_policy`。
- 如果只是选择已发布评分标准绑定到模块，按当前契约可以用 `manage_modules`。
- 如果同页展示操作日志，需要 `view_logs`；内容管理员无日志权限时，只能展示“已产生审计，联系有日志权限角色查看”或提供受限的 target-level audit projection。

#### 5.2 当前代码与契约的权限不一致点

需要在实现前统一以下点，否则治理页会产生“前端可见但后端拒绝”或“后端放行高风险”的不一致：

1. 文档默认模块矩阵提到 `sales_trainer.manage_materials`、`sales_trainer.manage_prompts`，但当前 `permissions.py` 没有 `manage_materials`，材料 API 使用 `_require_manager`，对应 `can_manage_sales_trainer` 即 admin/content_admin。见 `docs/api-contract/sales-trainer.md:249` 与 `backend/src/sales_trainer/permissions.py:90`。
2. 文档说 content_admin 可管理材料和录音评分标准，AI Coach 高风险字段仍需 `manage_prompts`，见 `docs/api-contract/sales-trainer.md:26`。但当前 `audio-score-prompts` API 也使用 `_require_manager`，不是 `manage_prompts`，见 `backend/src/sales_trainer/api.py:1910`。同时前端导航把 `scoreStandards` 放在 `manage_content` 下，把 `aiCoach` 放在 `manage_prompts` 下，见 `web/src/lib/sales-trainer/routes.ts:172`、`:188`。
3. `audio_score_prompt.rollback` 的测试断言 permission 为 `sales_trainer.manage_modules`，见 `backend/tests/integration/test_newcomer_training_path_score_prompt_api.py:202`。但 prompt 正文、rubric、output_schema 明显是 AI 判断高风险字段；如果治理要求“AI 判断能力不能糊”，建议不要继续把 prompt 发布/回滚归为 `manage_modules`。

推荐统一方案：

- `sales_trainer.manage_modules`：保存/发布/回滚 path config；选择已发布材料/评分标准绑定到 `ppt_explanation`；查看 path diagnostics。
- `sales_trainer.manage_content`：材料库、题库、文章、考卷等内容资产 CRUD；可创建/上传材料版本；是否发布材料版本需要看业务风险，当前可沿用 content_admin 允许。
- `sales_trainer.manage_prompts`：修改/发布/回滚录音评分标准的高风险字段，包括 `system_prompt`、`scoring_template`、`output_schema`、`learner_rubric`、模型/通过线/评分维度等。若产品坚持 content_admin 可管理评分标准，应新增更准确能力 `manage_audio_scoring_policy`，不要复用 AI Coach 的平台 prompt 权限语义。
- `sales_trainer.view_settings`：查看 ASR/Deucate 健康、配置来源、fallback 诊断。
- `sales_trainer.view_logs`：查看完整操作日志。
- `sales_trainer.view_records` / `view_global_records`：查看学员录音、评分结果、训练记录；培训负责人仅部门 scope。
- `sales_trainer.retry_jobs`：重试转写/评分任务。
- `sales_trainer.regrade_history`：历史重评 preview/run。

如果本期不改后端能力矩阵，则 PPT 治理页必须在文案和按钮上明确当前能力：content_admin 可以管理评分标准和材料，但不可以查看日志/设置/记录/重试/重评；高风险 prompt 字段的权限收敛留到后续 contract migration。

### 6. CRUD 操作应具备的校验与审计

#### 6.1 Create

材料创建：

- 校验 `material_key` 唯一、`name` 非空、`material_type` 合法、`purpose=ppt_pitch` 或允许值合法。
- 不允许直接创建为 learner 生效；新材料无 published version 前不能绑定。
- 审计 `material_created`，记录 actor、material_id、key、purpose、trace_id。
- 现有实现已在 `create_material` 中校验 key 并写日志，见 `backend/src/sales_trainer/services/material_service.py:118`。

材料版本创建/上传：

- 校验 material 未归档、`version_label` 唯一、文件名/content_type/size/storage_key/hash、存储路径在允许根目录下。
- 上传版本默认为 draft，不能自动替换 current_version。
- 审计 `material_version_created` 或上传日志，包含 file_name、file_size、hash、material_id、trace_id。
- 现有 upload 测试覆盖 draft version 和文件保存，见 `backend/tests/integration/test_newcomer_training_path_material_api.py:392`。

评分标准创建：

- 校验 name/purpose、`system_prompt`、`scoring_template`、`output_schema`、`learner_rubric` 合约；错误应是 422 或 typed error，不能写入半成品。
- 默认 draft，发布后才可绑定。
- 审计 `audio_score_prompt_created`。
- malformed schema/rubric 已有集成测试，见 `backend/tests/integration/test_newcomer_training_path_score_prompt_api.py:30`。

任务场景创建/补齐：

- 不应新建独立 task row；通过 `updatePathAudioBinding` 将缺失 `ppt_explanation` module 补入 path payload，并保存 working revision。现有前端会为缺失 audio module 创建默认 module，见 `web/src/lib/sales-trainer/path-config-editing.ts:96`。

#### 6.2 Read / Search

列表/查找：

- 材料、评分标准列表支持 `include_archived`、分页；治理页默认只展示 `status=published` 且当前版本存在的可绑定资产。
- 录音列表必须按对象级权限与部门 scope 过滤；training_manager/support 不能看跨部门记录，ops/admin 可看全局。
- operation logs 只允许 `view_logs`，并按 target_type/target_id 筛选。
- 前端不能在权限未知时请求受限数据；现有 route access 已覆盖。

诊断读取：

- `dead-data-diagnostics` 必须 dry-run，只读、不自动回填、不自动归档、不自动重评，见 `docs/api-contract/sales-trainer.md:678`。
- PPT 治理页应把 diagnostics 分成：阻断发布、可稍后补充、历史只读遗留、运维健康失败。

#### 6.3 Update

材料元数据更新：

- 已发布材料更新不应改写历史 snapshot，只影响未来；必须记录 before/after 和 changed_fields。
- 现有测试验证 `future_only`、`impact_scope=future_submissions_only`、before/after，见 `backend/tests/unit/test_newcomer_training_path_material_governance.py:101`。

评分标准更新：

- 对已发布 prompt 的高风险字段更新必须保存 working revision，不直接覆盖 active payload。当前实现已这样做，见 `backend/src/sales_trainer/services/prompt_service.py:144`。
- 发布前必须预览 change class、风险、影响范围；若当前 API 无 preview endpoint，应至少在治理页展示 working revision 与 changed_fields，并补后端 preview。

Path binding 更新：

- 保存前校验 canonical `path_key`、module_key/module_type、重复 order/module、target unit、material、version、scoring prompt。
- 保存 working revision 必须 reason；发布前再次用真实发布校验，不能只做前端检查。
- 现有前端保存要求 reason，见 `web/src/app/admin/sales-trainer/paths/use-path-config-center-workflow.ts:109`；后端音频发布校验在 `backend/src/sales_trainer/services/path_config_service.py:1199`、`:1220`。

#### 6.4 Publish

材料版本发布：

- 阻止 archived material 发布；发布新版本时旧 published 版本归档，material.current_version_id 指向新版本。
- 审计 before_version_id、after_version_id、archived_version_ids、impact_scope。
- 现有测试覆盖 `material_version_published` 与 `future_submissions_only`，见 `backend/tests/unit/test_newcomer_training_path_material_governance.py:52`。

评分标准发布：

- draft prompt 初次发布生成 active revision；published prompt 的 working revision 发布后更新 active revision。
- 审计 trace_id、change_class、future_only。
- 历史 submission 不变；如果需要重评，走 regrade。

Path config 发布：

- 必须先保存 working revision；无 working revision 返回 `[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]`，见 `docs/api-contract/sales-trainer.md:747`。
- 发布预览不写日志、不移动 active pointer；发布才记录 `newcomer_path_config.publish`，只影响未来 learner。
- 发布预览 response 需要返回 risk、changed_module_keys、historical_submissions_changed=false、rollback_hint、audit_event，见 `docs/api-contract/sales-trainer.md:682`。

#### 6.5 Delete / Archive

本域不建议提供硬删除。UI 如需“删除”，应命名为“归档”或“下架”，并有阻断校验：

- 材料归档：如果 active/working path revision 仍引用，必须阻止，现有测试 `MATERIAL_ARCHIVE_ACTIVE_REFERENCE` 覆盖，见 `backend/tests/unit/test_newcomer_training_path_material_governance.py:164`。
- 评分标准归档：如果 active/working path 引用或存在不可回放历史，应阻止或只允许禁用未来绑定；需补测试。
- Path module 不应删除历史模块配置；可 disabled 并说明 disabled_reason，发布后未来隐藏，历史保留。
- 任何归档必须写 before/after、引用阻断信息、reason、trace_id。

#### 6.6 Rollback

材料版本回滚：

- 必须先 preview，再 run；target 必须属于同一 material 且为可回滚 published/archived 版本。
- 回滚只改 current_version_id 和版本状态，历史 submission 的 confirmed version 与快照不变。
- 现有集成测试覆盖 preview 不变更、rollback 审计、historical_replay_preserved，见 `backend/tests/integration/test_newcomer_training_path_material_api.py:252`。

评分标准回滚：

- 必须先 preview，必须 reason；只恢复 active prompt payload/revision，不改历史 score_result。
- 现有测试覆盖 future_only、mutates_history=false、historical_submissions_changed=false 和审计，见 `backend/tests/integration/test_newcomer_training_path_score_prompt_api.py:129`。

Path config 回滚：

- 只允许回滚到已发布 path revision；只移动 active pointer；历史 attempt/submission/session 不变。
- 前端已有回滚 reason 测试，见 `web/src/app/admin/sales-trainer/paths/page.test.tsx:311`。

#### 6.7 Retry / Regrade

录音重试：

- `retry-transcription` 与 `retry-scoring` 是运维动作，只应给 `retry_jobs`，不能给 content_admin。
- `retry-scoring` 必须要求已有 transcript；状态从终态或失败态进入处理态，失败应写 typed error 和 audit。

历史重评：

- 必须 `regrade_history` 权限，部门 scope 生效，preview/run 分离，reason 必填，append-only 追加新 score_result，原 score_result 保留。
- 现有测试覆盖 content_admin 403、跨部门 404、reason 422、append_only 审计，见 `backend/tests/integration/test_newcomer_training_path_audio_regrade_api.py:205`、`:252`。

### 7. 错误状态矩阵

治理页和 API 至少要覆盖这些错误状态，不得吞成空状态：

#### 权限与访问

- 未登录/learner 调用 admin API：401/403，前端页面 fail-closed。
- capability 加载失败：不请求 path config/materials/prompts/settings，显示“页面访问受限/重新检查权限”。现有测试见 `web/src/app/admin/sales-trainer/paths/page.test.tsx:334`。
- content_admin 查看 settings/logs/records/regrade/retry：403。
- training_manager/support 无部门：空范围兜底，不放大全局；跨部门记录返回 404 而不是 403，以避免泄露存在性。

#### Path config

- active revision 缺失：learner 不能 fallback 到 legacy unit；返回空路径或 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`。
- working revision 缺失却 publish/preview：`[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]`。
- 非法 path_key/module_key/module_type/completion_rule/重复 module/order：`[NEWCOMER_MODULE_CONFIG_INVALID]`。
- `ppt_explanation` target unit 缺失、未发布、非 audio_scoring：`[NEWCOMER_MODULE_BINDING_MISSING]` 或更具体 typed error。

#### 材料

- PPT 模块缺材料：`[PPT_MATERIAL_BINDING_REQUIRED]` 或 `[NEWCOMER_MODULE_BINDING_MISSING]`。
- 材料不存在/归档/未发布/current_version 缺失/version 不匹配：发布阻断，UI 指向材料库快速修复。
- 学员未确认 required material version：`[MATERIAL_VERSION_CONFIRMATION_REQUIRED]`。
- 学员确认了非要求版本：应返回版本不匹配 typed error，不应自动改成 latest。
- 文件不存在或越权下载：404/403 typed error；历史文件必须按 frozen confirmed version 检查。

#### 评分标准 / AI 判断

- 评分标准不存在/未发布：`[SCORING_PROMPT_REQUIRED]`、`[SCORING_PROMPT_NOT_PUBLISHED]` 或 path publish 阻断。
- output_schema/learner_rubric 不合约：422，不能保存部分数据。
- Prompt revision lineage 缺失：diagnostics 标 `legacy_snapshot_only` 或 `regrade_unavailable`，不得伪造。
- Deucate 配置缺失/超时/请求失败/响应非法：`[DEUCATE_CONFIG_MISSING]`、`[DEUCATE_TIMEOUT]`、`[DEUCATE_REQUEST_FAILED]`、`[DEUCATE_RESPONSE_INVALID]`，submission 转 `scoring_failed` 并写日志。
- ASR 配置缺失/文件缺失/空转写/下载失败：typed error，submission 转 `transcription_failed` 或 terminal failure，不能假装 scored。

#### 发布/回滚/诊断

- 发布预览失败：页面仍可见，但展示失败代码与恢复入口；现有前端测试覆盖 provider readiness 失败显示，见 `web/src/app/admin/sales-trainer/paths/page.test.tsx:296`。
- rollback target 非 published revision 或不存在：typed 404/409。
- dead-data diagnostics：只读，候选动作必须 manual approval；不能提供自动修复按钮。

### 8. 分阶段实施计划

#### Phase 0：契约与权限收敛

目标：先解决权限语义和 API contract，不动 UI 业务逻辑。

- 决定 PPT 治理入口路由：建议 `/admin/sales-trainer/tasks/ppt-explanation` 或 `/admin/sales-trainer/paths?module=ppt_explanation` 的增强版；如果新增路由，路由仍映射 `manage_modules`。
- 统一能力命名：确认是否新增 `manage_materials` / `manage_audio_scoring_policy`；如果不新增，更新文档明确 `manage_content` 覆盖材料，评分标准高风险字段当前由谁管理。
- 明确评分标准发布/回滚权限：建议高风险字段使用 `manage_prompts` 或新能力；如果沿用 content_admin，需把风险写入 contract 和测试。
- 若新增聚合 API，先写 `docs/api-contract/sales-trainer.md`：DTO 字段、权限、错误码、发布/回滚 preview、audit fields。
- 验证：contract tests 更新；RBAC integration tests 覆盖每个角色访问新 route/API。

#### Phase 1：只读 PPT 任务治理页

目标：先让管理员看清现状，不引入写风险。

- 读取 capabilities、path config、path revisions、materials、score prompts、settings、publish preview。
- 聚焦展示 `ppt_explanation`：active revision、working revision、target unit、材料版本、评分标准、ASR/Deucate 健康、缺配置诊断、操作日志入口。
- 权限不足时 fail-closed，不请求敏感数据。
- 不展示 raw JSON、traceId、数据库主键给普通后台角色；debug/日志详情另说。
- 验证：前端 render/loading/empty/error/permission tests；断言缺材料/缺评分标准/Deucate 未配置有明确 remediation。

#### Phase 2：绑定已有发布资源并保存 working revision

目标：上下文内完成最常见修复：选择已有材料与评分标准。

- 在 PPT 页内选择已发布材料与评分标准；自动带当前 material current_version_id。
- 保存到 path working revision，reason 必填。
- 展示发布预览，不自动发布。
- 后端继续复用 `PUT /admin/newcomer-training/path-config` 与现有校验。
- 验证：`page-audio-bindings.test.tsx` 扩展为新入口；后端 path config binding tests 跑通。

#### Phase 3：快速新建/上传材料与评分标准

目标：满足 in-flow completion，但不降低治理。

- 材料：在 PPT 页抽屉快速创建材料 shell、上传 version draft、发布 version，再自动回填绑定。上传需要校验类型/大小/hash/storage root，发布有确认。
- 评分标准：提供“从已有标准复制/创建草稿”入口；完整 prompt/rubric/schema 编辑建议跳专门页面或专门抽屉，发布前显示高风险提示。
- 所有 create/upload/publish 都写审计，显示成功/失败状态和 trace 友好文案。
- 验证：材料 API integration、score prompt API integration、前端表单校验、重复提交防护、服务端错误映射。

#### Phase 4：发布、回滚、审计闭环

目标：治理页可落地发布与回滚。

- 发布 path working revision：必须 preview -> reason -> publish。
- 回滚 path revision：必须选择 target -> preview -> reason -> rollback。
- 材料版本与评分标准回滚：从各自资产页完成，PPT 页展示只读摘要和深链；若 PPT 页内操作，必须同样 preview/reason/audit。
- 操作日志：有 `view_logs` 时展示 target-filtered logs；无权限时展示“操作已记录”而非空白。
- 验证：publish/rollback happy path、preview fail、no working revision、rollback invalid target、audit metadata。

#### Phase 5：历史记录、重试、重评

目标：把运行结果治理纳入同一视图，但不混淆发布。

- PPT 页展示最近录音/失败状态链接到 audio submissions；records 权限才可见。
- ops 可重试转写/评分；content_admin 不可见或不可点。
- regrade_history 角色可从录音详情发起历史重评 preview/run；PPT 页只做入口提示，不自动重评。
- 验证：部门 scope、content_admin 403、ops retry、append-only regrade、历史快照不被发布/回滚改写。

### 9. 分层验证计划

#### 后端命令

建议从 `backend/` 执行：

```bash
pytest tests/unit/test_newcomer_training_path_config_bindings.py \
  tests/unit/test_newcomer_training_path_material_governance.py \
  tests/unit/test_newcomer_training_path_score_prompts.py \
  tests/unit/test_newcomer_training_path_audio_lineage.py \
  tests/unit/test_newcomer_training_path_audit_logs.py
```

```bash
pytest tests/integration/test_newcomer_training_path_config_api.py \
  tests/integration/test_newcomer_training_path_material_api.py \
  tests/integration/test_newcomer_training_path_score_prompt_api.py \
  tests/integration/test_newcomer_training_path_rbac_api.py \
  tests/integration/test_newcomer_training_path_audio_regrade_api.py
```

```bash
pytest tests/contract/test_sales_trainer_phase2_contract.py \
  tests/contract/test_audio_audit_contract.py \
  tests/contract/test_error_envelopes.py
ruff check src/
mypy src/
```

新增或修改 API 时必须补：

- 新 PPT 聚合 API contract test：字段、权限、错误 envelope、snake_case、trace_id。
- RBAC matrix：admin/content_admin/support/training_manager/operations/user 对新 API 与按钮的期望。
- Audit tests：create/update/publish/rollback/archive/regrade 的 action、target、reason、trace_id、before/after、impact_scope。
- Error tests：缺材料、缺评分标准、未发布版本、active revision 缺失、Deucate/ASR 配置缺失。

#### 前端命令

建议从 `web/` 执行：

```bash
npx vitest run \
  src/app/admin/sales-trainer/paths/page.test.tsx \
  src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx \
  src/app/admin/sales-trainer/materials/page.test.tsx \
  src/app/admin/sales-trainer/score-standards/page.test.tsx \
  src/app/admin/sales-trainer/audio-submissions/page.test.tsx \
  src/app/admin/sales-trainer/operation-logs/page.test.tsx \
  src/lib/api/sales-trainer.test.ts \
  src/lib/sales-trainer/config-center-audio-bindings.test.ts \
  src/lib/sales-trainer/routes.test.ts
```

```bash
npx tsc --noEmit
npx eslint . --quiet
```

新增 PPT 治理页时必须补：

- 页面访问：capability loading/error/denied 时不请求 path/material/prompt/settings。
- 只读态：active revision、working revision、材料、评分标准、ASR/Deucate 健康、缺配置诊断。
- 绑定态：选择已有 published material/prompt 后保存 reason，payload 写入 `ppt_explanation`。
- 发布态：working revision 存在时显示 preview；无 reason 禁用 publish；preview 失败仍保留页面。
- 回滚态：reason 必填；成功文案“只影响后续学员”。
- 权限态：无 `view_logs` 不显示完整日志；无 `view_settings` 不暴露配置健康详情；无 `view_records` 不请求 learner records。
- 错误态：所有 backend error message 经 `getApiErrorMessage` 显示，不渲染 raw stack/raw JSON。

### 10. 推荐验收标准

本任务可落地的 DoD：

- PPT 讲解录音治理页 3 秒内能回答：当前是否可发布、缺什么、谁能处理、发布会影响谁、如何回滚、审计在哪里。
- 新建、删除/归档、查找、发布、回滚、审计、权限、错误状态都有后端校验和前端状态，不靠隐藏按钮。
- 录音 AI 判断能力以“评分标准 revision + path binding + submission snapshot + score_result prompt_hash”追踪版本；发布/回滚默认 future-only；历史重评只能 append-only。
- 任务场景由 path config active revision 管理，不新增双真源；材料与评分标准作为被绑定资产治理。
- 权限矩阵在 docs/api-contract、后端 `permissions.py`、前端 routes/capabilities、tests 中一致。
- CRUD 关键动作都有 reason/trace_id/actor/before/after/impact_scope，敏感配置和 prompt/raw provider payload 不进入普通 UI 或日志。
- 自动化验证覆盖后端 unit/integration/contract、前端 vitest/tsc/eslint；不能只以“当前能跑”为完成标准。

### 11. Code patterns

- 权限模式：后端以 `sales_trainer.permissions` 为唯一能力投影，前端只消费 capabilities 做导航和 fail-closed；真实授权仍在每个 API helper 中执行。关键点：`backend/src/sales_trainer/permissions.py:23`、`backend/src/sales_trainer/api.py:398`、`web/src/lib/sales-trainer/use-admin-route-access.ts:20`。
- Future-only revision 模式：业务资产保存 working revision，发布/回滚移动 active pointer，历史记录读取 snapshot。关键点：`backend/src/sales_trainer/services/asset_revision_service.py:38`、`:133`、`:175`、`:209`。
- Path config 治理模式：PPT 任务场景属于 `newcomer_training_path_v1` active revision，发布前用真实校验预览风险。关键点：`backend/src/sales_trainer/services/path_config_service.py:144`、`:198`、`:232`、`:1199`、`:1220`。
- 材料治理模式：材料版本发布/回滚只影响未来提交，历史文件回放按 submission frozen version。关键点：`backend/src/sales_trainer/services/material_service.py:289`、`:325`、`:558`。
- 评分标准治理模式：已发布评分标准的高风险字段更新保存为 working prompt revision；发布/回滚不改写历史 score_result。关键点：`backend/src/sales_trainer/services/prompt_service.py:144`、`backend/src/sales_trainer/services/prompt_revision_service.py:40`、`:90`、`:208`、`:252`。
- 录音提交与 AI 判断模式：提交时冻结材料/评分方案/path lineage，评分优先使用 submission snapshot，并记录 prompt hash/model。关键点：`backend/src/sales_trainer/services/audio_submission_service.py:260`、`:623`、`:796`、`:823`、`:900`。
- 审计模式：操作日志统一记录 actor/action/target/request_id/metadata；发布、回滚、归档、重评都应包含 reason、trace_id、before/after、impact_scope。关键点：`backend/src/sales_trainer/services/operation_log_service.py:16`。

### 12. External references

- 未使用互联网外部资料。
- 使用的仓库内长期契约：`docs/api-contract/sales-trainer.md`、`docs/api-contract/README.md`、`docs/api-contract/voice-runtime.md`、`docs/api-contract/prompt-templates.md`、`docs/api-contract/release-verification.md`。
- 版本/日期参考：`docs/api-contract/sales-trainer.md` 标记“新人训练闭环契约冻结（2026-06-27）”，本审查日期为 2026-07-08。

### 13. Related specs

- `.trellis/spec/frontend/admin-console-patterns.md`：后台页面按 intent 分面、发布门禁稳定 URL、global policy 与 business asset 分离。
- `.trellis/spec/frontend/component-guidelines.md`、`.trellis/spec/frontend/index.md`：前端组件和页面状态覆盖要求。
- `.trellis/spec/backend/error-handling.md`：错误 envelope、trace_id、不可向 UI 暴露栈。
- `.trellis/spec/backend/logging-guidelines.md`：结构化日志、trace_id、敏感字段脱敏。
- `.trellis/spec/backend/prompt-template-governance.md`：Prompt 高风险字段、治理 repair、admin-only 平台 prompt 原则。
- `.trellis/spec/backend/business-rule-configs.md`：可调规则进入 business-rule 生命周期。
- `.trellis/spec/backend/sales-trainer-learning-topic-governance.md`：新人训练路径旁路学习专题不应重新混入 required path。
- `.trellis/spec/backend/quality-guidelines.md`：pytest/ruff/mypy/contract 测试和 forbidden patterns。

## Caveats / Not Found

- 当前 checkout 根目录未发现 `.codegraph/`，因此无法调用 CodeGraph；本轮已先检查并记录，按仓库规则跳过。
- `python3 ./.trellis/scripts/task.py current --source` 返回当前任务为空；用户已明确给出任务目录，本文件按用户给定目录写入。
- 本轮只读代码与测试，没有执行完整 pytest/vitest/tsc/ruff/mypy；上文列出的是建议验证计划，不是已运行结果。
- 未发现现成的独立 PPT 讲解录音治理页；当前能力主要分散在路径配置中心、材料库、录音评分标准、学员录音、操作记录。
- 权限契约存在需产品/工程确认的不一致：文档提到 `manage_materials`，代码无该 capability；录音评分标准 API 当前由 `_require_manager` 放行 content_admin，但高风险 prompt 语义更接近 `manage_prompts` 或新能力。实施前必须先统一。
- 没有使用外部互联网资料；“External references”限于仓库内 `docs/api-contract/`、`AGENTS.md` 与 `.trellis/spec/`。
