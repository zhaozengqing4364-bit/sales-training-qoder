---
id: T01
parent: S05
milestone: M004
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/replay.py", "backend/src/common/conversation/schemas.py", "backend/tests/unit/test_replay_service.py", "backend/tests/integration/test_practice_evidence_flow.py", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", "web/src/app/(dashboard)/history/page.test.tsx", ".gsd/milestones/M004/slices/S05/tasks/T01-SUMMARY.md"]
key_decisions: ["D073: make `/api/v1/sessions/{id}/replay` mirror the shared report route for presentation sessions by carrying `scenario_type`/`presentation_id`/`presentation_review` and clearing sales-only conclusion fields."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Passed the focused backend replay/evidence pytest suite with `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py`. Passed the focused report/replay/history Vitest suite with `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'`. Re-ran the slice verification as one chained command across backend and web, and it passed end to end."
completed_at: 2026-03-26T04:18:05.543Z
blocker_discovered: false
---

# T01: Repaired the shared replay contract and extended the learning-loop regression net for sales + PPT routes.

> Repaired the shared replay contract and extended the learning-loop regression net for sales + PPT routes.

## What Happened
---
id: T01
parent: S05
milestone: M004
key_files:
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/app/(dashboard)/history/page.test.tsx
  - .gsd/milestones/M004/slices/S05/tasks/T01-SUMMARY.md
key_decisions:
  - D073: make `/api/v1/sessions/{id}/replay` mirror the shared report route for presentation sessions by carrying `scenario_type`/`presentation_id`/`presentation_review` and clearing sales-only conclusion fields.
duration: ""
verification_result: passed
completed_at: 2026-03-26T04:18:05.544Z
blocker_discovered: false
---

# T01: Repaired the shared replay contract and extended the learning-loop regression net for sales + PPT routes.

**Repaired the shared replay contract and extended the learning-loop regression net for sales + PPT routes.**

## What Happened

Reproduced the planned replay/evidence verification first and found the shared replay payload was already broken: `ReplayService.get_replay_data()` had lost its `scenario_type` and `presentation_review` locals, so both unit and integration replay paths failed before new regression coverage could run. Repaired that seam in `backend/src/common/conversation/replay.py` by deriving `scenario_type` from the shared session-evidence projection, mirroring the report route’s presentation branch, preserving `presentation_review`/`presentation_id` on the existing replay surface, and nulling sales-only conclusion fields for presentation sessions. Extended `backend/src/common/conversation/schemas.py` so FastAPI no longer filtered `presentation_review` out of `/api/v1/sessions/{id}/replay` responses. Added focused backend regressions for PPT replay leakage and PPT report↔replay route-family parity, then added focused web regressions for PPT degraded report copy when highlights fail, PPT retry continuity from replay, and presentation history entries staying on the shared `/practice/{sessionId}/report` + `/practice/{sessionId}/replay` route family. Also repaired a corrupted local `backend/venv` Jinja2 install in place so backend pytest could collect again; the product-code delta stayed limited to the replay contract seam and the regression files.

## Verification

Passed the focused backend replay/evidence pytest suite with `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py`. Passed the focused report/replay/history Vitest suite with `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'`. Re-ran the slice verification as one chained command across backend and web, and it passed end to end.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py` | 0 | ✅ pass | 6100ms |
| 2 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'` | 0 | ✅ pass | 7600ms |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py && cd ../web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'` | 0 | ✅ pass | 7900ms |


## Deviations

The written task looked like a regression-net-only pass, but local reality required a small replay-contract repair first because the focused replay suites were already red before any new coverage could run. Verification also had to adapt the web leg to `pnpm dlx npm@11.6.1` because the machine’s global npm wrapper is unreliable.

## Known Issues

The machine’s global Volta `npm` wrapper still fails before Vitest starts, so focused web verification remains dependent on `pnpm dlx npm@11.6.1`. No product-code issue remains open from this task.

## Files Created/Modified

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/schemas.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`
- `.gsd/milestones/M004/slices/S05/tasks/T01-SUMMARY.md`


## Deviations
The written task looked like a regression-net-only pass, but local reality required a small replay-contract repair first because the focused replay suites were already red before any new coverage could run. Verification also had to adapt the web leg to `pnpm dlx npm@11.6.1` because the machine’s global npm wrapper is unreliable.

## Known Issues
The machine’s global Volta `npm` wrapper still fails before Vitest starts, so focused web verification remains dependent on `pnpm dlx npm@11.6.1`. No product-code issue remains open from this task.
