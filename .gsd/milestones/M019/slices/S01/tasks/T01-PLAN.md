---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T01: 盘点数据库演进与 bootstrap authority

- 盘点 `backend/src/common/db/session.py`、`backend/src/main.py`、bootstrap/auth 脚本、现有 Alembic revisions 和任何 compatibility patch 的当前职责。
- 把“启动初始化 / schema 演进 / 开发兼容 / 一次性 bootstrap”四类责任映射到真实代码入口。
- 在 `.gsd/analysis` 写一份 authority inventory，显式标出仍在 request/startup path 中执行的 schema 修补。

## Inputs

- `backend/src/common/db/session.py`
- `backend/src/main.py`
- `backend/alembic/versions`
- `scripts`
- `docs/backup-recovery-runbook.md`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/common/db/session.py`
- `backend/src/main.py`

## Verification

rg -n "create_all|alembic|bootstrap|repair_legacy_schema|init_db" backend/src/common/db/session.py backend/src/main.py backend/alembic/versions scripts
