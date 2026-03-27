# S05: 现有 admin 链路的组织化 UAT

**Goal:** Prove the current admin chain is sufficient for one real team management workflow, from analytics to drill-in to action to review.
**Demo:** After this: One real team workflow completes analytics → user drill-in → focus/reminder → report/replay review → weekly pack using the current admin surfaces.

## Tasks
- [x] **T01: Expanded the admin operating-chain regression pack to cover export, manager-lite reminder fallback, inactive-streak drill-ins, and richer intervention-result assertions on the shared evidence vocabulary.** — Assemble the regression pack for the current admin chain so analytics, users, interventions, manager-lite, and export stay on one evidence vocabulary. Reuse the focused backend/web suites created by earlier slices instead of a new acceptance framework.
  - Estimate: 75m
  - Files: backend/tests/contract/test_analytics.py, backend/tests/integration/test_admin_users_api.py, backend/tests/integration/test_admin_interventions_api.py, web/src/app/admin/analytics/page.test.tsx, web/src/app/admin/users/[id]/page.test.tsx, web/src/components/admin/manager-lite-panel.test.tsx
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_analytics.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py && cd ../web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
- [x] **T02: Captured a live admin analytics→drill-in→reminder→report/replay workflow on current routes and fixed the stale verification path blocking the gate.** — Run one real supervisor workflow using the current admin surfaces and capture the artifact trail: weekly/cycle view, user drill-in, focus or reminder action, and report/replay review on a resulting session. Keep the proof on current routes only.
  - Estimate: 90m
  - Files: .gsd/milestones/M005/slices/S05/S05-UAT.md
  - Verify: Manual review — file exists and is non-empty
- [ ] **T03: Write the final export and permission acceptance guardrails for M005** — Validate that the same current admin chain can produce an export/operating pack with the right permission boundary and evidence semantics, and write the final acceptance notes. This is the last guardrail before calling M005 operationally usable.
  - Estimate: 45m
  - Files: .gsd/milestones/M005/slices/S05/tasks/T03-PLAN.md
  - Verify: rg -n "export|permission|weekly|drill-in" .gsd/milestones/M005/slices/S05/tasks/T03-PLAN.md
