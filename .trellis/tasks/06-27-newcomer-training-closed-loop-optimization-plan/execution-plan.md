# 新人训练完整闭环执行计划

> 状态：Phase 1 契约/ADR、Phase 2 权限基础切片、材料文件对象级授权、article-progress active path scope、regrade 权限门槛，Phase 3 active revision/path-config 基础切片与 publish impact preview，Phase 4 材料 active/working 引用归档保护、历史只读回放、音频评分 prompt snapshot、dead data 诊断切片，Phase 5 TrainingJourney 后端只读投影、admin list/analytics 后端首切片与 learner 首页消费第一切片，Phase 6 AI Coach Prompt 前置校验，AI Coach SSE typed error/streaming disabled 失败兜底，Phase 7 realtime binding 配置治理、learner start API、真实 session external_binding 冻结、Journey outcome projection 与 training-record 只读投影首切片，Phase 8 前端 fail-closed、learner 实时对练入口、admin module nav/workbench capability 过滤、questions/papers/score-standards/articles/articles-capabilities/units/AI Coach capability fail-closed、audio/quiz 重试与重评 mutation guard、questions/score-standards/papers new/edit guard、questions/materials/audio detail/new form 直链错误显性化、admin training-record detail 前端 realtime/商务礼仪小测契约补齐与 admin analytics 前端首切片，Phase 9 deterministic newcomer Playwright smoke、商务技巧小测提交 E2E、录音 deterministic service-path 真评分 E2E、AI Coach deterministic stream 失败兜底 E2E、历史漂移回放 deterministic E2E、受限 manager 权限不足 E2E、真实 `/ws/sales` deterministic local provider E2E、新鲜生成完整闭环 E2E 与 CI gate 挂载，Phase 10 学员等级/角色等级治理投影、admin learner_level/role_level/training_stage/module_key 筛选、admin weakness heatmap、历史趋势投影与契约同步均已完成并通过聚焦验证；真实 provider release/nightly gate 已补 canonical 脚本模式、CI schedule/dispatch 入口和 classified evidence；AI Coach 真实 LLM 已用本地 DeepSeek 测试凭证 executed passed 且 runtime audit 来自 DB `ModelConfig`，StepFun 真实 provider 已用本地测试凭证在开放平台 URL 与候选 Step Plan URL 执行到上游但均返回 `upstream_auth_rejected` HTTP 401。
>
> 目标：把 `prd.md` 和 `research/audit-synthesis.md` 的 P0/P1/P2 审计问题转成可执行、可验证、可回滚的分阶段交付清单。本文是实施总账；代码实现必须按阶段推进，主 Agent 对最终集成、复核和验收负责。
>
> 逐项验收索引：`audit-closure-matrix.md`。
>
> 最终验收报告：`final-verification-report.md`。
>
> 外部验证 Runbook：`external-verification-runbook.md`。

## 成功标准

- `audit-synthesis.md` 中每个 P0/P1/P2 问题均有处理结果：已修复、已验证、文档化延期或需人工决策。
- learner 训练路径只以 active path revision projection 为唯一真源；无 active revision 时返回可诊断状态，不再制造 catalog/unit fallback 伪成功。
- 三类等级进入权限、展示、筛选、审计：角色等级、学员等级、训练阶段等级。
- AI Coach 与实时对练都进入 TrainingJourney、训练记录、管理看板、审计和测试门禁。
- 后端权限 fail-closed，所有对象级读取/写入均校验路径、模块、学员范围、部门范围和角色 capability。
- 配置有默认值、校验、fallback、诊断、发布预览和回滚语义；不可后台管理的 env-only 边界需写明原因。
- 内容资产 snapshot-first：材料、prompt、题卷、训练记录可追溯、可回放；不可回填历史显式标记 legacy。
- 前后端契约一致：DTO、error envelope、trace_id、fallback_applied/fallback_reason、capability 五层入口一致。
- 管理端支持按人员、部门、角色等级、学员等级、训练阶段、模块、状态分析。
- 后端相关 pytest/ruff/mypy、前端 npm test/lint/tsc、完整 Playwright E2E 和 CI gate 通过，或明确阻塞和延期原因。

## 风险等级

- 总体风险：P1，原因是涉及权限、状态聚合、配置治理、前后端契约和多模块联动。
- P0 条件风险：
  - 无 active path revision 时继续 `unit_backfill` 生成正式 learner 数据。
  - realtime 未补 ADR/API/runtime binding/权限/状态/回滚就直接接入新人训练闭环。
- P1 核心风险：
  - 对象级授权、配置发布、AI Coach prompt 校验、历史快照、前后端 fail-closed、E2E/CI 门禁。
- P2 普通风险：
  - UI/UX 看板增强、移动端展示、分析图表和筛选体验。

## 当前代码事实检查点

- `backend/src/sales_trainer/services/path_config_service.py` 已有 active revision、working revision、rollback preview 和 publish validation；当前已修复为：无 working revision 时禁止 publish，管理端 legacy 迁移诊断使用 `source="legacy_migration_snapshot"`，不再以 `unit_backfill` 作为 API source。
- `backend/src/sales_trainer/services/path_service.py` 的 learner path 已修复为只读 active projection；active 缺失时返回空列表，不再走 `_load_published_path_units()` fallback 生成正式 learner 路径。
- `backend/src/sales_trainer/permissions.py` 是本域 capability 权威；当前已修复为 `view_logs` / `view_settings` 仅 admin/ops，manager roles 通过 allowlist 过滤。
- `backend/src/sales_trainer/services/ai_coach_session_service.py` 旧逐题 service 与 v1 layered service 已改为复用 active path revision 解析：无 active revision、path payload 非法、模块缺失或模块未配置 AI Coach 时 fail-closed；文章绑定快照解析失败返回 typed error，不再吞异常后继续创建会话。`backend/src/sales_trainer/services/ai_coach_chat_session_creator.py` 也已在 runtime 解析前拒绝 draft-only path。
- `docs/api-contract/sales-trainer.md` 已更新 realtime runtime binding、TrainingJourney、训练记录、learner start API、三类等级、active revision 唯一真源和 AI Coach 必过契约；代码侧已实现 realtime binding 结构化 payload、发布前 provider readiness fail-closed、learner start API 调用 common session 创建权威并冻结 `voice_policy_snapshot.external_binding`、completed runtime outcome 只读投影进入 Journey 与 training-record 列表/详情；前端 learner Journey 模块已通过 `next_action=start_realtime_roleplay` 调用 start API 并跳转 practice；deterministic Playwright smoke 已覆盖 learner Journey active revision、商务技巧入口、录音 service-path 真评分、AI Coach SSE recoverable error、历史漂移回放、admin analytics、realtime disabled 诊断，以及真实 `/ws/sales` + local StepFun provider seam 的 start/WS/Journey/admin record 回流；真实第三方 provider release/nightly gate 已落到 `CRITICAL_GATE_MODE=newcomer-real-provider`，无凭证时输出 `credential_missing` classified skip，凭证可用时跑同一 newcomer realtime start/WS/Journey/admin record 路径；当前测试 key 已执行到 StepFun 上游并产生 `upstream_auth_rejected` HTTP 401 evidence。
- 子代理 Mill the 17th 只读复核指出 realtime outcome `passed=null` 会导致 required module 卡住 Journey 总状态；主 Agent 复核契约后没有把 realtime `passed=null` 伪装成通过，而是新增 `completion_satisfied`，把“完成规则已满足”和“考核通过”分离：`completion_rule="submitted"` 的 realtime completed outcome 可满足 Journey required completion，`passed` 仍保持 `null`。
- `docs/architecture.md` 明确 `sales_trainer` 不得直接 import `sales_bot/training_runtime` 创建或变更 realtime 会话；realtime 接入必须采用边界清晰的 runtime binding/投影契约。
- `backend/src/sales_trainer/services/material_service.py#resolve_file_access()` 已修复 learner active path/module/object scope，后台新增 admin/content_admin/ops published version 文件访问路由；历史引用的 archived material version 仍不可通过正式回放接口读取。
- `backend/src/sales_trainer/services/audio_submission_service.py` 已改为评分时优先使用 submission `score_scheme_snapshot.prompt_snapshot`；旧数据缺完整快照时才按 legacy prompt id 查当前发布行。
- `backend/src/sales_trainer/ai_coach_admin_api.py#get_ai_coach_config()` 已修复为 path payload 损坏、模块缺失等场景返回 typed error，不再吞异常回默认 `AiCoachConfig()`；AI Coach save/publish 已校验 PromptTemplate 存在、active、治理状态、用途/分类和 resolver，真正的 published revision 生命周期仍受现有 PromptTemplate 模型限制，需 Phase 4/6 继续治理 snapshot/revision。
- `backend/src/common/business_rules/defaults.py` / `validators.py` 已新增 `sales_trainer.learner_level.policy`：默认只提供 `unassigned`，真实等级枚举由后台配置发布；`TrainingJourneyService` 按已校验规则投影 `learner_level`，配置缺失/非法/停用显式返回 `fallback_applied/fallback_reason`。
- `backend/src/common/business_rules/defaults.py` / `validators.py` 已新增 `sales_trainer.role_level.policy`：默认把 `user` 映射为 `learner`，真实组织角色等级由后台配置发布；`TrainingJourneyService` 按已校验规则投影 `role_level`，与权限 capability scope 解耦。
- `/api/v1/admin/sales-trainer/journeys` 与 `/journeys/analytics` 已支持 `training_stage`、`module_key`、`learner_level`、`role_level` 精确过滤；`/journeys/analytics` 已新增基于 Journey outcome `completed_at/submitted_at` 的 `trend_data` 日期桶投影，前端 analytics 页面筛选项来自后端 summaries 或稳定 TrainingStage 枚举，不硬编码产品等级、组织角色等级或趋势数据。
- `web/src/app/(dashboard)/sales-trainer/page.tsx` 与 `web/src/lib/sales-trainer/module-path.ts` 已完成第一切片：移除 catalog/legacy fallback 伪成功；learner 首页 realtime module 已接入后端 start API，start 失败显示 error code 和 trace_id；`web/src/app/admin/sales-trainer/analytics/page.tsx` 已新增 admin Journey Analytics 首切片；admin workbench/module nav/直链页仍未共享 capability projection。
- `web/src/lib/api/types.ts` 与 `web/src/app/admin/sales-trainer/training-records/` 已补齐 `realtime_roleplay_session` 前端契约：后端合法实时对练训练记录不再被详情页白名单误拒，列表页可展示“实时对练”并跳转统一详情，详情页 raw snapshot 可回放 `external_binding/runtime_descriptor`，统一标签函数集中展示为“实时对练”。
- `SalesTrainerBusinessEtiquetteQuizAttempt` 已作为独立 `business_etiquette_quiz_attempt` 进入 admin training-record list/detail、Phase2 score explanation、ability profile、remediation 配置、operation log 回放和前端详情页；小测提交服务已修复为 flush 后记录审计日志，避免 target_id 为空导致历史回放不可关联。
- `web/src/lib/sales-trainer/routes.ts` 已新增 path-level capability 判断；`web/src/app/admin/sales-trainer/questions/page.tsx` 已先校验 `manage_questions`，能力未加载/加载失败/无权时不调用题库列表接口，不展示 AI 出题审核、小测预览、新建题目、发布、归档等写入口；`web/src/app/admin/sales-trainer/papers/page.tsx`、`web/src/app/admin/sales-trainer/score-standards/page.tsx`、`web/src/app/admin/sales-trainer/articles/page.tsx`、`web/src/app/admin/sales-trainer/articles/import/page.tsx` 和 `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx` 已先校验 `manage_content`，无权时不调用考卷/评分标准/文章/导入/能力点快照接口，不展示新建、编辑、上传、发布、归档、回滚、保存绑定、保存能力点快照等写入口；`web/src/app/admin/sales-trainer/units/page.tsx`、`web/src/app/admin/sales-trainer/units/new/page.tsx` 和 `web/src/app/admin/sales-trainer/units/[unitId]/edit/page.tsx` 已先校验 `manage_modules`，无权时不调用训练单元/历史版本/回滚/表单依赖/保存接口且不展示新建、编辑、发布、归档、历史版本、新建表单、编辑表单入口；`web/src/app/admin/sales-trainer/ai-coach/page.tsx` 已先校验 `manage_content` 或 `manage_prompts`，无权时不调用 AI Coach 配置接口且不展示保存草稿/发布入口。
- `scripts/critical-quality-gate.sh` 已纳入 sales_trainer/newcomer/business_etiquette 后端核心测试、新人训练 learner 首页/admin analytics/module-path 前端测试、runtime boundary、realtime start 单测和 `web/tests/e2e/newcomer-training-closed-loop.spec.ts` deterministic Playwright smoke；录音 deterministic service-path 真评分、AI Coach deterministic stream 失败兜底、历史漂移回放和 realtime 真 `/ws/sales` local provider 路径已有聚焦 Playwright 证据；真实第三方 provider 使用同一 canonical gate 的 `newcomer-real-provider` 模式由 `.github/workflows/release-truth-gate.yml` schedule/workflow_dispatch 执行，缺凭证不伪成功并生成 `.sisyphus/evidence/newcomer-real-provider-gate.json`；真实上游 401 会分类为 `upstream_auth_rejected`，并记录 model 与 realtime URL 配置状态。

## 阶段依赖

```text
Phase 0 计划检查
  -> Phase 1 契约/ADR 冻结
  -> Phase 2 权限 fail-closed 与对象级授权
  -> Phase 3 active path revision 唯一真源与配置治理
  -> Phase 4 内容资产/历史回放/死数据诊断
  -> Phase 5 TrainingJourney 聚合与状态机
  -> Phase 6 AI Coach 必过闭环
  -> Phase 7 realtime runtime binding 闭环
  -> Phase 8 前端 fail-closed、看板和 admin analytics
  -> Phase 9 E2E、CI gate、回归验收
```

不得跳过 Phase 1 直接实现 realtime；不得在 Phase 8 用前端隐藏替代 Phase 2 权限；不得在 Phase 6 用页面默认值替代 Phase 3 配置治理。

## 阶段计划

### Phase 0：计划检查与证据总账

- 目标：把审计问题、代码事实、任务归属、验证命令和暂停条件固定下来。
- 允许修改：本任务目录下计划/研究文件。
- 禁止修改：业务代码、迁移、生产配置。
- 成功标准：
  - 所有 P0/P1/P2 均有阶段归属。
  - 子代理报告覆盖后端真源、权限、配置/资产、前端、测试。
  - 主 Agent 复核 CodeGraph 与报告证据，不直接采信子代理结论。
- 验证命令：
  - `codegraph explore "..."`
  - `git status --short`
- 回滚策略：仅删除或修订本计划文件，无运行时影响。

### Phase 1：契约与 ADR 冻结

- 目标：更新 realtime 纳入闭环、TrainingJourney、三类等级、AI Coach 必过、active revision 唯一真源的 ADR/API 契约。
- 允许修改：`docs/api-contract/sales-trainer.md`、`docs/adr/`、任务目录文档。
- 禁止修改：业务代码直接接 realtime runtime。
- 成功标准：
  - API 契约新增 `TrainingJourney`、`ModuleProgress`、`ModuleOutcome`、`RoleCapability`、`LearnerLevel`、`TrainingStage`。
  - realtime 从 placeholder 升级为 runtime binding 契约，含 terminal/transient/voluntary failure、权限、配置健康、发布/回滚。
  - 契约删除或标注旧 learner fallback 的正式数据路径。
- 验证命令：
  - 文档审查：检查 contract 更新记录和 ADR 链接。
  - 后续 Phase 9 补 contract tests。
- 回滚策略：ADR 可追加 superseded 决策；API 契约回退到 placeholder 语义，代码不受影响。

### Phase 2：权限与对象级授权

- 目标：所有后端接口 fail-closed，修复材料文件、测验记录、logs/settings、article-progress、manager allowlist、regrade scope。
- 允许修改：`backend/src/sales_trainer/permissions.py`、相关 API/service、RBAC 测试。
- 禁止修改：无关 admin 权限体系、前端-only 权限替代。
- 成功标准：
  - content_admin 不能查看学员训练记录。
  - training_manager/support 只看部门范围记录，不能看全局 logs/settings。
  - ops 可看全局记录/日志/配置健康/重试重评，不能改内容。
  - learner article-progress、材料文件、音频、quiz、AI Coach、realtime 均校验 active path/module/object scope。
  - `SALES_TRAINER_MANAGER_ROLES` 缺失/空值使用默认；显式非法值过滤并输出诊断，全非法配置 fail-closed。
- 验证命令：
  - `cd backend && pytest tests/unit/test_sales_trainer_permissions*.py tests/unit/test_sales_trainer_*rbac*.py`
  - `cd backend && pytest tests/contract/test_error_envelopes.py`
  - `cd backend && ruff check src/`
- 回滚策略：权限改动按函数粒度回退；新增测试保留用于暴露风险。

### Phase 3：active path revision 唯一真源与配置治理

- 目标：废弃 learner fallback 伪成功，补 path payload validation、publish impact preview、fallback diagnostics、provider readiness。
- 允许修改：`backend/src/sales_trainer/services/path_*`、path config API/schemas/tests，必要的 `common/business_rules` 配置 resolver。
- 禁止修改：破坏历史 `unit_backfill` 只读诊断；不做生产数据修复。
- 成功标准：
  - learner `/paths` 无 active revision 时返回 typed diagnostic，不从 unit config 拼正式路径。
  - `unit_backfill` 仅管理端迁移/诊断可见，带 `legacy_snapshot_only=true`。
  - path payload 校验覆盖 path_key、module_key/order_index 唯一、module_type/completion_rule、binding、learning_units、realtime binding。
  - publish preview 返回影响范围；rollback 保留 preview/reason/trace_id。
  - fallback 返回 `fallback_applied/fallback_reason`。
- 验证命令：
  - `cd backend && pytest tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_boundary.py`
  - `cd backend && pytest tests/contract/`
  - `cd backend && ruff check src/`
- 回滚策略：保留 active revision 表结构不变；恢复 learner fallback 需明确标记为临时缓解，不作为完成。

### Phase 4：内容资产与历史回放

- 目标：prompt/material/paper/audio snapshot-first，历史只读回放和 dead data 诊断。
- 允许修改：`backend/src/sales_trainer/services/material*`、audio scoring、paper/quiz snapshot、asset revision lineage、dead data diagnostics。
- 禁止修改：批量生产数据回填、破坏性迁移。
- 成功标准：
  - 音频评分冻结 prompt revision 或完整 prompt snapshot。
  - 被历史提交引用的 archived material version 可经正式回放接口只读访问。
  - 资产归档保护 active/working path/template 引用。
  - legacy 数据显式 `legacy_snapshot_only` / `regrade_unavailable`。
  - dead data dashboard/report 可发现 orphan/missing/archived refs。
- 验证命令：
  - `cd backend && pytest tests/unit/test_sales_trainer_material* tests/unit/test_newcomer_training_path_audio_lineage.py`
  - `cd backend && pytest tests/integration/ -k sales_trainer`
- 回滚策略：新增回放/诊断接口可关闭入口；不修改原始历史记录。

### Phase 5：TrainingJourney 聚合与状态机

- 目标：建立新人训练 journey aggregate 和集中模块状态机。
- 允许修改：`backend/src/sales_trainer/services/` 新增 journey/progress/outcome 模块，schemas/API，相关前端 DTO。
- 禁止修改：让前端自行推断状态；跨域直接依赖 sales_bot runtime。
- 成功标准：
  - 聚合 audio、paper、business etiquette quiz、AI Coach、realtime、remediation、regrade、retry。
  - 返回机器可读状态：not_started、in_progress、processing、scored、passed、failed、needs_remediation、disabled、archived、error_terminal、error_transient。
  - 状态流转集中测试覆盖合法/非法/重复提交。
- 验证命令：
  - `cd backend && pytest tests/unit/test_sales_trainer_journey*.py tests/integration/test_sales_trainer_closed_loop*.py`
  - `cd backend && mypy src/`
- 回滚策略：journey 先作为 read model 投影，避免破坏原始记录表。

### Phase 6：AI Coach 必过闭环

- 目标：AI Coach 进入 path validation、journey、训练记录、可视化、失败兜底和审计。
- 允许修改：AI Coach config/chat/session services、path validation、training record projection、前端 AI Coach 工作台。
- 禁止修改：页面硬编码 mastery 阈值/文案/AI 参数；绕过 PromptTemplateService。
- 成功标准：
  - prompt/scoring prompt 必须真实存在、已发布、用途匹配。
  - 模型、temperature、timeout、retry、max tokens、成本阈值、降级策略集中治理。
  - AI Coach session 写 journey/training records/dashboard/audit。
  - 失败有 typed terminal/transient 语义与 UI 恢复动作。
- 验证命令：
  - `cd backend && pytest tests/unit/test_sales_trainer_ai_coach_chat.py tests/unit/test_sales_trainer_ai_coach*.py`
  - `cd web && npm test -- sales-trainer`
  - `cd web && npx tsc --noEmit`
- 回滚策略：保留旧 session 只读兼容；关闭新必过入口需返回配置诊断而非伪成功。

### Phase 7：实时对练纳入闭环

- 目标：按 ADR/API 契约接入 realtime runtime binding，结果进入 journey/dashboard/audit。
- 允许修改：`sales_trainer` 侧 binding/projection/API，必要 common runtime descriptor 引用；文档与测试。
- 禁止修改：`sales_trainer` 直接 import `sales_bot/` 或 `training_runtime/` 创建/变更 realtime 会话；不改 WS 主运行时边界。
- 成功标准：
  - path module 可绑定 realtime runtime config，发布前校验 provider readiness。
  - 创建 realtime session 前校验 path/module/learner level/权限/配置健康。
  - session outcome 进入 TrainingJourney 和 admin analytics。
  - terminal/transient/voluntary failure 分类明确，terminal 不盲目重连。
- 验证命令：
  - `cd backend && pytest tests/unit/test_sales_trainer_realtime_binding*.py tests/contract/`
  - `cd web && npm test -- realtime`
- 回滚策略：feature flag 或 module disabled 关闭 learner 入口；active revision 回滚到无 realtime binding。

### Phase 8：前端 fail-closed、训练看板和 admin analytics

- 目标：前端契约一致、五层 capability fail-closed、learner 看板和管理分析可用。
- 允许修改：`web/src/app/(dashboard)/sales-trainer/`、`web/src/app/admin/sales-trainer/`、`web/src/app/admin/newcomer-training/`、`web/src/lib/api/`、相关组件/测试。
- 禁止修改：Next.js API route、页面本地 fetch、页面硬编码业务阈值和状态流转。
- 成功标准：
  - sidebar、workbench card、module nav、按钮、直链页均受 capability 控制。
  - 403/500/network 不吞成“无绑定”；显示 trace_id 和可恢复动作。
  - `passed=null` 三态展示；移除录音结果页 `70` 硬兜底。
  - learner 看板展示三类等级、阶段、未开放原因、下一步。
  - admin analytics 支持漏斗、通过率、弱项热图、风险队列、部门/等级对比、趋势和移动端适配。
- 验证命令：
  - `cd web && npm test -- sales-trainer`
  - `cd web && npm run lint`
  - `cd web && npx tsc --noEmit`
- 回滚策略：保留旧路由只读兼容；新看板可通过导航回退到旧训练入口但不得恢复伪成功。

### Phase 9：E2E、CI 门禁与最终验收

- 目标：完整闭环测试和 CI gate 证明不是纸面闭环。
- 允许修改：`backend/tests/`、`web/tests/e2e/`、CI workflow、测试 fixture/seed。
- 禁止修改：跳过核心测试、真实 provider 默认必跑、引入不稳定外部依赖。
- 成功标准：
  - Playwright E2E 覆盖 learner 首页、文章/考试、录音评分、AI Coach、实时对练、管理端看板、权限不足、配置异常、历史回放。
  - backend unit/integration/contract、frontend vitest/lint/tsc 通过。
  - 销售训练核心测试进入 CI gate；真实 provider smoke 纳入 nightly/release，分类 skip 有明确原因。
- 验证命令：
  - `cd backend && pytest tests/unit/ tests/integration/ tests/contract/`
  - `cd backend && ruff check src/ && mypy src/`
  - `cd web && npm test && npm run lint && npx tsc --noEmit`
  - `cd web && npm run e2e -- newcomer-training-closed-loop`
- 回滚策略：CI gate 可按 workflow revert；E2E fixture 不影响生产。

## 审计问题归属总账

| 问题 | 风险 | 阶段 | 当前状态 |
|---|---:|---|---|
| 无 active revision 时 learner 走 fallback 伪成功 | P0 | Phase 3 | 已修复并验证：learner `/paths` 无 active revision 返回空，不再 unit fallback；聚焦测试 30 passed |
| realtime 未补契约直接接入 | P0 | Phase 1/7 | 契约/ADR 已更新为 runtime binding；后端切片已修复并验证：`realtime_roleplay` path payload 结构化校验、发布前 binding/provider readiness fail-closed、change fingerprint 纳入 binding、learner start API 通过 common 中性端口创建真实 session 并冻结 `voice_policy_snapshot.external_binding`，completed runtime session 进入 Journey `realtime_roleplay_session` outcome 和 training-record 列表/详情只读投影；前端 learner Journey 按 `next_action` 调用 start API 并跳转 practice，start 失败显式展示 error code/trace_id；admin training-record list/detail 类型、白名单和 raw snapshot 已接受 `realtime_roleplay_session`，不再前端误拒后端合法实时对练记录；真实 `/ws/sales` deterministic local provider Playwright 已覆盖 start API、WS 消息、Journey outcome 和 admin record binding 回流；真实第三方 provider gate 已接入 release/nightly canonical gate 模式，缺凭证 classified skip，凭证可用时按同一闭环路径硬失败 |
| 材料文件对象级授权 | P1 | Phase 2 | 已修复并验证：learner 仅可读 active path 可进入模块绑定材料，admin/content/ops 后台路由可读 published，manager 403；5 passed |
| 商务礼仪测验记录权限 | P1 | Phase 2/9 | 已修复并验证：records 权限 + manager 部门 scope；商务礼仪小测 attempt 作为独立 `business_etiquette_quiz_attempt` 进入 admin list/detail、Phase2 投影、审计日志和前端详情页；Playwright 已覆盖 learner UI 提交后进入 Journey/admin records |
| logs/settings manager 可见 | P1 | Phase 2 | 已修复并验证：后端返回 403；聚焦权限测试 34 passed |
| article-progress 任意内容访问 | P1/P2 | Phase 2/3 | 已修复并验证：learner article/article-progress 必须匹配 active path 当前模块绑定；无 active revision 返回 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`，路径外 published content GET/POST 均返回 `[LEARNING_CONTENT_MISMATCH]`；7 passed |
| manager roles allowlist | P1 | Phase 2 | 已修复并验证：空 env 使用默认；混入非法值只保留合法项；全非法 env fail-closed |
| regrade 对象级 scope | P2 当前 / 未来 P1 | Phase 2 | 已验证：当前重评入口仅 admin/ops 可用；quiz/audio regrade service 和 API 已强制接收 viewer/team scope；测试用 monkeypatch 模拟未来 manager 开放后，同部门 preview 成功、跨部门 run 返回 `[REGRADING_TARGET_NOT_FOUND]` 且不新增 regrade run；3 passed |
| 配置资产导出审计默认关闭 | P1 | Phase 2/3 | 已修复并验证：默认且强制记录导出审计，显式 false 也不可绕过 |
| JWT 默认密钥兜底风险 | P1 | Phase 2/9 | 已修复并验证：生产 readiness gate 同时校验 `SECRET_KEY` 与实际签发/校验使用的 `JWT_SECRET`，空值、默认值和短密钥均 fail-closed；lifespan 启动层复用同一安全规则，默认/弱 `JWT_SECRET` 会在数据库初始化前阻断；18-test 聚焦回归和 ruff 通过 |
| path payload 校验不足 | P1 | Phase 3 | 已修复并验证：path_key、canonical module_key/order_index、legacy alias、顶层 enabled、canonical module_key/module_type 配对、realtime binding/provider readiness 校验已落地；learner start API 已校验 active revision、runtime binding、provider readiness 和 practice_template_id；真实 runtime descriptor registry/readiness 已通过 `sales_trainer.realtime_provider.registry` 业务规则配置接入 draft/validate/publish/rollback/disable 和操作审计，缺失/停用/未就绪均 fail-closed；保存阶段与发布阶段采用分层校验，保存只拒绝永远不应成立的结构错配，材料、题卷、runtime binding 等依赖在 publish/preview 阶段 fail-closed，以保留 working draft 的可编辑性 |
| 顶层 path enabled 伪配置 | P1 | Phase 3 | 已修复并验证：写入拒绝 `enabled=false`；active projection 对旧坏数据 fail-closed |
| AI Coach prompt 前置校验 | P1 | Phase 3/6 | 已修复并验证：save/publish 校验 PromptTemplate 存在、active、治理状态、用途/分类、revision resolver；AI Coach 旧逐题/v1/chat 创建入口均要求 active path revision，模块必须显式配置 AI Coach，不再回默认 `AiCoachConfig()`；43 passed + 本切片 84 passed |
| publish impact preview | P1 | Phase 3 | 已修复并验证：新增 `/path-config/publish/preview`，复用发布校验，返回 future-only impact_scope、changed/affected modules、risk_level、rollback_hint、audit_event；无 working revision typed fail；27 passed |
| fallback diagnostics | P1 | Phase 3/6/8 | 已修复并验证：learner path 不再 unit fallback；AI Coach 创建入口无 active revision、非法 path payload、模块未配置和文章绑定异常均返回 typed error；path-config `diagnostics` 已结构化返回 `fallback_applied/fallback_reason` 和 realtime readiness；admin config center 显示路径真源 fallback、发布预览成功/失败诊断，不再吞掉 provider readiness typed error |
| 学员等级治理与筛选 | P1 | Phase 8/10 | 已修复并验证：新增 `sales_trainer.learner_level.policy` 业务规则，默认 `unassigned`，发布配置可定义 levels/rules；Journey 返回 source/config_revision/fallback 元数据；admin list/analytics 支持 `learner_level` 精确过滤，前端 analytics 可按后端 summary 选项筛选；真实产品等级枚举/人工分配来源仍需产品确认后接入 |
| 角色等级治理与筛选 | P1 | Phase 8/10 | 已修复并验证：新增 `sales_trainer.role_level.policy` 业务规则，默认 `user -> learner`，发布配置可定义 levels/rules；Journey 返回 role_level source/config_revision/fallback 元数据；admin list/analytics 支持 `role_level` 精确过滤，前端 analytics 可按后端 summary 选项筛选；已与权限 capability scope 解耦 |
| provider readiness | P1 | Phase 3/7/8 | 已修复并验证：realtime module binding 必须携带 `provider_readiness_snapshot.ready=true` 才能发布；learner start API 现在先校验 path snapshot，再读取 `sales_trainer.realtime_provider.registry` 当前 active 配置，registry 缺失/停用、descriptor 缺失/停用或 registry readiness 失败均 fail-closed；registry 通过 BusinessRuleConfig/ConfigBundleLifecycle 管理，默认 disabled，可 draft/validate/publish/rollback/disable，并写 `ConfigBundleAuditLog` before/after；start 成功时把 registry config_id/version/source/status/descriptor 冻结到 `voice_policy_snapshot.external_binding.runtime_registry` 和操作日志；前端配置中心和诊断页已接入 readiness 投影。专门 registry 管理 UI 属于非阻塞增强；真实第三方凭证执行由 release/nightly gate 覆盖，缺凭证按外部项分类 |
| prompt snapshot/revision | P1 | Phase 4/6 | 已修复并验证：`freeze_submission_snapshots()` 写入完整 `prompt_snapshot`，音频评分/重评优先使用提交时快照，legacy 缺快照才回退当前发布 prompt 行；seed 已制造当前 Prompt 漂移哨兵并验证训练记录详情仍只回放提交时冻结快照、不泄漏当前漂移；25-test 单测、39-test Phase 4 聚焦回归和本轮历史漂移 E2E 均通过 |
| 历史材料只读回放 | P1 | Phase 4 | 第一切片已修复并验证：普通 learner/admin 文件路由仍拒绝 archived version；新增训练记录详情材料回放路由，只允许读取该记录 `confirmed_material_version_id` 冻结引用的 archived/published version，并复用记录权限和部门 scope；7 passed，55-test 聚焦回归通过 |
| 资产归档引用保护 | P1 | Phase 4 | 第一切片已修复并验证：active/working 新人训练路径引用的材料或版本归档时返回 `[MATERIAL_ARCHIVE_ACTIVE_REFERENCE]`；历史提交引用不阻断归档但可经只读回放读取；7 passed，55-test 聚焦回归通过 |
| legacy/dead data 诊断 | P1/P2 | Phase 4 | 已修复并验证：新增只读 `/path-config/dead-data-diagnostics`，扫描 active/working revision、article_exam 内容/考卷、材料/版本 inventory、音频历史快照缺口，返回 `legacy_snapshot_only/regrade_unavailable` 元数据；17-test 集成验证和 ruff 通过 |
| TrainingJourney 聚合 | P1 | Phase 5 | 已修复并验证：新增后端只读 `TrainingJourneyService`、learner/admin detail/list/analytics endpoint，active revision fail-closed，聚合 audio/group audio、quiz、business etiquette quiz、AI Coach 和 completed realtime outcome；前端 learner 首页已消费并可从 realtime module 发起 start；realtime training-record 列表/详情只读投影与 learner start API 已接入；真实 `/ws/sales` E2E 已证明 realtime completed outcome 回流 Journey 与 admin record；本轮补齐 `completion_satisfied`，使 `completion_rule="submitted"` 的 realtime required module 不再因为 `passed=null` 卡住整条 Journey，同时保持契约要求的“不得伪装通过考核” |
| 不强制顺序解锁状态策略 | P1 | Phase 5 | 已确认：projection 仍读取 unlock_after_unit_ids 并 locked |
| AI Coach 入 journey/record/dashboard | P1 | Phase 6 | 已修复并验证：子代理只读复核确认 AI Coach session 已进入 TrainingJourney、training-record 和 admin analytics 聚合；本切片补齐创建入口 active revision/config fail-closed，防止 draft/default config session 写入闭环，并新增 API 集成断言证明 mastered session 进入 learner journey 与 admin weakness heatmap，not_mastered session 进入 training-record detail/list、effective_score、ability_profile、remediation 与 operation_logs；admin detail 页面已显式展示 AI Coach article/config/coach/prompt/path/mastery/trace 快照并覆盖 loading/error/invalid recordType fail-closed；后端 SSE typed error 与 streaming disabled 兜底已补单测，前端 deterministic Playwright 已覆盖 AI Coach stream recoverable error。真实 provider stream gate 已补独立 `newcomer-ai-coach-real-provider` 模式、CI schedule/dispatch 入口和 classified skip 证据；2026-06-28 已用真实 LLM provider 执行通过，覆盖 session stream、message stream、governed quiz_card 和 schema audit log |
| 前端五层 fail-closed | P1 | Phase 8 | 已修复并验证核心管理入口：learner 首页和 module-path 移除 catalog/legacy fallback；admin module nav 和 workbench card 复用 `/admin/sales-trainer/capabilities` 过滤入口，capability 加载失败 fail-closed，模块内导航自身加载能力失败时显示可重试错误条而不是静默消失；questions 列表/新建/编辑页已先校验 `manage_questions`，能力失败/无权时不调用题库/分类/题目详情/保存接口且不展示 AI 出题审核、小测预览、新建题目、发布、归档、新建表单、编辑表单入口；papers/score-standards/articles/articles-capabilities 页面级和 new/edit 页已先校验 `manage_content`，无权时不调用列表/导入/能力点快照/正式题库/考卷/评分标准/保存接口且不展示新建、编辑、上传、发布、归档、回滚、保存绑定、保存能力点快照、创建/编辑表单入口；units 列表/新建/编辑页已先校验 `manage_modules`，无权时不调用单元/历史版本/回滚/表单依赖/保存接口且不展示新建、编辑、发布、归档、历史版本、新建表单、编辑表单入口；AI Coach 页已先校验 `manage_content` 或 `manage_prompts`，无权时不调用配置接口且不展示保存草稿/发布入口；operation-logs 已先校验 `view_logs`，权限未确认/不足时不请求审计日志；training-records 列表和 score-results 列表已先校验 `view_records`，权限未确认/不足时不请求训练记录、做题结果或录音评分结果；training-record detail、audio submission detail 和 quiz attempt detail 已先校验 `view_records`，权限未确认/不足时不请求训练记录详情、录音详情或做题结果详情；materials、paths、settings、audio-submissions 列表和 Journey Analytics 已接入共享 `useSalesTrainerAdminRouteAccess`，能力接口失败或无权时不请求材料、路径配置、配置诊断、录音列表或分析业务 API；`/admin/sales-trainer/analytics` 已补入统一路由表并由 `view_records` 控制；`/admin/sales-trainer/quiz-attempts/*` 作为隐藏详情路由纳入 `view_records` 能力判定但不出现在导航；audio submission detail 的重试转写/评分受 `retry_jobs` 控制，audio/quiz 历史重评面板受 `regrade_history` 控制；materials、audio submission detail、quiz attempt detail、questions/new、units/new 直链页加载失败显式错误并阻断创建/上传/重试操作入口，重试成功可恢复；business-skills 学习页 AI Coach 路径解析失败时显示可诊断提示，不再静默隐藏入口；deterministic Playwright 已补受限 `training_manager`：后端 capability 只放行 `manage_questions/view_records`，直接读考卷 API 返回 403，`/admin/sales-trainer/papers` 不拉取考卷资源且无写入口，`/questions` 仍可进入题库管理；低频 articles/score-prompts 专项巡检未发现高置信残留 |
| admin 混用 learner 接口和吞错 | P1 | Phase 8 | 已修复并验证：admin 文章绑定页和路径配置中心不再调用 learner `getModuleArticle` 读取绑定态，统一从 admin `GET /admin/newcomer-training/path-config` 的 `path.modules[].learning_content_id` 派生；path-config 未绑定、绑定内容缺失、path-config 读取失败均显式展示，不再把 learner 404 吞成空绑定 |
| loading 卡死 / passed=null / 70 硬兜底 | P1 | Phase 8 | 已修复并验证：passed=null 和 70 硬兜底已修；audio submission detail 重试评分/转写成功后 `isOperating` 可恢复；录音结果页读取训练单元失败时不再静默隐藏通过线，改为展示配置诊断；录音结果详情读取 submission 失败时不再落成“结果不存在”，改为可重试错误态；learner quiz result 读取 attempt 失败时不再落成“做题结果不存在”，改为可重试错误态；admin quiz attempt detail 读取 attempt 失败时不再落成不可恢复错误，改为可重试错误卡；admin training-record detail 读取失败时不再落成“未找到训练记录”，改为可重试错误卡；admin training-records 列表读取失败时不再同时显示“暂无训练记录”，改为错误卡和重试；admin score-results 两个列表读取失败时不再同时显示“暂无做题结果/暂无评分结果”，改为错误行和错误提示；admin audio-submissions 列表读取失败时不再同时显示“暂无录音记录”，改为错误卡和重试；operation-logs 读取失败时不再渲染空日志；quiz result 的 AI Coach 入口路径读取失败时不再静默隐藏入口，改为展示可诊断提示；settings 配置诊断页新增页面级 loading/error/retry，依赖失败不再空白等待；questions/categories 直链页新增 capability fail-closed，权限未确认/不足时不加载分类或开放新建表单；questions/drafts 首次业务数据加载失败时显示阻断式错误卡和重试，不再把草稿/分类/能力点接口异常伪装成“暂无草稿”或空编辑器；papers/units 列表业务接口失败时显示阻断式错误卡和重试，不再把接口异常伪装成“暂无考卷/暂无训练单元” |
| learner 训练看板 | P2 | Phase 8 | 已修复并验证当前审计范围：learner 首页已移除成功态 `/paths`/catalog 兼容入口卡片，不再请求旧 units/paths 来伪装入口成功；首屏只读取 TrainingJourney，等级、诊断、模块状态和实时对练 action 均以 active revision Journey 为唯一真源；learner 录音上传页不再并行读取 legacy `/paths`，标题、说明、材料和通过线只来自 active path effective unit brief，旧路径接口故障不会影响录音训练入口；旧章节阅读直达页 `learn/[unitId]` 不再读取 legacy `/paths` 或 `/units` 做路径上下文 fallback，先用当前单元 learner 配置判定是否可读，再读取学习内容；商务技巧考试页不再跨单元借用其他考卷，当前 unit 未绑定考卷时直接显示配置缺失。视觉分析密度和移动端体验可继续优化，但不影响本轮“唯一真源/可诊断/闭环”验收 |
| admin analytics | P2 | Phase 8/10 | 前后端首切片已修复并验证：`/admin/sales-trainer/journeys/analytics` 返回并展示 summary/funnel/module_summaries/weakness_heatmap/trend_data/learner_level_summaries/role_level_summaries/risk_learners，页面具备 loading/empty/error/success、部门筛选、training_stage 筛选、module_key 筛选、learner_level 筛选、role_level 筛选、弱项热图和历史趋势；趋势由后端基于可追溯 Journey outcome 时间桶聚合，未用单次快照伪造 |
| 完整 E2E/CI gate | P1 | Phase 9 | 已修复并验证：`.trellis/.../research/phase9-e2e-ci-gate-plan.md` 明确场景矩阵、fixture/seed/mock 和 CI 分层；`scripts/dev-smoke-up.sh` 已接入 newcomer deterministic seed；`scripts/critical-quality-gate.sh` 已纳入新人训练核心后端 unit/integration、runtime boundary、realtime start、training-record projection、前端 Vitest 目标和 newcomer Playwright smoke；`web/tests/e2e/newcomer-training-closed-loop.spec.ts` 已覆盖 learner Journey active revision、商务技巧入口、商务礼仪小测 UI/API 提交进入 Journey/admin records/admin detail 回放、fresh current-run quiz/audio/AI Coach 同 active revision、admin analytics、seeded 录音/AI Coach outcomes、录音 service-path 真评分证据、admin training-record detail、AI Coach 快照显性回放、AI Coach stream recoverable error、历史漂移回放、受限 manager 权限不足旅程和真实 `/ws/sales` local provider 实时对练闭环；真实第三方 provider release/nightly gate 已接入 `.github/workflows/release-truth-gate.yml` 的 schedule/workflow_dispatch job，`newcomer-real-provider-gate.json` 已记录 StepFun Realtime 使用 `step-audio-2.3` 执行到上游但返回 `upstream_auth_rejected`；AI Coach 真实 LLM stream gate 已接入独立 schedule/dispatch job，`newcomer-ai-coach-real-provider-gate.json` 已记录真实 LLM provider `executed` 且通过；缺真实凭证默认失败，只有 workflow_dispatch 显式 allow skip 或本地对应 `*_CREDENTIAL_SKIP_ALLOWED=1` 才允许 classified skip 通过，避免缺凭证被误判为绿色 |
| 后端 mypy/coverage 质量门禁 | P1 | Phase 9/10 | 已修复并验证：`scripts/critical-quality-gate.sh` 新增 `Backend newcomer coverage gate` 和 `Backend newcomer mypy gate`；coverage 目标限定 `sales_trainer` + `common.business_rules`，测试覆盖 newcomer path boundary、TrainingJourney、newcomer journey API 和 business rule config service，当前 fail-under 基线为 45；mypy 目标限定本次触达的 business_rules、runtime outcome、external session start、TrainingJourney、realtime roleplay start，使用 `--follow-imports=skip` 避免全仓历史 SQLAlchemy/第三方 stub 噪音阻断新人训练门禁；同时修复本链路内 `_integer_range` 重名、runtime/realtime/journey/external session 类型缺口 |
| 新鲜生成完整闭环 E2E | P1 | Phase 9 | 已修复并验证：`NEWCOMER_E2E_FRESH_RUN_ID` 开启时 seed 会通过 deterministic service-path 新鲜生成 PPT 录音评分和 AI Coach mastered session，并发布 ready realtime provider registry；Playwright 同一 learner 运行中再通过真实商务礼仪 quiz API 新鲜提交 attempt，断言 fresh quiz/audio/AI Coach 都共享 Journey active `path_revision_id`，进入 Journey latest outcome、admin training-record list/detail、operation logs 和 analytics 投影；历史 baseline 回放测试改为按固定 filename/trace 找 seed 记录，避免 fresh latest 覆盖历史回放证据 |
| AI Coach 真实 provider stream gate | P1 | Phase 9 | 已修复并验证分类门禁：新增 `CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider`，缺 `LLM_API_KEY/OPENAI_API_KEY` 时生成 `.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json` classified skip 且默认失败；人工显式 `NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1` 才允许跳过；凭证可用时跑 Playwright `AI Coach real provider stream creates a governed first-card after learner choice`，先调用 `/newcomer-training/ai-coach/chat/sessions/stream` 验证 `plan_then_wait` 只生成 1 个 `followup_prompt` 且不生成 `quiz_card`，再用结构化 learner choice `{ command: "continue" }` 调用 `/messages/stream` 触发真实 LLM 首卡，要求无 SSE error、completed snapshot、assistant message、governed `quiz_card`，并通过 operation log 的 `ai_coach_chat_next_action_generated_v1` 断言后端实际解析出的 `llm_runtime.provider/model_name/base_url`。已验证缺凭证 allow-skip 退出 0、默认策略退出 1、evidence 字段正确、脚本/前端静态检查通过；2026-06-28 已用真实 LLM provider 执行通过 |
| 模型配置持久化审计 | P1 | Phase 2/3 | 已修复并验证：`admin/api/model_configs.py` 的 create/update/delete/persisted test/inline test/tts-preview 均写入 `SystemLog` 持久化审计，包含 actor、target_config_id、trace_id、source、before/after、success/status、latency 和 runtime_refresh_requested；快照只记录 `api_key_configured`，不写入明文或密文。主 Agent 复核子代理建议后选择 `SystemLog` 而非 `SalesTrainerOperationLog`，原因是模型配置属于平台级 AI/ASR/TTS runtime 配置，不是 sales_trainer 业务对象；集成测试已覆盖 CRUD/test/TTS preview 审计落库 |

## 已执行验证记录

- P1 JWT 默认密钥兜底风险：`cd backend && pytest --no-cov tests/unit/test_release_readiness.py tests/unit/test_app_factory.py`：18 passed，1 warning；覆盖 release readiness 拒绝弱 `SECRET_KEY`/`JWT_SECRET`、安全生产配置必须显式设置 JWT 密钥、lifespan 在数据库初始化前拒绝弱 `JWT_SECRET`。`cd backend && ruff check src/app_lifespan.py src/common/analytics/release_readiness.py tests/unit/test_app_factory.py tests/unit/test_release_readiness.py`：通过。直接运行不带 `--no-cov` 的同一聚焦命令时 18 个用例全部 passed，但因小范围运行触发仓库全局 coverage fail-under=48，命令退出 1，非功能断言失败。
- Phase 7/8 realtime provider registry 治理：`cd backend && pytest --no-cov tests/unit/test_config_bundle_roleplay_situation_packs.py tests/unit/test_sales_trainer_realtime_roleplay_start.py tests/unit/common/test_business_rule_config_service.py`：18 passed，1 warning；覆盖 registry 默认 disabled fail-closed、发布 ready registry 后 start 成功、external binding 冻结 registry descriptor、registry publish/disable 解析、非法 provider 拒绝、ConfigBundle adapter 暴露和 disable before/after 审计快照冻结。`cd backend && ruff check src/common/business_rules/defaults.py src/common/business_rules/validators.py src/admin/config_bundles/adapters.py src/admin/config_bundles/lifecycle.py src/sales_trainer/services/realtime_roleplay_start_service.py tests/unit/test_config_bundle_roleplay_situation_packs.py tests/unit/test_sales_trainer_realtime_roleplay_start.py tests/unit/common/test_business_rule_config_service.py`：通过。
- Phase 9 真实 provider release/nightly gate 策略：`CRITICAL_GATE_MODE=newcomer-real-provider STEPFUN_API_KEY= NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=0 bash scripts/critical-quality-gate.sh`：按预期退出 1，输出 `[ERROR] Newcomer real provider gate requires STEPFUN_API_KEY or NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1`；`CRITICAL_GATE_MODE=newcomer-real-provider STEPFUN_API_KEY= NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1 bash scripts/critical-quality-gate.sh`：退出 0，生成 `.sisyphus/evidence/newcomer-real-provider-gate.json`，其中 `classification=credential_missing`、`credential_skip_allowed=true`；`bash -n scripts/critical-quality-gate.sh` 和 `git diff --check -- scripts/critical-quality-gate.sh scripts/README.md .github/workflows/release-truth-gate.yml`：通过。
- Phase 5 测试矩阵：`.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/phase5-journey-test-matrix.md` 已完成，结论经主 Agent 用 CodeGraph 复核：当前缺少 TrainingJourney 权威对象、sales_trainer -> realtime binding 闭环测试、三类等级 contract/analytics 测试和新人训练闭环 Playwright E2E。
- Phase 5 后端 Journey 第一切片：`cd backend && pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q`：8 passed，1 warning；覆盖无 active revision、audio/quiz/AI Coach 聚合、商务礼仪小测 outcome、audio group duration option、realtime diagnostic、learner/admin 权限、部门 scope、admin list 和 analytics 路由顺序。
- Phase 5 后端 Journey ruff：`cd backend && ruff check src/sales_trainer/services/training_journey_service.py src/sales_trainer/api.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：通过。
- Phase 7 realtime binding 研究：`.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/phase7-realtime-binding-plan.md` 已完成并由主 Agent 复核；结论：先落 path binding/read-model fail-closed，不直接 import `sales_bot/training_runtime` 或创建 `PracticeSession`。
- Phase 7 realtime binding 后端首切片：`cd backend && pytest --no-cov tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_sales_trainer_training_journey_service.py -q`：18 passed，1 warning；覆盖 enabled realtime 缺 binding 拒绝发布、provider readiness 未通过拒绝发布、ready binding 进入 Journey 但无 completed outcome 时为 `not_started`。
- Phase 7 realtime Journey outcome projection：`cd backend && pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_newcomer_training_path_boundary.py -q`：12 passed，1 warning；覆盖 completed runtime session 通过 `voice_policy_snapshot.external_binding` 进入 `realtime_roleplay_session` outcome，且 `sales_trainer` 未直接 import/runtime 创建 realtime session。
- Phase 7 Journey API 回归：`cd backend && pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q`：9 passed，1 warning。
- Phase 7 ruff 聚焦检查：`cd backend && ruff check src/common/services/runtime_outcome_projection.py src/sales_trainer/services/training_journey_service.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：通过。
- Phase 7 realtime training-record 只读投影：`cd backend && pytest --no-cov tests/unit/test_sales_trainer_phase2_projection.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_runtime_dependency_contract.py tests/integration/test_newcomer_training_journey_api.py -q`：30 passed，1 warning；覆盖 realtime completed session 进入训练记录列表/详情、phase2 score explanation、Journey outcome、边界扫描和 runtime 依赖契约。
- Phase 7 realtime training-record ruff：`cd backend && ruff check src/common/services/runtime_outcome_projection.py src/sales_trainer/services/training_record_service.py src/sales_trainer/services/training_journey_service.py src/sales_trainer/services/phase2_projection_service.py src/sales_trainer/api.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_phase2_projection.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_newcomer_training_path_boundary.py`：通过。
- Phase 7/Phase 2 training-record 契约回归：`cd backend && pytest --no-cov tests/contract/test_sales_trainer_phase2_contract.py -q`：5 passed，1 warning。
- Phase 7 realtime learner start API：`cd backend && pytest --no-cov tests/unit/test_sales_trainer_realtime_roleplay_start.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_phase2_projection.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_runtime_dependency_contract.py tests/integration/test_newcomer_training_journey_api.py tests/contract/test_sessions.py tests/contract/test_sales_trainer_phase2_contract.py -q`：55 passed，1 warning；覆盖 learner-only enter 权限、无 active revision fail-closed、provider not ready fail-closed、common session 创建权威、`voice_policy_snapshot.external_binding` 冻结、runtime 边界扫描、Journey/training-record/session 契约回归。
- Phase 7 realtime learner start ruff：`cd backend && ruff check src/common/services/external_session_start.py src/common/services/practice_session_service.py src/sales_trainer/permissions.py src/sales_trainer/api.py src/sales_trainer/schemas.py src/sales_trainer/services/realtime_roleplay_start_service.py tests/unit/test_sales_trainer_realtime_roleplay_start.py`：通过。
- Phase 7/8 realtime learner 前端入口：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx' 'src/app/admin/sales-trainer/analytics/page.test.tsx' 'src/lib/sales-trainer/module-path.test.ts'`：4 files / 22 tests passed；覆盖 learner 首页 realtime `next_action` start 成功跳转 practice、start 失败显示 error code/trace_id、active revision fail-closed、admin analytics 和 module-path 回归。
- Phase 7/8 realtime learner 前端静态检查：`cd web && npx eslint 'src/app/(dashboard)/sales-trainer/page.tsx' 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx' src/lib/api/domains/sales-trainer.ts src/lib/api/types.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 7/8 realtime admin training-record list/detail 前端契约：`cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/page.test.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'`：2 files / 9 tests passed；覆盖列表展示实时对练、点击进入 `/admin/sales-trainer/training-records/realtime_roleplay_session/{id}`，以及 `audio_submission`、`quiz_attempt`、`ai_coach_session`、`realtime_roleplay_session` 四类合法详情均调用统一 API，实时对练 raw snapshot 展示 `newcomer_realtime_roleplay_v1`，未知 record type 仍 fail-closed 不请求。`cd web && npx eslint 'src/app/admin/sales-trainer/training-records/page.tsx' 'src/app/admin/sales-trainer/training-records/page.test.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx' src/lib/api/types.ts src/lib/sales-trainer/admin-display.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/lib/api/types.ts web/src/lib/sales-trainer/admin-display.ts web/src/app/admin/sales-trainer/training-records/page.test.tsx web/src/app/admin/sales-trainer/training-records/'[recordType]'/'[recordId]'/page.tsx web/src/app/admin/sales-trainer/training-records/'[recordType]'/'[recordId]'/page.test.tsx`：通过。
- Phase 5/8 前端 Journey 首页第一切片：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx' 'src/lib/sales-trainer/module-path.test.ts'`：3 files / 16 tests passed；覆盖 Journey 成功、active revision 缺失 fail-closed、不回退 `/paths` 伪成功、`passed=null` 三态、旧兼容读面 warning 和新人路径 scope。
- Phase 5/8 前端类型/静态检查：`cd web && npx tsc --noEmit`：通过；`cd web && npm run lint`：0 errors，84 existing warnings。
- Phase 8 admin Journey Analytics 前端首切片：`cd web && npx vitest run src/app/admin/sales-trainer/analytics/page.test.tsx`：1 file / 4 tests passed；覆盖成功、错误、空态、部门筛选/刷新。
- Phase 8 admin Journey Analytics 前端静态检查：`cd web && npx eslint src/app/admin/sales-trainer/analytics/page.tsx src/app/admin/sales-trainer/analytics/page.test.tsx src/lib/api/domains/sales-trainer.ts src/lib/api/types.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 9 E2E/CI 研究：`.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/phase9-e2e-ci-gate-plan.md` 已完成并由主 Agent 复核；子代理 Arendt 复核结论一致：先落 deterministic seed + newcomer Playwright smoke，AI Coach 真流式、录音真评分、realtime 真 WS 放后续 release/nightly 或补 deterministic provider seam 后再进 PR gate。
- Phase 9 newcomer seed 校验：`cd backend && .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only`：通过，输出 `verified=True`；`cd backend && ruff check scripts/seed_newcomer_training_path.py`：通过。修复了 seed verify 将 `CANONICAL_NEWCOMER_MODULE_KEYS` 误当必备集合的问题，当前允许 realtime 新旧模块键兼容但必须 disabled。
- Phase 9 newcomer Playwright smoke：`cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 PHASE4_E2E_PROVIDER=local npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1`：3 passed；执行期间 smoke seed 输出 `verified=True`。覆盖 learner Journey active revision/API + 页面真源、商务技巧 seeded article/workbench、admin Journey Analytics API + 页面、realtime disabled 诊断。
- Phase 9 newcomer Playwright 静态检查：`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`cd web && npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --list`：列出 3 tests；`cd web && npx tsc --noEmit`：通过。
- Phase 9 CI gate 首切片：`bash -n scripts/dev-smoke-up.sh scripts/critical-quality-gate.sh`：通过；`git diff --check -- scripts/dev-smoke-up.sh scripts/critical-quality-gate.sh web/tests/e2e/newcomer-training-closed-loop.spec.ts backend/scripts/seed_newcomer_training_path.py .trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/execution-plan.md`：通过。Gate 已显式纳入新人训练 learner 首页、admin analytics、module-path 前端测试、newcomer Playwright smoke，以及 path config、journey、article、material、RBAC、business etiquette、runtime boundary、realtime start 后端核心测试；完整 AI Coach/录音/历史漂移/realtime 真 WS Playwright 矩阵仍待后续。
- Phase 9 AI Coach / 录音 / 历史回放 E2E 复核：子代理 Jason 输出 `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/phase9-ai-audio-history-e2e-plan.md`，主 Agent 复核后采纳最小 deterministic seed 路线；真实 AI Coach 流式、真实 ASR/Deucate、realtime 真 WS 仍保持 release/nightly 或补 deterministic provider seam 后再进 PR gate。
- Phase 9 deterministic audio + AI Coach seed：`backend/scripts/seed_newcomer_training_path.py` 新增幂等录音评分结果和 AI Coach mastered session，并在 `--verify-only` 中证明二者都带 active path revision lineage、非 legacy snapshot、operation log、Journey latest outcome；`cd backend && .venv/bin/python scripts/seed_newcomer_training_path.py --apply`：`created=4 updated=28 verified=True`；`cd backend && .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only`：`created=0 updated=0 verified=True`。
- Phase 9 TrainingRecord 历史回放 API：`TrainingRecordService._serialize_ai_coach_record` 追加 `article_snapshot`、`path_config_snapshot`、`config_snapshot`、`coach_state` 和 prompt 绑定字段，保持 additive contract；后台详情页原始记录可回放 AI Coach 首版 active path module snapshot 与配置快照。
- Phase 9 newcomer Playwright smoke 扩展：`cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 PHASE4_E2E_PROVIDER=local npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1`：4 passed；新增覆盖 Journey 中 PPT 录音和 AI Coach latest outcome、admin training-record list/detail、learner 访问 admin detail 后端 403、learner 录音结果页、admin 原始记录历史快照页。
- Phase 9 静态/聚焦回归：`cd backend && .venv/bin/ruff check scripts/seed_newcomer_training_path.py src/sales_trainer/services/training_record_service.py`：通过；`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- backend/scripts/seed_newcomer_training_path.py backend/src/sales_trainer/services/training_record_service.py web/tests/e2e/newcomer-training-closed-loop.spec.ts .trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/execution-plan.md`：通过。
- Phase 9 后端聚焦回归：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_record_lineage.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_phase2_projection.py`：15 passed，1 warning。直接不带 `--no-cov` 时 15 个用例也全部 passed，但因小范围运行触发仓库全局 coverage fail-under=48 而命令退出 1，非本次功能失败。
- Phase 9 完整关键质量门禁：`bash scripts/critical-quality-gate.sh`：通过。覆盖 secret hygiene scan；smoke bootstrap + newcomer seed `verified=True`；`Web typecheck`；Vitest 20 files / 183 tests；Playwright smoke 9 passed；Playwright newcomer closed-loop 4 passed；Presentation Phase 4 E2E 2 passed；Sales Phase 4 E2E 1 passed；后端核心集成/单元 208 passed；后端 smoke regression 58 passed。该门禁已验证新人训练闭环 seed 被 CI 门禁调用并纳入 Playwright 核心路径。
- Phase 10 学员/角色等级治理后端聚焦：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py tests/unit/common/test_business_rule_config_service.py`：19 passed，1 warning；覆盖 learner/role level policy 缺失 fallback、自定义配置投影、admin list/analytics learner_level/role_level 过滤、team scope 和业务规则 seed/resolve。
- Phase 10 学员/角色等级治理后端 lint：`cd backend && .venv/bin/ruff check src/common/business_rules/defaults.py src/common/business_rules/validators.py src/sales_trainer/services/training_journey_service.py src/sales_trainer/api.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：通过。
- Phase 10 学员/角色等级治理前端验证：`cd web && npx eslint src/app/admin/sales-trainer/analytics/page.tsx src/app/admin/sales-trainer/analytics/page.test.tsx 'src/app/(dashboard)/sales-trainer/page.tsx' 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx' src/lib/api/types.ts src/lib/api/domains/sales-trainer.ts --quiet`、`cd web && npm test -- src/app/admin/sales-trainer/analytics/page.test.tsx 'src/app/(dashboard)/sales-trainer/page.test.tsx' 'src/app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx'`、`cd web && npx tsc --noEmit`：均通过；覆盖 analytics 页面 learner_level/role_level 选项来源和请求透传，以及 learner 首页 role_level DTO 展示。
- Phase 10 admin analytics 阶段/模块过滤后端聚焦：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：12 passed，1 warning；覆盖 `/journeys/analytics?training_stage=...`、`module_key=...`、service filters 回显、AI Coach mastered outcome 投影和 team scope。
- Phase 10 admin analytics 阶段/模块过滤前端验证：`cd web && npm test -- src/app/admin/sales-trainer/analytics/page.test.tsx`：4 passed；`cd web && npx eslint src/app/admin/sales-trainer/analytics/page.tsx src/app/admin/sales-trainer/analytics/page.test.tsx src/lib/api/types.ts src/lib/api/domains/sales-trainer.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；覆盖训练阶段/模块筛选请求透传和刷新保留。
- Phase 10 admin weakness heatmap 聚焦：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q`：12 passed，1 warning；覆盖 service/API `weakness_heatmap` 字段、`module_key + kind` 聚合、AI Coach heatmap passed 投影、module_key 过滤收窄、team scope。`cd backend && .venv/bin/ruff check src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：通过。`cd web && npm test -- src/app/admin/sales-trainer/analytics/page.test.tsx`：4 passed；`cd web && npx eslint src/app/admin/sales-trainer/analytics/page.tsx src/app/admin/sales-trainer/analytics/page.test.tsx src/lib/api/types.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过。历史趋势在后续独立切片中基于 outcome 时间桶闭环，未用单次快照伪造。
- Phase 10 admin Journey Analytics 历史趋势：子代理 Explorer the 7th 只读复核确认当前缺少 `trend_data` 后端契约、前端展示和 E2E 断言；主 Agent 用 CodeGraph/代码复核后新增基于 Journey outcome `completed_at/submitted_at` 的日期桶投影，不从前端快照反推趋势。验证：`cd backend && .venv/bin/ruff check src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py tests/integration/test_newcomer_training_journey_api.py`：通过；`cd backend && PYTEST_ADDOPTS=--no-cov .venv/bin/pytest tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q`：12 passed，1 warning；`cd web && npx eslint src/app/admin/sales-trainer/analytics/page.tsx src/app/admin/sales-trainer/analytics/page.test.tsx src/lib/api/types.ts tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`cd web && npm test -- --run src/app/admin/sales-trainer/analytics/page.test.tsx`：4 passed；`cd web && npx tsc --noEmit`：通过；`bash scripts/dev-smoke-up.sh && cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_REUSE_EXISTING_STACK=1 SMOKE_BACKEND_BASE_URL=http://127.0.0.1:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "admin analytics consumes journey projection" --workers=1`：1 passed，seed `verified=True`，随后 `dev-smoke-stop` 清理。
- Phase 8 admin capability fail-closed 前端聚焦：`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/components/admin/sales-trainer/module-nav.test.tsx src/components/layout/admin-sidebar.test.tsx src/components/layout/admin-shell.test.tsx src/app/admin/sales-trainer/page.test.tsx src/app/admin/sales-trainer/questions/page.test.tsx src/app/admin/sales-trainer/analytics/page.test.tsx`：7 files / 28 tests passed；覆盖 sales-trainer route helper fail-closed、workbench 根路由不误放行全部子路由、module nav sibling 不越权展示、capability 加载失败不泄漏入口、workbench card 按 capability 过滤、questions 403 不落成空态、sidebar/admin-shell/analytics 回归。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/components/admin/sales-trainer/module-nav.tsx src/components/admin/sales-trainer/module-nav.test.tsx src/app/admin/sales-trainer/page.tsx src/app/admin/sales-trainer/page.test.tsx src/app/admin/sales-trainer/questions/page.tsx src/app/admin/sales-trainer/questions/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过。剩余直链页和 mutation 按钮 capability guard 仍待后续统一收口。
- Phase 8 questions 页面级 capability fail-closed：子代理 Explorer the 4th 只读复核确认 `questions*`、`papers*`、`articles*`、`units*`、AI Coach、score standards 等写入口仍缺 page-level/mutation capability guard，主 Agent 先落最小高风险切片。`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/questions/page.test.tsx`：2 files / 10 tests passed；覆盖 path-level capability helper、`/admin/sales-trainer/questions/new` 仅 `manage_questions` 可进入、questions 页面 capability 加载失败或无 `manage_questions` 时不调用题库/分类接口且不展示 AI 出题审核/新建/发布/归档写入口。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/questions/page.tsx src/app/admin/sales-trainer/questions/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/lib/sales-trainer/routes.ts web/src/lib/sales-trainer/routes.test.ts web/src/app/admin/sales-trainer/questions/page.tsx web/src/app/admin/sales-trainer/questions/page.test.tsx`：通过。
- Phase 8 papers/score-standards 页面级 capability fail-closed：`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/questions/page.test.tsx src/app/admin/sales-trainer/papers/page.test.tsx src/app/admin/sales-trainer/score-standards/page.test.tsx`：4 files / 15 tests passed；覆盖 questions 回归、papers 无 `manage_content` 时不调用考卷/历史版本接口且不展示新建/发布/归档/回滚入口、score-standards 无 `manage_content` 时不调用评分标准接口且不展示新建/编辑/发布入口。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/questions/page.tsx src/app/admin/sales-trainer/questions/page.test.tsx src/app/admin/sales-trainer/papers/page.tsx src/app/admin/sales-trainer/papers/page.test.tsx src/app/admin/sales-trainer/score-standards/page.tsx src/app/admin/sales-trainer/score-standards/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/lib/sales-trainer/routes.ts web/src/lib/sales-trainer/routes.test.ts web/src/app/admin/sales-trainer/questions/page.tsx web/src/app/admin/sales-trainer/questions/page.test.tsx web/src/app/admin/sales-trainer/papers/page.tsx web/src/app/admin/sales-trainer/papers/page.test.tsx web/src/app/admin/sales-trainer/score-standards/page.tsx web/src/app/admin/sales-trainer/score-standards/page.test.tsx`：通过。
- Phase 8 articles 页面级 capability fail-closed：`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/articles/page.test.tsx src/app/admin/sales-trainer/articles/import/page.test.tsx`：3 files / 16 tests passed；覆盖文章绑定页无 `manage_content` 时不调用 learning content/article binding 接口且不展示新建文章、保存绑定、编辑章节入口；资料导入页无 `manage_content` 时不调用导入/影响预览/发布接口且不展示 Markdown 上传、生成草稿、确认发布入口。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/articles/page.tsx src/app/admin/sales-trainer/articles/page.test.tsx src/app/admin/sales-trainer/articles/import/page.tsx src/app/admin/sales-trainer/articles/import/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/lib/sales-trainer/routes.ts web/src/lib/sales-trainer/routes.test.ts web/src/app/admin/sales-trainer/articles/page.tsx web/src/app/admin/sales-trainer/articles/page.test.tsx web/src/app/admin/sales-trainer/articles/import/page.tsx web/src/app/admin/sales-trainer/articles/import/page.test.tsx`：通过。
- Phase 8 articles/capabilities 页面级 capability fail-closed：`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/articles/capabilities/page.test.tsx`：2 files / 9 tests passed；覆盖能力点页无 `manage_content` 时不调用商务礼仪能力点快照接口且不展示新增能力点、保存能力点快照、发布入口。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/articles/capabilities/page.tsx src/app/admin/sales-trainer/articles/capabilities/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/app/admin/sales-trainer/articles/capabilities/page.tsx web/src/app/admin/sales-trainer/articles/capabilities/page.test.tsx`：通过。
- Phase 8 units 列表页 capability fail-closed：`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/units/page.test.tsx`：2 files / 10 tests passed；覆盖单元列表页无 `manage_modules` 时不调用训练单元列表、历史版本、回滚接口且不展示新建训练单元、编辑、发布并生效、历史版本入口。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/units/page.tsx src/app/admin/sales-trainer/units/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/app/admin/sales-trainer/units/page.tsx web/src/app/admin/sales-trainer/units/page.test.tsx`：通过。
- Phase 8 units 新建/编辑直链 capability fail-closed：`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/units/page.test.tsx src/app/admin/sales-trainer/units/new/page.test.tsx 'src/app/admin/sales-trainer/units/[unitId]/edit/page.test.tsx'`：4 files / 15 tests passed；覆盖新建/编辑页无 `manage_modules` 时不加载题目、评分 Prompt、材料、单元列表依赖且不开放表单或保存入口；编辑页依赖失败不再伪装成未找到。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/units/page.tsx src/app/admin/sales-trainer/units/page.test.tsx src/app/admin/sales-trainer/units/new/page.tsx src/app/admin/sales-trainer/units/new/page.test.tsx 'src/app/admin/sales-trainer/units/[unitId]/edit/page.tsx' 'src/app/admin/sales-trainer/units/[unitId]/edit/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/app/admin/sales-trainer/units/page.tsx web/src/app/admin/sales-trainer/units/page.test.tsx web/src/app/admin/sales-trainer/units/new/page.tsx web/src/app/admin/sales-trainer/units/new/page.test.tsx 'web/src/app/admin/sales-trainer/units/[unitId]/edit/page.tsx' 'web/src/app/admin/sales-trainer/units/[unitId]/edit/page.test.tsx'`：通过。
- Phase 8 AI Coach 页面级 capability fail-closed：`cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/ai-coach/page.test.tsx`：2 files / 10 tests passed；覆盖 AI Coach 页无 `manage_content`/`manage_prompts` 时不调用配置接口且不展示保存草稿/发布入口。`cd web && npx eslint src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/ai-coach/page.tsx src/app/admin/sales-trainer/ai-coach/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/app/admin/sales-trainer/ai-coach/page.tsx web/src/app/admin/sales-trainer/ai-coach/page.test.tsx`：通过。
- Phase 8 audio/quiz 详情页 mutation capability guard：子代理 Explorer the 5th 只读复核确认高风险详情页 mutation 集中在 `audio-submissions/[submissionId]` 的重试/重评和 `quiz-attempts/[attemptId]` 的历史重评。`cd web && npx vitest run 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx'`：2 files / 8 tests passed；覆盖无 `retry_jobs` 时不展示重试转写/评分且不调用 retry API，无 `regrade_history` 时不展示 audio/quiz 重评面板且不调用 preview/run API。`cd web && npx eslint 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx' 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.tsx' 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片文件>`：通过。
- Phase 8 questions 新建/编辑直链 capability fail-closed：`cd web && npx vitest run src/app/admin/sales-trainer/questions/new/page.test.tsx 'src/app/admin/sales-trainer/questions/[questionId]/edit/page.test.tsx'`：2 files / 5 tests passed；覆盖无 `manage_questions` 时不加载分类/题目详情、不展示新建/编辑表单且不调用 create/update；编辑页依赖失败不再伪装成未找到。`cd web && npx eslint src/app/admin/sales-trainer/questions/new/page.tsx src/app/admin/sales-trainer/questions/new/page.test.tsx 'src/app/admin/sales-trainer/questions/[questionId]/edit/page.tsx' 'src/app/admin/sales-trainer/questions/[questionId]/edit/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片文件>`：通过。
- Phase 8 score-standards 新建/编辑直链 capability fail-closed：`cd web && npx vitest run src/app/admin/sales-trainer/score-standards/page.test.tsx src/app/admin/sales-trainer/score-standards/new/page.test.tsx 'src/app/admin/sales-trainer/score-standards/[id]/edit/page.test.tsx'`：3 files / 6 tests passed；覆盖无 `manage_content` 时不展示评分标准新建/编辑表单、不加载评分标准详情且不调用 create/update；编辑页依赖失败不再伪装成未找到。`cd web && npx eslint src/app/admin/sales-trainer/score-standards/page.tsx src/app/admin/sales-trainer/score-standards/page.test.tsx src/app/admin/sales-trainer/score-standards/new/page.tsx src/app/admin/sales-trainer/score-standards/new/page.test.tsx 'src/app/admin/sales-trainer/score-standards/[id]/edit/page.tsx' 'src/app/admin/sales-trainer/score-standards/[id]/edit/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片文件>`：通过。
- Phase 8 papers 新建/编辑直链 capability fail-closed：`cd web && npx vitest run src/app/admin/sales-trainer/papers/page.test.tsx src/app/admin/sales-trainer/papers/new/page.test.tsx 'src/app/admin/sales-trainer/papers/[paperId]/edit/page.test.tsx'`：3 files / 8 tests passed；覆盖无 `manage_content` 时不加载正式题库/考卷、不展示新建/编辑表单且不调用 create/update；编辑页未找到 paper 不再开放空表单。`cd web && npx eslint src/app/admin/sales-trainer/papers/page.tsx src/app/admin/sales-trainer/papers/page.test.tsx src/app/admin/sales-trainer/papers/new/page.tsx src/app/admin/sales-trainer/papers/new/page.test.tsx 'src/app/admin/sales-trainer/papers/[paperId]/edit/page.tsx' 'src/app/admin/sales-trainer/papers/[paperId]/edit/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片文件>`：通过。

- Phase 8 admin 直链页错误显性化聚焦：`cd web && npx vitest run src/app/admin/sales-trainer/materials/page.test.tsx 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' src/app/admin/sales-trainer/questions/new/page.test.tsx src/app/admin/sales-trainer/units/new/page.test.tsx`：4 files / 12 tests passed；覆盖 materials 403/500/network 不伪装为空材料库且不开放创建/上传壳、audio detail 加载失败不伪装成未找到、questions/new 分类失败不开放题目表单、units/new 任一依赖失败不开放单元表单、四页重试成功恢复。`cd web && npx eslint src/components/admin/sales-trainer/admin-load-error-card.tsx src/app/admin/sales-trainer/materials/page.tsx 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx' src/app/admin/sales-trainer/questions/new/page.tsx src/app/admin/sales-trainer/units/new/page.tsx src/app/admin/sales-trainer/materials/page.test.tsx 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' src/app/admin/sales-trainer/questions/new/page.test.tsx src/app/admin/sales-trainer/units/new/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片文件>`：通过。
- Phase 6 AI Coach active revision fail-closed：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_ai_coach.py tests/unit/test_sales_trainer_ai_coach_chat.py -q`：84 passed，1 warning；覆盖 AI Coach v1 无 active revision 拒绝、模块未配置 AI Coach 拒绝、chat creator 在 runtime 前拒绝 draft-only path 且不落库，并回归既有 AI Coach prompt/config/scoring 行为。`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q`：12 passed，1 warning；回归 AI Coach/Journey 聚合与 newcomer journey API，并新增 mastered session 进入 learner journey 和 admin analytics heatmap 的 API 集成断言。`cd backend && .venv/bin/ruff check src/sales_trainer/services/ai_coach_session_service.py src/sales_trainer/services/ai_coach_chat_session_creator.py src/sales_trainer/ai_coach_api.py tests/unit/test_sales_trainer_ai_coach.py tests/unit/test_sales_trainer_ai_coach_chat.py tests/integration/test_newcomer_training_journey_api.py`：通过。`cd backend && .venv/bin/mypy src/sales_trainer/services/ai_coach_session_service.py src/sales_trainer/services/ai_coach_chat_session_creator.py src/sales_trainer/ai_coach_api.py`：未通过，mypy 跟随依赖暴露 162 个既有类型问题，集中在 SQLAlchemy Column 推断、AI/common llm service 和缺失 `langchain_anthropic` stub；本切片未把 mypy 作为通过证据，需后续单独治理门禁基线。`git diff --check -- <本切片文件>`：通过。
- Phase 6 AI Coach training-record detail/not_mastered 后端证据：子代理 Explorer the 2nd 只读复核确认最小守门点是 `backend/tests/contract/test_sales_trainer_phase2_contract.py` 与 `backend/tests/unit/test_sales_trainer_phase2_projection.py`。`cd backend && .venv/bin/pytest --no-cov tests/contract/test_sales_trainer_phase2_contract.py::test_ai_coach_training_record_detail_should_expose_lineage_audit_and_remediation tests/unit/test_sales_trainer_phase2_projection.py::test_ai_coach_in_progress_record_requires_continuation tests/unit/test_sales_trainer_phase2_projection.py::test_ai_coach_not_mastered_record_projects_remediation_and_snapshot -q`：3 passed，1 warning；覆盖统一详情 API 回传 AI Coach lineage、article/config/coach/prompt snapshot、operation log、effective_score、score_explanation、ability_profile、remediation，以及列表态 not_mastered remediation。`cd backend && .venv/bin/pytest --no-cov tests/contract/test_sales_trainer_phase2_contract.py tests/unit/test_sales_trainer_phase2_projection.py -q`：14 passed，1 warning；回归统一训练记录三类记录、realtime 记录和 phase2 投影。`cd backend && .venv/bin/ruff check tests/contract/test_sales_trainer_phase2_contract.py tests/unit/test_sales_trainer_phase2_projection.py`：通过；`git diff --check -- <本切片文件>`：通过。
- Phase 6 AI Coach admin detail 前端快照：子代理 Explorer the 3rd 只读复核确认 detail 页面仅 raw JSON 展示 article/config/coach/prompt/mastery 快照，且缺 loading/error/invalid recordType 测试；本切片新增 `AI Coach 快照` 专属只读卡片。`cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'`：1 file / 7 tests passed；覆盖统一详情 API、AI Coach article/config/coach/prompt/path/mastery/trace 快照显性展示、loading、API error、非法 recordType fail-closed 不请求。`cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/page.test.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'`：2 files / 8 tests passed；回归列表到详情入口。`cd web && npx eslint 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片文件>`：通过。
- Phase 9 AI Coach 快照进入 newcomer Playwright smoke：`cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 PHASE4_E2E_PROVIDER=local npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1` 首次运行 3 passed / 1 failed，失败原因是新断言文本与 raw JSON 同时匹配导致 Playwright strict mode violation；改为 exact 文本断言后重跑：4 passed，smoke seed 输出 `verified=True`，并自动停止 backend/frontend smoke stack。新增覆盖 admin training-record detail 中 `AI Coach 快照` 卡片、已掌握状态、文章标题、active path revision、seed trace_id 与原始 snapshot fallback 同屏可见。`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`git diff --check -- web/tests/e2e/newcomer-training-closed-loop.spec.ts`：通过。
- Phase 9 受限 manager 权限不足 Playwright：`backend/scripts/seed_newcomer_training_path.py` 新增幂等 `newcomer.training.seed.manager@example.com` / `training_manager` smoke 账号；`web/tests/e2e/newcomer-training-closed-loop.spec.ts` 新增 E2E 断言：后端 `/admin/sales-trainer/capabilities` 仅授予 `manage_questions/view_records`，直接读取 `/admin/newcomer-training/papers` 返回 403，`/admin/sales-trainer/papers` 不请求考卷资源且不展示“新建考卷”，`/admin/sales-trainer/questions` 仍展示题库管理入口。验证：`bash scripts/dev-smoke-up.sh && cd web && SMOKE_REUSE_EXISTING_STACK=1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts -g "restricted manager" --workers=1; ... dev-smoke-stop`：1 passed；完整 `newcomer-training-closed-loop.spec.ts` 重跑：5 passed，seed 输出 `verified=True`；`cd backend && ruff check scripts/seed_newcomer_training_path.py`、`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`、`cd web && npx tsc --noEmit` 均通过。
- Phase 9 商务礼仪小测提交闭环：`TrainingRecordService` 新增 `business_etiquette_quiz_attempt` 独立记录类型，admin detail API allowlist、Pydantic/TS DTO、Phase2 score explanation/remediation、默认 business rule remediation 配置、前端详情页 raw payload 与“商务礼仪小测”标签同步补齐；`BusinessEtiquetteQuizService.submit_attempt()` 修复为 `flush` 后记录 operation log，避免 target_id 为空导致 admin detail 无法回放审计日志。验证：`cd backend && PYTEST_ADDOPTS=--no-cov pytest tests/unit/test_business_etiquette_quiz_service.py tests/unit/test_sales_trainer_phase2_projection.py tests/contract/test_sales_trainer_phase2_contract.py -q`：20 passed，1 warning；`cd backend && ruff check <本切片后端文件>`：通过；`cd web && npx eslint <本切片前端文件> --quiet && npx tsc --noEmit && npm test -- --run 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'`：Vitest 1 file / 9 tests passed；`bash scripts/dev-smoke-up.sh && cd web && SMOKE_REUSE_EXISTING_STACK=1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1; ... dev-smoke-stop`：6 passed，seed 输出 `verified=True`。
- Phase 9 AI Coach deterministic stream 失败兜底：子代理 Explorer the 9th/10th 只读复核确认后端缺 `_guarded()` typed error/timeout 与 streaming disabled SSE 契约单测，前端缺 learner AI Coach stream recoverable error Playwright；主 Agent 用 CodeGraph/源码复核后补最小测试。验证：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_ai_coach_chat.py -q`：57 passed，1 warning；`cd backend && .venv/bin/ruff check src/sales_trainer/services/ai_coach_chat_stream_service.py tests/unit/test_sales_trainer_ai_coach_chat.py`：通过；`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；首次 Playwright 目标用例因错误文案同时出现在 banner 和对话区触发 strict mode violation，收窄 locator 后重跑：`bash scripts/dev-smoke-up.sh && cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_REUSE_EXISTING_STACK=1 SMOKE_BACKEND_BASE_URL=http://127.0.0.1:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "learner AI Coach stream surfaces recoverable errors" --workers=1; ... dev-smoke-stop`：1 passed，smoke seed 输出 `verified=True`。覆盖 SSE `event/data` 格式、service error/timeout recoverable error、streaming disabled 可见错误，以及 learner AI Coach 页面消费 deterministic stream 后展示可恢复错误和“新开一局”恢复入口。
- Phase 9 历史漂移回放 deterministic 证据：子代理 Explorer the 11th/12th 只读复核确认现有代码返回持久化快照，但缺“active 配置漂移后仍回放旧快照”的反向证据；主 Agent 用 CodeGraph/源码复核后让 seed 在冻结音频评分 `prompt_snapshot` 后给当前评分 Prompt 写入漂移哨兵，并在 verify、API JSON、admin detail 页面和 Playwright 中断言历史记录只含冻结哨兵、不泄漏当前漂移哨兵。验证：`cd backend && .venv/bin/python scripts/seed_newcomer_training_path.py --apply && .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only`：`created=0 updated=34 verified=True` + `created=0 updated=0 verified=True`；`cd backend && .venv/bin/ruff check scripts/seed_newcomer_training_path.py src/sales_trainer/services/training_record_service.py`：通过；`cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_record_lineage.py tests/unit/test_sales_trainer_phase2_projection.py tests/contract/test_sales_trainer_phase2_contract.py -q`：17 passed，1 warning；`cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'`：10 passed；`cd web && npx eslint 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx' tests/e2e/newcomer-training-closed-loop.spec.ts --quiet && npx tsc --noEmit`：通过；`bash scripts/dev-smoke-up.sh && cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_REUSE_EXISTING_STACK=1 SMOKE_BACKEND_BASE_URL=http://127.0.0.1:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "seeded audio and AI Coach outcomes are replayable" --workers=1; ... dev-smoke-stop`：1 passed，smoke seed 输出 `verified=True`。
- Phase 9 录音 deterministic service-path 真评分：子代理 Explorer the 13th/14th 只读复核确认 `AudioSubmissionService.process_submission()` 已具备转写、评分、日志和读模型闭环，缺口是 seed 仍手工写 transcript/score 且 E2E 缺结构化证据。主 Agent 用 CodeGraph/源码复核后将 `seed_newcomer_training_path.py` 的 E2E 录音结果改为注入 deterministic ASR/scorer，并通过 `AudioSubmissionService.create_submission/process_submission` 生成 transcript、score、`audio_transcription_*`、`audio_scoring_*` 日志；verify 和 Playwright 断言 `transcript.provider/raw_payload.source`、`score_result.prompt_hash/deucate_model/raw_response.source/error_code`、operation log 链路和历史 prompt snapshot。验证：`cd backend && .venv/bin/ruff check scripts/seed_newcomer_training_path.py && .venv/bin/python scripts/seed_newcomer_training_path.py --apply && .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only`：通过，`created=0 updated=32 verified=True` + `created=0 updated=0 verified=True`；`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_services.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_record_lineage.py -q`：34 passed，1 warning；`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`bash scripts/dev-smoke-up.sh && cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_REUSE_EXISTING_STACK=1 SMOKE_BACKEND_BASE_URL=http://127.0.0.1:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "seeded audio and AI Coach outcomes are replayable" --workers=1; test_rc=$?; cd ..; bash scripts/dev-smoke-stop.sh; exit $test_rc`：1 passed，smoke seed 输出 `verified=True`。
- Phase 9 realtime 真实 `/ws/sales` deterministic local provider E2E：子代理 Explorer the 15th/16th 只读复核确认现有 `RealtimeRoleplayStartService`、common `ExternalSessionStartService`、`sales_bot` `/ws/sales`、`StepFunRealtimeHandler` 与 `RuntimeOutcomeProjectionService` 具备真实链路，缺口是 seed 未发布 enabled realtime binding、Journey API schema 丢 `next_action`、smoke runtime profile/case/ruleset/KB 资产不完整、training-record detail 未顶层暴露 `external_binding`。主 Agent 用 CodeGraph/源码复核后修复：seed 从 published units 回填 active path payload，发布 `realtime_roleplay` runtime binding；`TrainingJourneyModuleProgress` schema 保留 `next_action` 并新增 API 集成测试；smoke bootstrap 幂等创建 local StepFun runtime profile、published scoring ruleset、knowledge base、published case item，并把模板 curriculum plan 收敛为合法空 stages；training-record realtime DTO 顶层暴露 `external_binding` 且保留 raw snapshot。验证：`cd backend && .venv/bin/ruff check scripts/bootstrap_smoke_practice_evidence.py src/sales_trainer/services/training_record_service.py tests/unit/test_sales_trainer_phase2_projection.py && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_phase2_projection.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q && .venv/bin/python scripts/bootstrap_smoke_practice_evidence.py --email admin@qoder.ai && .venv/bin/python scripts/seed_newcomer_training_path.py --apply && .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only`：ruff 通过，22 passed，seed `verified=True`；`PHASE4_E2E_PROVIDER=local PHASE4_E2E_PROVIDER_SCRIPT=sales-provider-script.v1.json STEPFUN_API_KEY=phase4-local-e2e bash scripts/dev-smoke-up.sh && cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_REUSE_EXISTING_STACK=1 SMOKE_BACKEND_BASE_URL=http://127.0.0.1:3444/api/v1 PHASE4_E2E_PROVIDER=local PHASE4_E2E_PROVIDER_SCRIPT=sales-provider-script.v1.json STEPFUN_API_KEY=phase4-local-e2e npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "realtime roleplay starts from active path" --workers=1; test_rc=$?; cd ..; bash scripts/dev-smoke-stop.sh; exit $test_rc`：1 passed，覆盖 start API、浏览器 WebSocket `/ws/sales`、final transcript、TTS、`session_ended`、Journey outcome 和 admin training-record binding 回放。
- Phase 9 真实第三方 provider release/nightly gate：子代理 Explorer the 17th 只读复核确认 local provider E2E 已进主门禁，但真实第三方 provider gate/skip 分类未落地；主 Agent 复核 `critical-quality-gate.sh`、`.github/workflows/release-truth-gate.yml`、`newcomer-training-closed-loop.spec.ts` 和 CodeGraph provider seam 后，扩展唯一 canonical gate：`CRITICAL_GATE_MODE=newcomer-real-provider` 会在缺 `STEPFUN_API_KEY` 或仍使用 placeholder 时生成 `.sisyphus/evidence/newcomer-real-provider-gate.json`，classification=`credential_missing`；设置 `NEWCOMER_REAL_PROVIDER_REQUIRED=1` 时缺凭证硬失败；凭证可用时以非 local provider 启动 smoke stack，跑 newcomer realtime start、真实 `/ws/sales` lifecycle、Journey outcome 和 admin record projection；若 StepFun 握手返回 HTTP 401，则写入 `classification=upstream_auth_rejected`、`model=step-audio-2.3` 和 `realtime_url_configured`，避免把上游授权问题伪装成未执行。`.github/workflows/release-truth-gate.yml` 新增 schedule/workflow_dispatch job 和 artifact 上传，不影响 PR 默认 deterministic gate。验证：`bash -n scripts/critical-quality-gate.sh`：通过；`CRITICAL_GATE_MODE=newcomer-real-provider bash scripts/critical-quality-gate.sh`：可生成 `credential_missing` classified skip；2026-06-28 使用测试 key 强制执行后到达 StepFun 上游，返回 HTTP 401 并生成 `upstream_auth_rejected` evidence。
- Phase 5/7 realtime Journey 完成规则收口：子代理 Mill the 17th 只读复核指出 realtime completed outcome 的 `passed=null` 会使 required module 无法让 Journey 总状态进入 `passed`。主 Agent 复核 `docs/api-contract/sales-trainer.md` 后确认不能把 realtime `passed` 伪装为 true，因此新增 `completion_satisfied` DTO：`completion_rule="passed"` 仍必须 `passed=true`，`completion_rule="submitted"` 只要求有受治理 outcome 记录。验证：`cd backend && .venv/bin/ruff check src/common/services/runtime_outcome_projection.py src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_training_journey_service.py`：通过；`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py -q`：9 passed，1 warning；`cd backend && .venv/bin/pytest --no-cov tests/integration/test_newcomer_training_journey_api.py -q`：5 passed，1 warning；`cd web && npx tsc --noEmit`：通过；`git diff --check -- ...`：通过。
- Phase 8 admin 子页 capability fail-closed 收口：子代理 Mill the 17th 只读复核指出 `questions/quiz-preview` 和 `questions/drafts` 直链页未走统一 capability gate，且 quiz preview 混用 learner learning-units API。主 Agent 修复为：两个子页先读取 `api.admin.salesTrainer.getCapabilities()` 并用 `isSalesTrainerAdminPathAllowedForCapabilities` fail-closed；无权限或 capability 加载失败时不请求草稿、分类、能力点、小测预览等业务接口，也不展示刷新/生成/审核写入口；新增 admin `GET /admin/newcomer-training/business-etiquette/learning-units`，返回 active path revision 的小单元配置和能力点但不读取任何学员进度，前端预览页改走 admin API。验证：`cd backend && .venv/bin/ruff check src/sales_trainer/business_etiquette_api.py src/sales_trainer/services/business_etiquette_learning_service.py tests/integration/test_business_etiquette_learning_units_api.py`：通过；`cd backend && .venv/bin/pytest --no-cov tests/integration/test_business_etiquette_learning_units_api.py -q`：3 passed，1 warning；`cd web && npx vitest run src/app/admin/sales-trainer/questions/quiz-preview/page.test.tsx src/app/admin/sales-trainer/questions/drafts/page.test.tsx`：2 files / 7 tests passed；`cd web && npx eslint src/app/admin/sales-trainer/questions/quiz-preview/page.tsx src/app/admin/sales-trainer/questions/quiz-preview/page.test.tsx src/app/admin/sales-trainer/questions/drafts/page.tsx src/app/admin/sales-trainer/questions/drafts/page.test.tsx src/lib/api/domains/newcomer-training.ts src/lib/api/domains/sales-trainer.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 learner 首页 Journey-only 收口：CodeGraph 复核 learner 首页链路后确认成功态仍展示 `/paths` 兼容入口卡片；主 Agent 修复为首屏只请求 `api.salesTrainer.getJourney()`，成功态不再读取 `listUnits/listPaths`，失败态不再回退旧 catalog。验证：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/page.test.tsx'`：1 file / 7 tests passed；`cd web && npx eslint 'src/app/(dashboard)/sales-trainer/page.tsx' 'src/app/(dashboard)/sales-trainer/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 结果页配置异常显性化：子代理 Explorer the 18th 只读复核指出 `quiz/result` 的 AI Coach 入口路径读取失败和 `audio/result` 的训练单元读取失败仍会静默折叠为 `null`；主 Agent 修复为结果主内容继续展示，同时输出配置诊断，不再把缺失入口/通过线伪装为正常无配置。验证：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx'`：2 files / 12 tests passed；`cd web && npx eslint 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.tsx' 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 admin 文章绑定态真源收口：子代理 Explorer the 19th 只读复核指出 admin `articles` 和 `paths` 仍混用 learner `getModuleArticle` 读取绑定态。主 Agent 复核后没有新增不必要 admin GET article API，而是复用现有 admin `path-config` 权威读口：`articles/page.tsx` 与 `paths/page-data.ts` 均从 `api.admin.newcomerTraining.getPathConfig()` 的 `business_skills.learning_content_id` 派生绑定态；未绑定、绑定内容缺失、path-config 失败均显式展示。验证：`cd web && npx vitest run src/app/admin/sales-trainer/articles/page.test.tsx src/app/admin/sales-trainer/paths/page.test.tsx src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx`：4 files / 16 tests passed；`cd web && npx eslint src/app/admin/sales-trainer/articles/page.tsx src/app/admin/sales-trainer/articles/page.test.tsx src/app/admin/sales-trainer/paths/page-data.ts src/app/admin/sales-trainer/paths/page.test.tsx src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片文件>`：通过。
- Phase 3/8 provider readiness + fallback diagnostics 展示矩阵：子代理 Explorer the 20th 只读复核确认后端已有发布校验但缺稳定展示投影，前端 config center 只展示绑定/版本而未展示 readiness/fallback/preview。主 Agent 补齐后端 `path-config.diagnostics.realtime_provider_readiness` 与 `publish_preview.impact_scope.realtime_provider_readiness`，前端类型和配置中心消费 `fallback_applied/fallback_reason`、发布预览成功/typed failure、真实 `realtime_roleplay` provider readiness；ready=false 仍 fail-closed，不降级为占位成功。验证：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_config_revision.py -q`：14 passed，1 warning；`cd backend && .venv/bin/ruff check src/sales_trainer/services/path_config_service.py tests/unit/test_newcomer_training_path_config_revision.py`：通过；`cd web && npx vitest run src/lib/sales-trainer/config-center.test.ts src/app/admin/sales-trainer/paths/page.test.tsx`：2 files / 18 tests passed；`cd web && npx eslint src/lib/sales-trainer/config-center.ts src/lib/sales-trainer/config-center-types.ts src/components/admin/sales-trainer/path-config-center.tsx src/components/admin/sales-trainer/path-config-center-copy.ts src/app/admin/sales-trainer/paths/page-data.ts src/app/admin/sales-trainer/paths/page.test.tsx src/app/admin/sales-trainer/paths/page.test-data.ts src/lib/api/domains/newcomer-training.ts src/lib/api/types.ts src/lib/api/types/newcomer-training.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 loading/error fail-closed 页面级切片：子代理 Explorer the 21st 只读复核指出 `settings/page.tsx` 并行拉配置、路径修订、录音和评分结果但没有页面级 loading/failure UI，慢请求会呈现空白等待；主 Agent 同时修复已发现的 `questions/categories` 直链权限缺口。`settings` 页新增 `isLoading`、错误卡和 retry；`questions/categories` 页先校验 capability，无 `manage_questions` 或 capability 加载失败时不请求分类、不显示新建分类表单，分类接口失败时不渲染“暂无分类”伪空态。验证：`cd web && npx vitest run src/app/admin/sales-trainer/settings/page.test.tsx src/app/admin/sales-trainer/questions/categories/page.test.tsx src/lib/sales-trainer/routes.test.ts`：3 files / 13 tests passed；`cd web && npx eslint src/app/admin/sales-trainer/settings/page.tsx src/app/admin/sales-trainer/settings/page.test.tsx src/app/admin/sales-trainer/questions/categories/page.tsx src/app/admin/sales-trainer/questions/categories/page.test.tsx src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- web/src/app/admin/sales-trainer/settings/page.tsx web/src/app/admin/sales-trainer/settings/page.test.tsx web/src/app/admin/sales-trainer/questions/categories/page.tsx web/src/app/admin/sales-trainer/questions/categories/page.test.tsx`：通过。
- Phase 3/8 provider health 入口接入：子代理 Explorer the 22nd 只读复核确认仓库已有 `/support/runtime` 与 `support/runtime_status.py` 运行时健康视图，但 sales-trainer 配置治理页缺少直达入口；主 Agent 复核后把 realtime provider readiness 的配置中心 issue/operational check 指向 `/support/runtime`，并在 settings 页头与“路径配置诊断”面板增加运行时健康入口。该切片不宣称完成真实 descriptor registry、provider 启停、审计或回滚管理。验证：`cd web && npx vitest run src/lib/sales-trainer/config-center.test.ts src/app/admin/sales-trainer/settings/page.test.tsx`：2 files / 12 tests passed；`cd web && npx eslint src/lib/sales-trainer/config-center.ts src/lib/sales-trainer/config-center.test.ts src/app/admin/sales-trainer/settings/page.tsx src/app/admin/sales-trainer/settings/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 3/8 settings realtime provider 诊断源对齐：子代理 Explorer the 23rd 只读复核确认 `operational-diagnostics.test.ts` 缺 `realtime_roleplay` 回归覆盖，并指出 settings 诊断只读 `path.modules[*].runtime_binding` 会与配置中心优先读取 `diagnostics.realtime_provider_readiness` 分叉。主 Agent 补齐 `realtime_roleplay` 状态映射，ready/not-ready 均指向 `/support/runtime`，并抽出共享 `realtime-provider-readiness` helper，使 settings 运维诊断和 config center 都优先使用后端 diagnostics 投影、其次回退 runtime binding 快照。验证：`cd web && npx vitest run src/lib/sales-trainer/config-center.test.ts src/lib/sales-trainer/operational-diagnostics.test.ts src/app/admin/sales-trainer/settings/page.test.tsx`：3 files / 15 tests passed；`cd web && npx eslint src/lib/sales-trainer/config-center.ts src/lib/sales-trainer/config-center.test.ts src/lib/sales-trainer/operational-diagnostics.ts src/lib/sales-trainer/operational-diagnostics.test.ts src/lib/sales-trainer/realtime-provider-readiness.ts src/app/admin/sales-trainer/settings/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 loading/error fail-closed 第二轮：子代理 Explorer the 24th 只读扫描指出音频结果页、admin 音频列表和 quiz result 仍存在失败伪空态风险；主 Agent 同步复核并先修三个高收益切片：operation-logs 直链页先校验 `view_logs`，无权或 capability 加载失败时不请求日志接口；admin audio-submissions 列表接口失败时渲染错误卡和重试，不再显示“暂无录音记录”；learner audio result submission 读取失败时渲染“语音作业结果加载失败”并可重试，不再与“结果不存在”共用空态。验证：`cd web && npx vitest run src/app/admin/sales-trainer/operation-logs/page.test.tsx src/app/admin/sales-trainer/audio-submissions/page.test.tsx 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx'`：3 files / 13 tests passed；`cd web && npx eslint src/app/admin/sales-trainer/operation-logs/page.tsx src/app/admin/sales-trainer/operation-logs/page.test.tsx src/app/admin/sales-trainer/audio-submissions/page.tsx src/app/admin/sales-trainer/audio-submissions/page.test.tsx 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx' 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 loading/error fail-closed 第三轮：主 Agent 继续复核 Explorer the 24th 指出的 quiz result 缺口，修复 learner `quiz/result/[attemptId]`：`getQuizAttempt` 失败时渲染“做题结果加载失败”和重试按钮，不再与真实缺失共用“做题结果不存在”空态；重试成功后恢复做题结果和通过状态。验证：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx'`：1 file / 6 tests passed；`cd web && npx eslint 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.tsx' 'src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 loading/error fail-closed 第四轮：主 Agent 复核 audit 点名的后台录音详情 `passed=null` 后确认当前代码已有 `待判定` 测试覆盖，未重复修改；随后修复 admin `quiz-attempts/[attemptId]` 详情页：`getQuizAttempt` 失败时复用 `AdminLoadErrorCard` 展示“做题结果加载失败”和重试按钮，真实缺失才显示“未找到做题结果”。验证：`cd web && npx vitest run 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx'`：1 file / 4 tests passed；`cd web && npx eslint 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.tsx' 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 training-records capability 前置：子代理 Explorer the 25th 只读巡检指出 `training-records/page.tsx` 挂载即请求训练记录，未先确认权限。主 Agent 复核 `routes.ts` 后按 `view_records` 路由能力收口：页面先读取 `/admin/sales-trainer/capabilities`，能力失败或无 `view_records` 时不请求 `listTrainingRecords`，列表接口失败时渲染可重试错误卡而不是“暂无训练记录”。验证：`cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/page.test.tsx'`：1 file / 3 tests passed；`cd web && npx eslint 'src/app/admin/sales-trainer/training-records/page.tsx' 'src/app/admin/sales-trainer/training-records/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 score-results capability 前置：子代理 Explorer the 25th 只读巡检指出 `score-results/page.tsx` 挂载即请求做题结果和录音评分结果，未先确认权限。主 Agent 复核后按 `view_records` 路由能力收口：页面先读取 capabilities，能力失败或无 `view_records` 时不请求 `listQuizAttempts/listScoreResults`；两个列表读取失败时保留错误提示并渲染错误行，不再落成“暂无做题结果/暂无评分结果”。验证：`cd web && npx vitest run 'src/app/admin/sales-trainer/score-results/page.test.tsx'`：1 file / 3 tests passed；`cd web && npx eslint 'src/app/admin/sales-trainer/score-results/page.tsx' 'src/app/admin/sales-trainer/score-results/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 detail capability 前置：子代理 Explorer the 25th 只读巡检指出 `audio-submissions/[submissionId]` 和 `training-records/[recordType]/[recordId]` 详情页直接请求详情，未先确认查看权限。主 Agent 复核后按 `view_records` 收口：两个详情页先读取 capabilities，能力失败或无 `view_records` 时不请求 `getAudioSubmission/getTrainingRecordDetail`；训练记录详情 API 失败时复用可重试错误卡，不再落成“未找到训练记录”；录音详情仍保留 `retry_jobs/regrade_history` 对重试和历史重评的细粒度控制。验证：`cd web && npx vitest run 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'`：2 files / 17 tests passed；`cd web && npx eslint 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx' 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 剩余高价值直链 capability 前置：子代理 Gauss the 26th 只读复核确认 `materials/paths/settings/analytics` 等页仍存在“先请求业务 API，再显示错误”的 fail-closed 缺口；主 Agent 用 CodeGraph 复核 `routes.ts` 后新增共享 `useSalesTrainerAdminRouteAccess`，并接入 `materials`、`paths`、`settings`、`audio-submissions` 列表和 `analytics` 页面；`paths` workflow 增加 `enabled` 参数，权限未确认/失败时不加载 path-config；`/admin/sales-trainer/analytics` 补入统一路由表并由 `view_records` 控制。验证：首次 `npm test -- --run web/...` 因工作目录在 `web/` 导致文件匹配失败，改用 `src/...` 路径重跑；`cd web && npm test -- --run src/lib/sales-trainer/routes.test.ts src/app/admin/sales-trainer/materials/page.test.tsx src/app/admin/sales-trainer/audio-submissions/page.test.tsx src/app/admin/sales-trainer/settings/page.test.tsx src/app/admin/sales-trainer/paths/page.test.tsx src/app/admin/sales-trainer/analytics/page.test.tsx`：6 files / 34 tests passed；`cd web && npx eslint <本切片 13 个前端文件>`：通过；`cd web && npx tsc --noEmit`：通过。曾尝试 `npm run lint -- --file ...`，因 flat config 不支持 `--file` 参数失败，随后改用 `npx eslint <files>`。
- Phase 2/3 模型配置持久化审计：子代理 Explorer the 27th 只读复核确认 `model_configs.py` 的 CRUD/test/tts-preview 只有 `logger.info`，测试缺持久化审计断言；主 Agent 复核后未采用 sales_trainer 专属 `OperationLog`，改用平台级 `SystemLog`。新增统一审计 helper，create/update/delete/persisted test/inline test/tts-preview 写入 actor、target、trace_id、source、before/after、success/status、latency 和安全快照，密钥只记录 `api_key_configured`。验证：`cd backend && pytest --no-cov tests/integration/test_admin_model_configs_api.py -q`：4 passed，1 warning；`cd backend && ruff check src/admin/api/model_configs.py tests/integration/test_admin_model_configs_api.py`：通过；`git diff --check -- backend/src/admin/api/model_configs.py backend/tests/integration/test_admin_model_configs_api.py .trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/execution-plan.md`：通过。曾从仓库根运行 `pytest --no-cov tests/integration/test_admin_model_configs_api.py -q`，因根目录 `tests` 是指向 `backend/tests` 的 symlink，conftest 计算到不存在的 `root/src` 触发 `OSError: Starting path not found`；按项目测试路径改为 `cd backend && pytest tests/...` 后通过。
- Phase 9/10 后端 mypy/coverage 质量门禁：子代理 Explorer the 28th 只读复核确认 canonical gate 两处后端 pytest 使用 `--no-cov`，且全仓 mypy 仍会被历史 SQLAlchemy/第三方 stub 噪音阻断；主 Agent 建立 newcomer 后端窄门禁基线并修复本链路 mypy 错误。验证：`bash -n scripts/critical-quality-gate.sh`：通过；`cd backend && venv/bin/python -m pytest -c pyproject.toml -o addopts='-v --import-mode=importlib' tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py tests/unit/common/test_business_rule_config_service.py --cov=sales_trainer --cov=common.business_rules --cov-report=term-missing --cov-fail-under=45 -q`：30 passed，1 warning，coverage 45.28%；`cd backend && venv/bin/python -m mypy --config-file pyproject.toml --follow-imports=skip src/common/business_rules src/common/services/runtime_outcome_projection.py src/common/services/external_session_start.py src/sales_trainer/services/training_journey_service.py src/sales_trainer/services/realtime_roleplay_start_service.py`：Success，8 source files；`cd backend && ruff check src/common/business_rules/validators.py src/common/services/runtime_outcome_projection.py src/common/services/external_session_start.py src/sales_trainer/services/realtime_roleplay_start_service.py src/sales_trainer/services/training_journey_service.py`：通过。
- Phase 9 新鲜生成完整闭环 E2E：主 Agent 用 CodeGraph/源码复核后不新增生产测试后门，改为 `NEWCOMER_E2E_FRESH_RUN_ID` 驱动 smoke seed 生成 fresh PPT 录音评分和 AI Coach mastered session，并在 Playwright 中通过真实商务礼仪 quiz API 新鲜提交 attempt；seed 同时发布 ready `sales_trainer.realtime_provider.registry`，避免 realtime start 只靠 path binding 而 provider registry 仍默认 disabled。验证：`cd backend && ruff check scripts/seed_newcomer_training_path.py && NEWCOMER_E2E_FRESH_RUN_ID=fresh-local-20260628024907 PHASE4_E2E_PROVIDER=local STEPFUN_API_KEY=phase4-local-e2e .venv/bin/python scripts/seed_newcomer_training_path.py --apply`：通过，`created=4 updated=33 verified=True`；`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`git diff --check -- backend/scripts/seed_newcomer_training_path.py web/tests/e2e/newcomer-training-closed-loop.spec.ts scripts/critical-quality-gate.sh`：通过；`cd web && PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_REUSE_EXISTING_STACK=1 SMOKE_BACKEND_BASE_URL=http://127.0.0.1:3444/api/v1 SMOKE_WEB_BASE_URL=http://localhost:3445 NEWCOMER_E2E_FRESH_RUN_ID=fresh-local-20260628024907 PHASE4_E2E_PROVIDER=local STEPFUN_API_KEY=phase4-local-e2e npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "fresh current-run" --workers=1`：1 passed；同环境完整 `newcomer-training-closed-loop.spec.ts --workers=1`：9 passed，覆盖 learner 首页、商务技巧、AI Coach fallback、商务礼仪提交、fresh current-run、admin analytics、权限 fail-closed、历史回放和实时 `/ws/sales`。
- Phase 9 AI Coach 真实 LLM provider gate：`bash -n scripts/critical-quality-gate.sh`：通过；`git diff --check -- scripts/critical-quality-gate.sh scripts/README.md .github/workflows/release-truth-gate.yml web/tests/e2e/newcomer-training-closed-loop.spec.ts .trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/execution-plan.md`：通过；`cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`LLM_API_KEY= OPENAI_API_KEY= CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1 bash scripts/critical-quality-gate.sh`：退出 0，生成 `.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json`，其中 `classification=credential_missing`、`credential_skip_allowed=true`；`LLM_API_KEY= OPENAI_API_KEY= CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=0 bash scripts/critical-quality-gate.sh`：按预期退出 1 并写入 `credential_skip_allowed=false` evidence；`cd web && npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "AI Coach real provider stream" --list`：列出 1 条 gate 用例；2026-06-28 使用真实 LLM provider 执行通过，`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json` 为 `status=passed`、`classification=executed`、`model=deepseek-chat`，`.sisyphus/evidence/newcomer-ai-coach-real-provider-runtime-audit.json` 记录 `llm_runtime.provider=openai`、`base_url=https://api.deepseek.com/v1`、`source=model_config`、`model_config_id` 非空、`is_configured=true`，并断言证据不含 `api_key`。
- Phase 3 path payload 保存校验补强：`cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_config_revision.py -q`：16 passed，1 warning；覆盖 canonical module_key 必须匹配 canonical module_type，包含 `business_skills -> article_exam` 与 disabled `realtime_roleplay_placeholder -> realtime_placeholder`，保存 working revision 前拒绝结构错配。`cd backend && .venv/bin/ruff check scripts/seed_newcomer_training_path.py src/sales_trainer/services/path_config_models.py tests/unit/test_newcomer_training_path_config_revision.py`：通过。
- Phase 9 seed verify baseline/fresh 并存稳定性：首次 `cd backend && .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only` 暴露本地已有 fresh current-run 记录时 Journey latest 指向 fresh audio，而 verify 在缺少 `NEWCOMER_E2E_FRESH_RUN_ID` 时仍期待 baseline audio 的误红；已修复为先完整校验 baseline 历史回放，再在未显式 run id 时自动选择一组完整的 fresh audio + AI Coach 记录作为 Journey latest 期望。复跑 `cd backend && .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only`：`created=0 updated=0 verified=True`。
- Phase 8 quiz attempt detail capability-first：子代理 Explorer the 29th 只读巡检指出 `quiz-attempts/[attemptId]` 详情页在 capability 未确认前并行请求 `getQuizAttempt`，与 audio/training-record detail 的 fail-closed 模式不一致；主 Agent 复核后修复为先按 `view_records` 校验路由能力，能力加载中、能力接口失败或无权时不请求详情、不渲染对象内容，并把隐藏 `/admin/sales-trainer/quiz-attempts/*` 详情路由纳入 `view_records` 判定但不加入导航。验证：`cd web && npx vitest run 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx' src/lib/sales-trainer/routes.test.ts`：2 files / 14 tests passed；`cd web && npx eslint 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.tsx' 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx' src/lib/sales-trainer/routes.ts src/lib/sales-trainer/routes.test.ts --quiet`：通过；`cd web && npx tsc --noEmit`：通过；`git diff --check -- <本切片 4 个文件>`：通过。
- Phase 8 learner active brief 与草稿页失败态：子代理 Explorer the 30th 只读巡检指出 `questions/drafts`、`papers`、`units` 列表页仍有 API 失败伪空态风险；主 Agent 先修最高收益的 `questions/drafts`，新增页面级 `AdminLoadErrorCard` 和重试，业务数据加载失败时不展示“暂无草稿”或空编辑器。同时复核后端 `/sales-trainer/units/{unit_id}/brief` 已由 active path effective config 生成后，删除 learner 录音上传页对 legacy `/paths` 的并行读取，使录音入口只信任 unit brief；旧 paths 接口失败不再影响标题、说明、材料和通过线。验证：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/admin/sales-trainer/questions/drafts/page.test.tsx'`：2 files / 8 tests passed；`cd web && npx eslint 'src/app/admin/sales-trainer/questions/drafts/page.tsx' 'src/app/admin/sales-trainer/questions/drafts/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 papers/units 列表失败伪空态：继续收口 Explorer the 30th 指出的相邻残留，`papers` 和 `units` 列表页业务 API 失败时复用 `AdminLoadErrorCard` 显示可重试阻断错误，不再同时渲染“暂无考卷/暂无训练单元”；重试成功后恢复真实列表。验证：`cd web && npx vitest run 'src/app/admin/sales-trainer/papers/page.test.tsx' 'src/app/admin/sales-trainer/units/page.test.tsx'`：2 files / 9 tests passed；`cd web && npx eslint 'src/app/admin/sales-trainer/papers/page.tsx' 'src/app/admin/sales-trainer/papers/page.test.tsx' 'src/app/admin/sales-trainer/units/page.tsx' 'src/app/admin/sales-trainer/units/page.test.tsx' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 低频旧路由和导航配置异常：子代理 Explorer the 31st 只读巡检未发现高置信 P1 残留，指出两个 P2：旧 learner `learn/[unitId]` 仍并行读取 `/paths`/`/units`，模块内导航 capability 加载失败静默消失。主 Agent 复核后修复：`learn/[unitId]` 改为先读取当前单元并校验 learner chapter/content 配置，缺配置时终止且不请求学习内容或 legacy paths/units；成功路径也不再依赖 legacy paths/units。`SalesTrainerAdminModuleNav` 在内部 capability 请求失败时显示可重试错误条，仍不泄漏无权入口。验证：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/learn/[unitId]/page.test.tsx' src/components/admin/sales-trainer/module-nav.test.tsx`：2 files / 5 tests passed；`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' 'src/app/(dashboard)/sales-trainer/learn/[unitId]/page.test.tsx' 'src/app/admin/sales-trainer/questions/drafts/page.test.tsx' 'src/app/admin/sales-trainer/papers/page.test.tsx' 'src/app/admin/sales-trainer/units/page.test.tsx' src/components/admin/sales-trainer/module-nav.test.tsx`：6 files / 22 tests passed；`cd web && npx eslint <本轮 12 个前端文件> --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 8 business-skills 低频目录专项：子代理 Explorer the 32nd 只读巡检确认 `articles` 与 `score-prompts` 未发现高置信残留，指出 business-skills 两处缺口。主 Agent 复核后修复：考试页删除跨单元 `fallbackPaperId` 伪成功，当前 `unitId` 无 `exam_paper_id` 即显示“暂未绑定商务技巧考卷”，且不请求文章、进度或考卷；学习页 `listPaths()` 解析 AI Coach 入口失败时显示“AI 教练入口暂不可用”，不再静默隐藏关键入口。验证：`cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx' 'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx'`：2 files / 18 tests passed；`cd web && npx eslint 'src/app/(dashboard)/sales-trainer/business-skills/exam/page.tsx' 'src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx' 'src/app/(dashboard)/sales-trainer/business-skills/page.tsx' 'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx' 'src/app/(dashboard)/sales-trainer/business-skills/use-business-skills-workbench.ts' --quiet`：通过；`cd web && npx tsc --noEmit`：通过。
- Phase 3/8 active revision 真源与 diagnostics 契约复核：子代理 Explorer the 33rd 只读复核 `web/src/lib/sales-trainer/config-center*.ts`、`module-path*.ts` 及直接消费者，未发现旧 `/paths`/`/units` fallback 伪成功、`fallback_applied/fallback_reason` 展示不一致或 active revision 被 helper 绕过的高置信残留；子代理 Explorer the 34th 只读复核后端 `path_config_service/path_service/path_config_api`，确认 learner `list_paths_for_user()` 只走 `active_projection()`，无 active revision 返回空，admin `get_config()` 的 legacy backfill 只作为迁移诊断视图。主 Agent 随后把后端 `NewcomerPathConfigResponse.diagnostics` 从宽 `dict` 收紧为 typed schema，并同步前端 `NewcomerPathConfigResponse` 类型，锁住 `source/fallback_applied/fallback_reason/realtime_provider_readiness/permission_policy/high_risk_actions`；同时修正 API 契约文档中 `diagnostics.resource_type` 为后端权威常量 `newcomer_training_path`。验证：`cd backend && pytest --no-cov tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py -q`：34 passed，1 warning；`cd backend && ruff check src/sales_trainer/schemas.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py`：通过；`cd web && npx vitest run src/lib/sales-trainer/config-center.test.ts src/lib/sales-trainer/config-center-audio-bindings.test.ts src/lib/sales-trainer/operational-diagnostics.test.ts src/app/admin/sales-trainer/paths/page.test.tsx src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx src/app/admin/sales-trainer/articles/page.test.tsx`：6 files / 31 tests passed；`cd web && npx eslint src/lib/api/types.ts src/lib/sales-trainer/realtime-provider-readiness.ts src/lib/sales-trainer/config-center.test.ts src/lib/sales-trainer/config-center-audio-bindings.test.ts src/lib/sales-trainer/operational-diagnostics.test.ts src/app/admin/sales-trainer/paths/page.test-data.ts src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx src/app/admin/sales-trainer/articles/page.test.tsx --quiet`：通过；`cd web && npx tsc --noEmit`：通过；前置复核 `cd backend && pytest --no-cov tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py -q`：33 passed，1 warning；`cd backend && ruff check src/sales_trainer/services/path_config_service.py src/sales_trainer/path_config_api.py src/sales_trainer/services/path_config_models.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py`：通过。
- `cd backend && pytest --no-cov tests/unit/test_newcomer_training_path_permissions.py tests/integration/test_newcomer_training_path_rbac_api.py tests/integration/test_business_etiquette_quiz_api.py tests/unit/test_config_asset_import_export_service.py tests/integration/test_config_asset_import_export_api.py -q`：34 passed，5 warnings。
- Phase 2/3/4 后端聚焦回归：`cd backend && pytest --no-cov tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_article_api.py tests/integration/test_newcomer_training_path_config_api.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/unit/test_newcomer_training_path_permissions.py -q`：55 passed，1 warning。
- Phase 2/3/4 ruff 聚焦检查：`cd backend && ruff check src/sales_trainer/services/material_service.py src/sales_trainer/api.py src/sales_trainer/article_api.py src/sales_trainer/services/article_binding_service.py src/sales_trainer/path_config_api.py src/sales_trainer/services/path_config_service.py src/sales_trainer/schemas.py tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_article_api.py tests/integration/test_newcomer_training_path_config_api.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/unit/test_newcomer_training_path_permissions.py`：通过。
- Phase 4 音频评分 prompt snapshot 单测：`cd backend && pytest --no-cov tests/unit/test_sales_trainer_services.py -q`：25 passed，1 warning；覆盖提交快照含完整 prompt payload、提交后修改 prompt 行再处理仍使用提交时快照、旧 path projection 测试改为 active revision 发布路径。
- Phase 4 音频/材料回放聚焦回归：`cd backend && pytest --no-cov tests/unit/test_sales_trainer_services.py tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_audio_lineage.py -q`：39 passed，1 warning。
- Phase 4 prompt snapshot ruff：`cd backend && ruff check src/sales_trainer/services/audio_submission_service.py src/sales_trainer/services/material_service.py tests/unit/test_sales_trainer_services.py`：通过。
- Phase 4 dead data 诊断研究：`.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/phase4-dead-data-diagnostics.md` 已完成并由主 Agent 复核；当前切片覆盖其中 P1 最小只读诊断范围，历史回填/生产数据修复仍列为暂停条件。
- Phase 4 dead data 诊断接口测试：`cd backend && pytest --no-cov tests/integration/test_newcomer_training_path_config_api.py -q`：17 passed，1 warning；覆盖权限 fail-closed、archived 学习内容引用、legacy audio prompt snapshot、published material current version 缺失、orphan material。
- Phase 4 dead data 诊断 ruff：`cd backend && ruff check src/sales_trainer/services/newcomer_dead_data_diagnostics_service.py src/sales_trainer/path_config_api.py src/sales_trainer/schemas.py tests/integration/test_newcomer_training_path_config_api.py`：通过。
- Phase 4 dead data 诊断编译检查：`cd backend && python3 -m py_compile src/sales_trainer/services/newcomer_dead_data_diagnostics_service.py`：通过。
- `cd backend && ruff check src/sales_trainer/permissions.py src/sales_trainer/business_etiquette_api.py src/sales_trainer/services/business_etiquette_quiz_service.py src/admin/api/config_assets.py src/admin/config_assets/export_service.py tests/unit/test_newcomer_training_path_permissions.py tests/integration/test_newcomer_training_path_rbac_api.py tests/integration/test_business_etiquette_quiz_api.py tests/unit/test_config_asset_import_export_service.py tests/integration/test_config_asset_import_export_api.py`：通过。
- `cd backend && pytest --no-cov tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_sales_trainer_path_projection_ai_coach.py tests/integration/test_newcomer_training_path_config_api.py -q`：30 passed，1 warning。
- `cd backend && ruff check src/sales_trainer/schemas.py src/sales_trainer/services/path_service.py src/sales_trainer/services/path_config_service.py src/sales_trainer/services/path_config_models.py src/sales_trainer/path_config_api.py src/sales_trainer/ai_coach_admin_api.py tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_sales_trainer_path_projection_ai_coach.py tests/integration/test_newcomer_training_path_config_api.py`：通过。
- `cd backend && pytest --no-cov tests/integration/test_newcomer_training_path_config_api.py tests/unit/test_sales_trainer_ai_coach.py -q`：43 passed，1 warning。
- `cd backend && ruff check src/sales_trainer/services/path_config_service.py tests/integration/test_newcomer_training_path_config_api.py`：通过。
- `cd backend && pytest --no-cov tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_material_governance.py -q`：5 passed，1 warning。
- `cd backend && ruff check src/sales_trainer/api.py src/sales_trainer/services/material_service.py tests/integration/test_newcomer_training_path_material_api.py`：通过。
- `cd web && npx vitest run src/lib/sales-trainer/module-path.test.ts src/components/sales-trainer/sales-trainer-module-grid.test.tsx src/lib/sales-trainer/config-center.test.ts src/app/'(dashboard)'/sales-trainer/page.test.tsx src/app/admin/sales-trainer/paths/page.test.tsx src/app/'(dashboard)'/sales-trainer/audio/result/'[submissionId]'/page.test.tsx src/app/admin/sales-trainer/audio-submissions/'[submissionId]'/page.test.tsx`：7 files / 41 tests passed。
- `cd web && npm run lint`：0 errors，84 existing warnings。
- `cd web && npx tsc --noEmit`：通过。
- 合并后端聚焦回归：`cd backend && pytest --no-cov tests/unit/test_newcomer_training_path_permissions.py tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_sales_trainer_path_projection_ai_coach.py tests/unit/test_sales_trainer_ai_coach.py tests/integration/test_newcomer_training_path_rbac_api.py tests/integration/test_newcomer_training_path_config_api.py tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_material_governance.py tests/unit/test_config_asset_import_export_service.py tests/integration/test_config_asset_import_export_api.py -q`：103 passed，5 warnings。
- 合并后端 ruff：`cd backend && ruff check src/sales_trainer src/admin/api/config_assets.py src/admin/config_assets/export_service.py tests/unit/test_newcomer_training_path_permissions.py tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_sales_trainer_path_projection_ai_coach.py tests/unit/test_sales_trainer_ai_coach.py tests/integration/test_newcomer_training_path_rbac_api.py tests/integration/test_newcomer_training_path_config_api.py tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_material_governance.py tests/unit/test_config_asset_import_export_service.py tests/integration/test_config_asset_import_export_api.py`：通过。
- `git diff --check`：通过。
- 说明：直接运行聚焦 pytest 且不加 `--no-cov` 时，所有用例通过但会被仓库全局 coverage fail-under 拦截；当前切片用 `--no-cov` 记录功能验证，最终 Phase 9 仍需跑完整门禁。

## 子代理 Goal

### 子代理 A：后端闭环架构/真源

- 目标：复核 active path revision、TrainingJourney、AI Coach、realtime binding 边界。
- 允许修改：`research/phase0-backend-journey-source-of-truth.md`。
- 禁止范围：业务代码、迁移、`sales_bot/training_runtime` 实现。
- 验证方式：CodeGraph + 文件路径证据。
- 完成条件：输出阶段任务、风险、验证命令、暂停条件。
- 暂停条件：发现 realtime 接入方式必须产品/架构决策。

### 子代理 B：权限与对象级授权

- 目标：复核材料、quiz、article-progress、logs/settings、manager roles、regrade scope。
- 允许修改：`research/phase0-permissions-rbac.md`。
- 禁止范围：代码和权限策略修改。
- 验证方式：CodeGraph + RBAC 测试矩阵。
- 完成条件：每个权限问题给出修复点和测试。
- 暂停条件：角色等级/部门范围语义无法由代码判断。

### 子代理 C：前端契约与 UI/UX

- 目标：复核 API DTO、capability 五层、learner 看板、admin analytics、吞错和硬兜底。
- 允许修改：`research/phase0-frontend-contract-ux.md`。
- 禁止范围：业务代码、dev server、样式修改。
- 验证方式：CodeGraph + route/API 路径证据。
- 完成条件：给出前端任务拆解和测试计划。
- 暂停条件：产品需要确认 learner 等级枚举或分析指标口径。

### 子代理 D：测试与 CI

- 目标：复核现有测试覆盖和缺失门禁，设计完整 Playwright E2E。
- 允许修改：`research/phase0-test-ci-gate.md`。
- 禁止范围：代码、CI、耗时全量测试。
- 验证方式：测试文件/脚本/CI 配置证据。
- 完成条件：输出测试矩阵和阶段验证命令。
- 暂停条件：需要真实 provider 凭证或外部账号。

### 子代理 E：配置治理、内容资产、历史回放

- 目标：复核配置校验、publish preview、fallback、provider readiness、prompt/material/paper/audio snapshot、dead data。
- 允许修改：`research/phase0-config-assets-history.md`。
- 禁止范围：代码、迁移、真实数据操作。
- 验证方式：CodeGraph + 配置/资产服务证据。
- 完成条件：输出可执行任务和配置化分级。
- 暂停条件：需要历史数据回填策略或破坏性迁移。

## 计划检查清单

- [x] 已读取 `AGENTS.md`、`CLAUDE.md`、PRD、审计总账、API 契约、架构、backend/frontend spec index。
- [x] 已确认 CodeGraph 索引存在，并用 CLI 分析关键链路。
- [x] 已启动第一批子代理做 Phase 0 证据复核。
- [x] 子代理报告全部完成并被主 Agent 复核。
- [x] P0/P1/P2 问题全部有明确阶段归属和验证方式。
- [x] Phase 1 契约/ADR 通过计划检查：必须先更新 realtime/TrainingJourney/三类等级/active revision/AI Coach 契约。
- [x] Phase 2-9 实现前确认不会遗漏权限、配置、审计、状态、数据流通、前后端契约、UI/UX、测试和回滚。

## Phase 0 Gate 结论

- Gate 状态：通过，可以进入 Phase 1 契约/ADR 冻结；不得跳过 Phase 1 直接实现 realtime。
- 已确认 P0/P1 都有归属：P0 归 Phase 1/3/7，P1 分布在 Phase 2-9。
- 推荐第一批实现代理：先并行推进 Phase 1 文档契约和 Phase 2 后端权限修复；Phase 3 配置治理可先做 path 校验器和 AI Coach GET fail-closed，避免后续 UI/E2E 建在伪配置上。
- 暂不建议启动 UI/analytics 大改：必须等 Phase 3/5 的 DTO 和状态策略稳定后再做，否则会复制当前前端推断问题。

## 需要人工决策的候选项

- 学员等级首版枚举与来源：用户表字段、组织分层、后台配置，还是训练数据计算。
- realtime 接入方式：runtime binding 的最小可行 API 与 training_runtime/sales_bot 的边界。
- TrainingJourney 是否新增表，还是先做 read model 投影。
- 历史数据回填策略：哪些可回填 revision，哪些标记 legacy only。
- 真实 provider smoke 的凭证来源、secret 轮换和是否在人工 release dispatch 时启用 `NEWCOMER_REAL_PROVIDER_REQUIRED=1`。

## Phase 9 Final Gate 记录

- 时间：2026-06-28 17:00 CST。
- 证据文件：`.sisyphus/evidence/task-9-quality-gate.txt`。
- 结论：`bash scripts/critical-quality-gate.sh` 通过。
- 覆盖结果：
  - Secret hygiene scan：通过，448 files scanned；`evidence/` 与 `.sisyphus/evidence/` 已纳入 JWT/token 扫描。
  - Web typecheck：通过，`cd web && npx tsc --noEmit`。
  - Vitest coverage gate：20 files / 183 tests passed；coverage summary 非空。
  - Playwright smoke E2E：9 passed。
  - Playwright newcomer closed-loop E2E：9 passed / 1 skipped；AI Coach real provider 用例在 full gate 中跳过，由 focused gate 单独执行。
  - AI Coach real provider focused gate：1 passed，`.sisyphus/evidence/task-9-newcomer-ai-coach-real-provider-gate.txt` 记录 Playwright 通过；`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json` status=`passed`、classification=`executed`、model=`deepseek-chat`；runtime audit JSON 记录实际 provider/base_url/model，且 `source=model_config`、`model_config_id` 非空。
  - Playwright presentation Phase 4：2 passed。
  - Playwright sales Phase 4：1 passed；已将 auth/login 冷态样本和 explainability lineage 轮询样本从 sales core API p95 中拆分并记录到 evidence，避免功能门禁被非核心异步等待误杀。
  - Backend newcomer coverage gate：后续最新 2026-06-29 02:57 复验为 36 passed，coverage 45.72%，达到 `NEWCOMER_BACKEND_COV_FAIL_UNDER=45`。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend full gate：225 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
- 本轮门禁修复记录：
  - `scripts/critical-quality-gate.sh`：Web typecheck/Vitest 前置到 smoke 栈启动前，避免 `.next/dev/types` 被 dev server 半写入；新增 Backend ruff 与 Web lint gate；full/provider transcript 分离，避免 provider 专项失败覆盖 deterministic full gate 证据。
  - `backend/tests/integration/test_replay_api.py`：`test_sales_session_replay_unlocks_after_background_finalization` 显式隔离 `PHASE4_E2E_PROVIDER` / transcript 环境，防止 Phase4 local provider 开关绕过注入的失败 mock，确保该用例继续验证增强报告失败后的 canonical evidence 解锁路径。
  - `web/tests/e2e/newcomer-training-closed-loop.spec.ts`：受限管理员用例只过滤 dashboard 登录背景的三条既有 403；sales-trainer content-management fail-closed 断言保持严格。
  - `web/tests/e2e/sales-phase4.spec.ts`：拆分 auth/core/lineage API timing 样本，core p95 继续硬断言并把各类样本写入 manifest。
  - `backend/tests/integration/test_newcomer_training_path_material_api.py`：测试 fixture 对齐 `elevator_pitch` 的 canonical `audio_scoring_group` 和 `duration_options` 发布契约。
- 剩余外部项：
  - Realtime real provider gate 已执行到真实 StepFun 上游，`.sisyphus/evidence/newcomer-real-provider-gate.json` 当前为 `status=failed`、`classification=upstream_auth_rejected`、`model=step-audio-2.3`；需更换或授权可用 `STEPFUN_API_KEY` 后运行 `CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 STEPFUN_REALTIME_MODEL=step-audio-2.3 bash scripts/critical-quality-gate.sh`。

## Completion Audit 记录

- 时间：2026-06-28 16:11 CST。
- 复核方式：主 Agent 对照 PRD、`research/audit-synthesis.md`、本执行计划、CodeGraph 调用链结果、`.sisyphus/evidence/task-9-quality-gate.txt`、provider 专项 transcript 和 provider JSON evidence 做最终完成度审计。
- 已验证闭环：
  - P0/P1/P2 审计问题均在“审计问题归属总账”中有处理结果、阶段归属和验证证据。
  - learner active path revision 已成为唯一真源；无 active revision 时 fail-closed，不再用 catalog/unit backfill 伪成功。
  - 三类等级进入 Journey、权限/筛选/analytics DTO 和管理端视图；真实枚举来源属于产品治理项。
  - AI Coach 和 realtime 已进入 TrainingJourney、training-record、admin analytics、审计/快照与 Playwright deterministic 闭环。
  - 权限后端 fail-closed、配置可校验/发布预览/回滚、内容资产 snapshot-first/只读回放、前后端契约 typed diagnostics 均有测试或门禁证据。
  - `bash scripts/critical-quality-gate.sh` 已通过，覆盖后端、前端、Playwright、coverage、mypy、smoke 和新人训练 E2E。
- 未计作完成的外部项：
  - Realtime 真实 StepFun provider gate 已执行但 evidence 为 `upstream_auth_rejected` HTTP 401，需可用 StepFun 凭证/授权。
- 需人工/产品决策项：
  - 学员等级首版枚举与来源：后台配置、用户字段、组织分层或训练数据计算。
  - 历史生产数据回填策略：哪些记录可回填 path/prompt/material revision，哪些只能标记 `legacy_snapshot_only` 或 `regrade_unavailable`。
- 结论：代码与 deterministic gate 已覆盖本轮可在本地闭环的审计问题；真实第三方 provider 路径和生产历史回填不应被伪装为已执行，需在具备凭证/产品决策后按上方命令和策略补跑。

## 2026-06-28 16:35 Completion Audit 增量修复

- 主 Agent 复核 Goodall/Herschel/Jason 子代理报告后补齐以下缺口：
  - audio 新提交不再在无 active path 时落入 legacy unit config；`AudioSubmissionService.create_submission()` 使用 active revision effective config，`/sales-trainer/units/{unit_id}/brief` 同步 fail-closed。
  - 新增 `learner_unit_access` 对象级授权：普通 learner 的 audio/quiz 提交必须命中当前 active path projection 且 level 未 locked；active path 外或 locked 均返回 `[SALES_TRAINER_UNIT_NOT_FOUND]`，不创建提交/attempt。
  - `TrainingJourneyService.list_admin_journeys()` 改为先构建/过滤 journey 后分页；`get_admin_analytics()` 使用过滤后的全集做统计，避免 SQL `limit/offset` 先截断导致第二页匹配学员或默认 500 后统计漏算。
  - AI Coach runtime audit 增加 `llm_provider_response_received` provider response 事件，记录 latency/chunk/text 指标和 `fallback_used=false`，不记录正文或 key；真实 focused gate 已复跑并写入 `actual_runtime_audit.llm_runtime.provider_response`，且来源为 DB `ModelConfig`。
  - `scripts/critical-quality-gate.sh` 增加 `ruff check src` 和 `npm run lint` 静态门禁；没有把历史 test 目录 ruff 债务强塞进新人训练门禁。
  - `scripts/check_secret_hygiene.py` 在 Finding 采集时脱敏 excerpt，失败 stderr 和 JSON report 不再输出原始 secret。
- 本轮验证：
  - `cd backend && ruff check src`：通过。
  - `cd backend && pytest --no-cov tests/unit/test_sales_trainer_ai_coach_chat.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_secret_hygiene_scan.py -q`：92 passed。
  - `CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider bash scripts/critical-quality-gate.sh`：1 Playwright passed；evidence `status=passed`、`classification=executed`、`source=model_config`、`model_config_id` 非空、provider response `fallback_used=false`。
  - `CRITICAL_GATE_MODE=newcomer-real-provider bash scripts/critical-quality-gate.sh`：执行到 StepFun 上游后 HTTP 401，evidence `status=failed`、`classification=upstream_auth_rejected`、`model=step-audio-2.3`。
  - `python3 scripts/check_secret_hygiene.py --report .sisyphus/evidence/secret-scan-report.json`：450 files scanned，通过。
  - `CRITICAL_GATE_MODE=full PHASE4_E2E_PROVIDER=local STEPFUN_API_KEY=phase4-local-e2e bash scripts/critical-quality-gate.sh`：通过；该早期切片已被最新 2026-06-29 02:57 full gate 覆盖复验，当前基线为 secret scan 448 files scanned，Backend ruff 通过，Web typecheck 通过，Web lint 0 errors/85 warnings，Vitest 27 files/246 tests passed，Playwright smoke 9 passed，newcomer E2E 11 passed/1 skipped，presentation Phase 4 2 passed，sales Phase 4 1 passed，Backend newcomer coverage 36 passed/45.72%，mypy 8 source files 通过，Backend full gate 331 passed，Backend smoke regression 58 passed。
- 未计作完成：
  - StepFun 真实 realtime provider 仍需可用且授权 `step-audio-2.3` 的 key 后复跑。
  - 历史生产数据回填策略仍需产品/运维决策。

## 2026-06-28 17:12 外部凭证复验写入

- 本地配置写入：
  - 已将用户提供的 StepFun / DeepSeek 测试凭证写入本地忽略文件 `backend/.env`；仓库受 Git 跟踪文件未写入明文密钥。
  - `STEPFUN_REALTIME_MODEL` 保持 `step-audio-2.3`，并已在 `.env.example` / `backend/.env.example` 中作为默认示例模型。
- StepFun Realtime 复验：
  - 命令：`set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_NAME=stepfun_realtime NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh`。
  - 结果：exit code `1`。
  - evidence：`.sisyphus/evidence/newcomer-real-provider-gate.json`。
  - 结论：`status=failed`、`classification=upstream_auth_rejected`、`model=step-audio-2.3`、`realtime_url_configured=true`；后端 typed error 为 `[STEPFUN_UPSTREAM_REJECTED]`，StepFun 在 WebSocket 握手阶段返回 HTTP 401。
  - 主 Agent 与只读子代理复核：URL、model、Bearer auth 链路清晰，失败发生在 `session.update` 前；额外握手矩阵显示多个 Realtime 模型均 HTTP 401，因此更像 StepFun key/账号 Realtime 权限或 model 授权问题。
- AI Coach / DeepSeek 复验：
  - 命令：`set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh`。
  - 结果：exit code `0`，1 Playwright passed。
  - evidence：`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json`、`.sisyphus/evidence/newcomer-ai-coach-real-provider-runtime-audit.json`。
  - 结论：`status=passed`、`classification=executed`、`provider=openai`、`model=deepseek-chat`、`actual_runtime_audit.llm_runtime.source=model_config`、`model_config_id` 非空、`provider_response.status=received`、`fallback_used=false`；证据 JSON 不含明文 `api_key`。
- 文档同步：
  - 已更新 `external-verification-runbook.md`、`final-verification-report.md`、`audit-closure-matrix.md`，明确 DeepSeek/AI Coach 已真实通过，StepFun Realtime 仍需外部控制台授权或更换可用 key。

## 2026-06-28 17:35 StepFun Realtime session.update 协议补强

- 要证明什么：
  - 当前 HTTP 401 之前的 URL/header/model 连接链路已可观测；授权放开后，`session.update` 也必须符合 StepFun Realtime 协议，不应因为缺少固定 `modalities` 字段再失败。
- CodeGraph/源码复核：
  - `StepFunTransport.connect()` 负责 `wss://api.stepfun.com/v1/realtime?model=...` 与 `Authorization: Bearer <redacted>`。
  - `StepFunRealtimeHandler._connect_upstream()` 在连接成功后调用 `build_stepfun_session_update_payload()` 发送 `session.update`。
  - 失败证据仍发生在握手阶段，早于 `session.update`；本次补强不是用来掩盖 401，而是提前补齐后续协议字段。
- 实现：
  - `backend/src/training_runtime/stepfun_transport.py` 新增集中常量 `STEPFUN_DEFAULT_SESSION_MODALITIES=("text", "audio")`。
  - `StepFunSessionConfig` 增加默认 `modalities`，`build_stepfun_session_update_payload()` 输出 JSON list。
  - `backend/tests/unit/test_stepfun_transport.py`、`backend/tests/unit/test_stepfun_realtime_handler.py`、`backend/tests/unit/test_stepfun_payload_snapshots.py` 固定 transport、handler 和 snapshot allowlist 的 payload 形状。
- 验证：
  - `cd backend && pytest --no-cov tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_payload_snapshots.py -q`：153 passed，1 warning。
  - `cd backend && ruff check src/training_runtime/stepfun_transport.py tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_payload_snapshots.py`：通过。
- 剩余：
  - StepFun 上游 HTTP 401 仍需外部控制台授权或更换可用 key 才能验证真实音频会话；本地代码已补齐握手前配置链路与握手后 session.update 固定字段。

## 2026-06-28 18:13 Completion Audit 增量闭环

- 要证明什么：
  - AI Coach “首版必过”不再只是 journey/UI 可见，而是成为 path publish/preview 的后端硬门禁。
  - 默认 CI/full gate 必须覆盖 AI Coach 核心后端与管理端前端测试。
  - 配置异常 fail-closed 必须有真实后端 Playwright 证据，而不是只靠 mock。
  - 普通 smoke seed 与显式 fresh-run seed 可以在同一个本地持久数据库中重复执行，不被旧 fresh-run 记录污染。
- 实现：
  - `SalesTrainerPathConfigService._validate_article_exam_module()` 对 enabled `business_skills` 增加 AI Coach 必配校验：缺 `ai_coach`、未启用或缺 `prompt_template_id` 时 publish/preview 返回 `[AI_COACH_NOT_CONFIGURED]`。
  - `scripts/critical-quality-gate.sh` 默认 targets 纳入 AI Coach 后端核心测试和 `web/src/app/admin/sales-trainer/ai-coach/page.test.tsx`。
  - `web/tests/e2e/newcomer-training-closed-loop.spec.ts` 新增真实后端配置异常用例：保存缺 AI Coach working revision 可暂存，但 publish preview 409 fail-closed。
  - 同一 E2E 文件的商务礼仪小测答题 helper 改为题卡内 scoped 选择并断言 input checked，提交使用 `Promise.all([waitForResponse, click])`，消除重复选项文本导致的假等待。
  - `backend/scripts/seed_newcomer_training_path.py` 在普通 baseline 重建时刷新 synthetic audio/AI Coach baseline 的 `created_at/updated_at`；显式 `NEWCOMER_E2E_FRESH_RUN_ID` 仍会在 baseline 后创建 fresh 记录并成为期望最新。
  - 旧发布成功路径测试补齐合法 AI Coach prompt fixture；缺 AI Coach 发布失败路径单独覆盖，避免测试通过依赖旧伪配置。
- 验证：
  - `cd backend && pytest --no-cov tests/integration/test_newcomer_training_path_config_api.py -q`：18 passed。
  - `cd backend && pytest --no-cov tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_payload_snapshots.py -q`：153 passed。
  - `cd backend && pytest --no-cov ...BACKEND_GATE_TARGETS... -q`：315 passed，1 warning。
  - `cd backend && .venv/bin/python -m pytest -c pyproject.toml -o 'addopts=-v --import-mode=importlib' ... --cov-fail-under=45 -q`：该聚焦切片随后进入 full gate；最新 2026-06-29 02:57 newcomer coverage gate 为 36 passed，coverage 45.72%。
  - `cd backend && .venv/bin/python -m mypy --config-file pyproject.toml --follow-imports=skip ...`：8 source files，无错误。
  - `set -a; . backend/.env; set +a; cd backend && PYTHONPATH=src:. .venv/bin/python scripts/seed_newcomer_training_path.py --apply && PYTHONPATH=src:. .venv/bin/python scripts/seed_newcomer_training_path.py --verify-only`：`verified=True`。
  - `cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过。
  - 单条 Playwright：`business etiquette quiz submission enters journey and admin records`：1 passed。
  - 完整门禁：`CRITICAL_GATE_MODE=full PHASE4_E2E_PROVIDER=local STEPFUN_API_KEY=phase4-local-e2e bash scripts/critical-quality-gate.sh`：通过；该早期切片已被最新 2026-06-29 02:57 full gate 覆盖复验，当前基线为 secret scan 448 files scanned，backend ruff 通过，web typecheck 通过，web lint 0 errors/85 warnings，Vitest 27 files/246 tests passed，Playwright smoke 9 passed，newcomer E2E 11 passed/1 skipped，presentation Phase 4 2 passed，sales Phase 4 1 passed，backend coverage 36 passed/45.72%，mypy 8 source files 通过，backend core 331 passed，backend smoke regression 58 passed。
- 未计作完成：
  - StepFun 真实 realtime provider 仍是上游 HTTP 401 / `upstream_auth_rejected`，需要 StepFun 控制台 Realtime/model 授权或更换可用 key。
  - 历史生产数据回填仍需产品/运维确认范围、dry-run、影响条数和回滚策略。

## 2026-06-28 18:31 内容资产治理增量闭环

- 要证明什么：
  - dead data diagnostics 不只是问题列表，还必须成为生产回填前可机器读取的 dry-run 治理输入，明确不会改历史、候选动作、人工决策和回滚语义。
  - 录音评分 Prompt 不只是在发布时留 revision，还必须能列出历史 revision、预览回滚、执行回滚，并保证历史录音成绩不被改写。
- 实现：
  - `NewcomerDeadDataDiagnosticsService.build_report()` 返回 `mode="dry_run"`、`mutates_history=false`、`requires_manual_approval=true`、`candidate_actions`、`manual_decisions` 和 `rollback_plan.reason="diagnostics_only_no_mutation"`。
  - `NewcomerDeadDataDiagnosticsResponse` 增加候选动作、人工决策和 rollback plan DTO；`docs/api-contract/sales-trainer.md` 同步契约。
  - `AudioScorePromptRevisionService` 增加 `list_revisions()`、`preview_rollback()`、`rollback_prompt()`，复用 `SalesTrainerAssetRevisionService.rollback_to_revision()`，回滚只激活既有 published revision 并写 `audio_score_prompt_revision_rolled_back` 审计。
  - 管理端新增：
    - `GET /api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/revisions`
    - `POST /api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/rollback/preview`
    - `POST /api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/rollback`
  - Prompt rollback preview 返回 `historical_submissions_changed=false`、`historical_regrade_required=false`，rollback request 必须带 `reason`。
- 验证：
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_score_prompts.py tests/integration/test_newcomer_training_path_score_prompt_api.py tests/integration/test_newcomer_training_path_config_api.py::test_should_report_newcomer_path_dead_data_diagnostics tests/unit/test_sales_trainer_services.py::test_should_publish_material_version_as_single_current_version tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_material_api.py::test_should_preview_and_rollback_material_version_via_api -q`：9 passed，1 warning。
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/newcomer_dead_data_diagnostics_service.py src/sales_trainer/services/prompt_revision_service.py src/sales_trainer/services/prompt_service.py src/sales_trainer/services/material_service.py src/sales_trainer/api.py src/sales_trainer/schemas.py tests/integration/test_newcomer_training_path_config_api.py tests/integration/test_newcomer_training_path_score_prompt_api.py tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_score_prompts.py tests/unit/test_newcomer_training_path_material_governance.py tests/unit/test_sales_trainer_services.py`：通过。
- 未计作完成：
  - 生产历史回填仍不能自动执行；当前新增的是只读 dry-run 治理输入，不授权批量写生产数据。
  - StepFun 真实 provider 仍受上游授权 401 阻塞。

## 2026-06-28 18:31 材料版本回滚治理补强

- 要证明什么：
  - 材料资产不只支持发布新版本和历史只读回放，还必须能在管理端恢复既有历史版本为 current version，且不改写历史录音提交。
- 实现：
  - `SalesTrainerMaterialService.preview_version_rollback()` 返回 `action="material_version.rollback"`、`mutates_history=false`、`historical_submissions_changed=false`、`historical_replay_preserved=true`、active/working path 引用和 rollback plan。
  - `SalesTrainerMaterialService.rollback_version()` 允许恢复同一材料下 `published` 或 `archived` 历史版本为 current version，归档其他 published version，并写 `material_version_rolled_back` 审计。
  - 管理端新增：
    - `POST /api/v1/admin/sales-trainer/materials/{material_id}/versions/rollback/preview`
    - `POST /api/v1/admin/sales-trainer/materials/{material_id}/versions/rollback`
  - `docs/api-contract/sales-trainer.md` 同步 `SalesTrainerMaterialVersionRollbackPreviewResponse` 和 request 契约。
- 验证：
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_services.py::test_should_publish_material_version_as_single_current_version tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_material_api.py::test_should_preview_and_rollback_material_version_via_api -q`：5 passed，1 warning。
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/material_service.py src/sales_trainer/api.py src/sales_trainer/schemas.py tests/integration/test_newcomer_training_path_material_api.py`：通过。

## 2026-06-28 18:31 商务礼仪历史记录 lineage 补强

- 要证明什么：
  - 商务礼仪小测训练记录不能把缺 `path_revision_id/path_revision_no` 的旧 attempt 伪装成完整 active path lineage。
- 实现：
  - `TrainingRecordService._serialize_business_etiquette_quiz_record()` 改为按 `path_revision_id` 和 `path_revision_no` 判断 `legacy_snapshot_only`。
  - 新数据带 path revision 时仍返回 `legacy_snapshot_only=false`；旧数据缺 lineage 时返回 `legacy_snapshot_only=true`。
- 验证：
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_phase2_projection.py::test_business_etiquette_quiz_attempt_enters_training_records tests/unit/test_sales_trainer_phase2_projection.py::test_legacy_business_etiquette_quiz_attempt_is_marked_legacy -q`：2 passed，1 warning。
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/training_record_service.py tests/unit/test_sales_trainer_phase2_projection.py`：通过。

## 2026-06-28 19:14 训练记录明细筛选补强

- 要证明什么：
  - 管理端训练记录明细列表不只按技术 id 筛选，也能按模块、训练阶段、学员等级和角色等级治理。
  - `training_stage` 必须来自 active path revision 的 TrainingJourney 整体阶段投影，不由前端或单条记录状态推断。
  - `status` 必须作为单条记录原始状态筛选进入管理端，满足按训练阶段和记录状态分别分析。
- 实现：
  - `TrainingRecordService.list_records()` 新增 `module_key`、`training_stage`、`learner_level`、`role_level`、`status` 和 `viewer` 参数。
  - 高阶筛选先按统一记录窗口和权限范围取数，再用 `TrainingJourneyService.get_admin_journey()` 补齐 `training_stage`、`learner_level`、`role_level`，最后按 Journey 上下文与记录 `status` 筛选和分页。
  - `/api/v1/admin/sales-trainer/training-records` 新增同名 query 参数；训练记录 DTO 增加 journey 上下文字段。
  - `web/src/app/admin/sales-trainer/training-records/page.tsx` 新增模块、训练阶段、记录状态、学员等级、角色等级筛选控件，并在表格中展示阶段/等级；模块筛选使用 active path canonical `ppt_explanation`，不混用音频 purpose `ppt_pitch`。
  - `web/src/lib/api/domains/sales-trainer.ts` 与 `web/src/lib/api/sales-trainer.test.ts` 补齐 training-records query string 序列化证据。
  - `docs/api-contract/sales-trainer.md` 同步更新训练记录列表契约和五类记录类型。
- 验证：
  - `cd backend && .venv/bin/pytest --no-cov tests/contract/test_sales_trainer_phase2_contract.py::test_training_records_api_should_forward_journey_and_status_filters tests/unit/test_sales_trainer_phase2_projection.py::test_training_records_filter_by_module_stage_and_levels -q`：2 passed，1 warning；覆盖 FastAPI query 参数转发和 service 层过滤。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_phase2_projection.py::test_business_etiquette_quiz_attempt_enters_training_records tests/unit/test_sales_trainer_phase2_projection.py::test_legacy_business_etiquette_quiz_attempt_is_marked_legacy -q`：2 passed，1 warning。
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/training_record_service.py src/sales_trainer/api.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_phase2_projection.py`：通过。
  - `cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/page.test.tsx' 'src/lib/api/sales-trainer.test.ts'`：2 files / 20 tests passed。
  - `cd web && npx tsc --noEmit`：通过。
  - `cd web && npx eslint 'src/app/admin/sales-trainer/training-records/page.tsx' 'src/app/admin/sales-trainer/training-records/page.test.tsx' 'src/lib/api/domains/sales-trainer.ts' 'src/lib/api/types.ts' 'src/lib/api/sales-trainer.test.ts' --quiet`：通过。

## 2026-06-28 19:23 训练记录移动端表格兜底

- 要证明什么：
  - 管理端训练记录明细表格在窄屏不应被裁切到不可操作；同一份记录 DOM 应可横向滚动查看所有列。
- 实现：
  - `web/src/app/admin/sales-trainer/training-records/page.tsx` 为训练记录表格增加 `role="region"`、`aria-label="训练记录明细表格"`、`overflow-x-auto` 和 `min-w-[1120px]`。
  - 不复制移动端卡片 DOM，避免桌面/移动两套记录展示状态不一致。
- 验证：
  - `cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/page.test.tsx'`：1 file / 4 tests passed。
  - `cd web && npx eslint 'src/app/admin/sales-trainer/training-records/page.tsx' 'src/app/admin/sales-trainer/training-records/page.test.tsx' --quiet`：通过。

## 2026-06-28 19:30 管理端移动视口 E2E

- 要证明什么：
  - 训练记录明细页在 390px 移动视口下仍能访问模块、训练阶段、记录状态、学员等级、角色等级筛选。
  - 训练记录宽表格的横向溢出必须限制在显式 `role="region"` 滚动容器内，不得撑破页面。
  - Journey Analytics 在移动视口下能访问部门、训练阶段、模块、学员等级、角色等级筛选；筛选后允许真实空态，但不能吞错或出现页面级横向溢出。
- 实现：
  - `web/tests/e2e/newcomer-training-closed-loop.spec.ts` 新增 `mobile admin records and analytics expose governed filters without page overflow`。
  - 新增 `expectPageFitsMobileViewport()` helper，断言 `document.body/documentElement.scrollWidth` 不超过 viewport 宽度容差，避免把横向滚动泄漏到整页。
  - 用例先验证 analytics 未筛选 dashboard 区块，再应用 `in_progress` 筛选；首次执行发现该筛选在当前 seed 下真实返回 0 条，因此断言修正为接受“当前筛选下暂无 Journey 数据”空态或 dashboard 数据态。
- 验证：
  - `cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过。
  - `cd web && SMOKE_WEB_BASE_URL=http://localhost:3445 SMOKE_BACKEND_BASE_URL=http://localhost:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "mobile admin records and analytics" --workers=1`：1 passed；global setup 输出 `created=0 updated=33 verified=True`，完成后自动停栈。

## 2026-06-28 19:35 管理端移动端 a11y/截图证据补强

- 要证明什么：
  - Analytics 的核心分析区块不只靠视觉标题识别，也提供机器可读 region 名称，便于移动端和辅助技术定位。
  - 移动端 Playwright 不只断言 DOM，还生成可复核截图 artifact，作为管理端移动视口验收证据。
- 实现：
  - `web/src/app/admin/sales-trainer/analytics/page.tsx` 为 Journey 漏斗、历史趋势、模块通过率与状态分布、弱项热图、学员等级分布、角色等级分布、风险学员队列增加 `role="region"` 与 `aria-label`。
  - `web/tests/e2e/newcomer-training-closed-loop.spec.ts` 的 mobile smoke 增加 region 断言，并通过 `testInfo.attach()` 附加 `mobile-training-records` 和 `mobile-journey-analytics` 两张 full-page 截图。
- 验证：
  - `cd web && npx eslint 'src/app/admin/sales-trainer/analytics/page.tsx' tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过。
  - `cd web && npx vitest run 'src/app/admin/sales-trainer/analytics/page.test.tsx'`：1 file / 5 tests passed。
  - `cd web && npx tsc --noEmit`：通过。
  - `cd web && SMOKE_WEB_BASE_URL=http://localhost:3445 SMOKE_BACKEND_BASE_URL=http://localhost:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "mobile admin records and analytics" --workers=1`：1 passed；global setup 输出 `created=0 updated=33 verified=True`，完成后自动停栈。

## 2026-06-28 19:38 子代理复核缺口闭合

- 要证明什么：
  - training-records 列表和详情页的关键 Vitest 必须进入 full gate，而不只是本地聚焦验证。
  - 配置异常 Playwright 不能污染后续 working draft；验证缺 AI Coach fail-closed 后必须恢复原配置。
  - 移动端 records 用例必须证明筛选后的真实记录接口和表格语义状态，而不只证明控件存在。
- 实现：
  - `scripts/critical-quality-gate.sh` 的 `VITEST_GATE_TARGETS` 加入 `src/app/admin/sales-trainer/training-records/page.test.tsx` 和 `src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx`。
  - `path config publish preview fails closed...` 用例保存原始 path config，并在 `finally` 通过 `PUT /admin/newcomer-training/path-config` 恢复 working draft。
  - `mobile admin records...` 用例点击查询后等待 `/api/v1/admin/sales-trainer/training-records` GET 成功，并断言表格 region 出现“暂无训练记录”或“查看详情”。
- 验证：
  - `bash -n scripts/critical-quality-gate.sh`：通过。
  - `cd web && npx vitest run 'src/app/admin/sales-trainer/training-records/page.test.tsx' 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'`：2 files / 15 tests passed。
  - `cd web && npx eslint 'src/app/admin/sales-trainer/analytics/page.tsx' tests/e2e/newcomer-training-closed-loop.spec.ts --quiet && npx tsc --noEmit`：通过。
  - `cd web && SMOKE_WEB_BASE_URL=http://localhost:3445 SMOKE_BACKEND_BASE_URL=http://localhost:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "mobile admin records|path config publish preview" --workers=1`：2 passed；global setup 输出 `created=0 updated=33 verified=True`，完成后自动停栈。

## 2026-06-28 21:09 Full critical gate 复验

- 要证明什么：
  - 新增 training-records Vitest、移动端 E2E、配置异常恢复用例不只在聚焦命令通过，也真实进入 full critical gate。
  - full gate 仍覆盖后端 ruff、前端 typecheck/lint/Vitest、Playwright smoke、新人训练 E2E、presentation/sales Phase 4、后端 coverage/mypy/core/smoke regression。
  - 20:40 CST 暴露的 `fresh current-run quiz, audio, and AI Coach records share active revision` API timeout 已从根因闭环：商务礼仪闭环 E2E 不再用非空简答题触发真实 LLM 同步评分，真实 AI 简答评分由后端单测/provider gate 覆盖。
  - `SalesTrainerPathService` 不再保留旧 published unit fallback 私有方法，避免无 active revision 时未来被误接回 learner 正式路径。
  - learner audio upload、business skills page/exam/coach 组件级测试进入 full gate，不再只依赖 Playwright 和聚焦命令覆盖。
- 验证：
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/path_service.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_audio_lineage.py -q`：34 passed，1 warning。
  - `rg "_load_published_path_units\\(|def _ordered_items\\(|source=\\\"unit_backfill\\\"|unit_backfill" backend/src/sales_trainer/services/path_service.py backend/src/sales_trainer/services/path_config_service.py backend/src/sales_trainer/schemas.py web/src/lib/api/types.ts`：无 learner 运行链路命中。
  - `cd web && NEWCOMER_E2E_FRESH_RUN_ID=fresh-focused-$(date +%Y%m%d%H%M%S) SMOKE_WEB_BASE_URL=http://localhost:3445 SMOKE_BACKEND_BASE_URL=http://localhost:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "fresh current-run quiz" --workers=1`：1 passed。
  - `cd web && npm test -- --run src/app/'(dashboard)'/sales-trainer/audio/'[unitId]'/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/coach/page.test.tsx`：4 files / 41 tests passed。
  - `bash scripts/critical-quality-gate.sh`：2026-06-28 21:09 复跑通过。
  - secret hygiene scan：448 files scanned。
  - Backend ruff：通过。
  - Web typecheck：通过。
  - Web lint：0 errors / 84 warnings。
  - Vitest coverage gate：27 files / 245 tests passed，coverage summary 非空。
  - Playwright smoke：9 passed。
  - Playwright newcomer closed-loop E2E：11 passed / 1 skipped；包含 fresh current-run active revision、mobile admin records/analytics 和 path config publish preview fail-closed。
  - Playwright presentation Phase 4：2 passed。
  - Playwright sales Phase 4：1 passed。
  - Backend newcomer coverage gate：33 passed，coverage 45.46%，达到 fail-under 45。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend core gate：321 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
  - 证据文件：`.sisyphus/evidence/task-9-quality-gate.txt`，结尾为 `Critical quality gate passed`。

## 2026-06-28 19:46 移动端基础 a11y 自动检查

- 要证明什么：
  - 不引入新依赖的前提下，管理端移动 E2E 自动检查 records/analytics 主内容是否存在基础可访问性回归。
  - 当前闭环至少能自动发现重复 id、未命名 region、未标注 input/select/textarea、空按钮这类高信号问题。
- 实现：
  - `web/tests/e2e/newcomer-training-closed-loop.spec.ts` 新增 `expectBasicA11ySignals()`，限定在 `main` 内检查基础可访问性信号，避免 Next DevTools 等开发控件干扰。
  - mobile admin records/analytics 用例在训练记录页、analytics dashboard、analytics filtered page 三个状态均执行基础 a11y 检查。
- 验证：
  - `cd web && npx eslint tests/e2e/newcomer-training-closed-loop.spec.ts --quiet`：通过。
  - `cd web && npx tsc --noEmit`：通过。
  - `cd web && SMOKE_WEB_BASE_URL=http://localhost:3445 SMOKE_BACKEND_BASE_URL=http://localhost:3444/api/v1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "mobile admin records and analytics" --workers=1`：1 passed；global setup 输出 `created=0 updated=33 verified=True`，完成后自动停栈。

## 2026-06-28 19:54 AI Coach 真实 provider 首卡契约补强

- 要证明什么：
  - 用户提供的 DeepSeek 测试 key 已真实进入 AI Coach provider 链路，且 learner 在 `plan_then_wait` 首屏选择“继续”后，后端不能接受只输出 `followup_prompt` 的伪成功，必须产出受治理的 `quiz_card`。
- 本地配置写入：
  - 已将用户提供的 StepFun / DeepSeek 测试凭证写入 gitignore 的 `backend/.env`；受 Git 跟踪文件未写入明文密钥。
  - `STEPFUN_REALTIME_MODEL=step-audio-2.3`，AI Coach 走 DeepSeek OpenAI-compatible `LLM_BASE_URL=https://api.deepseek.com/v1`。
- CodeGraph/源码复核：
  - `AiCoachChatAutoAdvance.advance_for_command()` 在 learner command 下调用 `AiCoachChatGenerator.generate()` 并复用 `AiCoachChatNextActionGenerator._validate_response_for_action()`。
  - 旧校验允许 `continue_drill` / `increase_difficulty` 无 `quiz_card`，导致真实 provider 可返回纯 `followup_prompt` 但门禁不能证明“首版必过”。
- 实现：
  - `backend/src/sales_trainer/services/ai_coach_chat_next_action_generation.py` 将 `continue_drill` / `increase_difficulty` 收紧为必须且只能生成 1 张 `quiz_card`，可附 1 个 `followup_prompt`。
  - 同步系统提示，明确 action-specific UI event 约束，避免模型继续把 `continue_drill` 当成普通追问。
  - `backend/tests/unit/test_sales_trainer_ai_coach_chat.py` 把旧的“chat-only continue_drill allowed”改为拒绝用例，并新增带 `quiz_card` 的通过用例。
- 验证：
  - `cd backend && .venv/bin/pytest tests/unit/test_sales_trainer_ai_coach_chat.py -q`：58 tests passed，但单文件触发全仓 coverage fail-under，命令最终因 coverage 29% < 48% 退出 1；测试用例本身全部通过。
  - `cd backend && .venv/bin/pytest tests/unit/test_sales_trainer_ai_coach_chat.py -q --no-cov`：58 passed。
  - `set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh`：1 Playwright passed，`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json` 为 `status=passed`、`classification=executed`、`provider=openai`、`model=deepseek-chat`、`source=model_config`、`model_config_id` 非空、`fallback_used=false`。
  - `rg "<redacted StepFun key>|<redacted DeepSeek key>" -n . --hidden -g '!backend/.env' -g '!*.env' -g '!evidence/*token*' -g '!.sisyphus/**' -g '!node_modules/**'`：无命中，受控文件未写入明文密钥。
- StepFun Realtime 复验：
  - `set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh`：执行到 StepFun 上游后 HTTP 401，`.sisyphus/evidence/newcomer-real-provider-gate.json` 为 `status=failed`、`classification=upstream_auth_rejected`、`model=step-audio-2.3`。
  - 结论：模型已切到 `step-audio-2.3` 且本地 env 已生效；剩余失败是 StepFun 上游 key/账号/model Realtime 授权问题，不是本地链路未写入。

## 2026-06-28 20:18 learner fallback 与低频权限复核闭合

- 要证明什么：
  - learner 端不能再用 `70` 作为缺失通过线的硬兜底。
  - 新人训练首页模块视图和商务技巧直达页不能从旧 `unit.config.path` 推断模块身份，active path revision 投影必须是唯一运行真源。
  - 管理端低频/隐藏路由没有绕过 capability fail-closed 的高置信遗漏。
- 子代理复核与主 Agent 复核：
  - 前端 learner 巡检发现两个高置信缺口：`getAudioPassThreshold()` 默认 70、`module-path.ts` 仍读取旧 `unit.config.path`。
  - 管理端路由巡检发现 `score-prompts` 是旧路由重定向；主 Agent 复核目标 `score-standards` 列表/新建/编辑页均在能力未确认时不加载业务数据，未发现高置信权限旁路。
- 实现：
  - `web/src/lib/sales-trainer/learner-presenter.ts` 删除 `DEFAULT_AUDIO_PASS_THRESHOLD`，缺配置返回 `null`。
  - `web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.tsx` 缺通过线时展示“评分标准配置缺失”，并禁用上传提交。
  - `web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx` 缺通过线或单元读取失败时展示“评分标准配置不可用”，不再显示 70 分。
  - `web/src/lib/sales-trainer/module-path.ts` 只读取 `SalesTrainerPathLevel.module_key/module_type`，不再从 `unit.config.path` 推断模块身份、停用状态、按钮文案或 realtime 占位原因。
  - 删除无调用点的 `web/src/lib/sales-trainer/module-path-legacy.ts`，避免仓库继续保留旧 order fallback 实现。
  - 删除无调用点的 `web/src/app/(dashboard)/sales-trainer/extra-units-section.tsx`，并移除 `collectPathUnitIds` / `partitionUnits` / `sortExtraUnits` / `isLikelyInternalUnit` orphan unit helper，避免 learner 端保留 catalog extra units 入口。
  - `web/src/app/(dashboard)/sales-trainer/business-skills/config.ts` / `use-business-skills-workbench.ts` 收紧直达逻辑：无 active Journey 传入的 `unitId` 时不借旧 `module_key` 或其他单元 `exam_paper_id` 推断，学习页显示明确错误，考试页停在配置缺失态。
- 验证：
  - `cd web && npm test -- --run src/lib/sales-trainer/module-path.test.ts src/lib/sales-trainer/learner-presenter.test.ts src/app/'(dashboard)'/sales-trainer/audio/'[unitId]'/page.test.tsx src/app/'(dashboard)'/sales-trainer/audio/result/'[submissionId]'/page.test.tsx src/app/'(dashboard)'/sales-trainer/page.test.tsx src/app/'(dashboard)'/sales-trainer/page-newcomer-scope.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/coach/page.test.tsx src/lib/sales-trainer/routes.test.ts`：10 files / 80 tests passed。
  - `cd web && npx tsc --noEmit`：通过。
  - `cd web && npx eslint src/lib/sales-trainer/module-path.ts src/lib/sales-trainer/learner-presenter.ts src/app/'(dashboard)'/sales-trainer/audio/'[unitId]'/page.tsx src/app/'(dashboard)'/sales-trainer/audio/result/'[submissionId]'/page.tsx src/app/'(dashboard)'/sales-trainer/business-skills/config.ts src/app/'(dashboard)'/sales-trainer/business-skills/use-business-skills-workbench.ts`：通过。
  - 删除旧 extra units 入口后复验：`cd web && npm test -- --run src/app/'(dashboard)'/sales-trainer/page.test.tsx src/lib/sales-trainer/learner-presenter.test.ts`：2 files / 11 tests passed；`cd web && npx eslint src/lib/sales-trainer/learner-presenter.ts src/app/'(dashboard)'/sales-trainer/page.test.tsx`：通过；`rg "ExtraUnitsSection|collectPathUnitIds|partitionUnits|sortExtraUnits|isLikelyInternalUnit|unit\\.config\\.path\\?\\.module_key|buildLegacyModuleViews|module-path-legacy" web/src/app/'(dashboard)'/sales-trainer web/src/lib/sales-trainer web/src/components/sales-trainer`：仅剩后台 `admin-display.ts` 的显示兼容命中，不在 learner 运行链路。

## 2026-06-28 21:05 learner unit/brief 读取权限补强

- 要证明什么：
  - 普通 learner 不能只凭 `unit_id` 读取 active path 外、无 active path 或 locked level 的 published unit/brief。
  - unit/brief 读取面必须和 audio/quiz 提交面共用同一个后端对象级授权 gate，不能只靠前端隐藏入口。
  - 当前工作树不能新增明文 secret；git 历史疑似泄漏必须作为人工安全处置项单列，不能用当前扫描通过掩盖。
- 子代理复核与主 Agent 复核：
  - 安全子代理发现 `/sales-trainer/units/{unit_id}` 与 `/sales-trainer/units/{unit_id}/brief` 只检查 `unit.status == "published"`，未调用 `require_learner_active_path_unit_access()`。
  - 主 Agent 用 CodeGraph 复核路由链路：quiz/audio 提交已调用 `require_learner_active_path_unit_access()`，缺口集中在 learner unit/brief 读取面。
  - 安全子代理同时确认当前工作树 secret hygiene 通过、当前 diff 未发现新增真实 key 形态；但 git 历史存在旧 evidence/JWT/API-key 形态记录，需按泄漏风险由维护者轮换/清史。
- 实现：
  - `backend/src/sales_trainer/api.py` 新增 `_require_learner_unit_access_response()`，在 learner-facing unit 和 brief payload 组装前复用 `require_learner_active_path_unit_access()`。
  - `backend/tests/unit/test_newcomer_training_path_audio_lineage.py` 新增无 active path、active path 外、locked unit 三类读取面断言；unit 与 brief 都必须返回 404 `[SALES_TRAINER_UNIT_NOT_FOUND]`。
  - `audit-closure-matrix.md` 与 `final-verification-report.md` 更新权限读取面闭环、验证证据和 git 历史 secret 残余风险。
- 验证：
  - `codegraph explore "sales_trainer get_published_unit get_published_unit_brief require_learner_active_path_unit_access routes callers"`：确认缺口集中在 unit/brief learner 路由，quiz/audio 提交已走同一 gate。
  - `cd backend && .venv/bin/ruff check src/sales_trainer/api.py tests/unit/test_newcomer_training_path_audio_lineage.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_audio_lineage.py -q`：12 passed，1 warning。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_newcomer_training_path_permissions.py tests/integration/test_newcomer_training_path_material_api.py tests/integration/test_newcomer_training_path_rbac_api.py -q`：37 passed，1 warning。
  - `python3 scripts/check_secret_hygiene.py --report .sisyphus/evidence/secret-scan-report.json`：450 files scanned，passed。

## 2026-06-28 21:12 外部/人工剩余项 runbook 补强

- 要证明什么：
  - 剩余不能代码内伪装完成的事项必须有仓库内可执行步骤，而不是只存在聊天记录或最终报告口头风险里。
  - 学员等级真实枚举/来源、生产历史回填、git 历史疑似 secret 处置必须分别有确认问题、执行门槛、禁止事项和回写证据要求。
- CodeGraph/源码复核：
  - `TrainingJourneyService` 当前通过 `sales_trainer.learner_level.policy` 投影学员等级，默认 `unassigned`；配置缺失/非法/停用时返回 fallback 元数据。
  - 当前 `User` 模型没有稳定的新人训练学员等级字段可直接作为真实来源；真实枚举和人工/自动来源仍是产品/运营决策。
- 实现：
  - `external-verification-runbook.md` 更新时间到 `2026-06-28 21:12 CST`，记录 21:09 full gate 作为当前基线。
  - 新增 §3“学员等级真实枚举与来源确认”，列出产品/运营必须回答的问题、发布前最低验证和禁止事项。
  - 将历史生产回填章节调整为 §4，保留 dry-run、审批、回滚、禁止事项。
  - 新增 §5“git 历史疑似 secret/token 处置”，记录当前工作树干净不等于历史风险消失，并列出轮换、清史、完成判定。
  - `audit-closure-matrix.md` 与 `final-verification-report.md` 同步指向 runbook §3/§4/§5。
- 验证：
  - `codegraph explore "TrainingJourneyService learner_level policy user model fields sales_trainer.learner_level.policy business rules"`：确认等级来源为业务规则投影，未发现稳定用户表等级字段。
  - 文档窄搜确认 runbook、矩阵、最终报告均包含学员等级和 git 历史 secret 剩余项的可执行入口。

## 2026-06-28 23:24 StepFun Realtime endpoint 契约补强

- 要证明什么：
  - StepFun 真实 provider 401 不能只归因于外部 key；必须复核官方 Realtime 契约，确认本地握手 URL、鉴权和 model query 构造没有明显协议缺口。
  - 如果 key 属于 Step Plan 订阅，本地必须能通过 `STEPFUN_REALTIME_URL` 切到 `/step_plan/v1/realtime`，且不能因为 URL 已带 query 造成 endpoint 拼接错误。
- CodeGraph/官方契约复核：
  - `StepFunTransport.connect()` 是 StepFun 上游握手唯一封装，发送 `Authorization: Bearer <redacted>`，model 作为 query 参数。
  - StepFun 官方 Realtime 文档当前列出开放平台 `/v1/realtime` 和 Step Plan `/step_plan/v1/realtime` 两类 base URL，鉴权仍为 Bearer token。
  - 官方公开模型列表未显示 `step-audio-2.3`；该模型是用户指定模型，后续需以控制台授权范围为准。此前多模型握手矩阵均 401，说明当前证据更像 key/账号/path/model 授权范围问题。
- 实现：
  - `backend/src/training_runtime/stepfun_transport.py` 新增 `build_stepfun_realtime_endpoint()`，使用 `urlsplit/parse_qsl/urlunsplit` 结构化追加或替换 `model` query。
  - `backend/tests/unit/test_stepfun_transport.py` 新增 Step Plan URL 和既有 query 替换用例。
  - `docs/api-contract/voice-runtime.md` 明确开放平台 URL、Step Plan URL、model query 构造不允许字符串拼接出错。
  - `external-verification-runbook.md` 明确 Step Plan key 需要 `STEPFUN_REALTIME_URL=wss://api.stepfun.com/step_plan/v1/realtime`，并记录官方模型列表与 `step-audio-2.3` 的授权边界。
- 验证：
  - `cd backend && .venv/bin/ruff check src/training_runtime/stepfun_transport.py tests/unit/test_stepfun_transport.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_payload_snapshots.py -q`：155 passed，1 warning。

## 2026-06-28 23:29 Full critical gate 复验

- 要证明什么：
  - StepFun Realtime endpoint 契约补强、learner unit/brief 对象级授权、active revision 真源收口、前端 fail-closed 和新人训练 E2E 没有只停留在聚焦测试。
  - 本地 deterministic full gate 覆盖当时工作树基线，且受控文件没有写入用户提供的真实测试密钥明文。
- 验证：
  - `bash scripts/critical-quality-gate.sh`：2026-06-28 23:29 复跑通过。
  - Secret hygiene scan：448 files scanned，passed。
  - Backend ruff：通过。
  - Web typecheck：通过。
  - Web lint：0 errors / 84 warnings。
  - Vitest coverage gate：27 files / 245 tests passed。
  - Playwright smoke：9 passed。
  - Playwright newcomer closed-loop E2E：11 passed / 1 skipped。
  - Playwright presentation Phase 4：2 passed。
  - Playwright sales Phase 4：1 passed。
  - Backend newcomer coverage gate：33 passed，coverage 45.46%，达到 fail-under 45。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend core gate：321 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
  - 证据文件：`.sisyphus/evidence/task-9-quality-gate.txt`，结尾为 `Critical quality gate passed`。
- 结论：
  - 本地可验证闭环通过最新 full gate。
  - StepFun 真实 provider 仍不是本地闭环失败：真实 gate 已到上游并返回 HTTP 401 / `upstream_auth_rejected`，需 StepFun 控制台 Realtime/model 授权或更换可用 key 后复跑强制门禁。

## 2026-06-28 23:45 Active path list / workbench fail-closed 反审计补强

- 要证明什么：
  - learner 端不能通过 `/sales-trainer/units` 列表拿到 active path revision 外的 published catalog unit。
  - learner-facing unit/detail/brief 路由不能因为调用者是后台角色而绕过 active path 对象级授权。
  - 商务技巧文章/考卷绑定必须来自 active path level，而不是旧 `unit.config.path`。
  - `/admin/sales-trainer` workbench 直链必须和 sidebar/module nav 使用同一 capability projection；无权、权限加载失败或 dashboard 失败时不能渲染伪空态。
- 子代理复核与主 Agent 复核：
  - 安全子代理指出 `GET /sales-trainer/units` 仍直接返回全量 published units，且 `learner_unit_access` 对非 learner 角色有旁路。
  - 前端子代理指出 workbench 根页没有 route capability fail-closed，dashboard 失败时仍渲染空指标。
  - 测试子代理确认 deterministic full gate 和 AI Coach real provider 证据成立，但 StepFun real provider 仍是上游 401；文档子代理指出 P2 和外部项口径需收紧。
  - 主 Agent 用 CodeGraph 抽查 learner unit/brief、path service、business-skills active path 和 admin route capability 调用链；同时用源码窄搜确认旧 path service `unit_backfill` fallback 已删除，admin config center 中的旧 path payload 只属于管理配置分析，不属于 learner runtime 真源。
- 实现：
  - `backend/src/sales_trainer/api.py`：learner `GET /sales-trainer/units` 改为读取 `SalesTrainerPathConfigService.active_projection()`，只返回 active projection 中 enabled unit；无 active revision 返回空列表。
  - `backend/src/sales_trainer/services/learner_unit_access.py`：删除非 learner 角色旁路，learner-facing route 全部走 active path unit scope。
  - `backend/src/sales_trainer/schemas.py` 与 `path_projection_payloads.py`：`SalesTrainerPathLevelResponse` 增加 `learning_content_id`、`exam_paper_id`。
  - `web/src/app/(dashboard)/sales-trainer/business-skills/*` 与 `web/src/lib/api/types.ts`：学习页和考试页只从 active path level 读取文章/考卷绑定；旧 `unit.config.path` 绑定不再作为 learner 兜底。
  - `web/src/app/admin/sales-trainer/page.tsx`：workbench 根页接入 `useSalesTrainerAdminRouteAccess()`，无权/加载失败不请求 dashboard、不展示 workbench link；dashboard 业务失败展示 `AdminLoadErrorCard`，不伪装为空指标。
  - `docs/api-contract/sales-trainer.md`、`audit-closure-matrix.md`、`final-verification-report.md` 同步 active level 绑定、learner units 列表真源、workbench fail-closed 和四类外部/人工剩余项。
- 验证：
  - `cd backend && .venv/bin/ruff check src/sales_trainer/api.py src/sales_trainer/schemas.py src/sales_trainer/services/learner_unit_access.py src/sales_trainer/services/path_projection_payloads.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_boundary.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_boundary.py -q`：19 passed，1 warning。
  - `cd web && npm test -- --run src/app/'(dashboard)'/sales-trainer/business-skills/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.test.tsx src/app/admin/sales-trainer/page.test.tsx src/lib/sales-trainer/module-path.test.ts`：4 files / 38 tests passed。
  - `cd web && npx tsc --noEmit`：通过。
  - `cd web && npx eslint src/app/'(dashboard)'/sales-trainer/business-skills/config.ts src/app/'(dashboard)'/sales-trainer/business-skills/use-business-skills-workbench.ts src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.tsx src/app/admin/sales-trainer/page.tsx src/app/admin/sales-trainer/page.test.tsx`：通过。
- 结论：
  - 本轮反审计发现的两个真实代码缺口已修复并有聚焦测试证据。
  - 仍不能把 goal 标记为完全完成：StepFun 真实 provider 401、历史生产回填、学员等级真实枚举/来源、git 历史疑似 secret/token 处置仍需外部授权或人工决策。

## 2026-06-29 00:08 Admin analytics/records 筛选与 full gate 复验

- 要证明什么：
  - 管理端 records 和 analytics 的学员等级、角色等级筛选不只是页面上有控件，而是在真实浏览器路径中能使用后端返回的等级选项发起筛选请求，并把当前 scope 反馈给管理员。
  - 后端 analytics `limit` 不能只做 query echo，必须真实限制加载到模块/漏斗/等级摘要中的 learner 数，同时保留总匹配人数，避免大数据量分析页误导管理员。
  - 移动端 records/analytics 用例仍保持页面级横向溢出、基础 a11y 和筛选后可恢复显示。
- 子代理发现：
  - 前端子代理发现 training-records 页移动端点“查询”按钮不会重新提交筛选；主 Agent 复核后确认表单 submit 和按钮点击应共用同一 `submitFilters()`。
  - 后端子代理发现 `get_admin_analytics(limit=...)` 只回显 `filters.limit`，聚合仍使用全量匹配 journeys；主 Agent 复核 TrainingJourneyService 后改为 `loaded_journeys = journeys[:limit]`。
  - 验证子代理指出旧 full gate evidence 曾被误跑脚本污染，主 Agent 已重新执行 full gate 并以 2026-06-29 00:08 通过日志为准。
- 实现：
  - `backend/src/sales_trainer/services/training_journey_service.py`：analytics 聚合改用 `loaded_journeys`，`summary.learner_count` 保留总匹配数，`loaded_learner_count` 记录实际加载数。
  - `backend/tests/unit/test_sales_trainer_training_journey_service.py` 与 `backend/tests/integration/test_newcomer_training_journey_api.py`：补 `limit=1` 的 unit/API 断言。
  - `web/src/app/admin/sales-trainer/training-records/page.tsx`：筛选提交抽成 `submitFilters()`，form submit 和查询按钮统一调用，避免移动端按钮点击不发请求。
  - `web/tests/e2e/newcomer-training-closed-loop.spec.ts` 的 `mobile admin records and analytics expose governed filters without page overflow` 用例从 `学员等级筛选` / `角色等级筛选` select 中读取第一个后端返回的非空 option，不硬编码产品等级枚举。
  - 提交 records 筛选时等待 `/api/v1/admin/sales-trainer/training-records` 响应，并断言请求 query 包含 `user_id/module_key/training_stage/status/learner_level/role_level`。
  - 提交 analytics 筛选时等待 `/api/v1/admin/sales-trainer/journeys/analytics` 响应，并断言请求 query 同时包含 `department/training_stage/module_key/learner_level/role_level`。
  - 页面断言补充 `scope:`、`training_stage:`、`module_key:`、`learner_level:` 与 `role_level:` scope badge，避免接口参数正确但 UI 反馈缺失。
- 验证：
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/training_journey_service.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py tests/contract/test_sales_trainer_phase2_contract.py -q`：23 passed，1 warning。
  - `cd web && npx vitest run src/app/admin/sales-trainer/training-records/page.test.tsx src/app/admin/sales-trainer/analytics/page.test.tsx`：2 files / 9 tests passed。
  - `cd web && npx eslint src/app/admin/sales-trainer/training-records/page.tsx tests/e2e/newcomer-training-closed-loop.spec.ts`：通过。
  - `cd web && npx tsc --noEmit`：通过。
  - `cd web && npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "mobile admin records and analytics expose governed filters"`：1 passed。
  - `bash scripts/critical-quality-gate.sh`：2026-06-29 00:08 复跑通过；secret scan 448 files scanned，Backend ruff 通过，Web typecheck 通过，Web lint 0 errors/84 warnings，Vitest 27 files/245 tests passed，Playwright smoke 9 passed，newcomer E2E 11 passed/1 skipped，presentation Phase 4 2 passed，sales Phase 4 1 passed，Backend newcomer coverage 33 passed/45.46%，mypy 8 source files 通过，Backend core 321 passed，Backend smoke regression 58 passed。
- 结论：
  - 之前“analytics 等级筛选浏览器交互证据偏弱”“records 查询按钮没有真实发请求”“analytics limit 只回显不生效”的缺口已分别补强为代码、单元/API 测试和 Playwright 证据，并进入 full gate。
  - 真实学员等级枚举/来源仍按 `external-verification-runbook.md` 归为人工决策，不在前端硬编码。
  - StepFun 真实 provider 仍是上游 401 授权问题；本轮不把该外部项伪装为已完成。

## 2026-06-29 00:34 Service 授权内聚与 Journey next-step 真源反审计补强

- 要证明什么：
  - 训练记录 detail 与材料文件读取不能只在 route 层临时做部门 scope，service 层也必须表达 viewer/object scope，避免未来复用 `get_record()` 时绕过对象级授权。
  - AI Coach turn submit 不能只依赖 route 先查 session；service 层拿到 actor 时必须再次确认 session ownership。
  - 结果页“练完下一步”和 AI Coach 入口不能继续从 learner catalog/listPaths 伪推断，必须只读 TrainingJourney 的 active revision 投影。
  - admin dashboard 不能在 200 但 DTO shape 漂移时显示 `--` 或“暂无集中弱项”伪空态。
  - training-records 前端不能硬编码 learner/role level datalist，真实等级枚举来源未定前只能自由输入或使用后端返回选项。
- 子代理发现与主 Agent 复核：
  - 后端安全子代理指出 `TrainingRecordService.get_record()` 是全局取记录，route 层虽补了部门 scope，但 service 层缺对象级查看契约；同时 `AiCoachSessionService.submit_turn_v1()` 依赖 route 前置 ownership。
  - 前端子代理指出 `next-step-panel.tsx` 仍读取 `api.salesTrainer.listPaths()` 并合成 AI Coach fallback；quiz result 页另有 `resolveAiCoachHref()` 使用旧 `findBusinessSkillsCoachHref()`；admin dashboard malformed 200 和 training-records 等级硬编码也需要收口。
  - 主 Agent 用 CodeGraph 复核 `next-step-panel` 调用者、quiz/audio result 页、训练记录 detail route 和 AI Coach session service 后，按影响面做最小补强。
- 实现：
  - `backend/src/sales_trainer/services/training_record_service.py` 新增 `get_record_for_viewer()`，训练记录 detail 和材料文件 route 改用该方法，部门 scope 下沉到 service 层。
  - `backend/src/sales_trainer/services/ai_coach_session_service.py` 在 legacy `submit_turn()` 和 v1 `submit_turn_v1()` 中，当 actor 存在时通过 `get_session(session_id, actor.user_id)` 复查 ownership。
  - `backend/tests/integration/test_sales_trainer_api.py` 扩充同部门/跨部门训练记录 detail 与材料访问断言，并把 support 读 operation logs 的旧预期修正为 403 `[ROLE_REQUIRED]`。
  - `backend/tests/unit/test_sales_trainer_ai_coach.py` 新增 `test_submit_turn_v1_rechecks_actor_ownership`，证明跨用户 actor 在 service 层被拒绝。
  - `web/src/app/(dashboard)/sales-trainer/next-step-panel.tsx` 改为调用 `api.salesTrainer.getJourney()`，按 `modules[].next_action` 生成下一步建议；无后端 next action 时只回训练首页，不再合成 AI Coach fallback。
  - `web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx` 与 `quiz/result/[attemptId]/page.test.tsx` 改用 Journey mock，并断言 `listPaths` 不被调用；quiz result 页 AI Coach 入口仅在 `passed === false` 时从 Journey business_skills coach action 解析。
  - `web/src/app/admin/sales-trainer/page.tsx` 新增 dashboard runtime contract guard，malformed 200 进入 `AdminLoadErrorCard`。
  - `web/src/app/admin/sales-trainer/training-records/page.tsx` 移除前端硬编码 `LEVEL_FILTER_OPTIONS` / datalist，避免伪造真实等级枚举来源。
- 验证：
  - `cd backend && .venv/bin/ruff check src/sales_trainer/api.py src/sales_trainer/services/training_record_service.py src/sales_trainer/services/ai_coach_session_service.py tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_ai_coach.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/integration/test_sales_trainer_api.py::test_should_scope_sales_trainer_manager_to_same_department tests/integration/test_newcomer_training_path_material_api.py::test_should_replay_archived_material_version_from_training_record tests/contract/test_sales_trainer_phase2_contract.py tests/unit/test_sales_trainer_ai_coach.py::test_submit_turn_v1_rechecks_actor_ownership -q`：10 passed，1 warning。
  - `cd web && npx vitest run src/app/'(dashboard)'/sales-trainer/next-step-panel.test.tsx src/app/'(dashboard)'/sales-trainer/audio/result/'[submissionId]'/page.test.tsx src/app/'(dashboard)'/sales-trainer/quiz/result/'[attemptId]'/page.test.tsx src/app/admin/sales-trainer/training-records/page.test.tsx src/app/admin/sales-trainer/page.test.tsx`：5 files / 27 tests passed。
  - `cd web && npx eslint src/app/'(dashboard)'/sales-trainer/next-step-panel.tsx src/app/'(dashboard)'/sales-trainer/next-step-panel.test.tsx src/app/'(dashboard)'/sales-trainer/audio/result/'[submissionId]'/page.test.tsx src/app/'(dashboard)'/sales-trainer/quiz/result/'[attemptId]'/page.tsx src/app/'(dashboard)'/sales-trainer/quiz/result/'[attemptId]'/page.test.tsx src/app/admin/sales-trainer/training-records/page.tsx src/app/admin/sales-trainer/page.tsx src/app/admin/sales-trainer/page.test.tsx`：通过。
  - `cd web && npx tsc --noEmit`：通过。
- 结论：
  - 本轮把两个“可被未来复用绕过”的后端 scope 缺口下沉到 service 层，并把结果页仍读旧 catalog 的前端入口收口到 TrainingJourney。
  - 本轮未宣称 StepFun 真实 provider 已完成；该项仍是上游 HTTP 401 授权问题，按 runbook 复跑。
  - 学员等级真实枚举/来源仍是人工决策；本轮仅移除前端伪枚举硬编码。

## 2026-06-29 00:43 商务技巧页 AI Coach 入口 Journey 真源补强

- 要证明什么：
  - 商务技巧 workbench 不能继续通过 `/sales-trainer/paths` 的 legacy `ai_coach_availability` 推断 AI Coach 入口。
  - learner 可见 AI Coach 入口必须统一来自 TrainingJourney `modules[].next_action`。
  - 旧 helper 不能残留为后续误用入口。
- 子代理发现与主 Agent 复核：
  - 只读搜索子代理定位前端生产运行时仍有两个 `listPaths()` 调用：商务技巧 workbench 和考试页。考试页当前用于 active level 的 `learning_content_id/exam_paper_id` 绑定，未读取 AI Coach availability；workbench 原先确实从 path list 推断 AI Coach href。
  - 前端复核子代理确认主 Agent 修复后 workbench 已从 `api.salesTrainer.getJourney()` 解析 Coach action，`listPaths()` 只保留 active level 绑定用途。
  - 主 Agent 同步复核契约文档，发现 `docs/api-contract/sales-trainer.md` 仍写着通过 `/paths.levels[].ai_coach_availability` 判断入口，与 Journey 真源条款冲突。
- 实现：
  - `web/src/app/(dashboard)/sales-trainer/business-skills/use-business-skills-workbench.ts` 新增 Journey module action 解析，`coachHref` 从 `journey.modules` 中 `business_skills.next_action.target_path` 获取。
  - `web/src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx` 新增反例：path catalog 有 coach path，但 Journey 没有 next action 时不展示 AI Coach 入口；正例中 path catalog 和 Journey 给出不同 href，最终使用 Journey href。
  - 删除未使用的 `web/src/lib/sales-trainer/ai-coach-availability.ts`，避免后续再次回流。
  - `docs/api-contract/sales-trainer.md` 将 `/paths.ai_coach_availability` 明确降级为 legacy 兼容读面，learner 页面/结果页/商务技巧页入口展示必须以 TrainingJourney `next_action` 为真源。
- 验证：
  - `rg -n "ai-coach-availability|findBusinessSkillsCoachHref" web/src docs/api-contract/sales-trainer.md`：无命中。
  - `cd web && npx vitest run src/app/'(dashboard)'/sales-trainer/business-skills/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.test.tsx src/app/'(dashboard)'/sales-trainer/quiz/result/'[attemptId]'/page.test.tsx src/app/'(dashboard)'/sales-trainer/next-step-panel.test.tsx`：4 files / 32 tests passed。
  - `cd web && npx eslint src/app/'(dashboard)'/sales-trainer/business-skills/use-business-skills-workbench.ts src/app/'(dashboard)'/sales-trainer/business-skills/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.test.tsx src/app/'(dashboard)'/sales-trainer/quiz/result/'[attemptId]'/page.tsx src/app/'(dashboard)'/sales-trainer/next-step-panel.tsx`：通过。
  - `cd web && npx tsc --noEmit`：通过。
- 结论：
  - AI Coach 入口相关 learner 运行时已收口到 TrainingJourney；`/paths` 仍可作为 active level 绑定兼容读面，但不再作为 Coach 入口真源。
  - 2026-06-29 00:58 复核后继续推进：学习页与考试页均已迁到 TrainingJourney module binding，`/paths` 不再作为 learner 运行时绑定读取入口。

## 2026-06-29 00:58 Business skills binding 全量迁移到 TrainingJourney

- 要证明什么：
  - 商务技巧学习页、考试页和 AI Coach 入口都只能读取 TrainingJourney，不再调用 learner `/sales-trainer/paths` 获得文章/考卷/Coach 入口。
  - 后端 Journey DTO 必须真实带出 `target_unit_id`、`target_unit_ids`、`learning_content_id`、`exam_paper_id`，且 AI Coach `next_action` 必须通过 response model 校验后出现在 HTTP 响应中。
  - `module_key="business_skills"` 同时有 `quiz_attempt` 和 `ai_coach` 两条时，前端绑定读取必须锁定 `kind="quiz_attempt"`，避免拿错 AI Coach module。
  - StepFun realtime 默认模型必须保持 `step-audio-2.3`，但测试密钥不得写入仓库。
- 子代理发现与主 Agent 复核：
  - 前端只读子代理确认生产代码已改为 `getJourney()`，测试和旧 helper 噪音需要收口。
  - 后端只读子代理确认 Journey binding 字段已在 service/schema 层存在，但指出 `ModuleProgress` 契约文档缺字段，且同 `module_key` 多 module 时前端必须按 `kind` 过滤。
  - 主 Agent 复核后发现后端 `_next_action()` 只给 realtime 返回 action，AI Coach 首版必过入口在真实 HTTP Journey 中仍可能缺失，因此补后端 action 和 response model。
- 实现：
  - `backend/src/sales_trainer/services/training_journey_service.py`：AI Coach module 返回 `start_ai_coach` / `continue_ai_coach` action；business_skills 指向 `/sales-trainer/business-skills/coach`，锁定或未知模块时 disabled fail-closed。
  - `backend/src/sales_trainer/schemas.py`：`TrainingJourneyNextAction.action_key` 增加 `start_ai_coach`、`continue_ai_coach`。
  - `backend/tests/unit/test_sales_trainer_training_journey_service.py`：断言 business_skills quiz module 的 Journey binding 字段，AI Coach module 不伪造 `target_unit_id`，但保留文章/考卷上下文并给出 `continue_ai_coach`。
  - `backend/tests/integration/test_newcomer_training_journey_api.py`：新增 HTTP API 级断言，证明 Journey response 中 AI Coach `next_action` 与 binding 字段真实出现在 response model 后的 JSON。
  - `web/src/app/(dashboard)/sales-trainer/business-skills/config.ts`：删除旧 active path helper/import，`isBusinessSkillsJourneyModule()` 收紧为 `kind === "quiz_attempt"`。
  - `web/src/app/(dashboard)/sales-trainer/business-skills/use-business-skills-workbench.ts` 与 `exam/page.tsx`：学习页/考试页均使用 `api.salesTrainer.getJourney()` 的 module binding；不再调用 `listPaths()`。
  - `web/src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx` 与 `exam/page.test.tsx`：测试夹具迁移为 `journeyResponse()`，补缺绑定 fail-closed、旧 unit config stale binding 不回填、`listPaths` 不调用断言；删除未使用 `/paths` fixture。
  - `docs/api-contract/sales-trainer.md`：TrainingJourney `ModuleProgress` 补 `target_unit_id`、`target_unit_ids`、`learning_content_id`、`exam_paper_id` 和 AI Coach action key，并明确这些字段是 learner 文章/考试/AI Coach 上下文唯一运行绑定真源。
- 验证：
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q`：17 passed，1 warning。
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：通过。
  - `cd web && npx vitest run src/app/'(dashboard)'/sales-trainer/business-skills/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.test.tsx src/app/'(dashboard)'/sales-trainer/quiz/result/'[attemptId]'/page.test.tsx src/app/'(dashboard)'/sales-trainer/next-step-panel.test.tsx`：4 files / 32 tests passed。
  - `cd web && npx eslint src/app/'(dashboard)'/sales-trainer/business-skills/config.ts src/app/'(dashboard)'/sales-trainer/business-skills/use-business-skills-workbench.ts src/app/'(dashboard)'/sales-trainer/business-skills/page.test.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.tsx src/app/'(dashboard)'/sales-trainer/business-skills/exam/page.test.tsx src/lib/api/types.ts`：通过。
  - `cd web && npx tsc --noEmit`：通过。
  - `rg -n "api\.salesTrainer\.listPaths\(|listPaths\(" web/src/app/'(dashboard)'/sales-trainer web/src/lib/sales-trainer -g '*.ts' -g '*.tsx'`：无命中。
  - `git diff --check`：通过。
  - `python3 scripts/check_secret_hygiene.py --report .sisyphus/evidence/secret-scan-report.json`：Secret hygiene scan passed，450 files scanned。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_stepfun_transport.py tests/unit/test_voice_runtime_policy_service.py::test_env_fallback_policy_defaults_to_latest_realtime_model -q`：17 passed，1 warning。
  - `cd backend && .venv/bin/ruff check src/training_runtime/stepfun_transport.py src/sales_bot/services/voice_runtime_policy.py src/sales_bot/websocket/voice_runtime_profile.py tests/unit/test_stepfun_transport.py tests/unit/test_voice_runtime_policy_service.py`：通过。
- 未通过/不作为完成证据：
  - `cd backend && .venv/bin/mypy src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py` 仍触发仓库既有 SQLAlchemy/typing 问题，输出 465 errors / 54 files；其中 `training_journey_service.py` 也有此前已存在的 ORM Column 类型项。本轮不把 mypy 伪装为通过。
- 结论：
  - learner sales-trainer 运行链路内 `/paths` 调用已清零；business skills 文章、考试、AI Coach 均以 TrainingJourney active revision projection 为唯一真源。
  - StepFun 默认模型在代码、样例环境、契约和单测中均为 `step-audio-2.3`；用户提供的测试密钥未写入仓库，也未进入 secret 扫描命中。

## 2026-06-29 01:09 Material replay service scope 与类型门禁补强

- 要证明什么：
  - 历史材料只读回放不能只依赖 route 先查 `TrainingRecordService.get_record_for_viewer()`；底层 `SalesTrainerMaterialService.resolve_historical_file_access()` 也必须显式接收 viewer scope，避免未来新增调用点绕过对象级授权。
  - 同部门 manager 仍能回放被训练记录引用的 archived material；跨部门 manager 即使直接调用 material service 也只能得到 `[TRAINING_RECORD_NOT_FOUND]`。
  - 本轮新增的类型治理只能按实际运行结果记录，不能把不带 `--follow-imports=skip` 的仓库既有 mypy 债务伪装成通过。
- 子代理发现与主 Agent 复核：
  - 安全子代理指出当前公开 API 已在 route 层前置校验训练记录 viewer/team scope，未形成现有 P0/P1 越权；但 `resolve_historical_file_access()` 自身只校验 record/version 引用关系，是未来复用风险。
  - 验证子代理指出 00:08 full gate 是当时工作树基线，不能证明 00:34/00:58/01:09 之后的最终工作树；主 Agent 已把 `audit-closure-matrix.md` 和 `final-verification-report.md` 的措辞改为“基线 + 后续聚焦验证”。
- 实现：
  - `backend/src/sales_trainer/services/material_service.py`：`resolve_historical_file_access()` 新增必填 `viewer: User` 与 `team_department: str | None`，并在 service 内调用 `TrainingRecordService.get_record_for_viewer()`；无权或不存在统一返回 `[TRAINING_RECORD_NOT_FOUND]`。
  - `backend/src/sales_trainer/api.py`：历史材料回放 route 调用 material service 时传入 `current_user` 和 `_team_scope(current_user)`。
  - `backend/tests/integration/test_newcomer_training_path_material_api.py`：扩展历史回放测试，断言 service 级同部门访问成功、跨部门直接调用失败。
  - `backend/src/sales_trainer/services/material_service.py`：补充 `cast`，消除该文件内 Pydantic `model_dump()` 与签名服务返回值的局部 `Any` 类型报错。
  - `backend/src/sales_trainer/services/training_journey_service.py` 与 `backend/src/sales_trainer/schemas.py`：补强前序 Journey/schema 类型注解，`--follow-imports=skip` 文件级 mypy 通过。
- 验证：
  - `cd backend && .venv/bin/ruff check src/sales_trainer/api.py src/sales_trainer/services/material_service.py tests/integration/test_newcomer_training_path_material_api.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/integration/test_newcomer_training_path_material_api.py -q`：5 passed，1 warning。
  - `cd backend && .venv/bin/mypy src/sales_trainer/services/material_service.py --follow-imports=skip`：Success，1 source file。
  - `cd backend && .venv/bin/mypy src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py --follow-imports=skip`：Success，2 source files。
  - 前序 Journey/schema 聚焦验证仍成立：`cd backend && .venv/bin/ruff check src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py tests/unit/test_sales_trainer_ai_coach.py tests/unit/test_sales_trainer_ai_coach_chat.py` 通过；`cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py tests/unit/test_sales_trainer_ai_coach.py::test_submit_turn_v1_rechecks_actor_ownership tests/unit/test_sales_trainer_ai_coach_chat.py -q`：76 passed，1 warning。
- 未通过/不作为完成证据：
  - `cd backend && .venv/bin/mypy src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py` 不带 `--follow-imports=skip` 仍会牵出 `common/services/practice_helpers.py`、`runtime_outcome_projection.py`、SQLAlchemy Column 类型和第三方 stubs 等仓库既有类型债；本轮不把它计为通过。
  - 本阶段当时尚未重新执行 `bash scripts/critical-quality-gate.sh`，因此 00:08 full gate 只作为当时基线证据；后续已于 2026-06-29 01:24 重新执行 full gate 并通过，见“2026-06-29 01:24 当前工作树 full critical gate 复验”。
- 结论：
  - `material historical replay` 的对象级授权已经从 route 前置校验下沉到 material service 契约，当前调用链和未来 service 复用都 fail-closed。
  - full gate 证据口径已修正，避免把旧基线夸大为覆盖后续改动。

## 2026-06-29 01:18 Regrade service/API 对象级 scope 补强

- 要证明什么：
  - 历史重评不能只靠当前 admin/ops 入口权限；quiz/audio regrade service 本身必须表达 viewer/team scope，未来若产品允许 manager 重评，也不能跨部门操作历史记录。
  - `article-progress` GET 路径外 published content 的精确回归断言已经存在，不能重复用模糊“已覆盖”口径替代实际证据。
- 子代理发现与主 Agent 复核：
  - 安全子代理确认当前生产入口仍仅 admin/ops 可重评，manager/support/training_lead/training_manager 当前不能重评。
  - 安全子代理同时指出：如果未来直接把 manager 加入 `can_regrade_sales_trainer_history()`，必须保留 API 传入 `viewer/team_department` 和 service 内 `TrainingRecordService.get_record_for_viewer()` 校验；主 Agent 已补实现和测试。
  - CodeGraph 复核 `article-progress` 调用链后，主 Agent 确认 `get_newcomer_module_article_progress()` 已用 `require_active_binding=True`，现有 `test_should_reject_article_progress_for_content_outside_active_path` 已直接断言 GET query mismatch。
- 实现：
  - `backend/src/sales_trainer/services/regrade_service.py`：`preview_quiz_attempt()` / `run_quiz_attempt_regrade()` 强制接收 viewer/team scope，并在 preview 前调用 `TrainingRecordService.get_record_for_viewer("quiz_attempt", ...)`。
  - `backend/src/sales_trainer/services/audio_regrade_service.py`：`preview_audio_submission()` / `run_audio_submission_regrade()` 强制接收 viewer/team scope，并在 preview 前调用 `TrainingRecordService.get_record_for_viewer("audio_submission", ...)`。
  - `backend/src/sales_trainer/regrade_api.py`：四个 regrade route 继续先执行当前 `can_regrade_sales_trainer_history()` 权限门槛，同时向 service 传入 `viewer=current_user` 和 `_team_scope(current_user)`。
  - `backend/tests/integration/test_newcomer_training_path_regrade_api.py`：保留当前 content_admin 403/admin 成功路径，新增 service 直调同部门成功/跨部门失败，并用 monkeypatch 临时允许 manager regrade，证明 route 层同部门 preview 成功、跨部门 run 404 且未写 `sales_trainer_regrade_runs`。
  - `backend/tests/integration/test_newcomer_training_path_audio_regrade_api.py`：同样覆盖 audio regrade service/API 的同部门与跨部门 scope。
- 验证：
  - `cd backend && .venv/bin/ruff check src/sales_trainer/regrade_api.py src/sales_trainer/services/regrade_service.py src/sales_trainer/services/audio_regrade_service.py tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/integration/test_newcomer_training_path_article_api.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/integration/test_newcomer_training_path_article_api.py::test_should_reject_article_progress_for_content_outside_active_path -q`：3 passed，1 warning。
  - `cd backend && .venv/bin/mypy src/sales_trainer/regrade_api.py src/sales_trainer/services/regrade_service.py src/sales_trainer/services/audio_regrade_service.py --follow-imports=skip`：Success，3 source files。
- 未通过/不作为完成证据：
  - 本阶段未修改生产 regrade 权限 allowlist；manager 正式开放重评仍是产品权限策略，不在本阶段擅自扩大。
  - 本阶段当时尚未重跑 `bash scripts/critical-quality-gate.sh`，旧 00:08 full gate 仅作为历史基线；后续已于 2026-06-29 01:24 重新执行 full gate 并通过，见下节。
- 结论：
  - regrade 对象级 scope 不再只是“未来要补”的文档项；service/API/test 已经把未来 manager 权限开放时的跨部门 fail-closed 行为固定住。

## 2026-06-29 01:24 当前工作树 full critical gate 复验

- 要证明什么：
  - 00:58、01:09 和 01:18 后续代码改动不能只停留在聚焦验证，必须重新进入完整 deterministic critical gate。
  - regrade service/API 对象级 scope、material replay service scope、商务技巧 Journey binding、service 授权与 Journey next-step 真源、admin records/analytics 筛选、StepFun endpoint 契约补强都没有破坏核心闭环。
  - 当前工作树受控文件没有写入用户提供的 StepFun / DeepSeek 测试密钥明文。
- 验证：
  - `bash scripts/critical-quality-gate.sh`：2026-06-29 01:24:48 CST 复跑通过，证据 `.sisyphus/evidence/task-9-quality-gate.txt` 结尾为 `Critical quality gate passed`。
  - Secret hygiene scan：448 files scanned，passed。
  - Backend ruff：通过。
  - Web typecheck：通过。
  - Web lint：0 errors / 85 warnings。
  - Vitest coverage gate：27 files / 246 tests passed。
  - Playwright smoke：9 passed。
  - Playwright newcomer closed-loop E2E：11 passed / 1 skipped，包含 realtime roleplay local provider、AI Coach recoverable errors、fresh quiz/audio/AI Coach active revision、admin analytics、restricted manager fail-closed、历史回放、配置异常 fail-closed。
  - Playwright presentation Phase 4：2 passed。
  - Playwright sales Phase 4：1 passed。
  - Backend newcomer coverage gate：34 passed，coverage 45.47%，达到 fail-under 45。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend core gate：323 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
- 结论：
  - 2026-06-29 01:24 full gate 是该阶段的 deterministic 完整门禁证据，覆盖 00:58、01:09、01:18 的后续代码改动。
  - 该 full gate 仍不代表 StepFun real provider 已通过；StepFun 真实 provider 证据仍是 HTTP 401 / `upstream_auth_rejected`，需外部控制台授权或更换可用 key 后复跑强制 provider gate。

## 2026-06-29 01:40 StepFun realtime provider 预检治理与旧直连旁路清理

- 要证明什么：
  - StepFun 真实 provider 的剩余 401 不能被简单写成“key 一定无效”；必须把 key、账号 Realtime 权限、model 授权、Step Plan 路径组合拒绝写成可复跑诊断。
  - 本地预检不能打印 `STEPFUN_API_KEY`、`Authorization` 或 `Bearer ...`，也不能发起真实网络连接。
  - StepFun 上游连接不能保留第二套绕过 `StepFunTransport` 的直连实现，避免未来 MRO/继承顺序变化绕过 endpoint 构造、401 分类和 session.update 契约。
- 子代理发现与主 Agent 复核：
  - 子代理复核 `critical-quality-gate.sh` 后确认真实 provider evidence 不写密钥；当前 401 只能证明“上游授权/订阅/model/endpoint 组合被拒绝”，不能证明唯一原因是 key 无效。
  - 子代理指出 `StepFunRealtimePolicyMixin` 中仍有旧 `_connect_upstream()` 直接调用 `websockets.connect`；主 Agent 用 CodeGraph 复核当前 MRO 后确认运行时使用的是 `StepFunRealtimeConnectionMixin`，但旧方法是未来旁路风险。
  - 官方 Realtime 文档公开模型列表不含 `step-audio-2.3`；本任务仍按用户要求默认该模型，但必须标记“需控制台授权确认”。
- 实现：
  - `scripts/check_stepfun_realtime_prereqs.py`：新增不联网预检脚本，读取环境或 `backend/.env`，校验 key 是否缺失/占位、Realtime URL 是否 `wss://` 且有 host、最终 endpoint 是否结构化附加 model、是否 Step Plan path、model 是否在公开 Realtime 文档列表内；输出只含 `<configured>/<missing>` 和不含密钥的 endpoint。
  - `backend/tests/unit/test_stepfun_realtime_prereqs.py`：覆盖 key 脱敏、placeholder 阻断和未知模型 `--fail-on-warnings` 返回 3；02:25 后 `step-audio-2.3` 已按用户要求纳入当前默认 allowlist。
  - `backend/src/sales_bot/websocket/stepfun_realtime_policy.py`：删除旧 `_connect_upstream()` 直连实现和对应 imports。
  - `backend/tests/unit/test_stepfun_realtime_handler.py`：新增结构性断言，防止 `StepFunRealtimePolicyMixin` 重新拥有 `_connect_upstream`。
  - `docs/api-contract/voice-runtime.md`、`external-verification-runbook.md`、`scripts/README.md`、`audit-closure-matrix.md`、`final-verification-report.md`：同步预检命令、Step Plan 路径需控制台/官方支持确认、`step-audio-2.3` 作为当前默认且仍需真实 provider 授权确认的口径。
- 验证：
  - `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env`：exit 0；输出 `api_key_redacted="<configured>"`，`endpoint_without_secret="wss://api.stepfun.com/v1/realtime?model=step-audio-2.3"`，不输出密钥。
  - `python3 scripts/check_stepfun_realtime_prereqs.py --env-file <unknown-model-env> --fail-on-warnings`：exit 3，证明严格预检会阻止未知模型被误当成已授权。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_stepfun_realtime_prereqs.py tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_realtime_handler.py::test_policy_mixin_must_not_own_stepfun_upstream_connection tests/unit/test_stepfun_realtime_handler.py::test_connect_upstream_delegates_connection_to_shared_stepfun_transport -q`：21 passed，1 warning。
  - `cd backend && .venv/bin/ruff check ../scripts/check_stepfun_realtime_prereqs.py tests/unit/test_stepfun_realtime_prereqs.py tests/unit/test_stepfun_realtime_handler.py src/sales_bot/websocket/stepfun_realtime_policy.py`：通过。
- 结论：
  - StepFun real provider 仍未通过，不能计作完成；但剩余阻塞已经从“泛泛的 401”收口为可复跑、可脱敏、可区分 key/URL/model 授权的预检治理。
  - 上游连接路径的旧直连旁路已清理，StepFun 上游连接继续统一由 `StepFunTransport` 承担。

## 2026-06-29 01:45 当前工作树 full critical gate 复验

- 要证明什么：
  - 01:40 的 StepFun 预检脚本、旧直连旁路清理、runbook/契约口径修正不能只停留在聚焦验证，必须进入完整 deterministic critical gate。
  - 当前工作树仍无受控明文测试密钥，且 newcomer E2E、Phase 4 E2E、backend coverage/mypy/core/smoke 都未回退。
- 验证：
  - `bash scripts/critical-quality-gate.sh`：2026-06-29 01:45:52 CST 复跑通过，证据 `.sisyphus/evidence/task-9-quality-gate.txt` 结尾为 `Critical quality gate passed`。
  - Secret hygiene scan：448 files scanned，passed。
  - Backend ruff：通过。
  - Web typecheck：通过。
  - Web lint：0 errors / 85 warnings。
  - Vitest coverage gate：27 files / 246 tests passed。
  - Playwright smoke：9 passed。
  - Playwright newcomer closed-loop E2E：11 passed / 1 skipped。
  - Playwright presentation Phase 4：2 passed。
  - Playwright sales Phase 4：1 passed。
  - Backend newcomer coverage gate：34 passed，coverage 45.47%，达到 fail-under 45。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend core gate：323 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
- 结论：
  - 2026-06-29 01:45 full gate 是当时工作树的 deterministic 完整门禁证据；随后 2026-06-29 02:31 full gate 已覆盖 00:58、01:09、01:18、01:40、02:00、02:15、02:25 的后续代码改动。
  - 该 full gate 仍不代表 StepFun real provider 已通过；StepFun 真实 provider 证据仍是 HTTP 401 / `upstream_auth_rejected`，需外部控制台授权、model 授权和必要的 Step Plan Realtime 路径确认后复跑强制 provider gate。

## 2026-06-29 02:00 历史生产回填 dry-run 导出脚本补强

- 要证明什么：
  - `external-verification-runbook.md` §4 不能继续只写“未来脚本”占位；生产回填前至少要有当前仓库可执行、只读、可解析、可脱敏的 dry-run 预览。
  - dry-run 预览必须输出总扫描条数、自动回填记录数、人工复核记录数、legacy 标记记录数、分类样例 id、预期写入字段列表。
  - 当前阶段不得新增任何生产写入路径；没有产品/运维审批前不能提供隐式 apply。
- 子代理发现与主 Agent 复核：
  - 子代理 Sagan the 5th 复核后给出 `PARTIAL`：已有 `NewcomerDeadDataDiagnosticsService` 和只读 API，但 runbook 的 production backfill dry-run 字段不完整，且脚本缺少 `--dry-run/--limit/expected_write_fields`，默认全量 issues 也有容量和隐私风险。
  - 主 Agent 接受该结论，并把脚本收口为“默认聚合 + capped samples；显式 `--include-issues` 才输出脱敏明细”。
- 实现：
  - `backend/scripts/export_newcomer_dead_data_diagnostics.py`：新增只读导出脚本，复用 `NewcomerDeadDataDiagnosticsService`，支持 `--dry-run`、`--limit`、`--sample-limit`、`--output`、`--include-issues`；显式 import `agent.models` 注册 ORM mapper，避免命令行脚本绕过 app bootstrap 时触发关系解析失败。
  - 脚本输出 `scan_scope`、`summary.auto_backfill_records/manual_review_records/legacy_mark_records`、`sample_record_ids`、`expected_write_fields`、`warnings`、`rollback_plan`；当前 `auto_backfill=[]`，表示没有授权自动写入字段。
  - 脚本递归脱敏 `api_key`、`authorization`、`bearer`、`token`、`password`、`phone/mobile/email`、`storage_key`、`original_filename`、`file_hash`、`transcript`、`system_prompt`、`scoring_template`、`prompt`、`answer` 等字段。
  - `backend/tests/unit/test_newcomer_dead_data_diagnostics_export.py`：覆盖 dry-run/no-mutation 语义、扫描与样例计数、expected write fields、默认省略 issues、嵌套敏感字段脱敏、`--dry-run --limit` 参数兼容。
  - `external-verification-runbook.md`、`audit-closure-matrix.md`、`final-verification-report.md`：把历史回填章节从未来占位更新为实际脚本命令和验收口径，同时保留 apply 需人工决策。
- 验证：
  - `cd backend && .venv/bin/ruff check scripts/export_newcomer_dead_data_diagnostics.py tests/unit/test_newcomer_dead_data_diagnostics_export.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_dead_data_diagnostics_export.py -q`：3 passed，1 warning。
  - `cd backend && .venv/bin/python scripts/export_newcomer_dead_data_diagnostics.py --dry-run --limit 50 --sample-limit 3 --output /tmp/newcomer-backfill-preview.json`：成功写出 dry-run JSON。
  - `python3 -m json.tool /tmp/newcomer-backfill-preview.json >/dev/null`：通过。
  - `rg -i "api[_-]?key|authorization|bearer|token|password|phone|mobile|storage_key|original_filename|file_hash|transcript|system_prompt|scoring_template" /tmp/newcomer-backfill-preview.json`：无命中。
  - 样例输出确认：`mode=dry_run`、`mutates_history=false`、`scan_scope.limit=50`、`summary.total_scanned_records=57`、`summary.auto_backfill_records=0`、`summary.manual_review_records=4`、`issues_omitted=true`。
- 未通过/不作为完成证据：
  - 这不是生产 apply 脚本；当前脚本没有 `--apply`，也不会写库。
  - materials/material versions 仍按当前 diagnostics 服务扫描全部库存；若生产规模很大，正式 apply 前需另行评估批次、分页和只读锁影响。
  - 本阶段当时尚未重新执行 full `bash scripts/critical-quality-gate.sh`；随后已于 2026-06-29 02:05 重新执行 full gate 并通过，见下节。
- 结论：
  - 历史生产回填从“只有 runbook 占位要求”提升为“只读 dry-run 可执行、可解析、可脱敏、有单测”；但生产写入范围、审批、备份和回滚仍是人工决策项，不能标记 apply 完成。

## 2026-06-29 02:05 当前工作树 full critical gate 复验

- 要证明什么：
  - 02:00 新增的历史生产回填 dry-run 导出脚本、单测和 runbook/报告更新不能只停留在聚焦验证，必须进入完整 deterministic critical gate。
  - 当前工作树仍无受控明文测试密钥，且 newcomer E2E、Phase 4 E2E、backend coverage/mypy/core/smoke 都未回退。
- 验证：
  - `bash scripts/critical-quality-gate.sh`：2026-06-29 02:05:04 CST 复跑通过，证据 `.sisyphus/evidence/task-9-quality-gate.txt` 结尾为 `Critical quality gate passed`。
  - Secret hygiene scan：448 files scanned，passed。
  - Backend ruff：通过。
  - Web typecheck：通过。
  - Web lint：0 errors / 85 warnings。
  - Vitest coverage gate：27 files / 246 tests passed。
  - Playwright smoke：9 passed。
  - Playwright newcomer closed-loop E2E：11 passed / 1 skipped。
  - Playwright presentation Phase 4：2 passed。
  - Playwright sales Phase 4：1 passed。
  - Backend newcomer coverage gate：34 passed，coverage 45.47%，达到 fail-under 45。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend core gate：323 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
- 结论：
  - 2026-06-29 02:05 full gate 是当时工作树的 deterministic 完整门禁证据；随后 2026-06-29 02:31 full gate 已覆盖 00:58、01:09、01:18、01:40、02:00、02:15、02:25 的后续代码改动。
  - 该 full gate 仍不代表 StepFun real provider 已通过，也不代表生产历史回填 apply 已授权；StepFun 仍需外部控制台/model 授权确认，生产回填写入仍需产品/运维审批、备份和回滚策略。

## 2026-06-29 02:15 历史生产回填 dry-run 容量治理补强

- 要证明什么：
  - 02:00 已有 dry-run 导出脚本，但 materials/material versions 库存扫描仍有全量扫描风险；生产预览需要可控扫描上限，并且必须显式告诉运维结果是否被截断。
  - 限制 versions 扫描后，不能误报已扫描 material 的 current version 缺失。
  - HTTP dead-data diagnostics API 保持向后兼容；新增字段只能增强诊断，不能破坏现有调用方。
- 子代理与主 Agent 复核：
  - 主 Agent 用 CodeGraph 优先探索 dead data diagnostics 影响面；由于 `newcomer_dead_data_diagnostics_service.py` 是未跟踪新文件，CodeGraph 未能直接打开该文件，随后精确读取服务/API/脚本/test 文件。
  - 子代理 Pauli the 5th 只读复核指出三处缺口：`material_scan_limit` 下 `ORPHAN_MATERIAL` 可能误报、API 契约缺 partial scan 字段、CLI 导出单测未进 critical gate。主 Agent 复核源码后补齐三项，未直接采信子代理结论。
- 实现：
  - `NewcomerDeadDataDiagnosticsService` 新增 `material_scan_limit`，默认 `1000`。
  - `_scan_material_inventory()` 对 `SalesTrainerMaterial` 和 `SalesTrainerMaterialVersion` 分别按 `updated_at desc` 限量扫描，同时查询 total counts，返回 `total_materials`、`total_versions`、`limit`、`truncated`。
  - 对已扫描 material 的 `current_version_id`，若不在版本样本内，则按 id 精确读取，避免因版本 limit 产生 `MATERIAL_CURRENT_VERSION_MISSING` 假阳性。
  - 对历史提交引用的 `confirmed_material_version_id` 增加精确 version -> material 映射，避免引用版本落在扫描切片外时误报 `ORPHAN_MATERIAL`。
  - `export_newcomer_dead_data_diagnostics.py` 新增 `--material-scan-limit`，`scan_scope` 输出 `audio_scan_limit`、`material_scan_limit`、材料扫描数、总数和 `material_inventory_truncated`。
  - `docs/api-contract/sales-trainer.md` 同步 `scanned.materials.{total_materials,total_versions,limit,truncated}` 与 partial scan 语义；`scripts/critical-quality-gate.sh` 纳入 `tests/unit/test_newcomer_dead_data_diagnostics_export.py`。
  - `external-verification-runbook.md` 的生产 dry-run 命令加入 `--material-scan-limit 1000`，并说明 `material_inventory_truncated=true` 时只能作为采样预览。
- 验证：
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/newcomer_dead_data_diagnostics_service.py scripts/export_newcomer_dead_data_diagnostics.py tests/unit/test_newcomer_dead_data_diagnostics_export.py tests/integration/test_newcomer_training_path_config_api.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_newcomer_dead_data_diagnostics_export.py tests/integration/test_newcomer_training_path_config_api.py::test_should_limit_material_inventory_scan_in_dead_data_diagnostics tests/integration/test_newcomer_training_path_config_api.py::test_should_not_report_orphan_material_when_referenced_version_is_outside_scan_limit -q`：6 passed，1 warning。
  - `cd backend && .venv/bin/python scripts/export_newcomer_dead_data_diagnostics.py --dry-run --limit 50 --material-scan-limit 1 --sample-limit 3 --output /tmp/newcomer-backfill-preview-limited.json`：成功写出 dry-run JSON。
  - `python3 -m json.tool /tmp/newcomer-backfill-preview-limited.json >/dev/null`：通过。
  - `rg -i "api[_-]?key|authorization|bearer|token|password|phone|mobile|storage_key|original_filename|file_hash|transcript|system_prompt|scoring_template" /tmp/newcomer-backfill-preview-limited.json`：无命中；命令返回码 1 代表无匹配。
  - 样例输出确认：`audio_scan_limit=50`、`material_scan_limit=1`、`materials_scanned=1`、`materials_total=3`、`material_versions_scanned=1`、`material_versions_total=2`、`material_inventory_truncated=true`、`summary.total_scanned_records=54`。
- 未通过/不作为完成证据：
  - 本阶段当时尚未重新执行 full `bash scripts/critical-quality-gate.sh`；随后已于 2026-06-29 02:31 重新执行 full gate 并通过，见下节。
  - 这仍然不是生产 apply 脚本；当前脚本没有 `--apply`，也不会写库。
- 结论：
  - 生产回填 dry-run 预览现在具备材料库存扫描限流和截断信号；但生产写入范围、审批、备份和回滚仍是人工决策项，不能标记 apply 完成。

## 2026-06-29 02:25 Step Audio 2.3 默认模型补强

- 要证明什么：
  - 用户指定 Step Audio 2.3 后，当前默认配置不能只停留在 env fallback；DB server default、默认 runtime profile seed、admin 表单和预检脚本也必须一致。
  - 真实测试 key 不得写入仓库、日志、文档或证据。
- 子代理与主 Agent 复核：
  - 子代理 Explorer the 6th 只读复核旧默认值残留，指出运行时代码已是 `step-audio-2.3`，但 `CLAUDE.md`、admin 语音运行时表单、历史迁移链/seed 资产仍有旧默认或示例残留。
  - 主 Agent 用 CodeGraph 复核 `VoiceRuntimePolicyService`、`VoiceRuntimeProfile`、admin voice runtime API 和 StepFun transport 调用链；决定不改历史迁移文件本身，而新增可追踪、可回滚 migration 覆盖当前 head。
- 实现：
  - 新增 `backend/alembic/versions/20260629_0215_087_stepfun_default_model_audio23.py`，把 `voice_runtime_profiles.model_name` server default 改为 `step-audio-2.3`，并仅更新默认 `stepfun_realtime` profile 中旧模型值；downgrade 回到 `step-audio-2`。
  - `web/src/app/admin/voice-runtime/page.tsx` 的新建表单默认模型改为集中常量 `DEFAULT_STEPFUN_REALTIME_MODEL = "step-audio-2.3"`。
  - `CLAUDE.md`、`backend/scripts/seed_presales_cio_first_visit.py`、`backend/scripts/seed_presales_mvp.py`、`backend/config-assets/presales-cio-first-visit.export.json` 同步为 `step-audio-2.3`。
  - `scripts/check_stepfun_realtime_prereqs.py` 把 `step-audio-2.3` 纳入已知模型集合；预检仍会阻断 placeholder key、校验 wss URL，并且不输出密钥。
- 验证：
  - `cd backend && .venv/bin/ruff check src/admin/api/voice_runtime.py src/sales_bot/services/voice_runtime_policy.py src/sales_bot/websocket/voice_runtime_profile.py src/sales_bot/websocket/stepfun_realtime_handler.py scripts/seed_presales_cio_first_visit.py scripts/seed_presales_mvp.py tests/unit/test_stepfun_realtime_prereqs.py tests/unit/test_voice_runtime_policy_service.py tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_payload_snapshots.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_stepfun_realtime_prereqs.py tests/unit/test_voice_runtime_policy_service.py::test_env_fallback_policy_defaults_to_latest_realtime_model tests/unit/test_voice_runtime_policy_service.py::test_resolve_effective_policy_uses_step_audio_23_default_profile tests/unit/test_stepfun_transport.py tests/unit/test_stepfun_payload_snapshots.py -q`：30 passed，1 warning。
  - `cd backend && .venv/bin/python -m py_compile alembic/versions/20260629_0215_087_stepfun_default_model_audio23.py && .venv/bin/alembic heads`：`20260629_0215_087 (head)`。
  - `cd web && npx vitest run src/lib/api/client-governance.test.ts src/app/admin/asset-governance.test.tsx`：2 files / 14 tests passed。
  - `cd web && npx eslint src/app/admin/voice-runtime/page.tsx src/lib/api/client-governance.test.ts src/app/admin/asset-governance.test.tsx --quiet`：通过。
  - `rg --pcre2 -n "STEPFUN_REALTIME_MODEL=step-audio-2(?!\\.3)|model_name\\s*[:=]\\s*['\\\"]step-audio-2['\\\"]|profile\\.model_name\\s*=\\s*['\\\"]step-audio-2['\\\"]" CLAUDE.md .env.example backend/.env.example backend/src backend/scripts backend/config-assets web/src/app/admin/voice-runtime web/src/lib web/src/app/admin/asset-governance.test.tsx backend/alembic/versions/20260629_0215_087_stepfun_default_model_audio23.py`：无命中。
- 未通过/不作为完成证据：
  - 本阶段当时尚未重新执行 full `bash scripts/critical-quality-gate.sh`；随后已于 2026-06-29 02:31 重新执行 full gate 并通过，见下节。
  - 未把用户提供的 StepFun/DeepSeek 测试 key 写入仓库；如需真实 provider 复跑，应通过本地 env 注入。
- 结论：
  - Step Audio 2.3 已成为当前默认配置真源；真实 StepFun 上游是否通过仍取决于 key/账号/model Realtime 授权。

## 2026-06-29 02:31 当前工作树 full critical gate 复验

- 要证明什么：
  - 02:15 dead-data 容量治理和 02:25 Step Audio 2.3 migration/admin 默认值进入完整门禁后仍不破坏新人训练闭环。
  - 新增 migration 可在 smoke 启动时通过 `alembic upgrade head` 执行。
- 验证：
  - `bash scripts/critical-quality-gate.sh`：2026-06-29 02:31:13 CST 复跑通过，证据 `.sisyphus/evidence/task-9-quality-gate.txt` 结尾为 `Critical quality gate passed`。
  - Secret hygiene scan：448 files scanned，passed。
  - Backend ruff：通过。
  - Web typecheck：通过。
  - Web lint：0 errors / 85 warnings。
  - Vitest：27 files / 246 tests passed。
  - Smoke Playwright：9 passed。
  - Newcomer closed-loop Playwright：11 passed / 1 skipped。
  - Presentation Phase 4 Playwright：2 passed。
  - Sales Phase 4 Playwright：1 passed。
  - Backend newcomer coverage gate：34 passed，coverage 45.43%，达到 fail-under 45。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend core gate：329 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
  - Smoke 启动日志显示 Alembic 执行 `20260616_086 -> 20260629_0215_087`，证明 Step Audio 2.3 migration 可升级。
- 结论：
  - 2026-06-29 02:31 full gate 是当时工作树的 deterministic 完整门禁证据，覆盖 02:15 与 02:25 新增改动；随后 2026-06-29 02:57 full gate 已覆盖 02:50 admin analytics 反审计补强。

## 2026-06-29 02:43/02:50 真实 provider 复验与 admin analytics 反审计补强

- 要证明什么：
  - 用户明确要求写入的 StepFun/DeepSeek 测试凭证只进入 gitignore 的本地 `backend/.env`，不进入受 Git 跟踪文件。
  - DeepSeek/AI Coach 真实 provider 门禁能真实执行通过；StepFun 真实 provider 若仍失败，必须保留为上游授权阻塞，不能伪装完成。
  - admin analytics 的 `limit` 必须真实限制 Journey 构建/加载，而不是聚合后截断；`risk_reasons` 必须由后端契约输出，前端不能 fallback 到模块 key；analytics 管理入口必须有负向权限回归。
- 实现：
  - 本地 `backend/.env` 写入 `STEPFUN_API_KEY`、`STEPFUN_REALTIME_MODEL=step-audio-2.3`、DeepSeek OpenAI-compatible `LLM_API_KEY/OPENAI_API_KEY`、`LLM_BASE_URL/OPENAI_BASE_URL` 和 `LLM_MODEL/OPENAI_MODEL=deepseek-chat`；`backend/.env` 由 `.gitignore` 忽略。
  - `backend/src/sales_trainer/services/training_journey_service.py`：`get_admin_analytics()` 将 `limit` 下推到 `_filtered_admin_journeys()`；无 journey 过滤时 SQL 查询直接带 `LIMIT`，有 journey 过滤时最多构建到满足 `limit` 的匹配 Journey；`list_admin_journeys()` 传入 `offset + limit` 保持分页语义；`risk_learners` 增加后端生成的 `risk_reasons`。
  - `backend/src/sales_trainer/schemas.py`：`TrainingJourneyAnalyticsResponse` 从宽松 `dict[str, Any]` 收紧为类型化 Pydantic DTO，包含 summary/funnel/module/heatmap/trend/level/risk/filter 子 schema。
  - `web/src/lib/api/types.ts`：`TrainingJourneyAnalyticsRiskLearner.risk_reasons` 改为必填，`risk_module_count` 改为必填。
  - `web/src/app/admin/sales-trainer/analytics/page.tsx`：删除 `risk_reasons -> risk_module_keys` fallback。
  - `docs/api-contract/sales-trainer.md`、`external-verification-runbook.md`、`audit-closure-matrix.md`、`final-verification-report.md` 同步更新真实 provider 和 analytics 契约口径。
- 验证：
  - `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env`：`status=ready`，`api_key_redacted=<configured>`，`model=step-audio-2.3`，不输出密钥。
  - `set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh`：开放平台 URL 到达 StepFun 上游后 HTTP 401，`.sisyphus/evidence/newcomer-real-provider-gate.json` 为 `classification=upstream_auth_rejected`、`model=step-audio-2.3`。
  - `set -a; . backend/.env; set +a; STEPFUN_REALTIME_URL=wss://api.stepfun.com/step_plan/v1/realtime CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh`：候选 Step Plan URL 同样到达 StepFun 上游后 HTTP 401。
  - `set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh`：1 Playwright passed，`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json` 为 `status=passed`、`classification=executed`、`model=deepseek-chat`、`fallback_used=false`。
  - `cd backend && .venv/bin/ruff check src/sales_trainer/services/training_journey_service.py src/sales_trainer/schemas.py tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py`：通过。
  - `cd backend && .venv/bin/pytest --no-cov tests/unit/test_sales_trainer_training_journey_service.py::test_should_apply_analytics_limit_to_loaded_journeys tests/integration/test_newcomer_training_journey_api.py::test_should_list_and_analyze_admin_journeys_with_team_scope tests/integration/test_newcomer_training_journey_api.py::test_should_reject_non_record_viewers_from_admin_journey_analytics tests/integration/test_newcomer_training_journey_api.py::test_should_apply_analytics_limit_to_loaded_journeys tests/integration/test_newcomer_training_journey_api.py::test_should_return_typed_risk_reasons_for_admin_journey_analytics -q`：5 passed，1 warning。
  - `cd web && npx vitest run src/app/admin/sales-trainer/analytics/page.test.tsx`：1 file / 5 tests passed。
  - `cd web && npx eslint src/app/admin/sales-trainer/analytics/page.tsx src/app/admin/sales-trainer/analytics/page.test.tsx --quiet`：通过。
- 结论：
  - AI Coach/DeepSeek 真实 provider 已通过；StepFun 真实 provider 在开放平台 URL 与候选 Step Plan URL 下均为上游 401，仍是授权/账号/model/套餐问题，不是本地 env 未写入、模型未切换或 endpoint query 构造错误。
  - admin analytics 三项反审计问题已代码闭环并有 focused 测试证据；随后已于 2026-06-29 02:57 进入 full `scripts/critical-quality-gate.sh` 并通过，见下节。
  - 三类等级真实枚举/来源、历史生产回填 apply、StepFun 控制台授权仍是人工/外部决策项，只能标为“有处理结果”，不能标为“全部已验证”。

## 2026-06-29 02:57 当前工作树 full critical gate 复验

- 要证明什么：
  - 02:50 admin analytics 反审计补强已进入完整门禁，而不是只停留在 focused 测试。
  - 类型化 analytics DTO、`risk_reasons` 必填、analytics 权限负向测试和 Journey 构建 limit 下推不破坏新人训练完整闭环。
- 验证：
  - `bash scripts/critical-quality-gate.sh`：2026-06-29 02:57:30 CST 复跑通过，证据 `.sisyphus/evidence/task-9-quality-gate.txt` 结尾为 `Critical quality gate passed`。
  - Secret hygiene scan：448 files scanned，passed。
  - Backend ruff：通过。
  - Web typecheck：通过。
  - Web lint：0 errors / 85 warnings。
  - Vitest：27 files / 246 tests passed。
  - Smoke Playwright：9 passed。
  - Newcomer closed-loop Playwright：11 passed / 1 skipped。
  - Presentation Phase 4 Playwright：2 passed。
  - Sales Phase 4 Playwright：1 passed。
  - Backend newcomer coverage gate：36 passed，coverage 45.72%，达到 fail-under 45。
  - Backend newcomer mypy gate：8 source files，无类型错误。
  - Backend core gate：331 passed，1 warning。
  - Backend smoke regression：58 passed，1 warning。
- 结论：
  - 2026-06-29 02:57 full gate 是当前工作树最新 deterministic 完整门禁证据，覆盖 02:50 admin analytics 反审计补强。
  - 该 full gate 仍不代表 StepFun real provider 已通过，也不代表生产历史回填 apply 已授权；StepFun 仍需外部控制台/model 授权确认，生产回填写入仍需产品/运维审批、备份和回滚策略。
