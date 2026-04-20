---
id: T01
parent: S02
milestone: M008
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/runtime_diagnostics.py", "backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py"]
key_decisions: ["Extracted _derive_retrieval_status_and_summary() to prevent vocabulary drift between build_retrieval_facts and build_session_runtime_diagnostics", "Replicated bounds from stepfun_knowledge_helpers (MAX 10 entries, 8 KB IDs, 3 summaries, 240-char snippet) as module-level constants with comments referencing the source"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v` — all 20 tests pass (exit code 0, 2.92s)."
completed_at: 2026-03-29T17:16:43.530Z
blocker_discovered: false
---

# T01: Add build_retrieval_facts() shared read model that preserves knowledge_base_ids and result_summaries from persisted ledger

> Add build_retrieval_facts() shared read model that preserves knowledge_base_ids and result_summaries from persisted ledger

## What Happened
---
id: T01
parent: S02
milestone: M008
key_files:
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
key_decisions:
  - Extracted _derive_retrieval_status_and_summary() to prevent vocabulary drift between build_retrieval_facts and build_session_runtime_diagnostics
  - Replicated bounds from stepfun_knowledge_helpers (MAX 10 entries, 8 KB IDs, 3 summaries, 240-char snippet) as module-level constants with comments referencing the source
duration: ""
verification_result: passed
completed_at: 2026-03-29T17:16:43.531Z
blocker_discovered: false
---

# T01: Add build_retrieval_facts() shared read model that preserves knowledge_base_ids and result_summaries from persisted ledger

**Add build_retrieval_facts() shared read model that preserves knowledge_base_ids and result_summaries from persisted ledger**

## What Happened

Implemented `build_retrieval_facts(voice_policy_snapshot)` as a pure function in `runtime_diagnostics.py` — the single normalization point for retrieval truth. Added `_normalize_retrieval_attempt_full()` that preserves `knowledge_base_ids` (bounded to 8) and `result_summaries` (bounded to 3, snippet ≤ 240 chars), closing the key gap vs the existing lean normalizer. Extracted `_derive_retrieval_status_and_summary()` to deduplicate the status/summary if-else block between the new function and existing `build_session_runtime_diagnostics`. Added 17 unit tests covering hit/miss/failure/empty/malformed/bounded/disabled/no-kb/not-ready scenarios. All 20 tests (3 existing + 17 new) pass.

## Verification

Ran `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v` — all 20 tests pass (exit code 0, 2.92s).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v` | 0 | ✅ pass | 2920ms |


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
