---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T01: 硬化 backend governance / linked-asset schema

Introduce shared backend schema models for asset governance summary and linked-asset change references, then replace current dict-typed fields on knowledge/persona/presentation/runtime/admin-support response models. Keep the payload shape backward-compatible while making the contract explicit in Python types.

## Inputs

- `backend/src/common/db/schemas.py`
- `backend/src/common/knowledge/schemas.py`
- `backend/src/agent/schemas.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/admin/api/voice_runtime.py`
- `backend/src/support/api/runtime_status.py`

## Expected Output

- `Shared backend schema models for governance summary and linked asset references`
- `Current admin/support responses stop declaring these fields as raw dicts`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py
