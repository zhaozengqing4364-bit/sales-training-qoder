---
id: S03
parent: M012
milestone: M012
provides:
  - A real learner-shell route seam from the shared sidebar user menu into `/profile`, without regressing the shared history entry.
  - A shared frontend voice-speed preference seam whose normalized value now affects every learner audio playback path used during practice.
  - Learner-safe leaderboard explanation copy that tells users exactly which sessions count toward ranking and average score.
requires:
  - slice: S01
    provides: The existing forgot/reset-password flow and learner account baseline that S03 reuses for truthful password changes without adding backend auth scope.
  - slice: S02
    provides: The shared learner sidebar/navigation seam that S03 extends with a real `/profile` handoff while preserving the history entry stabilized in S02.
affects:
  []
key_files:
  - web/src/components/layout/sidebar.tsx
  - web/src/components/layout/sidebar.test.tsx
  - web/src/app/(dashboard)/profile/page.tsx
  - web/src/app/(dashboard)/profile/page.test.tsx
  - web/src/hooks/use-voice-speed-preference.ts
  - web/src/hooks/use-voice-speed-preference.test.ts
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-streaming-audio-player.ts
  - web/src/hooks/use-streaming-audio-player.test.ts
  - web/src/app/(dashboard)/leaderboard/page.tsx
  - web/src/app/(dashboard)/leaderboard/page.test.tsx
key_decisions:
  - Keep learner profile behavior inside existing trusted seams: the sidebar hands off to /profile, and password changes reuse the shipped forgot/reset-password route instead of inventing a new authenticated password API.
  - Treat voice speed as one frontend authority seam (`useVoiceSpeedPreference`) with supported-value normalization and localStorage persistence; every learner audio path must consume that same normalized playbackRate.
  - Converge learner leaderboard copy to the admin evaluable-session score basis without expanding S03 into leaderboard backend ordering or analytics-contract changes.
patterns_established:
  - For learner settings, prefer one explicit authority seam that owns normalization and persistence, then thread that value into every real consumer rather than duplicating page-local state.
  - When the product already has a truthful route for an action, use a real Next route handoff instead of leaving a dead button or inventing a fake in-place API.
  - If leaderboard/backend semantics must stay stable for scope reasons, align learner-facing explanation copy to the existing authoritative analytics contract and lock it with focused regressions.
observability_surfaces:
  - Focused Vitest gate for learner route handoff: `src/components/layout/sidebar.test.tsx` + `src/app/(dashboard)/profile/page.test.tsx`.
  - Focused Vitest gate for the voice-speed authority seam and playback-path wiring: `src/hooks/use-voice-speed-preference.test.ts` + `src/hooks/use-streaming-audio-player.test.ts`.
  - Focused Vitest gate for learner leaderboard semantics and fallback states: `src/app/(dashboard)/leaderboard/page.test.tsx`.
  - Fresh LSP diagnostics on `sidebar.tsx`, `profile/page.tsx`, `use-voice-speed-preference.ts`, `use-practice-websocket.ts`, `use-streaming-audio-player.ts`, and `leaderboard/page.tsx` all returned clean results.
drill_down_paths:
  - .gsd/milestones/M012/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M012/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M012/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-09T12:10:05.551Z
blocker_discovered: false
---

# S03: 个人中心与排行榜体验收敛

**S03 made learner profile and leaderboard behavior truthful: `/profile` is reachable from the shared shell, password changes hand off to the real forgot/reset flow, voice speed is persisted through one shared preference seam and applied to every playback path, and leaderboard copy now clearly limits ranking to evaluable completed sessions.**

## What Happened

S03 closed the remaining learner-facing trust gaps in the M012 first-login experience without expanding backend scope. T01 finished the learner-shell route handoff seam: the shared sidebar user menu no longer exposes a dead "编辑资料" button, and both expanded and collapsed learner affordances now land on the real `/profile` route while preserving the `SidebarContent` history entry that S02 had already stabilized. On the profile page itself, the password action was rewritten as truthful copy plus a real Next link to `/forgot-password`, so learners are told exactly how password changes happen and the page no longer relies on `window.location.href` or hints at a non-existent authenticated password API.

T02 turned voice speed from a fake profile preference into a real learner runtime seam. The new `useVoiceSpeedPreference()` hook owns supported-value normalization, SSR-safe defaulting, and localStorage persistence, which removed render-time storage reads and the pretend `voice_speed_preference` profile PATCH. The same normalized rate is now threaded through `usePracticeWebSocket()` into `useStreamingAudioPlayer()`, where all three playback paths — MediaSource `HTMLAudioElement`, fallback `new Audio(...)`, and PCM `AudioBufferSourceNode` scheduling — apply the same `playbackRate`. That means the setting a learner changes in `/profile` now materially affects the audio they hear during practice instead of being a page-local illusion.

T03 finished the leaderboard trust cleanup. The learner leaderboard kept its current filters, `myRank` fallback logic, empty state, and backend ordering contract, but its explanatory copy now matches the authoritative admin analytics semantics: only evaluable completed sessions count toward averages and ranking, while evidence-insufficient sessions stay in history without silently changing leaderboard math. Focused regressions now lock populated, empty/malformed, and fallback-my-rank states to that evaluable-session wording so future UI changes cannot drift back to the old weighted-score implication.

Downstream, this slice provides three reusable patterns: learner-visible settings should either affect a real downstream behavior or be removed; truthful route handoffs are better than fake in-place actions when the real contract already exists; and UX trust gaps caused by scoring semantics drift can often be closed at the learner-copy seam without prematurely expanding backend scope.

## Operational Readiness (Q8)
- **Health signal:** `/profile` remains reachable from learner sidebar affordances in both expanded and collapsed modes; the profile page shows the shared voice-speed options and persists them; practice playback honors the selected rate across MediaSource, fallback audio, and PCM paths; leaderboard header/footer copy continues to describe evaluable completed-session semantics.
- **Failure signal:** the sidebar/profile affordance regresses into a dead button, the password CTA stops pointing at `/forgot-password`, localStorage malformed values stop normalizing back to `1.0x`, or one playback path ignores the shared `playbackRate` while others still honor it.
- **Recovery procedure:** first rerun the three focused slice gates (sidebar/profile, voice-speed/audio, leaderboard); if audio-rate behavior drifts, inspect `useVoiceSpeedPreference()` → `usePracticeWebSocket()` → `useStreamingAudioPlayer()` before touching page-level UI; if profile/password routing drifts, restore the real Next `Link` handoff instead of adding fallback imperative navigation.
- **Monitoring gaps:** this slice has focused test and diagnostics coverage but no production telemetry for which playback path was used or whether learners changed voice speed, so regressions outside test coverage would still surface mainly through QA or user reports.

## Verification

Fresh slice-close verification passed exactly the three planned web gates plus clean diagnostics on the touched files.

1. `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/app/(dashboard)/profile/page.test.tsx"` ✅ pass (2 files, 9 tests). This re-proved the real `/profile` route handoff from the learner shell, preserved the shared history seam, and locked the truthful `/forgot-password` password CTA plus profile voice-speed behavior.
2. `npm --prefix web test -- --run "src/hooks/use-voice-speed-preference.test.ts" "src/hooks/use-streaming-audio-player.test.ts"` ✅ pass (2 files, 8 tests). This re-proved supported-value normalization, storage fallback behavior, and shared playbackRate wiring across MediaSource, fallback Audio, and PCM playback.
3. `npm --prefix web test -- --run "src/app/(dashboard)/leaderboard/page.test.tsx"` ✅ pass (1 file, 3 tests). This re-proved populated, empty/malformed, and fallback-my-rank leaderboard states all keep the evaluable completed-session explanation copy.
4. Fresh LSP diagnostics on `sidebar.tsx`, `profile/page.tsx`, `use-voice-speed-preference.ts`, `use-practice-websocket.ts`, `use-streaming-audio-player.ts`, and `leaderboard/page.tsx` all returned `No diagnostics`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Voice-speed preference is still browser-local rather than server-synced across devices, and the leaderboard change in S03 is intentionally copy/UX convergence only — backend ranking/aggregation semantics were left untouched.

## Follow-ups

If product requirements later demand cross-device profile settings sync or an authenticated in-profile password change flow, that should ship as an explicit backend/profile contract slice rather than being layered onto this frontend-only S03 seam.

## Files Created/Modified

- `web/src/components/layout/sidebar.tsx` — Turned the learner user-menu "编辑资料" affordance into a real /profile route handoff while preserving the shared SidebarContent history seam.
- `web/src/components/layout/sidebar.test.tsx` — Locked expanded/collapsed learner profile entry routing and preserved history/help affordances in the shared sidebar seam.
- `web/src/app/(dashboard)/profile/page.tsx` — Reworked profile settings so voice speed comes only from the shared preference hook, removed the fake notification toggle, and changed the password CTA to a truthful /forgot-password link.
- `web/src/app/(dashboard)/profile/page.test.tsx` — Added focused regressions for the /forgot-password password CTA, shared voice-speed hydration/persistence, malformed localStorage normalization, and the no-notification-toggle contract.
- `web/src/hooks/use-voice-speed-preference.ts` — Added the SSR-safe voice-speed preference authority seam with supported-value normalization and localStorage persistence.
- `web/src/hooks/use-voice-speed-preference.test.ts` — Locked malformed input normalization, storage-failure fallback, and persistence behavior for the shared voice-speed hook.
- `web/src/hooks/use-practice-websocket.ts` — Threaded the shared voice-speed preference into the learner realtime audio player seam so practice playback reads one normalized preference source.
- `web/src/hooks/use-streaming-audio-player.ts` — Applied the same normalized playbackRate across MediaSource HTMLAudio playback, fallback Audio playback, and PCM Web Audio scheduling.
- `web/src/hooks/use-streaming-audio-player.test.ts` — Added focused playback-rate regressions covering MediaSource, fallback Audio, PCM, and malformed-rate fallback behavior.
- `web/src/app/(dashboard)/leaderboard/page.tsx` — Updated learner leaderboard copy so ranking and averages clearly only count evaluable completed sessions while preserving existing filters and fallback behavior.
- `web/src/app/(dashboard)/leaderboard/page.test.tsx` — Locked populated, empty/malformed, and fallback-my-rank leaderboard states against the new evaluable-session explanation copy.
