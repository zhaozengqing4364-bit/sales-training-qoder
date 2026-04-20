---
id: T01
parent: S03
milestone: M014
key_files:
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D177 — keep learner help on DashboardShell + LearnerHelpEntry instead of scattering page-local help buttons.
duration: 
verification_result: passed
completed_at: 2026-04-11T15:33:35.000Z
blocker_discovered: false
---

# T01: Confirmed that learner help already hangs off the shared DashboardShell/LearnerHelpEntry seam, recorded that authority line for M014/S03, and marked the remaining gap as page-level discoverability/proof on home/profile/history.

**Confirmed that learner help already hangs off the shared DashboardShell/LearnerHelpEntry seam, recorded that authority line for M014/S03, and marked the remaining gap as page-level discoverability/proof on home/profile/history.**

## What Happened

I inventoried `web/src/components/layout/sidebar.tsx` plus the dashboard home/profile/history surfaces and found that the learner help entry was not actually missing from the runtime shell. `LearnerHelpEntry` is already mounted from `web/src/components/layout/dashboard-shell.tsx` into the desktop sidebar footer slot and the shared mobile drawer, and the same component is reused by `web/src/app/(user)/practice/layout.tsx`. What is still missing is focused learner-facing discoverability/proof around that shared seam on dashboard home, profile, and history: those page files and tests emphasize history/report/profile flows, while help assertions currently live only at the shell/layout layer. I recorded D177 so T02/T03 stay on the existing shell seam instead of adding per-page help buttons, added the finding to `.gsd/KNOWLEDGE.md`, and updated the loop state/log so the next task can continue from the real gap.

## Verification

Ran the task-plan inventory command `rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)` to locate the current learner shell/help/history surfaces, which showed help copy only on the shared layout seam rather than page-local dashboard/profile/history buttons. Then ran `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx"`, which passed 6/6 and confirmed the existing learner help entry stays mounted on the shared desktop sidebar and mobile drawer seams.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)` | 0 | ✅ pass | 20ms |
| 2 | `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx"` | 0 | ✅ pass | 1149ms |

## Deviations

The written task expected source-file touch under `web/src/components/layout` / `web/src/app/(dashboard)`, but local inspection showed the shared learner help seam already existed. I therefore documented the authoritative seam and gap in project knowledge/decisions instead of changing runtime files in this task.

## Known Issues

Home/profile/history page tests still do not directly assert learner help visibility; only `src/components/layout/sidebar.test.tsx` and `src/components/layout/dashboard-shell.test.tsx` currently lock the shared seam.

## Files Created/Modified

- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
