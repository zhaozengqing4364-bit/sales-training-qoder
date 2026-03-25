# S04: unsupported claim / weak evidence truth contract

**Goal:** Define an explicit evidence-backed truth contract for sales claims and reuse it across realtime coaching and completed-session read surfaces.
**Demo:** The same session can show that a claim was unsupported, weakly supported, evidence-pending, or evidence-verified, and that truth line appears on realtime, report, and replay surfaces.

## Must-Haves

- The same session can show whether a claim was unsupported, weakly supported, evidence-pending, or evidence-verified, and that truth line appears on current realtime, report, and replay surfaces using one vocabulary.

## Proof Level

- This slice proves: integration

## Integration Closure

Reuse the current kb-lock/runtime diagnostics plus evaluator/session-evidence/report/replay lines: `backend/src/common/knowledge/kb_lock_guard.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/api/practice.py`, `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/common/effectiveness/evaluator.py`, `backend/src/common/conversation/session_evidence.py`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, and `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`. No public-contract explosion.

## Verification

- Truth-contract regressions become visible in realtime/report/replay tests, runtime diagnostics, and same-session comparison surfaces. Weak-evidence and unsupported-claim states must stay distinct from chain failures.

## Tasks

- [x] **T01: Define the claim-truth flags on the current evaluator/session-evidence line** `est:90m`
  Define canonical truth flags for sales claims on the existing backend authority line: unsupported_claim, weak_evidence, evidence_pending, and evidence_verified. Add focused tests around evaluator/session-evidence semantics so the flags map cleanly onto current issue/goal families without renaming public report keys.
  - Files: `backend/src/common/effectiveness/evaluator.py`, `backend/src/common/conversation/session_evidence.py`, `backend/tests/unit/test_effectiveness_sales_report_alignment.py`, `backend/tests/unit/test_session_evidence_service.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py

- [ ] **T02: Expose the claim-truth contract on the current runtime diagnostics path** `est:90m`
  Wire the truth contract into the runtime and diagnostics path so objection handling can distinguish chain failure from weak or unsupported evidence. Reuse current kb-lock/runtime diagnostic helpers and StepFun handler surfaces rather than inventing another debug endpoint.
  - Files: `backend/src/common/knowledge/kb_lock_guard.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/common/api/practice.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py

- [ ] **T03: Show claim-truth states on current report and replay routes** `est:75m`
  Render the truth states on the existing learner-facing read surfaces so users can tell whether a statement lacked evidence, had weak evidence, or was verified. Update current report/replay UI and focused tests without adding a separate knowledge-debug page.
  - Files: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/lib/session-evidence.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'

## Files Likely Touched

- backend/src/common/effectiveness/evaluator.py
- backend/src/common/conversation/session_evidence.py
- backend/tests/unit/test_effectiveness_sales_report_alignment.py
- backend/tests/unit/test_session_evidence_service.py
- backend/src/common/knowledge/kb_lock_guard.py
- backend/src/sales_bot/websocket/stepfun_realtime_handler.py
- backend/src/common/conversation/runtime_diagnostics.py
- backend/src/common/api/practice.py
- backend/tests/unit/test_stepfun_realtime_handler.py
- web/src/app/(user)/practice/[sessionId]/report/page.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.tsx
- web/src/lib/session-evidence.ts
- web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
