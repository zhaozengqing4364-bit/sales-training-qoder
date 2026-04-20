# S03: 报告页检索事实可见化

**Goal:** 让学员在现有 `/practice/{sessionId}/report` 页面上直接看到 canonical retrieval truth：知识库绑定、最近一次检索事实、命中/未命中/失败解释，以及它与 `claim_truth` 弱证据提示的关系；页面不能再依赖 supplemental `/knowledge-check` 请求成功才显示这些事实。
**Demo:** After this: 打开现有 report 页即可看到该 session 的 KB 绑定、最近检索事实与对应的 hit/miss/failure/weak-evidence 说明。

## Tasks
- [x] **T01: Rendered canonical retrieval truth on the report page from `effectiveness_snapshot.retrieval_facts` with focused regression coverage.** — Load `react-best-practices` before coding and use `test` when adding the focused assertion. Add narrow retrieval-facts interfaces in `web/src/lib/api/types.ts`, then extend `web/src/lib/session-evidence.ts` with shared extraction / formatting helpers for retrieval status labels, latest-attempt summaries, miss/failure explanations, and bounded result-summary copy. Wire `web/src/app/(user)/practice/[sessionId]/report/page.tsx` so the sales knowledge section renders from `report.effectiveness_snapshot.retrieval_facts` first, keeps `claim_truth` separate, and treats `/knowledge-check` as supplemental only. Add one primary focused assertion in `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` that proves a retrieval hit and `weak_evidence` can coexist even when `getKnowledgeCheck` rejects.

Failure Modes: if the canonical report payload lacks `retrieval_facts`, the page must safely omit the retrieval section instead of showing stale diagnostics copy; if the optional `/knowledge-check` request fails, keep the canonical retrieval section visible; if `latest_attempt` or `result_summaries` is malformed, render only the fields that survived helper normalization.

Load Profile: this task adds no new network calls and should stay bounded to the latest attempt plus a small number of result summaries, so the first 10x breakpoint is DOM noise if the page forgets to respect the backend bounds.

Negative Tests: hit + weak_evidence coexistence, missing latest_attempt, empty result_summaries, and rejected `/knowledge-check` supplemental fetch.
  - Estimate: 2h
  - Files: web/src/lib/api/types.ts, web/src/lib/session-evidence.ts, web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - Verify: pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
- [x] **T02: Locked report-page regression coverage for canonical retrieval miss/search_failed fallback copy and PPT retrieval safety.** — Load `test` before editing assertions and keep `react-best-practices` in mind for selector/copy stability. Expand `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` with canonical report fixtures for `retrieval_facts.status="miss"` and `retrieval_facts.status="search_failed"`, plus explicit assertions that `getKnowledgeCheckMock` rejection never hides canonical retrieval truth and that presentation reports still hide the retrieval section while skipping the supplemental fetch. Adjust `web/src/app/(user)/practice/[sessionId]/report/page.tsx` or `web/src/lib/session-evidence.ts` only where these assertions reveal copy drift or malformed-guard gaps.

Failure Modes: brittle tests can accidentally couple to duplicated copy or the old diagnostics card; malformed fixtures can mask whether the page is using canonical report payload or the supplemental fetch.

Load Profile: this is still a single focused Vitest file in jsdom; the main 10x risk is selector brittleness if wording lives in multiple places instead of the shared helper seam.

Negative Tests: `miss` explanation visible, `search_failed` explanation visible, canonical retrieval still visible when `/knowledge-check` rejects, presentation path keeps retrieval section absent and `getKnowledgeCheck` uncalled.
  - Estimate: 90m
  - Files: web/src/app/(user)/practice/[sessionId]/report/page.test.tsx, web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/lib/session-evidence.ts
  - Verify: pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
