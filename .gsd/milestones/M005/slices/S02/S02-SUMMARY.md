---
id: S02
parent: M005
milestone: M005
provides:
  - Persistent manager intervention records on the current admin API chain.
  - Manager-lite deep links into `/admin/users/[id]` with prefilled focus context.
  - Projection-backed `manager_intervention_results` on the existing admin user sessions surface plus canonical report drill-ins.
requires:
  - slice: S01
    provides: projection-backed admin analytics / user drill-in semantics and the unified completed-session evidence baseline
affects:
  - S04
  - S05
key_files:
  - backend/alembic/versions/20260326_1000_021_add_manager_interventions.py
  - backend/src/admin/api/interventions.py
  - backend/src/admin/api/users.py
  - backend/src/common/analytics/history_service.py
  - backend/src/common/db/models.py
  - backend/src/common/db/schemas.py
  - backend/tests/integration/test_admin_interventions_api.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/app/admin/users/page.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
key_decisions:
  - Use a dedicated `manager_interventions` table instead of stretching current admin routes into a generic task system.
  - Keep `/admin/users/[id]` as the single supervisor authority surface, with manager-lite acting as a launcher through focus query params.
  - Derive intervention results on the read side from `HistoryService` + `SessionEvidenceService` projections instead of mutating intervention rows during GET requests.
patterns_established:
  - Add minimal durable workflow state to current admin entrypoints before considering a second governance surface.
  - Use manager-lite as a launcher into the same authority page instead of duplicating form and state orchestration.
  - When supervisor outcomes depend on training facts, derive them from the same projection-backed evidence line as report/admin previews and prefer the latest evaluable completed session after intervention creation.
observability_surfaces:
  - `manager_intervention_created` structured log.
  - `manager_lite_reminder_logged` structured log.
  - `practice_history_projection_query` with `query_name="admin_user_intervention_results"`.
drill_down_paths:
  - .gsd/milestones/M005/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-26T08:14:57.702Z
blocker_discovered: false
---

# S02: 系统内主管重点与提醒闭环

**主管现在可以在现有 admin 用户链路里设训练重点、记录提醒，并在同一页看到后续训练是否已经改善该问题家族。**

## What Happened

This slice closed the smallest usable supervisor loop on the current admin surfaces instead of introducing a second governance console. The backend added a dedicated `manager_interventions` table plus create/list/patch/remind endpoints so supervisor focus, reminder state, due state, and optional resolving-session linkage persist on the existing admin API chain. The legacy remind entrypoint stayed compatible, but now updates persisted reminder state when an open intervention already exists.

On the web side, manager-lite stayed a launcher rather than becoming a second workflow surface. Its not-passed cards now deep-link into `/admin/users/[id]` with prefilled `focusIssueFamily` / `focusNote` query params, and the current user detail page now owns the create/remind/read loop: supervisors can set a focus, inspect existing interventions, record a reminder, and drill into the canonical report for the linked resulting session.

Result linkage was kept on the read side. `HistoryService.build_manager_intervention_results(...)` derives the latest supervisor outcome from persisted interventions plus completed-session projections and prefers the latest evaluable completed session after intervention creation. That keeps the intervention card on the same evidence line as learner/report/admin previews, avoids GET-time mutation, and prevents a later thin `INSUFFICIENT_TURN_DATA` session from erasing a real earlier improvement.

## Verification

Fresh slice-close verification reran all planned task checks and the schema path: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py` passed 3/3 tests; `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` passed 2/2 test files and 7/7 tests; `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py` passed 15/15 tests; and `cd backend && /usr/bin/time -p venv/bin/alembic upgrade head` succeeded on the local backend database.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Reminder actions currently record in-product reminder lifecycle state only; they do not deliver an external notification. The detail page shows the latest meaningful resulting session but does not auto-resolve interventions or provide a bulk team-level queue. Team/cohort operating views remain future slice work.

## Follow-ups

S04 should aggregate these intervention results into team/cohort views instead of leaving them only on individual user detail pages. If the product later needs real delivery, the current remind action should fan out to an external notification channel while `manager_interventions` remains the source of truth.

## Files Created/Modified

- `backend/alembic/versions/20260326_1000_021_add_manager_interventions.py` — Added the `manager_interventions` migration and constraints/indexes for supervisor focus persistence.
- `backend/src/common/db/models.py` — Added the `ManagerIntervention` SQLAlchemy model.
- `backend/src/common/db/schemas.py` — Added manager intervention enums and request/response schemas.
- `backend/src/admin/api/interventions.py` — Implemented create/list/update/remind endpoints on the existing admin intervention chain.
- `backend/src/common/analytics/history_service.py` — Derived intervention-result summaries from persisted interventions plus unified session-evidence projections.
- `backend/src/admin/api/users.py` — Exposed `manager_intervention_results` on the existing admin user sessions read surface.
- `web/src/components/admin/manager-lite-panel.tsx` — Turned manager-lite into a launcher with unified-report links, deep links into user detail, and reminder actions.
- `web/src/app/admin/users/[id]/page.tsx` — Added the supervisor intervention form, intervention cards, reminder actions, and linked-result/report UI on the current detail page.
- `web/src/app/admin/users/page.tsx` — Updated current users-page copy so the supervisor-focus path is explicit on the existing entrypoint.
- `backend/tests/integration/test_admin_interventions_api.py` — Covered intervention persistence, remind lifecycle updates, and resolving-session linkage.
- `backend/tests/integration/test_admin_users_api.py` — Covered projection-backed admin sessions/progress plus intervention-result linkage.
- `web/src/app/admin/users/[id]/page.test.tsx` — Covered create/remind/result UX and current detail-page inline states.
- `web/src/components/admin/manager-lite-panel.test.tsx` — Covered manager-lite evidence wording, report links, and user-detail deep-link launcher behavior.
