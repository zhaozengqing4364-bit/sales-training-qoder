---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Expose the claim-truth contract on the current runtime diagnostics path

Wire the truth contract into the runtime and diagnostics path so objection handling can distinguish chain failure from weak or unsupported evidence. Reuse current kb-lock/runtime diagnostic helpers and StepFun handler surfaces rather than inventing another debug endpoint.

## Inputs

- `backend/src/common/knowledge/kb_lock_guard.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`

## Expected Output

- `backend/src/common/knowledge/kb_lock_guard.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py
