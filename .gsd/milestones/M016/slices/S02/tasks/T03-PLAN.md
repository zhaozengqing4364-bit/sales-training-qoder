---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: 为统一错误 shape 补跨端 proof

补 focused contract/integration proof，确认 frontend 不需要 page-local 猜测错误格式。

## Inputs

- `backend/tests/contract/test_presentations.py`
- `web/src/lib/api/client.ts`

## Expected Output

- `backend/tests/contract/*.py`
- `web/src/lib/api/*.test.ts`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q

## Observability Impact

error-path proof
