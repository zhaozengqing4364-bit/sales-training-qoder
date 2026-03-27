---
id: S04
parent: M005
milestone: M005
provides:
  - A projection-backed `/api/v1/admin/analytics/operating-pack` contract for weekly cohort blocker buckets, department issue summaries, degradation breakdowns, and manager lists.
  - A fixed-cadence weekly operating-pack panel on `/admin/analytics` that coexists with the broader analytics filters without changing their meaning.
  - One shared admin drill-in contract (`focusBucket` + `focusIssueFamily` + `focusNote`) from weekly pack/manager-lite/users list into `/admin/users/[id]`.
requires:
  - slice: S02
    provides: Manager intervention persistence plus projection-backed result semantics on current admin user detail/session surfaces.
  - slice: S03
    provides: Governance/runtime fault context already rendered on analytics and user-detail pages, so the weekly pack can sit on the current admin entrypoints instead of a new console.
affects:
  - S05
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/admin/api/analytics.py
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/contract/test_analytics.py
  - web/src/lib/api/types.ts
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
key_decisions:
  - Derive blocker families through `HistoryService` issue-family normalization and decide current not-passed risk membership from each user’s latest evaluable completed session, not any failure in the window.
  - Keep the weekly operating pack on its own fixed 7-day read model while leaving overview/trends/leaderboard on the user-selected analytics range.
  - Preserve weekly drill-in meaning across admin analytics, manager-lite, users list, and user detail with explicit `focusBucket` + `focusIssueFamily` + `focusNote` query params.
patterns_established:
  - Projection-backed weekly aggregation can live beside broader analytics filters if the weekly pack is treated as its own fixed-cadence read model.
  - Current risk and improvement lists stay trustworthy when they are anchored to the latest evaluable completed session per user rather than historical failures anywhere in the window.
  - Cross-page admin drill-ins remain aligned when context is carried explicitly in query params instead of being reconstructed heuristically on the destination page.
observability_surfaces:
  - `GET /api/v1/admin/analytics/operating-pack` returns `score_basis`, `weekly_summary`, cohort/department buckets, degradation breakdowns, and manager lists on the same evidence line.
  - Structured backend log `admin_operating_pack_calculated` records time range, scenario type, bucket counts, manager-list counts, and score basis for weekly-pack calculations.
  - `/admin/analytics` shows explicit projection score-basis copy plus visible evidence-insufficient/degraded-reason breakdowns inside the weekly operating pack.
  - `/admin/users/[id]` shows the weekly-source banner and prefilled intervention context derived from `focusBucket` / `focusIssueFamily` / `focusNote`.
drill_down_paths:
  - .gsd/milestones/M005/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-26T14:23:40.718Z
blocker_discovered: false
---

# S04: 团队周节奏包与 cohort 问题面

**Projection-backed weekly operating packs now expose cohort blocker buckets, department issue views, and context-preserving drill-ins across the current admin analytics and user surfaces.**

## What Happened

This slice turned the M005 admin evidence line into a fixed-cadence weekly operating view without creating a second admin console. On the backend, `AdminAnalyticsService` now builds a dedicated operating-pack payload from the same projection records used by history/report/replay. It normalizes blocker families through `HistoryService.resolve_summary_issue_family(...)`, splits out not-evaluable and degraded reasons, computes department-level issue buckets, and derives three manager lists from the projection line: current-risk members, inactive members, and improving members.

The risk logic is intentionally tied to each user’s latest evaluable completed session instead of “any failure in the window”. That keeps the weekly pack aligned with the supervisor/intervention facts introduced in S02: recovering users fall out of the current-risk list once their latest meaningful session passes, and evidence-insufficient sessions stay visible as their own bucket instead of polluting score averages.

The backend then exposes that read model through `GET /api/v1/admin/analytics/operating-pack`, plus a structured `admin_operating_pack_calculated` log that records bucket/list counts and score basis. Contract coverage now guards the operating-pack response shape end to end.

On the frontend, the current `/admin/analytics` page now renders a fixed 7-day operating pack alongside the existing broader analytics filters. The weekly pack answers the practical operating questions on the same page: how many completed/evaluable/not-evaluable/degraded sessions happened this week, what blocker family is repeating, which departments are clustering around which issue families, who is currently at risk, who has gone inactive, and who is improving. The UI also keeps the projection score-basis copy explicit so evidence-insufficient sessions are visibly accounted for but not silently mixed into averages.

Finally, the slice preserved that weekly vocabulary through drill-ins instead of forcing managers to reconstruct context by hand. `ManagerLitePanel`, `/admin/users`, and `/admin/users/[id]` now share a `focusBucket` + `focusIssueFamily` + `focusNote` query contract. Current-risk drill-ins keep the real issue family; inactive/improving drill-ins keep their own bucket identity; and the user detail page shows a visible "本周经营名单来源" banner plus prefilled supervisor focus text so a team lead can move from the weekly pack into a concrete member workflow without losing the same evidence language.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/contract/test_analytics.py` → 15 passed. Verified projection-backed operating-pack aggregation, latest-evaluable risk membership, department issue buckets, degradation/not-evaluable breakdowns, and `/api/v1/admin/analytics/operating-pack` contract coverage.
- `pnpm --dir web exec vitest run 'src/app/admin/analytics/page.test.tsx'` → 3 passed. Verified weekly operating-pack rendering, fixed 7-day summary copy, cohort/department buckets, projection score-basis messaging, and manager-list integration on the existing analytics page.
- `pnpm --dir web exec vitest run 'src/app/admin/users/[id]/page.test.tsx'` → 7 passed. Verified weekly drill-in source banner, preserved issue-family context, prefilled supervisor note/focus state, persisted intervention result cards, reminder flow, and unified report drill-ins.
- LSP diagnostics returned no issues for `backend/src/common/analytics/admin_analytics_service.py`, `backend/src/admin/api/analytics.py`, `web/src/app/admin/analytics/page.tsx`, `web/src/app/admin/users/page.tsx`, and `web/src/app/admin/users/*/page.tsx`.

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

- The weekly operating pack is intentionally fixed to a 7-day cadence even when the broader analytics page is filtered to 30/90/all-time; downstream work should treat it as a separate operating view, not a generic date-range report.
- This slice proves the read-side contract and current-page drill-in behavior, but it does not yet prove one full organization workflow from weekly pack → user drill-in → intervention/result review under live admin usage; S05 still owns that end-to-end UAT.

## Follow-ups

- S05 should run a real admin workflow that starts from the weekly operating pack, drills into a current-risk member, checks the unified report and intervention result, and confirms the same vocabulary survives the full supervisor loop.
- If future work adds new weekly bucket kinds, extend the shared `focusBucket` / `focusIssueFamily` drill contract across analytics, manager-lite, users list, and user detail together so the source banner and prefill logic do not drift.

## Files Created/Modified

- `backend/src/common/analytics/admin_analytics_service.py` — Added projection-backed operating-pack aggregation, latest-evaluable current-risk logic, department issue buckets, degradation breakdowns, and structured weekly-pack logging.
- `backend/src/admin/api/analytics.py` — Exposed `GET /api/v1/admin/analytics/operating-pack` for the weekly cohort operating pack contract.
- `backend/tests/unit/common/test_admin_analytics_service.py` — Added focused service coverage for cohort blocker grouping, department buckets, not-evaluable/degraded breakdowns, inactive lists, and improving/current-risk membership.
- `backend/tests/contract/test_analytics.py` — Added contract coverage for the admin operating-pack endpoint shape and its manager-list payloads.
- `web/src/lib/api/types.ts` — Extended shared API types with operating-pack issue buckets, weekly summary, degradation breakdowns, and manager-list structures.
- `web/src/app/admin/analytics/page.tsx` — Rendered the fixed 7-day weekly operating pack, repeated blocker families, department issue view, degradation copy, and manager lists on the existing analytics page.
- `web/src/app/admin/analytics/page.test.tsx` — Locked the weekly operating-pack UI contract, projection score-basis messaging, and current analytics-page manager-list rendering.
- `web/src/app/admin/users/page.tsx` — Added weekly operating drill-in cards on the users page and generated context-preserving links into user detail.
- `web/src/app/admin/users/[id]/page.tsx` — Rendered the weekly drill-in source banner and preserved `focusBucket` / `focusIssueFamily` / `focusNote` context when setting supervisor focus on the user detail page.
- `web/src/app/admin/users/[id]/page.test.tsx` — Verified current-risk drill-in context, supervisor-focus prefills, reminder/result cards, and unified report links on the user detail page.
