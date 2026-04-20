---
id: S05
parent: M004
milestone: M004
provides:
  - A closed-route proof that the existing learner report/replay/history entrypoints can carry both sales and PPT post-session learning loops without a new learning page.
  - A stable scenario-aware replay contract that stays aligned with the shared report route for presentation sessions.
  - A concrete UAT/evidence pack future slices can reuse when checking whether report/replay/retry still form one learner route family.
requires:
  - slice: S03
    provides: sales report/replay retry focus intent, deep-link anchors, and the current learner route family
  - slice: S04
    provides: PPT page-level evidence contract and missing-page-metadata degraded copy on the shared report/replay routes
affects:
  - M004 roadmap reassessment
  - M005 planning
key_files:
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/app/(dashboard)/history/page.test.tsx
  - .gsd/milestones/M004/slices/S05/S05-SUMMARY.md
  - .gsd/milestones/M004/slices/S05/S05-UAT.md
  - .artifacts/m004-s05-t02/summary.json
  - .artifacts/m004-s05-t03/summary.json
key_decisions:
  - D073: make `/api/v1/sessions/{id}/replay` mirror the shared report route for presentation sessions by carrying `scenario_type`/`presentation_id`/`presentation_review` and clearing sales-only conclusion fields.
patterns_established:
  - Keep report, replay, history, and retry on one scenario-aware route family instead of adding a second learning surface.
  - Treat PPT replay as the current sibling learner route from `/history` when report does not expose a replay CTA; do not reinterpret that shipped UI gap as a regression.
  - Preserve degraded learning states as explicit copy on the canonical route (`missing_page_metadata`, replay-anchor fallback) instead of silently dropping the learner into blank or sales-shaped UI.
observability_surfaces:
  - .artifacts/m004-s05-t02/summary.json
  - .artifacts/m004-s05-t03/summary.json
  - .artifacts/m004-s05-t03/degraded-report.png
  - .artifacts/m004-s05-t03/degraded-replay.png
  - backend/tests/integration/test_practice_evidence_flow.py
drill_down_paths:
  - .gsd/milestones/M004/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S05/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-26T05:19:44.208Z
blocker_discovered: false
---

# S05: sales + PPT 学习闭环终验

**The current learner route family now proves a usable post-session learning loop for both sales and PPT, with focused retry and explicit degraded states staying on the existing report/replay/history entrypoints.**

## What Happened

T01 repaired the remaining shared replay-contract drift by making `/api/v1/sessions/{id}/replay` scenario-aware for presentation sessions, carrying `scenario_type`/`presentation_id`/`presentation_review` and clearing sales-only conclusion fields. The focused backend and web regression net now covers replay service, practice evidence flow, report, replay, and history so both scenario types stay on one route vocabulary.

T02 then proved the live sales learner loop on the shipped routes. A completed sales row remained usable on `/history` even with newer non-completed rows above it; `/practice/{sessionId}/report` showed the canonical sales conclusion family and focus-intent retry; replay deep-linking stayed understandable via degraded anchor fallback when exact highlights were absent; and retry launched a new sales practice session on the same route family while preserving the source report focus intent.

T03 proved the PPT half of the same learner loop on the shared report/replay routes. `/practice/{sessionId}/report` rendered canonical PPT review data with page-level issue clusters, `/practice/{sessionId}/replay` let the learner inspect page evidence and jump to the linked turn, and retry relaunched a new presentation session with the same `presentation_id`. The degraded PPT case also stayed readable on both report and replay with explicit `missing_page_metadata` copy instead of blank state or sales fallback. The only accepted contract nuance is that PPT replay is currently reached from the sibling `/history` row rather than from a direct report CTA.

## Verification

Fresh closer verification reran the exact backend plan command `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py` (34 passed), reran the focused web suite `pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'` (23 tests across 3 files passed), and confirmed the saved sales/PPT browser proof pack plus rewritten `S05-SUMMARY.md` and `S05-UAT.md` exist on disk under `.artifacts/m004-s05-t02/` and `.artifacts/m004-s05-t03/`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The generic slice goal reads like `report -> replay -> evidence review -> retry` for both scenario types, but the shipped PPT UI currently reaches replay from the sibling `/history` row rather than from a direct report CTA. The slice accepted that real contract and proved PPT report + PPT replay + PPT retry on the current route family instead of inventing a new navigation surface for acceptance.

## Known Limitations

PPT report still does not expose a direct `定位问题片段` CTA. Replay remains reachable from the completed PPT row on `/history`, while report itself offers retry. The route proof is anchored to seeded completed sessions and saved artifact packs, so rerunning the saved Playwright verifiers still requires a local `localhost:3444` backend and `localhost:3445` web stack.

## Follow-ups

If later work wants a direct PPT report-to-replay handoff, build it on the existing `/practice/{sessionId}/replay` route and current page-anchor contract rather than adding a PPT-only review surface. Also repair or quarantine the repo-root pytest path before relying on it for future close-out gates; the authored backend venv path is the trustworthy verifier today.

## Files Created/Modified

- `backend/src/common/conversation/replay.py` — Aligned replay with the shared scenario-aware learner contract so presentation sessions stay on the same route family as report.
- `backend/src/common/conversation/schemas.py` — Carried the replay payload fields needed for presentation review and sales-field nulling.
- `backend/tests/unit/test_replay_service.py` — Locked replay behavior for sales deep links, PPT review payloads, and presentation-session field hygiene.
- `backend/tests/integration/test_practice_evidence_flow.py` — Proved shared report/replay/retry behavior across sales and PPT sessions.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Covered learner report behavior across sales, PPT, and degraded states on the shared route.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Covered replay deep-linking, PPT page evidence, and degraded replay behavior.
- `web/src/app/(dashboard)/history/page.test.tsx` — Locked the completed-session entrypoints that expose the current report/replay route family.
- `.gsd/milestones/M004/slices/S05/S05-SUMMARY.md` — Compressed the three task outputs into the slice-level delivery record for downstream roadmap work.
- `.gsd/milestones/M004/slices/S05/S05-UAT.md` — Recorded the concrete sales + PPT acceptance script tied to the saved browser evidence pack.
