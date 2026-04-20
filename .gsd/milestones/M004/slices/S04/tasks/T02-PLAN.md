---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: Show page-level learning evidence on the current PPT report route

Render the richer page-level evidence on the current shared PPT report page so the learner can see which page has which issue cluster and why. Reuse the current presentation branch of `report/page.tsx`; do not create a separate PPT learning page.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
