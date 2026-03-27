# S05: 现有 admin 链路的组织化 UAT — UAT

**Milestone:** M005
**Written:** 2026-03-27T02:02:44.979Z

# S05: 现有 admin 链路的组织化 UAT — UAT

**Milestone:** M005
**Written:** 2026-03-27

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: the slice goal is to prove one real supervisor workflow on the current shipped admin surfaces. Focused backend/web regressions already guard the route contracts and UI affordances, while the live steps below verify that the same evidence vocabulary survives the full analytics → drill-in → reminder → report/replay chain.

## Preconditions

- Backend and web apps are running with the latest migrations applied.
- Tester can sign in as an admin user and also has access to a non-admin account for the RBAC check.
- The environment contains at least one user who appears in the weekly operating pack as either `本周风险成员` or `本周连续未练`, and that user has at least one completed session that can be reviewed after the supervisor action.
- The current admin routes `/admin/analytics`, `/admin/users`, and `/admin/users/{id}` are reachable.
- Canonical learner review routes `/practice/{sessionId}/report` and `/practice/{sessionId}/replay` are reachable.
- Optional enhanced-report/highlights endpoints may still return fallback noise; that is acceptable only if the canonical report/replay routes remain readable.

## Smoke Test

1. Sign in as an admin and open `/admin/analytics`.
2. Confirm the page shows the weekly operating pack section and the `导出报表` action on the current analytics route.
3. **Expected:** the page loads the weekly pack, manager lists, and export affordance without navigating to a separate acceptance or supervisor-only surface.

## Test Cases

### 1. Weekly pack drill-in carries real operating context into the current user-detail page

1. Open `/admin/analytics`.
2. In `本周风险成员` or `本周连续未练`, choose one member and click the current drill-in CTA.
3. Wait for `/admin/users/{id}` to load.
4. Inspect the source banner and the supervisor focus/reminder area.
5. **Expected:** the detail page still shows the weekly-source banner, preserves the carried `focusBucket` meaning, and—when the source is a risk user—keeps the real `focusIssueFamily` context instead of collapsing to a generic evidence-gap fallback.

### 2. Supervisor reminder/focus action can be completed on the shipped user-detail surface

1. On `/admin/users/{id}`, create or review the current supervisor intervention.
2. Trigger the reminder action from the existing page controls.
3. If the member was opened from manager-lite or another path without an explicit intervention id, use that same reminder action and let the fallback path resolve the latest open focus.
4. Refresh the page.
5. **Expected:** the same current user-detail surface persists the intervention/reminder state, shows the updated reminder status after refresh, and does not require a second manager workflow page.

### 3. Result review stays on canonical report and replay routes

1. On the same user detail page, find the intervention result or latest resolving-session card.
2. Click `查看对应统一报告` (or the equivalent report-review CTA).
3. Confirm the browser opens `/practice/{sessionId}/report`.
4. Review the top-line conclusion, main issue, and next-goal copy.
5. From the same review path, open replay for that session.
6. **Expected:** report review stays on the canonical learner report route, replay review stays on the canonical replay route, and both surfaces describe the same outcome family that the admin chain was tracking.

### 4. Weekly pack, reminder result, and report/replay keep one evidence vocabulary

1. Compare the issue family / improvement state shown in the weekly pack, the intervention result card on `/admin/users/{id}`, and the canonical report/replay conclusion for the reviewed session.
2. **Expected:** these surfaces stay semantically aligned: a risk-user drill-in should still look like the same blocker family on user detail, and the later report/replay review should explain whether that blocker improved, stayed open, or is still not judgeable instead of switching to a conflicting score vocabulary.

### 5. Export stays on the current admin analytics surface and respects the current time window

1. Return to `/admin/analytics`.
2. Change the current analytics time range if the page exposes that filter.
3. Click `导出报表`.
4. Open the downloaded CSV.
5. **Expected:** the export comes from the existing `/api/v1/admin/analytics/export` route family, reflects the currently selected analytics window, and still contains the expected sections (`系统概览`, `分数分布`, `趋势数据`, `用户排行榜`) instead of a one-off acceptance export format.

### 6. Permission boundary is still explicit on analytics, weekly pack, and export

1. Sign out and sign in as a non-admin user.
2. Attempt to open `/admin/analytics` in the browser.
3. Attempt to call `/api/v1/admin/analytics/operating-pack` and `/api/v1/admin/analytics/export` with the non-admin session.
4. **Expected:** the non-admin user cannot use the analytics page or the export/operating-pack APIs; access is rejected by the existing admin-only boundary rather than hidden behind a client-only check.

## Edge Cases

### Manager-lite fallback reminder still lands on the latest open focus

1. Start from manager-lite or a user-detail state where no explicit intervention id is present.
2. Trigger the reminder action.
3. Refresh the page and inspect the current intervention card.
4. **Expected:** the reminder is attached to the latest open focus instead of failing or creating a duplicate silent intervention.

### Inactive-streak drill-ins keep cadence semantics instead of turning into a risk-family issue

1. From `本周连续未练`, open a member on `/admin/users/{id}`.
2. Inspect the prefilled note/focus state.
3. **Expected:** the detail page preserves the inactive-streak context and cadence-oriented wording instead of incorrectly treating the user as a blocker-family risk drill-in.

### Optional enhancement failure does not invalidate the canonical report/replay review path

1. Open a resolving session report where optional enhanced-report or highlights requests are currently degraded.
2. Watch the page state and any visible fallback copy.
3. **Expected:** the canonical report still renders the main evidence conclusion, replay still remains reachable if the session is completed, and any enhancement failure is shown as explicit fallback noise rather than a blank review surface.

## Failure Signals

- `/admin/analytics` loses `导出报表` or the export no longer reflects the current analytics window.
- Weekly drill-ins lose `focusBucket` / `focusIssueFamily` context and fall back to a generic focus on `/admin/users/{id}`.
- Reminder actions only work when an explicit intervention id is present and fail for manager-lite fallback paths.
- Intervention results open a non-canonical report surface or the report/replay pages describe a conflicting outcome vocabulary.
- Non-admin users can reach the weekly pack or export endpoints.
- Optional enhanced-report/highlights failures are mistaken for canonical report/replay failure because the page no longer renders explicit fallback copy.

## Requirements Proved By This UAT

- None directly retired at the requirement ledger level; this UAT proves the slice-level admin operating chain is now organized and operationally usable on current routes.

## Not Proven By This UAT

- Multi-manager concurrency, production reminder delivery telemetry, or organization-wide adoption reporting.
- Any new admin workflow outside the current `/admin/analytics` → `/admin/users/{id}` → canonical report/replay route family.
- A separate acceptance-only export or supervisor-only report surface, because this slice intentionally proves the current shipped routes instead.

## Notes for Tester

- Treat optional enhanced-report/highlights noise as non-blocking only when the canonical unified report and replay routes remain readable.
- If the export or weekly pack check fails for a non-admin user, inspect the existing admin router dependency in `backend/src/main.py` before assuming the analytics endpoint itself regressed.
- If auto-mode still reports task-level verification failures after the commands pass, confirm the corresponding `T01/T02/T03-VERIFY.json` artifacts have been refreshed; this slice previously had stale false-fail verifier files from broken auto-discovery commands.
