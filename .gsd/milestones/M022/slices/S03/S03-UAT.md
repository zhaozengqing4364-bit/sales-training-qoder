# S03: Manager calibration 与 admin truth surfaces 收口 — UAT

**Milestone:** M022
**Written:** 2026-04-14T08:17:33.375Z

# S03 UAT — Manager/admin truth surfaces use canonical evidence instead of fake stats

## Preconditions
- Use an admin account that can open `/admin`, `/admin/analytics`, and `/admin/users/[id]`.
- Seed or log into an environment with at least one completed evaluable session so analytics and manager-lite have real data to read.
- Have at least one learner with a visible progress history on `/admin/users/[id]`.

## Test Case 1 — Admin home is an honest inventory, not a fake ops dashboard
1. Open `/admin`.
   - Expected: the page shows the live effectiveness area sourced from recent training data, and the page copy explains that only current evidence-backed surfaces should be treated as real.
2. Scan the rest of the home page.
   - Expected: the old fake operator story is gone — no hardcoded resource/storage/user/session metrics, no fake alert feed, no fake activity feed, no fake config snapshot, and no fake announcement modal.
3. Inspect the lower cards/sections on the home page.
   - Expected: cards without backend authority are clearly presented as inventory / guidance / jump-off surfaces rather than live numbers.
4. Use the provided links from the home page.
   - Expected: they route into the current real management surfaces (`/admin/users`, `/admin/analytics`, `/admin/logs`) instead of opening pretend operator actions.

## Test Case 2 — Team summary and manager-lite stay on real analytics evidence
1. Open `/admin/analytics`.
   - Expected: overview/trend/team-summary surfaces render from real analytics payloads, not from homepage-only placeholder numbers.
2. Locate the `manager-lite` panel.
   - Expected: the panel shows supervisor triage lists such as not-passed / follow-up / trend-oriented entries, or a truthful empty state if no data exists.
3. Compare the panel and surrounding analytics copy.
   - Expected: the page language treats these lists as evidence-backed management views and does not claim a separate hidden manager-only score system.
4. Trigger any available drill-in link from manager-lite.
   - Expected: the target is an existing user-detail/report-oriented surface, not a fake or disconnected cockpit.

## Test Case 3 — User detail drill-in matches the same training fact line
1. Open one learner detail page from analytics or directly via `/admin/users/[id]`.
   - Expected: the page shows progress/history/intervention context grounded in the learner’s real completed sessions.
2. Inspect session previews, progress copy, and intervention-related sections.
   - Expected: the supervisor-readable summary can be tied back to real completed-session evidence rather than an unexplained local total score.
3. Compare the user-detail interpretation with the corresponding manager-lite / analytics context.
   - Expected: the same learner should not look healthy in one place and failing in another due to separate fake rollups; the surfaces should tell one consistent story.

## Test Case 4 — Edge case: surfaces with no authority stay downgraded instead of pretending to be live
1. Return to `/admin` and review any home-page section that does not currently have a backed API authority.
   - Expected: the UI stays explicit that the surface is inventory-only / future work / route guidance.
2. Verify that no homepage section claims to be a complete manager OS or real-time operations center unless it actually links to a current evidence-backed page.
   - Expected: the product boundary remains honest even when data is sparse or missing.

## Edge Cases
- If analytics or manager-lite have no rows, the page must show a truthful empty state rather than synthetic "healthy" numbers.
- If a future change adds new admin-home cards, they must remain downgraded until a real backend authority exists and the same evidence line is documented in tests and planning docs.
- If a learner has degraded or partial evidence, admin analytics and user detail should surface that degraded state instead of silently normalizing it into a fake complete score.

