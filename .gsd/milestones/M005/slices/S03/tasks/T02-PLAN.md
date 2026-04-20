---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Show governance context on the current admin asset pages

Surface the new governance data on the existing asset pages instead of introducing a new admin product. Update current knowledge/persona/presentation/voice-runtime pages so operators can see health anomalies, recent changes, and likely impact range where they already work.

## Inputs

- `web/src/app/admin/knowledge/page.tsx`
- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/presentations/page.tsx`
- `web/src/app/admin/voice-runtime/page.tsx`

## Expected Output

- `web/src/app/admin/knowledge/page.tsx`
- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/presentations/page.tsx`
- `web/src/app/admin/voice-runtime/page.tsx`
- `web/src/app/admin/asset-governance.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/admin/asset-governance.test.tsx'
