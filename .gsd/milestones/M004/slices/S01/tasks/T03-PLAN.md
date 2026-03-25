---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: Carry the learning-evidence vocabulary through report/history and lock degraded-state behavior

Make sure the report page and history page continue to speak the same learning vocabulary and stay usable when highlights are absent or enhanced data degrades. Add the minimum read-side carry-forward needed on the current user entrypoints; do not invent new routes. Lock the behavior with focused tests so future work cannot quietly revert to generic or conflicting evidence language.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
