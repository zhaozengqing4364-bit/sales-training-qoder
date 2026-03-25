---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: Let admins edit and inspect the pressure model on current Persona pages

Expose and validate the pressure model on the existing admin Persona surfaces so operators can edit, preview, and audit the behavior they are about to ship. Stay on the current admin Persona list/detail pages and API client/types; do not create a new management surface.

## Inputs

- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`

## Expected Output

- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/admin/personas/[id]/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/admin/personas/[id]/page.test.tsx'
