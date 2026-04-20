---
id: S01
parent: M014
milestone: M014
provides:
  - A truthful learner-home authority seam for primary CTA routing: recommendation → training, history deep link for review/filtering, recent-report shortcut only when genuinely available.
  - A minimal onboarding story future slices can build on without introducing a second onboarding subsystem.
  - Focused dashboard proof that will fail if export/share/goal affordances or fake report/filter buttons drift back into the homepage.
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - web/src/app/(dashboard)/page.tsx
  - web/src/app/(dashboard)/page.test.tsx
  - web/src/app/(dashboard)/history/page.test.tsx
  - .gsd/plans/GSD_PLAN_system-audit-repair.md
key_decisions:
  - D175 — Dashboard home must stay a thin learner-loop surface: recommendation-driven training CTA, history deep links for filtering/review, direct report links only for completed supported sessions, and otherwise honest disabled/absent affordances.
patterns_established:
  - Keep dashboard home as a thin learner-loop surface; route complex review/filtering back to `/history` instead of recreating those workflows on the homepage.
  - Resolve recent-session CTA through one helper (`getDashboardHistoryActions(...)`) so report deep links appear only for completed, supported sessions with a real session id; otherwise show explicit disabled learner copy.
  - Lock homepage closure with explicit focused dashboard tests (`page.test.tsx` + `history/page.test.tsx`) rather than relying on a shell glob that may not expand in auto-mode.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M014/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T14:13:26.771Z
blocker_discovered: false
---

# S01: 首页硬编码与空壳动作收口

**Learner homepage no longer behaves like a demo: it now offers a truthful three-step onboarding path and only exposes real training/history/report actions, with focused proof preventing fake CTA affordances from drifting back.**

## What Happened

S01 closed the learner homepage back onto the real training loop instead of leaving it as a demo surface. The shipped dashboard home now derives its visible actions from live recommendation and history data: the first screen shows a minimal three-step onboarding path (start training → go to history → open the latest unified report), the primary recommendation CTA deep-links to the real training target, and recent-session cards only expose two truthful actions — `/history` and `/practice/{sessionId}/report` when the record is a completed sales/presentation session with a usable session id. Records that cannot yet support a report no longer pretend to be actionable; they fall back to explicit disabled copy explaining why the learner must go through history or wait for completion. The home surface also stops pretending to own advanced filtering: the only remaining filter affordance is an explicit deep link back to `/history`.

This slice also retired the remaining fake or misleading homepage affordances. `导出报告` / `设定目标` / `分享分析` stay absent, rather than being reintroduced as decorative buttons. The version badge dialog now acts as a live entry summary instead of frozen release-note theater, and its footer actions both dismiss correctly while offering a real path into the current training recommendation. Focused proof was added on the existing dashboard test seam so future visual/copy changes cannot silently regress the homepage into empty CTA territory again.

For downstream slices, the important established pattern is that learner-home actions must be derived from existing authority surfaces instead of inventing a second workflow center. Recommendation owns the primary train-now CTA, `getDashboardHistoryActions(...)` owns whether a recent record can deep-link to report versus only history, and complex review/filter behavior stays centralized on `/history`. This gives M014/S02-S04 a stable entrypoint: auth/profile work can hand users back to a homepage that already routes truthfully, learner help/feedback can attach to a shell that no longer carries dead CTA clutter, and practice preflight work can start from a homepage whose promised next step is always real.

## Verification

Fresh slice-close verification reran the homepage-focused dashboard gates and the affordance grep on the shipped authority surface.

- `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"` ✅ pass (5/5)
- `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` ✅ pass (14/14)
- `rg -n '导出报告|设定目标|分享分析|筛选' 'web/src/app/(dashboard)/page.tsx'` ✅ pass — only the intentional history-filter guidance / strategy comments remain, with no restored dead CTA copy

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Product scope stayed aligned with the slice plan. The only close-out deviation was artifact recovery: T02/T03 product code and tests were already present, but auto-mode had left placeholder task summaries and unchecked task boxes. Close-out regenerated truthful task summaries and synchronized the plan markdown so downstream slices inherit accurate context.

## Known Limitations

Advanced filtering still intentionally lives on `/history`, and report export / goal-setting / share-analysis remain intentionally absent until those workflows have real product and backend support. This slice does not add learner help shell, auth/profile completion, or practice preflight UX; those remain in S02-S04.

## Follow-ups

S02 can now build auth/profile completion work on top of a truthful homepage entrypoint. S03 can assume learner help/feedback will plug into a homepage that already routes users to real next steps. S04 can design practice preflight/interruption UX without having to first unwind fake homepage CTA or filter affordances again.

## Files Created/Modified

- `web/src/app/(dashboard)/page.tsx` — Learner homepage authority surface: dynamic onboarding, truthful CTA routing, honest disabled report states, history-filter deep link, and version-dialog action cleanup.
- `web/src/app/(dashboard)/page.test.tsx` — Focused regression suite locking homepage onboarding, live CTA deep links, absent dead affordances, and learner-safe degraded states.
- `web/src/app/(dashboard)/history/page.test.tsx` — Existing dashboard history authority proof kept as the downstream regression partner for homepage handoff.
- `.gsd/plans/GSD_PLAN_system-audit-repair.md` — Normalized audit-repair plan now records the homepage CTA closure strategy and disposition table for fake affordances.
