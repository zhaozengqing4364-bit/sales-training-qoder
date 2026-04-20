---
id: T03
parent: S02
milestone: M008
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/runtime_diagnostics.py", "backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py"]
key_decisions: ["retrieval_facts extracted from projection_effectiveness_snapshot only when live_runtime_active=False, preserving single-source-of-truth where live sessions derive truth from the live handler", "retrieval_facts placed after upstream_unstable in the return dict to keep the new field at the boundary"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `-k 'retrieval_facts'` filter — 4 new tests pass. Ran full combined suite (runtime_diagnostics + session_evidence) — 34/34 pass. No regressions."
completed_at: 2026-03-29T17:29:08.457Z
blocker_discovered: false
---

# T03: Added retrieval_facts passthrough in build_session_runtime_diagnostics so knowledge-check and report routes return identical retrieval truth for completed sessions

> Added retrieval_facts passthrough in build_session_runtime_diagnostics so knowledge-check and report routes return identical retrieval truth for completed sessions

## What Happened
---
id: T03
parent: S02
milestone: M008
key_files:
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
key_decisions:
  - retrieval_facts extracted from projection_effectiveness_snapshot only when live_runtime_active=False, preserving single-source-of-truth where live sessions derive truth from the live handler
  - retrieval_facts placed after upstream_unstable in the return dict to keep the new field at the boundary
duration: ""
verification_result: passed
completed_at: 2026-03-29T17:29:08.458Z
blocker_discovered: false
---

# T03: Added retrieval_facts passthrough in build_session_runtime_diagnostics so knowledge-check and report routes return identical retrieval truth for completed sessions

**Added retrieval_facts passthrough in build_session_runtime_diagnostics so knowledge-check and report routes return identical retrieval truth for completed sessions**

## What Happened

Extended `build_session_runtime_diagnostics(...)` to extract `retrieval_facts` from `projection_effectiveness_snapshot` when `live_runtime_active=False`. The field is passed through verbatim (not recomputed), preserving the single-source-of-truth property established in T01 and wired into projection in T02. For live sessions, `retrieval_facts` is always `None` — live truth comes from the handler. Added 4 unit tests proving reuse, live-session isolation, backward compatibility, and live-session ignores projection. All 34 tests pass across runtime_diagnostics and session_evidence suites.

## Verification

Ran `-k 'retrieval_facts'` filter — 4 new tests pass. Ran full combined suite (runtime_diagnostics + session_evidence) — 34/34 pass. No regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v -k 'retrieval_facts'` | 0 | ✅ pass | 2710ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py tests/unit/test_session_evidence_service.py -v` | 0 | ✅ pass | 2710ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`


## Deviations
None.

## Known Issues
None.
