---
estimated_steps: 1
estimated_files: 12
skills_used: []
---

# T03: 串起引擎并接入 compatibility seam

实现 audit persistence，并把 engine orchestration 串起来：config → resolve → classify → plan → retrieve → rank → answerability → assemble → audit。随后通过 compat seam 接入 StepFunRealtimeHandler 和 runtime/report/replay diagnostics。

## Inputs

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/conversation/replay.py`

## Expected Output

- `backend/src/common/knowledge_engine/audit_repo.py`
- `backend/src/common/knowledge_engine/engine.py`
- `backend/src/common/knowledge_engine/compat.py`
- `backend/tests/unit/common/test_knowledge_answer_audit_repo.py`
- `backend/tests/unit/common/test_knowledge_answer_engine.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`
- `backend/tests/unit/test_replay_service.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py -q

## Observability Impact

每次回答写入 knowledge_answer_runs / knowledge_answer_run_steps，并在 diagnostics 中保留关联 ID。
