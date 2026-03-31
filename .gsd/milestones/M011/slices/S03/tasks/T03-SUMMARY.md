---
id: T03
parent: S03
milestone: M011
provides: []
requires: []
affects: []
key_files: ["backend/src/common/knowledge_engine/audit_repo.py", "backend/src/common/knowledge_engine/engine.py", "backend/src/common/knowledge_engine/compat.py", "backend/src/common/knowledge_engine/__init__.py", "backend/tests/unit/common/test_knowledge_answer_audit_repo.py", "backend/tests/unit/common/test_knowledge_answer_engine.py", "backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py", "backend/tests/unit/test_replay_service.py", "backend/tests/unit/test_stepfun_realtime_handler.py", ".gsd/milestones/M011/slices/S03/tasks/T03-SUMMARY.md"]
key_decisions: ["Use a dedicated compatibility mapper to expose audit_run_id/citations/answerability to existing realtime/runtime/replay payloads instead of forcing those consumers onto raw engine DTOs.", "Persist ordered KnowledgeAuditStep payloads per run so audit tables can be queried later from runtime diagnostics/report/replay without reconstructing execution from handler-local state."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the full task-plan verification command once to establish real status; it reached 132/134 passing and exposed two focused failures in the new audit/engine area. Fixed those focused failures, then reran `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py -q` and reached 5/5 passing tests for the new core modules. The broad task-plan verification command still needs a fresh rerun after the remaining runtime integration edits documented in the task summary."
completed_at: 2026-03-31T05:17:47.623Z
blocker_discovered: false
---

# T03: Added a real knowledge-answer engine orchestration path with persisted audit runs plus compatibility helpers that expose audit_run_id, citations, and answerability to existing runtime diagnostics and replay surfaces.

> Added a real knowledge-answer engine orchestration path with persisted audit runs plus compatibility helpers that expose audit_run_id, citations, and answerability to existing runtime diagnostics and replay surfaces.

## What Happened
---
id: T03
parent: S03
milestone: M011
key_files:
  - backend/src/common/knowledge_engine/audit_repo.py
  - backend/src/common/knowledge_engine/engine.py
  - backend/src/common/knowledge_engine/compat.py
  - backend/src/common/knowledge_engine/__init__.py
  - backend/tests/unit/common/test_knowledge_answer_audit_repo.py
  - backend/tests/unit/common/test_knowledge_answer_engine.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - .gsd/milestones/M011/slices/S03/tasks/T03-SUMMARY.md
key_decisions:
  - Use a dedicated compatibility mapper to expose audit_run_id/citations/answerability to existing realtime/runtime/replay payloads instead of forcing those consumers onto raw engine DTOs.
  - Persist ordered KnowledgeAuditStep payloads per run so audit tables can be queried later from runtime diagnostics/report/replay without reconstructing execution from handler-local state.
duration: ""
verification_result: mixed
completed_at: 2026-03-31T05:17:47.624Z
blocker_discovered: false
---

# T03: Added a real knowledge-answer engine orchestration path with persisted audit runs plus compatibility helpers that expose audit_run_id, citations, and answerability to existing runtime diagnostics and replay surfaces.

**Added a real knowledge-answer engine orchestration path with persisted audit runs plus compatibility helpers that expose audit_run_id, citations, and answerability to existing runtime diagnostics and replay surfaces.**

## What Happened

Implemented the core T03 deliverables under timeout recovery discipline: added `backend/src/common/knowledge_engine/audit_repo.py` for persistent audit rows, replaced the placeholder `backend/src/common/knowledge_engine/engine.py` with a real config-driven orchestration seam (`config -> resolve -> classify -> plan -> retrieve -> rank -> answerability -> assemble -> audit`), added `backend/src/common/knowledge_engine/compat.py` to map engine DTOs back into existing StepFun/runtime/replay payloads, and exported the new modules from `backend/src/common/knowledge_engine/__init__.py`. Added focused tests for audit persistence and engine orchestration, and extended realtime/runtime-diagnostics/replay tests to assert `audit_run_id` is preserved across compatibility seams. During hard-timeout recovery I prioritized durable artifacts over speculative final wiring, so the remaining unfinished work is explicitly documented: `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` still needs to complete its migration onto the engine/compat seam, and `backend/src/common/api/practice.py` still needs a local `live_knowledge_answer_diagnostics` binding in the knowledge-check endpoint before the full task verification can go green again.

## Verification

Ran the full task-plan verification command once to establish real status; it reached 132/134 passing and exposed two focused failures in the new audit/engine area. Fixed those focused failures, then reran `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py -q` and reached 5/5 passing tests for the new core modules. The broad task-plan verification command still needs a fresh rerun after the remaining runtime integration edits documented in the task summary.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py -q` | 1 | ❌ fail | 2350ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py -q` | 0 | ✅ pass | 250ms |


## Deviations

Switched from full completion to recovery-first artifact writing after the hard-timeout warning. Core engine/audit modules were completed and verified, but final runtime entrypoint wiring in `stepfun_internal_knowledge_searcher.py` and `common/api/practice.py` was intentionally left as explicit resume work instead of making low-confidence edits under timeout pressure.

## Known Issues

The full task-plan verification command is not yet green. `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` still contains partial migration work toward the engine/compat seam, and `backend/src/common/api/practice.py` knowledge-check endpoint still references `live_knowledge_answer_diagnostics` without a visible local assignment in the current file state.

## Files Created/Modified

- `backend/src/common/knowledge_engine/audit_repo.py`
- `backend/src/common/knowledge_engine/engine.py`
- `backend/src/common/knowledge_engine/compat.py`
- `backend/src/common/knowledge_engine/__init__.py`
- `backend/tests/unit/common/test_knowledge_answer_audit_repo.py`
- `backend/tests/unit/common/test_knowledge_answer_engine.py`
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `.gsd/milestones/M011/slices/S03/tasks/T03-SUMMARY.md`


## Deviations
Switched from full completion to recovery-first artifact writing after the hard-timeout warning. Core engine/audit modules were completed and verified, but final runtime entrypoint wiring in `stepfun_internal_knowledge_searcher.py` and `common/api/practice.py` was intentionally left as explicit resume work instead of making low-confidence edits under timeout pressure.

## Known Issues
The full task-plan verification command is not yet green. `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` still contains partial migration work toward the engine/compat seam, and `backend/src/common/api/practice.py` knowledge-check endpoint still references `live_knowledge_answer_diagnostics` without a visible local assignment in the current file state.
