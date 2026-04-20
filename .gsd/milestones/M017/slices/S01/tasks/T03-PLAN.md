---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: 沉淀 lifecycle concurrency contract 证据

Why: lifecycle 并发证明要沉淀成可复用 contract，否则后续 websocket/terminal-state 调整还会重复争论。

Do:
1. 在 focused tests 或说明中记录选择当前锁策略的理由。
2. 标清哪些竞态已被收敛，哪些终态差异是刻意保留。
3. 保持 repo-root focused proof 作为长期回归入口。

Done when: lifecycle concurrency contract 既有测试证明，也有可读的策略说明。

## Inputs

- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

## Expected Output

- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q

## Observability Impact

future agents 能从同一组 proof 理解当前 lifecycle 收敛语义。
