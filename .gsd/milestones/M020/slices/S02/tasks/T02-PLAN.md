---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T02: 在 logger、API、UI 三层统一 redaction policy

- 在 logger sink、system log serialization、admin logs UI 三层统一应用 redaction policy。
- 保留 trace_id、severity、error code、phase、session_id 等排障必要字段。
- 为 admin/support 视角补 focused tests，防止未来新增字段绕过 policy。

## Inputs

- `T01 policy`
- `current admin log tests`

## Expected Output

- `backend/src/common/monitoring/logger.py`
- `backend/src/admin/api/system_logs.py`
- `web/src/app/admin/logs/page.tsx`
- `backend/tests/*system_log*.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q && npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"
