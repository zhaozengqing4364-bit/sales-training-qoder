# 首发数据面重置 Runbook

最后更新：2026-07-15
适用范围：尚未发布的 development / test / internal / staging 环境
风险等级：P0

本 runbook 用于把项目完整数据面重建为首发 baseline，同时保留现有连接配置、密钥、模型名和 API key。它绝不授权清空共享 Redis 服务、整个 COS bucket 或未列入 manifest 的目录。

> 2026-07-15 已在当前 development 目标完成一次带独立备份的真实 `inspect → dry-run → apply → verify`，覆盖 PostgreSQL、共享 Redis 的显式 prefixes、Chroma、本地目录和三个 COS 项目前缀。该成功记录不构成对其他环境的授权；每个新目标仍必须重新确认指纹、scope 和备份策略。

## 1. 执行前置条件

1. 停止 API、worker、scheduler 和前端写入流量，避免 dry-run 后继续产生数据。
2. 确认当前环境不是 production/prod。
3. 如需保留旧业务事实，先停止：本流程会永久删除业务历史。项目当前决策是只保留配置，不保留业务历史。
4. 如需灾难恢复能力，先使用 `pg_dump` 和云厂商工具制作独立备份，并验证备份可读。reset 生成的配置快照不是完整数据库备份。
5. 选择不在任何 cleanup root 内、也不进入 Git 的控制目录；目录权限设为 `0700`。

示例：

```bash
export RESET_CONTROL_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/sales-training-qoder/launch-reset-20260715"
mkdir -p "${RESET_CONTROL_DIR}"
chmod 700 "${RESET_CONTROL_DIR}"
export RESET_MANIFEST="${RESET_CONTROL_DIR}/manifest.json"
export RESET_SNAPSHOT="${RESET_CONTROL_DIR}/config.snapshot.json"
```

manifest 与 snapshot 会以 `0600` 写入。snapshot 包含配置值和原有 ciphertext，应按敏感运维产物管理，不得提交到 Git、工单正文或聊天记录。

### 发布前隔离演练

仓库提供双循环演练器，在随机本机 disposable database 中连续执行两次 `dry-run → apply → verify → standard pack seed/verify`。它不会把现有应用数据库作为 reset 目标；Redis 只使用随机 prefix，文件只落在临时目录，COS 被禁用。目标应用角色需要 `CONNECT`，建库/删库可由单独的最小权限本机管理连接完成：

```bash
cd backend
set -a; source .env; set +a
export FOUNDATION_RESET_REHEARSAL_CONFIRM=1
# 仅当 DATABASE_URL 的角色没有 CREATEDB 时设置；必须仍是同一台本机 PostgreSQL。
export FOUNDATION_RESET_REHEARSAL_ADMIN_DATABASE_URL='<受控本机管理连接>'
PYTHONPATH=src .venv/bin/python scripts/rehearse_foundation_reset.py
unset FOUNDATION_RESET_REHEARSAL_CONFIRM FOUNDATION_RESET_REHEARSAL_ADMIN_DATABASE_URL
```

通过证据写入 `.sisyphus/evidence/foundation-reset-rehearsal.json`，要求 `status=passed`、`database_removed=true`、两个 cycle 均含 reset/verify/seed 结果。缺少显式确认、本机边界不匹配、没有建库权限或清理失败都会 fail closed；失败证据不能替代发布演练通过。

## 2. 明确配置数据面范围

继续使用现有环境中的连接、密钥和模型配置，不得删除、轮换或回显已有 `.env` / Secret 值。可以新增或规范化 reset 专用 allowlist/scope，但至少要核对以下变量已经指向本次唯一目标：

| 数据面 | 关键配置 | 强制边界 |
| --- | --- | --- |
| PostgreSQL | `DATABASE_URL` | 只支持已确认数据库的 `public` schema |
| Redis | `REDIS_URL`、`SESSION_STATE_REDIS_URL` | 共享 DB 必须设置明确前缀；独占 DB 必须进入 DB allowlist |
| Chroma | `CHROMA_PERSIST_DIRECTORY`、`CHROMADB_PERSIST_DIR` | 只允许明确目录 |
| 本地文件 | `DOCUMENT_STORAGE_PATH`、`AUDIO_STORAGE_PATH`、`AUDIO_ARCHIVE_STORAGE_PATH`、`UPLOAD_DIR`、`PPT_*`、`SALES_TRAINER_*_STORAGE_PATH`、`NEWCOMER_ASSIGNMENT_LOCAL_ROOT` | manifest 中逐项确认，不允许宽泛祖先目录或符号链接 |
| COS | `TENCENT_COS_BUCKET`、`TENCENT_COS_REGION`、`LAUNCH_RESET_COS_PREFIXES` | prefixes 必须显式提供、非空并以 `/` 结尾 |

共享 Redis 示例：

```bash
export LAUNCH_RESET_REDIS_EXCLUSIVE_DB=false
export LAUNCH_RESET_REDIS_PREFIXES="sales-training:,sales-training-qoder:"
```

只有确认 Redis DB 完全由本项目独占时，才允许：

```bash
export LAUNCH_RESET_REDIS_EXCLUSIVE_DB=true
export LAUNCH_RESET_ALLOWED_REDIS_DBS="14"
```

共享 COS 示例必须带项目根前缀，不能只写整个 bucket 的通用目录：

```bash
export LAUNCH_RESET_COS_PREFIXES="sales-trainer/audio/,sales-trainer/materials/,newcomer-assignments/"
```

## 3. 只读盘点

在仓库根目录执行：

```bash
cd backend
PYTHONPATH=src .venv/bin/python -m launch_reset.cli inspect \
  --manifest "${RESET_MANIFEST}"
```

逐项人工确认输出：

- environment 正确且不是 production/prod；
- PostgreSQL database、host、port 和 target fingerprint 正确；
- Redis 的 DB 编号、`exclusive_db/shared_prefixes` 模式和 prefixes 正确；
- 每一个 Chroma/local path 都属于当前项目；
- COS bucket、region 和每一个 project prefix 正确；
- 预计表、key、文件、字节和对象数量合理；
- 输出不包含数据库密码、Redis 密码、COS Secret、Provider API key 或 snapshot 内容。

任何一项不确定都停止，修正配置后重新 `inspect`。不要仅凭数据库名相似就继续。

## 4. 生成 dry-run 确认证据

```bash
PYTHONPATH=src .venv/bin/python -m launch_reset.cli dry-run \
  --manifest "${RESET_MANIFEST}"
```

记录本次输出中的：

- `target_fingerprint`
- `confirmation_token`
- `plan_checksum`

fingerprint 和 plan checksum 可以进入变更记录；confirmation token 只保留在当前受控 shell 中，不写入 Git、工单或日志。scope 发生任何变化后必须重新 dry-run，旧 token 不再使用。

```bash
export RESET_TARGET_FINGERPRINT="<dry-run 输出的 target_fingerprint>"
export RESET_CONFIRM_TOKEN="<dry-run 输出的 confirmation_token>"
```

## 5. 最后授权与管理员秘密

`apply` 还要求独立的环境、数据库和功能开关：

```bash
export ENVIRONMENT="development"
export LAUNCH_RESET_APPLY_ENABLED=true
export LAUNCH_RESET_ALLOWED_ENVIRONMENTS="development,test,testing,internal,staging"
export LAUNCH_RESET_ALLOWED_DATABASES="<本次 PostgreSQL database name>"
```

通过无回显输入准备至少 12 个字符的一次性管理员密码：

```bash
read -r -s -p "Launch admin initial password: " LAUNCH_ADMIN_INITIAL_PASSWORD
export LAUNCH_ADMIN_INITIAL_PASSWORD
```

不要把密码写入命令参数。`apply` 只从指定环境变量读取，数据库只保存密码哈希。

## 6. 执行 apply

```bash
PYTHONPATH=src .venv/bin/python -m launch_reset.cli apply \
  --manifest "${RESET_MANIFEST}" \
  --snapshot "${RESET_SNAPSHOT}" \
  --target-fingerprint "${RESET_TARGET_FINGERPRINT}" \
  --confirm-token "${RESET_CONFIRM_TOKEN}" \
  --admin-email "<首发管理员公司邮箱>" \
  --admin-name "<首发管理员姓名>" \
  --admin-password-env LAUNCH_ADMIN_INITIAL_PASSWORD
```

执行顺序固定为：配置快照 → 外部 scoped cleanup → PostgreSQL cleanup → Alembic → system seed → temporary admin → 配置恢复 → 独立验证。

成功条件：命令自然退出 0，manifest 的 `result=completed`，输出显示唯一 schema head、`admin_count=1`、`business_tables_empty=true`，配置 fingerprint 与 snapshot 一致。

## 7. 独立 verify

`apply` 完成后再次独立运行：

```bash
PYTHONPATH=src .venv/bin/python -m launch_reset.cli verify \
  --manifest "${RESET_MANIFEST}" \
  --snapshot "${RESET_SNAPSHOT}" \
  --admin-email "<首发管理员公司邮箱>"
```

随后启动应用。启动必须只读验证 Alembic head，不应出现 `CREATE/ALTER/DROP`。使用一次性密码登录，预期只能进入修改密码流程；修改成功后才获得业务 session。

管理员完成首次改密后可以再次运行同一 `verify`：合法的 `temporary` 状态和带 `password_changed_at` 的 `active` 状态都会通过；`reset_required`、无密码、停用、邮箱不匹配，或缺少改密时间的 active 状态仍会 fail closed。

最后清理 shell 中的临时授权值：

```bash
unset LAUNCH_ADMIN_INITIAL_PASSWORD RESET_CONFIRM_TOKEN
unset LAUNCH_RESET_APPLY_ENABLED LAUNCH_RESET_ALLOWED_DATABASES
```

manifest 和 snapshot 的保留期由环境负责人决定。保留时应放入加密存储；销毁前先确认配置恢复和 Provider smoke 已完成。

## 8. 失败处理

- `inspect/dry-run` 失败：没有删除发生；修正目标或 scope 后重新运行。
- `snapshot` 失败：没有 cleanup 发生；修正数据库读取、磁盘权限或 encryption key 后重试。
- 外部 cleaner 失败：PostgreSQL 尚未清理，但部分已完成的外部 scope 可能已为空。保留原 manifest/snapshot/token，修复原因后用完全相同参数重跑 `apply`。
- PostgreSQL cleanup 之后失败：不要生成新 manifest、不要执行旧 repair/stamp、不要手工写 `alembic_version`。保留原 manifest/snapshot/token，修复依赖后重跑同一 `apply`，已完成阶段会跳过。
- verification 失败：整体结果不会标记 completed。先查看 manifest 中第一个 failed stage 的脱敏错误码，再按同一 manifest 恢复。
- token、snapshot 或 manifest 丢失且 PostgreSQL 已清理：停止操作并从已验证外部备份恢复，或由负责人基于现场状态制定恢复方案；不能通过新的空快照伪装原配置已保留。

## 9. 发布与回滚

- 本 reset 不提供数据 rollback。真实执行前的外部备份是唯一数据恢复点。
- 代码发布回滚不能 downgrade 到归档 revision；应 forward fix，或恢复整套 pre-reset 数据面后再运行对应代码。
- `EXPLICIT_TEAM_SCOPE_ENABLED=false` 只会让 Team 管理范围 fail closed，不会恢复 department 授权。
- 现有 `AUTH_SHARED_PASSWORD` / `AUTH_USER_PASSWORDS_JSON` 环境值可以继续留在 Secret 管理系统中，但登录路径不会读取它们；不要把它们当作恢复管理员的方式。

架构决策见 [`docs/adr/2026-07-15-launch-baseline-and-scoped-data-reset.md`](adr/2026-07-15-launch-baseline-and-scoped-data-reset.md)。通用备份背景见 [`docs/backup-recovery-runbook.md`](backup-recovery-runbook.md)。
