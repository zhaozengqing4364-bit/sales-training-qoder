---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: 用 focused proof 区分真实并发问题与想象风险

补最小复现 proof 或测试，确认哪些路径真的会发生竞争、哪些只是 audit 猜测；输出下一步建议（如局部锁、幂等、状态约束）。

## Inputs

- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`

## Expected Output

- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`
- `discovery notes`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q

## Observability Impact

repro paths documented
