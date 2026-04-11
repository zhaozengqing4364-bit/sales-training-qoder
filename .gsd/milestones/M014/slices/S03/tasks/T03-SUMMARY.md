---
id: T03
parent: S03
milestone: M014
key_files:
  - web/src/app/(dashboard)/page.test.tsx
  - web/src/app/(dashboard)/profile/page.test.tsx
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Kept learner-help proof split between dashboard page discoverability tests and the existing `DashboardShell` seam proof instead of asserting page-local help buttons.
  - Recorded the local Vitest quoted-glob gotcha in `.gsd/KNOWLEDGE.md` so future multi-page dashboard verification uses explicit file lists when the contract spans more than one page.
duration: 
verification_result: passed
completed_at: 2026-04-11T15:50:07.367Z
blocker_discovered: false
---

# T03: Added focused dashboard tests that lock learner help discoverability on home/profile/history while preserving the shared DashboardShell help seam as the authority proof.

**Added focused dashboard tests that lock learner help discoverability on home/profile/history while preserving the shared DashboardShell help seam as the authority proof.**

## What Happened

I completed the missing proof layer for the learner help/feedback work without changing the runtime seam. History already had a focused learner-help regression from T02, so this task closed the remaining gap by adding matching assertions to `web/src/app/(dashboard)/page.test.tsx` and `web/src/app/(dashboard)/profile/page.test.tsx`. Those tests now lock the same truthful learner-help guidance that points learners back to the shared sidebar/mobile-drawer `DashboardShell` + `LearnerHelpEntry` seam, including the role-gated copy and the absence of fake support promises. I deliberately kept the proof anchored on the shared shell contract instead of inventing page-local help buttons or page-specific expectations. During verification I also confirmed a local Vitest gotcha: the literal quoted dashboard glob from the plan stays green but can execute only the explicitly named history file in this repo, so I documented that behavior in `.gsd/KNOWLEDGE.md` and updated the safe-grow continuity files to preserve the explicit multi-page verification path for future agents.

## Verification

I first checked LSP diagnostics on the changed test files, and both `web/src/app/(dashboard)/page.test.tsx` and `web/src/app/(dashboard)/profile/page.test.tsx` were clean. Then I ran the task-plan verification command exactly as written: `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"`; it passed, but local Vitest semantics only exercised the explicitly named history suite. To prove the intended task scope, I ran `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"`, which passed 22/22 tests across home/profile/history, and `npm --prefix web test -- --run "src/components/layout/dashboard-shell.test.tsx"`, which passed 2/2 tests for the shared desktop/mobile learner-help seam. Together these checks prove learners can find the help guidance from the key dashboard entry pages and that the shared shell seam still mounts the help entry.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"` | 0 | ✅ pass | 1107ms |
| 2 | `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` | 0 | ✅ pass | 1405ms |
| 3 | `npm --prefix web test -- --run "src/components/layout/dashboard-shell.test.tsx"` | 0 | ✅ pass | 845ms |

## Deviations

The written verification command used a quoted dashboard glob that did not broaden coverage under local Vitest behavior here. I kept the literal plan command in the evidence table, then added explicit page-suite and shell-seam commands so the proof actually covered home, profile, history, and the shared `DashboardShell` seam the slice contract depends on.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(dashboard)/page.test.tsx`
- `web/src/app/(dashboard)/profile/page.test.tsx`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
