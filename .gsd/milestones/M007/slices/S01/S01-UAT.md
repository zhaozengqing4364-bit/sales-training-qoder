# S01: 教练健康状态真相收口 — UAT

**Milestone:** M007
**Written:** 2026-03-28T04:01:01.715Z

# S01 UAT — 教练健康状态真相收口

## Preconditions
- Backend is running with the current sales realtime handlers enabled.
- Web app is running from the repo-root test shim or the normal learner route, and frontend/backend use the same loopback host.
- A dev/test user can open the learner route `/practice/{sessionId}`.
- Repo root commands are executed from `/Users/zhaozengqing/github/销售训练qoder`.

## Test Case 1 — Reconnect restores normalized coach-health instead of replaying stale raw snapshots
1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_persistence.py -k "restore_session_state"`.
2. Confirm the selected restore-state tests pass.
3. Review the assertions covered by that suite.

**Expected outcomes**
- Reconnect emits `reconnected.restored_state` from the rebuilt live handler snapshot, not the raw persisted payload.
- Malformed persisted `coach_health.status` values do not leak back to the client as bogus runtime truth.
- If recovered state omits `coach_health`, stale degraded state is cleared instead of lingering after recovery.
- Legacy stale read-side fields such as raw action-card remnants are not replayed as reconnect truth.

## Test Case 2 — Classic handler follows the same coach-health reconnect contract
1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py`.
2. Confirm the focused classic-handler suite passes.
3. Verify the suite covers degraded, resumed, malformed-payload, and recovery-clears-state behavior.

**Expected outcomes**
- Classic reconnect handling matches the StepFun contract for degraded/resumed coach-health.
- Invalid or malformed `coach_health` input is normalized or ignored instead of crashing the handler.
- Reconnect does not silently report healthy state before the live handler has rebuilt it.

## Test Case 3 — `/knowledge-check` still exposes the same live coach-health authority
1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py -k live_coach_health`.
2. Confirm the integration test passes.

**Expected outcomes**
- `GET /api/v1/practice/sessions/{id}/knowledge-check` reads live coach-health diagnostics from the registered session handler.
- A degraded runtime state is exposed with the same coach-health shape expected by the learner runtime flow.
- No extra polling/read-side authority is introduced just to render degraded/resumed state.

## Test Case 4 — Learner shell shows degraded status without opening the analysis panel
1. Run `npm test -- --run 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'`.
2. Confirm both files pass.
3. Inspect the assertions covered by `page.test.tsx`.

**Expected outcomes**
- The learner page shell renders `辅导状态提醒` when `coachHealth.status="degraded"` and `message="实时辅导暂不可用，训练仍可继续。"`.
- The page-level degraded notice still renders even when `RightPanelContent` is mocked, proving the shell itself owns the visibility requirement.
- Healthy state and malformed/no-message non-healthy payloads stay quiet; the shell does not show a warning banner for `healthy` or message-less payloads.

## Test Case 5 — Right panel keeps richer guidance visible while showing degraded/resumed coach-health
1. Reuse the command from Test Case 4 and inspect the assertions covered by `RightPanelContent.test.tsx`.
2. Verify degraded and resumed coach-health states.

**Expected outcomes**
- `辅导状态` appears with `实时辅导暂不可用，训练仍可继续。` for degraded state.
- `辅导状态` appears with `实时辅导已恢复，后续建议会继续更新。` for resumed state.
- `当前阶段` and `销售维度得分` remain visible while coach-health notices render.
- When an `action_card` is present, it remains the only primary textual coach surface; coach-health does not replace or duplicate the active guidance contract.

## Test Case 6 — Repo-root Vitest shim accepts planned `web/src/...` filters
1. From repo root, run `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts'`.
2. Confirm the suite executes and passes instead of failing with `No test files found`.
3. Optionally rerun `npm test -- --run 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'` to confirm the same behavior on multi-file filters.

**Expected outcomes**
- The repo-root shim strips the leading `web/` prefix and forwards valid `src/...` filters into the `web/` workspace.
- The reducer suite runs and passes, covering malformed reconnect normalization and omission-after-recovery behavior.
- Slice-plan verification commands now execute as written from repo root.

## Edge Checks
- Degraded state should be visible in both the page shell and right panel when a non-healthy message is present.
- Resumed state should be visible in the right panel with the recovery message and should not leave stale degraded state behind after reconnect.
- Healthy state must remain quiet on the learner shell; there should be no distracting success banner such as `实时辅导正常。`.
- Missing-message non-healthy payloads should fail safe by staying quiet rather than rendering partial or misleading coach-health UI.
- No browser/runtime path in this slice should require a second fetch loop or polling surface just to decide whether coaching is degraded or resumed.
