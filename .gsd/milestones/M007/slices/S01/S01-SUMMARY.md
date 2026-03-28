---
id: S01
parent: M007
milestone: M007
provides:
  - Reconnect payloads now carry normalized coach-health truth from the live runtime handler for both classic and StepFun sales sessions.
  - Learner practice pages expose degraded/resumed coach-health near the main controls without interrupting active training.
  - Repo-root focused Vitest commands can target `web/src/...` plan paths without false path failures.
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/sales_bot/websocket/enhanced_handler.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - backend/tests/unit/test_enhanced_handler_coach_health.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/components/practice/CoachHealthNotice.tsx
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/components/practice/RightPanelContent.test.tsx
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - scripts/run-vitest-root.mjs
  - package.json
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Continue treating the live runtime snapshot / websocket `coach_health` payload as the single authority for degraded/resumed truth, with `/knowledge-check` as the inspection surface instead of adding a second polling or read-side authority.
  - Emit `reconnected.restored_state` from a freshly rebuilt live handler snapshot after restore, rather than echoing the raw persisted snapshot back to the client.
  - Render non-healthy coach-health copy through a shared `CoachHealthNotice` so the learner shell and right panel stay on the same message contract while healthy state remains quiet.
patterns_established:
  - Restore persisted realtime state onto the live handler first, then regenerate the outbound reconnect snapshot from that live authority instead of replaying raw stored payloads.
  - For learner-visible runtime warnings, share one presentation helper across page-shell and panel surfaces so copy and quiet-state rules do not drift.
  - Keep repo-root verification shims honest about workspace-relative paths; if the root command delegates into `web/`, normalize `web/src/...` filters there instead of relying on manual command rewrites.
observability_surfaces:
  - `/api/v1/practice/sessions/{id}/knowledge-check` continues to expose live coach-health diagnostics from the active session handler.
  - The learner `/practice/{sessionId}` shell now shows a compact `辅导状态提醒` notice whenever coach health is degraded or resumed.
  - `RightPanelContent` still renders the richer `辅导状态` card for non-healthy runtime states without hiding current stage, score, or action-card guidance.
drill_down_paths:
  - .gsd/milestones/M007/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007/slices/S01/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-28T04:01:01.715Z
blocker_discovered: false
---

# S01: 教练健康状态真相收口

**S01 aligned reconnect emission, learner-page visibility, and live diagnostics on one coach-health authority so degraded/resumed state is visible without interrupting training and reconnect no longer replays stale runtime truth.**

## What Happened

This slice closed the highest-risk truth gap in the realtime coaching loop: reconnect, learner UI, and diagnostics were all talking about coach health, but they were not guaranteed to talk about the same state. T01 hardened the backend/runtime seam by making both StepFun and classic handlers restore persisted runtime state onto the live handler first, then emit `reconnected.restored_state` from a fresh handler snapshot instead of echoing the raw persisted payload. That preserved the intended `healthy -> degraded -> resumed -> healthy` semantics, kept malformed raw payloads from leaking back to the client, and left `/api/v1/practice/sessions/{id}/knowledge-check` on the same live authority line for inspection.

T02 then surfaced that same non-healthy state on the learner route itself. The page shell now mirrors a compact `CoachHealthNotice` above the primary controls, so the learner can see degraded/resumed status without opening the analysis panel, while `RightPanelContent` keeps the richer explanatory card alongside current stage, score, and action-card context. The shared notice component prevents copy drift between shell and panel. In the same task, the repo-root Vitest shim was normalized to strip a leading `web/` prefix before delegating into `web/`, so the planned verification commands now run as written instead of failing on a path mismatch.

The result is a single runtime authority for coach-health truth across reconnect, learner UI, and diagnostics, with focused backend, reducer, and UI verification all green. This slice advances R009 by making realtime coaching degradation/recovery visible and truthful during active practice, but it does not yet retire the same-session practice -> report -> replay live closure proof; S02 still owns that end-to-end authority check.

## Verification

Passed all slice-plan verification checks: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py`, `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_persistence.py -k "restore_session_state"`, `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py -k live_coach_health`, `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts'`, and `npm test -- --run 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'`. Also confirmed the temporary browser sanity check from T02: the learner route rendered on localhost and stayed quiet when no degraded/resumed coach-health message was present.

## Requirements Advanced

- R009 — Made degraded/resumed realtime coaching status truthful and learner-visible during active practice by aligning reconnect emission, learner shell, right-panel copy, and `/knowledge-check` on the same runtime authority.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The slice goal and task scope stayed intact, but the planned repo-root web verification paths needed correction in execution: the root `npm test` shim already runs inside `web/`, so a leading `web/` prefix produced a false `No test files found` failure. T02 fixed that shim structurally instead of continuing to rely on ad hoc command rewrites.

## Known Limitations

This slice stops at focused contract and learner-surface closure; it does not yet provide the same-session live closure proof from active practice through completed report/replay, so R009 remains active until S02/S04 finish that evidence. Focused backend pytest commands still emit the pre-existing coverage noise (`--cov=src` / `No data was collected`) even though the targeted suites pass.

## Follow-ups

S02 should now prove the same coach-health truth line stays coherent when one real localhost sales session moves from `/practice/{sessionId}` into canonical `/practice/{sessionId}/report` and `/practice/{sessionId}/replay`. S03 should absorb the remaining historical M002 remediation artifacts now that the degraded/resumed truth surface has an explicit M007 authority line.

## Files Created/Modified

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Changed StepFun reconnect restore to rehydrate live handler state and emit `reconnected.restored_state` from a freshly rebuilt snapshot instead of replaying the raw persisted payload.
- `backend/src/sales_bot/websocket/enhanced_handler.py` — Applied the same live-handler snapshot rebuild contract to the classic sales handler so degraded/resumed semantics stay aligned across runtimes.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — Added focused restore-state coverage for normalized reconnect payloads, omission-after-recovery behavior, and stale read-side snapshot suppression.
- `backend/tests/unit/test_enhanced_handler_coach_health.py` — Extended classic-handler coverage for reconnect parity and malformed/invalid coach-health payload handling.
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — Locked the `/api/v1/practice/sessions/{id}/knowledge-check` contract to the same live coach-health authority line used by reconnect.
- `web/src/hooks/websocket/message-handlers.test.ts` — Covered reducer behavior for malformed reconnect payload normalization and clearing stale degraded state when restored payloads omit `coach_health` after recovery.
- `web/src/components/practice/CoachHealthNotice.tsx` — Added a shared learner-facing notice renderer for degraded/resumed coach-health copy with a quiet healthy/no-message path.
- `web/src/components/practice/RightPanelContent.tsx` — Kept the richer right-panel coach-status card while reusing the shared notice and preserving stage, score, and action-card context.
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — Surfaced a compact coach-health notice in the learner page shell above the primary controls so degraded/resumed state is visible without opening the analysis panel.
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx` — Added page-shell assertions proving degraded notices render even when the right panel is mocked and healthy/malformed states stay quiet.
- `web/src/components/practice/RightPanelContent.test.tsx` — Added degraded/resumed coverage and verified coach-health copy coexists with active stage and score guidance instead of hiding it.
- `scripts/run-vitest-root.mjs` — Normalized repo-root Vitest filters by stripping a leading `web/` prefix before delegating into the `web/` workspace.
- `package.json` — Pointed the repo-root `npm test` shim at the new path-normalizing Vitest wrapper so planned verification commands execute correctly.
- `.gsd/PROJECT.md` — Updated current-state documentation to reflect that M007/S01 is complete and coach-health truth is now visible on the learner route and reconnect contract.
- `.gsd/KNOWLEDGE.md` — Recorded the reconnect authority rule so future realtime work does not reintroduce raw persisted `coach_health` replay drift.
