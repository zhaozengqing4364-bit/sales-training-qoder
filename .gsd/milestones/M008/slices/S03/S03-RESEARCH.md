# M008: 检索事实链收口 — S03 Research

**Date:** 2026-03-28

## Summary

S03 is a **light frontend closure slice**. S02 already did the risky work: the canonical report payload now carries `effectiveness_snapshot.retrieval_facts`, and `/knowledge-check` returns the same `retrieval_facts` object for completed sales sessions. What is still missing is the learner-visible rendering on `/practice/{sessionId}/report`.

This slice primarily supports the user-visible side of **R027 / R028** on top of the already-established retrieval-truth parity: the report page should explain KB binding, the latest retrieval attempt, hit/miss/failure status, and how that differs from the existing `claim_truth` weak-evidence line.

The existing report page still renders the old flat `knowledgeCheck` card only. It fetches `/report` first, then separately fetches `/knowledge-check`, and it hides the whole knowledge section when that second request fails. That is now the main drift risk, because the canonical report payload already contains the same retrieval truth.

## Recommendation

Keep S03 **frontend-only** unless implementation uncovers a real contract gap.

Recommended approach:

1. **Treat `report.effectiveness_snapshot.retrieval_facts` as the primary source** for report-page retrieval truth.
2. **Add shared extraction / wording helpers in `web/src/lib/session-evidence.ts`**, not page-local formatting. This follows the existing learner-facing wording seam and project knowledge that shared report/replay/history wording should come from `session-evidence.ts`.
3. **Do not collapse retrieval status into claim-truth status.** `retrieval_facts.status="hit"` can legitimately coexist with `claim_truth.status="weak_evidence"` (S02 contract already locks this). The UI should show retrieval success and evidence weakness as two related but distinct facts.
4. **Do not block the new UI on `/knowledge-check` succeeding.** If the existing extra fetch remains for legacy counters, it should be supplemental only. The page already has enough canonical data from `/report` to render the slice outcome.

This matches the loaded skills:
- **react-best-practices**: avoid unnecessary client-side dependency on a second request when the canonical route already carries the needed data.
- **fastapi-python**: preserve the existing typed contract and route family; no new route or backend schema is needed for S03.

## Implementation Landscape

### Primary files

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - Current report page.
  - Loads unified report first, then separate `getKnowledgeCheck(sessionId)` in a later `useEffect`.
  - The current knowledge section is still the old flat card (`status`, `summary`, counts, `last_query`, `recent_queries`).
  - Presentation sessions already skip the knowledge-check branch; keep that behavior.
  - Natural seam: replace or extend the current knowledge card so it can render from report-derived retrieval truth, with `/knowledge-check` as optional supplement only.

- `web/src/lib/session-evidence.ts`
  - Existing shared wording/extraction seam for learner-facing evidence (`claim_truth`, `main_issue`, `next_goal`, presentation degraded notes).
  - Best place to add:
    - `extractSessionRetrievalFacts(...)`
    - retrieval status label / tone mapping
    - formatting helpers for miss/failure explanations and latest-attempt summaries
  - This is the right authority seam; do not hardcode retrieval copy inside `page.tsx`.

- `web/src/lib/api/types.ts`
  - `KnowledgeCheckDiagnostics` currently has only the legacy flat fields typed; no `retrieval_facts` field is declared even though backend now returns it.
  - `SessionEvidenceContract.effectiveness_snapshot` remains `Record<string, unknown> | null`, so the lowest-risk change is to add exported retrieval-facts interfaces/types and parse from the open snapshot via helper, similar to the existing claim-truth pattern.
  - Avoid trying to fully type the whole `effectiveness_snapshot` object for this slice.

- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - Current focused report tests default `getKnowledgeCheckMock` to rejected in `beforeEach`.
  - There are no retrieval-facts assertions yet.
  - This default failure case is useful: it can prove the report page still shows retrieval facts from canonical `/report` even when the supplemental `/knowledge-check` request is unavailable.
  - Existing presentation tests already lock that the sales-only knowledge section stays hidden for PPT reports.

### Backend/reference files (should be read-only for S03 unless a real gap appears)

- `backend/src/common/conversation/runtime_diagnostics.py`
  - Canonical retrieval normalizer already exists: `build_retrieval_facts(...)`.
  - `build_session_runtime_diagnostics(...)` already passes through `retrieval_facts` for completed sessions.

- `backend/src/common/conversation/session_evidence.py`
  - `SessionEvidenceService.build_projection()` already overlays `retrieval_facts` into the report projection for completed sales sessions.

- `backend/tests/contract/test_practice_evidence_contract.py`
  - Already proves `/report` and `/knowledge-check` return identical `retrieval_facts` and that retrieval truth is independent from `claim_truth`.
  - Useful as design constraint, not as the main S03 verification target.

### Natural task seams

1. **Type + helper seam**
   - Add retrieval-facts TS types and extraction/format helpers.
   - Keep the open-ended `effectiveness_snapshot` contract; parse through helpers instead of widening every report type.

2. **Report-page rendering seam**
   - Update the sales report knowledge section to render:
     - KB binding
     - retrieval status/summary
     - latest attempt query / mode / result count
     - result summaries (bounded snippets / source KB names)
     - miss/failure explanation
     - weak-evidence note from `claim_truth` when relevant
   - Preserve presentation skip path.

3. **Focused test seam**
   - Add page tests for sales retrieval-facts rendering.
   - Lock the “report payload still shows retrieval truth even if `getKnowledgeCheck` fails” behavior.

## Verification Approach

Primary verification should stay frontend-focused:

- `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`

Recommended new assertions:

1. **Hit + weak_evidence coexistence**
   - report payload contains `effectiveness_snapshot.retrieval_facts.status = "hit"`
   - report payload also contains `claim_truth.status = "weak_evidence"`
   - page shows both retrieval success and the separate weak-evidence note.

2. **Miss / failure explanations**
   - `retrieval_facts.status = "miss"` shows the miss explanation.
   - `retrieval_facts.status = "search_failed"` shows the failure explanation.

3. **Supplemental fetch failure does not hide canonical retrieval truth**
   - keep `getKnowledgeCheckMock.mockRejectedValue(...)`
   - report payload still renders retrieval facts from `effectiveness_snapshot`.

4. **Presentation path unchanged**
   - existing PPT tests should keep proving the knowledge section stays hidden and `getKnowledgeCheck` is skipped.

Avoid making `tsc --noEmit` the acceptance gate for this slice; project knowledge already records unrelated noise in the web typecheck path.

## Constraints

- Stay on the existing shipped route family. No new route, no debug panel, no audit console.
- Keep retrieval truth **sales-only** on the report page. Presentation reports should remain unchanged.
- Do not invent a new “retrieval weak evidence” field. Weak evidence still comes from `claim_truth`, not `retrieval_facts`.
- Prefer the smallest reversible change: frontend read-side wiring and wording reuse, not backend reshaping.

## Common Pitfalls

- **Do not make the card depend solely on `knowledgeCheck`.** That recreates page-level drift even though `/report` already has the canonical retrieval truth.
- **Do not duplicate copy in `page.tsx`.** Put learner-facing retrieval wording in `web/src/lib/session-evidence.ts`.
- **Do not merge retrieval and claim-truth into one status.** A hit can still be weak evidence; the UI should explain both.
- **Do not widen `SessionEvidenceContract.effectiveness_snapshot` into a massive typed object for this slice.** Add narrow retrieval-facts types and parse from the open snapshot.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI / backend contract | `fastapi-python` | already available |
| React / Next.js report page | `react-best-practices` | already available |

## Planner Notes

This slice does **not** need another backend proof task unless implementation discovers that the report payload consumed by the page is missing fields that S02 contract tests claimed were present. The default plan should assume:

- one shared helper/types task,
- one report-page rendering task,
- one focused report-page test task.

If you want the lowest-risk implementation path, keep the existing `/knowledge-check` fetch for now but downgrade it to optional/supplemental data; make the user-visible retrieval section render from the canonical `/report` payload first.