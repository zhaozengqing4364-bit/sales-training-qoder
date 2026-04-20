---
id: T03
parent: S01
milestone: M008
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/runtime_diagnostics.py", "backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py", "backend/tests/integration/test_voice_runtime_session_snapshot.py", "backend/tests/contract/test_practice_evidence_contract.py", ".gsd/KNOWLEDGE.md", ".gsd/DECISIONS.md", ".gsd/milestones/M008/slices/S01/tasks/T03-SUMMARY.md"]
key_decisions: ["Prefer the latest valid runtime_metrics.knowledge_retrieval.recent_attempts entry only as a fallback for missing or stale flat last_* fields.", "Keep the fix inside build_session_runtime_diagnostics instead of adding a new audit route or changing report/replay payloads.", "Normalize away optional agent_persona_override_config:null in contract assertions so snapshot-ref tests keep checking the real immutability invariant."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Reproduced the gap with a new focused unit file, implemented the minimal reader-side fallback in backend/src/common/conversation/runtime_diagnostics.py, and reran the full task-plan verification pack. The final command passed with 24 tests green across the new unit file plus the route-level integration and contract proofs. lsp diagnostics also reported no diagnostics for the modified source and test files."
completed_at: 2026-03-29T16:33:41.599Z
blocker_discovered: false
---

# T03: Kept current session diagnostics truthful by falling back to persisted retrieval ledger attempts while preserving route contracts and frozen snapshot refs.

> Kept current session diagnostics truthful by falling back to persisted retrieval ledger attempts while preserving route contracts and frozen snapshot refs.

## What Happened
---
id: T03
parent: S01
milestone: M008
key_files:
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
  - .gsd/milestones/M008/slices/S01/tasks/T03-SUMMARY.md
key_decisions:
  - Prefer the latest valid runtime_metrics.knowledge_retrieval.recent_attempts entry only as a fallback for missing or stale flat last_* fields.
  - Keep the fix inside build_session_runtime_diagnostics instead of adding a new audit route or changing report/replay payloads.
  - Normalize away optional agent_persona_override_config:null in contract assertions so snapshot-ref tests keep checking the real immutability invariant.
duration: ""
verification_result: passed
completed_at: 2026-03-29T16:33:41.600Z
blocker_discovered: false
---

# T03: Kept current session diagnostics truthful by falling back to persisted retrieval ledger attempts while preserving route contracts and frozen snapshot refs.

**Kept current session diagnostics truthful by falling back to persisted retrieval ledger attempts while preserving route contracts and frozen snapshot refs.**

## What Happened

T03 closed the read-side gap left after T02. The persisted provider-neutral retrieval ledger already lived under practice_sessions.voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts, but current-session diagnostics still trusted flat last_* fields first and could report stale or empty values when those flat fields were missing. I wrote a focused unit regression that reproduced the failure for completed search_failed and malformed-ledger scenarios, confirmed the red phase, then added a bounded fallback path inside build_session_runtime_diagnostics that scans recent_attempts backwards, skips malformed entries, and uses the latest valid attempt only to fill missing or obviously stale last_status/last_query/last_result_count/last_error/last_retrieval_mode/updated_at fields. I then extended the integration and contract suites so the route family proves two things together: the persisted ledger is still readable on current session/detail surfaces, and detail/report/replay keep the same voice_policy_snapshot_ref while runtime_metrics churn underneath. The final focused verification pack passed cleanly and lsp diagnostics reported no file-level diagnostics on the touched files.

## Verification

Reproduced the gap with a new focused unit file, implemented the minimal reader-side fallback in backend/src/common/conversation/runtime_diagnostics.py, and reran the full task-plan verification pack. The final command passed with 24 tests green across the new unit file plus the route-level integration and contract proofs. lsp diagnostics also reported no diagnostics for the modified source and test files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 4710ms |


## Deviations

None.

## Known Issues

Focused pytest still emits the existing pytest-cov warnings about `Module src was never imported` / `No data was collected`; the targeted pack itself passes and this task did not change that coverage configuration.

## Files Created/Modified

- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
- `.gsd/milestones/M008/slices/S01/tasks/T03-SUMMARY.md`


## Deviations
None.

## Known Issues
Focused pytest still emits the existing pytest-cov warnings about `Module src was never imported` / `No data was collected`; the targeted pack itself passes and this task did not change that coverage configuration.
