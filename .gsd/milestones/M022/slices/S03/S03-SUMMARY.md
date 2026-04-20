---
id: S03
parent: M022
milestone: M022
provides:
  - A single honest manager/admin truth-surface boundary for downstream roadmap work.
  - An admin home that no longer mixes live effectiveness stats with fake ops metrics.
  - Durable documentation and knowledge guardrails preventing future manager-only local rollups or fake homepage summaries.
requires:
  - slice: S01
    provides: methodology-aware rubric semantics that manager/admin surfaces must reuse instead of inventing a second sales taxonomy.
  - slice: S02
    provides: runtime-binding / composed-asset provenance that downstream manager/admin planning should reuse for truth explanations.
affects:
  - S04
key_files:
  - web/src/app/admin/page.tsx
  - web/src/app/admin/page.test.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/admin/api/users.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D246 — Keep only the admin-home effectiveness card on live authority and downgrade the remaining admin-home ops cards to inventory; reuse admin analytics, manager-lite, and admin user detail/interventions as the current P0 manager/admin truth surfaces.
  - D247 — Treat manager-lite, admin analytics, and admin user detail/interventions as the only currently productized manager/admin truth surfaces; keep admin-home inventory cards and standalone calibration/coaching workspaces documented as future/inventory-only surfaces.
patterns_established:
  - Downgrade fake surfaces instead of fake-connecting them to invented stats.
  - Treat existing projection-backed manager-lite, admin analytics, and admin user detail surfaces as the reusable manager/admin truth seam.
  - Update product docs and architecture artifacts in the same change that redraws a management-surface boundary so roadmap language cannot get ahead of shipped evidence.
observability_surfaces:
  - The admin home now exposes an explicit truth-surface boundary instead of mixed live/demo operator copy.
  - Manager/admin analytics verification is locked to the projection-backed `test_admin_analytics_service.py` proof rather than homepage-only visual numbers.
drill_down_paths:
  - .gsd/milestones/M022/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M022/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M022/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T08:17:33.374Z
blocker_discovered: false
---

# S03: Manager calibration 与 admin truth surfaces 收口

**Manager/admin decision surfaces now use one honest truth line: admin home is downgraded to an inventory shell outside the live effectiveness card, while manager-lite, admin analytics, and admin user detail/interventions are the only productized manager/admin evidence surfaces.**

## What Happened

S03 closed the manager/admin trust gap by removing the remaining fake operator story from the admin home and explicitly re-centering supervisor decisions on existing projection-backed evidence surfaces. T01 converted `/admin` into an honesty-first boundary: the top effectiveness card still reads real `internal.health` + `analyticsOpen.getDashboard` data, while the former hardcoded user/session/resource/storage cards were downgraded to inventory copy instead of pretending to be live stats. T02 completed that cleanup by removing the remaining faux announcement/config/log/alert/activity blocks and leaving the homepage as a truthful launcher into the real surfaces rather than a second drifting dashboard. The real supervisor surfaces are now locked to `/admin/analytics` (team summary, trends, degraded breakdown, runtime faults, manager-lite), `ManagerLitePanel` (not passed / trend / follow-up triage), and `/admin/users/[id]` (single-user progress, session evidence, interventions). T03 then wrote that same product boundary into the architecture scan and post-M018 plan so roadmap work, docs, and future implementation cannot over-claim placeholder cards or standalone calibration shells as shipped capabilities. Across the slice, learner/manager/admin now read the same training-fact authority line: manager/admin surfaces are expected to reuse canonical evidence and projection-backed analytics rather than inventing manager-only rollups or homepage-only numbers.

## Verification

Fresh slice-close verification reran the exact web and backend proof bundle and it all passed. `npm --prefix web test -- --run "src/app/admin/page.test.tsx" "src/components/admin/manager-lite-panel.test.tsx"` passed 3/3 tests, confirming the admin home only keeps the real effectiveness card live and that manager-lite still points supervisors into current user-detail evidence surfaces. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py -x -q` passed 5/5 tests, confirming not-passed/trend/calibration-adjacent analytics payloads still stay on the projection-backed evidence line. `rg -n "manager|calibration|truth surface|fake stats|placeholder|canonical evidence" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md` passed, proving the durable planning artifacts now encode the same productized-vs-inventory boundary. LSP diagnostics on `web/src/app/admin/page.tsx`, `web/src/app/admin/page.test.tsx`, `web/src/components/admin/manager-lite-panel.tsx`, `backend/src/admin/api/users.py`, `backend/src/common/analytics/admin_analytics_service.py`, and `backend/tests/unit/common/test_admin_analytics_service.py` were clean. Browser automation in this harness remains blocked by a missing Playwright Chromium binary, so runtime UI proof for the slice is currently carried by the focused web tests plus the concrete UAT script below rather than a recorded localhost browser run.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None in shipped scope. The only execution limitation was that browser automation could not be recorded in this harness because the Playwright Chromium binary is missing; slice acceptance therefore relies on the fresh focused web/backend proof and the concrete UAT script rather than a stored localhost browser session.

## Known Limitations

Standalone manager calibration workspaces and a full team coaching cockpit are still future work. The admin home intentionally no longer acts like a complete live operations dashboard; beyond the effectiveness card, inventory sections remain downgraded until a real backend authority exists for them.

## Follow-ups

S04 should plan organization/team/tenant target-state work on top of the locked S03 boundary instead of reopening manager/admin truth semantics. Any future attempt to restore admin-home stats, alerts, activity, or dedicated calibration workspaces must first connect them to a real backend authority and update the focused proof plus docs in the same change.

## Files Created/Modified

- `web/src/app/admin/page.tsx` — Removed fake admin-home metrics and faux operator sections, leaving only the live effectiveness card plus inventory/link copy.
- `web/src/app/admin/page.test.tsx` — Added and extended focused proof that the admin home keeps only the real effectiveness card live and does not regress fake stats/actions.
- `web/src/components/admin/manager-lite-panel.tsx` — Retained the manager-lite truth seam that links supervisors into current user-detail evidence surfaces.
- `backend/src/common/analytics/admin_analytics_service.py` — Confirmed the existing projection-backed team-summary / manager-lite analytics contract remains the real backend authority.
- `backend/src/admin/api/users.py` — Confirmed user-detail/intervention read-side remains part of the real supervisor evidence seam.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Documented the productized-vs-inventory manager/admin truth-surface boundary and the locked entry points.
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` — Mirrored the same S03 truth-surface boundary into the durable plan so future roadmap work cannot over-claim shipped scope.
- `.gsd/KNOWLEDGE.md` — Captured the guardrail against reintroducing homepage-only manager rollups or fake stats.
- `.gsd/PROJECT.md` — Refreshed project state so M022/S03 is marked complete and S04 is the active next focus.
