---
id: S05
parent: M005
milestone: M005
provides:
  - A repo-root-safe regression pack that protects export, manager-lite reminder fallback, inactive-streak drill-ins, and intervention-result review on the current admin chain.
  - A live current-route proof that the weekly operating pack can drive user drill-in, supervisor reminder/focus action, and canonical report/replay review for one real team workflow.
  - Final M005 guardrails that keep export, weekly-pack semantics, and admin-only permission boundaries on the shipped `/admin/analytics*` route family.
requires:
  - slice: S02
    provides: Persisted manager intervention create/remind/result semantics on the current admin user-detail and sessions read surfaces.
  - slice: S04
    provides: Weekly operating-pack aggregation plus `focusBucket` / `focusIssueFamily` drill-ins on the current analytics and users surfaces.
affects:
  []
key_files:
  - backend/tests/contract/test_analytics.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/integration/test_admin_interventions_api.py
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
  - .gsd/milestones/M005/slices/S05/S05-UAT.md
  - .gsd/milestones/M005/slices/S05/tasks/T03-PLAN.md
  - .gsd/PROJECT.md
key_decisions:
  - Use the existing focused backend/web suites as the S05 regression pack and extend them in place instead of creating a second acceptance framework.
  - Keep the live proof on the shipped admin and canonical learner routes (`/admin/analytics` → `/admin/users/{id}` → `/practice/{sessionId}/report|replay`) rather than introducing a UAT-only workflow.
  - Treat the current admin analytics export surface and the admin-only router dependency in `backend/src/main.py` as the final operational guardrails for the weekly operating chain.
patterns_established:
  - Treat slice-close UAT as an extension of the existing focused backend/web suites plus one current-route live workflow, not as a new acceptance framework.
  - Keep admin operating-chain proof on the shipped route family (`/admin/analytics` → `/admin/users/{id}` → canonical report/replay) so export, permissions, and evidence semantics stay coupled.
  - When verification commands change to repo-root-safe forms, refresh the corresponding `T##-VERIFY.json` artifacts as part of the fix so auto-mode does not keep replaying stale failures.
observability_surfaces:
  - `GET /api/v1/admin/analytics/operating-pack` returns the weekly summary, `score_basis`, blocker families, department buckets, and manager lists on the same evidence line as the rest of the admin chain.
  - `GET /api/v1/admin/analytics/export` keeps the CSV operating pack on the shipped analytics route family instead of a separate admin-export surface.
  - `GET /api/v1/admin/users/{id}/sessions` plus the current user-detail page expose persisted intervention results and canonical report drill-ins for the resolving session.
  - Canonical `/practice/{sessionId}/report` and `/api/v1/sessions/{id}/replay` stay the review surfaces for the resulting session, with optional enhanced-report/highlights failures degrading explicitly instead of replacing the unified evidence route.
drill_down_paths:
  - .gsd/milestones/M005/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S05/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T02:02:44.979Z
blocker_discovered: false
---

# S05: 现有 admin 链路的组织化 UAT

**Verified that the shipped admin weekly operating chain can carry one real supervisor workflow from analytics through reminder and canonical report/replay review, with export/RBAC guardrails and a repo-root-safe regression pack.**

## What Happened

This slice did not build a new acceptance surface. Instead, it proved that the admin operating chain assembled across S01-S04 is already sufficient for one real team-management workflow on the routes the product currently ships.

T01 tightened the regression boundary around that chain. The backend contract and integration suites now cover the admin export route, projection-backed user sessions/results, persisted reminder fallback, and resolving-session linkage. The web focused tests now cover the analytics-page export action, manager-lite reminder fallback, inactive-streak drill-ins, carried weekly context on `/admin/users/[id]`, and richer intervention-result assertions. That matters because S05's job was not to invent new manager behavior; it was to prove that analytics, drill-in, reminder, and review all still speak one shared evidence vocabulary after the earlier slices.

T02 then captured the live workflow on current routes only: a team lead starts on `/admin/analytics`, uses the weekly operating pack to identify a current-risk member, drills into `/admin/users/{id}` with the carried `focusBucket` / `focusIssueFamily` context, confirms or sends the reminder/focus action on the current user-detail surface, and then reviews the resulting session on the canonical `/practice/{sessionId}/report` and `/practice/{sessionId}/replay` pages. The important slice outcome is that the workflow stays on shipped product surfaces end to end. The acceptance proof does not depend on a second console, a hidden admin-only report page, or a new one-off test harness.

T03 wrote the final guardrails around that live proof. The export surface remains `GET /api/v1/admin/analytics/export` on the same route family as the weekly operating pack, and `backend/src/main.py` continues to enforce the admin-only permission boundary for both `/api/v1/admin/analytics/operating-pack` and `/api/v1/admin/analytics/export`. The weekly pack itself keeps the `session_evidence_projection_evaluable_only` score basis and the same drill-in semantics proven in S04, so export, analytics, manager-lite, user detail, report, and replay all remain coupled to one evidence line.

This closer turn also repaired the stale task-level VERIFY artifacts that still recorded earlier auto-discovery failures (`cd ../web`, package-json fallback checks). With repo-root-safe regression commands re-run and the verifier artifacts rewritten to match the passing checks, downstream auto-mode consumers now see the same truthful state that the slice summary records.

### Operational Readiness (Q8)

- **Health signal:** the repo-root-safe backend regression pack passes on the current analytics/users/interventions routes; the focused web pack passes on the current analytics, manager-lite, and user-detail surfaces; `/admin/analytics` still exposes both the weekly operating pack and CSV export on the same route family; `/admin/users/[id]` still shows persisted intervention results with canonical report drill-ins; and the report/replay review path remains usable even when optional enhanced-report or highlights requests degrade.
- **Failure signal:** the export affordance disappears or stops forwarding the selected time range, a non-admin can reach `/api/v1/admin/analytics/export` or `/operating-pack`, weekly drill-ins lose `focusBucket` / `focusIssueFamily` and fall back to generic evidence-gap copy, or canonical `/practice/{sessionId}/report` / replay review becomes unreadable because the core evidence route fails rather than only optional enhancement calls falling back.
- **Recovery procedure:** rerun the S05 regression pack from repo root; inspect `backend/src/main.py` router dependencies plus `backend/src/admin/api/analytics.py` for export/operating-pack ownership; confirm query-param context is still carried from analytics/manager-lite/users into `/admin/users/[id]`; and verify the latest resolving session still opens on the canonical report/replay routes with explicit fallback copy if optional enhancement endpoints fail.
- **Monitoring gaps:** there is no dedicated structured metric yet for CSV export usage or reminder→review completion, intervention-result cards still expose a raw issue-family key, and browser console/network noise from optional enhanced-report/highlights failures can obscure the difference between non-blocking degradation and a true canonical-route regression during manual UAT.

## Verification

Fresh slice-close verification passed:
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/integration/test_admin_users_api.py backend/tests/integration/test_admin_interventions_api.py` → 32 passed. Verified current admin analytics export/operating-pack contract coverage, projection-backed user drill-ins, persisted reminder fallback, and resolving-session linkage.
- `npm --prefix web test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` → 15 passed across 3 files. Verified export click behavior, manager-lite reminder fallback, carried weekly context, inactive-streak drill-ins, reminder/result rendering, and review links on the shipped admin pages.
- `test -s .gsd/milestones/M005/slices/S05/S05-UAT.md` → passed. Confirmed the slice UAT artifact exists and is non-empty.
- `rg -n "export|permission|weekly|drill-in" .gsd/milestones/M005/slices/S05/tasks/T03-PLAN.md` → passed. Confirmed the final acceptance note explicitly covers export, permission, weekly-pack semantics, and drill-in continuity.
- LSP diagnostics returned no issues for `web/src/app/admin/analytics/page.tsx`, `web/src/components/admin/manager-lite-panel.tsx`, `backend/src/admin/api/analytics.py`, and `backend/src/main.py`.

Carried slice evidence from T02 remains the live proof boundary for this slice: the current shipped route family has already been exercised through `/admin/analytics` → `/admin/users/{id}` → reminder/focus action → canonical report/replay review, and this closer turn preserved that proof while re-running the full slice verification set.

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

- This slice proves one representative supervisor workflow on the current shipped admin surfaces; it does not yet measure multi-manager concurrency or long-running production adoption metrics.
- Persisted intervention-result cards still surface the raw issue-family key, which is truthful but less polished than the manager-facing copy elsewhere in the chain.
- Optional enhanced-report/highlights requests can still emit 404/500 fallback noise while the canonical report/replay routes remain usable; operators must distinguish that non-blocking noise from a core evidence-route failure.

## Follow-ups

- Roadmap reassessment / milestone close-out should decide whether the raw issue-family key on intervention-result cards needs a UX translation pass or can remain a documented non-blocking detail.
- If admin operations need stronger runtime monitoring, add explicit instrumentation for CSV export usage and reminder→report/replay completion instead of inferring them only from manual UAT and browser logs.

## Files Created/Modified

- `backend/tests/contract/test_analytics.py` — Expanded the current admin analytics contract pack to guard the shipped export route, operating-pack semantics, and the admin-only analytics evidence vocabulary.
- `backend/tests/integration/test_admin_users_api.py` — Extended admin user-detail integration coverage for projection-backed drill-ins, intervention results, and canonical report-review links on the current sessions read path.
- `backend/tests/integration/test_admin_interventions_api.py` — Locked persisted manager reminder fallback, open-intervention updates, and resolving-session linkage on the current admin intervention APIs.
- `web/src/app/admin/analytics/page.test.tsx` — Guarded the current analytics page's weekly operating-pack UI, export click behavior, and shared score-basis wording on shipped routes.
- `web/src/app/admin/users/[id]/page.test.tsx` — Guarded carried weekly drill-in context, reminder/result rendering, inactive-streak handling, and canonical report/replay review entrypoints on the current user detail page.
- `web/src/components/admin/manager-lite-panel.test.tsx` — Guarded manager-lite reminder fallback and context-preserving drill-ins into the existing user-detail workflow.
- `.gsd/milestones/M005/slices/S05/S05-UAT.md` — Captured the live admin analytics → drill-in → reminder → report/replay workflow and now records the final tailored slice UAT cases.
- `.gsd/milestones/M005/slices/S05/tasks/T03-PLAN.md` — Codified the final export, permission, and weekly-pack acceptance guardrails for the current admin chain.
- `.gsd/milestones/M005/slices/S05/tasks/T01-VERIFY.json` — Refreshed the stale task verifier artifact with repo-root-safe backend and web regression passes.
- `.gsd/milestones/M005/slices/S05/tasks/T02-VERIFY.json` — Refreshed the manual UAT verifier artifact so auto-mode sees the slice UAT evidence file as passing instead of reusing the stale package.json failure.
- `.gsd/milestones/M005/slices/S05/tasks/T03-VERIFY.json` — Refreshed the guardrail verifier artifact so auto-mode records the export/permission acceptance-note check as passing.
- `.gsd/PROJECT.md` — Updated project state to reflect that M005 now has S05's organized admin-chain UAT proof on the shipped surfaces.
