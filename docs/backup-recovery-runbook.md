# Backup / Recovery Baseline Runbook

最后更新：2026-04-14  
适用范围：当前仓库可见的本地开发 / 轻量手工运维场景  
配套现状清单：`docs/setup/backup-recovery-current-state.md`

> 当前基线只描述**今天仓库里真实能执行的路径**：本地脚本、PostgreSQL/Redis 标准工具、文件归档、Alembic、老库修复脚本、管理员账号重建。
>
> 本次文档已按当前仓库实物复核以下 repo-local 引用：`scripts/dev-up.sh`、`scripts/dev-stop.sh`、`scripts/recovery_drill_baseline.py`、`scripts/recovery_drill_runner.py`、`scripts/recovery-drill-baseline.py`、`scripts/recovery-drill-runner.py`、`backend/src/main.py`、`backend/scripts/repair_legacy_schema.py`、`backend/scripts/bootstrap_auth_admin.py`、`backend/src/common/db/session.py`、`backend/src/common/config.py`、`backend/src/common/storage/document.py`、`backend/src/common/knowledge/vector_store.py`、`backend/src/admin/api/admin.py`、`docs/setup/auth-local.md`。
>
> 当前仓库**没有** repo-native 的一键备份平台、OSS 批量导出脚本、统一灾备编排或明确值班名单；这些缺口会在文末的 **Follow-up（非当前基线）** 单列，不混入当前基线步骤。

## 0.1 Repo-local recovery drill baseline inventory

当前 runbook 对应的最小 recovery authority 已收口到一组 repo-local 脚本：

```bash
python3 scripts/recovery-drill-baseline.py status
python3 scripts/recovery-drill-baseline.py check
python3 scripts/recovery-drill-runner.py plan
```

说明：

- `scripts/recovery-drill-baseline.py` / `scripts/recovery-drill-runner.py` 是 CLI entrypoint；
- 真正的 authority module 仍然是 `scripts/recovery_drill_baseline.py` + `scripts/recovery_drill_runner.py`；
- runner 不维护第二套命令表，它直接复用 baseline 里同一组 `checked_command` / `preconditions` / `failure_signals`。

baseline 当前负责三件事：

1. 把最有价值的 recovery drills 固定成同一份 repo-local authority inventory：`db_migration`、`auth_bootstrap`、`redis_session_state`、`websocket_reconnect`、`oss_signing_playback`、`health_check`；
2. 为每个 drill 绑定同一条 checked command、显式 env preconditions（如 `RECOVERY_ADMIN_EMAIL` / `RECOVERY_ADMIN_NAME`）与 authority paths，避免 runbook、测试、后续自动化各写一份；
3. 显式列出仍然必须人工处理的边界：`redis_service_restore`、`oss_bucket_export`、`multi_instance_drain`。

最小可执行 runner 则负责：检查前置条件、按 baseline command 真正执行 migrate/bootstrap/runtime/auth/health proof、把每个 drill 的 stdout/stderr 落到 `./.dev/recovery-drills/<timestamp>/`，并生成 `summary.json` 作为恢复/演练证据。

常用示例：

```bash
RECOVERY_ADMIN_EMAIL=admin@qoder.ai \
RECOVERY_ADMIN_NAME=管理员 \
python3 scripts/recovery-drill-runner.py run --drill db_migration --drill auth_bootstrap --drill health_check
```

如果要把整组最小 drill 都跑完并继续记录后续失败信号：

```bash
RECOVERY_ADMIN_EMAIL=admin@qoder.ai \
RECOVERY_ADMIN_NAME=管理员 \
python3 scripts/recovery-drill-runner.py run --continue-on-failure
```

这里的 `status` / `check` 仍然是 inventory authority，不会执行破坏性 restore；真正会落副作用的内容只限于 baseline 已命名的 migrate / bootstrap / proof commands，manual-only 边界依旧不会被脚本伪装成已自动化能力。

## 1. 当前责任边界与证据位置

| 项目 | 当前真实口径 | 执行时必须留证的位置 |
|---|---|---|
| 执行人 | 当前实际维护该环境的人；仓库内未记录具体姓名/值班表 | 工单 / 变更单 / 值班记录 |
| 审批人 | 当前环境负责人；仓库内未记录具体人名 | 工单审批记录 |
| 仓库内事实依据 | 本 runbook + `docs/setup/backup-recovery-current-state.md` | 仓库文档本身 |
| 备份产物目录（建议） | 当前仓库无固定目录；最小基线建议放到本机或挂载盘的 `./.dev/backup-evidence/<YYYYMMDD-HHMM>/`，不要提交到 Git | 备份目录、截图、命令回显 |
| 恢复验证证据 | `/health` 回包、`alembic upgrade head` 输出、必要时 legacy repair / 管理员重建回显 | 同一工单 / 恢复演练记录 |

### 1.1 数据库 authority line（执行恢复/启动时必须遵守）

- `cd backend && venv/bin/python -m alembic upgrade head` 是唯一的 forward schema migration authority；恢复后的 schema 对齐和 CI 都应先走这里。
- `cd backend && python scripts/repair_legacy_schema.py --database-url <DATABASE_URL>` 是一次性 legacy repair authority；只在发现历史 `personas.persona_policy` / `knowledge_documents` drift 时显式执行。
- `cd backend && python scripts/bootstrap_auth_admin.py ...` 只负责账号 bootstrap，不拥有 schema authority。
- `backend/src/common/db/session.py` 里的 `init_db()` 只是 startup/bootstrap 入口：它仍会 `create_all()`，但 compatibility guard 只允许在 `development` / `test` / `testing` 做自动补齐；非开发环境发现 legacy drift 会 fail-fast 并要求你回到 Alembic / repair script。
- `scripts/dev-up.sh` 只负责拉起本地服务，不会先执行 `alembic upgrade head`；因此“能启动”不等于“迁移已经完成”。

## 2. 执行前先确认的环境事实

### 2.1 必须先记录真实环境变量

先在要执行的 shell 中确认真实值；不要直接相信仓库默认值，因为当前仓库有多处默认值漂移。

```bash
printf 'DATABASE_URL=%s\n' "${DATABASE_URL:-<unset>}"
printf 'REDIS_URL=%s\n' "${REDIS_URL:-<unset>}"
printf 'SESSION_STATE_REDIS_URL=%s\n' "${SESSION_STATE_REDIS_URL:-<unset>}"
printf 'DOCUMENT_STORAGE_PATH=%s\n' "${DOCUMENT_STORAGE_PATH:-<unset>}"
printf 'CHROMADB_PERSIST_DIR=%s\n' "${CHROMADB_PERSIST_DIR:-<unset>}"
printf 'CHROMA_PERSIST_DIRECTORY=%s\n' "${CHROMA_PERSIST_DIRECTORY:-<unset>}"
printf 'UPLOAD_DIR=%s\n' "${UPLOAD_DIR:-<unset>}"
printf 'ALI_OSS_BUCKET=%s\n' "${ALI_OSS_BUCKET:-<unset>}"
printf 'ALI_OSS_ENDPOINT=%s\n' "${ALI_OSS_ENDPOINT:-<unset>}"
```

### 2.2 当前必须记住的路径差异

- `scripts/dev-up.sh` 的本地开发默认库：`sales_training`
- `backend/src/common/db/session.py` 的运行时默认库：`ai_practice`
- `backend/src/common/config.py` 的 `DATABASE_URL` 默认值：SQLite `./ai_practice.db`
- `backend/src/common/storage/document.py` 默认文档目录：`./data/documents`
- `backend/src/common/knowledge/vector_store.py` 默认向量目录：`./data/chromadb`
- `backend/src/common/config.py` 的 `CHROMA_PERSIST_DIRECTORY` 默认值：`./data/chroma`
- `backend/src/common/config.py` 的通用上传目录：`./uploads`
- `backend/src/admin/api/admin.py` 旧 PPT 上传硬编码目录：`/data/uploads`

恢复或备份时，**以当前环境实际值为准**，不要假设仓库只有一个统一默认目录。

## 3. 当前最小备份频率（手工执行，不代表已自动化）

| 数据面 | 当前最小频率 | 当前可执行方式 | 当前风险说明 |
|---|---|---|---|
| PostgreSQL 主库 | 每周至少一次；每次执行 `alembic upgrade head`、`repair_legacy_schema.py`、`reset_db.py`、大版本发布前必须额外执行一次 | 手工 `pg_dump` | 仓库内没有自动调度或保留策略 |
| Redis 会话恢复状态 | 需要保留活跃会话可恢复能力时，在重启/迁移前执行一次；否则可接受丢失最近 30 分钟 reconnect 状态 | 手工 `redis-cli --rdb` | Redis 只承载短 TTL 会话快照，不是长期业务主数据 |
| 本地文档 / 向量库 / 上传目录 | 每周至少一次；知识库大批量导入或 PPT 上传后额外执行一次 | 手工 `tar` 归档 | 当前目录分散，且存在相对路径/绝对路径并存 |
| OSS 音频对象 | 当前仓库内**无**批量备份入口；至少每季度确认 bucket 配置与代表性对象可读 | 仓库内仅能验证 `object_key`/签名能力，不能批量导出 | 当前是已知缺口 |

## 4. 备份步骤（当前可执行基线）

以下步骤假设你已经在正确环境里导出了真实环境变量，并且 `pg_dump` / `pg_restore` / `redis-cli` / `tar` 已安装。

### 4.1 建立证据目录

```bash
export BACKUP_TS="$(date +%Y%m%d-%H%M%S)"
export BACKUP_DIR="./.dev/backup-evidence/${BACKUP_TS}"
mkdir -p "${BACKUP_DIR}"/{db,redis,files,notes}
```

### 4.2 PostgreSQL 逻辑备份

> 注意：应用运行时常用 `postgresql+asyncpg://...`；`pg_dump` / `pg_restore` 需要 libpq 风格 URL。

```bash
export PG_BACKUP_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"
pg_dump --format=custom --file "${BACKUP_DIR}/db/postgres.dump" "${PG_BACKUP_URL}"
pg_restore --list "${BACKUP_DIR}/db/postgres.dump" | head -n 20
```

如果上面的 `PG_BACKUP_URL` 为空或不正确，不要继续；先回到第 2 节确认真实 `DATABASE_URL`。

### 4.3 Redis 会话恢复状态备份（可选但建议在重启/迁移前执行）

```bash
export SESSION_STATE_REDIS_EFFECTIVE="${SESSION_STATE_REDIS_URL:-${REDIS_URL}}"
redis-cli -u "${SESSION_STATE_REDIS_EFFECTIVE}" --rdb "${BACKUP_DIR}/redis/session-state.rdb"
test -f "${BACKUP_DIR}/redis/session-state.rdb"
```

说明：
- 当前 Redis 主要保存 `ws:session_state:` 前缀、TTL 1800 秒的 reconnect 状态；
- 如果这部分丢失，活跃会话会失去恢复上下文，但数据库主数据不因此回退；
- 如果环境不要求保留活跃会话恢复，可以在记录风险后跳过此项。

### 4.4 本地目录归档

#### 4.4.1 仓库相对路径目录

```bash
for path in ./data/documents ./data/chromadb ./data/chroma ./uploads; do
  if [ -e "$path" ]; then
    safe_name="$(printf '%s' "$path" | tr '/' '_')"
    tar -czf "${BACKUP_DIR}/files/${safe_name}.tgz" "$path"
    tar -tzf "${BACKUP_DIR}/files/${safe_name}.tgz" | head -n 5
  fi
done
```

#### 4.4.2 旧绝对路径 `/data/uploads`（如果环境里真实存在）

```bash
if [ -e /data/uploads ]; then
  tar -P -czf "${BACKUP_DIR}/files/_data_uploads.tgz" /data/uploads
  tar -P -tzf "${BACKUP_DIR}/files/_data_uploads.tgz" | head -n 5
fi
```

### 4.5 OSS 音频对象当前基线

当前仓库只有以下事实：
- 数据库里保存 `object_key`
- 后端可基于 `ALI_OSS_*` 生成签名 PUT/GET URL
- 仓库内**没有**批量导出 OSS bucket 的脚本

因此当前备份基线只能做到：
1. 记录当前 bucket / endpoint 配置；
2. 确认关键环境中 OSS 凭证已配置；
3. 在工单里标注“OSS 批量备份不由仓库内脚本覆盖”。

## 5. 恢复步骤（当前真实顺序）

### 5.1 先停服务，避免边恢复边写入

```bash
bash scripts/dev-stop.sh
```

如果本次恢复也要停本机 PostgreSQL / Redis，可在确认影响后执行：

```bash
STOP_INFRA=1 bash scripts/dev-stop.sh
```

### 5.2 恢复 PostgreSQL 主库

以下命令适用于已经拿到 `postgres.dump` 的场景：

```bash
export PG_RESTORE_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"
pg_restore --clean --if-exists --no-owner --dbname "${PG_RESTORE_URL}" "${BACKUP_DIR}/db/postgres.dump"
```

如果目标环境要求先人工 drop/create 数据库，请先由环境负责人执行，再运行上面的 `pg_restore`。

### 5.3 对齐 schema 到当前代码版本

```bash
cd backend
alembic upgrade head
```

如果是老环境、升级后仍存在 `personas.persona_policy` 或 `knowledge_documents` legacy drift，再执行：

```bash
python scripts/repair_legacy_schema.py --database-url "${DATABASE_URL}"
```

这一步是**显式 repair authority**，不是 startup 自动补洞的替代写法。只有在你已经确认目标 revision 的前提下，才使用 `--stamp-revision <revision>`。

### 5.4 恢复本地目录

### 仓库相对路径目录

在仓库根目录执行：

```bash
for archive in "${BACKUP_DIR}"/files/*.tgz; do
  [ -e "$archive" ] || continue
  case "$archive" in
    *"_data_uploads.tgz") ;; # 绝对路径单独处理
    *) tar -xzf "$archive" ;;
  esac
done
```

### `/data/uploads` 绝对路径（如果有单独归档）

```bash
if [ -f "${BACKUP_DIR}/files/_data_uploads.tgz" ]; then
  tar -P -xzf "${BACKUP_DIR}/files/_data_uploads.tgz"
fi
```

### 5.5 Redis 会话状态恢复（可选）

当前仓库**没有**把 `session-state.rdb` 自动装回 Redis 的 repo-native 脚本。

因此当前真实口径是：
- 如果环境负责人有现成 Redis 服务级恢复流程，就按服务级流程恢复；
- 如果没有，就接受活跃会话 reconnect 状态丢失，并在恢复记录里注明“仅恢复数据库与文件面”。

### 5.6 必要时重建管理员 / 支持账号

```bash
cd backend
python scripts/bootstrap_auth_admin.py --email admin@qoder.ai --name 管理员 --role admin
python scripts/bootstrap_auth_admin.py --email support@qoder.ai --name 支持工程师 --role support
```

配套登录密码配置见：`docs/setup/auth-local.md`

### 5.7 启动服务

回到仓库根目录：

```bash
bash scripts/dev-up.sh
```

## 6. 恢复后验证步骤

至少执行下面这些检查并把输出附到同一条恢复记录。

### 6.1 后端健康检查

当前仓库以 `backend/src/main.py` 暴露的 `/health` 为准：

```bash
curl -fsS http://127.0.0.1:3444/health
```

预期包含：
- `"status": "healthy"`
- 当前时间戳
- 版本号字段

### 6.2 Schema 已对齐到当前代码

```bash
cd backend
alembic upgrade head
```

预期：无报错；如果已经是最新 revision，应表现为 no-op / 最新版本。若随后 startup 仍抛出 legacy personas / knowledge_documents drift 错误，说明需要回到 `python scripts/repair_legacy_schema.py --database-url "${DATABASE_URL}"` 这一显式 repair 入口，而不是依赖 `init_db()` 自动补齐。

### 6.3 管理员入口可重新建立

如果恢复后管理员账号缺失，重新执行：

```bash
cd backend
python scripts/bootstrap_auth_admin.py --email admin@qoder.ai --name 管理员 --role admin
```

预期：输出 `[created]` 或 `[updated]`。

### 6.4 文件面抽查

```bash
for path in ./data/documents ./data/chromadb ./data/chroma ./uploads /data/uploads; do
  [ -e "$path" ] && printf '[present] %s\n' "$path"
done
```

### 6.5 Redis 风险确认

如果本次没有恢复 Redis，会话恢复状态将从零开始。请在恢复记录里明确写明：
- 是否恢复 Redis；
- 如果未恢复，是否接受活跃会话 reconnect 状态丢失。

### 6.6 可复用的 repo-root authority 验证命令

以下命令可从仓库根目录直接执行，用于后续 M019 slices 或人工排查时快速确认 authority 线没有漂移：

```bash
rg -n "alembic upgrade head|repair_legacy_schema|bootstrap_auth_admin|init_db|startup" \
  docs/backup-recovery-runbook.md \
  docs/setup/backup-recovery-current-state.md \
  .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md \
  .github/workflows

backend/venv/bin/python -m pytest -c backend/pyproject.toml \
  backend/tests/integration/test_startup_or_bootstrap_authority.py \
  backend/tests/unit/common/test_db_session_compatibility.py -q
```

第一条命令确认文档 / CI 入口仍把 Alembic、repair script、bootstrap、`init_db()` 写在正确 authority 线上；第二条命令确认非开发环境 startup 不再静默修补 legacy drift，同时 development/test bootstrap 兼容 proof 仍然存在。

### 6.7 WebSocket runtime state / restart / drain guidance

这部分不是新的自动化功能，而是把当前仓库已经实现的 runtime authority 写成可执行口径，避免后续把“重启服务”误当成 cluster-aware drain。

#### 6.7.1 当前必须区分的两层 authority

- **进程内 live connection authority**：`SessionManager.get_stats()`
  - 真实拥有：`total_sessions`、`tracked_sessions[]`、`connection_visibility.scope=process_local`
  - 只说明“当前进程正在持有哪些 websocket / handler runtime diagnostics”
  - **不会**跨实例共享，**不会**跨重启保留
- **Redis reconnect snapshot authority**：`SessionStateService.get_stats()`
  - 真实拥有：`snapshot_visibility.scope=redis_snapshot`、`last_saved_snapshot`、`last_loaded_snapshot`、`request_epoch`、`connection_epoch`、`last_disconnect_reason`、`last_error`
  - 这是当前唯一可跨实例读取、并在 backend 重启后继续解释 reconnect 状态的 runtime authority

#### 6.7.2 单机 / systemd restart 的解释规则

如果当前环境是单机、单 backend 进程、或 systemd 直接拉起一个 backend worker：

1. restart 之前，如需留证，先记录：
   - 当前目标进程的 `SessionManager.get_stats()`（活跃连接数、tracked session、runtime diagnostics）
   - 当前共享 Redis 的 `SessionStateService.get_stats()`（最近 snapshot、request/connection epoch、last_error）
2. 执行 restart 后，`SessionManager` registry 归零是**预期行为**；这只说明旧进程已经退出，不等于所有 session 已正常终结。
3. restart 后仍可能存在可恢复的 session，是因为 Redis snapshot 还在 TTL 内，而不是因为 live socket 被“保留”了。
4. handler 内瞬态对象（pending response、websocket refs、最新 action card 等）不会跨重启保留；只能依赖 reconnect-safe snapshot 恢复最小 runtime subset。

#### 6.7.3 多实例 / 未来扩容的解释规则

如果未来是多实例或滚动发布：

- 必须把 `SessionManager.get_stats()` 的结论写成 **instance-local**；单个实例的 `total_sessions=0` 不能当成“整个集群已经 drain 完毕”。
- 必须把 `SessionStateService.get_stats()` 当成唯一 shared reconnect authority；它能说明哪些 session 还有可恢复 snapshot，但不能替代拥有 live websocket 的实例去执行 close / timeout / drain。
- 当前仓库**没有** repo-native 的 cluster drain endpoint、负载均衡摘流脚本或跨实例 live connection authority；真正的流量摘除 / 滚动升级要依赖仓库外的 ingress / LB / systemd 编排能力。

#### 6.7.4 当前可执行的最小 drain guidance

今天仓库里能诚实写出的最小 guidance 只有：

1. **先停新流量，再等 live connections 自然归零**：如果环境有上游 LB / ingress / 网关摘流能力，先把目标实例从新 websocket 流量里摘掉；仓库内没有替代这个动作的命令。
2. **观察 process-local active connections**：用 `SessionManager.get_stats()` 看目标实例的 `total_sessions` 是否下降，以及 `tracked_sessions[].runtime_diagnostics.reconnect_state` / `current_request_id` / `session_status` 是否仍在活动中。
3. **必要时接受强制重启的损失**：如果不能等待自然 drain，必须在工单里记录“live sockets 会被中断；只有 Redis reconnect snapshot 可能保留；pending response / action card / websocket ref 不会保留”。
4. **重启后验证 shared snapshot 是否仍可解释**：检查 `SessionStateService.get_stats()` 的 `last_saved_snapshot` / `last_loaded_snapshot` / `last_error`，确认 reconnect authority 没有因为 Redis 不可用而消失。

## 7. 当前已知不能假装存在的能力

以下能力当前**不应**写成“已具备”：

1. 仓库内没有自动调度的 PostgreSQL 备份任务；
2. 仓库内没有 Redis 恢复脚本；
3. 仓库内没有 OSS bucket 批量导出脚本；
4. 仓库内没有统一的 RTO / RPO 文档；
5. 仓库内没有明确值班人名册；
6. 仓库内没有 repo-native 的 websocket drain endpoint、负载均衡摘流脚本或 cluster-wide live connection authority。

## 8. Follow-up（非当前可执行基线）

### 8.1 灾难恢复演练建议（建议项，不代表已落地）

当前仓库没有灾难恢复演练记录。最小建议是**每季度至少做一次 60 分钟手工演练**，演练范围按下面顺序执行：

1. 选一个非生产环境，记录真实环境变量；
2. 手工做一次 PostgreSQL dump、Redis RDB（可选）、本地目录归档；
3. 停服务；
4. 从 dump 恢复数据库；
5. 执行 `alembic upgrade head`；
6. 恢复目录归档；
7. 必要时重建管理员账号；
8. `bash scripts/dev-up.sh`；
9. 执行 `/health` 检查并记录成功/失败；
10. 把本次耗时、缺失工具、路径漂移、人工判断点补回本 runbook。

### 8.2 后续改进（与当前可执行内容分开）

以下是后续改进项，不是当前仓库已落地能力：

- 提供 repo-native 的 `pg_dump` / `pg_restore` 包装脚本；
- 明确 Redis 服务级恢复流程；
- 明确 `./data/chromadb` 与 `./data/chroma` 的单一权威目录；
- 为 OSS 音频对象补齐批量导出或 bucket 级备份策略说明；
- 建立固定值班人、审批人、RTO / RPO、演练记录模板。
��目录归档；
7. 必要时重建管理员账号；
8. `bash scripts/dev-up.sh`；
9. 执行 `/health` 检查并记录成功/失败；
10. 把本次耗时、缺失工具、路径漂移、人工判断点补回本 runbook。

### 8.2 后续改进（与当前可执行内容分开）

以下是后续改进项，不是当前仓库已落地能力：

- 提供 repo-native 的 `pg_dump` / `pg_restore` 包装脚本；
- 明确 Redis 服务级恢复流程；
- 明确 `./data/chromadb` 与 `./data/chroma` 的单一权威目录；
- 为 OSS 音频对象补齐批量导出或 bucket 级备份策略说明；
- 建立固定值班人、审批人、RTO / RPO、演练记录模板。
