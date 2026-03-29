---
estimated_steps: 4
estimated_files: 4
skills_used: []
---

# T01: Render canonical retrieval truth on the report page through shared frontend helpers

Load `react-best-practices` before coding and use `test` when adding the focused assertion. Add narrow retrieval-facts interfaces in `web/src/lib/api/types.ts`, then extend `web/src/lib/session-evidence.ts` with shared extraction / formatting helpers for retrieval status labels, latest-attempt summaries, miss/failure explanations, and bounded result-summary copy. Wire `web/src/app/(user)/practice/[sessionId]/report/page.tsx` so the sales knowledge section renders from `report.effectiveness_snapshot.retrieval_facts` first, keeps `claim_truth` separate, and treats `/knowledge-check` as supplemental only. Add one primary focused assertion in `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` that proves a retrieval hit and `weak_evidence` can coexist even when `getKnowledgeCheck` rejects.

Failure Modes: if the canonical report payload lacks `retrieval_facts`, the page must safely omit the retrieval section instead of showing stale diagnostics copy; if the optional `/knowledge-check` request fails, keep the canonical retrieval section visible; if `latest_attempt` or `result_summaries` is malformed, render only the fields that survived helper normalization.

Load Profile: this task adds no new network calls and should stay bounded to the latest attempt plus a small number of result summaries, so the first 10x breakpoint is DOM noise if the page forgets to respect the backend bounds.

Negative Tests: hit + weak_evidence coexistence, missing latest_attempt, empty result_summaries, and rejected `/knowledge-check` supplemental fetch.

## Inputs

- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `backend/tests/contract/test_practice_evidence_contract.py`

## Expected Output

- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

## Verification

pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'

## Observability Impact

Keeps the existing report-page debug/log seam meaningful by making canonical retrieval visibility diverge from supplemental `/knowledge-check` failures; future agents can inspect the focused test fixture plus the visible retrieval card to tell whether drift is in extraction, rendering, or request-gating.
