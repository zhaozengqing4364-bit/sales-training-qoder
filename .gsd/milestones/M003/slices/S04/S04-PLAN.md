# S04: unsupported claim / weak evidence truth contract

**Goal:** Define and expose one canonical claim-truth contract across realtime diagnostics and completed-session read surfaces.
**Demo:** After this: The same session can show that a claim was unsupported, weakly supported, evidence-pending, or evidence-verified, and that truth line appears on realtime, report, and replay surfaces.

## Tasks
- [x] **T01: Added canonical sales claim-truth statuses to the evaluator and session-evidence projection without changing report/replay issue-goal keys.** — Define canonical truth flags for sales claims on the existing backend authority line: unsupported_claim, weak_evidence, evidence_pending, and evidence_verified. Add focused tests around evaluator/session-evidence semantics so the flags map cleanly onto current issue/goal families without renaming public report keys.
  - Estimate: 90m
  - Files: backend/src/common/effectiveness/evaluator.py, backend/src/common/conversation/session_evidence.py, backend/tests/unit/test_effectiveness_sales_report_alignment.py, backend/tests/unit/test_session_evidence_service.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py
- [x] **T02: Exposed claim-truth on StepFun score updates and knowledge-check diagnostics** — Wire the truth contract into the runtime and diagnostics path so objection handling can distinguish chain failure from weak or unsupported evidence. Reuse current kb-lock/runtime diagnostic helpers and StepFun handler surfaces rather than inventing another debug endpoint.
  - Estimate: 90m
  - Files: backend/src/common/knowledge/kb_lock_guard.py, backend/src/sales_bot/websocket/stepfun_realtime_handler.py, backend/src/common/conversation/runtime_diagnostics.py, backend/src/common/api/practice.py, backend/tests/unit/test_stepfun_realtime_handler.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py
- [x] **T03: Rendered canonical claim-truth states on learner report and replay surfaces.** — Render the truth states on the existing learner-facing read surfaces so users can tell whether a statement lacked evidence, had weak evidence, or was verified. Update current report/replay UI and focused tests without adding a separate knowledge-debug page.
  - Estimate: 75m
  - Files: web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.tsx, web/src/lib/session-evidence.ts, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
