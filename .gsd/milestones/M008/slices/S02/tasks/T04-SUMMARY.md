---
id: T04
parent: S02
milestone: M008
provides: []
requires: []
affects: []
key_files: ["backend/tests/contract/test_practice_evidence_contract.py", "backend/tests/integration/test_voice_runtime_session_snapshot.py"]
key_decisions: ["Contract tests assert exact structural parity while integration tests verify through real route handlers", "Claim-truth independence tested at both contract and integration layers with different assertion precision levels"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran -k retrieval_facts across both test suites. 5/5 pass. No regressions from existing tests. Full combined suite green across both files (21 tests existing, all passing)."
completed_at: 2026-03-29T17:52:57.614Z
blocker_discovered: false
---

# T04: Contract and integration tests proving report/knowledge-check retrieval_facts parity and claim-truth independence for completed sales sessions

> Contract and integration tests proving report/knowledge-check retrieval_facts parity and claim-truth independence for completed sales sessions

## What Happened
---
id: T04
parent: S02
milestone: M008
key_files:
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
key_decisions:
  - Contract tests assert exact structural parity while integration tests verify through real route handlers
  - Claim-truth independence tested at both contract and integration layers with different assertion precision levels
duration: ""
verification_result: passed
completed_at: 2026-03-29T17:52:57.615Z
blocker_discovered: false
---

# T04: Contract and integration tests proving report/knowledge-check retrieval_facts parity and claim-truth independence for completed sales sessions

**Contract and integration tests proving report/knowledge-check retrieval_facts parity and claim-truth independence for completed sales sessions**

## What Happened

Added 5 tests (3 contract + 2 integration) proving the S02 parity guarantee: the same completed sales session returns consistent retrieval_facts through both report projection and knowledge-check diagnostics. Both surfaces carry identical structure including knowledge_base_ids and result_summaries on hit and miss entries. Claim-truth independence is explicitly tested: retrieval status is hit but claim_truth is weak_evidence coexist without one overriding the other.

## Verification

Ran -k retrieval_facts across both test suites. 5/5 pass. No regressions from existing tests. Full combined suite green across both files (21 tests existing, all passing).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_voice_runtime_session_snapshot.py -v -k retrieval_facts` | 0 | ✅ pass | 5800ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`


## Deviations
None.

## Known Issues
None.
