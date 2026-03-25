# S05: sales + PPT 学习闭环终验

**Goal:** Prove that the current user-facing learning chain actually works end-to-end for both sales and presentation: report → replay → evidence review → retry.
**Demo:** At least one sales and one PPT route complete a live learning loop on the current entrypoints, and degraded states remain understandable.

## Must-Haves

- At least one sales and one PPT route complete a live learning loop on the current entrypoints, and degraded states remain understandable while the user can still inspect evidence and start the next practice.

## Proof Level

- This slice proves: final-assembly

## Integration Closure

Exercise the real report/replay/history/practice routes, not isolated helpers: current user report pages, replay pages, history page, and retry/practice create flow. No parallel acceptance app.

## Verification

- Live UAT artifacts plus focused report/replay/history/retry regressions become the release proof for M004. Degraded states must remain understandable on the same routes.

## Tasks

- [ ] **T01: Build the regression net for the current learning-loop routes** `est:75m`
  Build the regression net for the current learning chain so report, replay, history, highlights, and retry remain on one vocabulary and one route family. Reuse focused backend/web suites instead of adding a new acceptance framework.
  - Files: `backend/tests/unit/test_replay_service.py`, `backend/tests/integration/test_practice_evidence_flow.py`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`, `web/src/app/(dashboard)/history/page.test.tsx`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py && cd ../web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'

- [ ] **T02: Capture one live sales learning-loop proof on current user routes** `est:90m`
  Run one real sales learning path on the current user entrypoints and capture the evidence pack: report conclusion, replay anchor, highlight explanation, and focused retry launch. Keep the proof on the same routes users already use.
  - Files: `.gsd/milestones/M004/slices/S05/S05-UAT.md`
  - Verify: Manual review — file exists and is non-empty

- [ ] **T03: Capture one live PPT learning-loop proof on current shared routes** `est:90m`
  Run one real PPT learning path on the current shared report/replay routes and capture the page-level evidence and degraded-proof behavior when relevant. Use the same acceptance artifact family as the sales path.
  - Files: `.gsd/milestones/M004/slices/S05/S05-UAT.md`
  - Verify: Manual review — file exists and is non-empty

## Files Likely Touched

- backend/tests/unit/test_replay_service.py
- backend/tests/integration/test_practice_evidence_flow.py
- web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
- web/src/app/(dashboard)/history/page.test.tsx
- .gsd/milestones/M004/slices/S05/S05-UAT.md
