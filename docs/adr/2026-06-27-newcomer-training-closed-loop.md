# ADR-2026-06-27：新人训练完整闭环契约冻结

## Status

Accepted（2026-07-10 增补 Readiness 复核决策完整性）。本 ADR 冻结新人训练路径 Phase 1 的 API/运行时边界契约，作为后续权限、配置治理、TrainingJourney、AI Coach、Readiness 人工决定和 realtime 接入实现的门禁。

## 背景

新人训练路径已有路径配置、材料、文章、考卷、录音、AI 评分、AI Coach、训练记录和后台工作台基础，但 Phase 0 审计确认仍存在四类闭环缺口：

- learner 路径仍可在无 active path revision 时从旧 `SalesTrainerUnit.config.path` / `unit_backfill` 拼出正式读面，导致历史 lineage、发布回滚和审计解释失真。
- API 契约仍写明 realtime 模块只能是 disabled/coming-soon placeholder，无法承载“实时对练纳入完整闭环”的产品决策。
- 训练状态散落在 audio、quiz、business etiquette、AI Coach 等局部记录中，缺统一 TrainingJourney / ModuleProgress / ModuleOutcome 契约。
- 三类等级（角色等级、学员等级、训练阶段等级）和 AI Coach 必过语义未在闭环契约中统一表达，前端和管理看板容易继续自行推断。
- Readiness 人工复核曾复用记录读取权限并以通用 OperationLog 作为状态存储，导致 ops 可写、幂等与并发不可约束、有限日志窗口可能丢失当前状态，无法作为 realtime gate 的可信人工决定。

同时，`docs/architecture.md` 已明确 `sales_trainer` 不得直接 import `sales_bot/` 或 `training_runtime/` 创建或变更 realtime 会话；因此 realtime 接入必须先定义 binding/projection 契约，而不是在新人训练域内新建运行时。

## 决策

### 1. Active path revision 是 learner 唯一真源

learner 首页、模块入口、TrainingJourney、训练记录上下文和 realtime/AI Coach outcome projection 必须读取 active path revision。无 active revision 时，learner API 返回 typed diagnostic，例如 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`，不得从旧 unit config 拼正式路径。

旧 `unit_backfill` 只允许作为管理端迁移、诊断或历史回放说明来源暴露，必须标记 `legacy_snapshot_only=true`，不得伪造 revision id。

### 2. TrainingJourney 成为新人训练闭环读模型

新增 `TrainingJourney`、`ModuleProgress`、`ModuleOutcome` 契约，统一聚合：

- audio submission。
- quiz / paper attempt。
- business etiquette quiz attempt。
- AI Coach session。
- realtime roleplay session outcome。
- remediation、regrade、retry history。

第一阶段允许 TrainingJourney 先作为 read model projection 实现，不强制立即新增表。前端只渲染后端返回的 `TrainingStage`、`unmet_reasons` 和 `next_action`，不得自行推断完成、失败、未开放或异常状态。

### 3. 三类等级进入 API 契约

新人训练闭环同时暴露三类等级：

- 角色等级：通过 `RoleCapability` 表达能力、范围和拒绝原因，前端不得复制角色字符串矩阵。
- 学员等级：通过 `LearnerLevel` 表达等级 key、来源、排序和配置 revision，用于内容可见性、模块启用、推荐训练和管理筛选。
- 训练阶段等级：通过 `TrainingStage` 表达 not_started、in_progress、processing、passed、failed、needs_remediation、disabled、archived、error_terminal、error_transient 等机器可读状态。

### 4. Realtime 从 placeholder supersede 为 runtime binding

旧“实时对练只能 disabled placeholder”的语义被 supersede。实时对练可以纳入新人训练闭环，但 learner 入口开放前必须满足：

- active revision 中存在 `runtime_binding`。
- runtime descriptor / runtime config / provider readiness 可用。
- `sales_trainer.realtime_provider.registry` 当前 active 配置允许该 `runtime_descriptor_id`，且 descriptor 未停用、readiness 仍通过；path revision 中的旧 readiness snapshot 不能单独放行 learner start。
- path、module、learner level、对象级权限通过。
- terminal / transient / voluntary failure 分类明确。
- runtime outcome 可投影为 `ModuleOutcome`。
- 发布影响预览、审计和 active revision rollback 可用。

缺任一条件时必须 fail-closed，返回 typed diagnostic 或 disabled 状态。`sales_trainer` 不直接创建、修改、修复 realtime session，也不从 WebSocket 连接状态推断完成。

Realtime provider secret 不属于新人训练域数据。`runtime_binding`、provider registry、TrainingJourney、operation log 和历史 snapshot 只能保存 provider/model/readiness/config pointer/masked 状态；真实 `STEPFUN_API_KEY`、Authorization、Cookie、JWT、上游 raw payload 和完整 prompt 不得入库、不入日志、不进入 API 响应。StepAudio 2.5 模型迁移只允许修改默认 runtime profile/model pointer；控制台未授权或 key 无效时按 provider readiness/auth failure fail-closed，不得 fallback 到 legacy/local provider 伪成功。

### 5. AI Coach 是首版闭环必过能力

AI Coach 不再被视为可关闭的补练小功能。若 active revision 声明 `require_ai_coach=true`，TrainingJourney 必须包含 AI Coach `ModuleProgress`、达标 outcome、补救/人工复盘状态和历史证据。

AI Coach Prompt、评分 Prompt、模型、temperature、timeout、retry、max tokens、成本阈值和降级策略必须由配置或 prompt 服务治理。坏配置、缺 Prompt、模型不可用或输出不合约必须返回 typed terminal/transient 状态，不得静默默认通过。

### 6. Snapshot-first 历史展示

历史 attempt、submission、score result、AI Coach session 和 realtime outcome 必须优先读取创建时冻结的 snapshot 或 revision refs。无法可靠回填的旧记录只能标记 `legacy_snapshot_only=true` 或 `regrade_unavailable=true`，不得从 latest active revision 重建历史解释。

### 7. Readiness 复核采用独立权限和专用 append-only 真源

`review_readiness` 与 `view_records` 分离。平台管理员拥有全局复核权；现有 `SALES_TRAINER_MANAGER_ROLES` allowlist 中的培训负责人仅能复核本人部门 learner；ops 保留全局记录和 Dossier 读取能力，但 `review_readiness=false`。后端 route 与决策服务都必须校验能力和对象范围，前端隐藏表单不能替代授权。

新建 `sales_trainer_readiness_review_actions` 作为 `approve`、`require_retraining`、`mark_manual_follow_up` 三种决定的 canonical append-only 真源。MVP 不实现撤销、覆盖或复核人委派。`SalesTrainerOperationLog` 降为同一数据库事务内的审计 Adapter；审计失败必须使业务 action 一并回滚。Dossier 在有限兼容期双读专表和历史日志，并按 `audit_log_id` 去重；专表 action 的审计镜像不得再次作为 legacy 状态或并发版本。

写请求必须同时携带长度 16..100 的 `idempotency_key` 和 key 必须存在、值可为 `null` 的 `expected_latest_review_action_id`。同一 actor/key/规范化内容只产生一条 action 和一条审计记录；同 key 异内容以 409 `[READINESS_IDEMPOTENCY_KEY_REUSED]` 拒绝。learner 行锁内比较专表与未镜像 legacy 日志的合并最新版本；陈旧版本以 409 `[READINESS_REVIEW_VERSION_CONFLICT]` 和 `details.latest_review_action_id` 拒绝。客户端网络重试复用 token，编辑后换 token，版本冲突刷新档案并要求重新确认，禁止自动覆盖或自动重放。

## 备选方案

### 方案 A：继续保持 realtime placeholder，先做异步模块闭环

优点是改动范围小。缺点是违背已确认产品目标，且后续 realtime 接入仍会面对权限、配置健康、回滚和运行时边界缺契约的问题。

### 方案 B：在 `sales_trainer` 内直接创建 realtime session

优点是看起来能快速把实时对练放进新人训练页面。缺点是违反模块边界，重复 `sales_bot` / `training_runtime` 已有运行时能力，也会让 WebSocket 状态、权限和历史记录变成新人训练域内的隐式旁路。

### 方案 C：立即新增 TrainingJourney 表和完整状态机

优点是长期一致性更强。缺点是需要 migration、历史回填和事务边界设计，风险高于 Phase 1 契约冻结目标。

### 方案 D：先冻结 API/ADR，TrainingJourney 以 read model projection 起步

采用。它先统一契约、状态、权限和运行时边界，允许后续实现分阶段推进，同时不把表结构和 runtime 接入方式过早写死。

## 取舍

本决策接受短期存在旧记录和旧 placeholder 配置，但要求它们只能以兼容、迁移或诊断形态出现，不能继续作为 learner 正式成功路径。

TrainingJourney 先作为读模型，牺牲一部分写入侧一致性，换取低风险统一状态语义。后续若需要更强审计、补救任务编排或跨模块事务，可以在不改变 API 语义的前提下升级为持久化 aggregate。

Realtime 采用 runtime binding，而不是新人训练域内建运行时。这样会增加发布前校验和 outcome projection 工作，但保留了 `sales_trainer`、`sales_bot`、`training_runtime` 的边界。

## 影响

### API 影响

- `docs/api-contract/sales-trainer.md` 新增 `TrainingJourney`、`ModuleProgress`、`ModuleOutcome`、`LearnerLevel`、`TrainingStage`、`RoleCapability`。
- `SalesTrainerPath` 被降级为 legacy 兼容读面，新看板和管理分析应优先使用 TrainingJourney。
- realtime 模块新增 `runtime_binding`、provider registry/readiness、failure policy 和 rollback policy 契约。
- StepAudio 2.5 realtime 默认模型迁移必须具备 apply/rollback 语义：apply 只更新默认 StepFun realtime profile，rollback 只恢复默认模型；两者均不处理 secret、不覆盖管理员显式模型选择。
- Readiness review action 写请求新增必填幂等键和 expected-latest 版本；这是第一方 Web、后端与 migration 协调发布的内部强契约，不提供缺字段的静默兼容写入口。
- 新增 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`、`[NEWCOMER_REALTIME_BINDING_INVALID]`、`[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]`、`[NEWCOMER_REALTIME_PROVIDER_DESCRIPTOR_MISSING]`、`[NEWCOMER_REALTIME_PROVIDER_DISABLED]`、`[NEWCOMER_REALTIME_PROVIDER_NOT_READY]`、`[NEWCOMER_REALTIME_PERMISSION_DENIED]`、`[NEWCOMER_REALTIME_OUTCOME_MISSING]`。
- Readiness 新增 `[READINESS_REVIEW_ROLE_REQUIRED]`、`[READINESS_IDEMPOTENCY_KEY_REUSED]`、`[READINESS_REVIEW_VERSION_CONFLICT]` 等稳定错误；版本冲突通过 `details.latest_review_action_id` 暴露可重试基线，不暴露越权对象。

### 权限与状态影响

- 角色能力必须由后端 capability projection 返回，前端 fail-closed。
- `review_readiness` 独立投影：平台管理员全局、培训负责人本部门、ops 只读；对象级权限以后端最终校验为准。
- 学员等级来源仍可在后续人工决策中确定，但 API 必须暴露 `source` 和配置 revision。
- 训练阶段由后端统一返回，前端不得把 `passed=null`、网络错误或 403/500 推断为失败、无绑定或可用。

### 运行时影响

- 本 ADR 不接入 realtime runtime，不修改业务代码。
- 后续 realtime 实现必须通过 runtime binding 和 outcome projection 纳入闭环。
- terminal failure 禁止盲目重连；transient failure 才允许有限重试；voluntary failure 不计入故障。

### 数据与迁移影响

- 原 Phase 1 决策不要求立即持久化 TrainingJourney；2026-07-10 Readiness 增补以 additive migration `20260710_1200_092` 新增专用 action 表，不改变 TrainingJourney 是否持久化的决策。
- 新 Readiness 决定以专表为 canonical，OperationLog 只保留审计；历史 OperationLog 不回填、不删除，并通过 Dossier 双读继续可见。
- 旧历史数据通过 `legacy_snapshot_only`、`regrade_unavailable` 和 snapshot refs 解释。
- `unit_backfill` 不再是 learner 正式路径，只能用于管理端迁移/诊断。

### 测试影响

后续实现至少需要覆盖：

- 无 active revision 时 learner fail-closed。
- TrainingJourney 聚合 audio、quiz、business etiquette、AI Coach、realtime outcome。
- 三类等级筛选和权限范围。
- realtime binding 发布校验、provider not ready、terminal/transient/voluntary failure。
- AI Coach 必过、坏配置 fail-closed、Prompt 缺失和模型失败兜底。
- snapshot-first 历史展示，不从 latest active revision 伪造历史。
- Readiness 权限矩阵（含 ops 只读和培训负责人部门范围）、三决定 allowlist、幂等 replay/异体冲突、expected-latest 版本冲突、legacy 双读去重、前端明确确认和 token 重试语义。
- additive migration upgrade/downgrade 必须在隔离数据库验证：downgrade 仅删除专表，历史 OperationLog 保留；生产已有新 action 时不执行 schema downgrade。

## 回滚

若本决策阻塞后续实现，可按以下顺序回滚：

1. 在 ADR 中追加 superseded 记录，说明回退原因和影响范围。
2. API 契约可临时恢复 realtime disabled placeholder，但必须标记为 symptom fix，不能作为完整闭环完成标准。
3. TrainingJourney 可回退为 read model 只读关闭入口，保留原始 audio/quiz/AI Coach/realtime 记录不变。
4. Active revision 唯一真源若需迁移窗口，只允许在管理端暴露 legacy migration snapshot；不得恢复 learner `unit_backfill` 伪成功作为长期策略。
5. 已写入历史 snapshot、operation log、regrade run 和 runtime outcome projection 不得被回滚脚本覆盖。
6. Readiness 发布顺序为 migration → 支持专表/双读和新必填字段的后端 → 新 Web；混合版本窗口内旧 Web 不得继续提交复核写请求。
7. 应用回滚保留 additive `sales_trainer_readiness_review_actions` 及其业务数据，Dossier 继续双读。schema downgrade 只允许在确认专表无业务数据、或隔离环境完成备份后执行；其语义只删除专表，绝不删除或改写历史 OperationLog。
