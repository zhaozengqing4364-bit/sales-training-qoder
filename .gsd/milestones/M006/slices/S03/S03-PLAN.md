# S03: 主管 workflow service seam 抽取

**Goal:** Extract supervisor intervention write-side rules and read-side result semantics into dedicated service seams without changing the current API/UI contract.
**Demo:** After this: Create/remind/read supervisor interventions from the current `/admin/users/[id]` surface while the route handlers delegate workflow logic to extracted services and still show the same result semantics.

## Tasks
- [x] **T01: Extracted ManagerInterventionWriteService and slimmed the admin intervention routes down to service-backed transport/auth wrappers without changing the shipped response contract.** — Create a dedicated write-side service under `backend/src/admin/services/` to own `manager_interventions` create/load/update/remind rules, including due-state/reminder-state transitions and latest-open lookup. Refactor `/api/v1/admin/interventions` routes to delegate to it without changing response payloads.
  - Estimate: 0.75d
  - Files: backend/src/admin/services/manager_intervention_service.py, backend/src/admin/services/__init__.py, backend/src/admin/api/interventions.py, backend/tests/integration/test_admin_interventions_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py
- [ ] **T02: 抽出 latest-evaluable result resolver** — Extract latest-evaluable intervention-result resolution from `HistoryService` into a dedicated helper/module so supervisor workflow semantics are explicit and reusable. Keep the current rule that the latest evaluable completed session after intervention creation wins over a later thin non-evaluable session.
  - Estimate: 0.75d
  - Files: backend/src/common/analytics/manager_intervention_results.py, backend/src/common/analytics/history_service.py, backend/src/admin/api/users.py, backend/tests/integration/test_admin_users_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py
- [ ] **T03: 回归证明 current supervisor workflow 无漂移** — Run the current supervisor workflow regression path end-to-end after the service extraction and update the user-detail focused UI assertions if any copy or ordering assumptions need to be anchored more explicitly. The goal is zero behavior drift on the shipped `/admin/users/[id]` authority surface.
  - Estimate: 0.5d
  - Files: backend/tests/integration/test_admin_interventions_api.py, backend/tests/integration/test_admin_users_api.py, web/src/app/admin/users/[id]/page.test.tsx
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py tests/integration/test_admin_users_api.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'
