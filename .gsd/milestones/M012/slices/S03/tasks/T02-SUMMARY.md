---
id: T02
parent: S03
milestone: M012
provides: []
requires: []
affects: []
key_files: ["web/src/hooks/use-voice-speed-preference.ts", "web/src/hooks/use-voice-speed-preference.test.ts", "web/src/app/(dashboard)/profile/page.tsx", "web/src/app/(dashboard)/profile/page.test.tsx", "web/src/hooks/use-practice-websocket.ts", "web/src/hooks/use-streaming-audio-player.ts", "web/src/hooks/use-streaming-audio-player.test.ts"]
key_decisions: ["Kept voice speed frontend-owned and truthful by removing the fake profile PATCH and centralizing normalization plus persistence in one shared hook.", "Applied the normalized playback rate inside useStreamingAudioPlayer so MediaSource HTMLAudioElement, fallback Audio, and PCM Web Audio consume the same authority seam."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh task-level verification passed with npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts" "src/hooks/use-streaming-audio-player.test.ts" (13/13 tests green). The focused suite confirmed malformed storage values normalize to 1.0x, the profile page hydrates/persists the select via the shared seam without calling the fake PATCH, and MediaSource/fallback Audio/PCM playback all receive the configured rate. A browser smoke attempt against http://localhost:3445/profile timed out while the local Next dev server remained on 'Compiling instrumentation Node.js ...', so browser verification was inconclusive in this environment and is documented as a known issue rather than reported as a pass."
completed_at: 2026-04-09T11:45:45.948Z
blocker_discovered: false
---

# T02: Added a shared voice-speed preference hook, removed fake profile persistence, and wired the same normalized rate through MediaSource, fallback Audio, and PCM playback.

> Added a shared voice-speed preference hook, removed fake profile persistence, and wired the same normalized rate through MediaSource, fallback Audio, and PCM playback.

## What Happened
---
id: T02
parent: S03
milestone: M012
key_files:
  - web/src/hooks/use-voice-speed-preference.ts
  - web/src/hooks/use-voice-speed-preference.test.ts
  - web/src/app/(dashboard)/profile/page.tsx
  - web/src/app/(dashboard)/profile/page.test.tsx
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-streaming-audio-player.ts
  - web/src/hooks/use-streaming-audio-player.test.ts
key_decisions:
  - Kept voice speed frontend-owned and truthful by removing the fake profile PATCH and centralizing normalization plus persistence in one shared hook.
  - Applied the normalized playback rate inside useStreamingAudioPlayer so MediaSource HTMLAudioElement, fallback Audio, and PCM Web Audio consume the same authority seam.
duration: ""
verification_result: passed
completed_at: 2026-04-09T11:45:45.951Z
blocker_discovered: false
---

# T02: Added a shared voice-speed preference hook, removed fake profile persistence, and wired the same normalized rate through MediaSource, fallback Audio, and PCM playback.

**Added a shared voice-speed preference hook, removed fake profile persistence, and wired the same normalized rate through MediaSource, fallback Audio, and PCM playback.**

## What Happened

Added web/src/hooks/use-voice-speed-preference.ts as the single SSR-safe learner voice-speed authority, including normalization, canonical localStorage serialization, and a hook API consumed by both the profile page and runtime playback. Refactored web/src/app/(dashboard)/profile/page.tsx to use that hook instead of render-time localStorage reads and removed the fake api.user.updateProfile({ voice_speed_preference }) path so the UI stays truthful. Updated web/src/hooks/use-practice-websocket.ts to read the same shared preference and pass it into useStreamingAudioPlayer, then extended web/src/hooks/use-streaming-audio-player.ts so MediaSource HTMLAudioElement, fallback new Audio(audioUrl), and PCM AudioBufferSourceNode all apply the same normalized playbackRate. Added focused tests for normalization, profile hydration/persistence, and the three playback paths; attempted a browser smoke pass against localhost:3445/profile, but the local Next dev server stayed on instrumentation compilation and timed out before the page could be confirmed in-browser.

## Verification

Fresh task-level verification passed with npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts" "src/hooks/use-streaming-audio-player.test.ts" (13/13 tests green). The focused suite confirmed malformed storage values normalize to 1.0x, the profile page hydrates/persists the select via the shared seam without calling the fake PATCH, and MediaSource/fallback Audio/PCM playback all receive the configured rate. A browser smoke attempt against http://localhost:3445/profile timed out while the local Next dev server remained on 'Compiling instrumentation Node.js ...', so browser verification was inconclusive in this environment and is documented as a known issue rather than reported as a pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts" "src/hooks/use-streaming-audio-player.test.ts"` | 0 | ✅ pass | 1011ms |


## Deviations

None beyond replacing the previous oversized simulated player spec with focused hook tests that exercise the exact MediaSource, fallback Audio, and PCM branches named by the task contract.

## Known Issues

A browser smoke attempt against http://localhost:3445/profile timed out because the local Next dev server stayed on 'Compiling instrumentation Node.js ...', so real-browser verification was inconclusive in this environment.

## Files Created/Modified

- `web/src/hooks/use-voice-speed-preference.ts`
- `web/src/hooks/use-voice-speed-preference.test.ts`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(dashboard)/profile/page.test.tsx`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-streaming-audio-player.ts`
- `web/src/hooks/use-streaming-audio-player.test.ts`


## Deviations
None beyond replacing the previous oversized simulated player spec with focused hook tests that exercise the exact MediaSource, fallback Audio, and PCM branches named by the task contract.

## Known Issues
A browser smoke attempt against http://localhost:3445/profile timed out because the local Next dev server stayed on 'Compiling instrumentation Node.js ...', so real-browser verification was inconclusive in this environment.
