---
id: T02
parent: S01
milestone: M010
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/runtime_diagnostics.py", "backend/src/common/api/practice.py", "backend/tests/contract/test_conclusion_evidence_parity.py", ".gsd/milestones/M010/slices/S01/tasks/T02-SUMMARY.md"]
key_decisions: ["Kept knowledge-check on the existing SessionEvidenceService.get_projection(...) read path and passed projection.value.conclusion_evidence through build_session_runtime_diagnostics(...) instead of rebuilding provenance inside diagnostics.", "Locked route-family parity with a dedicated contract module that compares report, replay, and knowledge-check directly for sales happy-path, degraded, and presentation sessions."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task verification command from the plan: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_conclusion_evidence_parity.py tests/contract/test_practice_evidence_contract.py -x -q` and confirmed 29 tests passed. Then ran `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract -x -q` to verify backward compatibility across the existing contract suite; all 83 contract tests passed."
completed_at: 2026-03-30T01:57:26.502Z
blocker_discovered: false
---

# T02: Mirrored projection-backed conclusion evidence into knowledge-check and added cross-route parity contracts.

> Mirrored projection-backed conclusion evidence into knowledge-check and added cross-route parity contracts.

## What Happened
---
id: T02
parent: S01
milestone: M010
key_files:
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/api/practice.py
  - backend/tests/contract/test_conclusion_evidence_parity.py
  - .gsd/milestones/M010/slices/S01/tasks/T02-SUMMARY.md
key_decisions:
  - Kept knowledge-check on the existing SessionEvidenceService.get_projection(...) read path and passed projection.value.conclusion_evidence through build_session_runtime_diagnostics(...) instead of rebuilding provenance inside diagnostics.
  - Locked route-family parity with a dedicated contract module that compares report, replay, and knowledge-check directly for sales happy-path, degraded, and presentation sessions.
duration: ""
verification_result: passed
completed_at: 2026-03-30T01:57:26.514Z
blocker_discovered: false
---

# T02: Mirrored projection-backed conclusion evidence into knowledge-check and added cross-route parity contracts.

**Mirrored projection-backed conclusion evidence into knowledge-check and added cross-route parity contracts.**

## What Happened

Extended the completed-session knowledge-check path to reuse the same SessionEvidenceService projection that already feeds report and replay, extracted projection.value.conclusion_evidence in the route, and threaded it through build_session_runtime_diagnostics(...) so the diagnostics payload now exposes the same provenance bundle. Added backend/tests/contract/test_conclusion_evidence_parity.py to seed canonical completed sales and presentation sessions, then assert report, replay, and knowledge-check stay aligned for the happy path, degraded sales sessions without retrieval/audio evidence, and presentation sessions where the field must remain null. Verified the targeted task gate and the full backend contract suite after tightening the degraded fixture so it truly exercised a no-audio path rather than inheriting audio availability from message durations.

## Verification

Ran the task verification command from the plan: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_conclusion_evidence_parity.py tests/contract/test_practice_evidence_contract.py -x -q` and confirmed 29 tests passed. Then ran `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract -x -q` to verify backward compatibility across the existing contract suite; all 83 contract tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_conclusion_evidence_parity.py tests/contract/test_practice_evidence_contract.py -x -q` | 0 | ✅ pass | 45300ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract -x -q` | 0 | ✅ pass | 45300ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/tests/contract/test_conclusion_evidence_parity.py`
- `.gsd/milestones/M010/slices/S01/tasks/T02-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
