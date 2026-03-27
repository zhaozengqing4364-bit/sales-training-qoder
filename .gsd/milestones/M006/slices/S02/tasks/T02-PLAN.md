---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: 收口 frontend typed governance contract

Promote frontend admin governance and linked-asset data to shared typed interfaces in `web/src/lib/api/types.ts` and normalize them centrally in `web/src/lib/api/client.ts`. Remove page-level dependence on `Record<string, unknown>` for these contracts and update `AssetGovernanceSummaryCard` props to consume the typed shape directly.

## Inputs

- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `web/src/components/admin/asset-governance.tsx`
- `web/src/lib/admin/linked-assets.ts`

## Expected Output

- `Shared frontend interfaces for governance summary and linked asset changes`
- `API client returns typed governance/admin contracts to current pages/components`

## Verification

cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
