# S02: 系统内主管重点与提醒闭环

**Goal:** Turn the existing manager-lite / intervention entrypoints into a minimal in-product manager workflow with persistent focus, reminder, and result linkage.
**Demo:** A supervisor can set a training focus, send a reminder, and later see whether a resulting session improved that issue family — all on current admin surfaces.

## Must-Haves

- A supervisor can set a training focus, send a reminder, and later see whether a resulting session improved that issue family — all on current admin surfaces.

## Proof Level

- This slice proves: integration

## Integration Closure

Build on the current admin users and intervention routes/pages only: `backend/src/admin/api/interventions.py`, `backend/src/admin/api/users.py`, `backend/src/common/db/models.py`, `web/src/app/admin/users/[id]/page.tsx`, `web/src/app/admin/users/page.tsx`, and `web/src/components/admin/manager-lite-panel.tsx`. No separate task system.

## Verification

- Intervention state transitions and result linkage become inspectable on current admin routes and focused tests; the manager workflow should not hide in logs anymore.

## Tasks

- [ ] **T01: Persist the minimal manager intervention record on current admin APIs** `est:2h`
  Introduce a minimal persistent intervention record on the current admin backend chain: target issue family, note, due state, reminder status, and optional resolving session linkage. Keep it small and tied to current admin users/intervention routes rather than building a general task platform.
  - Files: `backend/src/admin/api/interventions.py`, `backend/src/common/db/models.py`, `backend/src/common/db/schemas.py`, `backend/tests/integration/test_admin_interventions_api.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py

- [ ] **T02: Let supervisors create and inspect interventions on current admin user surfaces** `est:90m`
  Update the current admin users detail/list surfaces so a supervisor can create and inspect interventions without leaving the existing business chain. Reuse current user detail and manager-lite components rather than adding a new workflow console.
  - Files: `web/src/app/admin/users/[id]/page.tsx`, `web/src/app/admin/users/page.tsx`, `web/src/components/admin/manager-lite-panel.tsx`, `web/src/app/admin/users/[id]/page.test.tsx`, `web/src/components/admin/manager-lite-panel.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'

- [ ] **T03: Link interventions back to later session outcomes on the current evidence line** `est:75m`
  Link the intervention state back to the current report/replay evidence chain so a manager can tell whether the targeted issue family improved after a later session. Reuse existing projection/evidence semantics and admin drill-ins instead of a bespoke result screen.
  - Files: `backend/src/admin/api/users.py`, `backend/src/common/analytics/history_service.py`, `backend/tests/integration/test_admin_users_api.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py

## Files Likely Touched

- backend/src/admin/api/interventions.py
- backend/src/common/db/models.py
- backend/src/common/db/schemas.py
- backend/tests/integration/test_admin_interventions_api.py
- web/src/app/admin/users/[id]/page.tsx
- web/src/app/admin/users/page.tsx
- web/src/components/admin/manager-lite-panel.tsx
- web/src/app/admin/users/[id]/page.test.tsx
- web/src/components/admin/manager-lite-panel.test.tsx
- backend/src/admin/api/users.py
- backend/src/common/analytics/history_service.py
- backend/tests/integration/test_admin_users_api.py
