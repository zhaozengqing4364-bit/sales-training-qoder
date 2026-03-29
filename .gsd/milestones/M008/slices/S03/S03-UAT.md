# S03: 报告页检索事实可见化 — UAT

**Milestone:** M008
**Written:** 2026-03-29T19:17:39.505Z

# S03 UAT: 报告页检索事实可见化

## Preconditions
- Backend running on `localhost:3444` with Alembic at head (including M008/S01 retrieval ledger schema).
- Frontend running on `localhost:3445`.
- At least one completed **sales** session with `effectiveness_snapshot.retrieval_facts` present (retrieval hit, miss, or search_failed).
- At least one completed **PPT** session.

## Test Cases

### TC-01: Sales report shows canonical retrieval truth when retrieval hit
1. Navigate to `/practice/{salesSessionId}/report` for a session where `retrieval_facts.status === "hit"`.
2. **Expected:** A "知识检索" (or equivalent) card is visible showing:
   - Status badge labeled "命中" (hit).
   - Summary text describing the retrieval outcome.
   - Stats row: KB count ≥ 1, attempt count ≥ 1, hit count ≥ 1, hit rate > 0%.
   - If `latest_attempt` is present, its query/time copy is visible.
   - If `result_summaries` is non-empty, bounded result items are listed.
3. If the session also has `claim_truth.status === "weak_evidence"`, a separate weak-evidence note referencing retrieval should appear alongside the claim-truth section (not replacing it).

### TC-02: Sales report shows retrieval miss with explanation
1. Navigate to `/practice/{salesSessionId}/report` for a session where `retrieval_facts.status === "miss"`.
2. **Expected:** The retrieval card is visible with:
   - Status badge labeled "未命中" (miss).
   - Miss explanation text from `formatMissExplanation()` (e.g., "检索未命中 — 当前知识库中没有匹配的内容" or similar).
   - Stats showing hit_count = 0, hit_rate = 0%.

### TC-03: Sales report shows search failure with explanation
1. Navigate to `/practice/{salesSessionId}/report` for a session where `retrieval_facts.status === "search_failed"`.
2. **Expected:** The retrieval card is visible with:
   - Status badge labeled "检索失败" or equivalent.
   - Failure explanation text from `formatSearchFailedExplanation()`.
   - Stats reflecting the failure state.

### TC-04: Absent retrieval_facts omits the section gracefully
1. Navigate to `/practice/{salesSessionId}/report` for a session where `effectiveness_snapshot` has no `retrieval_facts` key.
2. **Expected:** No retrieval-truth card or section is visible. The rest of the report renders normally (scores, issue, goal, evidence).

### TC-05: `/knowledge-check` failure does not hide canonical retrieval truth
1. Open browser devtools Network tab.
2. Navigate to `/practice/{salesSessionId}/report` where `retrieval_facts` is present in the report payload.
3. Block or reject the `/api/v1/practice/sessions/{id}/knowledge-check` request.
4. **Expected:** The canonical retrieval section (TC-01 through TC-03) remains fully visible. The supplemental fetch failure does not affect the retrieval-truth card.

### TC-06: PPT report does not show retrieval section
1. Navigate to `/practice/{pptSessionId}/report` for a presentation session.
2. **Expected:** No retrieval-truth card or section is visible.
3. In Network tab, confirm that `/knowledge-check` was NOT called for this session.

### TC-07: Malformed latest_attempt does not break the page
1. Navigate to `/practice/{salesSessionId}/report` where `retrieval_facts.latest_attempt` is missing or has unexpected fields.
2. **Expected:** The retrieval status badge and summary still render. Only normalized fields from `latest_attempt` appear; missing/malformed fields are silently omitted.

## Regression Checks
- Existing report features remain intact: sales rollup cards, main issue card, next goal card, evidence section, replay deep-links, retry CTA.
- PPT report continues to show page-level issues and PPT-specific retry.

