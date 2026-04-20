---
id: T01
parent: S01
milestone: M015
key_files:
  - web/src/lib/debug.ts
  - web/src/components/ErrorBoundary.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D180: keep raw console only for instrumentation bootstrap and the shared debug seam itself; treat route error surfaces, business/runtime faults, and debug-only utilities as migrate-to-seam callers.
duration: 
verification_result: passed
completed_at: 2026-04-11T17:12:25.021Z
blocker_discovered: false
---

# T01: Cataloged frontend console usage into one shared migration map and locked the allowed raw-console exception boundary for M015/S01.

**Cataloged frontend console usage into one shared migration map and locked the allowed raw-console exception boundary for M015/S01.**

## What Happened

I scanned the live `web/src` console inventory, verified the existing seams in `web/src/lib/debug.ts`, `web/src/components/ErrorBoundary.tsx`, and the instrumentation entrypoints, and then encoded the classification result directly in `web/src/lib/debug.ts` as a canonical `frontendConsoleInventory` plus `frontendConsoleRouteErrorPolicy`. That inventory narrows allowed raw-console exceptions to the shared debug seam itself and the bootstrap instrumentation entrypoints, marks route error surfaces as durable reporters that should migrate without losing fallback UI, and separates business/runtime faults from debug-only utility noise so later tasks can migrate against one fixed map instead of repeating ad hoc repo-wide searches. I also annotated `ErrorBoundary` and `AsyncErrorBoundary` to make their durable route-error role explicit for T02/T03, recorded the observability boundary as decision D180, saved the non-obvious rule to `.gsd/KNOWLEDGE.md`, and updated the repo loop state/log for continuity.

## Verification

Ran the task’s required repo-root inventory gate `rg -n "console\.(log|error|warn|info)" web/src` to confirm the live console callers after encoding the classification map; the command passed and now provides the expected post-inventory baseline for T02/T03 migration work. Also re-checked `web/src/lib/debug.ts` and `web/src/components/ErrorBoundary.tsx` with fresh LSP diagnostics, and both files reported no issues after the inventory/policy writeback.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "console\.(log|error|warn|info)" web/src` | 0 | ✅ pass | 26ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
