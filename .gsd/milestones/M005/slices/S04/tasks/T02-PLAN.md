---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: Render the weekly operating pack on the existing admin analytics route

Render the weekly operating pack on the current admin analytics page using the new aggregation outputs. Keep the UI on the existing page and make it answer the practical questions: who is at risk, who is improving, what issue family repeats this week, and what changed in the asset layer.

## Inputs

- `web/src/app/admin/analytics/page.tsx`
- `web/src/lib/api/types.ts`
- `web/src/components/admin/manager-lite-panel.tsx`

## Expected Output

- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/lib/api/types.ts`

## Verification

cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'
