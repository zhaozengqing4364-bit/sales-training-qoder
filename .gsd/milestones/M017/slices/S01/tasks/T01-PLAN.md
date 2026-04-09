---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 设计 lifecycle race 场景与失败证明

阅读 SessionLifecycleService 与现有 unit/integration tests，设计 pause/resume/end 的 race 场景，明确哪些转移最可能竞态。

## Inputs

- `backend/src/common/db/session_lifecycle.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

## Expected Output

- `race test plan`

## Verification

rg -n "pause|resume|end|scoring|completed" backend/src/common/db/session_lifecycle.py backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py

## Observability Impact

current race surface inventory
