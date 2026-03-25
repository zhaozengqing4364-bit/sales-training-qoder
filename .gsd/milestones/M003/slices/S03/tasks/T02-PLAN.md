---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Carry unresolved objections across turns and reconnect on both runtime paths

Wire the ledger through classic and StepFun runtime paths and make reconnect restore safe. Reuse current handlers and capability composition so objection state influences follow-up pressure without replaying stale prompts after reconnect.

## Inputs

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`

## Expected Output

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
