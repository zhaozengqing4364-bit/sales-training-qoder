# S04: PPT 页级学习证据

**Goal:** Extend the existing presentation report/replay authority line so page-level and point-level evidence can explain where the learner spoke off-page, omitted required points, over-expanded, or triggered forbidden wording.
**Demo:** After this: On the current PPT report/replay routes, a learner can see which page has which issue cluster and why it should be reworked.

## Tasks
- [ ] **T01: Group PPT learning issues at page and point level on the current report line** — Extend the current presentation report builder so it can group issues at page/point level on the existing authority line: off-page, missing point, overlong explanation, forbidden wording, and weak Q&A handling. Lock the contract with focused backend tests rather than freeform UI expectations.
  - Estimate: 90m
  - Files: backend/src/presentation_coach/services/presentation_report_service.py, backend/src/common/conversation/session_evidence.py, backend/tests/unit/test_presentation_report_service.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_presentation_report_service.py
- [ ] **T02: Show page-level learning evidence on the current PPT report route** — Render the richer page-level evidence on the current shared PPT report page so the learner can see which page has which issue cluster and why. Reuse the current presentation branch of `report/page.tsx`; do not create a separate PPT learning page.
  - Estimate: 75m
  - Files: web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/lib/session-evidence.ts, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
- [ ] **T03: Carry page-level evidence onto the current PPT replay/viewing path** — Carry the page-level evidence into the current replay/PPT viewing experience so users can navigate from report conclusions to the relevant page context. Reuse current replay service and PPT UI components; keep degraded states explicit when page anchors are missing.
  - Estimate: 75m
  - Files: backend/src/common/conversation/replay.py, web/src/components/practice/presentation/SlideViewer.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
