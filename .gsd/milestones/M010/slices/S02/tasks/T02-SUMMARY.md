---
id: T02
parent: S02
milestone: M010
provides: []
requires: []
affects: []
key_files: ["web/src/lib/api/types.ts", "backend/src/common/conversation/session_evidence.py", "backend/tests/unit/common/test_admin_analytics_service.py"]
key_decisions: ["Mirror degradation tokens into degraded_reasons list for backward-compat admin analytics consumers, replacing the old missing_fields-based extraction path."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran backend pytest on admin analytics (3 tests), history evidence projection (4 tests) — all 7 pass. py_compile on session_evidence.py succeeds. Frontend tsc --noEmit shows only pre-existing errors unrelated to the new types. The contract parity test has a pre-existing agents-table schema error unrelated to this task."
completed_at: 2026-03-30T03:32:18.995Z
blocker_discovered: false
---

# T02: Add TS EvidenceDegradation types, degraded_reasons mirror, and update admin analytics test expectations for four-layer taxonomy

> Add TS EvidenceDegradation types, degraded_reasons mirror, and update admin analytics test expectations for four-layer taxonomy

## What Happened
---
id: T02
parent: S02
milestone: M010
key_files:
  - web/src/lib/api/types.ts
  - backend/src/common/conversation/session_evidence.py
  - backend/tests/unit/common/test_admin_analytics_service.py
key_decisions:
  - Mirror degradation tokens into degraded_reasons list for backward-compat admin analytics consumers, replacing the old missing_fields-based extraction path.
duration: ""
verification_result: mixed
completed_at: 2026-03-30T03:32:18.998Z
blocker_discovered: false
---

# T02: Add TS EvidenceDegradation types, degraded_reasons mirror, and update admin analytics test expectations for four-layer taxonomy

**Add TS EvidenceDegradation types, degraded_reasons mirror, and update admin analytics test expectations for four-layer taxonomy**

## What Happened

Verified the degradation mirror code (already present from previous session) in session_evidence.py that mirrors canonical degradation layer tokens into evidence_completeness.degraded_reasons for backward-compat consumers. Added EvidenceDegradationLayer and EvidenceDegradation TypeScript interfaces in web/src/lib/api/types.ts and wired them into SessionEvidenceContract and KnowledgeCheckDiagnostics. Updated three assertion blocks in test_admin_analytics_service.py to match the new canonical degradation tokens (no_retrieval_facts, no_scored_turns, no_audio_segments) replacing the old missing_fields-based tokens (message_scores, stage_evidence).

## Verification

Ran backend pytest on admin analytics (3 tests), history evidence projection (4 tests) — all 7 pass. py_compile on session_evidence.py succeeds. Frontend tsc --noEmit shows only pre-existing errors unrelated to the new types. The contract parity test has a pre-existing agents-table schema error unrelated to this task.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q` | 0 | ✅ pass | 6600ms |
| 2 | `backend/venv/bin/python -m py_compile backend/src/common/conversation/session_evidence.py` | 0 | ✅ pass | 200ms |
| 3 | `cd web && npx tsc --noEmit --pretty 2>&1 | head -30` | 1 | ⚠️ pre-existing errors only | 7400ms |


## Deviations

Updated admin analytics test expectations to match new degradation token names and counts. Old tests asserted message_scores/stage_evidence tokens; new canonical tokens replace those.

## Known Issues

test_conclusion_evidence_parity.py has a pre-existing SQLAlchemy NoReferencedTableError for the agents table. Frontend tsc --noEmit has 4+ pre-existing type errors unrelated to new EvidenceDegradation types.

## Files Created/Modified

- `web/src/lib/api/types.ts`
- `backend/src/common/conversation/session_evidence.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`


## Deviations
Updated admin analytics test expectations to match new degradation token names and counts. Old tests asserted message_scores/stage_evidence tokens; new canonical tokens replace those.

## Known Issues
test_conclusion_evidence_parity.py has a pre-existing SQLAlchemy NoReferencedTableError for the agents table. Frontend tsc --noEmit has 4+ pre-existing type errors unrelated to new EvidenceDegradation types.
