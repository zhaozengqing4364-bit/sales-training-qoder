---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T02: 用 focused proof 区分真实并发问题与想象风险

Why: discovery 的价值在于把“真实问题”与“audit 猜测”分开，而不是先上锁再找理由。

Do:
1. 为最可疑路径补最小复现 proof 或 focused tests。
2. 证明哪些路径真的会发生竞争，哪些只是理论风险。
3. 对真实风险提出下一步建议（局部锁、幂等、状态约束等），但不抢跑到实现。 

Done when: focused presentation proof 通过，且已有一份区分真实问题/想象风险的结论。

## Inputs

- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`
- `backend/tests/integration/test_presentation_delete_permissions.py`

## Expected Output

- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`
- `backend/tests/integration/test_presentation_delete_permissions.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q

## Observability Impact

upload/resource race 的真实程度由 focused proof 暴露，而不是继续停留在猜测。
