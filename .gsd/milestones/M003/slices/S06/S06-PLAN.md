# S06: scoring 收口与 replay/highlights 解锁

**Goal:** Keep the shipped sales lifecycle contract at immediate `status="scoring"`, then unlock same-session replay/highlights only after background finalization can read canonical evidence and promote the session to `completed`.
**Demo:** After this: After this: The same objection-heavy proof chain finalizes `scoring -> completed`, and the accepted replay surface plus sibling highlights endpoint load same-session evidence instead of stopping at `[SESSION_NOT_COMPLETED]`.

## Tasks
- [x] **T01: Unlocked same-session replay/highlights after sales background finalization without changing the immediate `status="scoring"` end-session contract.** — 1. Add focused unit/integration/contract regressions that lock the two-stage sales status boundary and same-session replay/highlights unlock path.
2. Implement a narrow sales-only finalization seam in `ReportGenerationTrigger` that promotes `scoring -> completed` only when `SessionEvidenceService` can already read canonical evidence for that same session.
3. Re-run the accepted M003 backend chain and one localhost same-session learner-route proof: `/practice/{sessionId}` -> lifecycle end -> background finalization -> `/practice/{sessionId}/report` -> `/practice/{sessionId}/replay` plus sibling replay/highlights APIs.
4. Record the slice artifacts and evaluate whether M003 can now enter milestone validation.
  - Estimate: 1 turn
  - Files: backend/src/evaluation/services/report_generation_trigger.py, backend/tests/unit/test_report_generation_trigger.py, backend/tests/integration/test_session_lifecycle_api.py, backend/tests/integration/test_replay_api.py, backend/tests/contract/test_practice_evidence_contract.py, .gsd/milestones/M003/slices/S06/S06-SUMMARY.md, .gsd/milestones/M003/slices/S06/S06-UAT.md
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_report_generation_trigger.py tests/integration/test_session_lifecycle_api.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py -v && cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py && live localhost proof on /practice/{sessionId}, /practice/{sessionId}/report, /practice/{sessionId}/replay, plus GET /api/v1/practice/sessions/{id}/knowledge-check, /report, /api/v1/sessions/{id}/replay, /highlights
