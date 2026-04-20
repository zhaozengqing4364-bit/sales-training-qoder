---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T02: Launch focused retries from the current report and replay pages

Update the current report and replay CTAs so they can launch a focused retry using the new retry-entry intent. Reuse existing buttons/routes and keep scenario-specific behavior on the same entrypoints instead of adding a new retry flow.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
