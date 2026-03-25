---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: Connect asset changes to current runtime/admin inspection surfaces

Tie the asset-governance views back to existing support/runtime and admin drill-in surfaces so rising anomalies can reference recent changes without operators leaving the current chain. Keep the linkage minimal and evidence-based.

## Inputs

- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `backend/src/support/services/runtime_status_service.py`

## Expected Output

- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `backend/src/support/services/runtime_status_service.py`

## Verification

cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
