---
id: T01
parent: S03
milestone: M003
key_files:
  - backend/src/sales_bot/services/context_manager.py
  - backend/src/common/conversation/storage.py
  - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_context_manager.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_message_helpers.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Persist the structured objection ledger under `ConversationMessage.transcript_metadata["objection_ledger"]` instead of adding a new column or side store, so replay/report readers can keep using the current evidence chain.
  - Normalize the ledger once and reuse the same dict shape in both persisted message analysis and `StepFunRealtimeHandler` reconnect snapshots, so later classic/StepFun wiring work can carry one contract across runtime and read-side code.
  - Whitelist the ledger through both `stepfun_message_helpers` and `MessageStorageService`, because this codebase intentionally filters unknown analysis keys before persistence.
duration: ""
verification_result: passed
completed_at: 2026-03-25T03:30:14.684Z
blocker_discovered: false
---

# T01: Added a normalized unresolved-objection ledger seam to context, message persistence, and StepFun reconnect state.

**Added a normalized unresolved-objection ledger seam to context, message persistence, and StepFun reconnect state.**

## What Happened

I started with a red-green pass: added a new `backend/tests/unit/test_context_manager.py` file plus two StepFun handler snapshot tests, then ran the planned pytest command to confirm the repo did not yet expose a ledger shape. From there I added a minimal `ObjectionLedger` to `ContextManager`, exposed an `update_objection_ledger(...)` API that preserves earlier promised-proof/evidence fields while allowing closure-state updates, and surfaced the normalized ledger in conversation summaries for later diagnostics.

On the persistence side, I kept the change inside the existing evidence chain instead of inventing a new store. `MessageStorageService` now normalizes a four-field objection ledger and persists it under `transcript_metadata["objection_ledger"]`; `update_analysis(...)` can merge that ledger into transcript metadata on duplicate-message patch paths. Because the live StepFun path whitelists analysis data twice before it reaches storage, I also extended `stepfun_message_helpers` to carry `objection_ledger` through normalization/extraction and updated `StepFunRealtimeHandler` so reconnect snapshots can save and restore the same normalized dict on current runtime state. I recorded the persistence choice in `.gsd/DECISIONS.md` and added a `.gsd/KNOWLEDGE.md` note about the two-layer analysis-data whitelist, since that filtering would otherwise silently drop later structured runtime facts.

## Verification

Fresh verification evidence came from the planned backend gate and one extra helper suite for the widened persistence seam. `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py` passed with 60 tests, covering the new context-manager ledger API, transcript-metadata persistence, and StepFun snapshot save/restore behavior. Because T01 also touched the shared StepFun persistence helper layer, I ran `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_message_helpers.py`, which passed with 5 tests and confirmed the updated whitelist/duplicate-patch path stays green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py` | 0 | ✅ pass | 13930ms |
| 2 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_message_helpers.py` | 0 | ✅ pass | 12270ms |


## Deviations

Expanded beyond the four-file planner snapshot to update `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, and `backend/tests/unit/test_stepfun_message_helpers.py`, because the live persistence chain currently drops unknown `analysis_data` keys before they reach storage; without extending those seams, the new ledger shape would exist only in types/tests and not on the real runtime path.

## Known Issues

None.

## Files Created/Modified

- `backend/src/sales_bot/services/context_manager.py`
- `backend/src/common/conversation/storage.py`
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/unit/test_context_manager.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_message_helpers.py`
- `.gsd/KNOWLEDGE.md`
