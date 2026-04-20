---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: Lock the replay/highlight learning-evidence contract on the existing backend authority line

Write focused failing tests around `backend/src/common/conversation/replay.py` and the replay API, then extend the current replay/highlight payload so it can carry stable learning fields already implied by the product: reason, stage, nearby context, suggested better response, and issue-family linkage. Keep the current replay route and session evidence line authoritative; do not add a second scorer or freeform learning generator.

## Inputs

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/api.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_replay_api.py`

## Expected Output

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/api.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_replay_api.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py

## Observability Impact

Extends existing replay diagnostics rather than adding a new channel; focused unit/integration tests show when explanation fields disappear or drift.
