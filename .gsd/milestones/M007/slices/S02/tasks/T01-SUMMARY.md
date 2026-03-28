---
id: T01
parent: S02
milestone: M007
provides: []
requires: []
affects: []
key_files: ["backend/src/common/effectiveness/evaluator.py", "backend/src/common/effectiveness/__init__.py", "backend/src/common/conversation/runtime_diagnostics.py", "backend/src/common/api/practice.py", "backend/src/sales_bot/websocket/stepfun_realtime_handler.py", "backend/src/sales_bot/websocket/components/capability_processor.py", "backend/src/sales_bot/websocket/enhanced_handler.py", "backend/tests/unit/test_stepfun_realtime_handler.py", "backend/tests/unit/test_enhanced_handler_coach_health.py", "backend/tests/contract/test_practice_evidence_contract.py"]
key_decisions: ["Use one evaluator-backed `live_session_summary` object as the active-session authority for `main_issue`, `next_goal`, and `claim_truth`.", "Let `/practice/sessions/{id}/knowledge-check` prefer live handler diagnostics only when a live handler is present, and fail soft to null on malformed partial live summaries instead of reviving stale persisted snapshot conclusions.", "Keep top-level `claim_truth` in websocket/runtime diagnostics for backward compatibility while adding the richer `live_session_summary` contract."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the required task-plan verification suites after updating the StepFun reconnect assertion to check the emitted snapshot contract rather than object identity. All three required commands passed: the full StepFun realtime handler unit suite, the enhanced/classic handler coach-health + live-summary unit suite, and the practice evidence contract suite filtered to knowledge-check/report/replay coverage."
completed_at: 2026-03-28T07:46:22.013Z
blocker_discovered: false
---

# T01: Unified live sales conclusion summary across StepFun, classic runtime diagnostics, and `/knowledge-check`.

> Unified live sales conclusion summary across StepFun, classic runtime diagnostics, and `/knowledge-check`.

## What Happened
---
id: T01
parent: S02
milestone: M007
key_files:
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/effectiveness/__init__.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/api/practice.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - backend/src/sales_bot/websocket/enhanced_handler.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_enhanced_handler_coach_health.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - Use one evaluator-backed `live_session_summary` object as the active-session authority for `main_issue`, `next_goal`, and `claim_truth`.
  - Let `/practice/sessions/{id}/knowledge-check` prefer live handler diagnostics only when a live handler is present, and fail soft to null on malformed partial live summaries instead of reviving stale persisted snapshot conclusions.
  - Keep top-level `claim_truth` in websocket/runtime diagnostics for backward compatibility while adding the richer `live_session_summary` contract.
duration: ""
verification_result: passed
completed_at: 2026-03-28T07:46:22.014Z
blocker_discovered: false
---

# T01: Unified live sales conclusion summary across StepFun, classic runtime diagnostics, and `/knowledge-check`.

**Unified live sales conclusion summary across StepFun, classic runtime diagnostics, and `/knowledge-check`.**

## What Happened

I traced the seam drift to two different runtime behaviors: StepFun only surfaced live claim truth, while the classic capability path emitted `score_update` before objection-ledger alignment and exposed no same-session conclusion summary. I fixed that by adding one evaluator-backed `live_session_summary` shape carrying `main_issue`, `next_goal`, `claim_truth`, and alignment metadata. StepFun now persists, restores, emits, and exposes that full summary alongside the existing top-level claim-truth field. Classic now delays `score_update` emission until objection-ledger alignment is complete, attaches the same `live_session_summary`, and mirrors it through `EnhancedSalesHandler` runtime diagnostics and reconnect snapshots. I then tightened shared runtime diagnostics and `/practice/sessions/{id}/knowledge-check` so an active live handler overrides stale persisted session conclusions only while it is active, and malformed or partial live summaries fail soft to null instead of reviving old completed-session state. Focused unit/contract coverage now proves StepFun, classic, and knowledge-check all speak the same same-session issue/goal/claim-truth semantics.

## Verification

Ran the required task-plan verification suites after updating the StepFun reconnect assertion to check the emitted snapshot contract rather than object identity. All three required commands passed: the full StepFun realtime handler unit suite, the enhanced/classic handler coach-health + live-summary unit suite, and the practice evidence contract suite filtered to knowledge-check/report/replay coverage.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py` | 0 | ✅ pass | 10369ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py` | 0 | ✅ pass | 2650ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k 'knowledge_check or replay or report'` | 0 | ✅ pass | 3058ms |


## Deviations

Added a small export in `backend/src/common/effectiveness/__init__.py` so both runtime implementations could consume the shared evaluator helper through the existing package seam. Also ran `backend/tests/unit/test_capability_processor.py` as an extra guard because the classic `score_update` emission path was reordered behind objection-ledger alignment.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/common/effectiveness/__init__.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/sales_bot/websocket/enhanced_handler.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_enhanced_handler_coach_health.py`
- `backend/tests/contract/test_practice_evidence_contract.py`


## Deviations
Added a small export in `backend/src/common/effectiveness/__init__.py` so both runtime implementations could consume the shared evaluator helper through the existing package seam. Also ran `backend/tests/unit/test_capability_processor.py` as an extra guard because the classic `score_update` emission path was reordered behind objection-ledger alignment.

## Known Issues
None.
