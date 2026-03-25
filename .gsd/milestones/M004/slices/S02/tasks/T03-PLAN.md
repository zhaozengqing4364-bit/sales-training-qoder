---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: Land replay on the requested anchor and keep degraded fallback visible

Make the current replay page honor deep-link anchors and keep fallback behavior clear when the target highlight/marker does not exist. Stay on the existing replay page and lock the behavior with focused frontend tests.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
