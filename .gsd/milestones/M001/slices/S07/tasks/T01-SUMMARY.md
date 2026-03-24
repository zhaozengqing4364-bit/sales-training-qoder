---
id: T01
parent: S07
milestone: M001
provides:
  - Canonical normalized PPT review facts plus legacy/StepFun page-number persistence parity for downstream shared report wiring.
key_files:
  - backend/src/presentation_coach/services/presentation_report_service.py
  - backend/src/presentation_coach/websocket/presentation_handler.py
  - backend/tests/unit/evaluation/test_comprehensive_report_service.py
  - backend/tests/unit/test_presentation_handler_persistence.py
  - backend/tests/unit/test_presentation_stepfun_realtime_handler.py
  - .gsd/milestones/M001/slices/S07/S07-PLAN.md
key_decisions:
  - D029 centralizes normalized presentation review building in PresentationReportService and keeps legacy page evidence on the existing update_analysis persistence path.
patterns_established:
  - Reuse `PresentationReportService.build_presentation_review(...)` as the single PPT review fact source, then map that payload into enhanced/shared read surfaces instead of recomputing presentation heuristics elsewhere.
  - Persist legacy PPT page context via `transcript_metadata.page_number` on `MessageStorageService.update_analysis(...)` rather than adding a second message-write path.
observability_surfaces:
  - backend/src/presentation_coach/services/presentation_report_service.py
  - backend/src/presentation_coach/websocket/presentation_handler.py
  - backend/tests/unit/evaluation/test_comprehensive_report_service.py
  - backend/tests/unit/test_presentation_handler_persistence.py
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata`
duration: 2h
verification_result: passed
completed_at: 2026-03-24T10:09:23+08:00
blocker_discovered: false
---

# T01: 收稳 PPT 页级证据写入并抽出统一 presentation review builder

**Added a canonical PresentationReportService review builder and legacy page-number persistence for PPT sessions.**

## What Happened

I started with the red phase in the three planned unit-test files. On the legacy websocket side, I tightened the persistence tests so `_check_and_interrupt(...)` had to forward `current_page` into `analysis_data.transcript_metadata.page_number`, and `_update_message_analysis(...)` had to pass that field through `MessageStorageService.update_analysis(...)`. On the report side, I added direct tests for a new normalized PPT review payload: a happy path with six dimension scores, per-page summaries, required-talking-point coverage, issue counts, and empty degraded reasons; and a degraded historical path where missing page metadata still returns a presentation-shaped payload with explicit diagnostics instead of silently pretending page coverage is trustworthy. I also strengthened the StepFun baseline by pinning a non-default `current_page` in the normalization/persistence test.

Then I implemented the smallest production changes to satisfy that contract. `PresentationReportService` now has a reusable `build_presentation_review(...)` builder that loads the session/page context once and returns normalized presentation review facts: six dimensions, page summaries, required-talking-point coverage, interruption counts, strengths, improvements, recommendations, and diagnostics including `has_page_metadata`, coverage status, and degraded reasons. `build_report(...)` now reuses that builder instead of maintaining a second parallel presentation-metrics path. In the legacy PPT websocket handler, `_check_and_interrupt(...)` now writes `transcript_metadata.page_number=self.current_page` alongside AI feedback, and `_update_message_analysis(...)` forwards transcript metadata through the existing storage service so legacy and StepFun runtimes land on the same persisted evidence field.

I also fixed the slice plan’s pre-flight degraded-path verification selector. The original `-k degraded` matched zero tests and produced a false-negative gate failure; the plan now points at the real test name substring `degrades_without_page_metadata`.

## Verification

The task-level backend verification passed fresh: the full unit suite covering `PresentationReportService`, the legacy presentation handler, and the StepFun presentation handler is green, and the focused legacy page-number test path remains green. I also ran the explicit degraded-path unit check required by the slice observability fix, which passed.

For slice-level visibility, I ran the remaining automated checks as well. The backend contract/integration command currently fails because `tests/contract/test_presentation_report_contract.py` and `tests/integration/test_presentation_report_flow.py` do not exist yet; that is the expected next gap for T02, not a regression in T01. The existing shared report page test still passes. I did not run the slice runtime/UAT flow in this task because the shared `/practice/{sessionId}/report` presentation contract and presentation-specific UI branch are not implemented until T02/T03.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py` | 0 | ✅ pass | 7.38s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_presentation_handler_persistence.py -k page_number` | 0 | ✅ pass | 7.38s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata` | 0 | ✅ pass | 5.78s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` | 4 | ❌ fail | 3.35s |
| 5 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 1.55s |

## Diagnostics

- Inspect the normalized PPT review authority in `backend/src/presentation_coach/services/presentation_report_service.py`.
- Inspect the legacy persistence bridge in `backend/src/presentation_coach/websocket/presentation_handler.py`.
- Re-run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata` to confirm the explicit degraded payload when historical page metadata is missing.
- Re-run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py` to verify legacy/StepFun page-number persistence parity.
- At runtime, future agents can inspect `conversation_messages.transcript_metadata.page_number` for a completed presentation session to confirm both runtimes now persist the same page-evidence field.

## Deviations

- No product-scope deviation from the task plan.
- I made one local factual correction before execution: the slice-plan degraded-path verification entry used `-k degraded`, which matched zero tests. I updated it to `-k degrades_without_page_metadata` so the gate points at the actual degraded-path proof.

## Known Issues

- `backend/tests/contract/test_presentation_report_contract.py` and `backend/tests/integration/test_presentation_report_flow.py` are not present yet, so the slice-level backend contract/integration command remains red until T02 creates those tests and wires the shared report contract.
- Runtime/UAT for `/practice/{sessionId}/report` presentation rendering is intentionally deferred to T02/T03 because T01 only established the evidence/building blocks, not the shared report API/UI branch.

## Files Created/Modified

- `backend/src/presentation_coach/services/presentation_report_service.py` — added the normalized `build_presentation_review(...)` payload builder, explicit degraded diagnostics, and reused it from `build_report(...)`.
- `backend/src/presentation_coach/websocket/presentation_handler.py` — persisted legacy `current_page` via `transcript_metadata.page_number` on message-analysis updates.
- `backend/tests/unit/evaluation/test_comprehensive_report_service.py` — added normalized PPT review happy-path/degraded-path tests and the reuse-path guard for `build_report(...)`.
- `backend/tests/unit/test_presentation_handler_persistence.py` — added legacy transcript-metadata persistence assertions.
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py` — strengthened the StepFun page-number baseline with a non-default page.
- `.gsd/milestones/M001/slices/S07/S07-PLAN.md` — fixed the degraded-path verification selector and marked T01 complete.
- `.gsd/DECISIONS.md` — recorded D029 for the single-source presentation review builder and shared page-evidence persistence path.
- `.codex/loop/state.json` — advanced Safe Grow continuity to M001-S07-T01.
- `.codex/loop/log.md` — appended the Safe Grow iteration record for T01.
