# 首发基线重建技术设计

## 1. 目标与非目标

本任务把项目从“历史迁移、运行时补表、共享密码和部门字符串授权并存”的开发态，收敛为可重复发布的首发基线。完成后，空 PostgreSQL 只能由 Alembic 建库；reset 是受保护的运维 CLI；Team 是用户组织与数据范围的唯一权威；环境连接、密钥、模型名和 API key 原样保留。

本任务不迁移旧业务数据，不提供网页清库入口，不清空共享 Redis 服务或整个 COS bucket，也不轮换任何现有秘密。

## 2. 已确认的首发契约

### 2.1 Schema authority

- 活动 Alembic 路径只有一个新的 root baseline，旧 `001...095` 移至非活动归档目录。
- 应用启动只验证数据库位于 Alembic head，不执行 `create_all()`、`ALTER TABLE` 或 `_ensure_*` schema repair。
- reset 编排器只调用 Alembic upgrade；seed、管理员 bootstrap 和配置恢复均不得创建或修改表结构。
- ORM model registration 使用一个显式根组合入口，Alembic、启动验证和测试共用同一入口。

### 2.2 用户、Team 与权限

- `users.department` 从 schema、ORM、DTO、API、页面和生产查询删除。
- `TeamMembership` 表达学员当前主团队，`TeamLeaderAssignment` 表达训练经理负责范围。
- 平台管理员：全局范围。
- 训练经理：仅显式负责团队及其有效成员。
- 学员：仅自身对象。
- 内容管理员/运维/审计角色：后台入口权限不等于学员数据权限；没有单独授权时 fail closed。
- 内容对象上的“适用部门”仅是分类标签，不参与任何用户权限计算。

现有 `/admin/teams` 已具备在当前流程快速建账号、建团队并关联的工作区雏形；实现应复用并收紧该链路，不另建平行组织后台。

### 2.3 首发数据

- 恰好一个显式输入的受管管理员，初始秘密一次性提供，首次登录必须改密。
- 恢复白名单配置：模型、RAG、全局语音、Prompt、已发布业务规则、已发布评分规则。
- 写入应用启动真正必需的系统字典/默认值，使用稳定逻辑键幂等 upsert。
- 不创建演示学员、经理、团队、课程、材料、训练、评分、作业或历史记录。

## 3. 组件与职责

```text
CLI
 └─ ResetApplicationService
     ├─ TargetGuard / RunLock
     ├─ InventoryService
     ├─ ConfigSnapshotRegistry
     ├─ CleanerRegistry
     │   ├─ PostgreSQLCleaner
     │   ├─ RedisCleaner
     │   ├─ ChromaCleaner
     │   ├─ LocalPathCleaner
     │   └─ CosPrefixCleaner
     ├─ AlembicSchemaBootstrap
     ├─ SystemSeedService
     ├─ ManagedAdminBootstrap
     ├─ ConfigRestoreRegistry
     └─ IndependentVerifier
```

核心协议：

```python
class ScopedCleaner(Protocol):
    def inspect(self, scope: Scope) -> Inspection: ...
    def dry_run(self, scope: Scope) -> Plan: ...
    def apply(self, scope: Scope, confirmation: Confirmation) -> ApplyResult: ...
    def verify(self, scope: Scope) -> Verification: ...

class SnapshotHandler(Protocol):
    type_name: str
    schema_version: int
    def export(self, source: Connection) -> SnapshotSection: ...
    def restore(self, target: Connection, actor: ManagedAdmin) -> RestoreResult: ...
    def fingerprint(self, source: Connection) -> str: ...
```

编排器只执行阶段状态机，不包含具体删除 SQL、Redis 命令、文件遍历或 COS SDK 逻辑。新增数据面或配置类型通过 registry 注册，不修改已有 handler 内部逻辑。

## 4. 执行顺序与失败边界

```mermaid
flowchart LR
  I[inspect] --> D[dry-run]
  D --> S[配置快照]
  S --> C[按数据面清理]
  C --> A[Alembic upgrade head]
  A --> Y[系统 seed]
  Y --> B[受管管理员 bootstrap]
  B --> R[配置恢复与审计人重映射]
  R --> V[独立 verify]
```

1. `inspect` 解析目标，输出脱敏指纹、数据面范围和预计数量。
2. `dry-run` 固化版本化 manifest，生成一次性确认令牌；manifest 不含连接密码、API key 或密文正文。
3. `apply` 必须同时匹配 manifest checksum、目标指纹、环境白名单和确认令牌，并取得运行锁。
4. 配置快照完整写入并通过 checksum/encryption-key 指纹验证后，才允许开始清理。
5. PostgreSQL 清理后只通过 Alembic 建立 schema。
6. 先 seed 系统权威，再创建管理员，最后恢复配置；配置里的 `created_by/updated_by` 统一映射到新管理员或按合同置空，不引用旧 UUID。
7. `verify` 独立运行。任一步失败都记录最后成功阶段，整体状态为失败或部分失败，不伪装成功。

清理后的旧数据不可回滚；本任务的恢复策略是“配置快照 + 从空库重跑”。因此配置快照失败属于 apply 硬阻塞。

## 5. 数据面范围清单

| 数据面 | 允许范围 | 硬性拒绝条件 |
|---|---|---|
| PostgreSQL | 解析后的单一目标 database/schema | 生产标识、认证失败、目标指纹变化、未知 host/db |
| Redis | 明确 DB；项目独占 DB 可清 DB， shared DB 仅非空前缀白名单 | `FLUSHALL`；shared DB 的 `FLUSHDB`；空前缀；URL/DB 与 manifest 不符 |
| Chroma | `CHROMADB_PERSIST_DIR` 与 `CHROMA_PERSIST_DIRECTORY` 解析后的去重路径/明确 collection | 根目录、家目录、仓库根/父目录、路径逃逸 |
| 本地文件 | 文档、音频、PPT、材料、作业的显式 allowlist | 推导路径、空路径、符号链接逃逸、超出 allowlist |
| COS | `audio/`、`sales-trainer/audio/`、`sales-trainer/materials/`、`newcomer-assignments/` 等显式项目 prefix | 空 prefix、bucket 根、prefix 不以 `/` 结尾、bucket/endpoint 指纹变化 |

本地路径盘点需覆盖当前代码中的不一致别名：`./data/presentations`、`./data/ppts`、`/data/uploads`、`/data/ppt_versions`；在统一存储配置前均需显式列入或明确排除，不能靠目录名猜测。

Redis 当前已确认：WebSocket session 使用 `SESSION_STATE_KEY_PREFIX`（默认 `ws:session_state:`）；通用 `CacheManager` 接受任意业务前缀且存在 `flushdb()` 能力。reset 不复用 `CacheManager.clear()`，而使用专用受限 cleaner。

## 6. 配置快照 v1

顶层字段：

- `format = sales-training-config-snapshot`
- `version = 1`
- `created_at`、`source_fingerprint`
- `encryption_key_fingerprint`（不可逆，不含 key）
- `sections[]`：`type`、`schema_version`、`logical_key`、`payload_ciphertext_or_value`、`checksum`
- `manifest_checksum`

恢复拓扑：基础模型配置 → RAG/语音 runtime profile → Prompt → 已发布业务规则/评分规则 → 可证明逻辑依赖存在的绑定。Agent、Scenario 或历史业务对象不存在时，不恢复其 ID 绑定并给出显式 skipped 报告。

任何输出只显示数量、逻辑键、configured 状态和不可逆指纹。原 ciphertext 可以进入权限为 `0600` 的快照，但不能进入日志、普通报告或测试快照。

## 7. CLI 契约

```text
python -m launch_reset.cli inspect --manifest <path>
python -m launch_reset.cli dry-run --manifest <path>
python -m launch_reset.cli apply --manifest <path> --target-fingerprint <fp> --confirm-token <token>
python -m launch_reset.cli verify --manifest <path>
```

- 默认命令为只读；没有显式 `apply` 永远不删除。
- `apply` 不接受 `--yes` 这类静态万能确认。
- CLI 返回非零退出码表示失败/部分失败，并把脱敏 JSON 报告写入指定路径。
- 不新增 HTTP route。

## 8. 用户可见页面契约

受影响页面仅限账号、团队、学员范围和登录：

- 管理员用户页：只编辑账号、角色、状态和 Team；无 department 输入、筛选或 fallback 文案。
- 团队页：主任务是在当前工作区创建/选择账号、创建 Team、建立成员和负责人关系；服务端校验去重、权限和有效期。
- 学员/经理页：按集中 Team policy 返回数据；无关系显示清晰空态/无权限态，不建议用户跳到另一个模块补资料。
- 登录页：无受管密码时统一返回“账号或凭证无效”；一次性凭证成功后进入强制改密流程。

必须覆盖 loading、empty、error、permission denied、partial/stale、submitting 与 retry，且普通页面不展示数据库 ID、migration、trace 原文或 reset 工程术语。

## 9. 验证矩阵

- 空 PostgreSQL：`upgrade head`、单 head、schema parity、`alembic check`、应用启动零 DDL。
- 演进性：隔离目录临时 revision 从 baseline 升级，不污染活动 migrations。
- Auth：受管密码、过期一次性密码、强制改密、无 hash 失败、共享 env 值不被读取且不被改写。
- Team：平台管理员全局；训练经理正向/越权；学员自身/他人；内容/运维无隐式数据范围。
- Reset guard：错误目标、认证失败、目标漂移、空 prefix、路径逃逸、snapshot 失败、重复 apply、部分失败。
- 配置：前后数量/逻辑键/指纹一致，Provider smoke 可用但日志无秘密。
- 最小数据：第二次 seed 无重复；所有业务历史表为空；仅一个指定管理员。

## 10. 分批实现

1. PR1：统一 model registry、移除运行时 DDL/共享密码/用户 department、集中 Team scope、新 baseline 与 PostgreSQL 验证。
2. PR2：TargetGuard、manifest、状态机和五个 scoped cleaner；只在隔离资源上执行 destructive 测试。
3. PR3：配置 snapshot/restore、系统 seed、管理员 bootstrap、端到端 verify 与运维手册。

真实开发数据面的 `apply` 是独立发布动作：只有连接认证、完整 dry-run 清单和用户确认的目标指纹均通过后才能执行。
