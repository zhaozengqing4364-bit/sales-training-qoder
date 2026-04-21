# 2026-04-21 Lane C Practice / Live Session UX Brief

## Scope

Lane C owns `UX-01`, `UX-02`, `UX-03`, `UX-06`, `UX-09`, `UX-12`, and `UX-17` from the full audit remediation plan.

Primary files:

- `web/src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.ts`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`
- `web/src/hooks/use-practice-websocket.ts`
- Co-located tests for the above behavior.

## Phase 0 facts

- Current worktree status before code: clean detached HEAD.
- Worktree dependency state: `web/node_modules` was absent; baseline verification uses an ignored symlink to the leader checkout dependency install at `/Users/zhaozengqing/github/销售训练qoder/web/node_modules`.
- Baseline targeted tests passed before Lane C code changes:
  - `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.test.ts' 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/hooks/use-practice-websocket.test.ts' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' --reporter=dot`
  - Result: 4 files, 49 tests passed.
- Baseline targeted lint passed before Lane C code changes:
  - `pnpm --dir web exec eslint 'src/app/(user)/practice/[sessionId]/use-practice-recording-hotkeys.ts' 'src/app/(user)/practice/[sessionId]/page.tsx' 'src/hooks/use-practice-websocket.ts' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts' --quiet`

## Config governance for this lane

- Stable technical logic may remain in code when it is protocol or browser behavior, but adjustable UX thresholds must be centralized and validated.
- New/used adjustable defaults for this lane:
  - `practice.hotkey.recording_toggle`: default `Space`; validate against a local KeyboardEvent allowlist; invalid disables the hotkey instead of intercepting input/scroll.
  - `practice.autoscroll.bottom_threshold_px`: default `100`; validate `0..500`; fallback to `100`.
  - `practice.session_end.redirect_delay_seconds`: default `5`; validate `0..60`; `0` means immediate navigation.
  - `practice.message_dedupe.window_seconds`: default `300`; validate `30..3600`; fallback to `300`.
- Admin/audit note: the current frontend has no confirmed unified active business-rules settings surface for these practice UX values. This lane will centralize defaults/validation in a route-local config module and keep the admin/back-office persistence hook as a follow-up for Lane F/governance instead of scattering magic numbers.
- Rollback note: each behavior keeps a safe default if config is missing or invalid; no Docker/deploy/ops files are touched.

## Implementation assumptions

- Hotkey behavior should preserve keyboard accessibility without hijacking page scrolling: Space toggles only inside an explicit recording hotkey scope, and editable/scrollable targets keep browser defaults.
- Timer behavior should derive elapsed practice time from an absolute start timestamp, so transport reconnects do not reset or lose elapsed time.
- Recording transition gating should follow actual async start/stop/permission transitions rather than a fixed 300ms dead zone.
- Auto-scroll should only run while the learner is near the bottom or has not intentionally scrolled away.
- AI message dedupe should persist across reconnects within the same session with a bounded time window/LRU.
- Session terminal navigation should expose a short learner-controlled transition before auto-opening the report.
