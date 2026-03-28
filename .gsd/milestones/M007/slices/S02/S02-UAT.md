# S02: 同 session 结论同源收口 — UAT

**Milestone:** M007
**Written:** 2026-03-28T09:20:12.455Z

# S02: 同 session 结论同源收口 — UAT

**Milestone:** M007
**Written:** 2026-03-28

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: this slice changes both code-level authority seams (runtime diagnostics, websocket reducer, report/replay parity) and a live localhost route-family proof. Focused backend/web suites prove the contract edges; the localhost session proof proves the user-visible route family and preserves the remaining blocker truthfully.

## Preconditions

- Backend is reachable on `http://localhost:3444` and web is reachable on `http://localhost:3445`.
- Frontend and backend use the same loopback host (`localhost` ↔ `localhost`) so auth cookies stay aligned.
- Run `POST /api/v1/auth/dev-login` once before opening protected routes.
- Have either a fresh StepFun sales practice session or the recorded proof session referenced in `.artifacts/m007-s02-same-session/session-proof.md`.
- Focused verification suites are runnable from repo root:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py`
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py`
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k 'knowledge_check or replay or report'`
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py`
  - `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'`
  - `npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`

## Smoke Test

1. Run the focused backend/web verification commands above from repo root.
2. Open a same-session sales report route.
3. **Expected:** all focused suites pass; the report page shows `训练评估报告`, `主张证据状态`, `销售推进结果`, and `下一轮销售目标` on the same session.

## Test Cases

### 1. Active runtime and `/knowledge-check` share one live conclusion contract

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py`.
2. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py`.
3. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k 'knowledge_check or replay or report'`.
4. **Expected:** StepFun, classic, and `/knowledge-check` tests all pass; active-session live summary wins while a handler is live, malformed partial summaries fail soft instead of reviving stale completed-session conclusions, and claim-truth stays distinct from unrelated diagnostics.

### 2. Learner `/practice/{sessionId}` renders the stable same-session cue from websocket authority

1. Run `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'`.
2. Open a live sales practice session on `/practice/{sessionId}`.
3. Drive at least one real turn through the page websocket so a `score_update.data.live_session_summary` is emitted.
4. **Expected:** the learner route renders a stable same-session cue (`当前同 session 结论` plus main issue / next goal / claim-truth wording) sourced from backend payload fields; final-transcript cleanup clears only transient `actionCard` / `fuzzyDetections`, not the stable cue.

### 3. Canonical report remains authoritative while replay is still locked

1. End the same session through the existing lifecycle path.
2. Open `/practice/{sessionId}/report`.
3. Open `/practice/{sessionId}/replay` before the session is completed.
4. **Expected:** the report page still shows canonical issue/goal/claim-truth copy on that same session; replay returns the explicit `[SESSION_NOT_COMPLETED] Session must be completed for replay. Current status: ...` failure instead of fabricating replay content.

### 4. Completed-session report/replay parity stays on one projection family

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py`.
2. Run `npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`.
3. **Expected:** backend tests prove report is readable during scoring and replay matches the same canonical issue/goal/claim-truth family after unlock; frontend tests prove replay-only `replay_anchor` remains present but does not mutate the underlying conclusion authority.

## Edge Cases

### Missing or partial live summary payload

1. Feed a `score_update` without `live_session_summary`, or with only part of the summary object populated.
2. **Expected:** the learner reducer clears the stable cue instead of keeping a stale prior-turn issue/goal/claim-truth conclusion.

### Replay still locked while report is readable

1. Use the localhost proof session flow from `.artifacts/m007-s02-same-session/session-proof.md`.
2. End the StepFun session, wait for the report route to open, then retry replay.
3. **Expected:** if the backend still wedges in `status="scoring"`, report remains readable from the projection while replay continues returning `[SESSION_NOT_COMPLETED]`; this is recorded as the known blocker rather than treated as frontend drift.

### Optional enhancement noise on report

1. Load the canonical report route for the proof session.
2. Observe any 404/500 noise from optional enhanced-report/highlight endpoints.
3. **Expected:** the canonical report body still shows the unified issue/goal/claim-truth sections; optional enhancement failures are visible diagnostics but do not invalidate the core same-session conclusion contract.

## Failure Signals

- Learner `/practice/{sessionId}` re-derives issue/goal wording from stage text or action-card copy instead of rendering the backend `live_session_summary` fields.
- `/knowledge-check` shows stale completed-session conclusions while a live handler is active.
- Report and replay disagree on issue family / goal family after stripping replay-only `replay_anchor` data.
- Replay becomes available before completion, or report loses its canonical evidence sections while replay is still blocked.
- On localhost, a StepFun session ends with `status="scoring"`, replay remains `[SESSION_NOT_COMPLETED]`, and backend logs show `report_generation_failed [NO_STAGE_RESULTS]`.

## Requirements Proved By This UAT

- R009 — proves same-session coaching conclusions now stay on one vocabulary from live runtime through learner UI and canonical report/replay parity tests, while the remaining gap is an explicit completion wedge rather than semantic drift.

## Not Proven By This UAT

- A fresh localhost StepFun session reaching `/practice/{id}/replay` after completion. The current shipped terminal path can still wedge in `status="scoring"` after end.
- Legacy raw-microphone ASR proof on this machine. Local streaming ASR is environment-broken (`torch._C`), so that path is not treated as a product acceptance signal here.

## Notes for Tester

- Keep frontend/backend hosts aligned (`localhost` ↔ `localhost`) during live proof; mixed loopback hosts create false 401 regressions.
- If the report page shows optional enhanced-report or highlight failures but still renders `训练评估报告`, `主张证据状态`, `销售推进结果`, and `下一轮销售目标`, treat that as non-blocking noise unless the canonical family itself drifts.
- The durable live-proof reference for this slice is `.artifacts/m007-s02-same-session/session-proof.md`; use it when comparing future behavior against the current blocker.
