---
id: T01
parent: S03
milestone: M015
key_files:
  - milestones/M015/slices/S03/tasks/T01-RESEARCH.md
  - web/src/app/(dashboard)/history/loading.tsx
  - web/src/app/(user)/practice/[sessionId]/report/loading.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/loading.tsx
  - web/src/app/(auth)/login/page.tsx
  - web/src/app/(auth)/forgot-password/page.tsx
  - web/src/app/(auth)/reset-password/page.tsx
  - web/src/app/(auth)/login/page.test.tsx
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Treat learner-core fallback closure as the sidebar learner nav plus auth/practice flows, excluding `/support/runtime` even though it lives under `(dashboard)`.
  - Use T01 only for baseline recording plus low-risk a11y fixes on existing shells/forms; defer missing route-level fallback files and timezone semantics to T02/T03.
duration: 
verification_result: passed
completed_at: 2026-04-11T18:33:49.247Z
blocker_discovered: false
---

# T01: Recorded the learner fallback baseline matrix and shipped low-risk a11y fixes on existing loading shells and auth forms.

**Recorded the learner fallback baseline matrix and shipped low-risk a11y fixes on existing loading shells and auth forms.**

## What Happened

I started by reading the S03 slice/task contract, the repo-local safe-grow state files, and the actual learner route tree so T01 would stay bounded to one audited item. The inventory showed that learner-core coverage is uneven: the dashboard root already has a shared error boundary, history/report/replay already have some route-shell coverage, but most learner dashboard/auth routes still rely on parent shells or page-local fetch states. I also checked the real learner navigation boundary and recorded the non-obvious scope rule that `/support/runtime` is still role-gated support/admin surface, not a learner-shell gap.

With the gap list in hand, I wrote the durable baseline matrix to `milestones/M015/slices/S03/tasks/T01-RESEARCH.md`. That matrix records the live error/loading inventory, marks the true learner-core gaps, and separates what should happen next: T02 should add missing learner-core route-level fallbacks, while larger responsive/timezone semantics stay deferred unless a fallback change naturally touches them.

For the “low-risk, high-value” subset that fit T01 safely, I upgraded the existing learner loading shells (`history`, `report`, `replay`) with explicit `role="status"`, `aria-live="polite"`, and `aria-busy="true"` semantics plus screen-reader copy, so current fallback surfaces stop being purely visual. I also tightened the auth baseline by adding explicit labels to the login form, announcing auth errors as alerts, and upgrading reset-password’s Suspense fallback into a real loading status surface. Finally, I appended the learner-core scope rule to `.gsd/KNOWLEDGE.md` and updated the repo-local loop state/log so the next task can resume directly from the documented matrix instead of re-triaging scope.

## Verification

Ran the slice-plan inventory gate with `find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort`, which matched the gap list captured in T01-RESEARCH: current learner coverage is still dashboard root error + history loading + practice/report/replay shells, with the remaining learner-core routes still missing route-level loading/error files. Then ran `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx"`, which finished 9/9 green after the auth label/alert updates. Fresh LSP diagnostics were clean on `web/src/app/(auth)/login/page.tsx`, `web/src/app/(auth)/forgot-password/page.tsx`, `web/src/app/(auth)/reset-password/page.tsx`, `web/src/app/(dashboard)/history/loading.tsx`, and `web/src/app/(auth)/login/page.test.tsx`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort` | 0 | ✅ pass | 16ms |
| 2 | `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx"` | 0 | ✅ pass | 1212ms |

## Deviations

Minor local adaptation only: instead of creating missing route files early, T01 persisted the learner-core fallback matrix as a RESEARCH artifact (`milestones/M015/slices/S03/tasks/T01-RESEARCH.md`) and limited code changes to the low-risk a11y subset on already-existing loading/auth surfaces. `/support/runtime` was also explicitly excluded from learner-core closure because the current sidebar keeps it role-gated support/admin scope, not learner shell scope.

## Known Issues

Missing route-level fallback coverage still remains exactly as recorded in T01-RESEARCH: `(dashboard)` root has no shared loading shell; `/`, `/training`, `/training/sales`, `/training/presentation`, `/leaderboard`, `/profile`, `/agents/[agentId]`, `/practice/[sessionId]` loading, and `/login`/`/forgot-password` route shells are still gaps; `/reset-password` only has an inline Suspense loading state. Learner-facing timestamp formatting on dashboard/history/report/replay still uses browser-local `toLocaleString("zh-CN")`/`new Date(...)` without an explicit timezone contract, so timezone semantics remain baseline-only and should not be changed casually in T02.

## Files Created/Modified

- `milestones/M015/slices/S03/tasks/T01-RESEARCH.md`
- `web/src/app/(dashboard)/history/loading.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/loading.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/loading.tsx`
- `web/src/app/(auth)/login/page.tsx`
- `web/src/app/(auth)/forgot-password/page.tsx`
- `web/src/app/(auth)/reset-password/page.tsx`
- `web/src/app/(auth)/login/page.test.tsx`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
