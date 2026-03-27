---
id: T01
parent: S05
milestone: M005
provides:
  - A focused regression pack for the current admin operating chain covering analytics export, manager-lite reminder action, user drill-in context, and intervention review on one evidence vocabulary.
key_files:
  - backend/tests/contract/test_analytics.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/integration/test_admin_interventions_api.py
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
key_decisions:
  - Kept the regression pack on the existing focused backend and web suites instead of introducing a new acceptance harness.
  - Used the current admin export and manager-lite reminder surfaces as the regression boundary so future work extends the real chain instead of a parallel test-only path.
patterns_established:
  - Extend the current slice-owned contract/integration/page suites in place whenever the admin operating chain gains a new hop or action.
observability_surfaces:
  - Existing pytest/vitest suites plus explicit export/remind/drill-in assertions; no new runtime observability surface was added in this task.
duration: 55m
verification_result: passed
completed_at: 2026-03-27T09:20:37+08:00
blocker_discovered: false
---

# T01: Assemble the regression pack for the current admin operating chain

**Expanded the admin operating-chain regression pack to cover export, manager-lite reminder fallback, inactive-streak drill-ins, and richer intervention-result assertions on the shared evidence vocabulary.**

## What Happened

I verified the planned backend and web suites first, then tightened the pack instead of creating a new acceptance layer. On the backend side, I extended `backend/tests/contract/test_analytics.py` so the admin operating-pack contract now checks manager-list item shape and the current CSV export route, and I expanded `backend/tests/integration/test_admin_interventions_api.py` with the real manager-lite reminder path where `/admin/interventions/remind` runs without an explicit intervention id and must update the latest open focus. I also strengthened `backend/tests/integration/test_admin_users_api.py` so intervention-result payloads now assert their note and summary text, not just status transitions.

On the web side, I kept the regression vocabulary centered on the current admin routes. `web/src/app/admin/analytics/page.test.tsx` now proves two missing actions: exporting from the current analytics window and sending a manager-lite reminder from the weekly operating pack. `web/src/components/admin/manager-lite-panel.test.tsx` now covers the shared evidence-gap fallback note plus the inactive-streak drill-in path, and `web/src/app/admin/users/[id]/page.test.tsx` now verifies that an inactive-streak drill-in shows the right context without overwriting the supervisor note field.

## Verification

Fresh task-plan verification passed. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_analytics.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py` passed with 32 tests, including the new admin export contract and manager-lite reminder fallback integration case. `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` passed with 15 tests, including the new export-click, manager-lite reminder, fallback note, and inactive-streak drill-in assertions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_analytics.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py` | 0 | ✅ pass | 8010ms |
| 2 | `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass | 1820ms |

## Diagnostics

Re-run the two verification commands above to inspect this task later. For the manager-lite action path specifically, `backend/tests/integration/test_admin_interventions_api.py::test_manager_lite_remind_without_intervention_id_updates_latest_open_focus` is the narrowest proof. For the admin analytics route, `web/src/app/admin/analytics/page.test.tsx` now contains the explicit export and reminder interaction checks.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/tests/contract/test_analytics.py` — added export coverage and stronger operating-pack shape assertions.
- `backend/tests/integration/test_admin_users_api.py` — tightened intervention-result assertions to include note and summary text.
- `backend/tests/integration/test_admin_interventions_api.py` — aligned issue-family fixtures with the shared vocabulary and added the manager-lite reminder fallback integration case.
- `web/src/app/admin/analytics/page.test.tsx` — added export-click and manager-lite reminder interaction coverage for the current analytics route.
- `web/src/app/admin/users/[id]/page.test.tsx` — added inactive-streak drill-in context coverage.
- `web/src/components/admin/manager-lite-panel.test.tsx` — added fallback note and inactive-streak link assertions.
