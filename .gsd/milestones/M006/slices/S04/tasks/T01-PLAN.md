---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 建立 backend asset registry

Create a backend asset registry module that centralizes current asset-type metadata (label, admin path builder, reference extraction hooks) for knowledge bases, personas, presentations, and runtime profiles. Refactor `RuntimeStatusService` to consume the registry for asset-ref iteration and linked-change enrichment instead of owning asset-type conditionals inline.

## Inputs

- `backend/src/support/services/runtime_status_service.py`
- `backend/tests/unit/test_support_runtime_service.py`

## Expected Output

- `Backend asset registry/adapter seam for current four asset types`
- ``RuntimeStatusService` resolves asset metadata through the registry`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py
