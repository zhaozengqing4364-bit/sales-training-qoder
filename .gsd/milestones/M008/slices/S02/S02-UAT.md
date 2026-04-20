# S02: knowledge-check 与 report 共用检索真相 — UAT

**Milestone:** M008
**Written:** 2026-03-29T18:03:44.623Z

# S02: knowledge-check 与 report 共用检索真相 — UAT

**Milestone:** M008
**Written:** 2026-03-28

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: The slice delivers backend read-model parity between two API routes. All behavior is verifiable through automated contract and integration tests. No browser or live-runtime verification is needed — the contract is purely about data shape consistency across route handlers.

## Preconditions

- Backend test environment with `backend/venv` and dependencies installed
- SQLite test database (in-memory, auto-created by test fixtures)
- No running server required — tests use FastAPI TestClient

## Smoke Test

```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml \
  tests/contract/test_practice_evidence_contract.py \
  tests/integration/test_voice_runtime_session_snapshot.py \
  -v -k retrieval_facts
```

**Expected:** 5 tests pass (3 contract + 2 integration), 0 failures.

## Test Cases

### 1. Report and knowledge-check return identical retrieval_facts for a completed sales session with retrieval hits

1. Create a mock completed sales session with `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts` containing one hit entry (status=hit, result_count=3, knowledge_base_ids=["kb-1"], result_summaries=["summary text"])
2. Request report projection via `SessionEvidenceService.build_projection()` — assert `effectiveness_snapshot["retrieval_facts"]["latest_attempt"]["status"] == "hit"`
3. Request knowledge-check diagnostics via `build_session_runtime_diagnostics()` with `live_runtime_active=False` — assert `result["retrieval_facts"]["latest_attempt"]["status"] == "hit"`
4. **Expected:** Both payloads have structurally identical `retrieval_facts` including `knowledge_base_ids` and `result_summaries` on the hit entry. All canonical keys present (kb_binding, retrieval_status, latest_attempt, recent_attempts, miss_explanation, failure_details).

**Covered by:** `test_report_and_knowledge_check_return_identical_retrieval_facts_for_completed_sales_session` (contract), `test_completed_sales_session_returns_identical_retrieval_facts_through_report_and_knowledge_check` (integration)

### 2. Retrieval status=hit does not force claim_truth=evidence_verified (claim-truth independence)

1. Create a session with retrieval hits AND claim_truth=weak_evidence
2. Request both report and knowledge-check routes
3. **Expected:** `retrieval_facts.retrieval_status == "hit"` AND `claim_truth == "weak_evidence"` on both surfaces. Neither field overrides the other.

**Covered by:** `test_retrieval_facts_and_claim_truth_are_independent_retrieval_hit_with_weak_evidence` (contract), `test_retrieval_facts_hit_with_weak_evidence_claim_truth_proves_independence` (integration)

### 3. Miss status retrieval_facts parity between report and knowledge-check

1. Create a session where the latest retrieval attempt was a miss (status=miss, miss_reason="no_relevant_results")
2. Request both routes
3. **Expected:** Both surfaces return `retrieval_status == "miss"` with the same `miss_explanation`.

**Covered by:** `test_retrieval_facts_parity_with_miss_status` (contract)

### 4. Live session does not get retrieval_facts from projection

1. Call `build_session_runtime_diagnostics()` with `live_runtime_active=True` even though projection_effectiveness_snapshot contains retrieval_facts
2. **Expected:** `result["retrieval_facts"] == None` — live sessions always use live handler truth.

**Covered by:** `test_diagnostics_returns_none_retrieval_facts_for_live_session`, `test_diagnostics_ignores_retrieval_facts_in_projection_for_live_session` (unit)

### 5. Projection overlay does not mutate persisted session

1. Create a sales session with voice_policy_snapshot containing retrieval ledger data
2. Call `build_projection()` twice
3. **Expected:** `session.effectiveness_snapshot` remains unchanged after both calls (copy-on-write overlay only).

**Covered by:** `test_get_projection_attaches_retrieval_facts_for_completed_sales_session` (unit)

## Edge Cases

### Empty voice_policy_snapshot

1. Create a session with `voice_policy_snapshot=None`
2. **Expected:** Projection completes without error, no retrieval_facts attached.

**Covered by:** `test_get_projection_skips_retrieval_facts_when_voice_policy_snapshot_missing`

### Presentation session excluded

1. Create a presentation-type session with retrieval ledger data
2. Call `build_projection()`
3. **Expected:** No `retrieval_facts` in projection (sales-gated overlay).

**Covered by:** Existing projection tests confirm presentation path is unaffected.

### Disabled knowledge retrieval

1. Create a session where `knowledge_retrieval.enabled == False`
2. **Expected:** `retrieval_status == "disabled"` in retrieval_facts.

**Covered by:** Unit test `test_build_retrieval_facts_disabled_kb`

### Malformed recent_attempts entry

1. Create a session with a recent_attempts entry missing required fields
2. **Expected:** Entry is skipped gracefully; retrieval_facts still populated from valid entries.

**Covered by:** Unit test `test_build_retrieval_facts_malformed_entry_skipped`

## Failure Signals

- Any test in the retrieval_facts filter fails → parity contract is broken
- `retrieval_facts` appears in live-session diagnostics → live/projection truth confusion
- `retrieval_facts` appears in presentation session projection → sales-gate regression

## Requirements Proved By This UAT

- R010 (integration) — knowledge-check and report now share a single retrieval truth normalizer
- R011 (continuity) — retrieval facts are persisted via projection overlay, making them available for report/replay contexts

## Not Proven By This UAT

- Live-runtime retrieval fact delivery (live sessions use handler truth, not projection)
- Frontend rendering of retrieval_facts (deferred to S03)
- `used_in_reasoning` inference (explicitly out of scope per D114/D116)

## Notes for Tester

- All tests run against in-memory SQLite — no external dependencies needed
- Contract tests use mock sessions; integration tests use FastAPI TestClient with real route handlers
- If any test in the filtered suite fails, check `runtime_diagnostics.py` for the `build_retrieval_facts` function and `session_evidence.py` for the projection overlay — these are the two seams that maintain parity
