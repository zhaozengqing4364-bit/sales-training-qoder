# S04: 团队周节奏包与 cohort 问题面

**Goal:** Generate a usable weekly operating pack and cohort issue view from the current admin analytics, manager workflow, and asset-governance data paths.
**Demo:** After this: A team lead can look at the current admin entrypoints and see issue buckets, risk lists, improving lists, and a one-week operating summary.

## Tasks
- [x] **T01: Add a projection-backed admin operating-pack API for weekly blocker, department, degradation, and manager-risk views.** — Extend the current admin analytics aggregation so it can produce cohort- and department-level issue buckets, repeated blocker families, degradation/not-evaluable breakdowns, and improving/risk lists on the same evidence line as learner and supervisor views.
  - Estimate: 2h
  - Files: backend/src/common/analytics/admin_analytics_service.py, backend/src/admin/api/analytics.py, backend/tests/unit/common/test_admin_analytics_service.py, backend/tests/contract/test_analytics.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/contract/test_analytics.py
- [x] **T02: Rendered the admin analytics weekly operating pack with projection-backed risk lists, blocker buckets, and department issue views.** — Render the weekly operating pack on the current admin analytics page using the new aggregation outputs. Keep the UI on the existing page and make it answer the practical questions: who is at risk, who is improving, what issue family repeats this week, and what changed in the asset layer.
  - Estimate: 90m
  - Files: web/src/app/admin/analytics/page.tsx, web/src/app/admin/analytics/page.test.tsx, web/src/lib/api/types.ts
  - Verify: cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'
- [x] **T03: Aligned admin users drill-ins with the weekly operating pack by preserving bucket and issue-family context through manager-lite, /admin/users, and /admin/users/[id].** — Keep the current users list/detail surfaces aligned with the new cohort operating view so managers can drill from a weekly bucket into specific users without losing the same evidence vocabulary. Reuse current admin users pages and focused tests.
  - Estimate: 75m
  - Files: web/src/app/admin/users/page.tsx, web/src/app/admin/users/[id]/page.tsx, web/src/app/admin/users/[id]/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'
