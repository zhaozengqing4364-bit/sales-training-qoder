# ADR：首发 Alembic 基线与受保护的数据面重置

- 日期：2026-07-15
- 状态：Accepted
- 风险等级：P0（破坏性数据操作）

## 背景

项目尚未发布，原有开发数据可以全部清除。旧 Alembic 历史从一个已存在的数据库结构起步，不能可靠地从空 PostgreSQL 升级；应用启动、旧修补脚本和 `create_all()` 又曾共同拥有 schema 修改能力。继续兼容旧开发库会长期保留多个结构权威，并增加每次升级的验证成本。

项目数据也不只存在于 PostgreSQL：Redis、Chroma、本地文档/音频/PPT/材料/作业和 COS 对象都可能保留派生状态。只清关系库会留下孤立数据；清空整个共享 Redis 或 COS bucket 又会破坏其他项目。

## 决策

### 1. Schema 只有一个权威

- 活动 Alembic 历史从 `20260715_0000_001` 开始，旧 revision 只归档留证，不再参与 `history` 或 `upgrade`。归档共有 98 个物理 revision 文件；编号主序列到 `095`，文件数更多是因为历史分支、merge 和同号变体，并非漏归档。
- 所有旧开发数据库统一重建；不提供旧 `001...095` 到首发 baseline 的原地升级承诺。
- Alembic 是唯一 schema writer。应用启动只读校验数据库 revision 必须精确等于唯一 head。
- 旧 `reset_db.py`、legacy schema repair 和运行时 `create_all()` 入口退役，seed 与管理员 bootstrap 不得创建或修改 schema。
- baseline 后的变更必须新增线性 revision，并同时验证“空库到 head”和“上一首发版本到新 head”。

### 2. Reset 采用阶段化应用服务

```text
CLI
  -> TargetGuard / manifest / confirmation token / advisory lock
  -> ConfigSnapshot
  -> Redis / Chroma / Local / COS scoped cleaners
  -> PostgreSQL schema cleaner
  -> Alembic upgrade head
  -> idempotent system seed
  -> managed temporary admin
  -> logical-key config restore
  -> independent verifier
```

职责约束：

- CLI 只解析参数和输出脱敏结果；没有 HTTP reset 入口。
- application service 只编排顺序、阶段状态和恢复边界，不实现具体删除逻辑。
- 每个 cleaner 只负责一个数据面，并提供 `inspect/apply/verify`；新增数据面通过注册新 cleaner 扩展。
- snapshot handler 以类型注册表扩展，使用稳定逻辑键而不是复用旧主键。
- verifier 不复用删除逻辑，也不得修复数据；不满足不变量时直接失败。

### 3. 数据清理必须限定项目范围

- PostgreSQL 只允许清理已确认数据库的 `public` schema，不支持 drop database。
- Redis 只有在明确声明项目独占 DB 且 DB 编号进入 allowlist 时才允许 `FLUSHDB`；共享 DB 只能扫描并删除无通配符的非空前缀，禁止 `FLUSHALL`。
- Chroma 与本地文件只清空 manifest 中的明确目录，保留目录根；根目录、用户 home、仓库及其祖先、符号链接路径一律拒绝。
- COS 必须显式设置项目 object prefixes；配置了 bucket/region 却没有 `LAUNCH_RESET_COS_PREFIXES` 时直接失败。禁止默认前缀和 bucket-wide 删除。
- manifest 记录范围描述、数量、校验和、阶段状态和错误码，不记录数据库、Redis、COS 或 Provider 明文密钥。

### 4. 保留配置，不保留业务历史

环境文件、部署 Secret、连接地址、Provider endpoint、模型名、API key 和 encryption key 不由 reset 修改或删除。

数据库配置只通过白名单快照保留：

- `model_configs`
- `rag_profiles`
- 全局 `voice_runtime_profiles`
- Prompt templates
- 已发布业务规则
- 已发布评分规则集

快照使用版本、逐项 checksum、整体 fingerprint、逻辑键和 encryption-key fingerprint。API key 保持原 ciphertext；快照文件以原子写入和 `0600` 权限保存。用户、Team、训练内容、任务、提交、评分、会话、审计和演示数据不得进入快照。

### 5. 最小首发数据

重建后只允许存在：

- 一个显式指定的受管管理员；
- 管理员角色权限等启动必需的幂等系统字典；
- 从白名单快照恢复的运行时配置。

管理员初始密码只从调用者指定的环境变量读取，至少 12 个字符，只存哈希，状态为 `temporary`，并强制首次登录修改。首发 baseline 不创建演示用户、Team、课程、任务、练习、材料、作业或历史结果。

### 6. Team 是唯一组织与授权权威

`User.department` 不进入首发 schema、API 或 UI。人员归属和对象范围只由 `Team`、`TeamMembership`、`TeamLeaderAssignment` 及集中式 Team policy 决定；缺少显式关系时 fail closed。题库或训练内容上的“适用部门”仅是内容分类，不能参与人员授权。

## 失败与恢复语义

- `inspect` 和 `dry-run` 只读；`apply` 必须同时满足非生产环境白名单、数据库 allowlist、显式启用开关、目标指纹和确认令牌。
- destructive apply 先完成配置快照校验，再清理任何数据面；快照失败或 encryption-key fingerprint 不匹配时不继续。
- PostgreSQL advisory lock 防止同一目标并发 reset。manifest 在每个阶段前后原子落盘，重试跳过已完成阶段，不把部分成功写成整体成功。
- reset 本身没有数据级 rollback。操作前需要外部 PostgreSQL/对象存储备份时，由环境负责人完成；失败后按同一 manifest 恢复执行，或从经验证备份恢复后重新开始。
- 已执行首发 baseline 的数据库不能 downgrade 回归档历史。代码回滚应采用 forward fix 或恢复整套 pre-reset 备份，而不是修改 `alembic_version` 伪造兼容。

## 后果

收益是：空库可重复建立、schema authority 单一、配置与业务历史边界清楚、共享基础设施不会被整服务清空，并为新数据面和配置类型保留明确扩展点。

代价是：所有旧开发库必须重建；reset 前必须认真维护 scope 环境变量；配置快照是敏感运维产物，需要单独保管；任何未来需要保留的业务数据都必须另行设计正式迁移，不能扩张本 reset 白名单来绕过。

## 验证要求

- 活动 Alembic 只有一个 root/head，空 PostgreSQL `upgrade -> downgrade -> upgrade` 成功且与 ORM metadata 一致。
- 缺少 apply 开关、数据库 allowlist、目标指纹、确认令牌、Redis DB allowlist或 COS 明确前缀时均失败。
- 共享 Redis 外部 key、COS 前缀外对象、cleanup roots 外文件保持不变。
- 重建后恰有一个 temporary 管理员，业务表为空，配置 fingerprint 与快照一致。
- 应用在未迁移或 revision 不匹配时启动失败；匹配 head 时启动不执行 DDL。

执行步骤见 [`docs/launch-reset-runbook.md`](../launch-reset-runbook.md)。
