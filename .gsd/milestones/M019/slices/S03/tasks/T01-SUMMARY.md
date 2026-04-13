---
id: T01
parent: S03
milestone: M019
key_files:
  - web/src/lib/api/client.ts
  - web/src/hooks/use-practice-websocket.ts
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Keep page/component imports on the outward `api` façade while future domain modules move behind it.
  - Keep `usePracticeWebSocket()` as the sole outward transport contract for the live practice page while future transport helpers move underneath it.
duration: 
verification_result: passed
completed_at: 2026-04-13T04:19:10.021Z
blocker_discovered: false
---

# T01: Codified the frontend domain-client and websocket transport seam inventory so S03 can split internals without changing page contracts.

**Codified the frontend domain-client and websocket transport seam inventory so S03 can split internals without changing page contracts.**

## What Happened

I treated T01 as an authority-mapping task, not a behavior refactor. In `web/src/lib/api/client.ts` I added a durable M019/S03 inventory block above the `api` façade that names the shared auth/error/trace/transport seam, enumerates the current domain surfaces, and records the high-fan-out learner/admin consumers that must keep importing the façade instead of reaching into future domain modules directly. In `web/src/hooks/use-practice-websocket.ts` I extended the top-level contract comment to pin the outward consumer (`app/(user)/practice/[sessionId]/page.tsx`), the responsibilities already delegated to `message-handlers` / audio helpers, and the transport/orchestration responsibilities that intentionally remain in the outward hook. I then wrote the same seam map back into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` as section 4.5 and added a future-agent knowledge note in `.gsd/KNOWLEDGE.md` so T02/T03 can split internals from a truthful repo-local inventory instead of re-discovering the boundary from grep output.

## Verification

Verified the task-plan grep gate from repo root, then ran a focused web proof bundle covering the touched API client and websocket hook surfaces: `npm --prefix web test -- --run src/lib/api/client.auth.test.ts src/hooks/use-practice-websocket.test.ts` finished green (27/27). I also reran repo-root grep proof to confirm the new seam inventory is discoverable in `client.ts`, `use-practice-websocket.ts`, the architecture scan, and the knowledge log. Fresh LSP diagnostics for `web/src/lib/api/client.ts` and `web/src/hooks/use-practice-websocket.ts` reported no issues.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/lib/api/client.auth.test.ts src/hooks/use-practice-websocket.test.ts` | 0 | ✅ pass | 2741ms |
| 2 | `rg -n "export const api|normalizeApiErrorPayload|usePracticeWebSocket|MAX_RECONNECT_ATTEMPTS|message-handlers" web/src/lib/api web/src/hooks` | 0 | ✅ pass | 42ms |
| 3 | `rg -n "M019/S03|api façade|transport contract inventory|usePracticeWebSocket\(\)|websocket lifecycle|domain client seam inventory" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/lib/api/client.ts web/src/hooks/use-practice-websocket.ts .gsd/KNOWLEDGE.md` | 0 | ✅ pass | 23ms |
| 4 | `lsp diagnostics web/src/lib/api/client.ts` | 0 | ✅ pass | 0ms |
| 5 | `lsp diagnostics web/src/hooks/use-practice-websocket.ts` | 0 | ✅ pass | 0ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/api/client.ts`
- `web/src/hooks/use-practice-websocket.ts`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
