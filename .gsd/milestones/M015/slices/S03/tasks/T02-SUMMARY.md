---
id: T02
parent: S03
milestone: M015
key_files:
  - web/src/components/learner/learner-route-loading-state.tsx
  - web/src/components/learner/learner-route-loading-state.test.tsx
  - web/src/app/(dashboard)/loading.tsx
  - web/src/app/(auth)/loading.tsx
  - web/src/app/(auth)/error.tsx
  - web/src/app/(auth)/route-shells.test.tsx
  - web/src/app/(user)/practice/[sessionId]/loading.tsx
  - web/src/components/dashboard-skeleton.tsx
  - web/src/app/(user)/practice/[sessionId]/error.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D185 — close most learner loading gaps via one shared LearnerRouteLoadingState plus group-level loaders at `(dashboard)` and `(auth)`, with a dedicated live-practice loader only for `/practice/[sessionId]`.
  - Keep auth and live-practice route failures on the existing LearnerRouteErrorState + debug.durableError seam instead of creating a second auth-specific observability path.
duration: 
verification_result: passed
completed_at: 2026-04-11T18:41:41.855Z
blocker_discovered: false
---

# T02: Added shared learner loading/error shells for dashboard, auth, and live practice routes, plus a narrower-screen-safe dashboard fallback layout.

**Added shared learner loading/error shells for dashboard, auth, and live practice routes, plus a narrower-screen-safe dashboard fallback layout.**

## What Happened

I started from the T01 fallback matrix and kept the task narrowly scoped to the real learner-core gaps instead of adding page-local shells everywhere. To stay inside TDD, I first added focused tests for a new learner loading-state seam and auth route shells, ran them, and confirmed they failed because the new shared component and route files did not exist yet.

From that red state, I introduced `web/src/components/learner/learner-route-loading-state.tsx` as the shared accessible loading wrapper, then used it to add route-level loaders at `web/src/app/(dashboard)/loading.tsx`, `web/src/app/(auth)/loading.tsx`, and `web/src/app/(user)/practice/[sessionId]/loading.tsx`. I also added `web/src/app/(auth)/error.tsx` on the existing `LearnerRouteErrorState` durable-error seam so auth routes now fail through an explicit recoverable shell instead of bubbling to a blank or generic crash surface.

For the low-risk UX follow-through, I updated `web/src/components/dashboard-skeleton.tsx` so the shared dashboard fallback stacks cleanly on narrow screens instead of keeping the old edge-aligned header layout. I then aligned the existing live-practice error test with the already-shipped `debug.durableError(...)` observability seam so the learner error boundary proof matches the current tagged route-error behavior instead of the older console-only expectation.

I also recorded the new route-shell reuse pattern as D185 and appended a knowledge entry clarifying that `(dashboard)/loading`, `(auth)/loading`, and `practice/[sessionId]/loading` are now the default learner loading baseline for T03 and later audits.

## Verification

Verified the new learner route-shell baseline in four layers: (1) route inventory now shows new `(dashboard)/loading`, `(auth)/error`/`loading`, and `practice/[sessionId]/loading` files; (2) focused auth/loading seam tests passed after the red-to-green cycle for the new shared loading wrapper and auth shells; (3) the task-plan regression gate for history/report/replay finished green at 41/41, proving the new route-level shells did not regress core learner report/replay/history behavior; and (4) route-error observability proof finished green at 5/5, confirming learner route errors still report through the durableError seam with the expected tagged fallback behavior. Fresh LSP diagnostics were clean on the new auth/dashboard/loading/shared-shell files that the server could resolve directly.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort` | 0 | ✅ pass | 15ms |
| 2 | `npm --prefix web test -- --run "src/app/(auth)/route-shells.test.tsx" "src/components/learner/learner-route-loading-state.test.tsx"` | 0 | ✅ pass | 1816ms |
| 3 | `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` | 0 | ✅ pass | 2367ms |
| 4 | `npm --prefix web test -- --run "src/components/error-reporting.test.tsx" "src/app/(user)/practice/[sessionId]/error.test.tsx"` | 0 | ✅ pass | 1797ms |

## Deviations

Minor local adaptation only: instead of creating page-local `loading.tsx` files for every individual learner dashboard page, I closed the shared learner loading gap at the route-group boundary with `(dashboard)/loading.tsx` and `(auth)/loading.tsx`, then kept a dedicated page-family loader only for `/practice/[sessionId]`. This matched the real code shape and kept the change low-blast-radius while still closing the user-visible fallback hole.

## Known Issues

Timezone semantics on history/report/replay remain intentionally deferred from T01: those screens still rely on browser-local time formatting, and no timestamp contract change was made here because that would be a product-semantic decision, not a safe route-shell tweak. Also, dashboard child routes now share the new group-level loader by default; if a later slice needs a richer route-specific loading skeleton, it should add that page-local loader deliberately instead of treating the shared group shell as missing coverage.

## Files Created/Modified

- `web/src/components/learner/learner-route-loading-state.tsx`
- `web/src/components/learner/learner-route-loading-state.test.tsx`
- `web/src/app/(dashboard)/loading.tsx`
- `web/src/app/(auth)/loading.tsx`
- `web/src/app/(auth)/error.tsx`
- `web/src/app/(auth)/route-shells.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/loading.tsx`
- `web/src/components/dashboard-skeleton.tsx`
- `web/src/app/(user)/practice/[sessionId]/error.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
