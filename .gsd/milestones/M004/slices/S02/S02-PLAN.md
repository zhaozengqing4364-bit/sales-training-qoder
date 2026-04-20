# S02: report 直达 replay 关键片段

**Goal:** Wire the current report page directly to replay anchors so `main_issue`, `next_goal`, and key evidence can jump to the right turn or marker instead of forcing manual search.
**Demo:** After this: On the current report page, the learner can open the replay at the relevant turn/marker for the surfaced issue or goal.

## Tasks
- [x] **T01: Added stable replay anchors to replay issue/goal conclusions with degraded fallback coverage.** — Add stable replay anchor support on the current backend authority line so report items can target a real turn or marker. Reuse replay/timeline data rather than creating a separate deep-link resolver. Lock the anchor contract with focused backend tests.
  - Estimate: 75m
  - Files: backend/src/common/conversation/replay.py, backend/src/common/conversation/api.py, backend/tests/unit/test_replay_service.py, backend/tests/integration/test_replay_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py
- [x] **T02: Added replay deep-link CTAs to the report page for issue, goal, and highlight evidence.** — Update the current report page so `main_issue`, `next_goal`, and key learning evidence can deep-link into replay using the stable anchors. Reuse the existing report CTA area and current replay route rather than adding a separate learning workflow page.
  - Estimate: 90m
  - Files: web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/lib/api/client.ts, web/src/lib/api/types.ts, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
- [x] **T03: Replay now honors report deep links, auto-focuses the requested turn, and keeps degraded anchor fallback visible.** — Make the current replay page honor deep-link anchors and keep fallback behavior clear when the target highlight/marker does not exist. Stay on the existing replay page and lock the behavior with focused frontend tests.
  - Estimate: 60m
  - Files: web/src/app/(user)/practice/[sessionId]/replay/page.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
