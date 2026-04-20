---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Render the richer learning evidence on the existing replay/highlight surfaces

Update the current replay and highlight UI components to render the richer explanation contract directly from API data. Use the existing surfaces only: `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/components/highlights/HighlightList.tsx`, `HighlightCard`, and `HighlightDetailModal`. Make the UI explain why a turn matters and how to improve it, while keeping null/no-highlight states clean.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/components/highlights/HighlightList.tsx`
- `web/src/components/highlights/HighlightCard.tsx`
- `web/src/components/highlights/HighlightDetailModal.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/components/highlights/HighlightList.tsx`
- `web/src/components/highlights/HighlightCard.tsx`
- `web/src/components/highlights/HighlightDetailModal.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'
