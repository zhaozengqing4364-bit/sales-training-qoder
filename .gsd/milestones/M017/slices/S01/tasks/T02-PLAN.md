---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 实现 lifecycle 并发收敛策略

先写 failing-to-passing 的并发 proof，用测试明确竞态，再选择行锁或乐观并发策略实现收敛，保持现有终态差异。

## Inputs

- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

## Expected Output

- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q

## Observability Impact

竞态冲突与终态收敛可诊断
