# S03: Learner error/loading 覆盖与 responsive/a11y/timezone baseline — UAT

**Milestone:** M015
**Written:** 2026-04-11T18:54:01.531Z

# S03 UAT — learner shell fallback + baseline closure

## Preconditions
- Frontend is running with a learner-accessible account.
- Prepare one valid completed learner session ID so `/practice/{sessionId}/report` and `/practice/{sessionId}/replay` can be opened.
- Open browser devtools so network throttling and responsive viewport changes can be applied.

## Test Case 1 — Auth routes show explicit loading and form accessibility baseline
1. In devtools, enable a slow network profile (for example Slow 3G).
2. Open `/login` in a fresh tab or hard-refresh the page.
   - Expected: an explicit learner loading shell appears instead of a blank screen while the route resolves.
3. After the page loads, inspect the form visually and via accessibility tree.
   - Expected: username/email and password inputs have explicit labels; the page is operable without guessing placeholder-only fields.
4. Submit invalid credentials.
   - Expected: the auth error is announced in an alert-style surface instead of only changing subtle inline text.
5. Repeat the slow-refresh check for `/forgot-password` and `/reset-password`.
   - Expected: both routes use the shared auth loading shell, and reset-password still shows a real loading status while token state resolves.

## Test Case 2 — Learner dashboard routes use the shared dashboard loading shell
1. Keep network throttling enabled.
2. Open `/`, `/training`, `/leaderboard`, and `/profile` from the learner shell.
   - Expected: each route uses the shared `(dashboard)/loading.tsx` loader rather than flashing blank content.
3. Switch the browser to a narrow mobile-sized viewport (around 390px wide) and refresh one of those routes.
   - Expected: the dashboard skeleton stacks cleanly without the old edge-aligned header overlap or horizontal overflow.

## Test Case 3 — History/report/replay retain explicit learner loading semantics
1. Open `/history` with throttled network.
   - Expected: the loading state is visible and screen-reader friendly (`status` semantics), not purely decorative.
2. Open `/practice/{sessionId}/report` with throttled network.
   - Expected: the report route shows its loading shell before content arrives; no white screen appears.
3. Open `/practice/{sessionId}/replay` with throttled network.
   - Expected: the replay route shows its loading shell before content arrives; no white screen appears.

## Test Case 4 — Live practice route keeps explicit fallback + error observability seam
1. Open `/practice/{sessionId}` with throttled network.
   - Expected: the dedicated practice loading shell appears while the route resolves.
2. Trigger a practice-route failure in a local debug environment (for example by using the existing focused error test harness or a controlled render throw in the practice route).
   - Expected: the learner error state renders instead of a blank page, and the failure still reports through the tagged durable error seam rather than raw `console.error` only.

## Test Case 5 — Deferred baseline facts remain visible, not silently “fixed”
1. On dashboard home/profile, inspect the narrow-screen layout after the shared loader disappears.
   - Expected: route-shell protection is fixed, but the denser page-level dashboard grids/header layout still remain as known deferred responsive work.
2. On `/history`, `/practice/{sessionId}/report`, and `/practice/{sessionId}/replay`, inspect timestamps.
   - Expected: timestamps still follow browser-local `toLocaleString("zh-CN")` formatting. This is a recorded baseline fact for future product work, not a regression introduced by S03.
3. Open `/support/runtime` as a support/admin user if available.
   - Expected: that route is not part of learner-shell closure; do not treat its shell behavior as S03 learner coverage drift.
