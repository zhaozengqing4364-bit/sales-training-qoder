# S03: S03: Frontend domain client 与 transport seam 抽离 — UAT

**Milestone:** M019
**Written:** 2026-04-13T04:54:27.977Z

# S03 UAT — Frontend domain client 与 transport seam 抽离

## Preconditions
- Web app is running with the current branch.
- A learner account exists and can log in.
- At least one agent/persona-backed sales session can be created.
- At least one completed practice session exists for report/replay checks.
- Browser starts from a clean tab with normal network conditions.

## Test Case 1 — Auth + dashboard still use the outward API façade
1. Open `/login`.
   - **Expected:** The login form renders normally, forgot-password entry is visible, and no page-level crash or raw API payload leak appears.
2. Sign in with a valid learner account.
   - **Expected:** Navigation succeeds without needing page-local fetch logic changes.
3. Land on `/` (dashboard) and refresh once.
   - **Expected:** The dashboard still renders the current user display name and version badge; reload continues to work through the shared `api` façade/auth seam.
4. Trigger a known empty/degraded dashboard state if available (for example no recent sessions).
   - **Expected:** The page stays on the current dashboard contract instead of breaking because a page reached into a hidden domain module.

## Test Case 2 — Live practice page still depends on `usePracticeWebSocket()` as the outward transport contract
1. Start a new sales practice session and open `/practice/{sessionId}`.
   - **Expected:** The live shell loads, the session connects automatically, and there is no need for page-local websocket bootstrapping.
2. Send or speak one learner turn so the session has live transcript/audio activity.
   - **Expected:** The page receives updates normally through the hook contract.
3. While AI audio or transcript output is in progress, trigger the interrupt action.
   - **Expected:** Playback stops, any visible interim transcript clears, and stale learner text does not reappear a moment later from a delayed throttle callback.
4. Simulate a transient transport interruption if available.
   - **Expected:** The UI distinguishes `reconnecting` from `failed`; automatic recovery does not immediately surface the manual reconnect CTA.

## Test Case 3 — Report and replay still load through the extracted session domain builder
1. Open `/practice/{completedSessionId}/report`.
   - **Expected:** The report renders on the existing route contract with no page-level fetch regressions.
2. From the same completed session, open `/practice/{completedSessionId}/replay`.
   - **Expected:** Replay content loads successfully on the canonical replay route.
3. Refresh directly on the replay page.
   - **Expected:** Replay still hydrates correctly, proving the extracted `sessions` domain did not break direct-entry reads.

## Test Case 4 — Edge cases stay explicit instead of leaking seam drift into pages
1. Open `/practice/{notCompletedSessionId}/replay` for a session that is still scoring / not completed.
   - **Expected:** The page shows the existing explicit blocked message instead of crashing or silently misloading.
2. Force or wait for a websocket close reason that maps to a user-facing transport error.
   - **Expected:** The close reason is classified by the transport seam; reconnect/backoff behavior remains bounded and understandable.
3. Reopen login/report/replay after the above transport exercise.
   - **Expected:** Auth, report, and replay continue to behave through the outward `api` façade; no page was forced to compensate for the seam refactor.

## Exit Criteria
- Auth, dashboard, live practice, report, and replay all behave through the same outward contracts as before the slice.
- Interrupt no longer leaves a stale interim transcript behind.
- Any regression can be traced to one of the named seams (`client.ts`, `client-domains.ts`, `use-practice-websocket.ts`, `websocket/transport.ts`, `message-handlers.ts`) rather than a page-local workaround.
