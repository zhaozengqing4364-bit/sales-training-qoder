---
id: T03
parent: S04
milestone: M004
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/replay.py", "backend/src/common/conversation/schemas.py", "backend/tests/unit/test_replay_service.py", "web/src/app/(user)/practice/[sessionId]/replay/page.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", "web/src/components/practice/presentation/SlideViewer.tsx", "web/src/lib/api/types.ts", ".gsd/DECISIONS.md"]
key_decisions: ["D072: keep PPT page replay on the existing replay authority line by extending replay with scenario_type/presentation_id/presentation_review and consuming page routing via replay query params instead of inventing a second PPT replay payload."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Passed the exact replay-page task-plan suite with `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (7/7). Re-ran the upstream report-page suite with `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` (10/10) to confirm no regression. Also syntax-checked the touched backend replay files with `cd backend && venv/bin/python -m py_compile src/common/conversation/replay.py src/common/conversation/schemas.py`. The local web dev server booted successfully on :3445 and was shut down cleanly, but browser automation could not be counted because the Playwright tool install is broken on this machine (`Cannot find module './registry'`)."
completed_at: 2026-03-26T03:29:18.923Z
blocker_discovered: false
---

# T03: Extended the current replay route to show PPT page-level issues with page anchors, slide context, and transcript jumps.

> Extended the current replay route to show PPT page-level issues with page anchors, slide context, and transcript jumps.

## What Happened
---
id: T03
parent: S04
milestone: M004
key_files:
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/tests/unit/test_replay_service.py
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/components/practice/presentation/SlideViewer.tsx
  - web/src/lib/api/types.ts
  - .gsd/DECISIONS.md
key_decisions:
  - D072: keep PPT page replay on the existing replay authority line by extending replay with scenario_type/presentation_id/presentation_review and consuming page routing via replay query params instead of inventing a second PPT replay payload.
duration: ""
verification_result: passed
completed_at: 2026-03-26T03:29:18.924Z
blocker_discovered: false
---

# T03: Extended the current replay route to show PPT page-level issues with page anchors, slide context, and transcript jumps.

**Extended the current replay route to show PPT page-level issues with page anchors, slide context, and transcript jumps.**

## What Happened

I completed T03 by extending the existing replay authority line instead of adding a separate PPT replay surface. On the backend, replay payloads for presentation sessions now include scenario_type, presentation_id, and presentation_review so the existing replay route can render page-level evidence without depending on a second API contract. On the frontend, the current /practice/{sessionId}/replay page now branches for presentation sessions, reuses SlideViewer, resolves page/page_anchor_status/page_anchor_reason query params into explicit resolved/degraded page banners, shows the selected page summary and issue clusters, and lets learners jump from issue-cluster cards into the matching transcript turns. I also added focused replay tests for the new presentation behavior and kept the upstream report-page suite green to prove T02 did not regress. Local environment verification was partially constrained by a broken global npm wrapper, a broken backend pytest/pip install in backend/venv, and a broken Playwright browser tool install, so verification used the known pnpm dlx npm@11.6.1 workaround for web tests and py_compile for the touched backend replay files.

## Verification

Passed the exact replay-page task-plan suite with `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (7/7). Re-ran the upstream report-page suite with `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` (10/10) to confirm no regression. Also syntax-checked the touched backend replay files with `cd backend && venv/bin/python -m py_compile src/common/conversation/replay.py src/common/conversation/schemas.py`. The local web dev server booted successfully on :3445 and was shut down cleanly, but browser automation could not be counted because the Playwright tool install is broken on this machine (`Cannot find module './registry'`).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 1781ms |
| 2 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 1661ms |
| 3 | `cd backend && venv/bin/python -m py_compile src/common/conversation/replay.py src/common/conversation/schemas.py` | 0 | ✅ pass | 100ms |


## Deviations

Updated backend/src/common/conversation/schemas.py and web/src/lib/api/types.ts so the replay response model and typed frontend contract could carry the new presentation replay fields, and added small data-testid hooks to SlideViewer to keep the shared viewer verifiable on the replay route.

## Known Issues

The machine's global Volta npm wrapper still exits 1 before Vitest starts, so exact plain `npm test ...` commands remain environment-blocked; repo-local backend pytest/pip in backend/venv are also environment-broken (`ModuleNotFoundError: pygments.lexer` / `pip._vendor.rich.console`), and browser automation is blocked by a broken Playwright install (`Cannot find module './registry'`). None of these blockers are caused by the T03 product code changes.

## Files Created/Modified

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/schemas.py`
- `backend/tests/unit/test_replay_service.py`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/components/practice/presentation/SlideViewer.tsx`
- `web/src/lib/api/types.ts`
- `.gsd/DECISIONS.md`


## Deviations
Updated backend/src/common/conversation/schemas.py and web/src/lib/api/types.ts so the replay response model and typed frontend contract could carry the new presentation replay fields, and added small data-testid hooks to SlideViewer to keep the shared viewer verifiable on the replay route.

## Known Issues
The machine's global Volta npm wrapper still exits 1 before Vitest starts, so exact plain `npm test ...` commands remain environment-blocked; repo-local backend pytest/pip in backend/venv are also environment-broken (`ModuleNotFoundError: pygments.lexer` / `pip._vendor.rich.console`), and browser automation is blocked by a broken Playwright install (`Cannot find module './registry'`). None of these blockers are caused by the T03 product code changes.
