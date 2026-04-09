# S01: Session lifecycle 并发安全 proof

**Goal:** 为 SessionLifecycleService 建立并发安全证据，并在需要时引入行锁/乐观并发控制
**Demo:** After this: pause/resume/end 并发行为有可重复证明，状态收敛策略清晰

## Tasks
- [ ] **T01: 设计 lifecycle race 场景与失败证明** — 阅读 SessionLifecycleService 与现有 unit/integration tests，设计 pause/resume/end 的 race 场景，明确哪些转移最可能竞态。
  - Estimate: 35m
  - Files: backend/src/common/db/session_lifecycle.py, backend/tests/unit/test_session_lifecycle_service.py, backend/tests/integration/test_session_lifecycle_api.py
  - Verify: rg -n "pause|resume|end|scoring|completed" backend/src/common/db/session_lifecycle.py backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py
- [ ] **T02: 实现 lifecycle 并发收敛策略** — 先写 failing-to-passing 的并发 proof，用测试明确竞态，再选择行锁或乐观并发策略实现收敛，保持现有终态差异。
  - Estimate: 1.5h
  - Files: backend/src/common/db/session_lifecycle.py, backend/tests/unit/test_session_lifecycle_service.py, backend/tests/integration/test_session_lifecycle_api.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q
- [ ] **T03: 沉淀 lifecycle concurrency contract 证据** — 补审计/summary 说明，记录为何选择当前锁策略，以及哪些竞态被证明已收敛。
  - Estimate: 25m
  - Files: backend/tests/unit/test_session_lifecycle_service.py, backend/tests/integration/test_session_lifecycle_api.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q
