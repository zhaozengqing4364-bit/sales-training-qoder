# S03: 多轮异议 ledger 与持续施压

**Goal:** Persist unresolved objections, promised proof, and next proof request as cross-turn runtime/read-side facts so the AI customer can continue pressuring the same business gap instead of forgetting it.
**Demo:** An unresolved objection survives topic drift and reconnect, and the AI customer keeps returning to it until evidence is provided or the gap is acknowledged.

## Must-Haves

- A high-value objection survives topic drift and reconnect, the runtime keeps returning to it until proof is supplied or the gap is explicitly closed, and completed-session evidence can still explain that unresolved objection family afterward.

## Proof Level

- This slice proves: integration

## Integration Closure

Reuse the current sales runtime and evidence chain only: `backend/src/sales_bot/services/context_manager.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/src/common/conversation/storage.py`, `backend/src/common/conversation/session_evidence.py`, `web/src/hooks/use-practice-websocket.ts`, and `web/src/components/practice/RightPanelContent.tsx`. No parallel memory system.

## Verification

- Handler persistence/restore tests, replay/report evidence checks, and practice-page reducer tests become the main drift detectors for cross-turn objection state. Reconnect must not replay stale pressure state.

## Tasks

- [ ] **T01: Define and persist the unresolved-objection ledger on current runtime state** `est:90m`
  Define the minimum unresolved-objection ledger on the current runtime chain: unresolved objection family, promised proof, next expected evidence, and closure state. Add focused tests around the existing runtime/context components so this ledger can be persisted without inventing a second store.
  - Files: `backend/src/sales_bot/services/context_manager.py`, `backend/src/common/conversation/storage.py`, `backend/tests/unit/test_context_manager.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py

- [ ] **T02: Carry unresolved objections across turns and reconnect on both runtime paths** `est:2h`
  Wire the ledger through classic and StepFun runtime paths and make reconnect restore safe. Reuse current handlers and capability composition so objection state influences follow-up pressure without replaying stale prompts after reconnect.
  - Files: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`, `backend/tests/unit/test_stepfun_realtime_persistence.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py

- [ ] **T03: Carry unresolved objection evidence onto current learner and read-side surfaces** `est:75m`
  Expose the unresolved objection family on the existing learner/read-side surfaces so the user can still see what kept blocking the conversation. Reuse the current practice reducer/right panel and session-evidence/report paths; do not add a separate objection UI.
  - Files: `backend/src/common/conversation/session_evidence.py`, `web/src/hooks/use-practice-websocket.ts`, `web/src/components/practice/RightPanelContent.tsx`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/components/practice/RightPanelContent.test.tsx`
  - Verify: cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'

## Files Likely Touched

- backend/src/sales_bot/services/context_manager.py
- backend/src/common/conversation/storage.py
- backend/tests/unit/test_context_manager.py
- backend/tests/unit/test_stepfun_realtime_handler.py
- backend/src/sales_bot/websocket/stepfun_realtime_handler.py
- backend/src/sales_bot/websocket/components/capability_processor.py
- backend/tests/unit/test_stepfun_realtime_persistence.py
- backend/src/common/conversation/session_evidence.py
- web/src/hooks/use-practice-websocket.ts
- web/src/components/practice/RightPanelContent.tsx
- web/src/hooks/use-practice-websocket.test.ts
- web/src/components/practice/RightPanelContent.test.tsx
