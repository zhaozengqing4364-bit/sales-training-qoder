---
id: T02
parent: S03
milestone: M019
key_files:
  - web/src/lib/api/client.ts
  - web/src/lib/api/client-domains.ts
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/websocket/transport.ts
  - web/src/lib/api/client-domains.test.ts
  - web/src/hooks/websocket/transport.test.ts
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Keep `client.ts` as the single shared auth/error/trace/request seam while moving only the runtime-facing, page-proved domains behind `client-domains.ts`.
  - Keep `usePracticeWebSocket()` as the outward hook contract and extract only pure transport helpers (URL/queue/backoff/close-reason) into `websocket/transport.ts` instead of pushing websocket lifecycle logic into pages or multiple coordinators.
duration: 
verification_result: passed
completed_at: 2026-04-13T04:38:38.988Z
blocker_discovered: false
---

# T02: Split the runtime-facing frontend API and websocket transport seams behind dedicated helper modules without changing page contracts.

**Split the runtime-facing frontend API and websocket transport seams behind dedicated helper modules without changing page contracts.**

## What Happened

I executed this as a narrow seam refactor instead of a broad client rewrite. On the API side, I added `web/src/lib/api/client-domains.ts` and moved the runtime-facing domains that this slice actually proves at the page level — `auth`, `practice`, `sessions`, `agents`, `presentations`, and the report helpers consumed through `api.admin` — behind domain-builder functions. `web/src/lib/api/client.ts` still owns the cross-cutting seam (auth/session-expiry handling, trace headers, loopback retry, request cancellation, error normalization, and shared normalizers), but the outward `api` façade now points those proved runtime domains at the extracted module instead of keeping the logic inline. On the websocket side, I added `web/src/hooks/websocket/transport.ts` and moved URL assembly, queue/backoff helpers, reconnect delay policy, and close-reason mapping out of `use-practice-websocket.ts`, while keeping `usePracticeWebSocket()` itself as the outward transport/orchestration contract consumed by the live practice page. I drove the split red-first with new focused seam tests (`client-domains.test.ts` and `transport.test.ts`), fixed the only regression they surfaced (restoring the original websocket query-param order), and then reran the exact slice verification bundle to confirm login, live practice, report, and replay pages still pass unchanged through the outward contracts.

## Verification

First I ran the new red-first seam tests and then greened them after wiring the extracted modules: `npm --prefix web test -- --run src/lib/api/client-domains.test.ts src/hooks/websocket/transport.test.ts src/hooks/use-practice-websocket.test.ts` finished 23/23 green. I then ran the exact slice verification command from the task plan — `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` — and it finished 50/50 green, confirming the outward `api` façade plus `usePracticeWebSocket()` contract stayed intact for the proven login/practice/report/replay flows. Fresh LSP diagnostics for `web/src/lib/api/client.ts`, `web/src/lib/api/client-domains.ts`, `web/src/hooks/use-practice-websocket.ts`, and `web/src/hooks/websocket/transport.ts` all returned clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/lib/api/client-domains.test.ts src/hooks/websocket/transport.test.ts src/hooks/use-practice-websocket.test.ts` | 0 | ✅ pass | 1590ms |
| 2 | `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` | 0 | ✅ pass | 3700ms |
| 3 | `lsp diagnostics web/src/lib/api/client.ts` | 0 | ✅ pass | 0ms |
| 4 | `lsp diagnostics web/src/lib/api/client-domains.ts` | 0 | ✅ pass | 0ms |
| 5 | `lsp diagnostics web/src/hooks/use-practice-websocket.ts` | 0 | ✅ pass | 0ms |
| 6 | `lsp diagnostics web/src/hooks/websocket/transport.ts` | 0 | ✅ pass | 0ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/api/client.ts`
- `web/src/lib/api/client-domains.ts`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/websocket/transport.ts`
- `web/src/lib/api/client-domains.test.ts`
- `web/src/hooks/websocket/transport.test.ts`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
