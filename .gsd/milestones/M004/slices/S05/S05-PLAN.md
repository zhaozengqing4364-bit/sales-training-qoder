# S05: sales + PPT 学习闭环终验

**Goal:** Prove that the current user-facing learning chain actually works end-to-end for both sales and presentation: report → replay → evidence review → retry.
**Demo:** After this: At least one sales and one PPT route complete a live learning loop on the current entrypoints, and degraded states remain understandable.

## Tasks
- [x] **T01: Repaired the shared replay contract and extended the learning-loop regression net for sales + PPT routes.** — Build the regression net for the current learning chain so report, replay, history, highlights, and retry remain on one vocabulary and one route family. Reuse focused backend/web suites instead of adding a new acceptance framework.
  - Estimate: 75m
  - Files: backend/tests/unit/test_replay_service.py, backend/tests/integration/test_practice_evidence_flow.py, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx, web/src/app/(dashboard)/history/page.test.tsx
  - Verify (backend): cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py
  - Verify (web): npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'
- [x] **T02: Captured the live sales review loop on current user routes and repaired the stale verifier gate.** — Run one real sales learning path on the current user entrypoints and capture the evidence pack: report conclusion, replay anchor, highlight explanation, and focused retry launch. Keep the proof on the same routes users already use.
  - Estimate: 90m
  - Files: .gsd/milestones/M004/slices/S05/S05-UAT.md
  - Verify: Manual review — file exists and is non-empty
- [ ] **T03: Capture one live PPT learning-loop proof on current shared routes** — Run one real PPT learning path on the current shared report/replay routes and capture the page-level evidence and degraded-proof behavior when relevant. Use the same acceptance artifact family as the sales path.
  - Estimate: 90m
  - Files: .gsd/milestones/M004/slices/S05/S05-UAT.md
  - Verify: Manual review — file exists and is non-empty
