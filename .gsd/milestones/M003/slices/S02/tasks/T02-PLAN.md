---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Freeze the pressure model into the runtime compile and session snapshot chain

Compile the structured pressure model into the existing runtime authority chain and freeze it into new session snapshots. Reuse `voice_runtime_policy.py`, `voice_instruction_compiler.py`, and current session-create flow so the runtime sees one frozen Persona pressure contract per session instead of reading live admin config at execution time.

## Inputs

- `backend/src/sales_bot/services/voice_runtime_policy.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/src/common/api/practice.py`
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md`

## Expected Output

- `backend/src/sales_bot/services/voice_runtime_policy.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_voice_instruction_compiler.py`
- `backend/tests/integration/test_knowledge_flow.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py
