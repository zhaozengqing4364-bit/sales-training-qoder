# S03: 资产影响面与健康治理

**Goal:** Add impact, health, and recent-change governance to the current asset-management pages for knowledge, persona, presentation, and runtime profiles.
**Demo:** On the current knowledge/persona/presentation/runtime admin pages, operators can see recent changes, health anomalies, and likely impact range.

## Must-Haves

- Current knowledge/persona/presentation/runtime pages expose enough impact, health, and recent-change context that operators can tell what changed, who it affects, and whether rollout risk is rising.

## Proof Level

- This slice proves: integration

## Integration Closure

Reuse existing admin asset routes/pages and support/runtime diagnostics only: `backend/src/agent/services/persona_service.py`, `backend/src/common/knowledge/api.py`, `backend/src/presentation_coach/api/presentations.py`, `backend/src/admin/api/voice_runtime.py`, `backend/src/support/services/runtime_status_service.py`, and current admin asset pages under `web/src/app/admin/`. No separate governance console.

## Verification

- Asset health, impact, and recent-change regressions become visible on current admin surfaces and current support/runtime correlations. Operators should not need raw logs to guess which config changed what.

## Tasks

- [ ] **T01: Expose asset impact and recent-change summaries on current backend routes** `est:2h`
  Add backend impact and recent-change summaries for the current asset types: knowledge bases, personas, presentations, and voice runtime profiles. Reuse current services/APIs and support/runtime diagnostics so the data comes from real usage and anomaly lines rather than static metadata only.
  - Files: `backend/src/agent/services/persona_service.py`, `backend/src/common/knowledge/api.py`, `backend/src/presentation_coach/api/presentations.py`, `backend/src/admin/api/voice_runtime.py`, `backend/src/support/services/runtime_status_service.py`, `backend/tests/integration/test_asset_governance_api.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py

- [ ] **T02: Show governance context on the current admin asset pages** `est:90m`
  Surface the new governance data on the existing asset pages instead of introducing a new admin product. Update current knowledge/persona/presentation/voice-runtime pages so operators can see health anomalies, recent changes, and likely impact range where they already work.
  - Files: `web/src/app/admin/knowledge/page.tsx`, `web/src/app/admin/personas/page.tsx`, `web/src/app/admin/presentations/page.tsx`, `web/src/app/admin/voice-runtime/page.tsx`, `web/src/app/admin/asset-governance.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/admin/asset-governance.test.tsx'

- [ ] **T03: Connect asset changes to current runtime/admin inspection surfaces** `est:75m`
  Tie the asset-governance views back to existing support/runtime and admin drill-in surfaces so rising anomalies can reference recent changes without operators leaving the current chain. Keep the linkage minimal and evidence-based.
  - Files: `web/src/app/admin/analytics/page.tsx`, `web/src/app/admin/users/[id]/page.tsx`, `backend/src/support/services/runtime_status_service.py`
  - Verify: cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'

## Files Likely Touched

- backend/src/agent/services/persona_service.py
- backend/src/common/knowledge/api.py
- backend/src/presentation_coach/api/presentations.py
- backend/src/admin/api/voice_runtime.py
- backend/src/support/services/runtime_status_service.py
- backend/tests/integration/test_asset_governance_api.py
- web/src/app/admin/knowledge/page.tsx
- web/src/app/admin/personas/page.tsx
- web/src/app/admin/presentations/page.tsx
- web/src/app/admin/voice-runtime/page.tsx
- web/src/app/admin/asset-governance.test.tsx
- web/src/app/admin/analytics/page.tsx
- web/src/app/admin/users/[id]/page.tsx
