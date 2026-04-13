# S01: 启动期 schema authority 收口 — UAT

**Milestone:** M019
**Written:** 2026-04-13T03:15:29.446Z

# S01 UAT — 启动期 schema authority 收口

## Preconditions

- 从 repo root `/Users/zhaozengqing/github/销售训练qoder` 执行命令。
- `backend/venv` 已安装依赖。
- 本 UAT 使用测试创建的临时 SQLite fixture，不会修改真实业务库。
- 如果要做手工恢复演练，请先确认不会把命令指向生产库。

## Test Case 1 — production-like startup must fail fast on legacy persona schema drift

**Goal:** 证明非开发环境 startup 不再静默补 `personas.persona_policy`。

1. 运行：
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml \
     backend/tests/integration/test_startup_or_bootstrap_authority.py::test_production_startup_refuses_to_patch_legacy_personas_schema -q
   ```
2. 观察测试结果。

**Expected outcome**
- pytest 退出码为 0，测试通过。
- 该用例内部断言 startup 抛出 `RuntimeError`，并明确提示运行 Alembic migration `20260216_0100_015` 或 `python scripts/repair_legacy_schema.py`。
- 这证明 production-like startup 的失败信号是显式的，而不是自动补洞后继续启动。

## Test Case 2 — explicit repair seam must repair the same legacy schema deliberately

**Goal:** 证明 legacy drift 仍可通过显式 repair seam 修复，而不是必须靠 startup。

1. 运行：
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml \
     backend/tests/integration/test_startup_or_bootstrap_authority.py::test_repair_script_updates_legacy_personas_schema_explicitly -q
   ```
2. 观察测试结果。

**Expected outcome**
- pytest 退出码为 0，测试通过。
- 用例内部通过显式 repair seam 更新 legacy personas schema，并断言 `persona_policy` 列存在且带有从 legacy prompt 迁移出的 payload。
- 这证明 repair authority 已从 startup path 收到显式脚本/共享 repair seam。

## Test Case 3 — slice-level startup / bootstrap / migration proof bundle must stay green

**Goal:** 证明 slice 计划要求的集成 proof 入口保持可复跑。

1. 运行：
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration -k "startup or bootstrap or migration" -x -q
   ```
2. 查看 selected tests 与结果。

**Expected outcome**
- pytest 退出码为 0。
- 当前应选中并通过 startup authority focused tests。
- 允许出现已知的 pytest-cov no-data / SQLite teardown warning，但不得有失败测试。

## Test Case 4 — docs and CI must point to the same authority line

**Goal:** 证明 runbook / architecture scan / workflow 没有继续暗示 startup 是迁移 authority。

1. 运行：
   ```bash
   rg -n "alembic upgrade head|bootstrap|init_db|migration" \
     docs/backup-recovery-runbook.md \
     .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md \
     .github/workflows
   ```
2. 检查输出命中。

**Expected outcome**
- 输出明确包含：
  - `alembic upgrade head` 作为 migration authority；
  - `bootstrap_auth_admin.py` 只是 auth/bootstrap；
  - `init_db()` 是 startup/bootstrap seam；
  - workflow migration step 明确写成 Alembic-owned。
- 不应出现“startup 自动补齐即代表迁移完成”的表述。

## Test Case 5 — startup code inventory must still expose the authority seams directly

**Goal:** 证明后续开发者可以从代码入口直接读到 authority map。

1. 运行：
   ```bash
   rg -n "create_all|alembic|bootstrap|repair_legacy_schema|init_db" \
     backend/src/common/db/session.py backend/src/main.py backend/alembic/versions scripts
   ```
2. 检查输出。

**Expected outcome**
- `backend/src/common/db/session.py` 显示 `STARTUP_DB_AUTHORITY`、`Base.metadata.create_all`、`alembic upgrade head`、`repair_legacy_schema.py`、`bootstrap_auth_admin.py`。
- `backend/src/main.py` 显示 startup authority map logging 与 `await init_db()`。
- `backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py` 出现在输出中。

## Edge cases / failure interpretation

- 若 production-like startup 再次“成功启动”而没有失败信号，且库仍是 legacy schema，这属于 authority regression。
- 若 repair script 通过后仍提示 legacy drift，先检查是否跑错 `DATABASE_URL`，再检查是否漏跑 Alembic；不要回退到依赖 startup 自动修补。
- 若 focused test 在修改 `DATABASE_URL` / `ENVIRONMENT` 后表现异常，优先确认是否走了重新加载 `common.db.session` 的测试路径；该模块在 import 时就绑定 engine。
