---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: 补依赖治理 proof 与执行前置说明

如果环境具备，跑最小依赖检查 proof；若不具备，则明确 pip_audit 的前置条件与执行方式，避免伪装已验证。

## Inputs

- `backend/requirements.txt`

## Expected Output

- `docs/*`

## Verification

backend/venv/bin/python -m pip_audit

## Observability Impact

scan prerequisites documented
