# S03 — Research

**Date:** 2026-03-30

## Summary

S03 is a **frontend read-side slice**, not another contract-design slice. R027 and R028 are already satisfied on the backend: report, replay, and knowledge-check now expose the same `conclusion_evidence` and `evidence_degradation` payloads from the projection-backed authority seam. The remaining gap is that the web layer still renders the older evidence surfaces (`claim_truth`, `retrieval_facts`, `evidence_completeness`, `audio_audit`) and does **not** consume the new provenance bundle at all.

The concrete drift is visible in the current web files:
- `web/src/lib/api/types.ts` already declares `EvidenceDegradation`, but there is **no** `ConclusionEvidence` type and no `conclusion_evidence` field on the shared web contracts.
- `web/src/lib/session-evidence.ts` formats claim-truth, retrieval, completeness, and presentation degradation, but has **no helper** for `conclusion_evidence` or the four-layer `evidence_degradation` taxonomy.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` renders the claim-truth card and canonical retrieval section from `report.effectiveness_snapshot`, plus audio audit and completeness notes, but never reads `report.conclusion_evidence` or `report.evidence_degradation`.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` renders claim-truth, completeness, learning evidence, and audio audit, but likewise never reads `replayData.conclusion_evidence` or `replayData.evidence_degradation`.

That means S03 should stay small and follow D128 exactly: **add shared web parsing/wording in `session-evidence.ts`, then wire report and replay to those helpers without inventing page-local truth derivation.**

## Recommendation

Treat S03 as **two read seams plus one verification seam**:

1. **Shared web contract + helpers first**
   - Add typed `conclusion_evidence` support to `web/src/lib/api/types.ts`.
   - Add defensive extract/format helpers to `web/src/lib/session-evidence.ts` for:
     - per-conclusion provenance (`main_issue`, `next_goal`, `claim_truth`)
     - per-source availability (`retrieval_source`, `transcript_source`, `audio_source`)
     - layered degradation (`retrieval`, `transcript`, `audio`, `enhanced_report`)
   - Keep presentation sessions as `null`/hidden, matching backend semantics from S01/S02.

2. **Report page second**
   - Keep the current canonical claim-truth / retrieval cards.
   - Add learner-facing provenance/degradation rendering sourced from the new shared helpers.
   - Do **not** move authority to the supplemental `getKnowledgeCheck()` request. That side fetch already exists for extra retrieval diagnostics; S03 should keep it as optional context only.

3. **Replay page third**
   - Mirror the same shared provenance/degradation vocabulary on replay.
   - Keep replay-specific concerns (deep links, anchors, learning evidence, PPT page state) separate from the new evidence rendering.

This is a **light/targeted slice**. No new architecture is needed. The main risk is frontend contract drift, not backend uncertainty.

## Implementation Landscape

### Key Files

- `web/src/lib/api/types.ts`
  - Current web contract seam.
  - Already has `EvidenceDegradation` and threads `evidence_degradation` through `SessionEvidenceContract` and `KnowledgeCheckDiagnostics`.
  - Missing the parallel `conclusion_evidence` type and missing that field on the shared frontend contract.
  - Because `PracticeSessionReport` and `ReplayData` extend `SessionEvidenceContract`, this is the right place to add the new type once and fan it out safely.

- `web/src/lib/session-evidence.ts`
  - Existing anti-drift seam for learner-facing evidence wording.
  - Today it owns extraction/formatting for `claim_truth`, `retrieval_facts`, `evidence_completeness`, presentation degraded copy, issue/goal labels.
  - There are **no tests for this helper file today**, so the safest way to land S03 is to keep helper logic modest and verify it through the existing page tests.
  - This is where S03 should normalize backend dict payloads into safe frontend read models instead of teaching each page to parse nested evidence structures.

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - Current report evidence rendering seam.
  - Already renders:
    - claim-truth card
    - retrieval-facts card
    - completeness / presentation degraded banners
    - audio audit
    - replay deep-link hints
  - Also still loads `api.sessions.getKnowledgeCheck(sessionId)` for supplemental retrieval diagnostics; tests already assert the report page stays correct even when that call fails.
  - S03 should extend the canonical report payload rendering here, not add a second evidence authority path.

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
  - Current replay rendering seam.
  - Already renders:
    - claim-truth card
    - completeness / presentation degraded notes
    - learning evidence
    - audio audit
    - replay deep-link / presentation page notices
  - Missing any learner-facing surface for `conclusion_evidence` or the new four-layer degradation taxonomy.

- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - Strong existing contract-style page test seam.
  - Already asserts canonical report payload wins over failed supplemental knowledge-check calls, and covers claim-truth/retrieval/audio/presentation branches.
  - Best place to lock report-side provenance/degradation rendering without creating a new harness.

- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - Existing replay behavior seam.
  - Already proves replay trusts the canonical projection over stale report snapshots.
  - Best place to add parity assertions that replay shows the same provenance/degradation vocabulary as report for the same backend payload.

### Backend Files To Read, Not Rebuild

These are already the authority seam. S03 should consume them, not reinterpret them:
- `backend/src/common/conversation/schemas.py` — replay response already declares `conclusion_evidence` and `evidence_degradation`
- `backend/src/common/db/schemas.py` — report schema already includes both fields
- `backend/tests/unit/test_session_evidence_service.py` — documents the exact backend shape:
  - `conclusion_evidence.main_issue|next_goal|claim_truth.retrieval_source|transcript_source|audio_source`
  - `evidence_degradation.retrieval|transcript|audio|enhanced_report` with `status`, `token`, `explanation`
- `backend/tests/contract/test_conclusion_evidence_parity.py` — route-family parity cases already covered on the backend; frontend should mirror these scenarios in mocked page payloads

### Natural Task Split

1. **T1 — Web contract + shared helper layer**
   - `web/src/lib/api/types.ts`
   - `web/src/lib/session-evidence.ts`
   - Goal: make the new backend fields available and human-readable in one place.

2. **T2 — Report page rendering**
   - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
   - `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
   - Goal: render provenance + degradation on report without disturbing existing claim-truth / retrieval / replay deep-link behavior.

3. **T3 — Replay page rendering**
   - `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
   - `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
   - Goal: mirror the same read model and wording on replay while preserving replay-specific UX.

## What To Build First

Build the **helper/type seam first**.

Reason:
- It is the only real anti-drift seam on the frontend.
- D128 explicitly says provenance/degradation must render through `web/src/lib/session-evidence.ts`, not page-local heuristics.
- If report and replay each start parsing `conclusion_evidence` independently, S03 will recreate the same drift M010 is trying to close.

After that, report is the safer first page to update because it already renders the richer canonical evidence stack and has stronger tests around “canonical payload beats fallback requests.” Replay should then mirror that same helper output.

## Verification Approach

Use focused repo-root commands only. Do **not** rely on the repo-wide frontend typecheck as the acceptance gate; S02 already documented unrelated pre-existing `tsc` failures outside this slice.

Primary verification:
- `npm --prefix web test -- --run "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx" "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`

Recommended assertions to add:
- report renders learner-facing provenance for all three canonical conclusions from `report.conclusion_evidence`
- report renders four-layer degradation copy from `report.evidence_degradation`
- replay renders the same provenance/degradation copy for the same mocked payload
- presentation payloads still suppress these sales-only surfaces when backend returns `null`
- report still remains correct if the supplemental `getKnowledgeCheck()` request fails
- replay still prefers replay payload over stale report snapshot when both are present

Optional targeted typecheck on touched files if the executor wants an extra signal, but do not block slice completion on repo-wide unrelated errors.

## Constraints

- **Do not create a second frontend truth source.** Shared helper parsing belongs in `web/src/lib/session-evidence.ts`.
- **Do not promote `getKnowledgeCheck()` into the authority path for provenance.** Report already uses that request as supplemental context only.
- **Keep presentation sessions hidden/null for the new surfaces.** Backend contract intentionally returns `conclusion_evidence: null` and `evidence_degradation: null` for presentation.
- **Preserve existing claim-truth / retrieval / audio audit cards unless there is a direct collision.** S03 is additive learner-facing rendering, not a report page redesign.
- **Prefer the minimum safe change**, per `safe-grow`: one issue, smallest blast radius, immediate verification.
- **Avoid page-local derivation and duplicated parsing**, per D128 and the existing helper seam.

## Common Pitfalls

- **Adding raw backend dict access directly in pages** — this will duplicate null checks and token mapping between report and replay.
- **Overwriting the existing claim-truth / retrieval sections** — those cards already prove the canonical report payload is trustworthy and are covered by tests.
- **Using knowledge-check as the source of degradation wording on report** — the route already exists, but S03’s authoritative fields are on report/replay payloads themselves.
- **Forgetting presentation-null behavior** — the backend contract is sales-only for these new fields in M010.
- **Trying to verify with repo-wide `tsc` only** — known unrelated failures make that a noisy gate for this slice.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js frontend rendering | `react-best-practices` | preinstalled |
| Single-item low-blast-radius iteration in this repo | `safe-grow` | repo-local |

## Notes For Planner

This slice is ready to decompose immediately. The planner does **not** need more backend exploration.

The critical fact is simple: **the backend payloads are already correct; the web layer does not read them yet.**

Plan around a shared helper/type task first, then one report task, then one replay task, with page tests as the proof seam.