---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Add stable replay anchors on the existing replay/timeline contract

Add stable replay anchor support on the current backend authority line so report items can target a real turn or marker. Reuse replay/timeline data rather than creating a separate deep-link resolver. Lock the anchor contract with focused backend tests.

## Inputs

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/api.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_replay_api.py`

## Expected Output

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/api.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_replay_api.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py
