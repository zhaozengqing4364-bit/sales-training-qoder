# S03: 前端出处渲染与端到端验证

**Goal:** Render projection-backed conclusion provenance and four-layer degradation on learner report and replay pages through shared `session-evidence.ts` helpers, so completed sales sessions show why each key conclusion is believed and which evidence layers are degraded without inventing page-local truth.
**Demo:** After this: After this slice, report and replay pages render conclusion provenance (which evidence sources support each conclusion) and degradation indicators (which layers are missing) using shared helpers from session-evidence.ts.

## Tasks
- [x] **T01: Added shared conclusion-evidence helpers and rendered canonical report provenance/degradation on the learner report page.** — Load `safe-grow`, `react-best-practices`, `test`, and `verification-before-completion` before coding. This task establishes the frontend authority seam for S03 and immediately uses it on the learner report page; do not parse `conclusion_evidence` or `evidence_degradation` directly in the page component.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `GET /practice/sessions/{id}/report` payload | Keep existing page-level load/error handling; no fallback authority path is introduced | Existing report-page loading/error state remains the only timeout behavior | Helper normalization returns partial/null provenance rows and the page omits only the malformed subsection |
| Optional `GET /knowledge-check` supplemental request | Keep canonical report provenance/degradation visible; do not couple the new UI to this request | Same as error — supplemental diagnostics stay optional | Ignore malformed supplemental data for the new surfaces |

## Load Profile

- **Shared resources**: none beyond the existing report render path and jsdom test runtime.
- **Per-operation cost**: zero new network calls; one helper normalization pass over three conclusion entries and four degradation layers.
- **10x breakpoint**: the first failure at 10x is duplicated DOM/copy noise if the helper forgets to bound or filter malformed rows, not backend load.

## Negative Tests

- **Malformed inputs**: `conclusion_evidence=null`, missing per-source objects, missing `token`/`explanation`, wrong-shaped source entries.
- **Error paths**: rejected `getKnowledgeCheck()` must not hide the canonical report-driven provenance/degradation section.
- **Boundary conditions**: happy-path sales payload, degraded layer payload, and presentation payload with `conclusion_evidence=null` / `evidence_degradation=null`.

## Steps

1. Add shared frontend types for `ConclusionEvidenceSource`, `ConclusionEvidenceEntry`, and `ConclusionEvidence` in `web/src/lib/api/types.ts`, and thread `conclusion_evidence?: ConclusionEvidence | null` through `SessionEvidenceContract` so report and replay share one contract edge.
2. Extend `web/src/lib/session-evidence.ts` with defensive extract/format helpers for per-conclusion provenance rows and four-layer degradation rows, including stable Chinese copy for source availability and degradation tokens; malformed payload fragments must degrade to omission instead of throwing.
3. Wire `web/src/app/(user)/practice/[sessionId]/report/page.tsx` to render learner-facing provenance/degradation cards from `report.conclusion_evidence` and `report.evidence_degradation`, while preserving the current claim-truth, retrieval, audio-audit, and presentation-null behavior and keeping `/knowledge-check` supplemental only.
4. Update `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` with focused assertions for happy-path sales, degraded-layer copy, supplemental-request failure, and presentation-null suppression.

## Must-Haves

- [ ] The report page reads `conclusion_evidence` and `evidence_degradation` only through `session-evidence.ts` helpers.
- [ ] Presentation report fixtures still hide the new sales-only sections when the backend returns `null`.
- [ ] Rejected supplemental `getKnowledgeCheck()` calls do not hide canonical report-driven provenance/degradation copy.
  - Estimate: 2h
  - Files: web/src/lib/api/types.ts, web/src/lib/session-evidence.ts, web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx"
- [ ] **T02: Mirror the shared provenance/degradation vocabulary on replay and lock cross-page parity** — Load `safe-grow`, `react-best-practices`, `test`, and `verification-before-completion` before coding. This task mirrors the report vocabulary on replay without creating a second parser or falling back to stale report snapshots.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `GET /sessions/{id}/replay` payload | Keep existing replay error / completion-gate behavior; no report-snapshot fallback authority is introduced for the new surfaces | Existing replay loading/error state remains unchanged | Helper normalization omits malformed provenance/degradation rows while leaving the rest of replay usable |
| Optional report snapshot loaded for retry metadata | Continue to use it only for retry/fallback metadata, never for canonical provenance/degradation when replay payload provides those fields | Same as error | Ignore malformed report snapshot for the new surfaces |

## Load Profile

- **Shared resources**: existing replay render path, highlight rendering, and jsdom test runtime.
- **Per-operation cost**: zero new network calls; reuse the same helper output over three conclusion entries and four degradation layers.
- **10x breakpoint**: duplicated token-to-copy logic across replay/report would become the first drift point, so this task must keep all wording in the helper seam.

## Negative Tests

- **Malformed inputs**: missing replay `conclusion_evidence`, partial degradation layers, and stale report snapshot carrying conflicting provenance copy.
- **Error paths**: replay completion-gated errors and highlight/presentation flows must remain intact after the new section is added.
- **Boundary conditions**: happy-path sales payload, degraded-layer sales payload, and presentation payload with sales-only fields intentionally null.

## Steps

1. Wire `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` to render the shared provenance/degradation helper output from `replayData.conclusion_evidence` and `replayData.evidence_degradation`, keeping replay-specific anchor/retry/highlight flows separate and never deriving these fields from the report snapshot.
2. Extend `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` with happy-path, degraded, presentation-null, and stale-report-snapshot assertions that prove replay shows the same learner-facing vocabulary as report while still trusting replay payload truth.
3. Re-run the report and replay suites together as the slice gate so copy drift between the two pages is caught before completion.

## Must-Haves

- [ ] Replay renders the same helper-generated provenance/degradation labels as report for equivalent payloads.
- [ ] Replay never falls back to stale report-snapshot provenance/degradation when the replay contract already carries canonical fields.
- [ ] Existing replay-specific behaviors (anchor banners, retry, audio audit, presentation page evidence) continue to pass focused tests.
  - Estimate: 90m
  - Files: web/src/lib/session-evidence.ts, web/src/app/(user)/practice/[sessionId]/replay/page.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
