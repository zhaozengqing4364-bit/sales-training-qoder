# S03: 多轮异议 ledger 与持续施压

**Goal:** Persist unresolved objection ledger facts across turns/reconnect on the existing realtime and evidence chain.
**Demo:** After this: An unresolved objection survives topic drift and reconnect, and the AI customer keeps returning to it until evidence is provided or the gap is acknowledged.

## Tasks
- [x] **T01: Added a normalized unresolved-objection ledger seam to context, message persistence, and StepFun reconnect state.** — Define the minimum unresolved-objection ledger on the current runtime chain: unresolved objection family, promised proof, next expected evidence, and closure state. Add focused tests around the existing runtime/context components so this ledger can be persisted without inventing a second store.
  - Estimate: 90m
  - Files: backend/src/sales_bot/services/context_manager.py, backend/src/common/conversation/storage.py, backend/tests/unit/test_context_manager.py, backend/tests/unit/test_stepfun_realtime_handler.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py
- [x] **T02: Carried unresolved objection pressure through classic and StepFun runtime turns with reconnect-safe snapshot recovery.** — Wire the ledger through classic and StepFun runtime paths and make reconnect restore safe. Reuse current handlers and capability composition so objection state influences follow-up pressure without replaying stale prompts after reconnect.
  - Estimate: 2h
  - Files: backend/src/sales_bot/websocket/stepfun_realtime_handler.py, backend/src/sales_bot/websocket/components/capability_processor.py, backend/tests/unit/test_stepfun_realtime_handler.py, backend/tests/unit/test_stepfun_realtime_persistence.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
- [x] **T03: Surfaced unresolved objection proof gaps in report projection and the practice panel without replaying stale reconnect hints.** — Expose the unresolved objection family on the existing learner/read-side surfaces so the user can still see what kept blocking the conversation. Reuse the current practice reducer/right panel and session-evidence/report paths; do not add a separate objection UI.
  - Estimate: 75m
  - Files: backend/src/common/conversation/session_evidence.py, web/src/hooks/use-practice-websocket.ts, web/src/components/practice/RightPanelContent.tsx, web/src/hooks/use-practice-websocket.test.ts, web/src/components/practice/RightPanelContent.test.tsx
  - Verify: cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'
