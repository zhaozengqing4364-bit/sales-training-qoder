# S01: admin analytics / user drill-in 语义收口

**Goal:** Replace legacy weighted admin analytics semantics with the current projection/evidence line on the existing admin analytics and user drill-in routes.
**Demo:** The current admin analytics and user drill-in routes no longer disagree with learner/supervisor evidence about scores, issue families, or evaluability.

## Must-Haves

- Current admin analytics, user detail, and manager-lite surfaces share one projection-backed business semantic line and stop surfacing legacy 0.4/0.3/0.3 score truth or placeholder language.

## Proof Level

- This slice proves: integration

## Integration Closure

Reuse `backend/src/common/analytics/admin_analytics_service.py`, `backend/src/common/analytics/history_service.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/admin/api/analytics.py`, `backend/src/admin/api/users.py`, `web/src/app/admin/analytics/page.tsx`, `web/src/app/admin/users/[id]/page.tsx`, and `web/src/components/admin/manager-lite-panel.tsx`. No new admin console, no external integration scope.

## Verification

- Focused backend analytics tests, admin users integration tests, admin analytics page tests, and manager-lite tests become the drift detectors for admin semantics; placeholder or legacy score regressions become visible immediately.

## Tasks

- [ ] **T01: Replace legacy admin analytics math with projection-backed business summaries** `est:2h`
  Write focused failing tests around `backend/src/common/analytics/admin_analytics_service.py` and current admin analytics/user APIs, then replace legacy weighted-score calculations with projection-backed summaries sourced from `HistoryService` / `SessionEvidenceService`. Keep the current admin routes authoritative; do not create a second analytics pipeline.
  - Files: `backend/src/common/analytics/admin_analytics_service.py`, `backend/src/common/analytics/history_service.py`, `backend/src/admin/api/analytics.py`, `backend/src/admin/api/users.py`, `backend/tests/unit/common/test_admin_analytics_service.py`, `backend/tests/integration/test_admin_users_api.py`, `backend/tests/contract/test_analytics.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py

- [ ] **T02: Make the existing admin analytics page speak the current evidence language** `est:90m`
  Update the current admin analytics page and related web types so the UI speaks the same semantics as learner/supervisor evidence: issue families, evaluability, degradation, and projection-backed score meaning. Remove placeholder or legacy wording from the existing analytics page instead of adding a new dashboard.
  - Files: `web/src/app/admin/analytics/page.tsx`, `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/app/admin/analytics/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'

- [ ] **T03: Keep manager-lite and user drill-in aligned with the corrected admin truth line** `est:75m`
  Align current manager-lite and user drill-in surfaces with the same admin truth line so reminder/report CTAs and supervisor summaries do not drift from analytics. Reuse the existing `ManagerLitePanel` and `/admin/users/[id]` page; add focused regressions rather than a new workflow surface.
  - Files: `web/src/components/admin/manager-lite-panel.tsx`, `web/src/components/admin/manager-lite-panel.test.tsx`, `web/src/app/admin/users/[id]/page.tsx`, `web/src/app/admin/users/[id]/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'

## Files Likely Touched

- backend/src/common/analytics/admin_analytics_service.py
- backend/src/common/analytics/history_service.py
- backend/src/admin/api/analytics.py
- backend/src/admin/api/users.py
- backend/tests/unit/common/test_admin_analytics_service.py
- backend/tests/integration/test_admin_users_api.py
- backend/tests/contract/test_analytics.py
- web/src/app/admin/analytics/page.tsx
- web/src/lib/api/types.ts
- web/src/lib/api/client.ts
- web/src/app/admin/analytics/page.test.tsx
- web/src/components/admin/manager-lite-panel.tsx
- web/src/components/admin/manager-lite-panel.test.tsx
- web/src/app/admin/users/[id]/page.tsx
- web/src/app/admin/users/[id]/page.test.tsx
