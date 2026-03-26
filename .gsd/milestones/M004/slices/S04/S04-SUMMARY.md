---
id: S04
parent: M004
milestone: M004
provides:
  - A shared presentation-review page-level issue-cluster contract (`page_summaries[*].issue_clusters` + diagnostics/completeness aggregates) that explains where and why a PPT page needs rework.
  - A current-report-route PPT overview that shows which pages have which issue clusters and the evidence behind them without adding a second learning page.
  - A current-replay-route PPT page anchor flow that combines SlideViewer context, page-level issue clusters, explicit page-banner fallback states, and transcript jumps on the same replay surface.
requires:
  - slice: S01
    provides: the existing presentation report/replay learning-evidence authority line and shared vocabulary that S04 extends without creating new PPT routes
affects:
  - S05
key_files:
  - backend/src/presentation_coach/services/presentation_report_service.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/tests/unit/test_presentation_report_service.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/conftest.py
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/components/practice/presentation/SlideViewer.tsx
  - web/src/lib/session-evidence.ts
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - package.json
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D070: keep PPT page-level learning issues under `presentation_review.page_summaries[*].issue_clusters` and expose aggregate cluster count/types through diagnostics/completeness rather than inventing a second PPT evidence payload.
  - D071: render page-level issue details inside the existing `presentation_review.page_summaries[*]` report cards and drive the overview from `presentation_review.diagnostics.page_issue_cluster_count/page_issue_types` instead of building a second PPT learning panel.
  - D072: keep PPT page replay on the existing replay authority line by extending replay with `scenario_type` / `presentation_id` / `presentation_review` and consuming page routing through replay query params instead of creating a PPT-only replay route.
patterns_established:
  - Extend `presentation_review` and scenario-aware consumers on the current report/replay routes instead of creating PPT-only learning surfaces.
  - Keep both per-page evidence and aggregate diagnostics: render real issue cards from `page_summaries[*].issue_clusters`, but use cluster count/types for stable tests and degraded-state inspection.
  - For focused backend unit suites, lazy-import the FastAPI app inside fixtures so unrelated runtime dependencies do not block pure service verification during slice close-out.
observability_surfaces:
  - `presentation_review.diagnostics.page_issue_cluster_count` / `page_issue_types` now summarize how many page-level PPT issue clusters a completed session produced and which issue families appeared.
  - `SessionEvidenceService` presentation completeness now carries page-issue cluster aggregates so report/replay consumers and degraded-state diagnostics share the same observability line.
  - The replay route now surfaces page-anchor resolved/degraded/missing banners and preserves turn highlighting when a learner jumps from an issue cluster to the transcript, making anchor success or fallback visible in-product.
drill_down_paths:
  - .gsd/milestones/M004/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-26T03:57:14.145Z
blocker_discovered: false
---

# S04: PPT 页级学习证据

**Current PPT report/replay routes now show page-level issue clusters and let learners jump from page evidence into the matching slide context and transcript turns on the existing authority line.**

## What Happened

S04 extended the existing presentation report/replay authority line instead of adding a second PPT learning product. On the backend, `PresentationReportService` now groups presentation problems at the page level and explains them through `presentation_review.page_summaries[*].issue_clusters`, while diagnostics and session evidence completeness expose aggregate cluster count/types so downstream readers can tell how many page-level issues exist without parsing the full payload. On the report page, the current PPT branch now renders a page-level issue overview plus per-page evidence cards that explain which page drifted off-page, omitted required talking points, over-expanded, used forbidden wording, or answered questions weakly. On the replay page, the current route now accepts page anchor query params, shows explicit resolved/degraded/missing page banners, reuses `SlideViewer`, renders the selected page’s issue clusters, and lets learners jump from a page-level issue card into the matching transcript turns. During close-out, repo-root verification was also hardened so the planned backend/web commands can execute from the repository root without false negatives: `npm test` now delegates correctly into `web`, and focused backend unit suites no longer need to import the whole FastAPI runtime during pytest collection.

## Verification

Fresh slice-plan verification passed after the close-out gate repair: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_presentation_report_service.py` (2 passed), `npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` (10 passed), and `npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (7 passed). The repo-root `npm test` command now truthfully delegates into `web`, and the backend focused unit suite now runs without importing the entire FastAPI runtime during collection.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Close-out required two verification hardening changes that were outside the original task file lists but necessary for auto-mode to execute the planned checks truthfully: (1) added a repo-root `package.json` test shim so repo-root `npm test -- --run ...` delegates into `web` Vitest instead of failing before test startup, and (2) changed `backend/tests/conftest.py` to lazy-import `main` / `User` inside fixtures so the focused presentation service suite no longer drags the full FastAPI runtime dependency tree into pytest collection. No user-facing S04 product behavior changed because of these hardening steps.

## Known Limitations

Historical presentation sessions that never persisted `transcript_metadata.page_number` still degrade to summary-only PPT evidence and cannot truthfully render page anchors or page issue clusters. Replay slide thumbnails remain best-effort; if thumbnail loading fails the route still falls back to summary/issue-cluster/transcript evidence rather than full visual parity. Full live proof that these PPT page-level cues participate in the final combined learning loop remains deferred to S05.

## Follow-ups

S05 should run one live PPT proof that starts from the current report page, enters the current replay page with a page anchor, confirms the issue cluster -> transcript jump path on a real session, and then evaluates the combined sales + PPT learning loop at the milestone level.

## Files Created/Modified

- `backend/src/presentation_coach/services/presentation_report_service.py` — Added deterministic page-level PPT issue clusters plus aggregate diagnostics on the shared presentation review payload.
- `backend/src/common/conversation/session_evidence.py` — Projected page-issue cluster count/types into shared presentation evidence completeness and read-side diagnostics.
- `backend/src/common/conversation/replay.py` — Extended the existing replay authority line to carry presentation scenario metadata and `presentation_review` for PPT replay consumers.
- `backend/src/common/conversation/schemas.py` — Updated replay response models so new presentation replay fields survive FastAPI response filtering.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Rendered PPT page-level overview and per-page issue cluster evidence on the existing shared report route.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Rendered PPT page anchors, page banners, SlideViewer context, issue clusters, and transcript jumps on the existing replay route.
- `web/src/components/practice/presentation/SlideViewer.tsx` — Reused and lightly hardened the shared slide viewer so replay can present current-page context without a second PPT viewer surface.
- `web/src/lib/session-evidence.ts` — Added shared formatting helpers for PPT issue labels, context lines, and degraded notes.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Locked the shared report route to page-level PPT overview and per-page evidence behavior.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Locked the shared replay route to presentation page banners, issue clusters, and transcript jump behavior.
- `backend/tests/unit/test_presentation_report_service.py` — Locked the page-level issue cluster builder and completeness aggregation contract.
- `backend/tests/conftest.py` — Made app imports lazy so focused backend service suites can run without unrelated runtime dependency drift.
- `package.json` — Added a repo-root `npm test` shim that delegates to the web Vitest runner for auto-mode verification.
- `.gsd/KNOWLEDGE.md` — Recorded repo-root npm gate and pytest conftest lazy-import gotchas discovered during close-out.
- `.gsd/PROJECT.md` — Updated current-state documentation to show that M004/S04 page-level PPT learning evidence is complete.
