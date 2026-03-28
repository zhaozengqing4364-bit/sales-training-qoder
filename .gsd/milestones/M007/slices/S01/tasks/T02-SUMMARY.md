---
id: T02
parent: S01
milestone: M007
provides: []
requires: []
affects: []
key_files: ["web/src/app/(user)/practice/[sessionId]/page.tsx", "web/src/components/practice/CoachHealthNotice.tsx", "web/src/components/practice/RightPanelContent.tsx", "web/src/app/(user)/practice/[sessionId]/page.test.tsx", "web/src/components/practice/RightPanelContent.test.tsx", "package.json", "scripts/run-vitest-root.mjs"]
key_decisions: ["Extracted a shared `CoachHealthNotice` so the learner shell and right panel render the same `coachHealth` message instead of drifting into separate copy paths.", "Normalized repo-root `npm test` arguments by stripping a leading `web/` prefix before delegating to `web/` Vitest so the slice-plan verification command runs as written."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Confirmed the learner route and right panel focused Vitest suites pass via the planned repo-root command, confirmed the reconnect/runtime truth backend suites and reducer suite still pass, and ran a browser sanity check against a temporary frontend server on `http://localhost:3445/practice/session-current?scenario_type=sales&voice_mode=legacy`, verifying the learner route renders and the shell stays quiet when no degraded/resumed coach-health message is present."
completed_at: 2026-03-28T03:34:32.557Z
blocker_discovered: false
---

# T02: Surfaced degraded/resumed coach-health on the learner page shell and fixed the repo-root Vitest shim so the planned `web/src/...` verification command executes correctly.

> Surfaced degraded/resumed coach-health on the learner page shell and fixed the repo-root Vitest shim so the planned `web/src/...` verification command executes correctly.

## What Happened
---
id: T02
parent: S01
milestone: M007
key_files:
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/components/practice/CoachHealthNotice.tsx
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - web/src/components/practice/RightPanelContent.test.tsx
  - package.json
  - scripts/run-vitest-root.mjs
key_decisions:
  - Extracted a shared `CoachHealthNotice` so the learner shell and right panel render the same `coachHealth` message instead of drifting into separate copy paths.
  - Normalized repo-root `npm test` arguments by stripping a leading `web/` prefix before delegating to `web/` Vitest so the slice-plan verification command runs as written.
duration: ""
verification_result: passed
completed_at: 2026-03-28T03:34:32.559Z
blocker_discovered: false
---

# T02: Surfaced degraded/resumed coach-health on the learner page shell and fixed the repo-root Vitest shim so the planned `web/src/...` verification command executes correctly.

**Surfaced degraded/resumed coach-health on the learner page shell and fixed the repo-root Vitest shim so the planned `web/src/...` verification command executes correctly.**

## What Happened

Reproduced the verification failure and confirmed the carry-forward backend checks were already passing while the learner route still hid coach-health inside the right panel and the repo-root `npm test` shim dropped `web/src/...` filters. Added failing page-level assertions first, then extracted a shared `CoachHealthNotice` component so both the learner shell and `RightPanelContent` render the same non-healthy `coachHealth` message with a safe empty-message guard. Wired the learner page to show that compact notice above the primary controls, extended the page and panel tests for degraded/resumed plus healthy/malformed boundaries, and replaced the root `npm test` script with a small Node wrapper that strips a leading `web/` before delegating to `web/` Vitest. Reran the focused UI suite, the carry-forward backend/reducer checks, and a temporary browser sanity check on `:3445`, then shut the temporary server down.

## Verification

Confirmed the learner route and right panel focused Vitest suites pass via the planned repo-root command, confirmed the reconnect/runtime truth backend suites and reducer suite still pass, and ran a browser sanity check against a temporary frontend server on `http://localhost:3445/practice/session-current?scenario_type=sales&voice_mode=legacy`, verifying the learner route renders and the shell stays quiet when no degraded/resumed coach-health message is present.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm test -- --run 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'` | 0 | ✅ pass | 3550ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py` | 0 | ✅ pass | 5560ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_persistence.py -k 'restore_session_state'` | 0 | ✅ pass | 6040ms |
| 4 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py -k 'live_coach_health'` | 0 | ✅ pass | 7740ms |
| 5 | `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts'` | 0 | ✅ pass | 2280ms |


## Deviations

Added a small repo-root Vitest argument normalizer because the slice verification command itself was invalid in the current workspace and would have kept failing even after the UI work shipped.

## Known Issues

Focused backend pytest commands still emit the pre-existing `--cov=src` / `No data was collected` warnings from the backend coverage configuration even though the tests pass.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/components/practice/CoachHealthNotice.tsx`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/components/practice/RightPanelContent.test.tsx`
- `package.json`
- `scripts/run-vitest-root.mjs`


## Deviations
Added a small repo-root Vitest argument normalizer because the slice verification command itself was invalid in the current workspace and would have kept failing even after the UI work shipped.

## Known Issues
Focused backend pytest commands still emit the pre-existing `--cov=src` / `No data was collected` warnings from the backend coverage configuration even though the tests pass.
