# Backup / Recovery 当前现状清单

最后更新：2026-04-12  
适用范围：当前仓库可见的本地开发 / 仓库内运维入口  
用途：给 `docs/backup-recovery-runbook.md` 提供事实基线；这里只记录仓库里已经存在的真实路径、命令和缺口，不补写不存在的自动化。

## 1. 当前可确认的部署 / 启动方式

### 1.1 仓库内主入口是本机脚本，不是 Docker / K8s / IaC

当前仓库里可直接引用的启动入口：

- `scripts/dev-up.sh`
- `scripts/dev-stop.sh`
- `scripts/README.md`

从这些文件能确认：

- 默认是 **本机开发启动**；
- `scripts/dev-up.sh` 会按环境变量或 `.env` 内容拉起 backend / web；
- 当 `DATABASE_URL` / `REDIS_URL` 指向本机时，脚本会尝试用 `brew services` 自动启动 PostgreSQL / Redis；
- 仓库根下 **没有** `docker-compose.yml` / `compose.yaml` / `Dockerfile` 作为当前主部署说明；
- `.github/workflows/nfr-performance-check.yml` 只证明 CI 会拉一个临时 PostgreSQL 16 service 跑测试，**不能**当作生产备份能力存在的证据。

### 1.2 当前默认端口与本机依赖

`scripts/dev-up.sh` 里的默认值：

- Backend: `3444`
- Frontend: `3445`
- PostgreSQL: `5432`
- Redis: `6379`

可直接引用的命令：

```bash
bash scripts/dev-up.sh
bash scripts/dev-stop.sh
STOP_INFRA=1 bash scripts/dev-stop.sh
```

## 2. 当前可确认的数据面与持久化面

| 面向 | 当前仓库事实 | 证据路径 |
|---|---|---|
| 主业务数据库 | backend 运行时通过 `DATABASE_URL` 连接数据库；`scripts/dev-up.sh` 默认指向本机 PostgreSQL | `backend/src/common/db/session.py`, `scripts/dev-up.sh` |
| Redis 会话恢复状态 | WebSocket reconnect 状态保存在 Redis，默认 key 前缀 `ws:session_state:`，TTL 1800 秒 | `backend/src/common/websocket/session_state_service.py`, `backend/src/common/config.py`, `backend/.env.example` |
| 知识库原始文档 | 默认保存到本地目录 `./data/documents` | `backend/src/common/storage/document.py`, `backend/src/common/knowledge/processor.py`, `backend/process_pending_docs.py` |
| 向量库 / Chroma 持久化 | 当前代码默认使用本地目录 `./data/chromadb` | `backend/src/common/knowledge/vector_store.py`, `backend/process_pending_docs.py` |
| 一般上传目录配置 | `Settings.UPLOAD_DIR` 默认值是 `./uploads` | `backend/src/common/config.py` |
| 旧 admin PPT 上传路径 | 旧 admin 上传路由把文件直接写到硬编码路径 `/data/uploads` | `backend/src/admin/api/admin.py` |
| 训练音频原始字节 | `session_audio_segments` 只存元数据；实际音频字节在阿里云 OSS | `backend/src/common/db/models.py`, `backend/src/common/oss/signing.py` |

## 3. 数据库连接与迁移 / 修复事实

### 3.1 运行时数据库入口

当前 backend 运行时真实入口：

- `backend/src/main.py` 在 startup 中调用 `await init_db()`；
- `backend/src/common/db/session.py` 负责创建 `AsyncSessionLocal` 和 engine；
- 对非 SQLite，engine 使用连接池配置：`pool_pre_ping=True`、`pool_size=20`、`max_overflow=10`。

### 3.2 Alembic 已存在，可作为恢复后 schema 对齐入口

仓库里存在完整 Alembic 目录：

- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/*`

CI 里的真实调用方式也能直接引用：

```bash
cd backend
alembic upgrade head
```

证据路径：`.github/workflows/nfr-performance-check.yml`

### 3.3 启动时存在 `create_all()` 兼容行为，但这不是备份/恢复替代品

`backend/src/common/db/session.py` 里的 `init_db()` 会执行：

- `Base.metadata.create_all`
- `_ensure_persona_policy_column_compatibility(...)`
- `_ensure_knowledge_document_schema_compatibility(...)`

这说明：

- 仓库当前允许在启动时做一部分 **兼容性补丁 / 缺表创建**；
- 但这只是一种“代码升级后尽量别起不来”的保护；
- **不能**把它当成可靠的备份恢复方案，也不能替代完整的库级 restore 流程。

### 3.4 已有一次性修老库脚本

仓库内已有真实修复脚本：

```bash
cd backend
python scripts/repair_legacy_schema.py --database-url <DATABASE_URL>
python scripts/repair_legacy_schema.py --database-url <DATABASE_URL> --stamp-revision <revision>
```

它当前能做的事：

- 调用 `_ensure_knowledge_document_schema_compatibility(...)` 修老 schema；
- 在需要时写入 / 更新 `alembic_version`；
- 目标是“老环境补兼容 + 可选补 Alembic 状态”，不是通用 restore 工具。

证据路径：`backend/scripts/repair_legacy_schema.py`

### 3.5 已有破坏性 reset 脚本

仓库内有：

```bash
cd backend
python reset_db.py
```

它会：

- 读取 `DATABASE_URL`；
- `drop_all`；
- `create_all`。

这可以作为**重建空库**入口，但它是破坏性操作，不是 restore；执行前必须确认已经有外部备份。

证据路径：`backend/reset_db.py`

## 4. 当前可直接引用的“恢复后补齐”命令

### 4.1 恢复 schema 到当前代码版本

```bash
cd backend
alembic upgrade head
```

### 4.2 老环境 schema 漂移修补

```bash
cd backend
python scripts/repair_legacy_schema.py --database-url <DATABASE_URL>
```

### 4.3 本地重建管理员 / 支持账号

```bash
cd backend
python scripts/bootstrap_auth_admin.py --email admin@qoder.ai --name 管理员 --role admin
python scripts/bootstrap_auth_admin.py --email support@qoder.ai --name 支持工程师 --role support
```

证据路径：`backend/scripts/bootstrap_auth_admin.py`, `docs/setup/auth-local.md`

## 5. 当前已知的备份 / 恢复缺口（如实记录）

以下能力 **未在仓库中发现可执行入口**：

1. **没有** `pg_dump` / `pg_restore` / 逻辑备份脚本；
2. **没有** Redis dump / restore 脚本；
3. **没有** Chroma / `data/documents` / `/data/uploads` 的归档脚本；
4. **没有** 对 OSS 音频对象的仓库内备份脚本；
5. **没有** 现成的灾难恢复演练 runbook；
6. **没有** 明确的生产负责人 / 值班人 / RTO / RPO 文档；
7. **没有** 一份把“数据库 + Redis + 本地文档 + Chroma + OSS 音频”串起来的统一恢复步骤文档。

## 6. 当前容易踩坑但必须写进 runbook 的事实

### 6.1 `DATABASE_URL` 默认值并不完全一致

当前仓库里至少有两条默认线：

- `backend/src/common/db/session.py` 默认是 `postgresql+asyncpg://postgres:password@localhost:5432/ai_practice`
- `backend/src/common/config.py` 默认是 `sqlite+aiosqlite:///./ai_practice.db`
- `scripts/dev-up.sh` 本机开发默认是 `postgresql+asyncpg://dev:dev@127.0.0.1:5432/sales_training`

这意味着：

- runbook 不能写成“默认数据库唯一明确是 X”；
- 恢复前必须先确认 **实际环境中的 `DATABASE_URL`**；
- Alembic、runtime、开发脚本三处默认值并不天然等价。

### 6.2 持久化目录并不完全统一

当前至少存在这些路径事实：

- `./data/documents`：知识文档原件
- `./data/chromadb`：向量库持久化
- `./uploads`：通用上传目录配置默认值
- `/data/uploads`：旧 admin PPT 上传硬编码路径

这意味着恢复文档不能只写“恢复数据库即可”；至少还要区分：

- 本地文档原件是否还在；
- Chroma 向量目录是否还在；
- 旧 PPT 上传目录是否还在；
- OSS 音频对象是否还能按 `object_key` 取回。

## 7. T02 runbook 可直接复用的证据路径

建议下一任务直接引用这些路径：

- 启停入口：`scripts/README.md`, `scripts/dev-up.sh`, `scripts/dev-stop.sh`
- 数据库入口：`backend/src/common/db/session.py`, `backend/src/main.py`
- Alembic 入口：`backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/`
- 老库修复：`backend/scripts/repair_legacy_schema.py`
- 管理员恢复：`backend/scripts/bootstrap_auth_admin.py`, `docs/setup/auth-local.md`
- 破坏性重建入口：`backend/reset_db.py`
- 本地文档存储：`backend/src/common/storage/document.py`
- 向量库存储：`backend/src/common/knowledge/vector_store.py`
- Redis 会话恢复：`backend/src/common/websocket/session_state_service.py`
- 音频 OSS：`backend/src/common/oss/signing.py`, `backend/src/common/db/models.py`

## 8. 当前最小结论

当前仓库已经具备：

- 启动 / 停止本地环境的脚本；
- 数据库迁移与老库修复入口；
- 本地重建管理员账号入口；
- 可定位的本地文档、向量库、Redis、OSS 音频持久化面。

但当前仓库**还不具备**：

- 一键备份脚本；
- 一键恢复脚本；
- 数据面统一恢复顺序说明；
- 灾备演练记录。

因此 T02 的目标应是：把这些已存在的真实入口、路径、缺口和验证步骤整理成最小可执行 runbook，而不是假设仓库已经有自动化备份平台。
