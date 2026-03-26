# S02: 系统内主管重点与提醒闭环

**Goal:** Turn the existing manager-lite / intervention entrypoints into a minimal in-product manager workflow with persistent focus, reminder, and result linkage.
**Demo:** After this: A supervisor can set a training focus, send a reminder, and later see whether a resulting session improved that issue family — all on current admin surfaces.

## Tasks
- [x] **T01: Added persistent manager intervention records and reminder lifecycle state to the current admin API chain.** — Introduce a minimal persistent intervention record on the current admin backend chain: target issue family, note, due state, reminder status, and optional resolving session linkage. Keep it small and tied to current admin users/intervention routes rather than building a general task platform.
  - Estimate: 2h
  - Files: backend/src/admin/api/interventions.py, backend/src/common/db/models.py, backend/src/common/db/schemas.py, backend/tests/integration/test_admin_interventions_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py
- [x] **T02: Added in-place supervisor intervention create/remind UI on the admin user detail page, with manager-lite deep links into that same surface.** — Update the current admin users detail/list surfaces so a supervisor can create and inspect interventions without leaving the existing business chain. Reuse current user detail and manager-lite components rather than adding a new workflow console.
  - Estimate: 90m
  - Files: web/src/app/admin/users/[id]/page.tsx, web/src/app/admin/users/page.tsx, web/src/components/admin/manager-lite-panel.tsx, web/src/app/admin/users/[id]/page.test.tsx, web/src/components/admin/manager-lite-panel.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
- [x] **T03: Linked supervisor interventions to the latest meaningful session evidence and surfaced the result on the admin user detail page.** — Link the intervention state back to the current report/replay evidence chain so a manager can tell whether the targeted issue family improved after a later session. Reuse existing projection/evidence semantics and admin drill-ins instead of a bespoke result screen.
  - Estimate: 75m
  - Files: backend/src/admin/api/users.py, backend/src/common/analytics/history_service.py, backend/tests/integration/test_admin_users_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py
