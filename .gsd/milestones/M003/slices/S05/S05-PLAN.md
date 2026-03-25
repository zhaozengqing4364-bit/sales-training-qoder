# S05: objection-heavy live proof 与稳定性护栏

**Goal:** Run a real objection-heavy live proof that validates M003 against the current user entry chain and runtime constraints.
**Demo:** At least one real objection-heavy script proves that the system feels like a real customer, leaves inspectable evidence, and still respects current runtime stability/degraded guarantees.

## Must-Haves

- At least one objection-heavy script proves material-driven, Persona-driven objection handling on the current product chain, leaves inspectable same-session evidence, and stays within the current runtime stability/degraded guarantees.

## Proof Level

- This slice proves: final-assembly

## Integration Closure

Exercise the real admin config → practice → report/replay path, not helpers alone: existing admin Persona/knowledge pages, `/practice/[sessionId]`, `/practice/[sessionId]/report`, and replay/highlight surfaces. No sidecar debug app.

## Verification

- Live UAT artifacts, objection-heavy regression suites, and same-session screenshots/logs become the release proof for M003. Latency, degraded states, and evidence verdicts must be captured on the same path.

## Tasks

- [x] **T01: Build the objection-heavy regression net on current runtime routes** `est:90m`
  Build the focused regression net for objection-heavy realism on the current code paths: at least ROI, price, competitor, implementation risk, and evidence-proof cases. Reuse the current StepFun/runtime/unit/integration suites and add explicit assertions for weak-evidence / verified-evidence / search-failed paths.
  - Files: `backend/tests/unit/test_stepfun_realtime_handler.py`, `backend/tests/unit/test_stepfun_knowledge_helpers.py`, `backend/tests/integration/test_knowledge_flow.py`, `backend/tests/contract/test_practice_evidence_contract.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py

- [ ] **T02: Capture one live objection-heavy same-session evidence pack on current product surfaces** `est:2h`
  Run one real admin-configured Persona/knowledge path through the current practice page and capture the same-session evidence pack: runtime behavior, knowledge-check state, report/replay review, and any degraded or fallback signals. Keep host/runtime setup aligned with current local proof rules.
  - Files: `.gsd/milestones/M003/slices/S05/S05-UAT.md`
  - Verify: Manual review — file exists and is non-empty

- [ ] **T03: Write the final stability and acceptance guardrails for M003** `est:45m`
  Document the stability and acceptance guardrails for M003 on the same business chain: what counts as acceptable latency, which degraded states are still shippable, and which failures block release. Reuse current support/report/runtime evidence, not a separate checklist tool.
  - Files: `.gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md`
  - Verify: rg -n "latency|degraded|fallback|block" .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md

## Files Likely Touched

- backend/tests/unit/test_stepfun_realtime_handler.py
- backend/tests/unit/test_stepfun_knowledge_helpers.py
- backend/tests/integration/test_knowledge_flow.py
- backend/tests/contract/test_practice_evidence_contract.py
- .gsd/milestones/M003/slices/S05/S05-UAT.md
- .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
