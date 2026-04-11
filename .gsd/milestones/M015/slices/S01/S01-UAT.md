# S01: 前端日志出口统一化 — UAT

**Milestone:** M015
**Written:** 2026-04-11T17:39:38.914Z

# UAT — M015/S01 前端日志出口统一化

## Preconditions

- Repository root is `/Users/zhaozengqing/github/销售训练qoder`.
- Frontend dependencies are installed (`web/node_modules` present).
- Worktree contains the S01 changes.

## Test Case 1 — Raw console boundary inventory stays narrow

1. Run `rg -n "console\.(log|error|warn|info)" web/src` from the repo root.
2. Review the returned paths.

**Expected outcome**
- Matches appear only in `web/src/lib/debug.ts`, `web/src/instrumentation.ts`, and `web/src/instrumentation-client.ts`.
- No learner page, admin page, hook, highlight component, auth helper, or performance utility appears in the result.

## Test Case 2 — Shared seam regression pack stays green

1. Run `npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"`.
2. Observe the Vitest summary.

**Expected outcome**
- All 5 test files pass.
- Total result is 27/27 tests green.
- The suite proves all of the following together: console-boundary enforcement, shared debug helper behavior, durable route-error reporting, practice-page behavior, and practice websocket behavior.

## Test Case 3 — Durable route-error surfaces use the shared helper

1. Run `rg -n "debug\.durableError" web/src/components/ErrorBoundary.tsx web/src/components/learner/learner-route-error-state.tsx web/src/app/'(dashboard)'/error.tsx web/src/app/admin/error.tsx`.
2. Inspect the matching lines.

**Expected outcome**
- Each listed route/error-boundary surface contains a `debug.durableError(...)` call.
- There is no need for those files to own raw `console.error(...)` calls.

## Edge Case A — Developer/support diagnostics still have an approved path

1. Review `web/src/lib/debug.ts` and confirm `debug.log(...)`, `debug.warn(...)`, `debug.error(...)`, and `debug.durableError(...)` are present.
2. Confirm the repo-root console inventory from Test Case 1 still includes the shared seam file itself.

**Expected outcome**
- The slice did not remove debugging capability; it centralized it.
- Developer/support diagnostics still have a supported API without expanding the raw-console boundary.

## Edge Case B — Future regression detection is explicit

1. Review `web/src/lib/console-boundary.test.ts`.
2. Confirm the allowlist names only the intentional exception boundary (`web/src/lib/debug.ts` and `web/src/instrumentation*.ts`).

**Expected outcome**
- Boundary enforcement is code-backed and future regressions fail fast.
- Later slices can extend the seam safely without re-running a repo-wide investigation to rediscover policy.

