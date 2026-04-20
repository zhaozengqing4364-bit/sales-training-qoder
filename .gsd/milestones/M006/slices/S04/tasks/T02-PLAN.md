---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: 对齐 frontend asset metadata helper

Add a matching frontend asset metadata helper so linked-asset displays and governance surfaces stop hardcoding asset labels/admin-path assumptions in page components. Reuse the helper from the shared linked-asset utilities introduced earlier.

## Inputs

- `web/src/lib/admin/linked-assets.ts`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/components/admin/asset-governance.tsx`

## Expected Output

- `Frontend asset metadata helper aligned with backend registry names`
- `Analytics/user-detail linked-asset UI and governance surfaces reuse shared asset metadata`

## Verification

cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/admin/asset-governance.test.tsx'
