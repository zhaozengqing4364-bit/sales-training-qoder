# 部署说明

本文记录当前项目的实际部署方式，以及生产环境遇到“代码已升级但数据库/Alembic 状态未对齐”时的修复流程。

## 当前运行形态

- 后端端口：`3444`
- 前端端口：`3445`
- 后端进程：`pm2` 进程名 `sales-training-qoder-backend`
- 前端进程：`pm2` 进程名 `sales-training-qoder-web`
- 服务器目录：
  - 后端：`/root/sales-training-qoder/backend`
  - 前端：`/root/sales-training-qoder/web`
- 后端启动方式：
  - `cwd=/root/sales-training-qoder/backend/src`
  - `script=/root/sales-training-qoder/backend/runtime-venv/bin/python`
  - `args=-m uvicorn main:app --host 0.0.0.0 --port 3444`

## 热修复发布

当前线上目录可能不是一个完整的 Git 工作区，不能假设服务器支持 `git pull`。补丁发布建议走文件同步。

### 1. 同步后端文件

在本地仓库根目录执行：

```bash
rsync -avR \
  backend/requirements.txt \
  backend/alembic/versions/20260314_1200_018_expand_knowledge_document_file_types.py \
  backend/src/common/db/session.py \
  backend/src/common/knowledge/api.py \
  backend/src/common/knowledge/models.py \
  backend/src/common/knowledge/processor.py \
  backend/src/common/knowledge/schemas.py \
  backend/src/common/storage/document.py \
  backend/scripts/repair_legacy_schema.py \
  user@server:/root/sales-training-qoder/
```

### 2. 安装运行时依赖

```bash
cd /root/sales-training-qoder/backend
./runtime-venv/bin/pip install -r requirements.txt
```

当前知识库文档修复依赖以下包：

- `xlrd`
- `psycopg2-binary`

## 生产库兼容修复

历史环境可能已经有业务表，但没有 `alembic_version`，或者 `knowledge_documents.file_type` 仍只允许 `pdf/docx/txt/md`。

### 一次性修复命令

```bash
cd /root/sales-training-qoder/backend
./runtime-venv/bin/python scripts/repair_legacy_schema.py \
  --stamp-revision 20260314_1200_018
```

这个脚本会做两件事：

- 修复 `knowledge_documents` 旧约束，使其支持 `xlsx/xls`
- 在确认目标 revision 存在的前提下，补齐或更新 `alembic_version`

适用场景：

- 服务器库是“手工建库/历史导入”，不是从 Alembic 初始化出来的
- 代码已经升级，但 `alembic upgrade head` 会因为缺失版本状态或重复建表失败

## 重启服务

```bash
pm2 restart sales-training-qoder-backend
pm2 restart sales-training-qoder-web
pm2 list
```

仅改后端时，通常只需要重启 `sales-training-qoder-backend`。

## 发布后验证

### 1. 检查后端日志

```bash
pm2 logs sales-training-qoder-backend --lines 50 --nostream
```

### 2. 检查文档上传

建议至少验证两类文件：

- 带表格的 `docx`
- `xlsx`

预期：

- 上传接口返回 `202`
- 文档状态随后从 `pending` 变为 `ready`
- 后端日志出现 `Document processed successfully`

### 3. 数据库检查

PostgreSQL 可用：

```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'knowledge_documents'::regclass
  AND conname = 'ck_knowledge_document_file_type';
```

预期约束包含：

```sql
file_type IN ('pdf', 'docx', 'txt', 'md', 'xlsx', 'xls')
```

## 风险说明

- `repair_legacy_schema.py --stamp-revision ...` 只应用于已经存在业务表的历史环境。
- 如果数据库是全新环境，优先使用标准流程：

```bash
alembic upgrade head
```

- 如果 `alembic_version` 中出现多行，说明存在分支头或异常状态，脚本会拒绝自动覆盖，需要人工确认后再处理。
