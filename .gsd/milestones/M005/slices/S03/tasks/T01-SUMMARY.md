---
id: T01
parent: S03
milestone: M005
provides: []
requires: []
affects: []
key_files: ["backend/src/support/services/runtime_status_service.py", "backend/src/common/knowledge/api.py", "backend/src/common/knowledge/schemas.py", "backend/src/agent/services/persona_service.py", "backend/src/agent/schemas.py", "backend/src/common/db/schemas.py", "backend/src/presentation_coach/api/presentations.py", "backend/src/admin/api/voice_runtime.py", "backend/tests/integration/test_asset_governance_api.py"]
key_decisions: ["Reused RuntimeStatusService as the shared anomaly and impact seam, then layered asset-local change and health signals on each route.", "Kept governance data on the existing list endpoints by extending current response payloads instead of adding a new governance-specific backend surface."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py` and confirmed the new integration suite passes against the current routes and seeded runtime facts."
completed_at: 2026-03-26T08:40:26.083Z
blocker_discovered: false
---

# T01: Added shared runtime-backed governance summaries to the existing asset list routes for knowledge bases, personas, presentations, and voice runtime profiles.

> Added shared runtime-backed governance summaries to the existing asset list routes for knowledge bases, personas, presentations, and voice runtime profiles.

## What Happened
---
id: T01
parent: S03
milestone: M005
key_files:
  - backend/src/support/services/runtime_status_service.py
  - backend/src/common/knowledge/api.py
  - backend/src/common/knowledge/schemas.py
  - backend/src/agent/services/persona_service.py
  - backend/src/agent/schemas.py
  - backend/src/common/db/schemas.py
  - backend/src/presentation_coach/api/presentations.py
  - backend/src/admin/api/voice_runtime.py
  - backend/tests/integration/test_asset_governance_api.py
key_decisions:
  - Reused RuntimeStatusService as the shared anomaly and impact seam, then layered asset-local change and health signals on each route.
  - Kept governance data on the existing list endpoints by extending current response payloads instead of adding a new governance-specific backend surface.
duration: ""
verification_result: passed
completed_at: 2026-03-26T08:40:26.083Z
blocker_discovered: false
---

# T01: Added shared runtime-backed governance summaries to the existing asset list routes for knowledge bases, personas, presentations, and voice runtime profiles.

**Added shared runtime-backed governance summaries to the existing asset list routes for knowledge bases, personas, presentations, and voice runtime profiles.**

## What Happened

Implemented one shared backend governance shape for the current asset-management chain: impact_summary, recent_change_summary, and health_summary. RuntimeStatusService now builds per-asset usage and anomaly indexes from the existing typed support/runtime fault line, and the current list routes layer in asset-local facts such as failed knowledge documents, persona policy drift, presentation processing/failed status, and runtime-profile inactive state. Knowledge, persona, presentation, and voice-runtime routes now expose governance_summary directly on their existing responses instead of introducing a parallel governance API. A focused integration suite seeds real sessions and verifies that the four routes surface impact range, recent-change counts, and anomaly samples from real runtime behavior.

## Verification

Ran `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py` and confirmed the new integration suite passes against the current routes and seeded runtime facts.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py` | 0 | ✅ pass | 4720ms |


## Deviations

Adjusted the focused integration suite to the actual KB-lock runtime anomaly kind (`kb_lock_blocked_search_failed`) emitted by the shared support/runtime diagnostics seam instead of forcing a looser `knowledge_search_failed` label.

## Known Issues

None.

## Files Created/Modified

- `backend/src/support/services/runtime_status_service.py`
- `backend/src/common/knowledge/api.py`
- `backend/src/common/knowledge/schemas.py`
- `backend/src/agent/services/persona_service.py`
- `backend/src/agent/schemas.py`
- `backend/src/common/db/schemas.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/admin/api/voice_runtime.py`
- `backend/tests/integration/test_asset_governance_api.py`


## Deviations
Adjusted the focused integration suite to the actual KB-lock runtime anomaly kind (`kb_lock_blocked_search_failed`) emitted by the shared support/runtime diagnostics seam instead of forcing a looser `knowledge_search_failed` label.

## Known Issues
None.
