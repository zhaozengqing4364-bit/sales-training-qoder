# S03: 主问题驱动的再练入口

**Goal:** Turn `main_issue` and `next_goal` into a concrete re-practice launch on the existing create-session surfaces, with carry-forward focus visible to the learner.
**Demo:** From the current report or replay page, the learner can start a new practice session targeted at the previous issue family and see that focus carried into the new session.

## Must-Haves

- From the current report or replay page, a learner can launch a new practice session targeted at the prior issue family, and the new session visibly carries that focus on the existing practice entry chain.

## Proof Level

- This slice proves: integration

## Integration Closure

Reuse current practice creation and learner entrypoints only: `backend/src/common/api/practice.py`, `backend/src/common/api/training.py` if needed, `training_runtime/service.py`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, and the existing practice page/runtime descriptor. No new retry product surface.

## Verification

- Practice create-session contract tests, report/replay CTA tests, and practice-page focused tests become the drift detectors for retry intent and carry-forward focus.

## Tasks

- [x] **T01: Extend the current retry-entry contract with a structured focus intent** `est:90m`
  Extend the current retry-entry contract so it can carry a structured focus intent derived from `main_issue` / `next_goal` without inventing a second launch system. Keep the source of truth on current report/practice APIs and lock it with focused contract tests.
  - Files: `backend/src/common/api/practice.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_practice_evidence_flow.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py

- [x] **T02: Launch focused retries from the current report and replay pages** `est:75m`
  Update the current report and replay CTAs so they can launch a focused retry using the new retry-entry intent. Reuse existing buttons/routes and keep scenario-specific behavior on the same entrypoints instead of adding a new retry flow.
  - Files: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'

- [ ] **T03: Show the carry-forward focus on the current practice page** `est:60m`
  Make the existing practice entry chain display the carry-forward focus so the learner knows this is a targeted retry and not a generic new session. Reuse current runtime descriptor/practice page state; do not build a separate onboarding step.
  - Files: `backend/src/training_runtime/service.py`, `web/src/app/(user)/practice/[sessionId]/page.tsx`, `web/src/hooks/use-practice-websocket.test.ts`
  - Verify: cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'

## Files Likely Touched

- backend/src/common/api/practice.py
- backend/tests/contract/test_practice_evidence_contract.py
- backend/tests/integration/test_practice_evidence_flow.py
- web/src/app/(user)/practice/[sessionId]/report/page.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.tsx
- web/src/lib/api/client.ts
- web/src/lib/api/types.ts
- web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
- backend/src/training_runtime/service.py
- web/src/app/(user)/practice/[sessionId]/page.tsx
- web/src/hooks/use-practice-websocket.test.ts
