---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T01: Expose asset impact and recent-change summaries on current backend routes

Add backend impact and recent-change summaries for the current asset types: knowledge bases, personas, presentations, and voice runtime profiles. Reuse current services/APIs and support/runtime diagnostics so the data comes from real usage and anomaly lines rather than static metadata only.

## Inputs

- `backend/src/agent/services/persona_service.py`
- `backend/src/common/knowledge/api.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/admin/api/voice_runtime.py`
- `backend/src/support/services/runtime_status_service.py`

## Expected Output

- `backend/src/agent/services/persona_service.py`
- `backend/src/common/knowledge/api.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/admin/api/voice_runtime.py`
- `backend/src/support/services/runtime_status_service.py`
- `backend/tests/integration/test_asset_governance_api.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py
