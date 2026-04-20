---
id: T03
parent: S02
milestone: M015
key_files:
  - web/src/app/admin/records/page.test.tsx
  - web/src/lib/auth-handler.test.ts
  - .gsd/KNOWLEDGE.md
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-11T18:14:59.029Z
blocker_discovered: false
---

# T03: Strengthened the non-interruptive interaction proof with delete-dialog and auth-handler seam regressions.

**Strengthened the non-interruptive interaction proof with delete-dialog and auth-handler seam regressions.**

## What Happened

I started from the slice/task plan, re-ran the native-dialog and hard-navigation scan, and confirmed the remaining grep hits had already been reduced to documented exceptions in `ErrorBoundary`, `app/admin/error.tsx`, and `performance.ts`. From there I focused the proof on the two shared seams that still needed durable regression coverage. In `web/src/app/admin/records/page.test.tsx`, I tightened the destructive-action proof so record deletion now explicitly stays behind the shared confirm dialog before any mutation happens, verifies the dialog copy contains the selected record title, and asserts that neither `window.confirm` nor `window.alert` is used on the happy or failure paths. In `web/src/lib/auth-handler.test.ts`, I added a late-router-bridge regression proving that `sessionExpired()` can hold the redirect on the shared auth-handler seam until the Next router navigator is registered, instead of depending on a hard browser jump. While writing that test I hit a singleton gotcha: `authHandler` preserves auth-notification cooldown state across Vitest examples, so I isolated the fake clock and then recorded that pattern in `.gsd/KNOWLEDGE.md` for future agents. No product code path changed in this task; the work was entirely about making the existing non-interruptive behavior durable and inspectable.

## Verification

I ran a strict grep gate that failed the task if any `alert/confirm/window.location.assign/href` usage remained outside the documented exceptions and it passed, leaving only `web/src/components/ErrorBoundary.tsx`, `web/src/app/admin/error.tsx`, and `web/src/lib/performance.ts` as explained cases. I then ran the exact task-plan test command `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"`, which passed 7/7 and preserved the focused persona/login proof. Finally, I ran the expanded seam suite `npm --prefix web test -- --run src/app/admin/records/page.test.tsx src/lib/auth-handler.test.ts`, which passed 8/8 and exercised the new delete-confirmation and auth-redirect seam regressions. Fresh LSP diagnostics on the edited test files were clean earlier in the task.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `strict grep allowlist check for alert/confirm/window.location usage outside documented exceptions` | 0 | ✅ pass | 44ms |
| 2 | `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"` | 0 | ✅ pass | 1397ms |
| 3 | `npm --prefix web test -- --run src/app/admin/records/page.test.tsx src/lib/auth-handler.test.ts` | 0 | ✅ pass | 1308ms |

## Deviations

Added one expanded seam verification command and a stricter grep allowlist check beyond the exact plan command so the new proof explicitly covers the delete-confirmation and auth-handler seams the task was meant to lock. Also appended a non-obvious singleton-testing gotcha to `.gsd/KNOWLEDGE.md` because it directly affected this proof surface.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/admin/records/page.test.tsx`
- `web/src/lib/auth-handler.test.ts`
- `.gsd/KNOWLEDGE.md`
