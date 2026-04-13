# S01: 启动期 schema authority 收口

**Goal:** 把 `init_db` / startup compatibility patch / bootstrap 脚本 / Alembic 的职责界线画清并收口到可执行 authority。
**Demo:** After this: 数据库演进、bootstrap、兼容补齐的 authority map 会落到真实迁移/脚本/测试入口，非开发环境不再靠隐式 schema 修补蒙混过关。

## Must-Haves

- `backend/src/common/db/session.py`、`backend/src/main.py`、bootstrap 脚本、Alembic revisions 的职责被文档化并由 focused proof 覆盖。
- 新实现/计划不再允许 request/startup 路径隐式 `create_all` / patch schema 充当常态迁移机制。
- dev/prod 两条启动链路的前置条件和失败信号清楚可见。

## Proof Level

- This slice proves: integration

## Integration Closure

S01 结束后，数据库演进、bootstrap、兼容补齐会有明确 authority map，S02-S04 可在不再猜 schema/runtime 责任归属的前提下继续抽层与接 release gate。

## Verification

- startup / migration / bootstrap failure 能通过 focused proof、日志和脚本入口明确定位，而不是在运行时隐式修补中被吞掉。

## Tasks

- [x] **T01: 盘点数据库演进与 bootstrap authority** `est:45m`
  - 盘点 `backend/src/common/db/session.py`、`backend/src/main.py`、bootstrap/auth 脚本、现有 Alembic revisions 和任何 compatibility patch 的当前职责。
- 把“启动初始化 / schema 演进 / 开发兼容 / 一次性 bootstrap”四类责任映射到真实代码入口。
- 在 `.gsd/analysis` 写一份 authority inventory，显式标出仍在 request/startup path 中执行的 schema 修补。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/common/db/session.py`, `backend/src/main.py`, `backend/alembic/versions`, `scripts`
  - Verify: rg -n "create_all|alembic|bootstrap|repair_legacy_schema|init_db" backend/src/common/db/session.py backend/src/main.py backend/alembic/versions scripts

- [x] **T02: 把隐式 schema 修补迁到迁移或显式脚本** `est:1.5h`
  - 把真正仍需要的兼容性 DDL/数据补齐从运行时隐式路径移到 Alembic revision 或显式 bootstrap 脚本。
- 保留开发/测试兼容性所需的最小路径，但让 prod startup 不再承担 schema 修复责任。
- 补 focused proof，证明缺迁移/缺配置时失败信号是显式的。
  - Files: `backend/alembic/versions`, `backend/src/common/db/session.py`, `backend/src/main.py`, `backend/tests/integration`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration -k "startup or bootstrap or migration" -x -q

- [x] **T03: 把 authority 结果写回文档与验证入口** `est:35m`
  - 更新 runbook / setup / architecture scan，让后续执行模型能直接分辨什么时候跑 Alembic、什么时候跑 bootstrap、什么时候不该让 startup 自动补洞。
- 为 M019 后续 slices 写下可复用的 repo-root 验证命令。
- 确认 `.github/workflows` 与此 authority line 不冲突。
  - Files: `docs/backup-recovery-runbook.md`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.github/workflows`
  - Verify: rg -n "alembic upgrade head|bootstrap|init_db|migration" docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .github/workflows

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/common/db/session.py
- backend/src/main.py
- backend/alembic/versions
- scripts
- backend/tests/integration
- docs/backup-recovery-runbook.md
- .github/workflows
