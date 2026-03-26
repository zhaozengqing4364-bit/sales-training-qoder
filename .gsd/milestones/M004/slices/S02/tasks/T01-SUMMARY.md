---
id: T01
parent: S02
milestone: M004
provides: []
requires: []
affects: []
key_files: ["backend/src/common/conversation/replay.py", "backend/tests/unit/test_replay_service.py", "backend/tests/integration/test_replay_api.py", ".gsd/DECISIONS.md"]
key_decisions: ["Attach replay deep-link metadata as nested `replay_anchor` payloads on `replay.main_issue` and `replay.next_goal` instead of introducing a separate resolver surface.", "Resolve anchors from existing replay messages and timeline markers, preferring matching highlights and degrading to visible stage or missing-marker states when exact highlight targets are unavailable."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Wrote failing tests first for resolved and degraded replay anchors, confirmed the new assertions failed because `replay_anchor` was absent, then implemented the resolver and reran the focused backend verification command until the full targeted suite passed. Final verification covered unit and integration replay contracts for resolved highlight anchors, degraded stage fallback when no matching highlight exists, degraded missing-marker behavior, and the existing replay/message/highlights access-control and normalization checks."
completed_at: 2026-03-25T16:29:42.777Z
blocker_discovered: false
---

# T01: Added stable replay anchors to replay issue/goal conclusions with degraded fallback coverage.

> Added stable replay anchors to replay issue/goal conclusions with degraded fallback coverage.

## What Happened
---
id: T01
parent: S02
milestone: M004
key_files:
  - backend/src/common/conversation/replay.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/integration/test_replay_api.py
  - .gsd/DECISIONS.md
key_decisions:
  - Attach replay deep-link metadata as nested `replay_anchor` payloads on `replay.main_issue` and `replay.next_goal` instead of introducing a separate resolver surface.
  - Resolve anchors from existing replay messages and timeline markers, preferring matching highlights and degrading to visible stage or missing-marker states when exact highlight targets are unavailable.
duration: ""
verification_result: passed
completed_at: 2026-03-25T16:29:42.779Z
blocker_discovered: false
---

# T01: Added stable replay anchors to replay issue/goal conclusions with degraded fallback coverage.

**Added stable replay anchors to replay issue/goal conclusions with degraded fallback coverage.**

## What Happened

Started with TDD against the existing replay contract: added focused unit and integration assertions for three anchor paths before changing production code. The new tests first failed because the replay payload exposed `main_issue` and `next_goal` without any deep-link metadata.

Implemented anchor resolution inside `ReplayService.get_replay_data(...)` on the existing authority line. The service now derives a single `replay_anchor` payload from the projection’s normalized messages plus `timeline_markers`, then attaches that payload to both `main_issue` and `next_goal` in the replay response. Resolution prefers the latest matching highlight in the aligned stage, degrades to the stage-change marker when no highlight exists, and keeps `missing_marker` / `no_matching_highlight` states visible instead of silently dropping the target. I also added structured replay logging for anchor status and degraded reasons so downstream debugging can tell whether the page landed on a highlight, fell back to a stage marker, or had no usable marker.

After the first green run, one older unit test still compared the entire `main_issue` and `next_goal` dicts by equality. I updated it to assert the original conclusion fields plus the new anchor metadata, then reran the full focused suite. I also added an explicit missing-marker unit test so the degraded branch is locked, not just implemented implicitly.

Recorded the contract choice in `.gsd/DECISIONS.md` as D064 so T02/T03 can build against the same nested anchor seam instead of inventing a separate resolver.

## Verification

Wrote failing tests first for resolved and degraded replay anchors, confirmed the new assertions failed because `replay_anchor` was absent, then implemented the resolver and reran the focused backend verification command until the full targeted suite passed. Final verification covered unit and integration replay contracts for resolved highlight anchors, degraded stage fallback when no matching highlight exists, degraded missing-marker behavior, and the existing replay/message/highlights access-control and normalization checks.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py` | 0 | ✅ pass | 7700ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/conversation/replay.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_replay_api.py`
- `.gsd/DECISIONS.md`


## Deviations
None.

## Known Issues
None.
