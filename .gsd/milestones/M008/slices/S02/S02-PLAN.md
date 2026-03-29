# S02: knowledge-check 与 report 共用检索真相

**Goal:** 对同一条 completed sales session 连续请求 /api/v1/practice/sessions/{id}/knowledge-check 和 /api/v1/practice/sessions/{id}/report，两边返回一致的 retrieval 事实与分层解释：是否触发检索、何时检索、命中了什么、为什么 miss 或失败。
**Demo:** After this: 对同一条 completed session 连续请求 `/api/v1/practice/sessions/{id}/knowledge-check` 和 `/api/v1/practice/sessions/{id}/report`，两边返回一致的 retrieval 事实与分层解释。

## Tasks
- [x] **T01: Add build_retrieval_facts() shared read model that preserves knowledge_base_ids and result_summaries from persisted ledger** — Create a pure build_retrieval_facts(...) function in runtime_diagnostics.py that reads from persisted voice_policy_snapshot.runtime_metrics.knowledge_retrieval and produces a structured retrieval_facts dict. This normalizer is the single source of truth for how retrieval ledger entries become structured retrieval facts. It preserves knowledge_base_ids and result_summaries (which the existing _normalize_knowledge_retrieval_attempt drops), normalizes KB binding, latest attempt, bounded recent attempts, and structured miss/failure explanations. Include comprehensive unit tests.
  - Estimate: 45m
  - Files: backend/src/common/conversation/runtime_diagnostics.py, backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v
- [x] **T02: Wire build_retrieval_facts() into SessionEvidenceService.build_projection for sales sessions as copy-on-write overlay** — Wire the shared build_retrieval_facts(...) into SessionEvidenceService.build_projection(...) so that completed sales sessions get effectiveness_snapshot["retrieval_facts"] derived from voice_policy_snapshot.runtime_metrics.knowledge_retrieval. This must be a projection-only overlay (read-time augmentation, not persisted back). Add unit tests proving the field appears in projection.effectiveness_snapshot and that the persisted session.effectiveness_snapshot is not mutated.
  - Estimate: 30m
  - Files: backend/src/common/conversation/session_evidence.py, backend/tests/unit/test_session_evidence_service.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -v -k 'retrieval_facts'
- [x] **T03: Added retrieval_facts passthrough in build_session_runtime_diagnostics so knowledge-check and report routes return identical retrieval truth for completed sessions** — Extend build_session_runtime_diagnostics(...) so that when projection_effectiveness_snapshot already contains retrieval_facts (i.e., the route has already resolved a completed-session projection), the diagnostics response includes that same retrieval_facts payload as a top-level field. Keep all existing backward-compatible fields (status, summary, last_*, recent_queries, etc.) unchanged. The live-session path remains unchanged. Add unit tests proving reuse and backward compatibility.
  - Estimate: 30m
  - Files: backend/src/common/conversation/runtime_diagnostics.py, backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v -k 'retrieval_facts'
- [ ] **T04: Contract/integration proof: same-session retrieval facts parity** — Add contract and integration tests proving that the same completed sales session returns consistent retrieval_facts through both GET /api/v1/practice/sessions/{id}/knowledge-check and GET /api/v1/practice/sessions/{id}/report. The contract test uses mock sessions with populated voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts and asserts the retrieval_facts payloads are structurally identical. The integration test extends the existing test_voice_runtime_session_snapshot.py suite. Also verify that claim_truth and retrieval_facts remain distinct — a session with retrieval hits can still have claim_truth=weak_evidence.
  - Estimate: 30m
  - Files: backend/tests/contract/test_practice_evidence_contract.py, backend/tests/integration/test_voice_runtime_session_snapshot.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_voice_runtime_session_snapshot.py -v -k 'retrieval_facts'
