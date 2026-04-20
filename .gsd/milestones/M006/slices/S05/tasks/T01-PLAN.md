---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: 抽出 shared admin read-model adapters

Extract shared pure adapters for current admin read models — operating-pack highlights, manager-list drill-in cards, runtime-fault linked-asset enrichment, and user-session/intervention derived view state — under `web/src/lib/admin/`. Keep them route-shaped for the current pages instead of inventing a generic dashboard framework.

## Inputs

- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`

## Expected Output

- `Shared admin read-model adapter module(s) under `web/src/lib/admin/``
- `Current operating-pack, runtime fault, and user-session derivations can be consumed without page-local duplication`

## Verification

cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
