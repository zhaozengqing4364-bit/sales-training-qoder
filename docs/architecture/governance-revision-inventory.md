# 发布治理修订模型盘点

> 状态：阶段 0 基线盘点。本文是后续实现 `logical_id + revision_id + active_revision + snapshot + audit + rollback + regrade` 的事实清单，不是新存储表设计。

## 盘点规则

每个可配置 surface 必须能回答：

- `surface_key`：稳定识别名。
- `owner`：业务归属模块。
- `backing_store`：当前权威存储或兼容存储。
- `lifecycle`：当前草稿、发布、归档、回滚或不可编辑语义。
- `permission_policy`：权限权威位置。
- `audit_policy`：操作记录或审计事件来源。
- `snapshot_policy`：运行时或历史记录如何冻结当时内容。
- `public_projection`：学员端、管理员端或运行时读取面。
- `phase_0_gap`：进入实现前必须显式处理的缺口。

## Surface Inventory

| surface_key | owner | backing_store | lifecycle | permission_policy | audit_policy | snapshot_policy | public_projection | phase_0_gap |
|---|---|---|---|---|---|---|---|---|
| `sales_trainer.path_config` | 新人训练路径 | 当前由 `SalesTrainerUnit.config.path` 与 path service 聚合；计划提升为路径级 revision 真源 | 已有发布单元聚合；路径级 working/active revision 待实现 | `backend/src/sales_trainer/permissions.py` 的 `sales_trainer.manage_modules` | `operation_log_service`，后续需补 before/after revision、reason、trace_id | learner path projection 应冻结 module/unit/paper/content refs；旧记录使用 snapshot | learner `/api/v1/sales-trainer/paths`，admin path config 页面 | 不得继续把多个 unit config 反推作为唯一真源；需要 active_revision 指针 |
| `sales_trainer.unit` | 新人训练路径 | `SalesTrainerUnit` | 已发布后当前更新受限，常见路径是复制草稿/重新发布 | `manage_modules`、内容管理员兼容角色 | sales trainer operation log | attempt/submission 应记录 unit revision 或 legacy snapshot | admin unit/module 管理，learner module DTO | 训练单元需拆出 logical unit 与 immutable unit revision |
| `sales_trainer.exam_paper` | 新人训练路径商务技巧 | `SalesTrainerExamPaper` 与兼容 quiz unit | paper lifecycle 已存在但与 backing unit 耦合 | `manage_papers` / `manage_questions` | operation log，需明确 paper_id 与 unit_id 映射 | quiz attempt 应冻结 paper revision、question revision refs 和 answer snapshot | admin papers，learner paper attempt | paper 应成为 admin/API 语义权威，unit 仅兼容 projection |
| `sales_trainer.question` | 新人训练路径与课程题库 | `QuestionItem`，销售训练通过 adapter 复用 | published 后不可自然编辑 | test bank / sales trainer question 权限 | test bank 或 sales trainer operation log | answer snapshot 已保存题目内容；revision lineage 待补 | admin question bank，paper binding | 题干、选项、答案、分值、AI prompt 需要 question revision |
| `sales_trainer.article_binding` | 新人训练路径商务技巧 | LearningContent 绑定写入 unit/path config | 绑定生命周期跟随 unit/path config | `manage_modules` + learning content 权限 | operation log | study/attempt 需要 content revision 或 content snapshot | admin article binding，learner article page | 绑定关系应进入 path/module binding_revision |
| `sales_trainer.audio_material` | 新人训练路径录音模块 | material master + version/current version | 已有 material version 语义 | `manage_materials` | operation log | audio submission 已冻结 `material_snapshot`、`task_brief_snapshot`、`score_scheme_snapshot` | learner upload task，admin material library | 需把 material version 映射为统一 revision lineage |
| `sales_trainer.score_prompt` | 新人训练路径 AI 评分 | prompt service / PromptTemplate binding | 非 draft 不可改；PromptTemplate 有独立治理 | `sales_trainer.manage_prompts` | operation log + PromptTemplate audit | score result 保存 prompt version/hash；revision_id 待补 | admin scoring prompt，runtime scoring | prompt hash 由后端编译产生，admin 不得手写 |
| `sales_trainer.regrade_run` | 新人训练路径历史重评 | `SalesTrainerRegradeRun` 或等价任务记录 | 高风险显式动作，不能由发布自动触发 | `regrade_history` / ops / super_admin | 必须记录 reason、trace_id、before/after、影响范围 | append-only 新评分结果，保留原始结果 | admin records/regrade UI | 需明确 rollback 与 regrade 分离 |
| `curriculum_practice.template` | 课程闭环 | `PracticeTemplate` + `published_asset_refs` | 发布门禁已存在；自然编辑 revision 待实现 | curriculum admin 权限 | publish gate / domain audit | session 创建时冻结 `curriculum_snapshot` | `/learning-path` 与 runtime session | template revision 应继续生成 published_asset_refs |
| `curriculum_practice.case_item` | 课程闭环 | `CaseItem` | published 后不可自然编辑 | curriculum content admin | domain audit | `curriculum_snapshot` / roleplay contract 冻结剧本事实 | template binding / runtime dossier | 需 case revision，旧 session 不读 latest |
| `curriculum_practice.role_profile` | 课程闭环 | `RoleProfile` | published 后不可自然编辑 | curriculum content admin | domain audit | `curriculum_snapshot.roleplay_contract` 冻结角色行为 | template binding / runtime prompt | 需 role revision，voice/规则变更只影响未来 |
| `curriculum_practice.learning_content` | 课程闭环与新人训练路径文章 | `LearningContent` | publish/archive 已有 | learning content admin | domain audit | study/session/attempt 应冻结 content revision 或 snapshot | article reader / template study stage | 与商务技巧文章共用 revision 语言 |
| `prompt_templates.template` | 平台 Prompt 治理 | PromptTemplateService / PromptTemplate | 已有模板治理与渲染 contract | PromptTemplate admin + domain binding 权限 | PromptTemplate audit | runtime 应保存 prompt revision/hash 或 compiled contract hash | prompt admin / AI runtime | 平台模板 CRUD 与 domain binding approval 需要边界 |
| `config_bundle.bundle` | 配置资产中心 | `ConfigBundle` / ConfigVersion / adapter | draft/validate/preview/publish/rollback/audit | config admin | ConfigBundle audit | ConfigBundle snapshot 可冻结配置版本 | config center | 现有同步可能更新已有 snapshot，不可直接作为 immutable revision 存储 |
| `business_rule_config.ruleset` | 业务规则配置 | `BusinessRuleConfig` | draft/publish/rollback/audit | config admin / domain policy | BusinessRuleConfig audit | runtime 读取 active ruleset；应记录规则版本 | runtime policy / admin config | 适合字段风险策略、阈值、开关，不适合承载所有内容资产 |
| `scoring_ruleset.ruleset` | 评分治理 | `ScoringRuleset` + ConfigBundle 同步 | publish/rollback/dry-run/audit | scoring admin | ScoringRuleset audit + ConfigBundle audit | report/read side 记录 ruleset id/version/hash | scoring admin / evaluation | active pointer 语义成熟，但需和 regrade_run 分离 |

## 阶段 0 结论

- 新人训练路径的配置真源需要从 unit 聚合迁到路径级 `active_revision`，但第一步不改表，先锁定契约和 adapter 边界。
- 历史记录优先读取已存在 snapshot；没有 revision lineage 的旧数据只标记 `legacy_snapshot_only`。
- `ConfigBundle`、`BusinessRuleConfig`、`ScoringRuleset` 是生命周期和审计参照；不是所有内容资产的统一存储答案。
- 路由层后续只能做鉴权、参数解析和调用 service。发布、回滚、重评、审计、权限边界进入 service/rules/audit 层。
- 管理端主路径展示业务语言；`module_key`、`unit_id`、`paper_key`、`sales_trainer` 等技术字段只能放在诊断展开区。

## Architecture Inventory

Task 2 盘点补充以下非内容资产 surface。它们不是新的业务存储设计，而是后续重构时判断影响面、权限、审计和发布门禁的事实索引。

### Composition Roots

| composition_root | owner | backing_store | lifecycle | permission_policy | audit_policy | snapshot_policy | public_projection | phase_0_gap |
|---|---|---|---|---|---|---|---|---|
| `backend/src/app_factory.py` | 平台后端 | FastAPI app factory 与 lifespan 注册 | 进程启动时组装；不承载业务发布生命周期 | 环境与生产配置校验在启动期失败 | 结构化启动日志与异常日志 | 不生成业务 snapshot | 后端进程入口 | 保持为唯一 app 组合根；不得把领域规则塞进启动函数 |
| `backend/src/router_registry.py` | 平台后端 | HTTP router mount 列表与 contributor 注册调用 | 代码发布生效 | 各 router 自己的 dependency / permission guard | 路由层不写业务审计 | 无运行时 snapshot | HTTP API surface | 同时负责 route mounting 与 contributor bootstrap，后续需拆成受控 bootstrap |
| `backend/src/websocket_routes.py` | 实时运行时 | Presentation / curriculum / sales WS mount 与 runtime gate | 代码发布生效，连接前 gate 决定可运行性 | WebSocket admission、owner、feature flag、runtime gate | admission 日志和 runtime 事件 | 只消费已冻结 runtime/session snapshot | `/ws/*` 实时连接 | 保持 Terminal failure 在连接前暴露，不能靠重连掩盖 |
| `backend/src/common/services/practice_session_ports.py` | 平台运行时端口 | 进程内 contributor registry | 注册顺序随 app bootstrap | composition root 可注册，业务代码只消费 port | 无业务审计；测试用 cleanup helper 清理注册表 | 由 contributor 提供 session/template/snapshot 能力 | practice session lifecycle | reverse dependency allowlist 需要逐步收缩 |

### API Domains

| api_domain | owner | backing_store | lifecycle | permission_policy | audit_policy | snapshot_policy | public_projection | phase_0_gap |
|---|---|---|---|---|---|---|---|---|
| `sales_trainer.learner_api` | 新人训练路径 | `SalesTrainerUnit`、path config projection、attempt/submission/result | learner 只读配置与提交记录；发布只影响未来 | learner auth 与对象归属 | submission/result operation log | attempt/submission 保存 snapshot 或 legacy snapshot | `/api/v1/sales-trainer/*`、`/sales-trainer/*` | 不得进入 realtime `sales_bot` session 创建路径 |
| `sales_trainer.admin_api` | 新人训练路径管理 | unit、material、paper、question、prompt、path revision、operation log | draft/working/published/archived、publish、rollback、regrade | `sales_trainer.permissions` capability projection | `SalesTrainerOperationLog` | 管理动作不重写历史 snapshot | `/api/v1/admin/sales-trainer/*`、admin UI | 高风险 prompt/regrade/rollback 必须使用后端权限与 reason/trace_id |
| `admin.newcomer_training_api` | 新人训练路径兼容管理面 | path config、business etiquette、paper/article binding | working/active revision 与兼容 facade | admin dependency + sales trainer capabilities | domain operation log | path/module binding revision refs | `/api/v1/admin/newcomer-training/*` | 前端 facade 仍需继续从 sales-trainer domain 拆分 |
| `curriculum_practice_api` | 课程闭环 | PracticeTemplate、CaseItem、RoleProfile、LearningContent、published_asset_refs | draft/publish/archive，发布门禁 | curriculum admin 权限 | curriculum domain audit / publish gate | `curriculum_snapshot` 和 roleplay contract 冻结 | `/learning-path`、practice runtime | runtime 不得从 latest asset 重拼 |
| `config_bundle_api` | 配置资产中心 | `ConfigBundle`、`ConfigVersion`、adapter read model | draft/validate/preview/publish/rollback/disable | config admin 权限 | `ConfigBundleAuditLog` | bundle/version snapshot | `/api/v1/admin/config-bundles/*`、config center | 只能作为 read/lifecycle facade，不能替代所有内容资产存储 |
| `prompt_template_api` | Prompt 治理 | PromptTemplate / PromptTemplateService | system template lock、default replacement、revision compile | platform admin + domain binding approval | `SystemLog` 与 domain operation log | compiled prompt contract hash | prompt admin、AI runtime | 平台 CRUD 与 Sales Trainer `manage_prompts` 边界需显式化 |

### Audit Carriers

| audit_carrier | owner | backing_store | lifecycle | permission_policy | audit_policy | snapshot_policy | public_projection | phase_0_gap |
|---|---|---|---|---|---|---|---|---|
| `SalesTrainerOperationLog` | 新人训练路径 | sales trainer operation log table/service | append-only 业务操作记录 | sales trainer admin 查看权限 | action、target、metadata、request_id | metadata 携带 before/after、reason、trace_id、影响范围 | admin operation logs | schema 未强制 before/after/reason；高风险动作必须在 service 层补齐 |
| `BusinessRuleConfigAuditLog` | 业务规则配置 | business rule audit table/service | append-only lifecycle audit | config admin | publish/rollback/disable 等版本变更 | before/after snapshot | config center / ruleset admin | 适合规则配置，不适合直接承载内容资产 |
| `ConfigBundleAuditLog` | 配置资产中心 | config bundle audit table/service | append-only bundle lifecycle audit | config admin | validate/preview/publish/rollback/disable | version snapshot | config bundle versions | 与 domain audit 需要索引关系，避免双重真相 |
| `SystemLog` | 平台治理 | system log table/service | append-only 平台事件 | platform admin | prompt template 等平台操作 | 事件 payload 记录 contract/hash 信息 | platform admin diagnostics | 与 Sales Trainer prompt binding audit 需要边界说明 |
| `ReleaseVerificationRecord` | 发布治理 | release verification DB/API 与 evidence path | candidate/check/result | release/admin 操作权限 | gate status、evidence path、失败原因 | 保存命令结果摘要，不替代原始 evidence | release verification API/UI | 需要指向 canonical quality gate，而不是形成第二套 release truth |

### Quality Gates

| quality_gate | owner | backing_store | lifecycle | permission_policy | audit_policy | snapshot_policy | public_projection | phase_0_gap |
|---|---|---|---|---|---|---|---|---|
| `scripts/critical-quality-gate.sh` | 发布门禁 | `.sisyphus/evidence/task-9-quality-gate.txt` 与 Playwright/backend 输出 | 手动或 CI 运行，结果随 evidence 固化 | 本地/CI 执行权限 | shell transcript | evidence 文件是门禁快照 | `.github/workflows/release-truth-gate.yml`、本地 release check | 作为 executable truth；`.omo/evidence/project-governance-refactor/quality-gate/` 只做镜像或索引 |
| `scripts/dependency-governance.sh` | 依赖治理 | dependency graph / allowlist / shell output | 手动或 CI slice 运行 | 开发者/CI | stdout artifact | 命令输出记录当前边界状态 | governance evidence | common reverse dependency allowlist 应随重构收缩 |
| `scripts/secret-scan.sh` | 安全门禁 | secret scan output | 每轮门禁前运行 | 开发者/CI | stdout artifact | 扫描结果文件 | release gate evidence | 必须先于长门禁执行，失败不得进入 release candidate |
| `backend/tests/unit/common/test_alembic_migration_graph.py` | migration graph | Alembic ScriptDirectory | 每次 migration 改动后运行 | 开发者/CI | pytest stdout | 当前 heads/revision graph | migration gate evidence | 已改为单 head 动态断言，避免 stale head 硬编码 |
