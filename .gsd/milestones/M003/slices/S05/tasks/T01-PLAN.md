---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Build the objection-heavy regression net on current runtime routes

Build the focused regression net for objection-heavy realism on the current code paths: at least ROI, price, competitor, implementation risk, and evidence-proof cases. Reuse the current StepFun/runtime/unit/integration suites and add explicit assertions for weak-evidence / verified-evidence / search-failed paths.

## Inputs

- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_knowledge_helpers.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

## Expected Output

- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_knowledge_helpers.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py
