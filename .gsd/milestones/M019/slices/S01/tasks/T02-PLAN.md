---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T02: 把隐式 schema 修补迁到迁移或显式脚本

- 把真正仍需要的兼容性 DDL/数据补齐从运行时隐式路径移到 Alembic revision 或显式 bootstrap 脚本。
- 保留开发/测试兼容性所需的最小路径，但让 prod startup 不再承担 schema 修复责任。
- 补 focused proof，证明缺迁移/缺配置时失败信号是显式的。

## Inputs

- `T01 盘点结果`
- `backend/tests/integration`
- `backend/tests/unit`

## Expected Output

- `backend/alembic/versions/*`
- `backend/src/common/db/session.py`
- `backend/tests/integration/test_startup_or_bootstrap_authority.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration -k "startup or bootstrap or migration" -x -q
