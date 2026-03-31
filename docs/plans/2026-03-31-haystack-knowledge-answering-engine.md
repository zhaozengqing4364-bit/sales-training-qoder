# Haystack Knowledge Answering Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current patch-grown knowledge QA flow with a configurable, auditable, database-driven knowledge answering engine that uses Haystack as the execution substrate while preserving existing runtime/report/replay contracts.

**Architecture:** Introduce a project-owned `KnowledgeAnswerEngine` as the single entrypoint for grounded answering. The engine will read DB-backed query/ranking/answerability profiles from a new control plane, execute retrieval/reranking/evaluation through Haystack pipelines, then emit a project-owned answer contract plus step-level audit records. Existing callers (`StepFunRealtimeHandler`, runtime diagnostics, report, replay) will keep their current contracts and read the new engine output through a compatibility seam.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, Haystack, existing vector/keyword retrieval backend, existing StepFun realtime path, Vitest, pytest.

---

## Implementation principles

- Keep project-owned control plane in DB. Do not hardcode retrieval policy in prompts or handlers.
- Use Haystack only as execution substrate for retrieval / ranking / evaluation, not as the source of truth for policy.
- Preserve current learner-facing contracts first; migrate internals behind stable schemas.
- Follow TDD for every engine behavior and migration seam.
- Prefer additive rollout with feature flags and dual-read comparisons before cutover.

---

## Slice overview

1. **S1 — Engine seam and DB control plane skeleton**
2. **S2 — Query understanding and retrieval planning**
3. **S3 — Haystack retrieval/reranking execution layer**
4. **S4 — Answerability, answer assembly, and audit trail**
5. **S5 — Integrate realtime/report/replay via compatibility seam**
6. **S6 — Evaluation harness, admin/debug surfaces, and rollout controls**

---

## Data model additions

Add new tables via Alembic. Keep names explicit and audit-friendly.

- `knowledge_query_profiles`
- `knowledge_intent_rules`
- `knowledge_entity_aliases`
- `knowledge_ranking_profiles`
- `knowledge_doc_type_priorities`
- `knowledge_answerability_profiles`
- `knowledge_answer_runs`
- `knowledge_answer_run_steps`
- `knowledge_config_versions`

Each row must support: `id`, `enabled`, `created_at`, `updated_at`, `created_by`, `updated_by`, and a `version_tag` or `config_version_id` where appropriate.

---

## Task 1: Add Haystack dependency and isolated engine package

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/common/knowledge_engine/__init__.py`
- Create: `backend/src/common/knowledge_engine/engine.py`
- Create: `backend/src/common/knowledge_engine/schemas.py`
- Test: `backend/tests/unit/common/test_knowledge_answer_engine.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/common/test_knowledge_answer_engine.py` with a minimal engine creation test:

```python
from common.knowledge_engine.engine import KnowledgeAnswerEngine


def test_engine_can_be_constructed_with_default_dependencies():
    engine = KnowledgeAnswerEngine()
    assert engine is not None
```

**Step 2: Run test to verify it fails**

Run:
```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q
```
Expected: import failure because package/module does not exist.

**Step 3: Add minimal implementation**

- Add Haystack dependency to `backend/pyproject.toml`.
- Create `KnowledgeAnswerEngine` stub class in `engine.py`.
- Create a minimal `KnowledgeAnswerRequest` / `KnowledgeAnswerResult` in `schemas.py`.

**Step 4: Run test to verify it passes**

Run same test command.
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/src/common/knowledge_engine backend/tests/unit/common/test_knowledge_answer_engine.py
git commit -m "feat: add knowledge answer engine seam"
```

---

## Task 2: Add DB schema for control plane profiles

**Files:**
- Create: `backend/alembic/versions/<generated>_knowledge_answer_control_plane.py`
- Modify: `backend/src/common/db/models.py`
- Possibly modify: `backend/src/common/db/schemas.py`
- Test: `backend/tests/unit/common/test_knowledge_answer_control_plane_models.py`

**Step 1: Write failing tests**

Test each model can be instantiated and persists expected fields:

```python
def test_query_profile_model_has_profile_key_and_strategy_fields():
    profile = KnowledgeQueryProfile(profile_key="product_overview", enabled=True)
    assert profile.profile_key == "product_overview"
```

Add one test per new model with only essential fields.

**Step 2: Run tests to verify failure**

Expected: model names undefined.

**Step 3: Implement minimal models and Alembic migration**

Required fields:
- Query profile: `profile_key`, `description`, `rewrite_strategy`, `max_rewrite_queries`, `stop_after_first_success`
- Intent rule: `intent_key`, `priority`, `match_type`, `pattern`, `profile_key`
- Entity alias: `canonical_entity`, `alias`, `entity_type`, `confidence`
- Ranking profile: `profile_key`, `title_exact_boost`, `entity_match_boost`, `doc_type_weights_json`, `section_weights_json`, `min_pass_score`, `min_pass_score_keyword`
- Answerability profile: `profile_key`, `required_slots_json`, `optional_slots_json`, `sufficient_threshold`, `partial_threshold`
- Config version: `version_name`, `status`, `notes`

**Step 4: Run tests**

Run model tests plus migration smoke if available.

**Step 5: Commit**

```bash
git add backend/src/common/db/models.py backend/alembic backend/tests/unit/common/test_knowledge_answer_control_plane_models.py
git commit -m "feat: add knowledge answer control plane schema"
```

---

## Task 3: Add engine request/result contract and audit contract

**Files:**
- Modify: `backend/src/common/knowledge_engine/schemas.py`
- Test: `backend/tests/unit/common/test_knowledge_answer_schemas.py`

**Step 1: Write failing tests**

Define the required contract shape first:

```python
def test_knowledge_answer_result_includes_answerability_citations_and_audit_run_id():
    result = KnowledgeAnswerResult(
        final_text="ok",
        answerability="sufficient",
        citations=[],
        audit_run_id="run-1",
    )
    assert result.audit_run_id == "run-1"
```

**Step 2: Run test to fail**

Expected: missing schema fields.

**Step 3: Implement minimal schema**

Include:
- request: query, session_id, scenario_type, knowledge_base_ids, entrypoint, runtime_options
- result: final_text, blocked_text, answerability, source_status, citations, rewritten_queries, unsupported_claims, audit_run_id, retrieval_summary
- audit step schema: step_name, input_payload, output_payload, duration_ms, status

**Step 4: Run test to pass**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/schemas.py backend/tests/unit/common/test_knowledge_answer_schemas.py
git commit -m "feat: add knowledge answer engine contracts"
```

---

## Task 4: Implement DB-backed config repository

**Files:**
- Create: `backend/src/common/knowledge_engine/config_repo.py`
- Test: `backend/tests/unit/common/test_knowledge_answer_config_repo.py`

**Step 1: Write failing tests**

Test repository methods:
- `get_active_query_profile(profile_key)`
- `list_intent_rules()`
- `resolve_entity_alias(alias)`
- `get_ranking_profile(profile_key)`
- `get_answerability_profile(profile_key)`

**Step 2: Run tests to fail**

**Step 3: Implement minimal repository**

Repository should:
- read only `active` config version rows
- return normalized DTOs, not raw SQLAlchemy objects
- tolerate missing optional tables/rows with explicit defaults

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/config_repo.py backend/tests/unit/common/test_knowledge_answer_config_repo.py
git commit -m "feat: add db-backed knowledge config repository"
```

---

## Task 5: Implement entity resolution layer

**Files:**
- Create: `backend/src/common/knowledge_engine/entity_resolver.py`
- Test: `backend/tests/unit/common/test_knowledge_entity_resolver.py`

**Step 1: Write failing tests**

Cover:
- alias → canonical mapping
- exact canonical pass-through
- no match returns original value with `resolved=False`

Example:

```python
def test_resolver_maps_alias_to_canonical_entity():
    resolver = KnowledgeEntityResolver(alias_map={"世袭科技": "石犀科技"})
    result = resolver.resolve_query("请介绍一下世袭科技")
    assert result.canonical_entities == ["石犀科技"]
```

**Step 2: Run tests to fail**

**Step 3: Implement minimal resolver**

Do not overbuild NLP. Start with deterministic alias replacement + trace payload.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/entity_resolver.py backend/tests/unit/common/test_knowledge_entity_resolver.py
git commit -m "feat: add knowledge entity resolver"
```

---

## Task 6: Implement DB-driven intent classification

**Files:**
- Create: `backend/src/common/knowledge_engine/intent_classifier.py`
- Test: `backend/tests/unit/common/test_knowledge_intent_classifier.py`

**Step 1: Write failing tests**

Test matching order by priority and fallback to `generic_knowledge_query`.

**Step 2: Run tests to fail**

**Step 3: Implement minimal classifier**

Support:
- `regex`
- `keyword_contains`
- `entity_plus_keyword`

Output should include:
- `intent_key`
- `matched_rule_id`
- `profile_key`
- `debug_reason`

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/intent_classifier.py backend/tests/unit/common/test_knowledge_intent_classifier.py
git commit -m "feat: add db-driven knowledge intent classifier"
```

---

## Task 7: Implement retrieval planner

**Files:**
- Create: `backend/src/common/knowledge_engine/retrieval_planner.py`
- Test: `backend/tests/unit/common/test_knowledge_retrieval_planner.py`

**Step 1: Write failing tests**

Cover:
- product overview → progressive plan with ordered slots
- pricing → pricing-first plan
- coaching_only → no factual retrieval plan
- profile-configured `stop_after_first_success`

**Step 2: Run tests to fail**

**Step 3: Implement minimal planner**

Return a `RetrievalPlan` object containing ordered steps:
- `step_key`
- `query_text`
- `slot`
- `stop_after_success`

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/retrieval_planner.py backend/tests/unit/common/test_knowledge_retrieval_planner.py
git commit -m "feat: add knowledge retrieval planner"
```

---

## Task 8: Add Haystack execution adapter

**Files:**
- Create: `backend/src/common/knowledge_engine/haystack_adapter.py`
- Test: `backend/tests/unit/common/test_haystack_adapter.py`

**Step 1: Write failing tests**

Test the adapter can:
- run exact/keyword/vector retrieval plan steps
- stop on first successful step when configured
- return normalized document candidates

**Step 2: Run tests to fail**

**Step 3: Implement minimal adapter**

Important: do not couple adapter to FastAPI handlers.

Adapter responsibilities:
- turn `RetrievalPlan` into Haystack `Pipeline` execution
- normalize Haystack docs into project DTOs
- return per-step timing and raw scores

Initial version may use the existing retrieval backend under a Haystack-compatible wrapper if direct document store migration is not yet ready.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/haystack_adapter.py backend/tests/unit/common/test_haystack_adapter.py
git commit -m "feat: add haystack execution adapter"
```

---

## Task 9: Implement project-owned reranker on top of retrieved candidates

**Files:**
- Create: `backend/src/common/knowledge_engine/reranker.py`
- Test: `backend/tests/unit/common/test_knowledge_reranker.py`

**Step 1: Write failing tests**

Cover business ordering:
- exact title/entity match outranks pure semantic match
- doc type priority influences rank
- section priority influences rank
- diversity penalty prevents same-doc flooding

**Step 2: Run tests to fail**

**Step 3: Implement minimal reranker**

Score formula should be explicit and debuggable, e.g.:
- base semantic score
- title exact boost
- entity boost
- doc_type weight
- section weight
- recency/version bonus
- diversity penalty

Return score breakdown per candidate for auditing.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/reranker.py backend/tests/unit/common/test_knowledge_reranker.py
git commit -m "feat: add configurable knowledge reranker"
```

---

## Task 10: Implement coverage-based answerability

**Files:**
- Create: `backend/src/common/knowledge_engine/answerability.py`
- Test: `backend/tests/unit/common/test_knowledge_answerability.py`

**Step 1: Write failing tests**

Example cases:
- product overview with definition+capability+use_case → sufficient
- only definition → partial
- no required slots → insufficient
- search_failed / kb_not_ready → blocked

**Step 2: Run tests to fail**

**Step 3: Implement minimal coverage model**

Map ranked evidence into slots, then score coverage using DB-configured thresholds.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/answerability.py backend/tests/unit/common/test_knowledge_answerability.py
git commit -m "feat: add coverage-based knowledge answerability"
```

---

## Task 11: Implement answer assembly

**Files:**
- Create: `backend/src/common/knowledge_engine/assembler.py`
- Test: `backend/tests/unit/common/test_knowledge_answer_assembler.py`

**Step 1: Write failing tests**

Cover:
- sufficient product overview builds structured answer sections
- partial answer only includes covered slots
- unsupported claims recorded, not emitted
- blocked answer returns learner-safe text

**Step 2: Run tests to fail**

**Step 3: Implement minimal assembler**

Do not call the LLM first. Start with deterministic evidence assembly from ranked evidence.
If a later synthesis model is added, keep it behind a second explicit component.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/assembler.py backend/tests/unit/common/test_knowledge_answer_assembler.py
git commit -m "feat: add evidence-driven answer assembly"
```

---

## Task 12: Add audit persistence

**Files:**
- Create: `backend/src/common/knowledge_engine/audit_repo.py`
- Test: `backend/tests/unit/common/test_knowledge_answer_audit_repo.py`

**Step 1: Write failing tests**

Test that one engine run writes:
- one `knowledge_answer_runs` row
- multiple `knowledge_answer_run_steps` rows
- step payloads are JSON serializable and bounded

**Step 2: Run tests to fail**

**Step 3: Implement minimal audit repo**

Persist step-by-step payloads with bounded text lengths.
Never log secrets.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/audit_repo.py backend/tests/unit/common/test_knowledge_answer_audit_repo.py
git commit -m "feat: add knowledge answer audit persistence"
```

---

## Task 13: Wire engine orchestration

**Files:**
- Modify: `backend/src/common/knowledge_engine/engine.py`
- Test: `backend/tests/unit/common/test_knowledge_answer_engine.py`

**Step 1: Write failing integration-style unit test**

Mock config repo / resolver / planner / adapter / reranker / answerability / assembler / audit repo.
Assert engine runs all steps in order and returns final contract.

**Step 2: Run tests to fail**

**Step 3: Implement orchestration**

Flow:
- load config
- resolve entity
- classify intent
- build plan
- run Haystack adapter
- rerank
- assess answerability
- assemble answer
- persist audit

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/engine.py backend/tests/unit/common/test_knowledge_answer_engine.py
git commit -m "feat: orchestrate knowledge answer engine"
```

---

## Task 14: Add compatibility seam for current runtime contract

**Files:**
- Create: `backend/src/common/knowledge_engine/compat.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Test: `backend/tests/unit/test_stepfun_realtime_handler.py`

**Step 1: Write failing test**

Test that realtime handler can call engine and still emit:
- `knowledge_answer_diagnostics`
- learner-safe blocked response
- citation payloads in websocket output

**Step 2: Run tests to fail**

**Step 3: Implement seam**

Do not rewrite the whole handler. Replace the internals behind:
- `_prepare_grounding_context`
- `_latest_knowledge_answer_diagnostics`
- blocked response resolution

The handler should consume engine output, not recreate logic.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/compat.py backend/src/sales_bot/websocket/stepfun_realtime_handler.py backend/tests/unit/test_stepfun_realtime_handler.py
git commit -m "feat: wire realtime handler to knowledge answer engine"
```

---

## Task 15: Preserve report / replay / runtime diagnostics contract

**Files:**
- Modify: `backend/src/common/conversation/runtime_diagnostics.py`
- Modify: `backend/src/common/conversation/replay.py`
- Modify: `backend/src/common/api/practice.py`
- Test: existing runtime/replay tests plus new engine compatibility tests

**Step 1: Write failing compatibility tests**

Ensure report/replay still expose:
- `knowledge_answer_diagnostics`
- citations
- rewritten_queries
- answerability
- persisted transcript metadata compatibility

**Step 2: Run tests to fail**

**Step 3: Implement minimal compatibility mapping**

Map engine output → existing learner/read model fields.
Do not change frontend contracts in this task.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/conversation/runtime_diagnostics.py backend/src/common/conversation/replay.py backend/src/common/api/practice.py
git commit -m "feat: preserve runtime and replay contracts via engine output"
```

---

## Task 16: Add admin/debug API for knowledge answer runs

**Files:**
- Create: `backend/src/common/api/knowledge_debug.py`
- Modify: `backend/src/main.py` or router registration file
- Test: `backend/tests/integration/test_knowledge_debug_api.py`

**Step 1: Write failing tests**

Endpoints:
- list recent answer runs
- get one answer run
- get step breakdown for one run

**Step 2: Run tests to fail**

**Step 3: Implement minimal read-only debug API**

This is required for "可审计、可调试".

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/api/knowledge_debug.py backend/tests/integration/test_knowledge_debug_api.py
git commit -m "feat: add knowledge answer debug api"
```

---

## Task 17: Add evaluation harness

**Files:**
- Create: `backend/src/common/knowledge_engine/evaluation.py`
- Create: `backend/tests/evaluation/test_knowledge_answer_engine_eval.py`
- Create: `backend/tests/fixtures/knowledge_answer_eval_cases.json`

**Step 1: Write failing eval tests**

Use a small benchmark set first:
- product overview
- pricing
- version comparison
- unsupported query
- coaching-only query

Track:
- retrieval relevance
- answerability correctness
- blocked correctness
- citation presence

**Step 2: Run tests to fail**

**Step 3: Implement minimal eval harness**

Support running engine against fixture cases and asserting expected answerability / evidence behavior.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/evaluation.py backend/tests/evaluation/test_knowledge_answer_engine_eval.py backend/tests/fixtures/knowledge_answer_eval_cases.json
git commit -m "feat: add knowledge answer evaluation harness"
```

---

## Task 18: Add feature flag and dual-run rollout

**Files:**
- Modify: `backend/src/common/knowledge_engine/compat.py`
- Modify: config/env handling files if needed
- Test: `backend/tests/unit/common/test_knowledge_answer_feature_flag.py`

**Step 1: Write failing tests**

Cover:
- old path when engine disabled
- new path when enabled
- dual-run mode records audit without user-visible cutover

**Step 2: Run tests to fail**

**Step 3: Implement feature flag**

Suggested flags:
- `KNOWLEDGE_ANSWER_ENGINE_ENABLED`
- `KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN`

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/src/common/knowledge_engine/compat.py backend/tests/unit/common/test_knowledge_answer_feature_flag.py
git commit -m "feat: add knowledge answer engine rollout flags"
```

---

## Task 19: Add initial seed config and migration docs

**Files:**
- Create: `backend/scripts/seed_knowledge_answer_config.py`
- Create: `docs/plans/knowledge-answer-config-seed-notes.md` or merge into this plan’s follow-up docs
- Test: `backend/tests/unit/common/test_seed_knowledge_answer_config.py`

**Step 1: Write failing tests**

Test seed script inserts:
- one active config version
- base query profiles
- base ranking profile
- base answerability profile
- starter entity alias rows

**Step 2: Run tests to fail**

**Step 3: Implement seed script**

Seed only minimal, explicit defaults. No giant speculative taxonomy.

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add backend/scripts/seed_knowledge_answer_config.py backend/tests/unit/common/test_seed_knowledge_answer_config.py docs/plans/knowledge-answer-config-seed-notes.md
git commit -m "feat: add knowledge answer config seed"
```

---

## Task 20: Full focused verification before rollout

**Files:**
- No new source files required
- Verify existing tests + new engine suites

**Step 1: Run backend focused suite**

```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml \
  backend/tests/unit/test_stepfun_internal_knowledge_searcher.py \
  backend/tests/unit/test_stepfun_realtime_handler.py \
  backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py \
  backend/tests/unit/test_replay_service.py \
  backend/tests/unit/common/test_kb_lock_guard.py \
  backend/tests/unit/common/test_knowledge_answer_engine.py \
  backend/tests/unit/common/test_knowledge_answer_control_plane_models.py \
  backend/tests/unit/common/test_knowledge_answer_config_repo.py \
  backend/tests/unit/common/test_knowledge_entity_resolver.py \
  backend/tests/unit/common/test_knowledge_intent_classifier.py \
  backend/tests/unit/common/test_knowledge_retrieval_planner.py \
  backend/tests/unit/common/test_haystack_adapter.py \
  backend/tests/unit/common/test_knowledge_reranker.py \
  backend/tests/unit/common/test_knowledge_answerability.py \
  backend/tests/unit/common/test_knowledge_answer_assembler.py \
  backend/tests/unit/common/test_knowledge_answer_audit_repo.py \
  backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q
```

**Step 2: Run web compatibility suite**

```bash
npm --prefix web test -- --run \
  src/hooks/websocket/message-handlers.test.ts \
  src/components/ui/chat-bubble.test.tsx \
  "src/app/(user)/practice/[sessionId]/report/page.test.tsx" \
  "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
```

**Step 3: Manual/live verification**

Verify these queries against a running local system:
- 产品介绍类 query
- 价格类 query
- 辅导类 query
- KB timeout / low-confidence degradation

Expected:
- no hallucination
- no mid-stream audio truncation
- report/replay diagnostics remain visible

**Step 4: Commit rollout-ready state**

```bash
git add -A
git commit -m "feat: integrate haystack-backed knowledge answering engine"
```

---

## Recommended rollout strategy

1. Ship DB schema + engine seam dark
2. Seed config in staging/dev
3. Enable dual-run and compare audit outputs against current path
4. Turn on runtime path for one entrypoint first (`realtime`)
5. Then switch report/replay read model to engine-owned audit where appropriate

---

## Risks to watch

- Overfitting config taxonomy before real usage appears
- Letting Haystack types leak into learner-facing contracts
- Losing existing diagnostics/citation compatibility during migration
- Replacing business ranking logic with framework-default ranking
- Making config editable without versioning/audit

---

## Done criteria

This feature is done when:
- knowledge answering behavior is controlled by DB-backed config, not hardcoded query cases
- runtime/report/replay share one engine output seam
- audit logs can reconstruct every answer step-by-step
- product overview queries no longer depend on patch-specific handler logic
- retrieval/ranking/answerability behavior can be tuned without code edits
- focused backend/web suites pass
- live verification shows stable, non-hallucinated behavior

---

Plan complete and saved to `docs/plans/2026-03-31-haystack-knowledge-answering-engine.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
