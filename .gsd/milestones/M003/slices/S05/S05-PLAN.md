# S05: objection-heavy live proof 与稳定性护栏

**Goal:** Run one honest objection-heavy live proof on the accepted current routes and document the release boundary for M003.
**Demo:** After this: At least one real objection-heavy script proves that the system feels like a real customer, leaves inspectable evidence, and still respects current runtime stability/degraded guarantees.

## Tasks
- [x] **T01: Expanded objection-heavy runtime regressions across competitor, implementation-risk, and claim-truth evidence paths** — Build the focused regression net for objection-heavy realism on the current code paths: at least ROI, price, competitor, implementation risk, and evidence-proof cases. Reuse the current StepFun/runtime/unit/integration suites and add explicit assertions for weak-evidence / verified-evidence / search-failed paths.
  - Estimate: 90m
  - Files: backend/tests/unit/test_stepfun_realtime_handler.py, backend/tests/unit/test_stepfun_knowledge_helpers.py, backend/tests/integration/test_knowledge_flow.py, backend/tests/contract/test_practice_evidence_contract.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py
- [x] **T02: Captured a live objection-heavy S05 evidence pack with canonical report proof and replay degradation evidence.** — Run one real admin-configured Persona/knowledge path through the current practice page and capture the same-session evidence pack: runtime behavior, knowledge-check state, report/replay review, and any degraded or fallback signals. Keep host/runtime setup aligned with current local proof rules.
  - Estimate: 2h
  - Files: .gsd/milestones/M003/slices/S05/S05-UAT.md
  - Verify: Manual review — file exists and is non-empty
- [x] **T03: Documented M003 release guardrails and marked replay-blocked scoring sessions as the remaining acceptance blocker.** — Document the stability and acceptance guardrails for M003 on the same business chain: what counts as acceptable latency, which degraded states are still shippable, and which failures block release. Reuse current support/report/runtime evidence, not a separate checklist tool.
  - Estimate: 45m
  - Files: .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
  - Verify: rg -n "latency|degraded|fallback|block" .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
