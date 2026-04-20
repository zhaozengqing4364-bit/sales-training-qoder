# S03: 主问题驱动的再练入口

**Goal:** Turn `main_issue` and `next_goal` into a concrete re-practice launch on the existing create-session surfaces, with carry-forward focus visible to the learner.
**Demo:** After this: From the current report or replay page, the learner can start a new practice session targeted at the previous issue family and see that focus carried into the new session.

## Tasks
- [x] **T01: Added structured sales retry focus intent to the report/create-session contract and persisted it on new session snapshots** — Extend the current retry-entry contract so it can carry a structured focus intent derived from `main_issue` / `next_goal` without inventing a second launch system. Keep the source of truth on current report/practice APIs and lock it with focused contract tests.
  - Estimate: 90m
  - Files: backend/src/common/api/practice.py, backend/tests/contract/test_practice_evidence_contract.py, backend/tests/integration/test_practice_evidence_flow.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
- [x] **T02: Connected report and replay retry CTAs to focused create-session launches** — Update the current report and replay CTAs so they can launch a focused retry using the new retry-entry intent. Reuse existing buttons/routes and keep scenario-specific behavior on the same entrypoints instead of adding a new retry flow.
  - Estimate: 75m
  - Files: web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.tsx, web/src/lib/api/client.ts, web/src/lib/api/types.ts, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
- [x] **T03: Surfaced carry-forward retry focus on the learner practice page via the runtime descriptor** — Make the existing practice entry chain display the carry-forward focus so the learner knows this is a targeted retry and not a generic new session. Reuse current runtime descriptor/practice page state; do not build a separate onboarding step.
  - Estimate: 60m
  - Files: backend/src/training_runtime/service.py, web/src/app/(user)/practice/[sessionId]/page.tsx, web/src/hooks/use-practice-websocket.test.ts
  - Verify: cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'
