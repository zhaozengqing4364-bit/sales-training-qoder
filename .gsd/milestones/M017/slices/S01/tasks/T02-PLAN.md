---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T02: 实现 lifecycle 并发收敛策略

Why: 只有从 failing-to-passing 的并发 proof 出发，锁策略才会是事实驱动，而不是经验性补丁。

Do:
1. 先写 race-oriented failing proof。
2. 选择行锁或乐观并发策略实现收敛。
3. 保持 sales/presentation 现有终态差异与 report/replay 解锁语义。
4. 不把简单防抖误包装成并发安全修复。

Done when: focused lifecycle backend proof 通过，且状态收敛策略有明确理由。

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

竞态冲突与终态收敛策略可由 focused tests 与实现边界回查。
