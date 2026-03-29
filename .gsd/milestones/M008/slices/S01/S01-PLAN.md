# S01: 会话检索账本落库

**Goal:** 在不引入新表或新路由的前提下，把每次 StepFun 内部知识检索的 provider-neutral retrieval ledger 落进 `practice_sessions.voice_policy_snapshot.runtime_metrics.knowledge_retrieval`，让同一条 knowledge-backed session 的 persisted snapshot 能回答是否触发检索、何时检索、查了什么、命中了什么、为什么 miss 或失败。
**Demo:** 查看同一条 knowledge-backed session 的 persisted `voice_policy_snapshot`，可以回答是否发生检索、查了什么、返回了多少结果、为什么 miss 或失败。

## Must-Haves

- Persist a bounded, provider-neutral retrieval ledger inside `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` without adding a new table or route.
- Keep existing flat metrics (`attempt_count`, `hit_query_count`, `total_results`, `last_status`, `last_error`) backward-compatible for current `knowledge-check` readers.
- The persisted snapshot must record enough bounded facts to answer whether retrieval happened, what query ran, what result summaries came back, and why miss/failure happened.
- `voice_policy_snapshot_ref` must remain stable while runtime metrics mutate.

## Threat Surface

- **Abuse**: repeated retrieval attempts or oversized result payloads must not bloat the session snapshot; the ledger must stay bounded and normalized.
- **Data exposure**: persist only provider-neutral query/result summaries that are already safe for session diagnostics; do not persist embeddings, raw provider payloads, or secrets.
- **Input trust**: query text and KB search results are untrusted runtime inputs and must be truncated/normalized before snapshot persistence.

## Requirement Impact

- **Requirements touched**: R002, R010, R011.
- **Re-verify**: StepFun internal retrieval persistence, session detail snapshot reads, existing `knowledge-check` status derivation, and `voice_policy_snapshot_ref` stability on current routes.
- **Decisions revisited**: D113, D115, D116.

## Proof Level

- This slice proves: contract + integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_knowledge_helpers.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_runtime_metrics_helpers.py backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py`

## Observability / Diagnostics

- Runtime signals: persisted `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` counters plus a bounded recent-attempt ledger.
- Inspection surfaces: session detail route, `knowledge-check`, and the `PracticeSession.voice_policy_snapshot` row itself.
- Failure visibility: latest retrieval status/error, bounded hit/miss/failure event history, and snapshot-ref stability regressions caught by focused contract tests.
- Redaction constraints: persist provider-neutral summaries only; no embeddings, raw provider payloads, or secrets.

## Integration Closure

- Upstream surfaces consumed: `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py`, `backend/src/common/conversation/runtime_diagnostics.py`, current practice session routes.
- New wiring introduced in this slice: bounded retrieval ledger events flowing from StepFun internal search into persisted runtime metrics and current session readers.
- What remains before the milestone is truly usable end-to-end: S02 must make `/api/v1/practice/sessions/{id}/knowledge-check` and `/api/v1/practice/sessions/{id}/report` explain the same persisted ledger, and S03 must visualize that truth on the report page.

## Tasks

- [ ] **T01: Normalize retrieval ledger events in the search helper layer** `est:50m`
  - Why: Define one provider-neutral event shape before persistence so every hit, miss, and failure path records the same bounded truth.
  - Files: `backend/src/sales_bot/websocket/components/stepfun_helpers.py`, `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`, `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, `backend/tests/unit/test_stepfun_knowledge_helpers.py`, `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`
  - Do: Add a bounded retrieval ledger entry shape on top of the current `knowledge_retrieval` metrics, thread it through the search-helper layer, and cover normalization/trimming for hit, miss, `kb_not_ready`, and failure outcomes without introducing a second result schema.
  - Verify: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_knowledge_helpers.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`
  - Done when: helper/searcher tests prove every retrieval outcome becomes one bounded, provider-neutral ledger event while the current flat metrics remain readable.
- [ ] **T02: Persist retrieval ledger entries through the runtime-metrics path** `est:45m`
  - Why: The slice is not real until those normalized events survive merge/commit into `PracticeSession.voice_policy_snapshot` without mutating the original snapshot object.
  - Files: `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/tests/unit/test_stepfun_runtime_metrics_helpers.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`
  - Do: Extend runtime-metrics merge/persistence helpers and the StepFun handler so one retrieval attempt writes one bounded snapshot update, preserving copy-on-write behavior and the current warning-only failure surface.
  - Verify: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_runtime_metrics_helpers.py backend/tests/unit/test_stepfun_realtime_handler.py`
  - Done when: focused unit tests prove ledger entries survive merge/commit, caps hold across repeated writes, and the original snapshot object is not mutated in place.
- [ ] **T03: Keep current session routes readable with ledger-backed snapshots** `est:50m`
  - Why: S01 should land on existing session surfaces, not only in helpers, while still leaving cross-route report semantics for S02.
  - Files: `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/common/api/practice.py`, `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`, `backend/tests/integration/test_voice_runtime_session_snapshot.py`, `backend/tests/contract/test_practice_evidence_contract.py`
  - Do: Teach current session readers to tolerate the richer `knowledge_retrieval` payload, keep today’s counter/status summary contract, and lock route-level proof that the mutated snapshot is readable while `voice_policy_snapshot_ref` stays frozen.
  - Verify: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py`
  - Done when: current detail/knowledge-check routes read ledger-backed snapshots truthfully, snapshot refs ignore runtime-metric churn, and no new audit/report surface was introduced.

## Files Likely Touched

- `backend/src/sales_bot/websocket/components/stepfun_helpers.py`
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
- `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
