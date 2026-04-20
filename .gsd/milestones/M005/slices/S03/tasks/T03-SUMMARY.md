---
id: T03
parent: S03
milestone: M005
provides: []
requires: []
affects: []
key_files: ["backend/src/support/services/runtime_status_service.py", "web/src/app/admin/analytics/page.tsx", "web/src/app/admin/users/[id]/page.tsx", "web/src/app/admin/analytics/page.test.tsx", "web/src/app/admin/users/[id]/page.test.tsx", "backend/tests/unit/test_support_runtime_service.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M005/slices/S03/tasks/T03-SUMMARY.md"]
key_decisions: ["Reused support/runtime fault diagnostics as the single seam for anomaly-linked asset changes, then rendered that seam on analytics and user-detail pages instead of creating a new governance drill-in API."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the slice-required focused web regression for `admin/analytics` and `admin/users/[id]` and confirmed the new anomaly-linked asset-change surfaces render on both pages. Then ran the existing focused support-runtime service unit suite to confirm the backend payload-builder still classifies release-health anomalies correctly after adding `linked_asset_changes`. I also gave `backend/src/support/services/runtime_status_service.py` a direct `py_compile` syntax check."
completed_at: 2026-03-26T10:17:30.970Z
blocker_discovered: false
---

# T03: Linked support/runtime anomaly changes into the current admin analytics and user-detail pages using fault-backed asset references instead of a new drill-in API.

> Linked support/runtime anomaly changes into the current admin analytics and user-detail pages using fault-backed asset references instead of a new drill-in API.

## What Happened
---
id: T03
parent: S03
milestone: M005
key_files:
  - backend/src/support/services/runtime_status_service.py
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - backend/tests/unit/test_support_runtime_service.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M005/slices/S03/tasks/T03-SUMMARY.md
key_decisions:
  - Reused support/runtime fault diagnostics as the single seam for anomaly-linked asset changes, then rendered that seam on analytics and user-detail pages instead of creating a new governance drill-in API.
duration: ""
verification_result: passed
completed_at: 2026-03-26T10:17:30.979Z
blocker_discovered: false
---

# T03: Linked support/runtime anomaly changes into the current admin analytics and user-detail pages using fault-backed asset references instead of a new drill-in API.

**Linked support/runtime anomaly changes into the current admin analytics and user-detail pages using fault-backed asset references instead of a new drill-in API.**

## What Happened

Extended `RuntimeStatusService` so support/runtime fault items can carry `linked_asset_changes` metadata for the knowledge, persona, presentation, and runtime-profile assets already implicated by the session. The service now reuses the same asset-governance inputs established earlier in S03, flattens recent-change metadata into support/runtime fault diagnostics, and keeps the linkage on the current runtime anomaly line instead of introducing another backend endpoint. On the frontend, the analytics page now loads the existing support/runtime faults feed alongside the current analytics data and renders a compact anomaly-linked asset-change section with direct links back to the current asset-management pages. The admin user-detail page now does the same at session-row level: when a learner session is tied to a recent asset change, the unified-report preview cell surfaces the current runtime anomaly plus direct links back to the implicated asset page. I also repaired the focused support-runtime unit fixture so direct `RuntimeSessionRecord` construction continues to pass the dataclass’s required `voice_policy_snapshot` field, then recorded that gotcha in `.gsd/KNOWLEDGE.md`.

## Verification

Ran the slice-required focused web regression for `admin/analytics` and `admin/users/[id]` and confirmed the new anomaly-linked asset-change surfaces render on both pages. Then ran the existing focused support-runtime service unit suite to confirm the backend payload-builder still classifies release-health anomalies correctly after adding `linked_asset_changes`. I also gave `backend/src/support/services/runtime_status_service.py` a direct `py_compile` syntax check.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1120ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py` | 0 | ✅ pass | 3660ms |
| 3 | `python3 -m py_compile backend/src/support/services/runtime_status_service.py` | 0 | ✅ pass | 100ms |


## Deviations

Added one focused backend unit-fixture fix in `backend/tests/unit/test_support_runtime_service.py` even though the task plan only listed the three production files, because the new support/runtime payload seam was already covered there and the stale fixture made the verification signal unusable.

## Known Issues

A browser spot-check was attempted, but the only live local web server on `127.0.0.1:3000` was not this repository’s app and returned a 404 for `/admin/analytics`; no repo-specific admin browser surface was available on the expected local ports during this task.

## Files Created/Modified

- `backend/src/support/services/runtime_status_service.py`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `backend/tests/unit/test_support_runtime_service.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M005/slices/S03/tasks/T03-SUMMARY.md`


## Deviations
Added one focused backend unit-fixture fix in `backend/tests/unit/test_support_runtime_service.py` even though the task plan only listed the three production files, because the new support/runtime payload seam was already covered there and the stale fixture made the verification signal unusable.

## Known Issues
A browser spot-check was attempted, but the only live local web server on `127.0.0.1:3000` was not this repository’s app and returned a 404 for `/admin/analytics`; no repo-specific admin browser surface was available on the expected local ports during this task.
