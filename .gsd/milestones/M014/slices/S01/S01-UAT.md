# S01: 首页硬编码与空壳动作收口 — UAT

**Milestone:** M014
**Written:** 2026-04-11T14:13:26.771Z

# S01 UAT — 首页硬编码与空壳动作收口

## Preconditions
- Use a learner account that can open the dashboard homepage.
- Prepare three dashboard states (real data or mocked API fixtures are both acceptable):
  1. **First-time learner**: recommendation exists, history list empty.
  2. **Returning learner**: recommendation exists, history contains at least one completed sales/presentation session with a valid `session_id`.
  3. **Degraded history records**: history contains one record missing `session_id` and one record with `status != completed`.
- Confirm the app is running on the current branch with the shipped dashboard homepage.

## Test Case 1 — First-time learner sees a real onboarding path instead of demo CTA
1. Sign in as a learner whose dashboard history is empty and open `/`.
   - Expected: the homepage renders a real greeting for the current user and shows the onboarding title `第一次来，先这样开始`.
2. Inspect the onboarding area.
   - Expected: there are three learner-facing steps that explain the loop `先训练 → 去历史页 → 看统一报告`.
3. Click the primary training CTA from the onboarding card or recommendation card.
   - Expected: the CTA navigates to the recommendation's real training target (for example `/training` or `/training/sales`), not to `#`, a modal stub, or no-op behavior.
4. Return to the homepage and click `去历史页`.
   - Expected: navigation goes to `/history`.
5. Inspect the report step for this no-history user.
   - Expected: the report entry still routes to `/history` and explains that the learner should finish training first before reviewing the unified report.

## Test Case 2 — Returning learner gets the latest real report shortcut
1. Open the homepage for a learner with at least two completed history records that have valid session ids.
   - Expected: the onboarding title switches to `继续按这 3 步推进训练`.
2. Inspect the third onboarding step.
   - Expected: it references the latest available report (the newest completed supported session), not an older record and not a placeholder label.
3. Click the onboarding `报告入口` link.
   - Expected: navigation goes directly to `/practice/{latestSessionId}/report`.
4. Inspect each recent-record card.
   - Expected: each card offers `历史页` and, when eligible, `查看报告`; there is no `查看详情` fake action.

## Test Case 3 — Homepage stays honest for incomplete or malformed records
1. Open the homepage with one recent record missing `session_id`.
   - Expected: the record does **not** expose a clickable report link; instead it shows disabled copy explaining that the session id is missing and the learner should verify via history.
2. Open the homepage with one in-progress recent record.
   - Expected: the record shows a disabled `报告生成中` state with copy explaining that the learner must wait until completion/evidence generation finishes.
3. Attempt to activate the disabled report buttons.
   - Expected: they are not clickable links and do not navigate anywhere.

## Test Case 4 — Fake homepage affordances remain removed
1. Inspect the homepage header, recommendation area, onboarding cards, and recent-record section.
   - Expected: there is no learner-visible `导出报告`, `设定目标`, or `分享分析` button/link anywhere on the homepage.
2. Inspect the filter affordance near recent records.
   - Expected: the only filter-related action is explicit guidance plus `去历史页筛选`, which navigates to `/history`.
3. Confirm there is no fake filter modal, no `应用筛选` button, and no decorative chips that do nothing.
   - Expected: filtering is clearly delegated to the history page.

## Test Case 5 — Version badge dialog truthfully summarizes live entrypoints
1. Click the homepage version badge.
   - Expected: a dialog opens describing the **current usable entrypoints** rather than static release-note marketing copy.
2. Verify the dialog body.
   - Expected: it summarizes the current recommendation, history/report availability, and the fact that the homepage only keeps real loop actions.
3. Click `稍后再看`.
   - Expected: the dialog dismisses cleanly.
4. Reopen the version dialog and click the primary CTA.
   - Expected: the dialog dismisses and routes to the current recommendation target path.

## Edge Cases
- If history API loading fails entirely, the homepage should degrade to the empty-state learner loop: no report shortcut is shown, `开始训练` remains available, and the history-filter deep link still points to `/history`.
- If the latest recent record is a supported completed session but an older record is newer-looking only because of malformed timestamps, the homepage must still choose the newest valid report shortcut according to the persisted `start_time` ordering used in the shipped logic.
- If a recent record belongs to an unsupported scenario type, the homepage must not guess a report route; it should keep the learner on `/history` with disabled explanatory copy.

