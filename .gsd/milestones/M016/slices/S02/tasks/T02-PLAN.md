---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T02: 收口 backend error contract 并对齐 frontend client

Why: 统一 outward 错误 shape 是 frontend client 和 admin/learner 页面停止 page-local 猜测的前提。

Do:
1. 为 domain、permission、not-found、validation error 收口统一 outward contract。
2. 在高噪声 route family 上落这套 contract，而不是一次性扫完整个 backend。
3. 对齐 frontend `apiFetch`，确保稳定解析这套 shape。
4. 不重写 FastAPI 全局异常体系，只修当前 audit 命中的核心 surface。

Done when: focused contract/integration proof 通过，frontend client 不再依赖页面本地错误猜测。

## Inputs

- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`

## Expected Output

- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q

## Observability Impact

错误 outward shape 统一后，跨端故障定位成本下降。
