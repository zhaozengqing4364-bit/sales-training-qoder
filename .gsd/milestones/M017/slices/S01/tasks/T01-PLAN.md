---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 设计 lifecycle race 场景与失败证明

Why: 先设计真实 race 场景，才能避免只在代码里凭感觉加锁或加 guard。

Do:
1. 阅读 SessionLifecycleService 与现有 unit/integration tests。
2. 设计 pause/resume/end 的 race 场景和最可能的非法状态迁移。
3. 明确哪些转移最值得先证明。

Done when: 已形成一组可执行 race 场景，后续实现可直接从 failing proof 出发。

## Inputs

- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

## Expected Output

- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

## Verification

rg -n "pause|resume|end|scoring|completed" backend/src/common/db/session_lifecycle.py backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py

## Observability Impact

形成 lifecycle race 场景与失败证明清单。
