---
id: T02
parent: S07
milestone: M001
provides:
  - Scenario-aware shared report baselines for presentation sessions, including canonical `presentation_review` facts and degraded page-evidence diagnostics on `/practice/{sessionId}/report`.
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/db/schemas.py
  - backend/src/common/api/practice.py
  - backend/tests/contract/test_presentation_report_contract.py
  - backend/tests/integration/test_presentation_report_flow.py
  - web/src/lib/api/types.ts
key_decisions:
  - Carried forward D029 by making the shared report contract read `PresentationReportService.build_presentation_review(...)` instead of remapping PPT facts into legacy sales fields.
patterns_established:
  - Presentation sessions keep `scenario_type="presentation"` even when page metadata is missing; degradation lives in `presentation_review` and `evidence_completeness`, not in sales `main_issue` / `next_goal` fallbacks.
observability_surfaces:
  - `GET /api/v1/practice/sessions/{id}/report`
  - `practice_session_evidence_projection_built`
  - `practice_session_report_built`
  - `backend/tests/contract/test_presentation_report_contract.py`
  - `backend/tests/integration/test_presentation_report_flow.py`
duration: 1h
verification_result: passed
completed_at: 2026-03-24T11:02:36+08:00
blocker_discovered: false
---

# T02: 把 shared session report contract 扩成 scenario-aware presentation baseline

**Shared session reports now return scenario-aware presentation baselines with canonical `presentation_review`, degraded page-evidence diagnostics, and retry `presentation_id` continuity.**

## What Happened

I started by checking local reality before editing, because the planned T02 files were already present in the worktree: the shared evidence projection already had a presentation branch, `SessionReport` / frontend report types already exposed `scenario_type` and `presentation_review`, and new contract/integration tests for happy-path plus degraded historical presentation sessions were already on disk. Instead of re-authoring a second copy of that work, I read the implementation and treated the tests as the red/green boundary for execution.

The verified T02 baseline is now scenario-aware end to end. `SessionEvidenceService` attaches `PresentationReportService.build_presentation_review(...)` for presentation sessions, rewrites `evidence_completeness` to expose page-metadata completeness plus degraded reasons, and keeps sales projection semantics untouched. `backend/src/common/db/schemas.py` and `web/src/lib/api/types.ts` carry top-level `scenario_type` and `presentation_review` rather than forcing PPT facts through sales-shaped keys. `backend/src/common/api/practice.py` returns the canonical presentation payload from the shared `/practice/sessions/{id}/report` route, preserves retry continuity via `retry_entry.presentation_id`, and leaves sales-only fields null for presentation sessions instead of misrepresenting them as PPT conclusions.

Because the implementation was already in local reality when I picked up T02, the code work in this turn was verification-first plus continuity artifacts: I confirmed the contract matches the task plan, updated safe-grow state/log continuity, wrote this task summary, and marked T02 complete in the slice plan.

## Verification

The task-level backend contract and integration suite passed fresh. Those tests prove both presentation shapes required by the task plan: the happy path returns `scenario_type="presentation"`, canonical `presentation_review`, and retry `presentation_id`; the degraded historical path stays presentation-shaped, returns explicit `degraded` coverage/page-summary diagnostics, and does not revive sales-only fields.

I also ran the rest of the slice’s automated checks for continuity. The T01 backend unit suite is still green, the explicit degraded-path unit and integration selectors both pass, and the existing shared report page test still passes. I did not run the live runtime/browser UAT in T02; that remains part of the final slice closure once the page task is formally wrapped.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py` | 0 | ✅ pass | 4.23s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata` | 0 | ✅ pass | 3.24s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` | 0 | ✅ pass | 3.26s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_presentation_report_flow.py -k degraded` | 0 | ✅ pass | 3.27s |
| 5 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 0.81s |

## Diagnostics

- Request `GET /api/v1/practice/sessions/{id}/report` and inspect `scenario_type`, `presentation_review`, `retry_entry.presentation_id`, and `evidence_completeness.page_metadata_complete / degraded_reasons`.
- Check `practice_session_evidence_projection_built` for `scenario_type`, `projection_complete`, `presentation_page_metadata_complete`, and `presentation_degraded_reasons`.
- Check `practice_session_report_built` for the route-level `scenario_type`, overall score, and presentation completeness diagnostics.
- Re-run `backend/tests/contract/test_presentation_report_contract.py` for contract shape drift and `backend/tests/integration/test_presentation_report_flow.py` for builder-to-route parity.

## Deviations

- Minor local-state correction: the planned T02 code and tests were already present in the worktree when execution started, so this turn validated and carried forward that implementation instead of authoring it from an initial red state.

## Known Issues

- Slice runtime/UAT is still open. I did not run a live presentation session through `/practice/{sessionId}/report` in this task; that proof remains for final slice closure.
- T03 still owns the formal page-task handoff even though the current shared report page test already passes in local reality.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py` — scenario-aware projection now carries `presentation_review` and presentation-specific completeness diagnostics.
- `backend/src/common/db/schemas.py` — `SessionReport` carries top-level `scenario_type` and `presentation_review` schema fields.
- `backend/src/common/api/practice.py` — shared report route returns presentation baselines from the canonical builder and keeps presentation retry metadata.
- `backend/tests/contract/test_presentation_report_contract.py` — locks the happy-path and degraded shared-report contract for presentation sessions.
- `backend/tests/integration/test_presentation_report_flow.py` — proves shared report parity with `PresentationReportService` and degraded-path visibility.
- `web/src/lib/api/types.ts` — frontend shared-report types mirror the scenario-aware presentation contract.
- `.gsd/milestones/M001/slices/S07/S07-PLAN.md` — marked T02 complete.
- `.gsd/milestones/M001/slices/S07/tasks/T02-SUMMARY.md` — recorded task execution, verification evidence, and continuity notes.
- `.codex/loop/state.json` — advanced safe-grow continuity to M001-S07-T02.
- `.codex/loop/log.md` — appended the T02 execution record.
