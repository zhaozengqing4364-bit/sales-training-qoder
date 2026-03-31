---
id: T03
parent: S04
milestone: M011
provides: []
requires: []
affects: []
key_files: ["backend/src/common/knowledge_engine/compat.py", "backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py", "backend/src/sales_bot/websocket/stepfun_realtime_handler.py", "backend/scripts/seed_knowledge_answer_config.py", "backend/tests/unit/common/test_seed_knowledge_answer_config.py", "backend/tests/unit/common/test_knowledge_answer_feature_flag.py", "backend/tests/unit/test_stepfun_internal_knowledge_searcher.py", "docs/plans/knowledge-answer-config-seed-notes.md", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Gate the new engine at the compat seam with three explicit modes: legacy default, engine-enabled cutover, and dual-run shadow audit.", "Persist shadow/live answer-run audits only when a real session_id is available, and surface rollout state through `_diagnostics.knowledge_answer_rollout` plus the existing runtime metric ledger."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Focused T03 tests passed first (`test_seed_knowledge_answer_config.py` and `test_knowledge_answer_feature_flag.py`), then the full task-plan gate passed from repo root: backend focused compatibility suite finished 197/197 green across StepFun search/runtime, replay/runtime diagnostics, engine/eval, and new rollout tests; the chained web compatibility suite finished 68/68 green across websocket message handlers plus learner report/replay pages. LSP diagnostics reported no issues on all touched Python files and tests."
completed_at: 2026-03-31T06:27:37.784Z
blocker_discovered: false
---

# T03: Added seedable knowledge-answer rollout controls with enabled/dual-run compat gating, shadow audit persistence, and full backend/web verification green.

> Added seedable knowledge-answer rollout controls with enabled/dual-run compat gating, shadow audit persistence, and full backend/web verification green.

## What Happened
---
id: T03
parent: S04
milestone: M011
key_files:
  - backend/src/common/knowledge_engine/compat.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/scripts/seed_knowledge_answer_config.py
  - backend/tests/unit/common/test_seed_knowledge_answer_config.py
  - backend/tests/unit/common/test_knowledge_answer_feature_flag.py
  - backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
  - docs/plans/knowledge-answer-config-seed-notes.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Gate the new engine at the compat seam with three explicit modes: legacy default, engine-enabled cutover, and dual-run shadow audit.
  - Persist shadow/live answer-run audits only when a real session_id is available, and surface rollout state through `_diagnostics.knowledge_answer_rollout` plus the existing runtime metric ledger.
duration: ""
verification_result: passed
completed_at: 2026-03-31T06:27:37.785Z
blocker_discovered: false
---

# T03: Added seedable knowledge-answer rollout controls with enabled/dual-run compat gating, shadow audit persistence, and full backend/web verification green.

**Added seedable knowledge-answer rollout controls with enabled/dual-run compat gating, shadow audit persistence, and full backend/web verification green.**

## What Happened

Executed T03 in TDD order. I first added failing tests for the new seed script and rollout flags, then extracted rollout control into `backend/src/common/knowledge_engine/compat.py` so one seam now owns legacy default, enabled cutover, and dual-run shadow-audit modes. `stepfun_internal_knowledge_searcher.py` now routes through that compat seam, preserves the existing runtime metric ledger in enabled mode, and attaches `_diagnostics.knowledge_answer_rollout` for enabled/dual-run inspection. `StepFunRealtimeHandler` now forwards `session_id` so enabled and dual-run modes can truthfully persist `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` rows. I added `backend/scripts/seed_knowledge_answer_config.py` with explicit starter profiles for product overview, pricing, version comparison, and coaching guidance; the script is idempotent by `version_name` and reactivates existing versions instead of duplicating rows. I also added `docs/plans/knowledge-answer-config-seed-notes.md` to document seeded profiles, CLI usage, activation behavior, and rollout order. During final verification I fixed two real compatibility gaps instead of weakening tests: the older config-driven StepFun search test now explicitly opts into enabled mode, and the enabled-path compat wrapper now normalizes legacy content-only rows plus emits the existing runtime metric ledger before returning. Final focused backend and web compatibility gates passed end to end.

## Verification

Focused T03 tests passed first (`test_seed_knowledge_answer_config.py` and `test_knowledge_answer_feature_flag.py`), then the full task-plan gate passed from repo root: backend focused compatibility suite finished 197/197 green across StepFun search/runtime, replay/runtime diagnostics, engine/eval, and new rollout tests; the chained web compatibility suite finished 68/68 green across websocket message handlers plus learner report/replay pages. LSP diagnostics reported no issues on all touched Python files and tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_seed_knowledge_answer_config.py backend/tests/unit/common/test_knowledge_answer_feature_flag.py -q` | 0 | ✅ pass | 750ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py::test_search_internal_knowledge_uses_config_driven_resolution_planning_adapter_and_reranking -q` | 0 | ✅ pass | 550ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py backend/tests/unit/common/test_kb_lock_guard.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/common/test_knowledge_answer_control_plane_models.py backend/tests/unit/common/test_knowledge_answer_config_repo.py backend/tests/unit/common/test_knowledge_entity_resolver.py backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/common/test_knowledge_answerability.py backend/tests/unit/common/test_knowledge_answer_assembler.py backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/evaluation/test_knowledge_answer_engine_eval.py backend/tests/unit/common/test_seed_knowledge_answer_config.py backend/tests/unit/common/test_knowledge_answer_feature_flag.py -q && npm --prefix web test -- --run src/hooks/websocket/message-handlers.test.ts src/components/ui/chat-bubble.test.tsx "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` | 0 | ✅ pass | 15800ms |


## Deviations

The runtime already contained a partially inlined config-driven engine branch inside `stepfun_internal_knowledge_searcher.py`, so I extracted the feature-flag/dual-run behavior into the compat seam instead of adding another parallel path. The seed script also had to own its own sync SQLAlchemy session bootstrap because the repo’s shared DB session module only exposes async factories.

## Known Issues

The full backend gate still emits the pre-existing narrow-run pytest-cov warnings (`Module src was never imported` / `No data was collected`) from repo-root focused pytest usage, and the replay suite still emits the existing `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` warning from `backend/src/common/conversation/replay.py:292`. All required backend/web verification commands passed.

## Files Created/Modified

- `backend/src/common/knowledge_engine/compat.py`
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/scripts/seed_knowledge_answer_config.py`
- `backend/tests/unit/common/test_seed_knowledge_answer_config.py`
- `backend/tests/unit/common/test_knowledge_answer_feature_flag.py`
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`
- `docs/plans/knowledge-answer-config-seed-notes.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
The runtime already contained a partially inlined config-driven engine branch inside `stepfun_internal_knowledge_searcher.py`, so I extracted the feature-flag/dual-run behavior into the compat seam instead of adding another parallel path. The seed script also had to own its own sync SQLAlchemy session bootstrap because the repo’s shared DB session module only exposes async factories.

## Known Issues
The full backend gate still emits the pre-existing narrow-run pytest-cov warnings (`Module src was never imported` / `No data was collected`) from repo-root focused pytest usage, and the replay suite still emits the existing `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` warning from `backend/src/common/conversation/replay.py:292`. All required backend/web verification commands passed.
