---
id: T02
parent: S02
milestone: M008
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/session_evidence.py", "backend/tests/unit/test_session_evidence_service.py"]
key_decisions: ["Gated retrieval_facts overlay on resolved_scenario_type==sales to avoid polluting presentation sessions which have a separate review path", "Used the existing copy-on-write dict spread pattern consistent with how claim_truth/main_issue/next_goal are overlaid"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran three verification commands: (1) T02-specific filter `-k 'retrieval_facts'` — 2 selected tests pass; (2) full session_evidence suite — 10/10 pass; (3) T01 runtime_diagnostics suite — 20/20 pass. All green, no regressions."
completed_at: 2026-03-29T17:23:34.521Z
blocker_discovered: false
---

# T02: Wire build_retrieval_facts() into SessionEvidenceService.build_projection for sales sessions as copy-on-write overlay

> Wire build_retrieval_facts() into SessionEvidenceService.build_projection for sales sessions as copy-on-write overlay

## What Happened
---
id: T02
parent: S02
milestone: M008
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/tests/unit/test_session_evidence_service.py
key_decisions:
  - Gated retrieval_facts overlay on resolved_scenario_type==sales to avoid polluting presentation sessions which have a separate review path
  - Used the existing copy-on-write dict spread pattern consistent with how claim_truth/main_issue/next_goal are overlaid
duration: ""
verification_result: passed
completed_at: 2026-03-29T17:23:34.523Z
blocker_discovered: false
---

# T02: Wire build_retrieval_facts() into SessionEvidenceService.build_projection for sales sessions as copy-on-write overlay

**Wire build_retrieval_facts() into SessionEvidenceService.build_projection for sales sessions as copy-on-write overlay**

## What Happened

Imported `build_retrieval_facts` from `common.conversation.runtime_diagnostics` into `session_evidence.py`. Added a sales-gated overlay block in `build_projection()` that calls `build_retrieval_facts(session.voice_policy_snapshot)` and merges the result into `projection_snapshot` using the existing copy-on-write dict spread pattern. Also added `retrieval_facts_status` to the `practice_session_evidence_projection_built` structured log. Three new unit tests prove: (1) retrieval_facts appears for completed sales sessions with retrieval ledger data, (2) the persisted session.effectiveness_snapshot is not mutated, (3) sessions without voice_policy_snapshot gracefully skip. All 10 session_evidence tests and 20 runtime_diagnostics tests pass.

## Verification

Ran three verification commands: (1) T02-specific filter `-k 'retrieval_facts'` — 2 selected tests pass; (2) full session_evidence suite — 10/10 pass; (3) T01 runtime_diagnostics suite — 20/20 pass. All green, no regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -v -k 'retrieval_facts'` | 0 | ✅ pass | 2770ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -v` | 0 | ✅ pass | 2730ms |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v` | 0 | ✅ pass | 2810ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py`
- `backend/tests/unit/test_session_evidence_service.py`


## Deviations
None.

## Known Issues
None.
