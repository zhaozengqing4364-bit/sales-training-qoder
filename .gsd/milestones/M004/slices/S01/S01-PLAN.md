# S01: 当前 report/replay/highlight 入口的学习证据 contract

**Goal:** Upgrade the existing replay/highlight authority line so a completed session can expose explanation-rich evidence tied to the real turn, stage, issue family, context, and suggested better response.
**Demo:** After this: On the existing replay and highlight surfaces, a learner can see which turn mattered, why it mattered, which stage it belongs to, and what a better response looks like — without adding a new learning page.

## Tasks
- [x] **T01: Lock replay/highlight learning evidence to the shared session projection with a stable nested contract** — Write focused failing tests around `backend/src/common/conversation/replay.py` and the replay API, then extend the current replay/highlight payload so it can carry stable learning fields already implied by the product: reason, stage, nearby context, suggested better response, and issue-family linkage. Keep the current replay route and session evidence line authoritative; do not add a second scorer or freeform learning generator.
  - Estimate: 90m
  - Files: backend/src/common/conversation/replay.py, backend/src/common/conversation/session_evidence.py, backend/src/common/conversation/api.py, backend/tests/unit/test_replay_service.py, backend/tests/integration/test_replay_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py
- [x] **T02: Rendered shared learning evidence on the replay and highlight surfaces with focused UI tests.** — Update the current replay and highlight UI components to render the richer explanation contract directly from API data. Use the existing surfaces only: `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/components/highlights/HighlightList.tsx`, `HighlightCard`, and `HighlightDetailModal`. Make the UI explain why a turn matters and how to improve it, while keeping null/no-highlight states clean.
  - Estimate: 90m
  - Files: web/src/app/(user)/practice/[sessionId]/replay/page.tsx, web/src/components/highlights/HighlightList.tsx, web/src/components/highlights/HighlightCard.tsx, web/src/components/highlights/HighlightDetailModal.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'
- [x] **T03: Aligned report and history learning cues with replay evidence and degraded-state behavior.** — Make sure the report page and history page continue to speak the same learning vocabulary and stay usable when highlights are absent or enhanced data degrades. Add the minimum read-side carry-forward needed on the current user entrypoints; do not invent new routes. Lock the behavior with focused tests so future work cannot quietly revert to generic or conflicting evidence language.
  - Estimate: 75m
  - Files: web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/app/(dashboard)/history/page.tsx, web/src/lib/session-evidence.ts, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx, web/src/app/(dashboard)/history/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
