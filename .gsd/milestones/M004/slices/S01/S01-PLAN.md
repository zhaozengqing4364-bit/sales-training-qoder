# S01: 当前 report/replay/highlight 入口的学习证据 contract

**Goal:** Upgrade the existing replay/highlight authority line so a completed session can expose explanation-rich evidence tied to the real turn, stage, issue family, context, and suggested better response.
**Demo:** On the existing replay and highlight surfaces, a learner can see which turn mattered, why it mattered, which stage it belongs to, and what a better response looks like — without adding a new learning page.

## Must-Haves

- On the current replay/highlight routes, a completed session can expose explanation-rich evidence tied to the real turn, stage, issue family, context, and suggested better response; the replay page renders that evidence without a second truth line; report/history remain readable when no highlights or degraded evidence are present.

## Proof Level

- This slice proves: integration

## Integration Closure

Keep `backend/src/common/conversation/replay.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/conversation/api.py`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, and `web/src/components/highlights/*` on one learning-evidence contract. No new learning center, no second evaluator, no tooling-only scope.

## Verification

- Replay service tests, replay API tests, replay page tests, and highlight component tests become the primary drift detectors; degraded states such as no highlights or missing enhanced data stay visible on the current entrypoints.

## Tasks

- [ ] **T01: Lock the replay/highlight learning-evidence contract on the existing backend authority line** `est:90m`
  Write focused failing tests around `backend/src/common/conversation/replay.py` and the replay API, then extend the current replay/highlight payload so it can carry stable learning fields already implied by the product: reason, stage, nearby context, suggested better response, and issue-family linkage. Keep the current replay route and session evidence line authoritative; do not add a second scorer or freeform learning generator.
  - Files: `backend/src/common/conversation/replay.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/conversation/api.py`, `backend/tests/unit/test_replay_service.py`, `backend/tests/integration/test_replay_api.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py

- [ ] **T02: Render the richer learning evidence on the existing replay/highlight surfaces** `est:90m`
  Update the current replay and highlight UI components to render the richer explanation contract directly from API data. Use the existing surfaces only: `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/components/highlights/HighlightList.tsx`, `HighlightCard`, and `HighlightDetailModal`. Make the UI explain why a turn matters and how to improve it, while keeping null/no-highlight states clean.
  - Files: `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/components/highlights/HighlightList.tsx`, `web/src/components/highlights/HighlightCard.tsx`, `web/src/components/highlights/HighlightDetailModal.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'

- [ ] **T03: Carry the learning-evidence vocabulary through report/history and lock degraded-state behavior** `est:75m`
  Make sure the report page and history page continue to speak the same learning vocabulary and stay usable when highlights are absent or enhanced data degrades. Add the minimum read-side carry-forward needed on the current user entrypoints; do not invent new routes. Lock the behavior with focused tests so future work cannot quietly revert to generic or conflicting evidence language.
  - Files: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(dashboard)/history/page.tsx`, `web/src/lib/session-evidence.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/(dashboard)/history/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'

## Files Likely Touched

- backend/src/common/conversation/replay.py
- backend/src/common/conversation/session_evidence.py
- backend/src/common/conversation/api.py
- backend/tests/unit/test_replay_service.py
- backend/tests/integration/test_replay_api.py
- web/src/app/(user)/practice/[sessionId]/replay/page.tsx
- web/src/components/highlights/HighlightList.tsx
- web/src/components/highlights/HighlightCard.tsx
- web/src/components/highlights/HighlightDetailModal.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
- web/src/app/(user)/practice/[sessionId]/report/page.tsx
- web/src/app/(dashboard)/history/page.tsx
- web/src/lib/session-evidence.ts
- web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
- web/src/app/(dashboard)/history/page.test.tsx
