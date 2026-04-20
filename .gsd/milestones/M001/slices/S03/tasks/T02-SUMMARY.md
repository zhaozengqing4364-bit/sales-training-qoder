---
id: T02
parent: S03
milestone: M001
provides:
  - Projection-backed supervisor session previews plus direct report CTAs from admin user detail and manager-lite
key_files:
  - backend/src/admin/api/users.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/lib/api/types.ts
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
key_decisions:
  - Reused SessionEvidenceService.build_projection for completed admin session rows instead of preserving the legacy 0.4/0.3/0.3 weighted summary
patterns_established:
  - Any supervisor-facing completed-session preview must come from the same unified evidence projection as /practice/{sessionId}/report and link to that page directly
observability_surfaces:
  - backend `/api/v1/admin/users/{userId}/sessions` now exposes `overall_result`, `evaluable`, `not_evaluable_reason`, `main_issue`, `next_goal`, `feedback_summary`, and `suggestions`; admin page and manager-lite focused tests lock the CTA target
duration: 1h15m
verification_result: passed
completed_at: 2026-03-23T14:48:00+08:00
blocker_discovered: false
---

# T02: 把主管列表入口接到同一权威报告页

**Switched supervisor session previews to unified evidence and wired both admin entry points to the canonical report page.**

## What Happened

I first added failing coverage for the two missing contracts: backend admin session rows had to stop using the legacy 0.4/0.3/0.3 weighted summary for completed sessions, and both supervisor entry points had to expose a direct `查看报告` path to `/practice/{sessionId}/report`.

On the backend, I changed `backend/src/admin/api/users.py` so `get_user_sessions()` batch-loads conversation messages for the current completed-page slice and runs `SessionEvidenceService.build_projection(...)` per completed session. That switched completed rows onto the same evidence line already used by report/replay/history. The sessions payload now returns projection-backed `scores.overall`, `overall_result`, `evaluable`, `not_evaluable_reason`, `evidence_completeness`, `main_issue`, `next_goal`, `feedback_summary`, and `suggestions`. In-progress rows stay honest and keep those preview fields empty.

On the frontend, I extended `web/src/lib/api/types.ts` with the unified preview fields, updated `web/src/app/admin/users/[id]/page.tsx` to show verdict + preview text + next-goal copy in the sessions table, and rendered a completed-row `查看报告` CTA pointing straight at `/practice/{sessionId}/report`. I also updated `web/src/components/admin/manager-lite-panel.tsx` so each `not_passed` card now shows the same `查看报告` CTA next to the existing reminder action.

Finally, I added focused frontend specs for the admin detail page and manager-lite panel, recorded the projection choice in GSD decisions, and added one knowledge note so future agents do not regress to legacy supervisor summaries.

## Verification

I ran the task-level backend and frontend commands from the T02 plan and both passed. I also ran the slice-level automated backend and frontend commands; both passed as well.

I did **not** run the slice-level manual browser review or failure-path browser inspection in this timeout-constrained recovery window, so those human/UAT checks remain to be executed separately.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && pytest tests/integration/test_admin_users_api.py` | 0 | ✅ pass | 2.82s |
| 2 | `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass | 0.95s |
| 3 | `cd backend && pytest tests/contract/test_practice_evidence_contract.py tests/integration/test_admin_users_api.py` | 0 | ✅ pass | 3.19s |
| 4 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass | 0.95s |

## Diagnostics

- Inspect `GET /api/v1/admin/users/{userId}/sessions` and confirm completed rows expose `scores.overall`, `overall_result`, `evaluable`, `not_evaluable_reason`, `main_issue`, `next_goal`, `feedback_summary`, and `suggestions` from the unified projection.
- Re-run `cd backend && pytest tests/integration/test_admin_users_api.py` to catch any regression back to legacy weighted summaries.
- Re-run `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` to validate supervisor preview rendering and CTA wiring.
- In the UI, `admin/users/[id]` and `admin/analytics` should both deep-link completed failures to `/practice/{sessionId}/report`.

## Deviations

- I exposed `feedback_summary` and `suggestions` on admin session rows in addition to the task plan’s required preview fields, because the slice-level observability note explicitly asked for those surfaces to stay visible in supervisor payloads.
- I did not start a local web server or perform browser/UAT verification in this recovery window; only automated slice/task commands were executed.

## Known Issues

- Slice-level manual review for `/practice/<sessionId>/report`, `/admin/users/<id>`, and `/admin/analytics` is still pending.
- Slice-level failure-path browser inspection for an `evaluable=false` / incomplete-evidence session is still pending.

## Files Created/Modified

- `backend/src/admin/api/users.py` — switched completed session rows from legacy weighting to batched unified evidence projection and exposed preview fields
- `backend/tests/integration/test_admin_users_api.py` — locked the admin sessions contract to projection-backed preview fields and honest in-progress rows
- `web/src/lib/api/types.ts` — added unified supervisor preview fields to `UserSessionItem`
- `web/src/app/admin/users/[id]/page.tsx` — rendered unified preview copy and a completed-row `查看报告` CTA
- `web/src/app/admin/users/[id]/page.test.tsx` — focused test for admin detail preview rendering and report CTA wiring
- `web/src/components/admin/manager-lite-panel.tsx` — added direct report CTA to `not_passed` cards while preserving reminder action
- `web/src/components/admin/manager-lite-panel.test.tsx` — focused test for manager-lite report drill-in
- `.gsd/KNOWLEDGE.md` — recorded the non-obvious rule to batch project completed admin previews through `SessionEvidenceService.build_projection(...)`
- `.gsd/DECISIONS.md` — appended decision D018 about using one evidence line for supervisor previews and drill-ins
- `.gsd/milestones/M001/slices/S03/S03-PLAN.md` — marked T02 done
