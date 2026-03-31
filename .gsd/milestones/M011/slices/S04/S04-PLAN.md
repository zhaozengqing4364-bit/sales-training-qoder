# S04: 评测、debug API 与 rollout

**Goal:** 给新引擎补上 evaluation harness、debug API、seed config 和 feature flag/dual-run rollout。
**Demo:** After this: 可以查询最近一次知识问答 run 的完整执行轨迹，并通过 eval cases 验证产品介绍类 query 行为。

## Tasks
- [x] **T01: Added a fixture-driven knowledge-answer evaluation harness with initial cases for intro, pricing, comparison, coaching, and blocked-timeout degradation.** — 实现 evaluation harness 与初始 fixture case 集。先覆盖产品介绍、价格、版本比较、辅导类、blocked/timeout 降级等样例。
  - Estimate: 35-45m
  - Files: backend/src/common/knowledge_engine/evaluation.py, backend/tests/evaluation/test_knowledge_answer_engine_eval.py, backend/tests/fixtures/knowledge_answer_eval_cases.json
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q
- [ ] **T02: 增加知识问答 debug API** — 实现 read-only debug API。支持列出 answer runs、查看单次 run、查看 step breakdown，让后续可以按 run_id 调试。
  - Estimate: 30-40m
  - Files: backend/src/common/api/knowledge_debug.py, backend/src/main.py, backend/tests/integration/test_knowledge_debug_api.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q
- [ ] **T03: 增加 seed config、feature flags 与 rollout** — 增加 seed config 与 feature flags/dual-run rollout。支持初始化 active profiles，并通过 `KNOWLEDGE_ANSWER_ENGINE_ENABLED` / `KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN` 控制切换。最后跑完整 focused backend + web compatibility suites。
  - Estimate: 45-60m
  - Files: backend/scripts/seed_knowledge_answer_config.py, backend/tests/unit/common/test_seed_knowledge_answer_config.py, backend/tests/unit/common/test_knowledge_answer_feature_flag.py, backend/src/common/knowledge_engine/compat.py, docs/plans/knowledge-answer-config-seed-notes.md
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py backend/tests/unit/common/test_kb_lock_guard.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/common/test_knowledge_answer_control_plane_models.py backend/tests/unit/common/test_knowledge_answer_config_repo.py backend/tests/unit/common/test_knowledge_entity_resolver.py backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/common/test_knowledge_answerability.py backend/tests/unit/common/test_knowledge_answer_assembler.py backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/evaluation/test_knowledge_answer_engine_eval.py backend/tests/unit/common/test_seed_knowledge_answer_config.py backend/tests/unit/common/test_knowledge_answer_feature_flag.py -q && npm --prefix web test -- --run src/hooks/websocket/message-handlers.test.ts src/components/ui/chat-bubble.test.tsx "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
