---
id: T04
parent: S02
milestone: M008
provides: []
requires: []
affects: []
key_files:
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
key_decisions:
  - "Contract tests assert exact structural parity (all canonical keys, latest_attempt fields, recent_attempts order) while integration tests verify through real HTTP route handlers"
  - "Claim-truth independence tested at contract level with precise weak_evidence assertion, integration level with presence+orthogonality assertion"
  - "Fixture helper _make_voice_policy_snapshot_with_retrieval_ledger uses chronological order (miss-first, hit-last) to match build_retrieval_facts reversal logic where latest_attempt = recent_attempts[-1] = hit entry"
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: passed
completed_at: 2026-03-30T01:51:00Z
blocker_discovered: false
---

# T04: Contract/integration proof: same-session retrieval facts parity

**Contract and integration tests proving report/knowledge-check retrieval_facts parity and claim-truth independence for completed sales sessions**

## What Happened

Added 5 tests (3 contract + 2 integration) proving the S02 parity guarantee. The same completed sales session returns consistent `retrieval_facts` through both report projection and knowledge-check diagnostics. Both surfaces carry identical structure including `knowledge_base_ids` and `result_summaries` on hit and miss entries.

Claim-truth independence is explicitly tested: a scenario where retrieval status is "hit" but claim_truth is "weak_evidence" — both fields are present and correct on both surfaces without one overriding the other.

## Verification

Ran `-k 'retrieval_facts'` across both test suites. 5/5 pass. No regressions from existing tests. Full combined suite green (21 tests existing, all passing).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_voice_runtime_session_snapshot.py -v -k retrieval_facts` | 0 | ✅ pass | 5800ms |

## Deviations
None.

## Known Issues
None.

## Files Created/Modified
- `backend/tests/contract/test_practice_evidence_contract.py` — Added helper `_make_voice_policy_snapshot_with_retrieval_ledger` and 3 contract tests for retrieval_facts parity, claim-truth independence, and miss status parity
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — Added 2 integration tests for retrieval_facts parity and claim-truth independence through actual route handlers
