# S02: Query understanding、planner 与 Haystack 检索执行 — UAT

**Milestone:** M011
**Written:** 2026-03-31T04:19:35.853Z

# S02: Query understanding、planner 与 Haystack 检索执行 — UAT

**Milestone:** M011  
**UAT mode:** focused backend/runtime verification on the shipped StepFun internal knowledge search path

## Why this UAT mode is sufficient

This slice delivers backend runtime behavior on the current StepFun internal knowledge search entrypoint, not a new learner-facing page yet. Acceptance therefore depends on verifying the exact runtime seam the product will reuse later: entity resolution, intent classification, retrieval planning, execution traces, reranked results, and legacy fallback behavior.

## Preconditions

- Backend dependencies are installed in `backend/venv`.
- Run commands from the repository root.
- An active config snapshot can be created by tests through the current knowledge-answer control-plane tables.
- Focused backend verification must run **serially**, not in parallel, because this repo’s pytest-cov setup shares the top-level `.coverage` SQLite file.

## Smoke Test

Run all slice-plan gates serially:

1. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_entity_resolver.py -q`
2. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q`
3. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q`

**Expected:** all 23 focused tests pass.

## Test Cases

### 1. Alias query is normalized to a canonical entity with auditable trace

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_entity_resolver.py -q`.
2. Inspect the alias-path assertion for `请介绍一下世袭科技`.
3. **Expected:** the resolver returns `normalized_query == "请介绍一下石犀科技"`, `canonical_entities == ["石犀科技"]`, and a match trace whose `matched_text` is `世袭科技` and `match_source` is `alias`.

### 2. Canonical entity pass-through remains auditable instead of silently skipping resolution

1. In the same resolver suite, inspect the exact-canonical-path assertion.
2. **Expected:** querying `请介绍一下石犀科技` leaves the normalized query unchanged but still returns one trace entry with `match_source == "canonical"`.

### 3. No-match queries stay unchanged and do not fabricate entities

1. In the same resolver suite, inspect the no-match assertion.
2. **Expected:** queries without a configured alias/entity keep the original text, return `resolved == False`, and expose no canonical entities or matches.

### 4. DB-backed intent rules prefer higher-priority regex matches over lower-priority keyword rules

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q`.
2. Inspect the `company_intro` vs `pricing_query` classifier case.
3. **Expected:** the normalized query `请介绍一下石犀科技` matches the higher-priority regex rule, yields `intent_key == "company_intro"`, `profile_key == "product_overview"`, and carries a trace with `match_type == "regex"` and the configured pattern.

### 5. `entity_keyword_contains` rules fire only when both entity presence and keyword match are satisfied

1. In the same classifier suite, inspect the entity+keyword case.
2. **Expected:** `石犀科技价格怎么样` matches the `entity_pricing` rule and returns `matched_terms == ["价格"]`, while `价格怎么样` falls back to `general_lookup` because no entity was resolved.

### 6. Product-overview planning emits a progressive multi-query plan anchored on the resolved entity

1. In the planner suite, inspect the product-overview plan assertion.
2. **Expected:** the plan emits these exact steps in order:
   - `请介绍一下石犀科技`
   - `石犀科技 产品介绍`
   - `石犀科技 核心能力`
   - `石犀科技 适用场景`
3. **Expected:** the first step is `primary`, later steps are `expansion`, `stop_after_first_success == True`, and audit metadata records `query_count == 4` plus `generated_from_entity == True`.

### 7. Single-query profiles do not expand and dedupe repeated matched terms

1. In the same planner suite, inspect the `pricing_lookup` case.
2. **Expected:** the plan emits only the normalized query itself, leaves `stop_after_first_success == False`, and dedupes repeated matched terms down to `matched_terms == ["价格"]` in the audit payload.

### 8. The execution adapter dedupes duplicate rows and stops after the first successful expansion step

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q`.
2. Inspect the adapter early-stop case.
3. **Expected:** the adapter executes `请介绍一下石犀科技` first, then `石犀科技 产品介绍`, dedupes duplicate rows with the same KB/title/content key, records step statuses `miss` then `hit`, sets `early_stopped == True` on the hit step, and never executes `石犀科技 核心能力`.

### 9. The execution adapter records failed steps without inventing hits

1. In the same adapter suite, inspect the failure-path case.
2. **Expected:** when one search step fails, `search_failures` contains the failure token, the failed step is recorded with `status == "failed"` and its error message, and `stopped_early == False` because no successful hit occurred.

### 10. The reranker applies explainable business weighting and keeps the best retained rows

1. In the reranker suite, inspect the product-overview ranking case.
2. **Expected:** the product-intro row outranks the generic FAQ row because the reranker adds title/entity/doc_type/section boosts, and the retained row exposes a `score_breakdown` with explicit `base_score`, `title_exact`, `entity_match`, `doc_type`, `section`, `diversity_penalty`, and threshold values.

### 11. Duplicate titles are diversity-filtered and keyword-fallback thresholds differ from hybrid thresholds

1. In the same reranker suite, inspect the keyword-fallback duplicate-title case.
2. **Expected:** only one duplicate-title row is retained, the retained row still passes because the keyword threshold is lower than the normal threshold, and explainability fields remain present.

### 12. StepFun runtime uses the active config snapshot to drive the new retrieval seam end to end

1. In `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`, inspect `test_search_internal_knowledge_uses_config_driven_resolution_planning_adapter_and_reranking`.
2. **Expected:** with an active config snapshot seeded in the DB, the runtime:
   - rewrites `请介绍一下世袭科技` to `请介绍一下石犀科技`
   - records `entity_resolution.canonical_entities == ["石犀科技"]`
   - selects `intent.intent_key == "company_intro"`
   - emits a `retrieval_plan` whose `stop_after_first_success == True`
   - executes only `请介绍一下石犀科技` and `石犀科技 产品介绍`
   - returns `execution_trace.stopped_early == True`
   - retains the reranked intro row with explainable `score_breakdown`
   - records a hit metric/ledger event against the canonicalized query.

### 13. Product-overview legacy behavior is preserved when no active config snapshot exists

1. In the same runtime suite, inspect the legacy rewritten-query cases.
2. **Expected:** when config is absent, StepFun still builds rewritten queries through the legacy helper path, can early-stop on product-overview queries after the first successful rewritten expansion, and still records the expected hit/miss ledger events.

### 14. Search-failure, missing-query, no-KB, and KB-not-ready paths stay truthful on the existing StepFun route

1. In the same runtime suite, inspect the negative-path tests for missing query, no KB bound, KB not ready, explicit search failure, and unexpected exception.
2. **Expected:** the runtime keeps the existing response semantics (`缺少 query 参数`, `当前会话未关联内部知识库`, `内部知识库文档尚未处理完成，请稍后重试`, `知识检索失败`) and records matching ledger/metric statuses instead of masking them behind the new pipeline.

## Edge Cases

### A. Active config missing
- **Expected:** StepFun falls back to the existing legacy rewritten-query loop and does not hard-fail just because the new knowledge-engine snapshot is absent.

### B. Early-stop product-overview execution
- **Expected:** `retrieval_plan.steps` may contain more expansions than `rewritten_queries` or `execution_trace.executed_steps`; this is correct and proves later steps were planned but intentionally not executed.

### C. Duplicate retrieval rows
- **Expected:** rows with the same `(knowledge_base_id, title/source, content)` key are deduped before reranking and before final results are returned.

### D. Missing ranking profile
- **Expected:** reranking degrades to ordered passthrough with `score_breakdown.strategy == "passthrough"` rather than dropping rows or failing the request.

## Failure Signals

- Alias queries no longer normalize to canonical entities, or canonical entity mentions stop emitting traceable matches.
- Intent classification bypasses the DB-backed rule priority order or stops requiring entity presence for `entity_keyword_contains` rules.
- Product-overview planning no longer emits deterministic progressive steps.
- The adapter executes expansion steps after an early-stop hit, or hides failed steps from the trace.
- StepFun runtime responses stop exposing `entity_resolution`, `intent`, `retrieval_plan`, or `execution_trace` when an active config snapshot exists.
- `rewritten_queries` starts reporting the full planned step list instead of the actually executed queries.
- Reranker explainability fields are dropped by the response transformation layer.
- Search-failure / no-KB / KB-not-ready behavior regresses behind the new pipeline.

## Requirements Proved By This UAT

No requirement status changes are claimed at slice close-out. This UAT proves the new query-understanding and retrieval-execution seam needed for downstream answerability/debug work, not a new learner-facing requirement transition.

## Not Proved By This UAT

- Coverage answerability, answer assembly, or compatibility surfaces.
- A learner-visible debug API or completed-session report/replay parity for the new query-understanding fields.
- End-to-end browser proof beyond the focused StepFun runtime/backend seam.

## Notes For The Next Slice

Build S03 directly on the new retrieval-truth seam. Do not re-derive entity resolution, intent selection, or executed queries from handler-local heuristics. Use `retrieval_plan.steps` for what was planned and `execution_trace.executed_steps` / `rewritten_queries` for what actually ran.
