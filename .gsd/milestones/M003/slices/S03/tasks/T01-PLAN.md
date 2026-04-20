---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Define and persist the unresolved-objection ledger on current runtime state

Define the minimum unresolved-objection ledger on the current runtime chain: unresolved objection family, promised proof, next expected evidence, and closure state. Add focused tests around the existing runtime/context components so this ledger can be persisted without inventing a second store.

## Inputs

- `backend/src/sales_bot/services/context_manager.py`
- `backend/src/common/conversation/storage.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`

## Expected Output

- `backend/src/sales_bot/services/context_manager.py`
- `backend/src/common/conversation/storage.py`
- `backend/tests/unit/test_context_manager.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py
