---
estimated_steps: 4
estimated_files: 3
skills_used: []
---

# T02: Lock miss/failure fallback and presentation safety in the focused report-page suite

Load `test` before editing assertions and keep `react-best-practices` in mind for selector/copy stability. Expand `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` with canonical report fixtures for `retrieval_facts.status="miss"` and `retrieval_facts.status="search_failed"`, plus explicit assertions that `getKnowledgeCheckMock` rejection never hides canonical retrieval truth and that presentation reports still hide the retrieval section while skipping the supplemental fetch. Adjust `web/src/app/(user)/practice/[sessionId]/report/page.tsx` or `web/src/lib/session-evidence.ts` only where these assertions reveal copy drift or malformed-guard gaps.

Failure Modes: brittle tests can accidentally couple to duplicated copy or the old diagnostics card; malformed fixtures can mask whether the page is using canonical report payload or the supplemental fetch.

Load Profile: this is still a single focused Vitest file in jsdom; the main 10x risk is selector brittleness if wording lives in multiple places instead of the shared helper seam.

Negative Tests: `miss` explanation visible, `search_failed` explanation visible, canonical retrieval still visible when `/knowledge-check` rejects, presentation path keeps retrieval section absent and `getKnowledgeCheck` uncalled.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/session-evidence.ts`
- `backend/tests/contract/test_practice_evidence_contract.py`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`

## Verification

pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
