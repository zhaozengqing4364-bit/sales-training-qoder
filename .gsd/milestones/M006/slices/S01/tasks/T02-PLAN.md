---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 收口 user-detail drill-in context parser

Move current user-detail `focusBucket` parsing and banner-context derivation onto the shared drill-in helper. Preserve the shipped badge/copy behavior for `not_passed` / `inactive_streak` / `improving`, and update focused tests so the context contract is locked from both launcher and destination sides.

## Inputs

- `web/src/lib/admin/drill-in.ts`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Expected Output

- ``/admin/users/[id]` reads drill-in context through the shared helper`
- `Focused user-detail tests lock the preserved banner/prefill behavior`

## Verification

cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'
