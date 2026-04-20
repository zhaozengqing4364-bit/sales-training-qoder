---
id: S03
parent: M014
milestone: M014
provides:
  - A reusable `LearnerHelpCard` discoverability layer for dashboard home/profile/history that points to the existing learner help seam.
  - A fresh proof line that learners can find help from the three main dashboard entry pages while the real help interaction still lives in the shared shell seam.
requires:
  - slice: S01
    provides: Dashboard home already truthfully routes training/history/report CTAs through real learner-loop actions.
  - slice: S02
    provides: Profile/auth seams already provide truthful password reset handoff and shared learner-shell baseline for profile.
affects:
  - S04
key_files:
  - web/src/components/dashboard/learner-help-card.tsx
  - web/src/app/(dashboard)/page.tsx
  - web/src/app/(dashboard)/profile/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - web/src/app/(dashboard)/page.test.tsx
  - web/src/app/(dashboard)/profile/page.test.tsx
  - web/src/app/(dashboard)/history/page.test.tsx
  - web/src/components/layout/dashboard-shell.test.tsx
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D177 — treat `DashboardShell` + `LearnerHelpEntry` as the single learner help seam and improve discoverability/proof there instead of adding page-local help buttons.
  - Use a shared `LearnerHelpCard` on dashboard home/profile/history to point learners back to the real shell entry instead of inventing a help center or fake support promise.
  - Keep proof split between page-level discoverability tests and the shared `DashboardShell` seam test; do not rely on page-local help controls or the quoted Vitest glob alone.
patterns_established:
  - Shared learner-shell seams should be made discoverable with reusable page-level guidance components rather than duplicated buttons.
  - For multi-page dashboard proof in this repo, pair explicit dashboard page test files with `src/components/layout/dashboard-shell.test.tsx`; the quoted dashboard glob alone can under-run.
observability_surfaces:
  - Focused Vitest seam proof for dashboard home/profile/history plus `DashboardShell` learner help entry visibility.
drill_down_paths:
  - .gsd/milestones/M014/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T15:55:36.187Z
blocker_discovered: false
---

# S03: Learner 导航、反馈入口与系统壳层补齐

**Dashboard 首页、个人中心和历史页现在都通过同一套 learner help guidance 指向共享的 DashboardShell + LearnerHelpEntry 帮助入口，帮助/反馈路径不再依赖散落的页内特例按钮。**

## What Happened

## Delivered
- Confirmed the existing learner help authority seam instead of inventing a new one: `web/src/components/layout/dashboard-shell.tsx` + `LearnerHelpEntry` remain the single help/feedback mount path for learner dashboard surfaces.
- Added a shared `LearnerHelpCard` to `web/src/app/(dashboard)/page.tsx`, `web/src/app/(dashboard)/profile/page.tsx`, and `web/src/app/(dashboard)/history/page.tsx` so learners can discover the real help entry from the three primary dashboard entry pages.
- Kept the copy truthful: learners are told the real entry is the sidebar footer / mobile drawer, that page path or session id should be reported when something is wrong, and that runtime/admin surfaces are intentionally role-gated.
- Added focused proof on dashboard home/profile/history plus the shared shell seam, so future shell work can detect regressions without falling back to page-local help buttons.

## Why this matters downstream
This slice did not create a new support system or help center. It closed a discoverability gap on top of the existing learner shell seam, which means downstream slices should keep extending the shared `DashboardShell` / `LearnerHelpEntry` contract instead of scattering new support affordances across pages.

## Deviations from plan
The written plan assumed S03 might need to add a new learner-shell help entry. Code inventory showed that seam already existed from earlier learner-shell work, so S03 closed the gap by adding shared discoverability guidance and proof on home/profile/history rather than adding duplicate buttons or a fake support center.

## Known limitations
- The learner help path is still a frontend-only context handoff; there is no in-app ticketing, support mailbox configuration UI, or backend feedback pipeline in this slice.
- The literal quoted Vitest dashboard glob in the task plan can stay green while only executing the explicitly named history suite in this repo; multi-page closure still requires explicit page test files plus the shared shell test.

## Verification

Fresh slice-close verification passed on the current branch:

1. `rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)` → exit 0. Output confirmed the help seam still lives in `learner-help-entry.tsx` / `dashboard-shell.test.tsx`, while the dashboard home/profile/history pages and tests now include the learner-help discoverability layer.
2. `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"` → exit 0, 1 file passed, 6/6 tests passed.
3. `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"` → exit 0, 1 file passed, 6/6 tests passed. This also reconfirmed the local quoted-glob behavior noted in project knowledge.
4. `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` → exit 0, 3 files passed, 22/22 tests passed across home/profile/history.
5. `npm --prefix web test -- --run "src/components/layout/dashboard-shell.test.tsx"` → exit 0, 1 file passed, 2/2 tests passed for the shared desktop/mobile help seam.
6. LSP diagnostics on `web/src/components/dashboard/learner-help-card.tsx`, the three dashboard pages, the three dashboard page tests, and `web/src/components/layout/dashboard-shell.test.tsx` all returned `No diagnostics`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

S03 originally looked like a shell-entry implementation task, but the runtime shell entry already existed. The slice therefore closed the real gap — discoverability and proof on home/profile/history — instead of adding duplicate help buttons or a fake help center.

## Known Limitations

Learner help/feedback remains a frontend-only contextual handoff. There is still no backend ticketing flow, persisted feedback submission, or configurable support destination in this slice.

## Follow-ups

If later learner UX slices need more guidance, reuse `DashboardShell` + `LearnerHelpEntry` and the shared `LearnerHelpCard` pattern instead of introducing new page-local help affordances.

## Files Created/Modified

- `web/src/components/dashboard/learner-help-card.tsx` — Added the shared learner help discoverability card used by dashboard home, profile, and history.
- `web/src/app/(dashboard)/page.tsx` — Mounted the shared learner help card on dashboard home.
- `web/src/app/(dashboard)/profile/page.tsx` — Mounted the shared learner help card on profile.
- `web/src/app/(dashboard)/history/page.tsx` — Mounted the shared learner help card on history.
- `web/src/app/(dashboard)/page.test.tsx` — Locked learner help discoverability on dashboard home.
- `web/src/app/(dashboard)/profile/page.test.tsx` — Locked learner help discoverability on profile.
- `web/src/app/(dashboard)/history/page.test.tsx` — Locked learner help discoverability on history.
- `web/src/components/layout/dashboard-shell.test.tsx` — Reconfirmed the shared desktop/mobile learner help seam remains mounted.
- `.gsd/KNOWLEDGE.md` — Recorded the shared learner-help seam finding and the local Vitest quoted-glob verification gotcha.
- `.gsd/DECISIONS.md` — Recorded D177 so future work keeps learner help on the shared shell seam instead of scattering page-local buttons.
