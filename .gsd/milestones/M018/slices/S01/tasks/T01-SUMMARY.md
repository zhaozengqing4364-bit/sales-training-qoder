---
id: T01
parent: S01
milestone: M018
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/common/analytics/history_service.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/admin/api/training_records.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D203 — keep the M018 DB performance baseline in code-adjacent inventories and grade confirmed query-shape facts separately from unproved index ideas.
duration: 
verification_result: passed
completed_at: 2026-04-11T22:32:02.673Z
blocker_discovered: false
---

# T01: Added code-adjacent DB hotspot inventories for admin analytics, history/projection, and admin training records.

**Added code-adjacent DB hotspot inventories for admin analytics, history/projection, and admin training records.**

## What Happened

I mapped the live analytics/history/admin/projection read paths from the planner’s target files, then encoded the first-round DB performance baseline directly beside the authority seams instead of leaving it as an ad-hoc grep result. In `backend/src/common/analytics/admin_analytics_service.py` I recorded that the admin analytics endpoints share one repeated bulk projection-window loader and that `/admin/analytics/export` fans out into multiple independent full-window rebuilds; this is a confirmed query-fanout hotspot, while any index work still needs real Postgres evidence. In `backend/src/common/analytics/history_service.py` I captured the user-history/progress pattern as a batched session window plus one grouped message fetch — not a classical DB N+1, but still a large repeated session/message replay seam, especially when manager intervention overlays trigger a second full reload. In `backend/src/common/conversation/session_evidence.py` I documented the per-session projection path as a single-session message fan-in seam whose main cost is rebuilding the projection over full message lists, with the timestamp-extension index remaining only a hypothesis until EXPLAIN proves it. In `backend/src/admin/api/training_records.py` I locked the one confirmed row-level N+1 in this task: `session_to_response()` can issue up to two extra SELECTs per row for agent/persona metadata after the page query already completed. I also saved D203 to record that M018’s DB baseline should stay in code-adjacent inventories and explicitly grade confirmed query-shape facts separately from unproved index ideas, then appended the matching handoff note to `.gsd/KNOWLEDGE.md` and updated the safe-grow continuity files for the next task.

## Verification

Ran the exact task-plan verification command `rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api`, which now surfaces the new code-adjacent inventory constants alongside the underlying query shapes they describe. Ran fresh LSP diagnostics on `backend/src/common/analytics/admin_analytics_service.py`, `backend/src/common/analytics/history_service.py`, `backend/src/common/conversation/session_evidence.py`, and `backend/src/admin/api/training_records.py`; all returned clean. Also sanity-checked `.codex/loop/state.json` with `python3` JSON parsing after updating continuity metadata. Slice-level note: this intermediate task completed the discovery inventory baseline only; the focused analytics pytest proof and evidence-backed ranking work remain for T02/T03.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api` | 0 | ✅ pass | 140ms |
| 2 | `lsp diagnostics backend/src/common/analytics/admin_analytics_service.py` | 0 | ✅ pass | 60ms |
| 3 | `lsp diagnostics backend/src/common/analytics/history_service.py` | 0 | ✅ pass | 58ms |
| 4 | `lsp diagnostics backend/src/common/conversation/session_evidence.py` | 0 | ✅ pass | 55ms |
| 5 | `lsp diagnostics backend/src/admin/api/training_records.py` | 0 | ✅ pass | 52ms |
| 6 | `python3 - <<'PY'
import json
from pathlib import Path
json.loads(Path('.codex/loop/state.json').read_text())
print('state.json OK')
PY` | 0 | ✅ pass | 47ms |

## Deviations

Used four authority files instead of only the planner’s minimal three-file estimate so the baseline could capture one confirmed admin N+1 seam (`training_records.py`) in addition to the shared analytics/history/projection loaders. This stayed within the slice contract and did not change task scope.

## Known Issues

Index priority is still intentionally unproved at this stage. The inventories mark composite-index and search-index ideas as candidates only; T02 still needs real Postgres/runtime evidence before any of them should become implementation work.

## Files Created/Modified

- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/admin/api/training_records.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
