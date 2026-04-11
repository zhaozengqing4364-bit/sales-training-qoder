# S01: Session lifecycle 并发安全 proof

**Goal:** 为 SessionLifecycleService 建立并发安全证据，并在需要时引入行锁/乐观并发控制。
**Demo:** pause/resume/end 并发行为有可重复证明，状态收敛策略清晰。

## Must-Haves

- 至少一组 pause/resume/end race 场景有可重复 proof。
- lifecycle 的收敛策略（行锁或乐观并发）被明确选择，并保持现有终态差异。
- focused backend proof 能说明哪些竞态已被收敛，哪些语义仍是故意保留。

## Proof Level

- This slice proves: integration

## Integration Closure

S01 先证明 lifecycle 竞态与状态收敛边界，供 S02 websocket interrupt/reconnect 和 S03 上传/资源竞争 discovery 复用同一终态语义。

## Verification

- future agents 可通过 lifecycle focused tests 与状态收敛规则判断问题是 race、非法状态迁移还是正常终态差异。

## Tasks

- [x] **T01: 设计 lifecycle race 场景与失败证明** `est:35m`
  Why: 先设计真实 race 场景，才能避免只在代码里凭感觉加锁或加 guard。

Do:
1. 阅读 SessionLifecycleService 与现有 unit/integration tests。
2. 设计 pause/resume/end 的 race 场景和最可能的非法状态迁移。
3. 明确哪些转移最值得先证明。

Done when: 已形成一组可执行 race 场景，后续实现可直接从 failing proof 出发。
  - Files: `backend/src/common/db/session_lifecycle.py`, `backend/tests/unit/test_session_lifecycle_service.py`, `backend/tests/integration/test_session_lifecycle_api.py`
  - Verify: rg -n "pause|resume|end|scoring|completed" backend/src/common/db/session_lifecycle.py backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py

- [x] **T02: 实现 lifecycle 并发收敛策略** `est:1.5h`
  Why: 只有从 failing-to-passing 的并发 proof 出发，锁策略才会是事实驱动，而不是经验性补丁。

Do:
1. 先写 race-oriented failing proof。
2. 选择行锁或乐观并发策略实现收敛。
3. 保持 sales/presentation 现有终态差异与 report/replay 解锁语义。
4. 不把简单防抖误包装成并发安全修复。

Done when: focused lifecycle backend proof 通过，且状态收敛策略有明确理由。
  - Files: `backend/src/common/db/session_lifecycle.py`, `backend/tests/unit/test_session_lifecycle_service.py`, `backend/tests/integration/test_session_lifecycle_api.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q

- [ ] **T03: 沉淀 lifecycle concurrency contract 证据** `est:25m`
  Why: lifecycle 并发证明要沉淀成可复用 contract，否则后续 websocket/terminal-state 调整还会重复争论。

Do:
1. 在 focused tests 或说明中记录选择当前锁策略的理由。
2. 标清哪些竞态已被收敛，哪些终态差异是刻意保留。
3. 保持 repo-root focused proof 作为长期回归入口。

Done when: lifecycle concurrency contract 既有测试证明，也有可读的策略说明。
  - Files: `backend/tests/unit/test_session_lifecycle_service.py`, `backend/tests/integration/test_session_lifecycle_api.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q

## Files Likely Touched

- backend/src/common/db/session_lifecycle.py
- backend/tests/unit/test_session_lifecycle_service.py
- backend/tests/integration/test_session_lifecycle_api.py
