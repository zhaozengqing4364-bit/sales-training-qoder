# F3 Frontend Focused Gate

Date: 2026-06-20

## Commands and Results

- `cd web && npx tsc --noEmit`
  - Result: passed.

- `cd web && npx vitest run src/components/layout/admin-sidebar.test.tsx src/components/admin/sales-trainer/module-nav.test.tsx src/lib/api/sales-trainer.test.ts src/lib/api/newcomer-training.test.ts src/app/admin/sales-trainer/paths/page.test.tsx 'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx'`
  - Result: passed.
  - Summary: `6 passed (6)`, `54 passed (54)`.

## Browser QA Classification

Browser QA was not executed in this environment.

Reason:

- No running frontend/backend application stack was detected on the common local ports checked with `lsof`.
- The planned browser routes require seeded admin and learner accounts plus backend API state.
- The web dev script is available as `next dev -p 3445`, but starting only the frontend would not satisfy the plan's end-to-end route prerequisites.

Disposition:

- Browser QA remains an external/manual gate and is recorded again in F5.
- Release readiness is not claimed without that manual route evidence.
