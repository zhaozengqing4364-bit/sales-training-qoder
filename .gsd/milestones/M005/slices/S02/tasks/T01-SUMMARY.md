---
id: T01
parent: S02
milestone: M005
provides: []
requires: []
affects: []
key_files: ["backend/src/admin/api/interventions.py", "backend/src/common/db/models.py", "backend/src/common/db/schemas.py", "backend/tests/integration/test_admin_interventions_api.py", "backend/alembic/versions/20260326_1000_021_add_manager_interventions.py"]
key_decisions: ["Persist the first manager workflow record in a dedicated `manager_interventions` table instead of stretching existing analytics or user routes into a generic task system.", "Keep `/api/v1/admin/interventions/remind` backward-compatible for current manager-lite callers while letting it update persisted reminder state when an intervention already exists."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the focused task verifier in red/green order and then re-ran it under explicit timing for evidence capture: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py` passed all 3 new integration tests. Also ran `cd backend && /usr/bin/time -p venv/bin/alembic upgrade head`, which applied revision `20260326_1000_021` successfully."
completed_at: 2026-03-26T07:05:35.959Z
blocker_discovered: false
---

# T01: Added persistent manager intervention records and reminder lifecycle state to the current admin API chain.

> Added persistent manager intervention records and reminder lifecycle state to the current admin API chain.

## What Happened
---
id: T01
parent: S02
milestone: M005
key_files:
  - backend/src/admin/api/interventions.py
  - backend/src/common/db/models.py
  - backend/src/common/db/schemas.py
  - backend/tests/integration/test_admin_interventions_api.py
  - backend/alembic/versions/20260326_1000_021_add_manager_interventions.py
key_decisions:
  - Persist the first manager workflow record in a dedicated `manager_interventions` table instead of stretching existing analytics or user routes into a generic task system.
  - Keep `/api/v1/admin/interventions/remind` backward-compatible for current manager-lite callers while letting it update persisted reminder state when an intervention already exists.
duration: ""
verification_result: passed
completed_at: 2026-03-26T07:05:35.961Z
blocker_discovered: false
---

# T01: Added persistent manager intervention records and reminder lifecycle state to the current admin API chain.

**Added persistent manager intervention records and reminder lifecycle state to the current admin API chain.**

## What Happened

Added a dedicated `manager_interventions` persistence layer for the current admin workflow instead of introducing a broader task platform. `backend/src/common/db/models.py` now defines the intervention table plus due-state and reminder-status enums, `backend/src/common/db/schemas.py` exposes typed create/update/reminder/response schemas, and `backend/src/admin/api/interventions.py` now supports create/list/patch intervention lifecycle operations while keeping `/api/v1/admin/interventions/remind` backward-compatible for current callers. The remind route now updates persisted reminder state when an intervention is present, and the patch route gives later slice work a narrow way to attach a resolving session link. Added a real Alembic revision so the new table exists on the actual backend database path, not only inside in-memory pytest setup.

## Verification

Ran the focused task verifier in red/green order and then re-ran it under explicit timing for evidence capture: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py` passed all 3 new integration tests. Also ran `cd backend && /usr/bin/time -p venv/bin/alembic upgrade head`, which applied revision `20260326_1000_021` successfully.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py` | 0 | ✅ pass | 5660ms |
| 2 | `cd backend && /usr/bin/time -p venv/bin/alembic upgrade head` | 0 | ✅ pass | 1010ms |


## Deviations

Added an Alembic migration file and a narrow `PATCH /api/v1/admin/interventions/{intervention_id}` lifecycle route in addition to the planned files because persistent storage needs a real schema upgrade path and later slice work needs a minimal way to attach resolving-session linkage without rebuilding the API surface.

## Known Issues

None.

## Files Created/Modified

- `backend/src/admin/api/interventions.py`
- `backend/src/common/db/models.py`
- `backend/src/common/db/schemas.py`
- `backend/tests/integration/test_admin_interventions_api.py`
- `backend/alembic/versions/20260326_1000_021_add_manager_interventions.py`


## Deviations
Added an Alembic migration file and a narrow `PATCH /api/v1/admin/interventions/{intervention_id}` lifecycle route in addition to the planned files because persistent storage needs a real schema upgrade path and later slice work needs a minimal way to attach resolving-session linkage without rebuilding the API surface.

## Known Issues
None.
