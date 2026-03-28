# S06: scoring 收口与 replay/highlights 解锁 — UAT

**Milestone:** M003
**Written:** 2026-03-27T13:12:27.131Z

# S06: scoring 收口与 replay/highlights 解锁 — UAT

**Milestone:** M003
**Written:** 2026-03-27T21:00:00+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S06 is a status-boundary slice. Acceptance requires both focused backend proof and one live same-session localhost route proof showing that the exact session moves from immediate `scoring` to background-finalized `completed`, then unlocks report/replay/highlights on the current learner surfaces.

## Preconditions

- Backend is running locally on `http://localhost:3444`.
- Web is running locally on `http://localhost:3445`.
- Frontend and backend use the same host (`localhost` with `localhost`).
- Browser session is dev-logged-in via `POST http://localhost:3444/api/v1/auth/dev-login`.
- Published sales agent `dee4a877-2f19-47f4-a326-954f2ab554d5` (`语言的魅力`) and linked active persona `348d955b-da04-4431-9421-2f7f2bbb5271` (`客户1`) are available.
- Fresh proof session: `6a9e45d7-c15a-43c6-95cf-59583918780a`.

## Smoke Test

1. Create a fresh sales session on the live API.
2. Open `/practice/{sessionId}` and confirm the learner route loads.
3. End the session through the real lifecycle API and confirm the immediate response still returns `status="scoring"`.
4. Run the background finalization seam with optional enhanced-report generation forced to fail.
5. Load canonical report, replay, and highlights for that same session.
6. **Expected:** report/replay/highlights all unlock on the same session after finalization, while a true unfinished session would still be blocked.

## Test Cases

### 1. Immediate lifecycle end response still returns `scoring`

1. Create a fresh sales session on `POST /api/v1/practice/sessions`.
2. Open `/practice/{sessionId}` and allow the learner route to initialize.
3. End the session through `POST /api/v1/practice/sessions/{id}/lifecycle` with `{ "action": "end" }`.
4. **Expected:** the live response body still returns `status="scoring"` and does not change the shipped sales terminal contract.

### 2. Background finalization promotes the same session to `completed`

1. Seed canonical same-session evidence on the fresh session (messages, session scores, effectiveness snapshot).
2. Read the persisted `PracticeSession` row before finalization.
3. Execute the background report/finalization seam on that same session while forcing optional enhanced-report generation to fail.
4. Read the same `PracticeSession` row again.
5. **Expected:** `status` changes from `scoring` to `completed`, while `report_status` may remain `failed` with `[ENHANCED_REPORT_FAILED]`.

### 3. Canonical report, replay, and highlights unlock on the same session

1. After finalization, request:
   - `GET /api/v1/practice/sessions/{id}/report`
   - `GET /api/v1/sessions/{id}/replay`
   - `GET /api/v1/sessions/{id}/highlights`
2. Open `/practice/{sessionId}/report` in the browser.
3. Open `/practice/{sessionId}/replay` in the browser.
4. **Expected:** all three live APIs return 200 for the same session, report/replay pages render the same-session evidence line, and replay no longer falls back to `[SESSION_NOT_COMPLETED]` / `统一训练证据不可用`.

### 4. True unfinished sessions remain blocked

1. Re-run the focused backend contract/integration checks for an `in_progress` sales session.
2. Request replay/highlights for that unfinished session.
3. **Expected:** the APIs still return `[SESSION_NOT_COMPLETED]`; S06 must not relax the gate for generic scoring/in-progress sessions.

## Edge Cases

### Optional enhanced-report failure does not prevent canonical finalization

1. Trigger background finalization with a report service that returns `Result.fail("[ENHANCED_REPORT_FAILED]")`.
2. Inspect the final persisted session status plus canonical report/replay/highlights responses.
3. **Expected:** `report_status` can stay `failed`, but canonical report/replay/highlights still unlock once projection-backed same-session evidence is readable.

### Browser report keeps optional enhanced-report noise isolated

1. Open `/practice/{sessionId}/report` after finalization.
2. Observe browser logs and network requests.
3. **Expected:** optional enhanced-report endpoints may still 404/500 with `[REPORT_NOT_FOUND]` / `[REPORT_GENERATION_FAILED]`, but the canonical report body remains readable and the same-session replay/highlights contract is already unlocked.

## Failure Signals

- `POST /lifecycle end` starts returning `completed` for sales sessions immediately.
- Background finalization leaves a replay-ready same-session stuck at `status="scoring"`.
- Replay/highlights start admitting generic scoring/in-progress sessions instead of only finalized ones.
- Replay page still shows `统一训练证据不可用` for a session whose persisted status is already `completed` and whose replay API returns 200.
- Canonical replay/highlights depend on optional enhanced-report success instead of the projection-backed evidence line.

## Requirements Proved By This UAT

- R010 — proved the accepted same-session sales chain can now cross the final status boundary and unlock report/replay/highlights on current routes without weakening the unfinished-session gate.

## Not Proven By This UAT

- A fresh live admin Persona/knowledge mutation in the same browser session; S05 remains the slice that proved that upstream edit path.
- Healthy optional enhanced-report generation on the localhost proof path.

## Notes for Tester

- Keep frontend and backend on the same loopback host.
- For this slice, the decisive proof is the state boundary on the exact same session: immediate end response, persisted row before finalization, persisted row after finalization, then live report/replay/highlights/browser routes.
- Treat optional enhanced-report 404/500 noise separately from canonical replay/highlights availability.
