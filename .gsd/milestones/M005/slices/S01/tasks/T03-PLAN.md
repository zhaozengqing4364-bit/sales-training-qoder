---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T03: Keep manager-lite and user drill-in aligned with the corrected admin truth line

Align current manager-lite and user drill-in surfaces with the same admin truth line so reminder/report CTAs and supervisor summaries do not drift from analytics. Reuse the existing `ManagerLitePanel` and `/admin/users/[id]` page; add focused regressions rather than a new workflow surface.

## Inputs

- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `backend/src/admin/api/users.py`
- `backend/src/admin/api/analytics.py`

## Expected Output

- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
