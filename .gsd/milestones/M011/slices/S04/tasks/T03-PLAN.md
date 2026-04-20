---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: 增加 seed config、feature flags 与 rollout

增加 seed config 与 feature flags/dual-run rollout。支持初始化 active profiles，并通过 `KNOWLEDGE_ANSWER_ENGINE_ENABLED` / `KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN` 控制切换。最后跑完整 focused backend + web compatibility suites。

## Inputs

- `docs/plans/2026-03-31-haystack-knowledge-answering-engine.md`

## Expected Output

- `backend/scripts/seed_knowledge_answer_config.py`
- `backend/tests/unit/common/test_seed_knowledge_answer_config.py`
- `backend/tests/unit/common/test_knowledge_answer_feature_flag.py`
- `docs/plans/knowledge-answer-config-seed-notes.md`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py backend/tests/unit/common/test_kb_lock_guard.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/common/test_knowledge_answer_control_plane_models.py backend/tests/unit/common/test_knowledge_answer_config_repo.py backend/tests/unit/common/test_knowledge_entity_resolver.py backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/common/test_knowledge_answerability.py backend/tests/unit/common/test_knowledge_answer_assembler.py backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/evaluation/test_knowledge_answer_engine_eval.py backend/tests/unit/common/test_seed_knowledge_answer_config.py backend/tests/unit/common/test_knowledge_answer_feature_flag.py -q && npm --prefix web test -- --run src/hooks/websocket/message-handlers.test.ts src/components/ui/chat-bubble.test.tsx "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
