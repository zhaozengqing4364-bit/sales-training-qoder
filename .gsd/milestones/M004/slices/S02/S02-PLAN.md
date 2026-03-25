# S02: report 直达 replay 关键片段

**Goal:** Wire the current report page directly to replay anchors so `main_issue`, `next_goal`, and key evidence can jump to the right turn or marker instead of forcing manual search.
**Demo:** On the current report page, the learner can open the replay at the relevant turn/marker for the surfaced issue or goal.

## Must-Haves

- On the current report page, the learner can jump to replay anchors for the surfaced issue/goal/evidence chain, and the replay page can land on a stable turn or marker without introducing a second evidence model.

## Proof Level

- This slice proves: integration

## Integration Closure

Reuse the existing report/replay routes and supporting authority modules only: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `backend/src/common/conversation/replay.py`, `backend/src/common/conversation/api.py`, `backend/src/common/api/practice.py`, and `web/src/lib/session-evidence.ts`. No new page family.

## Verification

- Focused report/replay tests and replay API assertions become the drift detectors for anchor stability; degraded states such as no matching highlight or missing marker must stay visible rather than silently failing.

## Tasks

- [x] **T01: Add stable replay anchors on the existing replay/timeline contract** `est:75m`
  Add stable replay anchor support on the current backend authority line so report items can target a real turn or marker. Reuse replay/timeline data rather than creating a separate deep-link resolver. Lock the anchor contract with focused backend tests.
  - Files: `backend/src/common/conversation/replay.py`, `backend/src/common/conversation/api.py`, `backend/tests/unit/test_replay_service.py`, `backend/tests/integration/test_replay_api.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py

- [x] **T02: Deep-link report conclusions into the current replay route** `est:90m`
  Update the current report page so `main_issue`, `next_goal`, and key learning evidence can deep-link into replay using the stable anchors. Reuse the existing report CTA area and current replay route rather than adding a separate learning workflow page.
  - Files: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'

- [x] **T03: Land replay on the requested anchor and keep degraded fallback visible** `est:60m`
  Make the current replay page honor deep-link anchors and keep fallback behavior clear when the target highlight/marker does not exist. Stay on the existing replay page and lock the behavior with focused frontend tests.
  - Files: `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'

## Files Likely Touched

- backend/src/common/conversation/replay.py
- backend/src/common/conversation/api.py
- backend/tests/unit/test_replay_service.py
- backend/tests/integration/test_replay_api.py
- web/src/app/(user)/practice/[sessionId]/report/page.tsx
- web/src/lib/api/client.ts
- web/src/lib/api/types.ts
- web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
