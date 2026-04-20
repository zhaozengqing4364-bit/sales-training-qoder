---
estimated_steps: 5
estimated_files: 2
skills_used:
  - pydantic
---

# T01: Build shared retrieval-truth read model from persisted ledger

**Slice:** S02 — knowledge-check 与 report 共用检索真相
**Milestone:** M008

## Description

Build a pure `build_retrieval_facts(...)` function in `runtime_diagnostics.py` that reads from persisted `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` and produces a structured `retrieval_facts` dict. This is the single normalization point that both projection (report) and diagnostics (knowledge-check) will call, preventing parity drift.

The current `_normalize_knowledge_retrieval_attempt(...)` strips `knowledge_base_ids` and `result_summaries` — this task creates a richer normalizer that preserves those fields while staying bounded.

## Steps

1. **Define the retrieval_facts output shape.** Add `build_retrieval_facts(voice_policy_snapshot: dict[str, Any] | None) -> dict[str, Any] | None` in `backend/src/common/conversation/runtime_diagnostics.py`. It should read `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` (the S01 persisted shape) and return:
   ```python
   {
       "kb_bound": bool,                    # whether knowledge_base_ids is non-empty
       "knowledge_base_ids": list[str],     # normalized KB IDs
       "knowledge_base_count": int,         # len of above
       "retrieval_enabled": bool,           # from runtime_metrics.knowledge_retrieval or tool_policy
       "status": str,                       # "hit" | "miss" | "not_triggered" | "kb_not_ready" | "search_failed" | "no_knowledge_base" | "disabled"
       "summary": str,                      # human-readable Chinese explanation
       "attempt_count": int,                # from flat metrics
       "hit_count": int,                    # from flat metrics hit_query_count
       "hit_rate": float,                   # rounded to 4 decimals
       "latest_attempt": {...} | None,      # the latest valid ledger entry, FULLY normalized WITH knowledge_base_ids and result_summaries
       "recent_attempts": list[dict],       # bounded to last 10 valid entries, fully normalized
       "miss_explanation": str | None,      # structured explanation when status is miss (e.g., "查询'xxx'未命中知识库内容，可能需要补充相关文档")
       "failure_explanation": str | None,   # structured explanation when status is search_failed
   }
   ```
   Return `None` when `voice_policy_snapshot` is None, not a dict, or has no `runtime_metrics`.

2. **Create a richer attempt normalizer.** Add `_normalize_retrieval_attempt_full(...)` alongside the existing `_normalize_knowledge_retrieval_attempt(...)`. The new one preserves `knowledge_base_ids` (bounded to 8) and `result_summaries` (bounded to 3, snippet ≤ 240 chars) — reusing the same bounds from `stepfun_knowledge_helpers.py`. Import the constants or replicate them with clear comments referencing the source.

3. **Implement status/summary derivation.** Derive `status` and `summary` from the same logic currently in `build_session_runtime_diagnostics(...)`: check KB binding, internal_retrieval_enabled flag, kb_not_ready, search_failed, attempt_count, hit count. Reuse the existing Chinese summary strings. Extract this logic so it's callable from both the new function and the existing diagnostics builder (avoid duplication).

4. **Build miss/failure explanations.** For `miss_explanation`: when status is "miss", include the last query text and a suggestion to check KB coverage. For `failure_explanation`: include the error_summary from the latest failed attempt. Keep these bounded and provider-neutral.

5. **Write comprehensive unit tests.** In `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`, add a new test class or section for `build_retrieval_facts`:
   - No voice_policy_snapshot → returns None
   - No runtime_metrics → returns None
   - No knowledge_retrieval → returns status="not_triggered" with defaults
   - Hit case: recent_attempts has entries with status="hit", result_summaries present, kb_bound=True
   - Miss case: recent_attempts has entries with status="miss", miss_explanation populated
   - Failure case: recent_attempts has search_failed entry, failure_explanation populated
   - Bounded recent_attempts: 15 entries → only last 10 kept
   - Malformed entries in recent_attempts are skipped
   - knowledge_base_ids and result_summaries are preserved in the output

## Must-Haves

- [ ] `build_retrieval_facts(...)` is a pure function with no DB/session/live-handler dependencies
- [ ] Output preserves `knowledge_base_ids` and `result_summaries` from ledger entries (the key gap vs existing normalizer)
- [ ] Status/summary vocabulary matches existing knowledge-check vocabulary (hit/miss/not_triggered/kb_not_ready/search_failed/no_knowledge_base/disabled)
- [ ] `recent_attempts` is bounded (max 10) and skips malformed entries
- [ ] Unit tests cover hit/miss/failure/empty/malformed/bounded cases

## Verification

```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v
```

All new + existing tests must pass.

## Inputs

- `backend/src/common/conversation/runtime_diagnostics.py` — where build_retrieval_facts will be added
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — reference for ledger entry shape and bounds (MAX_KNOWLEDGE_RETRIEVAL_LEDGER_ENTRIES=10, MAX_KNOWLEDGE_RETRIEVAL_RESULT_SUMMARIES=3, MAX_KNOWLEDGE_RETRIEVAL_SNIPPET_CHARS=240, MAX_KNOWLEDGE_RETRIEVAL_LEDGER_KB_IDS=8)
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py` — existing tests to extend

## Expected Output

- `backend/src/common/conversation/runtime_diagnostics.py` — added build_retrieval_facts(...) and _normalize_retrieval_attempt_full(...)
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py` — new test class covering the shared read model
