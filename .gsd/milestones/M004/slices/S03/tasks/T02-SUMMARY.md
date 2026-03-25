---
id: T02
parent: S03
milestone: M004
key_files:
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
key_decisions:
  - Reuse the existing report/replay CTA and `api.practice.createSession` surface for retries instead of creating a retry-specific frontend flow.
  - Load replay retry metadata from the canonical report `retry_entry` so report and replay stay aligned on one retry-launch contract.
  - Keep scenario selection visible in the follow-up `/practice/{sessionId}` URL via existing query params while `focus_intent` travels in the create-session request body.
duration: ""
verification_result: passed
completed_at: 2026-03-25T18:03:40.265Z
blocker_discovered: false
---

# T02: Connected report and replay retry CTAs to focused create-session launches

**Connected report and replay retry CTAs to focused create-session launches**

## What Happened

The T02 implementation is now formally recorded. The report page reuses the existing retry CTA and create-session surface, forwarding `retry_entry.focus_intent` together with the current scenario identifiers so a learner can relaunch directly into a targeted retry without introducing a separate flow. The replay page mirrors that behavior by loading the canonical report `retry_entry` alongside replay evidence, then using the same create-session call and existing `/practice/{sessionId}` entry route. The shared API client/type layer already carries `RetryFocusIntent`, and the focused report/replay tests cover both the targeted retry launch and the replay-anchor behavior. In this recovery pass I verified the shipped state and found the remaining gate failure was the missing task artifact, not a product regression.

## Verification

Re-ran the task-plan verification command from `web/`. Vitest passed for both `src/app/(user)/practice/[sessionId]/report/page.test.tsx` and `src/app/(user)/practice/[sessionId]/replay/page.test.tsx` (14 tests total), confirming the focused retry CTA wiring, `focus_intent` forwarding, scenario-specific navigation params, and replay deep-link behavior remain green. I also confirmed the task summary artifact itself was missing before this completion call, which explains the gate failure.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 15900ms |


## Deviations

No product-scope deviations. This recovery pass did not require code edits because the T02 implementation was already present; the failing gate was caused by the missing `T02-SUMMARY.md` artifact.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
