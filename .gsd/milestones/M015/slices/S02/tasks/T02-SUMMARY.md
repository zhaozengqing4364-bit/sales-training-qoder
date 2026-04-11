---
id: T02
parent: S02
milestone: M015
key_files:
  - web/src/lib/auth-handler.ts
  - web/src/components/providers/app-providers.tsx
  - web/src/components/layout/dashboard-shell.tsx
  - web/src/components/layout/admin-shell.tsx
  - web/src/app/admin/records/page.tsx
  - web/src/app/admin/rag-profiles/page.tsx
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/lib/auth-handler.test.ts
  - web/src/components/layout/dashboard-shell.test.tsx
  - web/src/components/layout/admin-shell.test.tsx
  - web/src/app/admin/records/page.test.tsx
  - web/src/app/admin/rag-profiles/page.test.tsx
  - web/src/app/admin/personas/[id]/page.test.tsx
key_decisions:
  - D184 — register Next router navigation in AppProviders through authHandler.setNavigator, route auth expiry through authHandler/sessionExpired, keep non-auth role fallback on local router.replace, and standardize destructive admin actions on ConfirmDialog plus toast.
duration: 
verification_result: passed
completed_at: 2026-04-11T18:09:33.324Z
blocker_discovered: false
---

# T02: Unified confirm/auth/navigation flows onto authHandler, router, dialog, and toast seams across the planned admin and learner touchpoints.

**Unified confirm/auth/navigation flows onto authHandler, router, dialog, and toast seams across the planned admin and learner touchpoints.**

## What Happened

I verified the remaining T02 touchpoints from the slice inventory, then replaced the last high-risk hard redirects and native blocking interactions with shared seams. In `web/src/lib/auth-handler.ts` I removed direct `window.location.assign` usage, added a router-aware navigator registration API, and kept auth expiry timing centralized by queueing navigation through the shared auth seam. In `web/src/components/providers/app-providers.tsx` I registered that navigator with Next router so auth-triggered redirects now resolve through one client seam. In `web/src/components/layout/dashboard-shell.tsx` and `web/src/components/layout/admin-shell.tsx`, auth errors now delegate to `authHandler.sessionExpired()` instead of forcing browser jumps, while the admin role mismatch fallback now uses `router.replace("/")` as ordinary business navigation.

On the interruptive UI side, `web/src/app/admin/records/page.tsx` now uses `ConfirmDialog` plus toast feedback for record deletion, `web/src/app/admin/rag-profiles/page.tsx` now uses `ConfirmDialog` for destructive deletion and routes its migration CTA through `router.push(...)` instead of a plain hard-navigation anchor, and `web/src/app/admin/personas/[id]/page.tsx` now replaces validation/save/TTS preview alerts with toast feedback while keeping the success path on router navigation. I also updated the shared `interruptiveUiInventory` statuses from remaining cleanup items to `cleaned-up` for the surfaces closed in T02, and added focused regression tests covering the auth-handler router seam, admin/dashboard shell handoff, records deletion dialog, rag-profile deletion/router handoff, and persona toast-based validation/failure feedback.

## Verification

Ran the exact task-plan verification command `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"`, which passed 7/7 tests and proved the persona edit page now uses toast-based validation/failure handling while the login handoff proof still passes. Then ran an expanded seam regression suite `npm --prefix web test -- --run src/lib/auth-handler.test.ts src/components/layout/dashboard-shell.test.tsx src/components/layout/admin-shell.test.tsx src/app/admin/records/page.test.tsx src/app/admin/rag-profiles/page.test.tsx`, which passed 12/12 tests and locked the centralized auth redirect seam plus the records/rag destructive dialog behavior. Fresh LSP diagnostics reported no issues on `web/src/lib/auth-handler.ts`, `web/src/components/providers/app-providers.tsx`, `web/src/components/layout/dashboard-shell.tsx`, `web/src/components/layout/admin-shell.tsx`, `web/src/app/admin/records/page.tsx`, `web/src/app/admin/rag-profiles/page.tsx`, and the persona page glob `web/src/app/admin/personas/*/page.tsx`. The persona failure-path test intentionally emits one `debug.error` line while asserting toast fallback behavior; the suite still passes and no production diagnostics were introduced.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"` | 0 | ✅ pass | 1698ms |
| 2 | `npm --prefix web test -- --run src/lib/auth-handler.test.ts src/components/layout/dashboard-shell.test.tsx src/components/layout/admin-shell.test.tsx src/app/admin/records/page.test.tsx src/app/admin/rag-profiles/page.test.tsx` | 0 | ✅ pass | 1567ms |

## Deviations

Added focused seam regression tests for auth-handler, shell routing, records, and rag-profiles beyond the exact plan command so the newly centralized dialog/router/auth-handler behavior is explicitly locked. I also converted the rag-profile migration CTA from a plain anchor to `router.push(...)` because it was a remaining hard-navigation case on a planned touchpoint.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/auth-handler.ts`
- `web/src/components/providers/app-providers.tsx`
- `web/src/components/layout/dashboard-shell.tsx`
- `web/src/components/layout/admin-shell.tsx`
- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/lib/auth-handler.test.ts`
- `web/src/components/layout/dashboard-shell.test.tsx`
- `web/src/components/layout/admin-shell.test.tsx`
- `web/src/app/admin/records/page.test.tsx`
- `web/src/app/admin/rag-profiles/page.test.tsx`
- `web/src/app/admin/personas/[id]/page.test.tsx`
