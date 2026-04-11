---
id: T02
parent: S01
milestone: M015
key_files:
  - web/src/lib/debug.ts
  - web/src/components/ErrorBoundary.tsx
  - web/src/components/learner/learner-route-error-state.tsx
  - web/src/app/(dashboard)/error.tsx
  - web/src/app/admin/error.tsx
  - web/src/lib/debug.test.ts
  - web/src/components/error-reporting.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D181: route error surfaces and React error boundaries now report through `debug.durableError(scope, error, context)` instead of ad hoc raw console calls.
duration: 
verification_result: passed
completed_at: 2026-04-11T17:22:01.521Z
blocker_discovered: false
---

# T02: Added `debug.durableError(...)` and migrated route error surfaces and React boundaries onto the shared frontend observability seam.

**Added `debug.durableError(...)` and migrated route error surfaces and React boundaries onto the shared frontend observability seam.**

## What Happened

I extended `web/src/lib/debug.ts` with an explicit `debug.durableError(scope, error, context)` helper so durable frontend failures have a single always-on observability seam that is distinct from the existing dev-gated `debug.log` / `debug.warn` paths. I then migrated the durable route-failure surfaces named in the inventory—`web/src/components/ErrorBoundary.tsx`, `web/src/components/learner/learner-route-error-state.tsx`, `web/src/app/(dashboard)/error.tsx`, and `web/src/app/admin/error.tsx`—to call that helper with stable scope tags and contextual metadata instead of owning their own `console.error(...)` calls. The existing fallback UI, Sentry capture, and analytics POST behavior in `ErrorBoundary` stayed intact; only the reporting seam changed. To keep the seam regression-proof, I added a direct helper test in `web/src/lib/debug.test.ts` and a route-surface test in `web/src/components/error-reporting.test.tsx` that proves app error surfaces and both React boundaries call the shared durable seam.

## Verification

Reran a combined Vitest gate covering the new seam tests plus the task’s focused verification suites: `src/lib/debug.test.ts`, `src/components/error-reporting.test.tsx`, `src/app/(user)/practice/[sessionId]/page.test.tsx`, and `src/hooks/use-practice-websocket.test.ts`. The run passed with 4 test files / 26 tests green. I also ran a focused `rg` check on the migrated files to confirm route surfaces now call `debug.durableError(...)` and that remaining raw `console.error(...)` ownership is constrained to `web/src/lib/debug.ts`, which is the intentional seam boundary. Separate LSP diagnostics on the edited production files reported no issues.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"` | 0 | ✅ pass | 1248ms |
| 2 | `rg -n "durableError|console\\.error" web/src/lib/debug.ts web/src/components/ErrorBoundary.tsx web/src/components/learner/learner-route-error-state.tsx web/src/app/'(dashboard)'/error.tsx web/src/app/admin/error.tsx` | 0 | ✅ pass | 31ms |

## Deviations

Added two focused regression test files (`web/src/lib/debug.test.ts` and `web/src/components/error-reporting.test.tsx`) so the new seam and its migrated callers are locked directly; this tightened verification without changing the task scope.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/components/learner/learner-route-error-state.tsx`
- `web/src/app/(dashboard)/error.tsx`
- `web/src/app/admin/error.tsx`
- `web/src/lib/debug.test.ts`
- `web/src/components/error-reporting.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
