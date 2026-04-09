---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 定位 upload / resource race 风险点

梳理 presentation upload / replace / delete 等路径的共享资源访问点，并和现有 active-session blocker 一起看，区分已覆盖与未覆盖的竞争面。

## Inputs

- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`
- `backend/tests/integration/test_presentation_delete_permissions.py`

## Expected Output

- `concurrency risk inventory`

## Verification

rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py

## Observability Impact

risk inventory
