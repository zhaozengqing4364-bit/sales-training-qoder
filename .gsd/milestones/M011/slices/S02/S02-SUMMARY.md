---
id: S02
parent: M011
milestone: M011
provides:
  - A deterministic entity-resolution seam that rewrites configured aliases to canonical entities and returns auditable match traces.
  - A DB-backed intent-classification and retrieval-planning seam that selects retrieval profiles and emits progressive query steps with explicit audit metadata.
  - A config-driven retrieval execution path on the shipped StepFun internal knowledge search entrypoint, including step-level execution traces, early-stop behavior, and explainable reranked results.
  - A retrieval-truth seam that downstream slices can use for answerability, answer assembly, compatibility, and debug/report surfaces without re-deriving query-understanding behavior from handler-local heuristics.
requires:
  - slice: S01
    provides: The project-owned `common.knowledge_engine` seam, active-config repository, and normalized control-plane snapshot DTOs that S02 wires into runtime query understanding and retrieval execution.
affects:
  - S03
  - S04
key_files:
  - backend/src/common/knowledge_engine/entity_resolver.py
  - backend/src/common/knowledge_engine/intent_classifier.py
  - backend/src/common/knowledge_engine/retrieval_planner.py
  - backend/src/common/knowledge_engine/haystack_adapter.py
  - backend/src/common/knowledge_engine/reranker.py
  - backend/src/common/knowledge_engine/__init__.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
  - backend/tests/unit/common/test_knowledge_entity_resolver.py
  - backend/tests/unit/common/test_knowledge_intent_classifier.py
  - backend/tests/unit/common/test_knowledge_retrieval_planner.py
  - backend/tests/unit/common/test_haystack_adapter.py
  - backend/tests/unit/common/test_knowledge_reranker.py
  - backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - Use deterministic alias/canonical entity matching with explicit trace payloads and defer fuzzy NLP until retrieval evidence proves it is needed.
  - Keep intent classification and retrieval planning on project-owned DTOs with `regex`, `keyword_contains`, and `entity_keyword_contains` rule types, instead of adding new control-plane columns or pulling legacy websocket helper state into the new engine seam.
  - When an active config snapshot exists, drive StepFun internal knowledge search through entity resolution → intent classification → retrieval planning → execution adapter → business reranker; when it does not, fall back to the legacy rewritten-query loop.
  - Treat `retrieval_plan.steps` as the planned query set and `execution_trace.executed_steps` plus `rewritten_queries` as the actual executed query set, especially when early-stop prevents later expansion steps from running.
patterns_established:
  - Keep query understanding, planning, and ranking on project-owned DTOs and runtime payloads rather than leaking ORM rows, raw control-plane JSON, or Haystack types into handler code or downstream consumers.
  - Preserve the distinction between planned retrieval steps and actually executed retrieval steps; when early-stop is enabled, expose both `retrieval_plan.steps` and `execution_trace.executed_steps`/`rewritten_queries` so downstream answerability and debug surfaces can reason about real execution.
  - Use config-driven runtime integration with safe legacy fallback: StepFun should prefer the active knowledge-engine snapshot when present, but missing control-plane state must degrade to the existing legacy rewritten-query loop instead of breaking knowledge search entirely.
  - Attach explainability at the row and execution layers before response shaping, then keep those fields alive through helper transforms so downstream consumers do not lose ranking or execution truth.
observability_surfaces:
  - `entity_resolution` payload on StepFun internal knowledge search responses, including canonical entities, normalized query, and per-match trace metadata.
  - `intent` and `retrieval_plan` payloads on StepFun internal knowledge search responses, showing selected profile, matched terms, strategy, stop-after-first-success behavior, and planned query steps.
  - `execution_trace` plus `rewritten_queries` on StepFun internal knowledge search responses, showing what actually ran, where hits/misses/failures occurred, and whether early-stop triggered.
  - Per-result reranker explainability fields (`score_breakdown`, `ranking_passed`) preserved through transformed StepFun search results.
  - Focused backend slice-close verification gates: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_entity_resolver.py -q`, `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q`, and `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q`.
  - Fresh LSP diagnostics on `backend/src/common/knowledge_engine/*.py`, `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`, and the focused test files all reported no issues.
drill_down_paths:
  - .gsd/milestones/M011/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M011/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M011/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T04:19:35.852Z
blocker_discovered: false
---

# S02: Query understanding、planner 与 Haystack 检索执行

**Delivered the first real query-understanding and retrieval-execution seam for the new knowledge engine: StepFun internal knowledge search now resolves configured entities, classifies intent from DB-backed rules, emits a progressive retrieval plan, executes only the needed search steps, and returns explainable reranked results with execution traces.**

## What Happened

S02 turned the M011/S01 control-plane foundation into a working retrieval pipeline on the shipped StepFun internal knowledge search entrypoint. T01 introduced a deterministic `KnowledgeEntityResolver` that rewrites configured aliases to canonical entities, preserves canonical pass-through, and emits auditable per-match traces instead of opaque NLP behavior. T02 then added a project-owned `KnowledgeIntentClassifier` plus `KnowledgeRetrievalPlanner` on top of the normalized DB snapshot: runtime now supports `regex`, `keyword_contains`, and `entity_keyword_contains` rules, picks a query profile from DB-backed config, and emits progressive retrieval steps plus audit metadata without reaching back into legacy websocket helper state. T03 completed the runtime seam by implementing `KnowledgeHaystackAdapter` and `KnowledgeReranker`, then wiring StepFun internal knowledge search to load the active knowledge-engine config snapshot and run entity resolution → intent classification → retrieval planning → execution adapter → business reranking when config exists, while preserving the legacy rewritten-query loop as fallback when it does not.

The shipped behavior now matches the slice goal. For product-overview queries such as “请介绍一下世袭科技”, StepFun search normalizes the query to the canonical entity, exposes `entity_resolution`, `intent`, `retrieval_plan`, `execution_trace`, and actual `rewritten_queries`, early-stops after the first successful expansion step when the selected profile says to do so, and returns only the reranked retained rows with explainable `score_breakdown` / `ranking_passed` metadata. The runtime no longer hides the pre-ranking and execution decisions inside handler-local heuristics; downstream answerability, answer assembly, and debug/report slices can now build on an explicit retrieval-truth seam.

This slice also established two important runtime patterns for downstream work. First, query understanding stays on project-owned DTOs rather than leaking ORM rows, raw control-plane JSON, or Haystack types into the execution path. Second, the StepFun helper now distinguishes the full planned query list from the queries actually executed: `retrieval_plan.steps` shows what was planned, while `execution_trace.executed_steps` and `rewritten_queries` show what really ran before early-stop or failure. That distinction matters for S03/S04 answerability and debug work because it prevents future consumers from assuming unexecuted expansion steps actually ran.

Fresh slice-close verification reran every slice-plan gate from repo root and all passed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_entity_resolver.py -q` (3 passed), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q` (4 passed), and `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q` (16 passed). Fresh LSP diagnostics on the new query-understanding modules, runtime integration files, helper exports, and focused tests reported no issues. During close-out, an initial parallel auto-mode pytest run proved invalid because this repo’s pytest-cov setup shares the top-level `.coverage` SQLite file; final evidence therefore uses serial reruns only, and that gotcha has been written into `.gsd/KNOWLEDGE.md` for future slices.

Operationally, the new runtime seam is inspectable but not fully productized yet. Health is currently visible through the retrieval payload itself: successful config-driven runs expose `entity_resolution`, `intent`, `retrieval_plan`, `execution_trace`, executed `rewritten_queries`, and reranker `score_breakdown` fields. Failure is visible through existing `search_failed` / `kb_not_ready` responses plus empty or fallback config-driven branches. Recovery is straightforward today: verify that an enabled active config snapshot exists, inspect entity resolution and intent traces, compare planned steps versus executed steps, and if no active snapshot is present rely on the preserved legacy rewritten-query loop. The main monitoring gap is that S02 stops at focused backend/runtime verification; there is not yet a dedicated answerability/debug surface or completed-session compatibility proof for these new fields. That is the explicit handoff to S03 and S04.

## Verification

Fresh slice-close verification reran every slice-plan backend gate serially from repo root and all passed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_entity_resolver.py -q` (3 passed), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q` (4 passed), and `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q` (16 passed). Fresh LSP diagnostics on the new knowledge-engine modules, helper exports, runtime integration file, and focused tests reported no issues.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

No shipped product-scope deviation from the slice plan. During slice-close verification, an initial parallel auto-mode pytest attempt produced an invalid pytest-cov `.coverage` SQLite race even though the tests themselves passed; final verification was rerun serially and the gotcha was documented in `.gsd/KNOWLEDGE.md`.

## Known Limitations

S02 stops at query understanding, retrieval execution, and ranking. Entity resolution is still deterministic alias/canonical matching only; intent rules are currently limited to `regex`, `keyword_contains`, and `entity_keyword_contains`; and the new runtime traces are proven through focused backend/runtime tests rather than a learner-visible debug API or completed-session compatibility surface. When no active config snapshot exists, StepFun intentionally falls back to the legacy rewritten-query loop instead of surfacing the new planning/execution payloads.

## Follow-ups

S03 should build coverage answerability, answer assembly, and compatibility surfaces directly on the new retrieval-truth seam (`entity_resolution` / `intent` / `retrieval_plan` / `execution_trace` / reranked rows) rather than reintroducing handler-local heuristics. S04 should expose the same seam through debug/eval/reporting tooling so recent runs can be inspected end to end without relying only on focused unit tests.

## Files Created/Modified

- `backend/src/common/knowledge_engine/entity_resolver.py` — Added deterministic alias/canonical entity normalization with auditable per-match trace metadata for downstream planner/debug consumers.
- `backend/src/common/knowledge_engine/intent_classifier.py` — Added DB-backed intent classification over normalized queries with regex, keyword, and entity+keyword rule support plus explicit match traces and fallback behavior.
- `backend/src/common/knowledge_engine/retrieval_planner.py` — Added progressive retrieval-plan generation that emits profile-owned query steps, stop-after-first-success behavior, and audit metadata.
- `backend/src/common/knowledge_engine/haystack_adapter.py` — Added the execution adapter that runs planner steps against the existing knowledge search service, dedupes rows, records step-level hit/miss/failure status, and supports early-stop.
- `backend/src/common/knowledge_engine/reranker.py` — Added an explainable business reranker that combines title/entity/doc_type/section weighting with diversity suppression and per-row score breakdowns.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — Wired the active StepFun internal knowledge search path to load the active config snapshot, run the new query-understanding/execution pipeline, expose execution traces, and preserve legacy fallback behavior when config is absent.
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — Preserved transformed search-row explainability fields so reranker score breakdowns and related execution metadata survive the response shaping layer.
- `backend/tests/unit/common/test_knowledge_entity_resolver.py` — Locked alias mapping, canonical pass-through, and no-match fallback behavior for the deterministic entity resolver.
- `backend/tests/unit/common/test_knowledge_intent_classifier.py` — Locked priority ordering, entity+keyword gating, and explicit profile selection for DB-backed intent classification.
- `backend/tests/unit/common/test_knowledge_retrieval_planner.py` — Locked progressive query planning, stop-after-first-success semantics, and matched-term deduplication for retrieval planning.
- `backend/tests/unit/common/test_haystack_adapter.py` — Locked execution-step tracing, deduplication, failure capture, and early-stop behavior for the adapter.
- `backend/tests/unit/common/test_knowledge_reranker.py` — Locked explainable score breakdowns, keyword-threshold behavior, and duplicate-title suppression for business reranking.
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` — Locked end-to-end StepFun runtime behavior for config-driven entity resolution, planning, early-stop execution traces, reranked results, and preserved legacy fallback semantics.
- `.gsd/KNOWLEDGE.md` — Recorded the shared `.coverage` pytest-cov race so future auto-mode closers do not invalidate backend verification by running focused pytest gates in parallel.
- `.gsd/PROJECT.md` — Updated current project state to record that M011/S02 is now complete and to hand off S03 onto the new retrieval-truth seam.
