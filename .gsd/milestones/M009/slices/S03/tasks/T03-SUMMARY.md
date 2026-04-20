---
id: T03
parent: S03
milestone: M009
provides: []
requires: []
affects: []
key_files: ["backend/src/support/services/runtime_status_service.py", "backend/tests/unit/test_support_runtime_service.py"]
key_decisions: ["Audio anomaly state derived from voice_policy_snapshot.runtime_metrics.audio_audit bounded summary rather than querying SessionAudioSegment rows directly, keeping the runtime read model lightweight", "Severity escalation from warning to blocking when failed_segment_count exceeds 50% of total segments", "learner_status computed from audio_audit counts (available/partial/missing) rather than stored as a field, matching the canonical derivation in build_session_audio_audit()"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran focused audio tests (-k audio) and full suite: 8/8 pass (3 existing + 5 new). No regressions. Verified _extract_audio_diagnostics() handles missing/empty/malformed voice_policy_snapshot gracefully."
completed_at: 2026-03-29T23:44:46.110Z
blocker_discovered: false
---

# T03: Added audio_upload_degraded and audio_missing anomaly kinds to RuntimeStatusService with severity escalation and bounded-summary extraction from voice_policy_snapshot

> Added audio_upload_degraded and audio_missing anomaly kinds to RuntimeStatusService with severity escalation and bounded-summary extraction from voice_policy_snapshot

## What Happened
---
id: T03
parent: S03
milestone: M009
key_files:
  - backend/src/support/services/runtime_status_service.py
  - backend/tests/unit/test_support_runtime_service.py
key_decisions:
  - Audio anomaly state derived from voice_policy_snapshot.runtime_metrics.audio_audit bounded summary rather than querying SessionAudioSegment rows directly, keeping the runtime read model lightweight
  - Severity escalation from warning to blocking when failed_segment_count exceeds 50% of total segments
  - learner_status computed from audio_audit counts (available/partial/missing) rather than stored as a field, matching the canonical derivation in build_session_audio_audit()
duration: ""
verification_result: passed
completed_at: 2026-03-29T23:44:46.111Z
blocker_discovered: false
---

# T03: Added audio_upload_degraded and audio_missing anomaly kinds to RuntimeStatusService with severity escalation and bounded-summary extraction from voice_policy_snapshot

**Added audio_upload_degraded and audio_missing anomaly kinds to RuntimeStatusService with severity escalation and bounded-summary extraction from voice_policy_snapshot**

## What Happened

Extended the support runtime diagnostic pipeline to classify audio anomalies. Added audio_diagnostics field to RuntimeSessionRecord (extracted from voice_policy_snapshot.runtime_metrics.audio_audit). Added _build_fault_items() classification: audio_missing (warning) when all segments failed, audio_upload_degraded (warning/blocking) when partial with severity escalation when >50% failed. Five new unit tests cover all scenarios plus edge cases. All 8 tests pass with no regressions.

## Verification

Ran focused audio tests (-k audio) and full suite: 8/8 pass (3 existing + 5 new). No regressions. Verified _extract_audio_diagnostics() handles missing/empty/malformed voice_policy_snapshot gracefully.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py -v -k audio` | 0 | ✅ pass | 6900ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py -v` | 0 | ✅ pass | 5800ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/support/services/runtime_status_service.py`
- `backend/tests/unit/test_support_runtime_service.py`


## Deviations
None.

## Known Issues
None.
