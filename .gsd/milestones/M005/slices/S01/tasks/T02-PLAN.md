---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Make the existing admin analytics page speak the current evidence language

Update the current admin analytics page and related web types so the UI speaks the same semantics as learner/supervisor evidence: issue families, evaluability, degradation, and projection-backed score meaning. Remove placeholder or legacy wording from the existing analytics page instead of adding a new dashboard.

## Inputs

- `web/src/app/admin/analytics/page.tsx`
- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `backend/src/admin/api/analytics.py`

## Expected Output

- `web/src/app/admin/analytics/page.tsx`
- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `web/src/app/admin/analytics/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'
