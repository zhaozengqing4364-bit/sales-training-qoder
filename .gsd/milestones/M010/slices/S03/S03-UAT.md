# S03: 前端出处渲染与端到端验证 — UAT

**Milestone:** M010
**Written:** 2026-03-30T08:11:30.230Z

# S03: 前端出处渲染与端到端验证 — UAT

**Milestone:** M010
**Written:** 2026-03-30

## UAT Type

- UAT mode: focused frontend artifact verification
- Why this mode is sufficient: S03 ships learner-facing report/replay rendering and shared helper-owned copy, not a new backend contract or standalone runtime workflow. Acceptance depends on whether canonical report/replay payloads are rendered truthfully, degraded gracefully, and kept on one frontend authority seam.

## Preconditions

- Node dependencies are installed for `web/`.
- The branch includes the S03 report/replay and `session-evidence.ts` changes.
- No stale test job is still running from an earlier source tree.
- Run commands from repo root.

## Smoke Test

Run:

`npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`

**Expected:** Vitest passes 33/33 tests, proving report and replay render the same learner-facing provenance/degradation vocabulary while preserving route-specific authority and existing replay/report behaviors.

## Test Cases

### 1. Report renders canonical conclusion provenance and layered degradation for a completed sales session

1. Run:
   `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx"`
2. Inspect the happy-path sales assertions.
3. **Expected:** The report page shows helper-owned provenance/degradation copy for the completed sales payload, including conclusion evidence rows and all four degradation layers when provided.

### 2. Report keeps canonical provenance visible even when supplemental knowledge-check loading fails

1. In the same report suite, inspect the test that rejects `getKnowledgeCheck()`.
2. **Expected:** Canonical report-driven provenance/degradation still renders; the optional supplemental request does not become the authority source and does not blank the new section.

### 3. Report omits malformed provenance/degradation fragments instead of crashing or inventing filler truth

1. In the report suite, inspect the malformed-input coverage.
2. **Expected:** Wrong-shaped `conclusion_evidence` / `evidence_degradation` fragments are filtered out by `session-evidence.ts`; the page remains usable and only the malformed subsection is omitted.

### 4. Presentation report payloads keep the new sales-only sections suppressed

1. In the report suite, inspect the presentation-null assertions.
2. **Expected:** When the backend returns `conclusion_evidence = null` and `evidence_degradation = null`, the learner report does not render the new sales-only provenance/degradation cards.

### 5. Replay renders the same helper-owned learner vocabulary from canonical replay payload fields

1. Run:
   `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`
2. Inspect the happy-path replay assertions.
3. **Expected:** The replay page shows the same learner-facing provenance/degradation wording as report for equivalent payloads, but the source of truth is `replayData.conclusion_evidence` and `replayData.evidence_degradation`.

### 6. Replay does not fall back to stale report-snapshot provenance/degradation truth

1. In the replay suite, inspect the stale-report-snapshot regression test.
2. **Expected:** When replay payload and report snapshot conflict, the rendered provenance/degradation copy follows the replay payload only; the report snapshot remains retry-metadata-only.

### 7. Replay keeps existing replay-specific behaviors intact after the new section lands

1. In the replay suite, inspect the completion-gate, retry CTA, and highlight/deep-link anchor tests.
2. **Expected:** Existing blocked-state messaging, retry CTA behavior, and replay anchor behavior still pass with the new provenance/degradation section present.

### 8. Presentation replay payloads keep the new sales-only sections suppressed

1. In the replay suite, inspect the presentation-null assertions.
2. **Expected:** Presentation replay payloads with `conclusion_evidence = null` / `evidence_degradation = null` do not render the sales-only provenance/degradation UI.

## Edge Cases

### Cross-page helper authority seam

1. Inspect `web/src/lib/session-evidence.ts`, `report/page.tsx`, and `replay/page.tsx`.
2. **Expected:** Token-to-copy mapping and malformed-fragment filtering live in `session-evidence.ts`; report/replay pages only render helper output and do not implement their own provenance/degradation parsers.

### Replay authority boundary

1. Inspect `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`.
2. **Expected:** The replay page reads provenance/degradation from replay payload fields, while any report snapshot loaded on the page is used for retry metadata only.

## Failure Signals

- Report and replay show different learner-facing provenance/degradation wording for equivalent payloads.
- Supplemental `getKnowledgeCheck()` failure hides canonical report-driven provenance/degradation.
- Replay starts rendering provenance/degradation from report snapshot data instead of replay payload truth.
- Malformed payload fragments throw render errors or produce invented filler copy.
- Presentation payloads unexpectedly show the new sales-only sections.
- Replay completion-gate, retry CTA, or anchor tests regress after the new section is added.

## Requirements Proved By This UAT

- R027 — Learner-facing report/replay surfaces now expose key-conclusion provenance instead of leaving the evidence line backend-only.
- R028 — Learner-facing report/replay surfaces now expose layered degradation truth with shared vocabulary and without stale fallback paths.

## Not Proven By This UAT

- Live browser/runtime behavior outside the focused jsdom/Vitest learner report/replay surfaces.
- Repo-wide frontend type health; unrelated baseline `tsc` failures remain outside this slice.
- Any new backend route-family contract work; S03 assumes the S01/S02 backend parity contract is already authoritative.

## Notes for Tester

Treat the paired report/replay Vitest gate as the authority for this slice. If one page drifts, inspect `web/src/lib/session-evidence.ts` first, then confirm each page is reading the correct route payload before touching backend contracts. On replay specifically, stale report snapshots are expected to remain useful for retry metadata only and must not become a provenance/degradation fallback path.
