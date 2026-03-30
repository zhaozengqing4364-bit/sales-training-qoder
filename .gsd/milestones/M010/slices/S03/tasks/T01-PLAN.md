---
estimated_steps: 23
estimated_files: 4
skills_used: []
---

# T01: Add shared conclusion-evidence helpers and render canonical provenance/degradation on the report page

Load `safe-grow`, `react-best-practices`, `test`, and `verification-before-completion` before coding. This task establishes the frontend authority seam for S03 and immediately uses it on the learner report page; do not parse `conclusion_evidence` or `evidence_degradation` directly in the page component.

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

## Inputs

- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `backend/tests/contract/test_conclusion_evidence_parity.py`

## Expected Output

- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx"

## Observability Impact

- Signals added/changed: helper-driven provenance/degradation sections give the report page a visible canonical read seam distinct from optional knowledge-check diagnostics.
- How a future agent inspects this: run the focused report-page suite and compare the visible provenance/degradation cards against the report payload fixture.
- Failure state exposed: if copy disappears or drifts, the failure localizes to helper normalization vs report-page wiring instead of the backend contract.
