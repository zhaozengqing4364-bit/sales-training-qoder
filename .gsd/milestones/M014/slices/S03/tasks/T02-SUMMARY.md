---
id: T02
parent: S03
milestone: M014
key_files:
  - web/src/components/dashboard/learner-help-card.tsx
  - web/src/app/(dashboard)/page.tsx
  - web/src/app/(dashboard)/profile/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - web/src/app/(dashboard)/history/page.test.tsx
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Kept learner help on the existing shared `DashboardShell` + `LearnerHelpEntry` seam and used a shared dashboard guidance card for discoverability instead of adding page-local help buttons or a fake help center.
duration: 
verification_result: passed
completed_at: 2026-04-11T15:43:47.208Z
blocker_discovered: false
---

# T02: Added a shared learner help guidance card to dashboard home, profile, and history so learners can find the existing sidebar help seam and understand role-gated links.

**Added a shared learner help guidance card to dashboard home, profile, and history so learners can find the existing sidebar help seam and understand role-gated links.**

## What Happened

I followed the existing T01 authority line instead of inventing a new support path: the learner help runtime seam remains `DashboardShell` + `LearnerHelpEntry`, and this task closes the discoverability gap around it. I started with a new history-page regression that expected truthful learner help guidance, ran it red, and confirmed the failure was real because the page had no such guidance yet. Then I added `web/src/components/dashboard/learner-help-card.tsx`, a shared dashboard card that tells learners the real help/feedback entry lives in the sidebar/mobile drawer, that page/session context should be reported there, and that runtime/admin links are intentionally role-gated. I reused that same card on dashboard home, profile, and history so the learner-facing guidance stays consistent across the three main entry pages without adding page-local help buttons, a fake help center, or any unimplemented ticketing promise. I also updated `.codex/loop/state.json` and `.codex/loop/log.md` so the repository continuity layer reflects that T02 is done and T03 should focus on broader proof rather than more runtime wiring.

## Verification

Verified the change with a test-first cycle and fresh post-change runs. First, `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"` failed on the new help-card expectation because history had no discoverable learner help guidance. After implementing the shared learner help card and wiring it into home/profile/history, I reran that exact task-plan verification command and it passed 6/6. I then ran `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx"`, which passed 14/14 and confirmed the reused help card did not regress the other learner entry pages. Earlier in the task I also checked LSP diagnostics on the touched runtime files, and all reported clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"` | 0 | ✅ pass | 1231ms |
| 2 | `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx"` | 0 | ✅ pass | 1419ms |

## Deviations

The written plan allowed adding the unified entry in the learner shell or on page surfaces. Local reality from T01 showed the shared shell entry already existed, so instead of adding another help button I implemented shared page-level discoverability guidance that points back to the existing `DashboardShell`/`LearnerHelpEntry` seam.

## Known Issues

T03 still needs broader focused proof that the shared learner help seam remains visible and understandable across the dashboard entry pages; this task added the runtime guidance and one focused history regression, but not the full multi-page seam-proof layer yet.

## Files Created/Modified

- `web/src/components/dashboard/learner-help-card.tsx`
- `web/src/app/(dashboard)/page.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
