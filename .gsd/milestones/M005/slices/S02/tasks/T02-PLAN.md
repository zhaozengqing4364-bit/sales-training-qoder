---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Let supervisors create and inspect interventions on current admin user surfaces

Update the current admin users detail/list surfaces so a supervisor can create and inspect interventions without leaving the existing business chain. Reuse current user detail and manager-lite components rather than adding a new workflow console.

## Inputs

- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`

## Expected Output

- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
