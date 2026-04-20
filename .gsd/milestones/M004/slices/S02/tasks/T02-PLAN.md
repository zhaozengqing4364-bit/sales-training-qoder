---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Deep-link report conclusions into the current replay route

Update the current report page so `main_issue`, `next_goal`, and key learning evidence can deep-link into replay using the stable anchors. Reuse the existing report CTA area and current replay route rather than adding a separate learning workflow page.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
