---
estimated_steps: 3
estimated_files: 2
skills_used:
  - fastapi-python
---

# T04: Contract/integration proof: same-session retrieval facts parity

**Slice:** S02 — knowledge-check 与 report 共用检索真相
**Milestone:** M008

## Description

Add contract and integration tests proving the S02 parity guarantee: the same completed sales session returns consistent `retrieval_facts` through both `GET /api/v1/practice/sessions/{id}/knowledge-check` and `GET /api/v1/practice/sessions/{id}/report`. Also prove that claim_truth and retrieval_facts remain distinct — retrieval hits do not imply claim verification.

## Steps

1. **Contract test for retrieval_facts parity.** In `backend/tests/contract/test_practice_evidence_contract.py`, add a new test class or test function:
   - Create a mock completed sales session with populated `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts` (include both hit and miss entries, with `knowledge_base_ids` and `result_summaries`).
   - Build the report projection via `SessionEvidenceService.build_projection(...)` and extract `effectiveness_snapshot["retrieval_facts"]`.
   - Build the knowledge-check diagnostics via `build_session_runtime_diagnostics(...)` with `projection_effectiveness_snapshot` set to the projection's effectiveness_snapshot, and extract the top-level `retrieval_facts`.
   - Assert the two `retrieval_facts` payloads are structurally identical (same keys, same values for status, summary, latest_attempt, recent_attempts, kb_bound, etc.).
   - Assert `claim_truth` and `retrieval_facts` are independent: set up a scenario where retrieval status is "hit" but claim_truth is "weak_evidence" — verify both values are preserved without one overriding the other.

2. **Integration test extending existing suite.** In `backend/tests/integration/test_voice_runtime_session_snapshot.py`, add test(s):
   - Use the existing session fixture pattern to create a completed sales session with retrieval ledger entries in `voice_policy_snapshot`.
   - Call the report route handler to get `effectiveness_snapshot.retrieval_facts`.
   - Call the knowledge-check route handler to get `retrieval_facts`.
   - Assert structural parity.
   - Follow the existing integration test patterns in the file (see existing test functions for fixture setup conventions).

3. **Claim-truth independence proof.** In either the contract or integration test file, add an explicit test proving:
   - Session with `retrieval_facts.status = "hit"` + `retrieval_facts.latest_attempt.result_count > 0`
   - But `claim_truth.status = "weak_evidence"` + `claim_truth.source = "sales_coaching_arbiter"`
   - Both fields are present and correct in both report and knowledge-check responses
   - This proves the two concepts are orthogonal as designed

## Must-Haves

- [ ] Contract test proves retrieval_facts from report projection equals retrieval_facts from knowledge-check diagnostics for the same session
- [ ] Integration test proves the same parity through actual route handlers (or close-to-route service calls)
- [ ] Claim-truth and retrieval_facts independence is explicitly tested — hit retrieval + weak_evidence claim truth coexist
- [ ] Tests use realistic voice_policy_snapshot fixtures with recent_attempts containing knowledge_base_ids and result_summaries

## Verification

```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_voice_runtime_session_snapshot.py -v -k 'retrieval_facts'
```

## Inputs

- `backend/src/common/conversation/runtime_diagnostics.py` — T01+T03 output with build_retrieval_facts and retrieval_facts in diagnostics
- `backend/src/common/conversation/session_evidence.py` — T02 output with retrieval_facts in projection
- `backend/tests/contract/test_practice_evidence_contract.py` — existing contract tests to extend
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — existing integration tests to extend

## Expected Output

- `backend/tests/contract/test_practice_evidence_contract.py` — new retrieval_facts parity contract tests
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — new retrieval_facts parity integration tests
