---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: 抽出 shared linked-asset parser

Create `web/src/lib/admin/linked-assets.ts` with shared linked-asset change typing, parsing, filtering, and label helpers. Migrate `/admin/analytics` and `/admin/users/[id]` to use it so fault-linked asset sections stop owning duplicate parser code.

## Inputs

- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Expected Output

- ``web/src/lib/admin/linked-assets.ts` shared parser/label helper`
- `Analytics and user-detail pages consume the same linked-asset helper path`

## Verification

cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
