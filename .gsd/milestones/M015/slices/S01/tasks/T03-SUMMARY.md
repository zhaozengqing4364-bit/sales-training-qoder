---
id: T03
parent: S01
milestone: M015
key_files:
  - web/src/lib/console-boundary.test.ts
  - web/src/app/(dashboard)/agents/[agentId]/page.tsx
  - web/src/app/(dashboard)/training/presentation/page.tsx
  - web/src/app/(dashboard)/training/sales/page.tsx
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/settings/page.tsx
  - web/src/components/highlights/HighlightCard.tsx
  - web/src/hooks/use-audio-recorder.ts
  - web/src/hooks/use-streaming-audio-player.ts
  - web/src/lib/auth-handler.ts
  - web/src/lib/performance.ts
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D182: migrate business pages/hooks/dev-support utilities onto debug.log/debug.warn/debug.error and leave raw console only in web/src/lib/debug.ts plus instrumentation bootstrap entrypoints.
duration: 
verification_result: mixed
completed_at: 2026-04-11T17:30:47.884Z
blocker_discovered: false
---

# T03: Migrated the remaining frontend raw-console callers onto the shared debug seam and locked the boundary with a focused inventory test.

**Migrated the remaining frontend raw-console callers onto the shared debug seam and locked the boundary with a focused inventory test.**

## What Happened

I added a filesystem-backed proof gate in web/src/lib/console-boundary.test.ts that scans the frontend source tree and fails whenever raw console usage appears outside the explicit exception boundary. After watching that test fail against the live inventory, I migrated the remaining scattered callers in business pages, hooks, highlight/media components, auth/performance utilities, and the developer test-mic page from raw console onto the shared debug seam via debug.log/debug.warn/debug.error. This kept the already-established durable route-error seam from T02 intact, narrowed the remaining raw-console footprint to web/src/lib/debug.ts plus the two instrumentation bootstrap entrypoints, and wrote back the resulting policy as decision D182 plus a knowledge note explaining that the boundary test and inventory must move together if exceptions ever change. I also updated the repository loop state/log so future safe-grow turns can resume from the new console boundary instead of rescanning from scratch.

## Verification

Reran a focused frontend seam gate with Vitest: npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"; it passed 27/27 and proved the new boundary test, existing debug seam test, route-error seam test, and practice websocket/page regressions all stayed green. Reran the task’s required repo-root inventory gate rg -n "console\.(log|error|warn|info)" web/src; it now reports raw console only in instrumentation.ts, instrumentation-client.ts, and web/src/lib/debug.ts, which matches the intended exception boundary. I also ran a broader tsconfig typecheck via ./web/node_modules/.bin/tsc --noEmit -p web/tsconfig.json; it still fails, but only on unrelated pre-existing issues outside the migrated console-cleanup files. Sampled LSP diagnostics across the touched app/admin/components/hooks/lib globs reported no new issues on the migrated surface.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"` | 0 | ✅ pass | 1557ms |
| 2 | `rg -n "console\.(log|error|warn|info)" web/src` | 0 | ✅ pass | 32ms |
| 3 | `./web/node_modules/.bin/tsc --noEmit -p web/tsconfig.json` | 1 | ❌ fail | 1061ms |

## Deviations

The written plan estimated two files, but the live inventory showed raw-console callers still spread across the remaining business pages, hooks, and developer/support utilities. I stayed inside scope by migrating only those callers onto the existing debug seam and by adding one focused boundary test instead of broad observability redesign.

## Known Issues

Repo-wide TypeScript still has unrelated pre-existing failures outside this task’s console-cleanup scope: web/src/app/(dashboard)/page.tsx button variant typing, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx ReactNode typing, web/src/components/error-reporting.test.tsx JSX typing, web/src/components/ui/chat-bubble.test.tsx payload typing, and web/src/lib/admin/linked-assets.test.ts expectations.

## Files Created/Modified

- `web/src/lib/console-boundary.test.ts`
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
- `web/src/app/(dashboard)/training/presentation/page.tsx`
- `web/src/app/(dashboard)/training/sales/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/settings/page.tsx`
- `web/src/components/highlights/HighlightCard.tsx`
- `web/src/hooks/use-audio-recorder.ts`
- `web/src/hooks/use-streaming-audio-player.ts`
- `web/src/lib/auth-handler.ts`
- `web/src/lib/performance.ts`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
