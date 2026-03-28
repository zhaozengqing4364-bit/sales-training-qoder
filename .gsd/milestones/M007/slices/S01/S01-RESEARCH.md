# S01 Research — 教练健康状态真相收口

## Summary

- **Active requirement focus:** `R009` is the direct owner for this slice. The work is not “add more coaching”; it is to make the existing realtime coaching truthfully visible and reconnect-safe on the current learner route.
- The codebase already has a real **coach-health state machine** (`healthy -> degraded -> resumed -> healthy`) in both sales runtime implementations:
  - `backend/src/sales_bot/websocket/components/capability_processor.py`
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `backend/src/sales_bot/websocket/enhanced_handler.py`
- The learner UI already has a **non-blocking coach-health presentation** in `web/src/components/practice/RightPanelContent.tsx`, but it is only guaranteed visible where that panel is visible. On mobile it is hidden inside the bottom sheet until the learner opens it.
- Reconnect truth currently depends on the **persisted runtime snapshot** sent through `reconnected -> restored_state.runtime_state.coach_health`. If that field is omitted, the frontend deliberately resets to `healthy`.
- The **completed-session conclusion seam is already centralized and should be treated as protected** in S01:
  - `backend/src/common/conversation/session_evidence.py`
  - `backend/src/common/api/practice.py` (`/practice/sessions/{id}/report`)
  - `backend/src/common/conversation/replay.py`
  - `web/src/lib/session-evidence.ts`
  - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- Recommendation: make S01 about **live runtime truth + learner visibility**, not about recomputing report/replay conclusions.

## Requirement Focus

- **R009 (active, owner:M007/S01):** current session should provide useful realtime coaching during training. For S01, that means the learner can tell whether coaching is healthy, degraded, or resumed **without the training loop stopping** and without reconnect making the state lie.
- This slice also protects already-validated continuity/failure-visibility behavior (`R001`, `R002`, `R011`) by ensuring degradation is explicit rather than silently swallowed.

## Skills Discovered

- **Loaded skills used for research guidance**
  - `fastapi-python`
  - `react-best-practices`
- **Newly discovered and installed**
  - `jeffallan/claude-skills@websocket-engineer` via `npx skills add ... -g -y`
  - It did not become available inside the current prompt’s skill list yet, so it could not be invoked in this unit. It should be available to later units after skill refresh.

## Recommendation

1. **Keep coach health single-sourced from handler runtime state.**
   The backend already has the authority object (`status`, `reason`, `message`) and already persists/restores it through session snapshots. S01 should preserve that instead of inventing a second frontend-only derivation.
2. **Do not lead with `/knowledge-check` as the primary learner-state source.**
   `GET /api/v1/practice/sessions/{id}/knowledge-check` already surfaces `coach_health`, but the learner practice page does not currently use it. Per the React best-practices skill, avoid introducing a new client waterfall/polling loop unless websocket truth proves insufficient. If a REST fallback is needed, make it **one-shot** on page boot/reconnect, not a polling authority.
3. **Make visibility explicit on the page shell, not only inside the analysis panel, if the product bar is “explicitly visible”.**
   The existing badge in `RightPanelContent` is already non-blocking and visually appropriate. The likely smallest truthful UI change is a compact page-level strip/chip near the main controls that mirrors the same `coachHealth` object, while keeping the richer explanation in the right panel.
4. **Treat report/replay/session-evidence as a protected seam in this slice.**
   S01 should not change alignment logic unless the live runtime truth fix exposes an actual drift bug. That completed-session seam is already established and already backed by contract tests.
5. **If frontend starts consuming richer runtime diagnostics, extend typed contracts first.**
   The FastAPI skill pushes toward typed surfaces over ad hoc dict access. `web/src/lib/api/types.ts` currently defines `KnowledgeCheckDiagnostics` without the `coach_health*` fields that the backend already returns.

## Implementation Landscape

### 1) Backend runtime-truth authority

- `backend/src/sales_bot/websocket/components/capability_processor.py`
  - Legacy/enhanced sales capability pipeline.
  - Emits `coach_health_update` when scoring/fuzzy pipeline fails or resumes.
  - Message text is already product-ready:
    - degraded: `实时辅导暂不可用，训练仍可继续。`
    - resumed: `实时辅导已恢复，后续建议会继续更新。`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - StepFun runtime authority for current realtime sales route.
  - `_create_state_snapshot()` persists reconnect-safe runtime fields, including `coach_health` when state is not healthy.
  - `_restore_session_state()` restores `coach_health`, `_feedback_pacing_state`, latest score snapshot, objection ledger, then emits `reconnected`.
  - `get_runtime_diagnostics()` returns `claim_truth` + `coach_health` for live readers.
- `backend/src/sales_bot/websocket/enhanced_handler.py`
  - Legacy/classic runtime still follows the same coach-health contract.
  - Same snapshot/restore shape for `coach_health`.
- `backend/src/common/websocket/base_handler.py`
  - `_send_reconnection_success()` sends the raw `SessionStateSnapshot.to_dict()` under `reconnected.data.restored_state`.
  - Any reconnect truth change must still fit this shape.
- `backend/src/common/api/practice.py`
  - `GET /practice/sessions/{id}/knowledge-check` reads live handler diagnostics through `SessionManager` and includes `coach_health` in the response.
- `backend/src/common/conversation/runtime_diagnostics.py`
  - Shared normalizer for knowledge-check/support readers.
  - Already normalizes `coach_health`, `coach_health_status`, `coach_health_reason`, `coach_health_summary`.

### 2) Frontend live surfaces

- `web/src/hooks/websocket/types.ts`
  - `CoachHealth` type already exists with `healthy | degraded | resumed`.
  - Initial state defaults to `healthy`.
- `web/src/hooks/websocket/message-handlers.ts`
  - `normalizeCoachHealth()` is the sole frontend normalizer for websocket payloads.
  - `coach_health_update` updates state directly.
  - `status` can also carry `coach_health`.
  - `reconnected` restores `restored_state.runtime_state.coach_health`.
  - **Important behavior:** if reconnect snapshot omits `coach_health`, frontend resets to normalized healthy state.
- `web/src/components/practice/RightPanelContent.tsx`
  - Already renders a non-blocking degraded/resumed card for sales mode.
  - This is the current learner-facing surface.
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
  - Wires `coachHealth` into `RightPanelContent` for desktop side panel and mobile bottom sheet.
  - The main conversation/control column does **not** currently show coach health.
- `web/src/lib/api/client.ts`
  - `api.sessions.getKnowledgeCheck(sessionId)` already exists.
- `web/src/lib/api/types.ts`
  - `KnowledgeCheckDiagnostics` currently omits backend-returned `coach_health`, `coach_health_status`, `coach_health_reason`, `coach_health_summary`.

### 3) Protected completed-session seam

These files are already the same-family authority for `main_issue` / `next_goal` / `claim_truth` and should stay stable during S01 unless a real defect is uncovered:

- `backend/src/common/conversation/session_evidence.py`
  - `build_projection()` and `_resolve_sales_projection_alignment()` are the read-side authority.
  - It explicitly walks backward through persisted score snapshots until it finds one where `resolve_sales_report_alignment(...)` can truly align.
- `backend/src/common/effectiveness/evaluator.py`
  - `resolve_sales_report_alignment(...)` is the canonical mapping from stage + score evidence to `main_issue`, `next_goal`, and `claim_truth`.
- `backend/src/common/api/practice.py`
  - `/practice/sessions/{id}/report` reads projection output.
- `backend/src/common/conversation/replay.py`
  - Replay reads the same projection and only adds `replay_anchor` metadata.
- `web/src/lib/session-evidence.ts`
  - Shared frontend labels/helpers for issue/goal/claim-truth families.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`

### 4) Existing test coverage

**Backend, coach-health specific**
- `backend/tests/unit/test_capability_processor.py`
  - degraded when capability pipeline fails
  - resumed after next successful turn
- `backend/tests/unit/test_stepfun_realtime_handler.py`
  - degraded/resumed behavior on StepFun realtime path
- `backend/tests/unit/test_enhanced_handler_coach_health.py`
  - classic/enhanced snapshot persistence + restore
- `backend/tests/unit/test_stepfun_realtime_persistence.py`
  - reconnect-safe StepFun runtime subset restoration
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`
  - `/knowledge-check` exposes live `coach_health`

**Frontend, coach-health specific**
- `web/src/components/practice/RightPanelContent.test.tsx`
  - degraded/resumed card renders without hiding stage/score guidance
- `web/src/hooks/websocket/message-handlers.test.ts`
  - degraded/resumed websocket events
  - reconnect restore behavior

**Protected same-session evidence contracts**
- `backend/tests/contract/test_practice_evidence_contract.py`
  - report/replay same-family assertions for `main_issue`, `next_goal`, `claim_truth`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Forward Intelligence / Watchouts

1. **Mobile visibility is currently weaker than desktop visibility.**
   `coachHealth` is only rendered inside `RightPanelContent`. On mobile that means it is hidden inside `GlassSheet` until the learner opens the analysis panel. If “explicitly visible” means “learner sees it during practice without extra action”, S01 likely needs a page-level surface.

2. **Reconnect omission currently means “healthy”.**
   `web/src/hooks/websocket/message-handlers.ts` intentionally resets to healthy when `restored_state.runtime_state.coach_health` is absent. That is only truthful if the backend reliably persists non-healthy and resumed states whenever they matter. If the observed bug is “reconnect says healthy too early”, fix the backend omission/restore contract first.

3. **The frontend typed contract is behind the backend diagnostics contract.**
   `KnowledgeCheckDiagnostics` in `web/src/lib/api/types.ts` does not include coach-health fields, even though the backend returns them. If planners choose a REST fallback or diagnostic display on the learner page, this type must move first.

4. **`PracticeSessionPage` tests currently mock out `RightPanelContent`.**
   `web/src/app/(user)/practice/[sessionId]/page.test.tsx` cannot catch learner-page visibility regressions for coach health today. If S01 adds a page-shell chip/banner, this test file becomes part of the acceptance pack.

5. **There is stale reconnect-test gravity in the backend.**
   `backend/tests/integration/test_sales_realtime_reconnect_flow.py` still asserts `latest_action_card` persistence, which conflicts with the project knowledge that reconnect snapshots should keep only minimal pacing state. Do not treat that test as the authority seam for S01 planning; prefer `backend/tests/unit/test_stepfun_realtime_persistence.py` plus the project knowledge entry.

6. **Avoid creating a second authority for live truth.**
   The backend already exposes coach health through websocket events, reconnect snapshots, and `/knowledge-check`. S01 should keep one semantic object and fan it out, not derive “frontend-only resumed/degraded” from unrelated heuristics.

## What To Build Or Prove First

1. **Lock the reconnect truth contract first.**
   Confirm exactly when `coach_health` is persisted/restored for both StepFun and classic handlers, and align frontend reconnect expectations around that. This retires the highest-risk “UI lies after reconnect” failure mode.

2. **Then decide the learner visibility surface.**
   If existing right-panel visibility is insufficient for the slice acceptance, add a small page-shell indicator driven by the same `coachHealth` object. Keep it informational and non-blocking.

3. **Only then add any REST fallback/diagnostic reuse.**
   If websocket truth alone is enough, skip extra fetching. If not, reuse `/knowledge-check` once on boot/reconnect and extend typed contracts instead of inventing a new endpoint.

4. **Leave report/replay alignment untouched unless runtime work exposes a real mismatch.**
   The planner should treat same-family conclusion logic as already-owned by S02/Sexisting contracts, not as the first move in S01.

## Verification

Run backend suites **sequentially**; this repo’s pytest/cov setup is noisy when parallelized.

### Focused backend verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_capability_processor.py -k "coach_health"`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py -k "coach_health"`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_persistence.py -k "restore_session_state"`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py -k "live_coach_health"`

### Focused frontend verification

- `npm test -- --run "web/src/components/practice/RightPanelContent.test.tsx"`
- `npm test -- --run "web/src/hooks/websocket/message-handlers.test.ts"`
- If the page shell changes: `npm test -- --run "web/src/app/(user)/practice/[sessionId]/page.test.tsx"`

### Slice-level live/UAT note

- Current codebase already has the right runtime primitives, but there is **no obvious built-in fault toggle** for “force coach degraded/resumed in localhost UI” on the learner page.
- If later execution requires browser proof on localhost, keep both frontend and backend on the same loopback host (`localhost` with `localhost`, or `127.0.0.1` with `127.0.0.1`) per project knowledge, and prefer proving the websocket/reconnect truth path rather than mocking a second authority.
- Usual local ports in this repo are backend `:3444` and web `:3445`.
