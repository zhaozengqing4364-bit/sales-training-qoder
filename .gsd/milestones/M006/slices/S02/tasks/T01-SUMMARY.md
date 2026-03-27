---
id: T01
parent: S02
milestone: M006
provides: []
requires: []
affects: []
key_files: ["backend/src/common/db/schemas.py", "backend/src/common/knowledge/schemas.py", "backend/src/common/knowledge/api.py", "backend/src/agent/schemas.py", "backend/src/admin/api/voice_runtime.py", "backend/src/support/api/runtime_status.py", "backend/tests/integration/test_asset_governance_api.py", "backend/tests/contract/test_support_runtime.py", ".gsd/milestones/M006/slices/S02/tasks/T01-SUMMARY.md"]
key_decisions: ["Anchored AssetGovernanceSummary and LinkedAssetChangeReference in common backend schemas, then reused them from route-local response envelopes instead of leaving runtime/support OpenAPI as generic objects.", "Validated governance_summary into a typed Pydantic model before copying it into knowledge list responses so the hardened contract stays typed in-memory as well as at the route boundary."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Passed the planned backend verification command from backend/: tests/integration/test_asset_governance_api.py, tests/contract/test_analytics.py, and tests/contract/test_support_runtime.py all passed. The new focused schema/OpenAPI assertions passed within that suite, and LSP diagnostics were clean for backend/src/common/db/schemas.py, backend/src/common/knowledge/schemas.py, backend/src/common/knowledge/api.py, backend/src/agent/schemas.py, backend/src/admin/api/voice_runtime.py, backend/src/support/api/runtime_status.py, backend/tests/integration/test_asset_governance_api.py, and backend/tests/contract/test_support_runtime.py."
completed_at: 2026-03-27T06:31:12.895Z
blocker_discovered: false
---

# T01: Added shared backend governance schemas plus typed runtime/support envelopes without changing the shipped JSON payloads.

> Added shared backend governance schemas plus typed runtime/support envelopes without changing the shipped JSON payloads.

## What Happened
---
id: T01
parent: S02
milestone: M006
key_files:
  - backend/src/common/db/schemas.py
  - backend/src/common/knowledge/schemas.py
  - backend/src/common/knowledge/api.py
  - backend/src/agent/schemas.py
  - backend/src/admin/api/voice_runtime.py
  - backend/src/support/api/runtime_status.py
  - backend/tests/integration/test_asset_governance_api.py
  - backend/tests/contract/test_support_runtime.py
  - .gsd/milestones/M006/slices/S02/tasks/T01-SUMMARY.md
key_decisions:
  - Anchored AssetGovernanceSummary and LinkedAssetChangeReference in common backend schemas, then reused them from route-local response envelopes instead of leaving runtime/support OpenAPI as generic objects.
  - Validated governance_summary into a typed Pydantic model before copying it into knowledge list responses so the hardened contract stays typed in-memory as well as at the route boundary.
duration: ""
verification_result: passed
completed_at: 2026-03-27T06:31:12.897Z
blocker_discovered: false
---

# T01: Added shared backend governance schemas plus typed runtime/support envelopes without changing the shipped JSON payloads.

**Added shared backend governance schemas plus typed runtime/support envelopes without changing the shipped JSON payloads.**

## What Happened

Introduced shared AssetGovernanceSummary and LinkedAssetChangeReference models in backend/src/common/db/schemas.py, then promoted the knowledge, persona, and presentation response schemas to use the shared governance type instead of raw dict fields. Added explicit runtime-profile and support-runtime response envelopes so /api/v1/admin/voice-runtime/profiles, /api/v1/support/runtime/overview, and /api/v1/support/runtime/faults now advertise typed governance and linked-asset contracts in OpenAPI. Added focused regression checks for schema refs and OpenAPI refs, then fixed a remaining weak spot in common/knowledge/api.py by validating governance_summary before copying it into a typed response model to avoid serializer warnings. The planned backend verification suite passed end-to-end, so T01 now provides the backend contract anchor for T02/T03 without changing the shipped payload keys.

## Verification

Passed the planned backend verification command from backend/: tests/integration/test_asset_governance_api.py, tests/contract/test_analytics.py, and tests/contract/test_support_runtime.py all passed. The new focused schema/OpenAPI assertions passed within that suite, and LSP diagnostics were clean for backend/src/common/db/schemas.py, backend/src/common/knowledge/schemas.py, backend/src/common/knowledge/api.py, backend/src/agent/schemas.py, backend/src/admin/api/voice_runtime.py, backend/src/support/api/runtime_status.py, backend/tests/integration/test_asset_governance_api.py, and backend/tests/contract/test_support_runtime.py.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py` | 0 | ✅ pass | 7180ms |


## Deviations

None.

## Known Issues

The backend OpenAPI build still emits the pre-existing duplicate operation-id warning from admin/api/model_configs.py; this task did not change that surface.

## Files Created/Modified

- `backend/src/common/db/schemas.py`
- `backend/src/common/knowledge/schemas.py`
- `backend/src/common/knowledge/api.py`
- `backend/src/agent/schemas.py`
- `backend/src/admin/api/voice_runtime.py`
- `backend/src/support/api/runtime_status.py`
- `backend/tests/integration/test_asset_governance_api.py`
- `backend/tests/contract/test_support_runtime.py`
- `.gsd/milestones/M006/slices/S02/tasks/T01-SUMMARY.md`


## Deviations
None.

## Known Issues
The backend OpenAPI build still emits the pre-existing duplicate operation-id warning from admin/api/model_configs.py; this task did not change that surface.
