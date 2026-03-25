# S04: 团队周节奏包与 cohort 问题面

**Goal:** Generate a usable weekly operating pack and cohort issue view from the current admin analytics, manager workflow, and asset-governance data paths.
**Demo:** A team lead can look at the current admin entrypoints and see issue buckets, risk lists, improving lists, and a one-week operating summary.

## Must-Haves

- A team lead can use the current admin entrypoints to see issue buckets, risk lists, improving lists, and a one-week operating summary without reconstructing the view manually from spreadsheets.

## Proof Level

- This slice proves: integration

## Integration Closure

Stay on the current admin analytics/users surfaces and export path: `backend/src/admin/api/analytics.py`, `backend/src/admin/api/users.py`, `backend/src/common/analytics/admin_analytics_service.py`, `backend/src/common/analytics/history_service.py`, `web/src/app/admin/analytics/page.tsx`, and `web/src/app/admin/users/page.tsx`. No new BI layer.

## Verification

- Weekly operating packs, cohort issue buckets, and export payloads become regression-tested outputs on current admin routes; drift from the evidence line or asset context becomes visible in analytics tests.

## Tasks

- [ ] **T01: Add cohort issue buckets and weekly operating summaries to current analytics APIs** `est:2h`
  Extend the current admin analytics aggregation so it can produce cohort- and department-level issue buckets, repeated blocker families, degradation/not-evaluable breakdowns, and improving/risk lists on the same evidence line as learner and supervisor views.
  - Files: `backend/src/common/analytics/admin_analytics_service.py`, `backend/src/admin/api/analytics.py`, `backend/tests/unit/common/test_admin_analytics_service.py`, `backend/tests/contract/test_analytics.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/contract/test_analytics.py

- [ ] **T02: Render the weekly operating pack on the existing admin analytics route** `est:90m`
  Render the weekly operating pack on the current admin analytics page using the new aggregation outputs. Keep the UI on the existing page and make it answer the practical questions: who is at risk, who is improving, what issue family repeats this week, and what changed in the asset layer.
  - Files: `web/src/app/admin/analytics/page.tsx`, `web/src/app/admin/analytics/page.test.tsx`, `web/src/lib/api/types.ts`
  - Verify: cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'

- [ ] **T03: Let current admin users surfaces drill into the weekly operating buckets** `est:75m`
  Keep the current users list/detail surfaces aligned with the new cohort operating view so managers can drill from a weekly bucket into specific users without losing the same evidence vocabulary. Reuse current admin users pages and focused tests.
  - Files: `web/src/app/admin/users/page.tsx`, `web/src/app/admin/users/[id]/page.tsx`, `web/src/app/admin/users/[id]/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'

## Files Likely Touched

- backend/src/common/analytics/admin_analytics_service.py
- backend/src/admin/api/analytics.py
- backend/tests/unit/common/test_admin_analytics_service.py
- backend/tests/contract/test_analytics.py
- web/src/app/admin/analytics/page.tsx
- web/src/app/admin/analytics/page.test.tsx
- web/src/lib/api/types.ts
- web/src/app/admin/users/page.tsx
- web/src/app/admin/users/[id]/page.tsx
- web/src/app/admin/users/[id]/page.test.tsx
