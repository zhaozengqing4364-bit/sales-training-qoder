---
id: T01
parent: S04
milestone: M002
provides:
  - Shared stage-aware sales report-alignment helper for persisted sales evidence
  - Focused regression coverage for discovery, objection, closing, and insufficient-evidence fallback cases
key_files:
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/effectiveness/schemas.py
  - backend/src/common/effectiveness/__init__.py
  - backend/tests/unit/test_effectiveness_sales_report_alignment.py
  - .gsd/milestones/M002/slices/S04/S04-PLAN.md
  - .gsd/milestones/M002/slices/S04/tasks/T01-PLAN.md
key_decisions:
  - D041: keep public report keys stable and expose alignment diagnostics only on the internal helper seam
patterns_established:
  - Use `resolve_sales_report_alignment(...)` for persisted sales-stage + full dimension-score evidence, and fall back through current evaluator semantics instead of partial read-side heuristics
observability_surfaces:
  - backend/tests/unit/test_effectiveness_sales_report_alignment.py
  - internal helper diagnostics: `alignment_used`, `stage_key`, `focus_type`, `fallback_reason`
  - .gsd/DECISIONS.md (D041)
duration: 1h48m
verification_result: passed
completed_at: 2026-03-24T23:03:44+0800
blocker_discovered: false
---

# T01: Add a shared sales report-alignment helper in `common.effectiveness`

**Added a shared persisted-evidence sales alignment helper with exact stage-aware issue/goal tests.**

## What Happened

I first fixed the preflight artifact gaps by adding an explicit slice-level failure-path verification line in `.gsd/milestones/M002/slices/S04/S04-PLAN.md` and an `## Observability Impact` section in `.gsd/milestones/M002/slices/S04/tasks/T01-PLAN.md`.

Then I followed TDD for the task itself: I created `backend/tests/unit/test_effectiveness_sales_report_alignment.py`, ran it red to confirm the missing helper/export, and implemented the smallest shared backend seam in `backend/src/common/effectiveness/evaluator.py`.

The new `resolve_sales_report_alignment(...)` helper:
- accepts persisted `sales_stage` + `score_snapshot`
- reuses the S03 coaching-focus selector for stage-aware alignment when full sales dimension evidence is present
- returns the existing report-shaped `main_issue` / `next_goal`
- exposes internal diagnostics (`alignment_used`, `stage_key`, `focus_type`, `fallback_reason`) for later projection/logging work
- falls back through current evaluator semantics when persisted sales evidence is incomplete

To keep vocabulary from drifting, I also centralized the sales report issue/goal payload map and reused it from both the existing sales evaluator path and the new alignment helper. I added the minimal typed contracts in `backend/src/common/effectiveness/schemas.py`, exported the helper from `backend/src/common/effectiveness/__init__.py`, and recorded the downstream-relevant seam choice as D041.

## Verification

Task-level verification passed fresh on the new focused backend suite, including the verbose rerun and the explicit insufficient-evidence failure-path selector.

I also ran the full slice verification set as required for an intermediate task. Results were partial, as expected:
- backend contract/integration checks already pass
- the new focused failure-path check passes
- one broad backend unit pack still fails on carried-forward replay-service tests outside this helper seam
- the focused `-k 'sales_alignment or stale_snapshot or insufficient_sales_evidence'` slice command currently selects 0 tests and exits 5 because those named T02 cases do not exist yet
- the web slice command still fails on a pre-existing report-page degraded-copy expectation outside T01 scope

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py` | 0 | ✅ pass | 2.55s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -vv` | 0 | ✅ pass | 2.51s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py` | 1 | ❌ fail | 6.00s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv` | 5 | ❌ fail | 5.61s |
| 5 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv` | 0 | ✅ pass | 5.30s |
| 6 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py` | 0 | ✅ pass | 6.05s |
| 7 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 1 | ❌ fail | 1.49s |

## Diagnostics

Inspect the helper directly through `backend/tests/unit/test_effectiveness_sales_report_alignment.py`. The internal alignment result now exposes `alignment_used`, `stage_key`, `focus_type`, and `fallback_reason`, which gives T02 a single seam for projection logging without changing public report/websocket/database contracts. D041 in `.gsd/DECISIONS.md` records that boundary explicitly.

## Deviations

I added internal helper diagnostics and minimal typing beyond the bare task text so the later projection/logging tasks can inspect override vs fallback behavior from one shared seam. Public field names and external contracts remained unchanged.

## Known Issues

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py` still fails in `tests/unit/test_replay_service.py` because mocked completed sessions fall into the presentation-review path and return `[PRESENTATION_REVIEW_BUILD_FAILED:]`; this is outside the T01 helper seam.
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv` currently selects 0 tests and exits 5 because those focused T02 cases are not present yet.
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` still fails on `report/page.test.tsx` because it expects the older enhanced-report degraded copy (`综合洞察暂不可用，当前页面仅展示统一训练证据。`) that the current page no longer renders.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S04/S04-PLAN.md` — added an explicit slice-level failure-path verification command per the preflight observability gap.
- `.gsd/milestones/M002/slices/S04/tasks/T01-PLAN.md` — added the missing `## Observability Impact` section.
- `backend/src/common/effectiveness/evaluator.py` — added `resolve_sales_report_alignment(...)`, centralized the sales report issue/goal vocabulary map, and kept fallback semantics on the current evaluator path.
- `backend/src/common/effectiveness/schemas.py` — added typed contracts for `MainIssue` and `SalesReportAlignment`.
- `backend/src/common/effectiveness/__init__.py` — exported the new alignment helper.
- `backend/tests/unit/test_effectiveness_sales_report_alignment.py` — added focused red/green coverage for persisted-evidence alignment and insufficient-evidence fallback.
- `.gsd/DECISIONS.md` — appended D041 to document the internal diagnostic seam choice.
