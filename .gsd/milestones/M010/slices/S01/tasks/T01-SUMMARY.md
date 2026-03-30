---
id: T01
parent: S01
milestone: M010
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/session_evidence.py", "backend/src/common/conversation/replay.py", "backend/src/common/conversation/schemas.py", "backend/src/common/db/schemas.py", "backend/src/common/api/practice.py", "backend/tests/unit/test_session_evidence_service.py", "backend/tests/contract/test_practice_evidence_contract.py", ".gsd/milestones/M010/slices/S01/tasks/T01-SUMMARY.md"]
key_decisions: ["Built `conclusion_evidence` inside `SessionEvidenceService.build_projection()` so report and replay share one provenance bundle.", "Kept the new field additive and `null` for presentation sessions to preserve backward compatibility."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task verification command from the plan: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py -x -q`. The suite passed with 37 tests green."
completed_at: 2026-03-30T01:29:12.878Z
blocker_discovered: false
---

# T01: Added projection-backed conclusion provenance to completed-session report and replay responses.

> Added projection-backed conclusion provenance to completed-session report and replay responses.

## What Happened
---
id: T01
parent: S01
milestone: M010
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/db/schemas.py
  - backend/src/common/api/practice.py
  - backend/tests/unit/test_session_evidence_service.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - .gsd/milestones/M010/slices/S01/tasks/T01-SUMMARY.md
key_decisions:
  - Built `conclusion_evidence` inside `SessionEvidenceService.build_projection()` so report and replay share one provenance bundle.
  - Kept the new field additive and `null` for presentation sessions to preserve backward compatibility.
duration: ""
verification_result: passed
completed_at: 2026-03-30T01:29:12.881Z
blocker_discovered: false
---

# T01: Added projection-backed conclusion provenance to completed-session report and replay responses.

**Added projection-backed conclusion provenance to completed-session report and replay responses.**

## What Happened

Implemented a shared completed-session conclusion provenance bundle in `SessionEvidenceService` and threaded it through the existing report and replay read paths. Added the new additive `conclusion_evidence` field to the report and replay schemas so FastAPI preserves it, and added structured `projection_conclusion_evidence_built` logging with retrieval/transcript/audio availability flags. Extended focused contract and unit coverage, then updated a few logger assertions because the new observability event adds a second `info` log per projection build. The final focused pytest gate passed.

## Verification

Ran the task verification command from the plan: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py -x -q`. The suite passed with 37 tests green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py -x -q` | 0 | ✅ pass | 12530ms |


## Deviations

None.

## Known Issues

Knowledge-check parity is not implemented in this task; it remains for T02.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/schemas.py`
- `backend/src/common/db/schemas.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_session_evidence_service.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `.gsd/milestones/M010/slices/S01/tasks/T01-SUMMARY.md`


## Deviations
None.

## Known Issues
Knowledge-check parity is not implemented in this task; it remains for T02.
