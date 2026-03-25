---
id: T02
parent: S04
milestone: M003
key_files:
  - backend/src/common/knowledge/kb_lock_guard.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/api/practice.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Kept the stable persisted/public `score_snapshot` shape unchanged and exposed live `claim_truth` separately on the existing `score_update` websocket payload plus reconnect-safe handler state.
  - Made `/practice/sessions/{id}/knowledge-check` prefer live handler `claim_truth` and only fall back to completed-session `SessionEvidenceService` projection when no live runtime state is available.
  - Added an explicit `kb_lock_chain_failure` classifier so runtime diagnostics can distinguish infrastructure/setup failure from evidence-quality states like `unsupported_claim` or `weak_evidence`.
duration: ""
verification_result: passed
completed_at: 2026-03-25T06:44:08.718Z
blocker_discovered: false
---

# T02: Exposed claim-truth on StepFun score updates and knowledge-check diagnostics

**Exposed claim-truth on StepFun score updates and knowledge-check diagnostics**

## What Happened

I followed a red-green loop on the two planned seams. First I tightened the existing StepFun realtime tests and added a new practice contract test so the runtime path had to expose the canonical claim-truth contract while keeping KB-lock chain failures separate. The initial red run failed on the missing diagnostics fields, which confirmed the gap was on the intended path rather than in test setup.

On the implementation side, I added a shared KB-lock chain-failure classifier in `backend/src/common/knowledge/kb_lock_guard.py` so diagnostics can tell infra/setup failures apart from normal evidence-quality states. I then extended `backend/src/common/conversation/runtime_diagnostics.py` to return the live/read-side claim-truth payload plus flat `claim_truth_status` / `claim_truth_source` fields and an explicit `kb_lock_chain_failure` boolean.

For the live StepFun seam, I kept the persisted/public `score_snapshot` shape stable and introduced a separate `_latest_claim_truth` handler state instead. `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` now derives `claim_truth` from the existing `resolve_sales_report_alignment(...)` helper after objection-ledger merge, emits that payload on the existing `score_update` websocket event, and carries the same value through reconnect snapshots without mutating the normalized stored score snapshot contract.

Finally, `backend/src/common/api/practice.py` now enriches `/api/v1/practice/sessions/{id}/knowledge-check` by reading live handler claim truth first and falling back to the completed-session `SessionEvidenceService` projection for sales sessions. That keeps runtime diagnostics on the same evidence vocabulary as report/replay without adding a new debug endpoint. I recorded the contract choice in `D058` and added the score-snapshot normalization gotcha to `.gsd/KNOWLEDGE.md`.

## Verification

Ran focused backend proofs first with `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_emits_canonical_sales_score_and_action_card tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable tests/contract/test_practice_evidence_contract.py::test_knowledge_check_keeps_claim_truth_distinct_from_kb_lock_chain_failures`, which passed and covered both live StepFun payloads and the knowledge-check contract. Then ran the task-plan gate `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py`; all 62 tests passed. LSP diagnostics on the touched backend source and test files returned no diagnostics.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_emits_canonical_sales_score_and_action_card tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable tests/contract/test_practice_evidence_contract.py::test_knowledge_check_keeps_claim_truth_distinct_from_kb_lock_chain_failures` | 0 | ✅ pass | 13600ms |
| 2 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 11960ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/knowledge/kb_lock_guard.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
