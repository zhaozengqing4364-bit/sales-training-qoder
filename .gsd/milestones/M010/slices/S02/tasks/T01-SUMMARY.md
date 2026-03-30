---
id: T01
parent: S02
milestone: M010
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/session_evidence.py", "backend/src/common/conversation/runtime_diagnostics.py", "backend/src/common/api/practice.py", "backend/src/common/conversation/replay.py", "backend/src/common/db/schemas.py", "backend/tests/contract/test_conclusion_evidence_parity.py", "backend/tests/unit/test_session_evidence_service.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M010/slices/S02/tasks/T01-SUMMARY.md"]
key_decisions: ["Build evidence_degradation once on SessionEvidenceProjection and mirror it into knowledge-check instead of recomputing per route.", "Use canonical degraded tokens on the layer payload itself (no_retrieval_facts, no_scored_turns, audio reason token, report_generation_failed).", "Record the replay-schema serialization seam in .gsd/KNOWLEDGE.md because replay can silently drop new projection fields even when ReplayService includes them in the payload."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-level pytest suite from the slice plan multiple times. Fixed test-file and practice.py patch artifacts until verification reached a real functional failure. Current verified state: projection builder emits projection_evidence_degradation_built; report and knowledge-check expose evidence_degradation; replay payload builder attaches the field; replay response still drops it at serialization time because the replay schema layer is missing evidence_degradation. Also ran py_compile on the touched Python files successfully."
completed_at: 2026-03-30T03:06:13.035Z
blocker_discovered: true
---

# T01: Added projection-level evidence_degradation and partial route wiring, but replay parity is still blocked by the replay response schema dropping the new field.

> Added projection-level evidence_degradation and partial route wiring, but replay parity is still blocked by the replay response schema dropping the new field.

## What Happened
---
id: T01
parent: S02
milestone: M010
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/api/practice.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/db/schemas.py
  - backend/tests/contract/test_conclusion_evidence_parity.py
  - backend/tests/unit/test_session_evidence_service.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M010/slices/S02/tasks/T01-SUMMARY.md
key_decisions:
  - Build evidence_degradation once on SessionEvidenceProjection and mirror it into knowledge-check instead of recomputing per route.
  - Use canonical degraded tokens on the layer payload itself (no_retrieval_facts, no_scored_turns, audio reason token, report_generation_failed).
  - Record the replay-schema serialization seam in .gsd/KNOWLEDGE.md because replay can silently drop new projection fields even when ReplayService includes them in the payload.
duration: ""
verification_result: mixed
completed_at: 2026-03-30T03:06:13.043Z
blocker_discovered: true
---

# T01: Added projection-level evidence_degradation and partial route wiring, but replay parity is still blocked by the replay response schema dropping the new field.

**Added projection-level evidence_degradation and partial route wiring, but replay parity is still blocked by the replay response schema dropping the new field.**

## What Happened

Implemented a new projection-level evidence_degradation taxonomy in backend/src/common/conversation/session_evidence.py, including a builder that derives retrieval/transcript/audio/enhanced_report layers from conclusion provenance and session report state, plus a projection_evidence_degradation_built structured log. Wired the new field into SessionReport/report responses and knowledge-check diagnostics, and attached it in ReplayService payload construction. Extended contract and unit tests for degradation scenarios and updated logger expectations. Verification progressed from syntax/patch-artifact failures to one real integration failure: report and knowledge-check return evidence_degradation, but replay still serializes it as null/missing because backend/src/common/conversation/schemas.py replay response models do not declare the new field, so FastAPI/Pydantic trims it. This makes cross-route parity incomplete and plan-invalidating for the remainder of the task as written.

## Verification

Ran the task-level pytest suite from the slice plan multiple times. Fixed test-file and practice.py patch artifacts until verification reached a real functional failure. Current verified state: projection builder emits projection_evidence_degradation_built; report and knowledge-check expose evidence_degradation; replay payload builder attaches the field; replay response still drops it at serialization time because the replay schema layer is missing evidence_degradation. Also ran py_compile on the touched Python files successfully.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q` | 1 | ❌ fail | 30200ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q` | 1 | ❌ fail | 57900ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q` | 1 | ❌ fail | 30200ms |
| 4 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q` | 1 | ❌ fail | 16600ms |
| 5 | `backend/venv/bin/python -m py_compile backend/tests/contract/test_conclusion_evidence_parity.py backend/src/common/api/practice.py backend/src/common/conversation/session_evidence.py backend/src/common/conversation/runtime_diagnostics.py backend/src/common/conversation/replay.py backend/tests/unit/test_session_evidence_service.py` | 0 | ✅ pass | 1200ms |


## Deviations

Stopped before fixing backend/src/common/conversation/schemas.py and before running the second slice verification command because the recovery budget was exhausted and the replay-schema gap made the task contract incomplete. The summary captures the exact remaining seam for the next pass.

## Known Issues

Replay parity is still broken because backend/src/common/conversation/schemas.py replay response models do not yet declare evidence_degradation, so replay serializes the field as null/missing even though ReplayService adds it to the response dict.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/db/schemas.py`
- `backend/tests/contract/test_conclusion_evidence_parity.py`
- `backend/tests/unit/test_session_evidence_service.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M010/slices/S02/tasks/T01-SUMMARY.md`


## Deviations
Stopped before fixing backend/src/common/conversation/schemas.py and before running the second slice verification command because the recovery budget was exhausted and the replay-schema gap made the task contract incomplete. The summary captures the exact remaining seam for the next pass.

## Known Issues
Replay parity is still broken because backend/src/common/conversation/schemas.py replay response models do not yet declare evidence_degradation, so replay serializes the field as null/missing even though ReplayService adds it to the response dict.
