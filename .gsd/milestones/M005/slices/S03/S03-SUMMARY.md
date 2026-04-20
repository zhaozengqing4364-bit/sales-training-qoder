---
id: S03
parent: M005
milestone: M005
provides:
  - Runtime-backed governance summaries on the current knowledge, persona, presentation, and voice-runtime list routes
  - Inline governance UI on the current asset-management pages
  - Fault-to-asset-change linkage on analytics and admin user-detail surfaces for anomaly triage
requires:
  - slice: S01
    provides: projection-backed admin analytics and user drill-in semantics on the current admin surfaces
affects:
  - S04
  - S05
key_files:
  - backend/src/support/services/runtime_status_service.py
  - backend/src/common/knowledge/api.py
  - backend/src/agent/services/persona_service.py
  - backend/src/presentation_coach/api/presentations.py
  - backend/src/admin/api/voice_runtime.py
  - web/src/app/admin/knowledge/page.tsx
  - web/src/app/admin/personas/page.tsx
  - web/src/app/admin/presentations/page.tsx
  - web/src/app/admin/voice-runtime/page.tsx
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - backend/tests/integration/test_asset_governance_api.py
  - web/src/app/admin/asset-governance.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
key_decisions:
  - Reused RuntimeStatusService as the shared recent-impact and anomaly seam for asset governance, then layered asset-local recent-change and health signals on top of that shared index.
  - Kept governance on the current admin asset pages and routes by extending existing contracts with governance_summary instead of creating a separate governance API or console.
  - Attached linked_asset_changes to support/runtime fault diagnostics and rendered them directly on analytics and user-detail pages instead of adding a new anomaly drill-in API.
patterns_established:
  - Use RuntimeStatusService as the shared recent-impact and anomaly seam, then layer per-asset recent-change and local-health facts on top of that shared index.
  - Extend current admin routes and pages with governance_summary and linked_asset_changes instead of introducing a second governance API or console.
  - Render one shared governance vocabulary across knowledge, personas, presentations, and runtime profiles so downstream slices can compare asset health without translation.
observability_surfaces:
  - RuntimeStatusService.build_asset_governance_summary(...) on the current asset list routes
  - /api/v1/support/runtime/faults diagnostics.linked_asset_changes propagated into analytics and admin user detail
  - Shared inline governance cards and runtime-anomaly banners on the current admin asset and drill-in pages
drill_down_paths:
  - .gsd/milestones/M005/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-26T10:25:21.888Z
blocker_discovered: false
---

# S03: 资产影响面与健康治理

**The current admin knowledge, persona, presentation, voice-runtime, analytics, and user-detail pages now expose runtime-backed asset impact, recent-change, and anomaly context without introducing a separate governance product.**

## What Happened

This slice turned asset governance into a runtime-backed part of the current admin product instead of a static metadata view. On the backend, RuntimeStatusService now builds per-asset indexes from the same typed runtime-fault and evidence snapshot used by support/runtime, and the current knowledge, persona, presentation, and voice-runtime list routes each attach a governance_summary with impact, recent-change, and health sections. The route-local layer then adds the asset-specific facts that matter on top of that shared seam: failed knowledge documents, persona policy-health drift, presentation degraded-report signals, and combined runtime blast radius across recent sessions.

On the web side, the existing asset-management pages were updated in place. The knowledge, personas, presentations, and voice-runtime pages now render one shared governance vocabulary for impact range, recent changes, and sample anomalies, with the runtime page also showing the selected profile's current governance context. Operators do not have to leave the pages where they already manage these assets, and the same backend contract now drives all four surfaces.

The slice then connected runtime anomalies back into the current admin inspection flow. Support/runtime fault diagnostics now carry linked_asset_changes references, and the existing analytics and admin user-detail pages render those references directly next to the blocking or warning fault summaries and affected session rows. That lets operators move from an anomaly to the affected report and the likely recent asset change without a new drill-in API or a second governance console.

## Verification

Fresh slice verification passed:
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py` — passed (1 integration test), proving the current knowledge/persona/presentation/runtime routes expose runtime-backed governance summaries and expected anomaly kinds.
- `cd web && npm test -- --run 'src/app/admin/asset-governance.test.tsx'` — passed (4 tests), proving the current asset pages render the shared inline governance context.
- `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` — passed (8 tests), proving analytics and admin user detail render fault-backed linked asset changes on the existing inspection surfaces.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Governance is still a recent-window operating aid, not a full historical audit console: each asset exposes last-change labels/counts, recent impact counts, and sample anomalies, but not a full change timeline or per-change causality proof. Analytics and user-detail surfaces only show linked asset changes when support/runtime fault diagnostics include linked_asset_changes; otherwise they intentionally fall back to explicit empty-state copy.

## Follow-ups

S04 can aggregate the same governance_summary and linked_asset_changes seams into cohort and weekly operating views instead of inventing a parallel asset-health model.

## Files Created/Modified

- `backend/src/support/services/runtime_status_service.py` — Added the shared asset-governance summary builder and fault-level linked_asset_changes diagnostics that both asset lists and downstream admin pages consume.
- `backend/src/common/knowledge/api.py` — Extended the current knowledge-base list route to return runtime-backed governance_summary data plus knowledge-document health context.
- `backend/src/agent/services/persona_service.py` — Extended the current persona list service to merge runtime-backed governance context with persona policy-health anomalies.
- `backend/src/presentation_coach/api/presentations.py` — Extended the live presentations list API to expose governance_summary on each presentation row.
- `backend/src/admin/api/voice_runtime.py` — Extended the current voice-runtime profile list route to expose governance_summary on each profile.
- `web/src/app/admin/knowledge/page.tsx` — Rendered the shared governance card and overview copy inline on the current knowledge asset page.
- `web/src/app/admin/personas/page.tsx` — Rendered the shared governance card alongside persona policy audit context on the current personas page.
- `web/src/app/admin/presentations/page.tsx` — Rendered the shared governance card inside the current presentations list page.
- `web/src/app/admin/voice-runtime/page.tsx` — Rendered governance context in both the runtime profile list and the selected profile editor pane.
- `web/src/app/admin/analytics/page.tsx` — Rendered support/runtime fault items with linked asset changes on the current analytics page instead of introducing a new drill-in surface.
- `web/src/app/admin/users/[id]/page.tsx` — Rendered recent runtime anomaly banners plus linked asset changes directly inside current user-session rows.
- `backend/tests/integration/test_asset_governance_api.py` — Locked the backend contract for knowledge/persona/presentation/runtime governance summaries and anomaly kinds on the current routes.
- `web/src/app/admin/asset-governance.test.tsx` — Locked the shared inline governance rendering across the four current asset pages.
- `web/src/app/admin/analytics/page.test.tsx` — Locked analytics rendering of fault-backed linked asset changes.
- `web/src/app/admin/users/[id]/page.test.tsx` — Locked user-detail rendering of fault-backed linked asset changes inside current session rows.
