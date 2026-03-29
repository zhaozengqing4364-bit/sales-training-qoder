---
id: T02
parent: S01
milestone: M008
provides: []
requires: []
affects: []
key_files: ["backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py", "backend/src/sales_bot/websocket/components/stepfun_helpers.py", "backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py", "backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py", "backend/src/sales_bot/websocket/stepfun_realtime_handler.py", "backend/tests/unit/test_stepfun_runtime_metrics_helpers.py", "backend/tests/unit/test_stepfun_realtime_handler.py", ".gsd/milestones/M008/slices/S01/tasks/T02-SUMMARY.md"]
key_decisions: ["Reused the existing knowledge runtime-metrics seam as the only persistence channel for retrieval ledger entries instead of introducing a second write path.", "Rejected malformed persisted recent_attempts payloads at snapshot-merge time so invalid ledger state does not half-write PracticeSession.voice_policy_snapshot."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh verification passed for the T01 helper/searcher command and the T02 runtime-metrics/handler command. The downstream slice-level read-side command still fails because the planned T03 test file does not exist yet, which is consistent with this being an intermediate task rather than a slice close-out."
completed_at: 2026-03-29T15:57:04.534Z
blocker_discovered: false
---

# T02: Wired provider-neutral retrieval ledger events through the existing StepFun runtime-metrics persistence path with copy-on-write snapshot merges and handler warning-only failure behavior.

> Wired provider-neutral retrieval ledger events through the existing StepFun runtime-metrics persistence path with copy-on-write snapshot merges and handler warning-only failure behavior.

## What Happened
---
id: T02
parent: S01
milestone: M008
key_files:
  - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
  - backend/src/sales_bot/websocket/components/stepfun_helpers.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_runtime_metrics_helpers.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - .gsd/milestones/M008/slices/S01/tasks/T02-SUMMARY.md
key_decisions:
  - Reused the existing knowledge runtime-metrics seam as the only persistence channel for retrieval ledger entries instead of introducing a second write path.
  - Rejected malformed persisted recent_attempts payloads at snapshot-merge time so invalid ledger state does not half-write PracticeSession.voice_policy_snapshot.
duration: ""
verification_result: mixed
completed_at: 2026-03-29T15:57:04.537Z
blocker_discovered: false
---

# T02: Wired provider-neutral retrieval ledger events through the existing StepFun runtime-metrics persistence path with copy-on-write snapshot merges and handler warning-only failure behavior.

**Wired provider-neutral retrieval ledger events through the existing StepFun runtime-metrics persistence path with copy-on-write snapshot merges and handler warning-only failure behavior.**

## What Happened

T02 could not be real on the original code because T01 still had no ledger payload to persist, so I finished that dependency inside the same slice boundary first: helper/searcher code now builds one bounded provider-neutral ledger_event for missing-query, no-kb, kb-not-ready, miss, hit, and failure paths. I then extended the planned T02 seam so apply_knowledge_runtime_metric(...) and StepFunRealtimeHandler._record_knowledge_runtime_metric(...) carry that event through the existing runtime-metrics path, and merge_runtime_metrics_snapshot(...) deep-copies the knowledge metrics into a new snapshot object while rejecting malformed persisted recent_attempts payloads. Focused runtime-metrics and handler tests now prove copy-on-write persistence, bounded ledger retention, and the preexisting warning-only failure surface when persistence raises after the in-memory update.

## Verification

Fresh verification passed for the T01 helper/searcher command and the T02 runtime-metrics/handler command. The downstream slice-level read-side command still fails because the planned T03 test file does not exist yet, which is consistent with this being an intermediate task rather than a slice close-out.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_knowledge_helpers.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` | 0 | ✅ pass | 69200ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_runtime_metrics_helpers.py backend/tests/unit/test_stepfun_realtime_handler.py` | 0 | ✅ pass | 116500ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py` | 4 | ❌ fail | 11600ms |


## Deviations

Pulled the unfinished T01 helper/searcher seam into this unit because T02 had no truthful ledger_event payload to persist. I kept the deviation inside the same slice boundary and did not widen into T03 route-reader work.

## Known Issues

The third slice-level verification command still fails immediately because backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py is not present on disk yet; that downstream read-side proof remains T03 work. Backend pytest also still emits the existing project coverage warning (Module src was never imported / No data was collected), but the passing task commands exit 0.

## Files Created/Modified

- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
- `backend/src/sales_bot/websocket/components/stepfun_helpers.py`
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
- `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_runtime_metrics_helpers.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `.gsd/milestones/M008/slices/S01/tasks/T02-SUMMARY.md`


## Deviations
Pulled the unfinished T01 helper/searcher seam into this unit because T02 had no truthful ledger_event payload to persist. I kept the deviation inside the same slice boundary and did not widen into T03 route-reader work.

## Known Issues
The third slice-level verification command still fails immediately because backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py is not present on disk yet; that downstream read-side proof remains T03 work. Backend pytest also still emits the existing project coverage warning (Module src was never imported / No data was collected), but the passing task commands exit 0.
