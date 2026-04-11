---
id: S01
parent: M015
milestone: M015
provides:
  - A single frontend debug/observability seam that downstream slices can reuse instead of adding page-local console exits.
  - A regression-proof raw-console boundary that distinguishes allowed instrumentation/bootstrap exceptions from product/runtime logging.
  - Durable route-error reporting already wired into learner/admin/dashboard error surfaces for reuse by learner-shell follow-up work.
requires:
  []
affects:
  - S02
  - S03
key_files:
  - web/src/lib/debug.ts
  - web/src/lib/console-boundary.test.ts
  - web/src/components/ErrorBoundary.tsx
  - web/src/components/learner/learner-route-error-state.tsx
  - web/src/app/(dashboard)/error.tsx
  - web/src/app/admin/error.tsx
key_decisions:
  - D180 — raw console is allowed only in instrumentation bootstrap and the shared debug seam itself.
  - D181 — route error surfaces and React boundaries use `debug.durableError(scope, error, context)` as the durable frontend failure seam.
  - D182 — business pages, hooks, and developer/support utilities use `debug.log/debug.warn/debug.error`; raw console does not return outside the shared seam/bootstrap exceptions.
patterns_established:
  - Use `debug.durableError(...)` for user-visible route/error-boundary failures and `debug.log/warn/error(...)` for ordinary dev/support diagnostics.
  - Treat `web/src/lib/console-boundary.test.ts` plus the repo-root raw-console grep as the canonical proof boundary for frontend console hygiene.
  - Update the inventory, decision record, knowledge note, and boundary allowlist together if the raw-console exception set ever changes.
observability_surfaces:
  - `web/src/lib/debug.ts` shared frontend debug/observability seam
  - `web/src/lib/console-boundary.test.ts` raw-console boundary gate
  - Repo-root `rg -n "console\.(log|error|warn|info)" web/src` inventory scan
  - Route/error-boundary `debug.durableError(...)` reporting path
drill_down_paths:
  - .gsd/milestones/M015/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M015/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M015/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T17:39:38.914Z
blocker_discovered: false
---

# S01: 前端日志出口统一化

**Frontend business pages, hooks, and route-error surfaces now report through one shared debug/observability seam, with raw console limited to the intentional debug/instrumentation exception boundary.**

## What Happened

## What this slice actually delivered

S01 turned frontend logging from a page-local habit into one explicit seam. `web/src/lib/debug.ts` now carries the canonical frontend console inventory plus the durable/frontend debug helpers that downstream work should reuse instead of opening new `console.*` escape hatches. The slice narrowed raw-console exceptions to exactly three places: `web/src/lib/debug.ts` itself and the bootstrap instrumentation entrypoints `web/src/instrumentation.ts` / `web/src/instrumentation-client.ts`.

On top of that boundary, route-level failure surfaces were migrated onto `debug.durableError(scope, error, context)`: `web/src/components/ErrorBoundary.tsx`, `web/src/components/learner/learner-route-error-state.tsx`, `web/src/app/(dashboard)/error.tsx`, and `web/src/app/admin/error.tsx` now keep their fallback UI/analytics behavior while reporting durable failures through one helper instead of ad hoc `console.error(...)` calls.

The remaining noisy business callers were then migrated onto `debug.log(...)`, `debug.warn(...)`, or `debug.error(...)` across learner/admin pages, hooks, highlight/media helpers, auth/performance utilities, and the developer test-mic path. To keep that cleanup from drifting back, `web/src/lib/console-boundary.test.ts` now scans the frontend source tree and fails whenever a raw `console.*` slips outside the explicit allowlist.

## Patterns established for downstream slices

- **One explicit frontend observability seam:** use `debug.durableError(...)` for user-visible route/error-boundary failures and `debug.log/warn/error(...)` for dev/support diagnostics; do not reintroduce page-local raw console usage.
- **Inventory-backed exception policy:** the allowlist lives in code and proof, not tribal knowledge. If a future slice truly needs a new raw-console exception, it must update the inventory/decision/knowledge entries together with the boundary proof.
- **Proof by boundary, not by hope:** downstream agents can prove console hygiene with one focused Vitest suite plus one repo-root `rg` scan instead of rereading dozens of files.

## Operational Readiness

- **Health signal:** `npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"` stays green, and `rg -n "console\.(log|error|warn|info)" web/src` only returns `web/src/lib/debug.ts` plus `web/src/instrumentation*.ts`.
- **Failure signal:** a new raw `console.*` appears in a business page/hook/route surface, `console-boundary.test.ts` fails, or a route error surface stops calling `debug.durableError(...)` and starts owning its own logging again.
- **Recovery procedure:** classify the offending caller with the `frontendConsoleInventory`, migrate it onto `debug.durableError(...)` or `debug.log/warn/error(...)` as appropriate, keep raw console limited to the shared seam/bootstrap exceptions, then rerun the Vitest seam gate and repo-root `rg` gate.
- **Monitoring gaps:** the slice intentionally standardized the frontend logging exit but did not add a remote durable reporter beyond existing side effects; future work may still choose to connect `debug.durableError(...)` to stronger observability sinks.

## What the next slices should know

S02 should treat this slice as the authority for frontend logging policy: replacing native dialogs or `window.location` must not come with new page-local console escape hatches. S03 should reuse the already-migrated learner route/error boundary seam when adding loading/error coverage, rather than inventing a second reporting path for learner shell failures.

## Verification

Fresh slice-close verification reran the focused seam gate `npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"` and it passed 5 files / 27 tests green. Fresh repo-root inventory verification reran `rg -n "console\.(log|error|warn|info)" web/src` and it reported raw console only in `web/src/instrumentation.ts`, `web/src/instrumentation-client.ts`, and `web/src/lib/debug.ts`, matching the intended exception boundary. Fresh LSP diagnostics on `web/src/lib/debug.ts`, `web/src/components/ErrorBoundary.tsx`, `web/src/components/learner/learner-route-error-state.tsx`, `web/src/app/(dashboard)/error.tsx`, `web/src/app/admin/error.tsx`, and `web/src/lib/console-boundary.test.ts` reported no diagnostics.

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

S01 standardizes the frontend logging exit but does not yet add a stronger remote/browser-side durable reporting sink beyond the existing shared helper and existing side effects.

## Follow-ups

S02 should reuse the shared debug seam while replacing native dialogs and `window.location`; S03 should reuse the learner route/error durable seam while filling loading/error fallback coverage.

## Files Created/Modified

- `web/src/lib/debug.ts` — Added the canonical frontend console inventory plus shared debug and durable-error helpers.
- `web/src/lib/console-boundary.test.ts` — Added the filesystem-backed regression gate that fails when raw console escapes the approved boundary.
- `web/src/components/ErrorBoundary.tsx` — Migrated React error boundaries onto the shared durable frontend error seam.
- `web/src/components/learner/learner-route-error-state.tsx` — Moved learner route-level fallback reporting onto `debug.durableError(...)`.
- `web/src/app/(dashboard)/error.tsx` — Migrated dashboard route-error reporting onto the shared durable seam.
- `web/src/app/admin/error.tsx` — Migrated admin route-error reporting onto the shared durable seam.
