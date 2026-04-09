---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: 收口 backend error contract 并对齐 frontend client

实现统一错误 shape：把 domain / permission / not-found / validation error 收口到一致 outward contract，并确保 frontend apiFetch 能稳定解析。

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

typed error contract 成形
