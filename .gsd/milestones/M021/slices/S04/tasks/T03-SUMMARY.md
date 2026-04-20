---
id: T03
parent: S04
milestone: M021
key_files:
  - docs/api-contract/support-runtime.md
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Keep the T02 runtime-event semantics documented on the existing `/support/runtime/faults.items[].diagnostics.runtime_events[]` contract instead of inventing a second support payload.
  - Use the existing report/replay `data-contract-source` surface plus explicit failure copy as the frontend proof line for compat/failure semantics, rather than adding new UI-only status plumbing in T03.
duration: 
verification_result: passed
completed_at: 2026-04-14T04:42:38.210Z
blocker_discovered: false
---

# T03: Documented support/runtime event reading rules and locked report/replay proof for compat and failure states.

**Documented support/runtime event reading rules and locked report/replay proof for compat and failure states.**

## What Happened

I treated T03 as a read-side/write-back task rather than another runtime implementation pass, because T02 had already shipped the unified event schema and support/read-side surfaces. First I re-read `docs/api-contract/support-runtime.md`, the report/replay page tests, the report/replay page implementations, and the M021 architecture scan section to confirm what the shipped UI and support contract already expose. That review showed a precise mismatch: the backend contract already carries `diagnostics.runtime_events[]`, and the frontend already distinguishes canonical vs compatibility score readers plus multiple degraded/failure states, but the long-lived docs did not explain how to read `mode` vs `degraded` vs `failure` vs `cost`, and the page tests did not explicitly lock the compat-reader path or the retrieval `search_failed` copy away from success-like wording.

I then wrote the support/read-side rules back into `docs/api-contract/support-runtime.md`: the doc now explains the `runtime_events` shape (`event_id/category/severity/status/source/summary/details/metrics/occurred_at`), the allowed `quality/cost/failure/mode` categories and `info/ok/degraded/failure` severities, and the interpretation rule that `category=mode` with `status=live|compat` answers path provenance while `severity=degraded|failure` answers quality/result status. I also updated `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` so downstream M021 work has one explicit read-side rule: support faults reuse `/support/runtime/faults.items[].diagnostics.runtime_events[]`, and report/replay proof must show compat/failure explicitly instead of inferring them from stale scores or fallback copy.

On the frontend proof side, I kept the shipped UI unchanged and tightened the tests around the existing surfaces. In `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` I added a focused compatibility-reader assertion proving the score card switches to `data-contract-source="compatibility_reader"` and keeps the legacy compatibility badge visible when the canonical kernel is absent, and I strengthened the retrieval `search_failed` assertion so failure remains explicit and does not collapse into hit/miss success copy. In `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` I added the same compatibility-reader source assertion for replay. The end result is that future readers can now inspect the shipped support/runtime docs and the report/replay proof directly, instead of reverse-engineering the semantics from default scores, fallback copy, or scattered logs.

## Verification

I ran the exact task-plan verification command fresh after the edits. `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` passed with 39/39 tests green, including the new focused assertions for compatibility-reader rollups and the strengthened failure-path check that retrieval `search_failed` stays explicit instead of rendering as hit/miss. I then ran `rg -n "quality|cost|failure|degraded|compat" docs/api-contract/support-runtime.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, which passed and showed the intended keywords directly in the long-lived support/runtime and architecture artifacts.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` | 0 | ✅ pass | 3471ms |
| 2 | `rg -n "quality|cost|failure|degraded|compat" docs/api-contract/support-runtime.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` | 0 | ✅ pass | 37ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `docs/api-contract/support-runtime.md`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
