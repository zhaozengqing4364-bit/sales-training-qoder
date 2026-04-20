# S01: 会话检索账本落库 — UAT

**Milestone:** M008
**Written:** 2026-03-29T16:45:01.293Z

# S01 UAT: 会话检索账本落库

## Preconditions
- Backend venv active with all dependencies installed
- No external services required (all tests use in-memory mocks/fixtures)

## Test Case 1: Provider-neutral ledger normalization — hit path

**Objective:** Verify that a successful internal knowledge search produces a bounded ledger event with correct fields.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py::test_search_internal_knowledge_records_hit_ledger_event_from_transformed_results -v`
2. Confirm exit code 0

**Expected outcome:** Test passes, proving the hit ledger event contains normalized query, status=`hit`, result_count > 0, retrieval_mode, and bounded result summaries.

## Test Case 2: Provider-neutral ledger normalization — miss path

**Objective:** Verify that an empty search result produces a truthful miss ledger event.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py::test_search_internal_knowledge_records_miss_ledger_event_with_empty_results -v`
2. Confirm exit code 0

**Expected outcome:** Test passes, proving the miss event has status=`miss`, result_count=0, and empty result summaries.

## Test Case 3: Provider-neutral ledger normalization — failure paths

**Objective:** Verify that missing query, no KB, KB not ready, search failure, and unexpected exception all produce safe bounded failure/no-op events.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -k "missing_query or no_kb or kb_not_ready or search_failed or unexpected_exception" -v`
2. Confirm exit code 0

**Expected outcome:** All tests pass, each producing a truthful ledger event (no raw provider payloads, no unbounded data).

## Test Case 4: Copy-on-write snapshot persistence

**Objective:** Verify that ledger persistence deep-copies the snapshot and never mutates the original object.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_runtime_metrics_helpers.py -v`
2. Confirm exit code 0

**Expected outcome:** All tests pass, including copy-on-write verification tests that prove the original snapshot object is unchanged after a merge.

## Test Case 5: Handler warning-only failure surface

**Objective:** Verify that persistence failures in the handler log a warning but do not crash or change training session status.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py -k "knowledge_runtime" -v`
2. Confirm exit code 0

**Expected outcome:** Tests pass proving handler catches persistence errors, logs warnings, and keeps the training session running.

## Test Case 6: Read-side ledger fallback

**Objective:** Verify that diagnostics fall back to the latest valid recent_attempts entry when flat fields are stale.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v`
2. Confirm exit code 0

**Expected outcome:** Tests pass proving that when flat last_* fields are missing or stale, the latest valid ledger entry fills the gap truthfully.

## Test Case 7: Route-level frozen ref proof

**Objective:** Verify that runtime-metrics churn does not change voice_policy_snapshot_ref across detail/report/replay reads.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py -v`
2. Confirm exit code 0

**Expected outcome:** All tests pass, including snapshot-ref immutability assertions and route-level contract proofs.

## Test Case 8: Full regression pack

**Objective:** Run the entire S01 verification suite to confirm nothing regresses.

**Steps:**
1. Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_knowledge_helpers.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py backend/tests/unit/test_stepfun_runtime_metrics_helpers.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py`
2. Confirm exit code 0

**Expected outcome:** All 121 tests pass. No regressions in existing flat metrics, snapshot semantics, or route contracts.

## Edge Cases Covered
- Malformed persisted recent_attempts are rejected at merge time
- Ledger cap is enforced on repeated writes
- Missing query, no KB, KB not ready, search failure, and unexpected exception all produce bounded truthful events
- Stale flat fields are correctly overridden by valid ledger entries
- Frozen snapshot ref survives runtime-metrics churn
