---
id: T01
parent: S03
milestone: M001
provides:
  - Deterministic server-side coaching suggestions plus a report first screen that leads with result, issue, next goal, and evidence
key_files:
  - backend/src/common/api/practice.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/lib/session-evidence.ts
  - web/src/lib/api/types.ts
key_decisions:
  - Reused one backend deterministic suggestion builder for both `/practice/sessions/{id}/report` and end-session report payloads so coaching copy stays authoritative and contract-tested
patterns_established:
  - Derive learner-facing coaching copy and first-screen summary strictly from unified evidence fields, not from enhanced reports or client-side heuristics
observability_surfaces:
  - backend `/api/v1/practice/sessions/{id}/report` payload suggestions + overall_result/evaluable/main_issue/next_goal, `[Report]` frontend debug logs, and `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
duration: 35m
verification_result: passed
completed_at: 2026-03-23T11:59:30+08:00
blocker_discovered: false
---

# T01: 重排单次报告首屏并替换占位建议文案

**Made report suggestions deterministic and reordered the report first screen around result, issue, next goal, and evidence.**

## What Happened

I first fixed the slice plan’s missing failure-path verification note so this slice has an explicit degraded-state check. Then I added failing backend and frontend focused tests before touching runtime behavior.

On the backend, I replaced the hardcoded English placeholder suggestion copy with one deterministic builder in `backend/src/common/api/practice.py`. The builder now uses only unified evidence facts (`overall_result`, `main_issue`, `next_goal`, `evaluable`, `not_evaluable_reason`, `stage_summary`) and formats actionable Chinese coaching copy. I reused that same builder for the end-session report payloads so the API does not diverge between “session just ended” and “open report later”. This addresses the first must-have: `report.suggestions` no longer returns placeholder English text and is now projection-backed and testable.

On the frontend, I updated `web/src/lib/api/types.ts` and `web/src/lib/session-evidence.ts` so completeness gaps like `message_scores`, `stage_evidence`, and `presentation` render as human labels instead of machine field names. Then I restructured `web/src/app/(user)/practice/[sessionId]/report/page.tsx` so the top of the page now answers the four intended questions in order: result, issue, next goal, evidence. Enhanced insights, knowledge-check diagnostics, voice policy snapshots, detailed stage facts, and highlights remain available but are pushed below the first reading path. I also removed the dead “导出报告” affordance. This addresses the second must-have: the report first screen now stays readable from unified evidence even when enhanced/highlights are missing, instead of letting diagnostics crowd the main reading path.

## Verification

I ran the task-level backend and frontend verification commands and both passed after the changes. I also ran the slice-level backend regression command to make sure the report contract work did not break existing admin user API coverage. The slice-level frontend command returned success but only executed the report page spec because the admin-focused spec files referenced in the slice plan are not present in this worktree yet; that is expected to be completed in T02.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && pytest tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 2.14s |
| 2 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 0.68s |
| 3 | `cd backend && pytest tests/contract/test_practice_evidence_contract.py tests/integration/test_admin_users_api.py` | 0 | ✅ pass | 2.92s |
| 4 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass* | 0.72s |
| 5 | `python3 -m py_compile backend/src/common/api/practice.py` | 0 | ✅ pass | <1s |

`*` The command succeeded, but only `src/app/(user)/practice/[sessionId]/report/page.test.tsx` ran because the admin-focused spec files do not exist yet in this slice task.

## Diagnostics

- Inspect `GET /api/v1/practice/sessions/{sessionId}/report` and confirm `suggestions`, `overall_result`, `evaluable`, `main_issue`, `next_goal`, and `evidence_completeness` are present.
- Inspect frontend logs for `[Report] Loaded unified evidence contract`, `[Report] Enhanced report unavailable; keeping unified evidence`, and `[Report] Highlights unavailable; keeping unified evidence`.
- Re-run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` to verify first-screen ordering, not-evaluable clarity, and degraded enhanced/highlights behavior.

## Deviations

- I also applied the deterministic suggestion builder to the end-session report payloads, not only the `/practice/sessions/{id}/report` endpoint, so there is no copy drift between immediate and later report reads.
- I did not create extra unit tests for `web/src/lib/session-evidence.ts`; instead, the new page-focused assertions cover the humanized completeness labels through the real report page surface.

## Known Issues

- Browser-based manual review for `/practice/<sessionId>/report` was not completed in this time-box; the task currently relies on focused automated verification only.
- The slice-level admin frontend specs referenced in `S03-PLAN.md` (`src/app/admin/users/[id]/page.test.tsx`, `src/components/admin/manager-lite-panel.test.tsx`) are not present yet and remain part of T02.

## Files Created/Modified

- `backend/src/common/api/practice.py` — added deterministic suggestion generation and reused it for report payloads
- `backend/tests/contract/test_practice_evidence_contract.py` — locked suggestion copy to unified evidence fields
- `web/src/lib/api/types.ts` — tightened evidence completeness/suggestion semantics on the frontend boundary
- `web/src/lib/session-evidence.ts` — humanized completeness labels for missing evidence fields
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — reordered the first screen and removed the dead export button
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — added focused assertions for first-screen ordering, degraded-state clarity, and human-readable completeness messaging
- `.gsd/milestones/M001/slices/S03/S03-PLAN.md` — added a failure-path verification bullet required by pre-flight
