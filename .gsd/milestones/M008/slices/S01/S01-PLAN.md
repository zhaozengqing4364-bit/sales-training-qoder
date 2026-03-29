# S01: 会话检索账本落库

**Goal:** 在不引入新表或新路由的前提下，把每次 StepFun 内部知识检索的 provider-neutral retrieval ledger 落进 `practice_sessions.voice_policy_snapshot.runtime_metrics.knowledge_retrieval`，让同一条 knowledge-backed session 的 persisted snapshot 能回答是否触发检索、何时检索、查了什么、命中了什么、为什么 miss 或失败。
**Demo:** After this: 查看同一条 knowledge-backed session 的 persisted `voice_policy_snapshot`，可以回答是否发生检索、查了什么、返回了多少结果、为什么 miss 或失败。

## Tasks
- [x] **T01: Normalize retrieval ledger events in the search helper layer** — The executor should load `safe-grow`, `fastapi-python`, `test-driven-development`, and `verification-before-completion` before coding.

Extend the search-helper layer so every internal retrieval outcome can be normalized into one provider-neutral ledger event before persistence is involved.

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
  - Estimate: 50m
  - Files: backend/src/sales_bot/websocket/components/stepfun_helpers.py, backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py, backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py, backend/tests/unit/test_stepfun_knowledge_helpers.py, backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_knowledge_helpers.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
- [x] **T02: Wired provider-neutral retrieval ledger events through the existing StepFun runtime-metrics persistence path with copy-on-write snapshot merges and handler warning-only failure behavior.** — The executor should load `safe-grow`, `fastapi-python`, `test-driven-development`, and `verification-before-completion` before coding.

Once ledger events exist, wire them through the current runtime-metrics persistence path so the session snapshot records them immutably alongside today's counters.

## Failure Modes
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `persist_runtime_metrics_to_session(...)` | leave the previous snapshot intact and fail the focused regression instead of mutating in place | treat as incomplete persistence and keep the old snapshot visible | reject invalid runtime metrics rather than half-writing the session row |
| `StepFunRealtimeHandler._record_knowledge_runtime_metric(...)` | preserve the existing warning path and fail the new regression if ledger events are dropped | keep the preexisting persistence cadence; do not add loops or retries | normalize malformed event payloads before commit or reject them cleanly |

## Load Profile
- **Shared resources**: async DB session, `practice_sessions.voice_policy_snapshot` JSON field, and deep-copy/merge work.
- **Per-operation cost**: one bounded ledger append plus the existing snapshot merge/commit.
- **10x breakpoint**: deep-copy churn or repeated commit amplification if persistence is no longer one-write-per-event.

## Negative Tests
- **Malformed inputs**: missing runtime metrics or malformed ledger state should fail safely without mutating the original snapshot.
- **Error paths**: handler-level failure paths must still preserve `last_status`/`last_error` while writing a bounded ledger entry when possible.
- **Boundary conditions**: repeated persistence keeps the ledger capped and preserves copy-on-write snapshot semantics.

## Steps
1. Extend `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py` so runtime-metric merges carry the bounded ledger into `practice_sessions.voice_policy_snapshot` without mutating the original snapshot object.
2. Update `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` to pass the richer ledger-event payload through `_record_knowledge_runtime_metric(...)` while keeping the current warning-only failure surface.
3. Add focused unit coverage proving copy-on-write persistence, capped repeated writes, and handler-level persistence for hit and failure paths.

## Must-Haves
- [ ] Snapshot persistence remains copy-on-write.
- [ ] Existing flat metrics stay readable after ledger writes.
- [ ] One retrieval attempt still maps to one bounded snapshot update, not a second persistence channel.
  - Estimate: 45m
  - Files: backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py, backend/src/sales_bot/websocket/stepfun_realtime_handler.py, backend/tests/unit/test_stepfun_runtime_metrics_helpers.py, backend/tests/unit/test_stepfun_realtime_handler.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_runtime_metrics_helpers.py backend/tests/unit/test_stepfun_realtime_handler.py
- [ ] **T03: Keep current session routes readable with ledger-backed snapshots** — The executor should load `safe-grow`, `fastapi-python`, `test-driven-development`, and `verification-before-completion` before coding.

Lock the read side on current session routes so ledger-backed snapshots stay truthful and backward-compatible before S02 starts sharing this truth with report.

## Failure Modes
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `build_session_runtime_diagnostics(...)` | keep current knowledge-check summary behavior and fail the new regression if ledger-backed snapshots cannot be read | do not add new polling or runtime dependencies to read the ledger | fall back to the latest valid ledger entry or current flat fields instead of throwing |
| current practice session/detail routes | preserve existing access-control and snapshot-ref behavior | keep current single-read behavior; do not add background fetches | reject runtime-metrics drift that changes `voice_policy_snapshot_ref` |

## Load Profile
- **Shared resources**: one session fetch and current diagnostics normalization on existing routes.
- **Per-operation cost**: one read plus lightweight fallback logic from flat fields to the latest bounded ledger entry.
- **10x breakpoint**: repeated JSON normalization on every read if fallback logic becomes expensive or duplicates work.

## Negative Tests
- **Malformed inputs**: partial or missing flat `last_*` fields should still allow ledger-backed snapshots to read truthfully when a valid latest event exists.
- **Error paths**: completed-session hit/miss/failure snapshots still classify correctly on `knowledge-check` and current detail routes.
- **Boundary conditions**: `voice_policy_snapshot_ref` remains unchanged while runtime metrics churn, and owner/admin access on current session routes does not regress.

## Steps
1. Teach `backend/src/common/conversation/runtime_diagnostics.py` and only the minimal API glue it needs to tolerate the richer `knowledge_retrieval` payload while preserving today's counter/status summary contract.
2. Extend snapshot and contract tests so a completed knowledge-backed session proves the bounded ledger is visible on current session/detail surfaces and `voice_policy_snapshot_ref` still ignores runtime-metric churn across detail/report/replay reads.
3. Re-run the focused route tests sequentially and stop if the implementation starts adding report semantics or new routes that belong to S02 rather than S01.

## Must-Haves
- [ ] No new audit route or report payload redesign in S01.
- [ ] Existing `knowledge-check` status summaries stay compatible with ledger-backed snapshots.
- [ ] Current session routes remain the proof surface for persisted snapshot truth.
  - Estimate: 50m
  - Files: backend/src/common/conversation/runtime_diagnostics.py, backend/src/common/api/practice.py, backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py, backend/tests/integration/test_voice_runtime_session_snapshot.py, backend/tests/contract/test_practice_evidence_contract.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py
