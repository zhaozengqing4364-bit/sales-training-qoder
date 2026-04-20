---
estimated_steps: 4
estimated_files: 4
skills_used:
  - test-driven-development
  - react-best-practices
  - verification-before-completion
---

# T02: 把 coach-health 状态抬到 learner page shell

**Slice:** S01 — 教练健康状态真相收口
**Milestone:** M007

## Description

Make degraded/resumed explicitly visible on the learner route itself, especially on mobile where the current signal is hidden until the bottom sheet is opened. Reuse the same `coachHealth` object already flowing through the practice page; this task is about surfacing existing truth, not inventing a second derivation or replacing the richer right-panel guidance.

## Negative Tests

- **Malformed inputs**: `coachHealth` objects with missing reason/message fields should still render safely or stay quiet in the healthy case
- **Error paths**: degraded/resumed status must remain visible even when `RightPanelContent` is mocked in the page test
- **Boundary conditions**: mobile and desktop both expose the learner-visible status, healthy state stays quiet, and degraded/resumed copy coexists with stage and score guidance

## Steps

1. Add a compact, non-blocking page-shell strip or chip near the primary practice controls that mirrors the existing `coachHealth` object.
2. Keep `RightPanelContent` as the richer explanation surface, extracting a tiny shared presentational helper only if duplication would otherwise drift.
3. Extend `page.test.tsx` so the page-shell status is asserted even with `RightPanelContent` mocked, and keep the panel tests proving the guidance surfaces stay visible.
4. Re-run the focused learner-page and panel tests from repo root.

## Must-Haves

- [ ] degraded/resumed is visible on `/practice/{sessionId}` without opening the analysis panel
- [ ] healthy state stays quiet and non-distracting
- [ ] page-shell status uses the existing `coachHealth` object instead of a second client-side authority
- [ ] right-panel stage, score, action-card, and fuzzy-detection guidance remain intact

## Verification

- `npm test -- --run 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'`

## Observability Impact

- Signals added/changed: learner page shell becomes an immediate visual inspection surface for live coach health
- How a future agent inspects this: compare `/practice/{sessionId}` page-shell rendering with `RightPanelContent` rendering and the focused page/panel tests
- Failure state exposed: mobile-hidden degraded/resumed regressions become visible as page-level UI failures instead of only panel-level misses

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx` — learner page shell and control area
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx` — page-level assertions with `RightPanelContent` mocked
- `web/src/components/practice/RightPanelContent.tsx` — existing richer coach-health explanation surface
- `web/src/components/practice/RightPanelContent.test.tsx` — panel-level degraded/resumed non-blocking assertions
- `web/src/hooks/use-practice-websocket.ts` — current source of the `coachHealth` object flowing into the page
- `web/src/hooks/websocket/types.ts` — `CoachHealth` type used by page and panel props

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.tsx` — learner page shell shows compact degraded/resumed status
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx` — page-level visibility is asserted independently of the right panel
- `web/src/components/practice/RightPanelContent.tsx` — richer panel status remains aligned with the shared coach-health copy
- `web/src/components/practice/RightPanelContent.test.tsx` — panel-level non-blocking guidance assertions still pass alongside the new page-shell surface
