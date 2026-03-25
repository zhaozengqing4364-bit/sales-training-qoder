---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: Let current admin users surfaces drill into the weekly operating buckets

Keep the current users list/detail surfaces aligned with the new cohort operating view so managers can drill from a weekly bucket into specific users without losing the same evidence vocabulary. Reuse current admin users pages and focused tests.

## Inputs

- `web/src/app/admin/users/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Expected Output

- `web/src/app/admin/users/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'
