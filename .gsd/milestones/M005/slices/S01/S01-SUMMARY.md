---
id: S01
parent: M005
milestone: M005
provides:
  - Projection-backed admin analytics and drill-in semantics aligned with learner/supervisor evidence.
  - Unified admin score-basis/evaluability vocabulary for downstream M005 slices to reuse.
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/admin/api/users.py
  - web/src/app/admin/analytics/page.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/lib/api/types.ts
key_decisions:
  - D074: admin analytics aggregates from HistoryService / SessionEvidenceService projection summaries instead of legacy weighted SQL score math.
  - Admin score-bearing routes and pages now expose score-basis and evaluability metadata explicitly instead of implying semantics from one average score.
patterns_established:
  - Admin aggregates should project completed sessions through HistoryService / SessionEvidenceService first, then derive averages, issue families, next-goal buckets, and not-evaluable counts from that shared summary line.
  - Existing admin surfaces should deep-link to the canonical /practice/{sessionId}/report page instead of inventing a parallel supervisor-only report vocabulary.
observability_surfaces:
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/contract/test_analytics.py
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
drill_down_paths:
  - .gsd/milestones/M005/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-26T06:44:55.703Z
blocker_discovered: false
---

# S01: admin analytics / user drill-in 语义收口

**The current admin analytics page, manager-lite panel, and user drill-in now read from the same projection-backed evidence line as learner/supervisor reports, with explicit evaluability and score-basis semantics instead of legacy weighted-score wording.**

## What Happened

S01 closed the remaining semantic drift between the current admin analytics routes and the projection-backed learner/supervisor evidence line. On the backend, AdminAnalyticsService and related admin user routes now aggregate completed sessions through HistoryService / SessionEvidenceService summaries instead of legacy weighted SQL score math, carrying evaluability counts, score basis, repeated issue-family buckets, repeated next-goal buckets, and not-evaluable reason buckets through overview, trends, leaderboard, stats, progress, and completed-session previews. On the frontend, the existing admin analytics page was reframed around that contract so operators can see what the board actually counts, why some completed sessions are excluded from the score line, which issue family is repeating, and what next-goal family is recurring. ManagerLitePanel and the /admin/users/[id] drill-in were then aligned to the same vocabulary: fail/improving lists explicitly exclude evidence-insufficient sessions, report CTAs deep-link to the canonical /practice/{sessionId}/report entrypoint, and the user detail page shows score basis, evaluable/not-evaluable counts, repeated blockers/goals, and inline progress empty/error states without collapsing the rest of the page shell. The slice deliberately reused the current admin surfaces and shared evidence contracts instead of adding a second analytics pipeline or a supervisor-only report surface.

## Verification

Fresh slice verification passed on all planned surfaces. Commands run: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py` (27 passed); `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx'` (2 passed); `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` (4 passed).

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

This slice aligns the semantics of existing admin analytics and drill-in surfaces only. It does not yet add the supervisor focus/reminder outcome loop planned for S02, the asset-impact governance planned for S03, or the weekly operating pack planned for S04.

## Follow-ups

S02 should reuse the new admin issue_family / repeated_next_goals / score_basis fields when wiring supervisor focus and reminder follow-through. S03/S04 should keep reusing the same evaluability language instead of reintroducing raw averages or implicit score semantics.

## Files Created/Modified

- `backend/src/common/analytics/admin_analytics_service.py` — Replaced legacy weighted admin overview/trends/leaderboard aggregation with projection-backed session evidence summaries, including evaluability, issue-family, next-goal, and not-evaluable-reason buckets.
- `backend/src/admin/api/users.py` — Aligned admin user stats, progress, and completed-session previews to the same projection-backed score/evidence contract used by learner and supervisor report surfaces.
- `web/src/app/admin/analytics/page.tsx` — Reframed the current analytics page around score basis, evaluability scope, issue-family, repeated next-goal, and evidence-insufficient messaging instead of legacy dashboard wording.
- `web/src/components/admin/manager-lite-panel.tsx` — Aligned manager-lite fail/improving lists and report/reminder copy to the unified evidence line while keeping the current surface and canonical report deep-link.
- `web/src/app/admin/users/[id]/page.tsx` — Surfaced unified score basis, evaluability counts, repeated blocker/goal summaries, and resilient inline progress empty/error states on the admin user drill-in page.
- `web/src/lib/api/types.ts` — Extended admin analytics and user-detail types to carry projection-backed evaluability and score-basis metadata end to end.
