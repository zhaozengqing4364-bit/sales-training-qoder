---
id: T03
parent: S01
milestone: M004
provides: []
requires: []
affects: []
key_files: ["web/src/lib/session-evidence.ts", "web/src/app/(user)/practice/[sessionId]/report/page.tsx", "web/src/app/(dashboard)/history/page.tsx", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", "web/src/app/(dashboard)/history/page.test.tsx", ".gsd/DECISIONS.md", ".codex/loop/state.json", ".codex/loop/log.md"]
key_decisions: ["Derived report/history coaching cues from the unified completed-session contract (`main_issue` / `next_goal`) via a shared frontend helper instead of treating highlights or enhanced reports as the primary source.", "Kept degraded-state behavior on the existing routes explicit: report retains issue/goal vocabulary when enhanced report or highlights fail, and history retains unified-evidence cues when analytics snapshots degrade."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Red-green path: I first extended `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` and `web/src/app/(dashboard)/history/page.test.tsx`, then ran `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` and watched it fail on the missing `证据支撑` / `证据补强` labels and missing history learning cues. After implementing the shared helper and page updates, I reran the same command and it passed (10/10 tests). Because this is the final task in the slice, I also reran the earlier slice drift detectors: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py` passed (43 tests), and `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'` passed (5 tests). Together those checks confirm the backend replay authority line, replay/highlight UI, and the new report/history carry-forward stay aligned on the current routes while degraded states remain explicit."
completed_at: 2026-03-25T16:07:52.404Z
blocker_discovered: false
---

# T03: Aligned report and history learning cues with replay evidence and degraded-state behavior.

> Aligned report and history learning cues with replay evidence and degraded-state behavior.

## What Happened
---
id: T03
parent: S01
milestone: M004
key_files:
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(dashboard)/history/page.test.tsx
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Derived report/history coaching cues from the unified completed-session contract (`main_issue` / `next_goal`) via a shared frontend helper instead of treating highlights or enhanced reports as the primary source.
  - Kept degraded-state behavior on the existing routes explicit: report retains issue/goal vocabulary when enhanced report or highlights fail, and history retains unified-evidence cues when analytics snapshots degrade.
duration: ""
verification_result: passed
completed_at: 2026-03-25T16:07:52.407Z
blocker_discovered: false
---

# T03: Aligned report and history learning cues with replay evidence and degraded-state behavior.

**Aligned report and history learning cues with replay evidence and degraded-state behavior.**

## What Happened

I started with red-green coverage on the current report and history entrypoints so the shared learning vocabulary was locked before production changes. The new assertions required the report page to render the same issue/goal labels already used on replay/highlights, and required the history page to keep those learning cues visible even when analytics snapshots degrade. Those tests failed first on the missing labels and missing history cue block, which confirmed the drift was real rather than a test setup problem.

To fix that without introducing a second truth line, I added a small `extractSessionLearningCue(...)` helper in `web/src/lib/session-evidence.ts`. That helper derives issue label, goal label, text, and fallback summary from the unified completed-session contract (`main_issue`, `next_goal`, `feedback_summary`) so report and history can stay aligned with replay/highlight vocabulary.

On `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, I reused that helper to render issue-family and next-goal badges directly in the existing sales result cards. The page still uses the current route and current sections, but it now speaks the same coaching labels as replay/highlights even when enhanced report generation or highlight loading degrades.

On `web/src/app/(dashboard)/history/page.tsx`, I added a compact learning-cue block inside each history card. When unified evidence exposes a main issue, next goal, or feedback summary, the history entry now shows the same issue/goal badges plus the current卡点 / 下一轮重点 text and any summary line. The degraded analytics hint remains explicit and the history list still renders from unified evidence when statistics or trends fail.

After the production changes I reran the focused task suite and the earlier slice drift detectors, then recorded the frontend contract decision in `.gsd/DECISIONS.md` and updated `.codex/loop/state.json` plus `.codex/loop/log.md` so the repository continuity layer points at M004/S01/T03 instead of the stale M003 item.

## Verification

Red-green path: I first extended `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` and `web/src/app/(dashboard)/history/page.test.tsx`, then ran `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` and watched it fail on the missing `证据支撑` / `证据补强` labels and missing history learning cues. After implementing the shared helper and page updates, I reran the same command and it passed (10/10 tests). Because this is the final task in the slice, I also reran the earlier slice drift detectors: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py` passed (43 tests), and `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'` passed (5 tests). Together those checks confirm the backend replay authority line, replay/highlight UI, and the new report/history carry-forward stay aligned on the current routes while degraded states remain explicit.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py` | 0 | ✅ pass | 8300ms |
| 2 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'` | 0 | ✅ pass | 6800ms |
| 3 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 9800ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`


## Deviations
None.

## Known Issues
None.
