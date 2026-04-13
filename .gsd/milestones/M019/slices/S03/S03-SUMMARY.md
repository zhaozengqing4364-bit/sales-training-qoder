---
id: S03
parent: M019
milestone: M019
provides:
  - An explicit frontend domain-client seam for auth/practice/sessions/agents/presentations/admin-report builders behind the outward `api` façade.
  - An explicit websocket transport helper seam for URL construction, reconnect policy, close-reason mapping, and pending outbound queue rules.
  - A documented outward-hook rule for interrupt/reconnect/backpressure ownership that downstream realtime slices can extend without page-level hacks.
requires:
  []
affects:
  - S04
key_files:
  - web/src/lib/api/client.ts
  - web/src/lib/api/client-domains.ts
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/websocket/transport.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D216 — keep `client.ts` as the outward API façade and shared auth/error/trace seam while extracted runtime domains live behind `client-domains.ts` and websocket helpers live behind `websocket/transport.ts`.
  - D215 — keep throttled interim-transcript cancellation inside `usePracticeWebSocket()` interrupt pre-cleanup instead of pushing stale-transcript cleanup into the learner page or message handlers.
patterns_established:
  - Preserve one outward contract (`api`, `usePracticeWebSocket()`) while splitting inward helpers and builders underneath it.
  - Keep cross-cutting auth/error/trace logic centralized in `client.ts`; keep outbound websocket orchestration centralized in `usePracticeWebSocket()` plus pure helpers in `websocket/transport.ts`.
  - Document seam ownership in code-adjacent inventories (`client.ts`, `use-practice-websocket.ts`, architecture scan, knowledge log) so later slices change the owning layer instead of patching pages.
observability_surfaces:
  - Code-adjacent seam inventories in `web/src/lib/api/client.ts`, `web/src/lib/api/client-domains.ts`, `web/src/hooks/use-practice-websocket.ts`, and `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`.
  - Focused Vitest proof gates for client governance/domain builders plus login/dashboard/practice/report/replay and websocket transport behavior.
  - Knowledge-log guidance in `.gsd/KNOWLEDGE.md` that classifies stale-interrupt transcript cleanup as a transport-seam issue.
drill_down_paths:
  - .gsd/milestones/M019/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M019/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M019/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-13T04:54:27.977Z
blocker_discovered: false
---

# S03: S03: Frontend domain client 与 transport seam 抽离

**Split the frontend API client and practice websocket mega files into explicit domain/transport seams while keeping the existing auth, dashboard, practice, report, and replay contracts green.**

## What Happened

## What this slice delivered

S03 closed the two biggest remaining frontend mega-file seams without changing the pages that depend on them.

- `web/src/lib/api/client.ts` remains the single outward `api` façade and the only shared place that owns auth expiry handling, trace/header wiring, request transport, loopback retry, and API error normalization.
- `web/src/lib/api/client-domains.ts` now holds the extracted page-proved runtime domain builders for `auth`, `practice`, `sessions`, `agents`, `presentations`, and admin report actions, so future work can extend domain modules without teaching pages to fetch directly.
- `web/src/hooks/use-practice-websocket.ts` stays the sole outward transport/orchestration hook consumed by the live learner practice page, while `web/src/hooks/websocket/transport.ts` now owns URL assembly, pending-message queue rules, reconnect backoff, and close-reason mapping.
- Interrupt cleanup is now explicitly transport-owned: `sendInterrupt()` clears the throttled interim-transcript timer in the outward hook, so stale learner text cannot reappear after interrupt and the page does not need local cleanup hacks.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` and `.gsd/KNOWLEDGE.md` now document the exact downstream split rules: extend API domains inside `web/src/lib/api/*`, extend inbound websocket state in `message-handlers.ts`, and extend outbound websocket pacing/reconnect logic in `use-practice-websocket.ts` or `websocket/transport.ts`.

## Why it matters downstream

After S03, frontend request and transport changes no longer have to start inside two opaque mega files.

- Auth/dashboard/practice/report/replay pages still import the same outward contracts, so slice-local refactors did not create hidden page-level coupling.
- M020+ frontend work can add or move API behavior by domain module instead of growing `client.ts` blindly.
- Realtime work can now classify failures into clearer layers: domain client, shared auth/error seam, outbound transport/orchestration, or inbound message handlers.
- S04 can attach release-gate proof, metrics, and doc-contract checks to named seams instead of informal file folklore.

## Operational Readiness (Q8)

- **Health signal:** the outward `api` façade and `usePracticeWebSocket()` contract remain green across focused auth/dashboard/practice/report/replay suites; extracted seam tests for `client-domains.ts` and `websocket/transport.ts` are also green; LSP diagnostics for the touched seam files are clean.
- **Failure signal:** regressions should now show up as one of four buckets: domain-builder drift (`client-domains.ts`), shared auth/error/trace drift (`client.ts`), outbound transport/orchestration drift (`use-practice-websocket.ts` / `websocket/transport.ts`), or inbound state projection drift (`websocket/message-handlers.ts`). A stale interim transcript after interrupt is a transport-cleanup regression, not a page bug.
- **Recovery procedure:** start at the outward contract that failed, fix the owning seam instead of patching a page, then rerun the focused suites (`client.auth` / `client-domains` / `client-governance`, login/dashboard/practice/report/replay, websocket hook/transport).
- **Monitoring gaps:** this slice proved the seam with code-adjacent inventories and focused tests, but production-facing release metrics and truth-line automation are still missing; S04 remains responsible for turning these seam boundaries into a durable release gate.

## Verification

Fresh slice-close verification from repo root:

1. `rg -n "export const api|normalizeApiErrorPayload|usePracticeWebSocket|MAX_RECONNECT_ATTEMPTS|message-handlers" web/src/lib/api web/src/hooks` ✅ pass — confirmed the outward API façade, error-normalization seam, websocket outward hook, reconnect budget, and handler split are still discoverable in the expected files.
2. `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` ✅ pass — 4 files / 50 tests green.
3. `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"` ✅ pass — 2 files / 30 tests green.
4. `npm --prefix web test -- --run src/lib/api/client-domains.test.ts src/hooks/websocket/transport.test.ts` ✅ pass — 2 files / 5 tests green.
5. `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" src/lib/api/client.auth.test.ts src/lib/api/client-domains.test.ts src/lib/api/client-governance.test.ts` ✅ pass — 4 files / 24 tests green, covering dashboard plus API façade governance.
6. LSP diagnostics on `web/src/lib/api/client.ts`, `web/src/lib/api/client-domains.ts`, `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/websocket/transport.ts`, and `web/src/hooks/use-practice-websocket.test.ts` all returned `No diagnostics`.

Net result: the slice plan’s required contract checks passed fresh, the extracted seam helpers are covered directly, and the touched frontend seam files are type/diagnostic clean.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

`web/src/lib/api/client.ts` still contains several inline façade domains (`user`, `dashboard`, `analytics`, `admin`, etc.), so the client split is intentionally partial rather than a full decomposition. Production-facing release truth lines and metrics for these new seams are also still pending S04.

## Follow-ups

S04 should attach release-gate proof, metrics, and doc-contract checks to the new frontend seam boundaries. Later frontend slices can continue extracting the remaining inline façade domains from `client.ts`, but they should preserve the outward `api` import contract and avoid teaching pages to call domain builders directly.

## Files Created/Modified

- `web/src/lib/api/client.ts` — Preserved the outward API façade and cross-cutting auth/error/trace seam while wiring extracted runtime domains behind it and documenting the split.
- `web/src/lib/api/client-domains.ts` — Added extracted domain builders for auth, practice, sessions, agents, presentations, and admin report actions.
- `web/src/hooks/use-practice-websocket.ts` — Kept the outward transport/orchestration hook stable, documented retained responsibilities, and fixed interrupt cleanup to cancel throttled interim transcript updates.
- `web/src/hooks/websocket/transport.ts` — Added pure transport helpers for websocket URL assembly, pending queue behavior, reconnect backoff, and close-reason mapping.
- `web/src/hooks/use-practice-websocket.test.ts` — Locked the interrupt/transcript cleanup contract and continued proving the outward websocket hook behavior.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Recorded the concrete frontend API-domain and websocket transport ownership map for downstream slices.
- `.gsd/KNOWLEDGE.md` — Captured the outward-contract and interrupt-throttle gotchas so later slices do not reintroduce page-level cleanup hacks.
