---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T02: 迁移 current admin pages 到 shared adapters

Migrate current admin pages to the shared adapters/hooks and delete the remaining duplicated normalize/derive code that now belongs in the shared layer. Keep the route family unchanged and resist introducing a second state-management abstraction.

## Inputs

- `web/src/lib/admin/read-models.ts`
- `web/src/lib/admin/runtime-faults.ts`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`

## Expected Output

- `Analytics/users/user-detail pages consume shared admin adapters/hooks`
- `Remaining page-local duplicate derive code is removed or reduced to route-specific composition`

## Verification

cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
