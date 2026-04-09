---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: 为 auth recovery contract 补 focused proof

补 focused tests 覆盖 forgot/reset 成功、过期、重复使用、rate limit 等路径，确认 request-path DDL 已移除。

## Inputs

- `backend/tests/integration/test_auth_login_api.py`
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`

## Expected Output

- `backend/tests/integration/test_auth_login_api.py`
- `backend/tests/**/*reset*.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

## Observability Impact

failure-path proof
