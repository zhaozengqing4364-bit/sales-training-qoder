# brainstorm: 从零初始化数据库并建立首发基线

## Goal

在项目尚未发布、现有历史数据允许全部清除的前提下，建立一套安全、可重复、可验证的数据库全量重建与首发初始化方案，消除兼容旧数据所带来的迁移风险，尽快得到可用于内部试点的干净运行基线。

## What I already know

* 项目尚未正式发布。
* 用户明确允许清除当前全部历史数据，并从零初始化数据库。
* 当前工作区包含账号凭证、显式团队、批量开户和新人训练路径等尚未发布的结构变化。
* 现有部门到团队迁移存在中文编码碰撞风险；若从零建库并直接创建显式团队，可以不执行该历史数据迁移。
* 清空关系数据库不必然清除对象存储、向量库、Redis、生成文件或外部 Provider 中的派生状态，必须先核对完整数据边界。
* 任务调研时的旧 Alembic revision 图只有一个 head：`20260714_1600_095`；该事实是建立新 baseline 的输入证据，不是当前活动 head。
* 任务调研时的旧第一条 migration `001` 假设 `users` 和 `practice_sessions` 已存在；隔离空库实测 `alembic upgrade head` 立即因缺少 `practice_sessions` 失败。
* 现有 `backend/reset_db.py` 既没有安全护栏和 Alembic stamp，隔离实测也因 metadata 没有完整注册 `practice_templates` 而无法 `create_all()`。
* PostgreSQL 之外还存在 Redis、Chroma、本地文档/音频/PPT/材料/作业目录，以及可选 COS 对象；只清数据库会留下孤立数据。
* 现有 `bootstrap_auth_admin.py` 不创建受管密码哈希，新空库不能继续依赖它走共享密码兼容路径。
* 用户已选择清理完整项目数据面：PostgreSQL、指定 Redis DB、Chroma、本地文档/音频/PPT/材料/作业，以及 COS 中明确的项目路径前缀；禁止清空整个共享服务。
* 用户明确要求保留已经配置的链接地址、密钥、模型名和 API key，不将凭证轮换或删除纳入本次初始化。
* 当前应用启动仍调用 `Base.metadata.create_all()` 并执行 persona、knowledge document、report evaluation 等兼容补丁；这与 Alembic 单一 schema authority 冲突。
* 当前登录在用户缺少 `hashed_password` 时仍回退到 `AUTH_USER_PASSWORDS_JSON`/`AUTH_SHARED_PASSWORD`；新首发管理员已具备受管密码，因此该兼容登录不应继续成为首发认证路径。
* `User.department` 仍暴露于管理员用户 API、个人资料页、分析和新人训练权限代码；虽然已有显式 Team policy，但部分训练查询仍按部门字符串授权，存在双重权限权威。

## Confirmed constraints

* 目标环境是开发或内部试点环境，不是已经承载真实用户的生产环境。
* 新 baseline 应表达经过审查的“首发理想 schema”，而不是机械复制当前 ORM metadata 中的历史兼容结构。
* 当前 development 目标已经通过显式 `DATABASE_URL`、数据库 allowlist、单一 Redis DB/prefix scope、Chroma/local allowlist 和三个 COS 项目前缀完成指纹确认；真实数据面已按 dry-run 计划执行 `apply` 并独立验证。
* 当前工作区包含大量其他进行中的改动；实现必须逐文件保留既有改动，不通过 reset/checkout 回退用户工作。

## Requirements (evolving)

* 提供显式、可审计的 destructive reset 命令，默认拒绝误操作。
* 从空 PostgreSQL 数据库可重复升级到新的首发 schema head。
* 不执行依赖旧 department 字段的历史团队迁移逻辑。
* 初始化过程不得生成共享生产密码或把原始凭证写入日志。
* 初始化结果必须能通过 schema、约束、管理员登录和核心业务链路验证。
* reset、schema upgrade、bootstrap、seed 和 verify 必须是独立阶段，失败时能明确定位，不能由应用启动隐式完成。
* 清理范围覆盖完整项目数据面，但 Redis 和 COS 只能按已确认的数据库编号、key namespace 和 object prefix 清理，禁止 `FLUSHALL` 或清空整个 bucket。
* `.env`、部署 Secret、Provider endpoint、模型名和 API key 属于保留范围；reset 工具不得改写、打印或复制原始秘密到报告。
* 若运行时配置存在于 PostgreSQL，必须先生成加密或严格权限保护的配置快照，并在新 baseline 后恢复、校验；业务历史数据不得混入该快照。
* 配置恢复采用白名单：保留 `model_configs`、`rag_profiles`、全局 `voice_runtime_profiles`、Prompt、已发布业务规则和评分规则；带 Agent/Scenario 等外键的绑定按逻辑键重建，不盲目恢复旧 ID。
* 数据库内 API key 保持原 ciphertext，`MODEL_CONFIG_ENCRYPTION_KEY` 原样保留；任何报告只允许输出数量、`configured` 状态和不可逆指纹。
* 采用新的首发 Alembic baseline：旧 `001...095` revision 只归档留证，不再处于活动 migration 路径；所有现有开发数据库统一从空库重建。
* Alembic 是唯一 schema authority；应用启动、reset 编排器和 seed 脚本不得通过 `create_all()` 或临时 DDL 隐式改变 schema。
* baseline 之后的每次 schema 变更都通过独立、线性、可审查的增量 revision 演进，保持单一 head，并在空库与“上一已发布版本”两条路径上验证升级。
* reset 系统按职责拆分为：目标识别与预检、配置快照、各数据面清理适配器、schema 升级、配置恢复、系统 seed、管理员 bootstrap、验证与审计；编排层只控制顺序和失败策略。
* PostgreSQL、Redis、Chroma、本地文件和 COS 使用独立的 scoped cleaner；每个适配器必须实现 `inspect/dry-run/apply/verify` 语义，不能共享模糊的“全部清空”实现。
* 配置快照格式必须版本化，使用稳定逻辑键、依赖顺序、校验和与 encryption-key 指纹，避免绑定旧数据库主键，并为以后新增配置类型保留显式注册点。
* 最小首发 seed 只包含：一个受管管理员、恢复后的模型/RAG/语音/Prompt/已发布规则配置，以及应用启动所必需的系统字典或默认值。
* 不写入虚假学员、经理、团队、训练任务、练习记录、评分、作业、材料或演示历史；真实团队和训练内容在首次业务流程中就地创建并自动关联。
* 管理员身份由显式输入提供，初始凭证采用一次性秘密并强制首次修改；seed 文件和日志不得包含固定共享密码。
* 系统 seed 必须按稳定逻辑键幂等执行、可独立版本化，重复运行不能覆盖管理员已修改的业务配置或生成重复数据。
* 首发运行时不得调用 `Base.metadata.create_all()` 或任何 `_ensure_*_compatibility` DDL；这些结构必须完整进入 baseline，并在应用启动前通过 Alembic 建立。
* 认证只接受用户自己的受管密码哈希；现有环境文件中的 `AUTH_SHARED_PASSWORD`/`AUTH_USER_PASSWORDS_JSON` 值不由 reset 删除或打印，但不得继续作为首发登录 fallback。
* 从 `users` 表、User ORM、账号 API/DTO、个人资料、管理员用户界面和训练权限查询中删除用户 `department`；不保留旧字段或按部门字符串授权的兼容路径。
* 用户归属和数据范围只由 `Team`、`TeamMembership`、`TeamLeaderAssignment` 及集中式 Team policy 决定；无显式关系时必须 fail closed，同时在当前业务流程提供就地创建或关联能力。
* 题库或训练内容上的“适用部门”继续作为内容分类标签保留，但不能参与用户身份、对象权限或数据范围计算。
* 首发 reset 只提供运维 CLI，不提供 Web API 或管理员页面入口；CLI 支持独立的 `inspect`、`dry-run`、`apply`、`verify` 阶段。

## Acceptance Criteria (evolving)

* [x] 在临时 PostgreSQL 实例上从空库升级到 migration head 成功。
* [x] 连续执行两次初始化得到等价的 schema 与最小系统数据。
* [x] 初始化后不存在旧部门授权、孤立团队关系或重复团队编码。
* [x] 初始化后至少一个管理员可使用一次性凭证登录并被强制修改密码。
* [x] destructive reset 缺少目标环境确认和显式确认参数时拒绝执行。
* [x] 相关 lint、类型检查、迁移测试和核心集成测试通过。
* [x] `alembic heads` 只有一个 head，`alembic check` 无未生成的 schema 变化。
* [x] 新 baseline 在真实 PostgreSQL 临时库上完成 upgrade、应用启动、核心 smoke 和第二次幂等验证。
* [x] 清理前后配置指纹一致，Provider endpoint、模型选择和 API key 可用但不会出现在日志或普通报告中。
* [x] Redis 清理只影响确认过的 DB/namespace，COS 清理只影响确认过的项目 prefix。
* [x] 配置快照失败、数据库认证失败或 encryption key 指纹不匹配时，destructive apply 必须拒绝执行。
* [x] 活动 Alembic 路径只包含新的首发 baseline 及其后续增量 revision；归档 revision 不会被 `history/upgrade` 执行。
* [x] baseline 定义与完整 ORM metadata 在 PostgreSQL 上完成 schema parity 检查，差异必须显式说明或消除，不能依赖启动时补丁。
* [x] 在隔离测试目录生成一条不进入活动 migration 路径的临时后续 revision，可从首发 head 正常升级并保持单一 head，证明后续可持续演进。
* [x] reset 各阶段可独立测试和重试；任一阶段失败时，报告准确的完成边界，且不会把部分成功标记为整体成功。
* [ ] 新增一种数据面或配置类型时，只需注册新的 cleaner/snapshot handler，不需要修改既有清理器的内部逻辑。
* [x] 初始化完成后恰有一个指定的首发管理员，并能通过一次性凭证登录后强制修改密码。
* [x] 独立 `verify` 同时接受刚初始化的 temporary 管理员和已完成首次改密的 active 管理员；active 状态缺少 `password_changed_at` 时仍 fail closed。
* [x] 初始化后不存在演示用户、虚假团队、训练记录、作业、评分或业务历史；业务表初始为空。
* [x] 对最小系统 seed 连续执行两次，系统字典和默认配置不重复，已恢复的用户配置不被静默覆盖。
* [ ] 管理员首次进入团队或训练主流程时，可以在当前流程就地创建所需对象并自动关联，无需先跳转到独立配置模块。
* [x] 应用在空库未执行 Alembic 时明确启动失败；执行 baseline 后启动过程不发出任何 DDL。
* [x] 缺少用户受管密码哈希时登录失败并返回统一安全错误，不读取共享密码 fallback；已有环境配置内容保持原样且不进入日志。
* [x] 新 baseline 的 `users` 表不存在 `department` 字段，生产源代码不存在 `User.department`、`team_scope_department` 或部门字符串授权 fallback。
* [x] 平台管理员拥有全局范围；训练经理仅能访问显式负责团队；学员仅能访问自身对象；内容管理员和运维角色不因“能进入后台”而自动获得学员数据范围。各角色均有正向与越权测试，缺少 Team 关系时后端拒绝访问。
* [ ] 题库/训练内容的“适用部门”标签仍可创建、筛选和展示，但修改该标签不会改变任何用户权限。
* [x] reset 功能没有可被普通应用流量调用的 HTTP 入口；CLI 在没有显式 `apply`、目标指纹和确认令牌时只能执行只读盘点。

未勾选项的当前边界：cleaner 已按数据面拆分，但尚未抽成外部可注入注册表；首次 Team/训练流程的全部 in-flow UI 与内容“适用部门”非授权语义未在本 P0 数据任务中做真实浏览器回归。真实 development reset 已验证 PostgreSQL、Redis、Chroma、本地目录和 COS 项目前缀，恢复后的两个 LLM 配置也已完成不回显密钥的真实 Provider smoke。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky
* 数据边界、清理顺序、初始化顺序和失败恢复方式有可执行说明

## Out of Scope (explicit)

* 保留或迁移当前历史业务数据。
* 多租户数据迁移。
* 为未确认的生产环境自动执行清库。
* 在需求收敛前实际删除数据库或外部数据。
* 轮换、吊销或删除现有 Provider 密钥、数据库连接配置和模型 API key。
* 支持旧 `001...095` 开发数据库原地升级到新 baseline；旧库统一丢弃并重建。
* 内置演示账号、演示团队、演示课程、虚假练习结果或历史行为数据。
* 为用户 `department` 字段、部门字符串授权或旧账号 API 提供向后兼容；项目尚未发布，首发契约直接以 Team 为准。
* 在首发版本提供网页清库按钮或远程 destructive reset API。

## Technical Notes

* 风险背景见 `docs/project-analysis/audit-2026-07-15-current-worktree-deep-review.md`。
* 重点核对 Alembic 配置、migration head、数据库初始化脚本、seed/demo 数据、Redis、Chroma/向量库、对象存储和本地上传目录。
* 本任务属于 P0 破坏性数据操作设计；实现阶段必须有环境白名单、双重确认、目标指纹、dry-run 和重建后验证。
* 复杂度：Complex。它同时改变 schema authority、数据生命周期、凭证 bootstrap、外部状态清理和发布基线。

## Research References

* [`research/alembic-zero-baseline.md`](research/alembic-zero-baseline.md) — 当前历史链不能从空库执行；在未发布前建立新的 Alembic baseline 总风险最低。
* [`research/configuration-preservation-boundary.md`](research/configuration-preservation-boundary.md) — 环境 Secret 原地保留，数据库运行时配置使用白名单快照和原 ciphertext 恢复。

## Decision (ADR-lite)

### 首发 migration 基线

采用新的首发 Alembic baseline。旧 `001...095` revision 移出活动 migration 路径并只读归档，保留代码审计证据，但不再承诺从旧开发库原地升级。所有现有开发数据库统一清理后从空 PostgreSQL 执行新 baseline；此后恢复正常的增量 revision 演进。

baseline 不是对当前表结构的无脑快照：实现前必须完成模型注册、外键/约束/索引/默认值审查，删除已确认不应进入首发版本的历史兼容结构，并以真实 PostgreSQL 验证。架构目标是单一 schema authority、线性升级路径、阶段职责清晰和数据面适配器可扩展。

### 数据清理范围

清理完整项目数据面：PostgreSQL、指定 Redis DB/namespace、Chroma、本地文档/音频/PPT/材料/作业，以及 COS 中明确的项目 object prefix；禁止清空整个 Redis 服务或 COS bucket。

### 配置与秘密

保留链接地址、密钥、模型名和 API key。环境文件与部署 Secret 不修改；数据库配置在 apply 前做白名单快照，恢复后以不可逆指纹和 Provider smoke 验证。

### 最小首发数据

采用“最小可用基线”：创建一个受管管理员，恢复允许保留的模型/RAG/语音/Prompt/已发布规则配置，并写入运行所必需的系统字典。除此之外不制造任何演示业务数据；真实团队、人员和训练内容由管理员在首次业务流程中就地创建。

### 用户组织与授权权威

用户维度完全移除 `department`，Team 体系成为唯一组织归属和授权权威。内容对象可以继续保留“适用部门”作为分类标签，但该标签与用户权限隔离。无 Team 关系时后端 fail closed，前端遵循上下文内完成原则提供就地创建或关联。

### 兼容登录与启动补丁

首发版本只接受受管用户密码，不再回退到共享环境密码；已有环境配置值原样保留但不读取。应用启动不再建表或修复 schema，只验证当前数据库处于 Alembic head，否则显式失败。

## Feasible Approaches

### Approach A：新的首发 Alembic baseline（已选择）

归档旧 revision 作为历史证据，以完整当前 schema 生成一个人工复核过的空库 baseline，后续 migration 从该 revision 延续。优点是 schema authority 单一且可测试；代价是现有开发库全部重建，不能原地升级。

### Approach B：补齐全部旧 migration

新增旧基础表 revision，再逐条修复和验证现有 migration 链。能保留历史，但项目尚未发布，兼容收益很低，工时和失败面最大。

### Approach C：`create_all()` 后 `stamp head`

Alembic 官方支持该模式，但当前 metadata 注册已经实测不完整，也会让 ORM metadata 成为隐含的建库权威。除非先建立完整 metadata 和 schema parity 证明，否则不建议作为本项目的首发路径。

## Technical Architecture (evolving)

```text
Reset CLI / Orchestrator
  ├─ TargetGuard        目标环境、指纹、确认令牌、运行锁
  ├─ Inventory          只读盘点各数据面及预计影响
  ├─ ConfigSnapshot     白名单、版本、逻辑键、密文、校验和
  ├─ DataPlaneCleaners  PostgreSQL / Redis / Chroma / Local / COS
  ├─ SchemaBootstrap    只调用 Alembic upgrade head
  ├─ SystemSeed         仅写首发必需、可重复执行的数据
  ├─ AdminBootstrap     受管账号、一次性凭证、强制改密
  ├─ ConfigRestore      按依赖拓扑恢复、重映射审计人并验证引用
  └─ Verifier/Audit     schema、配置、边界、核心 smoke、脱敏报告
```

职责边界：

* 编排器不包含具体存储删除逻辑，只执行阶段状态机并记录审计结果。
* cleaner 只负责一个数据面和一个明确 scope，不负责 schema、seed 或秘密恢复。
* Alembic 只负责 schema；snapshot/restore 只负责允许保留的运行时配置；seed 只负责可声明、幂等的系统初始数据。
* 验证器独立于执行器，必须能在不执行 reset 的情况下复核目标库和外部数据面。
* 阶段产物使用带版本的 manifest 串联；manifest 只含范围、数量、哈希、状态和错误摘要，不含明文秘密。
* MVP 采用本地运维 CLI，避免给破坏性能力增加远程攻击面；执行逻辑仍放在可测试的 application service 中，未来若有受控运维平台，只能复用 service 并重新增加权限、审批和审计边界。
* Redis cleaner 必须解析并固定目标 DB。通用缓存尚无统一 namespace 时，只有“项目独占 DB”模式可以清理该 DB 的全部 key；共享 DB 模式必须提供非空前缀白名单并逐 key 扫描删除，禁止调用 `FLUSHALL`，也禁止在共享 DB 上调用 `FLUSHDB`。
* 本地路径 cleaner 必须使用显式 allowlist、解析真实路径、拒绝根目录/家目录/仓库根目录及其父目录，并拒绝符号链接逃逸。COS cleaner 只接受非空且以 `/` 结尾的项目路径前缀。

### 首发兼容层收敛建议

* 删除应用启动时 `create_all()` 和运行时 schema repair，统一由 Alembic baseline 建立完整结构。
* 停用共享密码和按用户环境密码映射的登录 fallback，只保留受管密码、一次性密码和重置流程；环境配置值不主动删除。
* 用户授权与训练数据范围完全由 `Team`、`TeamMembership`、`TeamLeaderAssignment` 决定；`User.department` 从首发 schema 和用户契约中移除。内容对象上的“适用部门”仅作为非授权分类标签。

## Implementation Plan (small PRs)

### PR1：首发 schema authority 与认证/组织模型

* 完整注册并审查 ORM metadata，移除用户 `department`、部门授权 fallback、共享密码 fallback 和启动时 DDL。
* 将旧 `001...095` revision 移出活动路径，建立人工复核的新 Alembic baseline。
* 增加空 PostgreSQL upgrade、schema parity、单 head、Team 权限和受管密码回归测试。

### PR2：安全 reset 编排与完整数据面适配器

* 实现 TargetGuard、Inventory、版本化 manifest 和阶段状态机。
* 实现 PostgreSQL、指定 Redis DB/namespace、Chroma、本地目录、COS 项目前缀 cleaner 的 `inspect/dry-run/apply/verify`。
* 增加范围逃逸、错误目标、部分失败、重复执行、路径与 prefix 边界测试。

### PR3：配置保全、最小 seed 与发布验证

* 实现配置白名单快照/恢复、逻辑键解析、密文与 encryption-key 指纹验证。
* 实现受管管理员一次性凭证和幂等最小系统 seed。
* 完成 Provider smoke、管理员登录/改密、Team 就地创建、核心训练链路及脱敏审计报告，并编写运行/恢复手册。
