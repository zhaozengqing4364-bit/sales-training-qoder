# task-5-audit-015-020.md

RUN_ID: 20260213T134317Z

## AUDIT-015
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getOverview" "web/src/app/(dashboard)/support/runtime/page.tsx"; grep -n "/support/runtime/overview" "backend/src/support/api/runtime_status.py"`
- code_refs: web/src/app/(dashboard)/support/runtime/page.tsx, backend/src/support/api/runtime_status.py
- db_refs: system_logs, practice_sessions
- expected: Support runtime page filters and fault list map to read-only support runtime APIs.
- actual: Page requests overview/faults and backend defines matching endpoints with status/limit filters.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-016
- verdict: FAIL
- passes: false
- confidence: medium
- command: `grep -n "api.admin.getUsers" "web/src/app/admin/page.tsx"; grep -n "/overview" "backend/src/admin/api/analytics.py"`
- code_refs: web/src/app/admin/page.tsx, backend/src/admin/api/users.py, backend/src/admin/api/analytics.py, backend/src/admin/api/system_logs.py
- db_refs: users, system_logs, practice_sessions
- expected: Admin home cards map to user/log/analytics backend endpoints.
- actual: Admin homepage contains visible action buttons without concrete FE->API mapping for several actions; only part of entries are wired.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path
- unblock_condition: Bind each visible admin action button to an implemented backend endpoint or hide unsupported controls.

## AUDIT-017
- verdict: FAIL
- passes: false
- confidence: high
- command: `grep -n "createUser" "web/src/app/admin/users/page.tsx"; grep -n "/{user_id}/suspend" "backend/src/admin/api/users.py"`
- code_refs: web/src/app/admin/users/page.tsx, backend/src/admin/api/users.py
- db_refs: users
- expected: All user-management actions have unique API mapping and status persistence semantics.
- actual: Users page contract mismatch: frontend create payload omits required backend username and update path uses PATCH semantics against PUT route.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path
- unblock_condition: Align frontend payload/method with backend contract (`username` + PUT) and add integration assertion for create/update compatibility.

## AUDIT-018
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getUserStats" "web/src/app/admin/users/[id]/page.tsx"; grep -n "/{user_id}/progress" "backend/src/admin/api/users.py"`
- code_refs: web/src/app/admin/users/[id]/page.tsx, backend/src/admin/api/users.py
- db_refs: users, practice_sessions
- expected: User detail statistics/session/progress tabs map to backend endpoints with same filters.
- actual: Detail page requests stats/sessions/progress; backend exposes matching parameterized routes.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-019
- verdict: FAIL
- passes: false
- confidence: high
- command: `grep -n "getTrainingRecords" "web/src/app/admin/records/page.tsx"; grep -n "/admin/training-records" "backend/src/admin/api/training_records.py"`
- code_refs: web/src/app/admin/records/page.tsx, backend/src/admin/api/training_records.py
- db_refs: practice_sessions, scenarios, users
- expected: Records list/search/pagination/delete actions map to backend record endpoints.
- actual: Records page exposes export/advanced filter controls that are not backed by equivalent backend routes/query params.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path
- unblock_condition: Implement backend export/filter endpoints used by UI controls, or remove unsupported controls to match backend capability.

## AUDIT-020
- verdict: FAIL
- passes: false
- confidence: medium
- command: `grep -n "api.analytics.getOverview" "web/src/app/admin/analytics/page.tsx"; grep -n "/export" "backend/src/admin/api/analytics.py"`
- code_refs: web/src/app/admin/analytics/page.tsx, backend/src/admin/api/analytics.py
- db_refs: practice_sessions, users, leaderboard_entries
- expected: Analytics filters and export action map to backend analytics routes.
- actual: Analytics page applies global scenario filter, but backend support is partial across metrics endpoints, producing inconsistent filter behavior.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path
- unblock_condition: Standardize scenario filter support across overview/trends/agents/leaderboard/export or scope UI filter to supported endpoints only.

