---
id: T03
parent: S03
milestone: M019
key_files:
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/lib/api/client.ts
  - web/src/lib/api/client-domains.ts
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep throttled interim-transcript cancellation inside `usePracticeWebSocket()` interrupt pre-cleanup instead of pushing stale-transcript cleanup into the learner page or inbound message handlers.
  - Keep `client.ts` as the outward façade and cross-cutting seam while `client-domains.ts` documents the extracted page-proved domain builders future slices should extend.
duration: 
verification_result: mixed
completed_at: 2026-04-13T04:47:55.365Z
blocker_discovered: false
---

# T03: Locked the frontend websocket seam with interrupt transcript cleanup, focused contract proof, and updated domain/transport seam inventory docs.

**Locked the frontend websocket seam with interrupt transcript cleanup, focused contract proof, and updated domain/transport seam inventory docs.**

## What Happened

I treated T03 as contract-proof hardening, not another broad refactor. First I added a red regression in `web/src/hooks/use-practice-websocket.test.ts` proving that `sendInterrupt()` must cancel any throttled interim transcript update; the failing run showed stale learner text reappearing after interrupt, which meant the outward hook still leaked cleanup responsibility into the page layer. I then fixed `web/src/hooks/use-practice-websocket.ts` so interrupt pre-cleanup clears the pending transcript throttle and blanks `interimTranscript` alongside the existing playback/backpressure cleanup. After the runtime fix, I tightened the seam inventory so downstream slices can see the split truth directly in code: `web/src/lib/api/client-domains.ts` now states which extracted builders own the proved runtime domains, `web/src/lib/api/client.ts` now distinguishes extracted versus still-inline façade domains, and the websocket hook header now points future work at `websocket/transport.ts` versus `websocket/message-handlers.ts` while documenting the responsibilities intentionally retained in the outward hook. I also updated `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` with the same concrete module map and added a `.gsd/KNOWLEDGE.md` note for the interrupt/throttling gotcha so later slices do not reintroduce page-level cleanup hacks.

## Verification

I followed a red-green verification loop on the new interrupt regression: `npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts` first failed with a stale `interimTranscript` after interrupt, then passed once the hook cleared the throttled transcript timer. I then ran the exact slice verification command, `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"`, which finished 30/30 green and confirmed the existing learner practice page contract still holds after the seam proof changes. Fresh LSP diagnostics for `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/lib/api/client.ts`, and `web/src/lib/api/client-domains.ts` were clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts` | 1 | ❌ fail | 1630ms |
| 2 | `npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts` | 0 | ✅ pass | 1510ms |
| 3 | `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"` | 0 | ✅ pass | 2190ms |
| 4 | `lsp diagnostics web/src/hooks/use-practice-websocket.ts` | 0 | ✅ pass | 0ms |
| 5 | `lsp diagnostics web/src/hooks/use-practice-websocket.test.ts` | 0 | ✅ pass | 0ms |
| 6 | `lsp diagnostics web/src/lib/api/client.ts` | 0 | ✅ pass | 0ms |
| 7 | `lsp diagnostics web/src/lib/api/client-domains.ts` | 0 | ✅ pass | 0ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/client-domains.ts`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
