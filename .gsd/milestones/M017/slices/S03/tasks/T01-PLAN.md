---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 定位 upload / resource race 风险点

Why: 先沿真实 upload/replace/delete 链路识别共享资源访问点，才能把 active-session blocker 已覆盖的和未覆盖的竞争面分开。

Do:
1. 梳理 presentation upload/replace/delete 路径的共享资源访问点。
2. 对照现有 active-session blocker，区分已覆盖与未覆盖竞争面。
3. 明确最值得先证明的 race surface。

Done when: 已形成 upload/resource race 风险点列表，后续 focused proof 有明确目标。

## Inputs

- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`

## Expected Output

- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`

## Verification

rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py

## Observability Impact

形成 upload/resource race 风险点 inventory。
