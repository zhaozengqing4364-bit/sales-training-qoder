---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: 为 auth recovery contract 补 focused proof

Why: S01 只有在 focused proof 能锁定 forgot/reset 全链路行为时才算真正闭合。

Do:
1. 补 focused tests，覆盖 forgot/reset 成功、过期、重复使用、rate limit 等路径。
2. 增加对 request-path DDL 已移除的约束性 proof。
3. 保持 auth proof 仍围绕 repo-root focused gate，不引入新的大而全测试入口。

Done when: auth recovery contract 的关键正负路径都有 focused proof，且回归命令稳定通过。

## Inputs

- `backend/tests/integration/test_auth_login_api.py`
- `backend/tests/**/*reset*.py`

## Expected Output

- `backend/tests/integration/test_auth_login_api.py`
- `backend/tests/**/*reset*.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

## Observability Impact

auth recovery contract 是否退化可由 focused tests 直接暴露。
