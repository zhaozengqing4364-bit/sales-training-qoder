# S03: Coverage answerability、answer assembly 与 compatibility seam

**Goal:** 把 coverage-based answerability、evidence-driven answer assembly 和 audit 持久化接起来，并通过 compatibility seam 接入 realtime/report/replay。
**Demo:** After this: 一次真实问答后，可以从 replay/report/runtime diagnostics 追到同一条 audit run，并看到 answerability/citations。

## Tasks
- [x] **T01: Added a slot-coverage-based answerability evaluator that classifies grounded answers from required/optional profile slots, preserves blocked retrieval semantics, and degrades to count-based verdicts when no answerability profile is configured yet.** — 实现 coverage-based answerability。按 profile required/optional slots 判 sufficient / partial / insufficient / blocked，不再只看命中条数。
  - Estimate: 25-35m
  - Files: backend/src/common/knowledge_engine/answerability.py, backend/tests/unit/common/test_knowledge_answerability.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answerability.py -q
- [x] **T02: Added a deterministic evidence-driven answer assembler that turns answerability plus evidence rows into learner-safe blocked copy, numbered grounded final_text, normalized citations, unsupported_claims, rewritten_queries, and compact retrieval diagnostics.** — 实现 evidence-driven answer assembler。先从 deterministic structured assembly 开始，输出 final_text、blocked_text、citations、unsupported_claims。
  - Estimate: 30-40m
  - Files: backend/src/common/knowledge_engine/assembler.py, backend/tests/unit/common/test_knowledge_answer_assembler.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_assembler.py -q
- [x] **T03: Added a real knowledge-answer engine orchestration path with persisted audit runs plus compatibility helpers that expose audit_run_id, citations, and answerability to existing runtime diagnostics and replay surfaces.** — 实现 audit persistence，并把 engine orchestration 串起来：config → resolve → classify → plan → retrieve → rank → answerability → assemble → audit。随后通过 compat seam 接入 StepFunRealtimeHandler 和 runtime/report/replay diagnostics。
  - Estimate: 60-75m
  - Files: backend/src/common/knowledge_engine/audit_repo.py, backend/src/common/knowledge_engine/engine.py, backend/src/common/knowledge_engine/compat.py, backend/src/sales_bot/websocket/stepfun_realtime_handler.py, backend/src/common/conversation/runtime_diagnostics.py, backend/src/common/conversation/replay.py, backend/src/common/api/practice.py, backend/tests/unit/common/test_knowledge_answer_audit_repo.py, backend/tests/unit/common/test_knowledge_answer_engine.py, backend/tests/unit/test_stepfun_realtime_handler.py, backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py, backend/tests/unit/test_replay_service.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py -q
