# S01: admin analytics / user drill-in 语义收口

**Goal:** Replace legacy weighted admin analytics semantics with the current projection/evidence line on the existing admin analytics and user drill-in routes.
**Demo:** After this: The current admin analytics and user drill-in routes no longer disagree with learner/supervisor evidence about scores, issue families, or evaluability.

## Tasks
- [x] **T01: Switched admin analytics and user stats to projection-backed session evidence summaries with evaluability metadata.** — Write focused failing tests around `backend/src/common/analytics/admin_analytics_service.py` and current admin analytics/user APIs, then replace legacy weighted-score calculations with projection-backed summaries sourced from `HistoryService` / `SessionEvidenceService`. Keep the current admin routes authoritative; do not create a second analytics pipeline.
  - Estimate: 2h
  - Files: backend/src/common/analytics/admin_analytics_service.py, backend/src/common/analytics/history_service.py, backend/src/admin/api/analytics.py, backend/src/admin/api/users.py, backend/tests/unit/common/test_admin_analytics_service.py, backend/tests/integration/test_admin_users_api.py, backend/tests/contract/test_analytics.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py
- [x] **T02: Reframed the existing admin analytics page around projection-backed evaluability, issue families, and next-goal evidence language.** — Update the current admin analytics page and related web types so the UI speaks the same semantics as learner/supervisor evidence: issue families, evaluability, degradation, and projection-backed score meaning. Remove placeholder or legacy wording from the existing analytics page instead of adding a new dashboard.
  - Estimate: 90m
  - Files: web/src/app/admin/analytics/page.tsx, web/src/lib/api/types.ts, web/src/lib/api/client.ts, web/src/app/admin/analytics/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'
- [x] **T03: Align admin drill-in and manager-lite copy with unified evidence score semantics.** — Align current manager-lite and user drill-in surfaces with the same admin truth line so reminder/report CTAs and supervisor summaries do not drift from analytics. Reuse the existing `ManagerLitePanel` and `/admin/users/[id]` page; add focused regressions rather than a new workflow surface.
  - Estimate: 75m
  - Files: web/src/components/admin/manager-lite-panel.tsx, web/src/components/admin/manager-lite-panel.test.tsx, web/src/app/admin/users/[id]/page.tsx, web/src/app/admin/users/[id]/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
