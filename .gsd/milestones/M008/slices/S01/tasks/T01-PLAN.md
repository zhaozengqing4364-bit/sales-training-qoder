---
estimated_steps: 3
estimated_files: 5
skills_used:
  - safe-grow
  - fastapi-python
  - test-driven-development
  - verification-before-completion
---

# T01: Normalize retrieval ledger events in the search helper layer

**Slice:** S01 — 会话检索账本落库
**Milestone:** M008

## Description

Define one provider-neutral retrieval-ledger event shape before persistence so every internal-search hit, miss, and failure path records the same bounded truth. The executor should load `safe-grow`, `fastapi-python`, `test-driven-development`, and `verification-before-completion` before coding. Work only on the existing helper/searcher seam; do not introduce a second result schema or any new route.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `search_internal_knowledge(...)` orchestration | return a normalized failure event and keep counters compatible | record timeout/failure state as a bounded ledger event instead of dropping the attempt | normalize to safe empty/failure summaries instead of persisting raw rows |
| transformed retrieval result payload | cap and sanitize result summaries before they reach snapshot persistence | keep the event status truthful even when no result summary is available | reject provider-specific/raw row shapes and reuse the existing transformed result schema |

## Load Profile

- **Shared resources**: in-memory retrieval payloads and the eventual JSON snapshot row they will feed.
- **Per-operation cost**: one normalized ledger event plus a bounded subset of transformed result summaries.
- **10x breakpoint**: snapshot/event bloat if entries or per-entry result previews are not capped.

## Negative Tests

- **Malformed inputs**: missing query, unbound KBs, and malformed search results still produce safe bounded failure/no-op events.
- **Error paths**: `kb_not_ready`, explicit search failure, and unexpected exception paths all create truthful ledger events.
- **Boundary conditions**: repeated hits/misses trim to the configured ledger cap and per-entry result-summary cap.

## Steps

1. Define the bounded ledger entry shape on top of the current `knowledge_retrieval` metrics, including normalized query text, status, result count, retrieval mode, error summary, and bounded result summaries from the transformed search payload.
2. Thread that richer event payload through `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` and helper utilities without inventing a second result schema.
3. Add focused helper/searcher tests proving normalization, trimming, and truthful hit/miss/failure event creation.

## Must-Haves

- [ ] Keep current flat metrics backward-compatible while adding the ledger.
- [ ] Never persist raw provider payloads or unbounded snippets.
- [ ] Reuse the transformed search result shape so later slices read one truth source.

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_knowledge_helpers.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`
- Inspect test assertions to confirm hit, miss, `kb_not_ready`, and failure outcomes each create one bounded ledger event.

## Observability Impact

- Signals added/changed: normalized retrieval ledger events are created for hit/miss/failure before persistence.
- How a future agent inspects this: rerun the focused helper/searcher unit pack and inspect the event payloads it asserts.
- Failure state exposed: whether a retrieval attempt was dropped, oversized, or mislabeled before it ever reached snapshot persistence.

## Inputs

- `backend/src/sales_bot/websocket/components/stepfun_helpers.py` — current flat `knowledge_retrieval` metric defaults.
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — transformed retrieval payload helpers and immutable snapshot merge helpers.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — current search orchestration and metric callback seam.
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — existing helper-level coverage.
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` — existing search-orchestration coverage.

## Expected Output

- `backend/src/sales_bot/websocket/components/stepfun_helpers.py` — ledger-aware metric defaults/helpers.
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — bounded provider-neutral ledger-event helpers.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — search outcomes emitting ledger events.
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — helper regressions for normalization and trimming.
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` — search-orchestration regressions for hit/miss/failure ledger events.
