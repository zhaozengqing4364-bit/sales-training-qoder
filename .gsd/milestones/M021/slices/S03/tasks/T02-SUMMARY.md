---
id: T02
parent: S03
milestone: M021
key_files:
  - backend/src/common/effectiveness/canonical.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/analytics/history_service.py
  - backend/src/common/services/practice_report_service.py
  - backend/src/common/conversation/replay.py
  - backend/src/agent/capabilities/realtime_scoring.py
  - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/unit/test_history_service_evidence_projection.py
  - backend/tests/unit/test_realtime_scoring.py
key_decisions:
  - D237 — emit explicit canonical_evaluation_kernel plus compatibility_readers while preserving legacy rollup fields during the migration.
duration: 
verification_result: passed
completed_at: 2026-04-14T03:17:45.596Z
blocker_discovered: false
---

# T02: Added a shared canonical evaluation kernel plus compatibility readers across realtime scoring and projection-backed report/replay/history surfaces.

**Added a shared canonical evaluation kernel plus compatibility readers across realtime scoring and projection-backed report/replay/history surfaces.**

## What Happened

I turned the T01 schema inventory into a real shared runtime/read-side contract. In `backend/src/common/effectiveness/canonical.py` I added builders that materialize one scenario-aware `canonical_evaluation_kernel` plus `compatibility_readers` for sales and presentation instead of leaving the canonical schema as metadata only. I wired realtime scoring to emit the kernel alongside the legacy score payload and updated StepFun score-snapshot normalization so those new fields survive persistence into `ConversationMessage.score_snapshot`. In `backend/src/common/conversation/session_evidence.py` I made the shared projection build and carry the canonical kernel, derive legacy rollup fields from the same compat reader, and project presentation review data through the same kernel contract. I then threaded that projection through `common/analytics/history_service.py`, `common/services/practice_report_service.py`, and `common/conversation/replay.py`, plus the response schemas in `common/db/schemas.py` and `common/conversation/schemas.py`, so report/replay/history-facing consumers can read explicit canonical truth while old top-level fields remain stable. I also updated the realtime session write path in `common/api/practice.py` and `common/services/practice_session_service.py` to derive persisted rollups from the same canonical kernel builder, saved decision D237 for the explicit kernel+compat exposure strategy, and wrote a knowledge note about StepFun score-snapshot normalization silently dropping new fields unless it is extended in lockstep.

## Verification

Verified in three layers. First, I did a red-green cycle with new focused tests that required realtime scoring, history summaries, and report/replay contracts to expose `canonical_evaluation_kernel` and `compatibility_readers`; those now pass. Second, I ran the exact task-plan verification command and it finished green across conclusion-evidence parity, practice evidence contract, admin analytics, and history projection. Third, I ran LSP diagnostics on every touched backend authority file and got no diagnostics, confirming the new kernel/plumbing changes are syntactically and structurally clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_effectiveness_canonical_kernel.py backend/tests/unit/test_realtime_scoring.py backend/tests/unit/test_history_service_evidence_projection.py -q` | 0 | ✅ pass | 4294ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q` | 0 | ✅ pass | 21404ms |

## Deviations

Added score-snapshot normalization and API schema plumbing (`sales_bot/websocket/components/stepfun_message_helpers.py`, `common/db/schemas.py`, `common/conversation/schemas.py`) so the new kernel survives persistence and serialization. This was a local implementation adaptation required to make the planned canonical contract actually durable across realtime -> storage -> read-side flows.

## Known Issues

Pre-existing focused-test warnings from pytest-cov (no data collected for that focused subset) and third-party Python 3.14 deprecation warnings from LangChain/Chroma remain, but the product code and task verification gates are green.

## Files Created/Modified

- `backend/src/common/effectiveness/canonical.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/common/services/practice_report_service.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/agent/capabilities/realtime_scoring.py`
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/unit/test_history_service_evidence_projection.py`
- `backend/tests/unit/test_realtime_scoring.py`
