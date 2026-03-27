# S04: 团队周节奏包与 cohort 问题面 — UAT

**Milestone:** M005
**Written:** 2026-03-26T14:23:40.718Z

# S04: 团队周节奏包与 cohort 问题面 — UAT

**Milestone:** M005
**Written:** 2026-03-26

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: the slice is a deterministic admin read-model plus drill-in flow. Focused backend contract/unit tests already prove the aggregation semantics and payload shape, while the live steps below verify that the same vocabulary survives on the current admin entrypoints.

## Preconditions

- Backend and web apps are running with the latest migrations applied.
- Tester can sign in as an admin user.
- The environment contains at least one week of completed sessions covering all of the following cases:
  - one member whose latest **evaluable completed** session is still fail/not-pass,
  - one member with a recent completed but **not-evaluable** session,
  - one member with a completed session that produces a **degraded** evidence signal,
  - one member whose last completed session is older than 7 days,
  - one member with enough evaluable history to appear in the **显著回升** list.
- `/admin/analytics`, `/admin/users`, and `/admin/users/{id}` are reachable on the current admin surface.

## Smoke Test

1. Sign in as admin and open `/admin/analytics`.
2. Scroll to the section titled `本周经营节奏包`.
3. **Expected:** the page shows the weekly summary cards, repeated blocker family area, department issue cards, and the three manager lists without navigating to a different admin surface.

## Test Cases

### 1. Weekly pack stays on the current evidence line and fixed weekly cadence

1. Open `/admin/analytics` with the default filters.
2. Confirm the weekly pack summary text states how many completed sessions happened this week, how many were evaluable, and how many were evidence-insufficient.
3. Change the main analytics time-range filter from `30天` to `90天`.
4. **Expected:** overview/trend widgets can change with the broader filter, but the weekly section remains `本周经营节奏包` and still speaks in the current-week cadence; the score-basis copy continues to say the average only uses evaluable completed sessions.

### 2. Repeated blocker families and department issue surfaces are visible

1. On `/admin/analytics`, locate the `反复卡点` / blocker-family area inside the weekly pack.
2. Verify at least one issue family card shows the family label plus counts for users/departments.
3. Scroll to `部门问题面`.
4. Open one department card and inspect the counts.
5. **Expected:** each department card shows total completed sessions, evaluable sessions, evidence-insufficient sessions, top issue buckets, and separate not-evaluable/degraded reason breakdowns instead of collapsing everything into one score line.

### 3. Current-risk drill-in preserves the real issue family on user detail

1. From the weekly risk list on `/admin/analytics` or `/admin/users`, click `查看并设重点` for a member in `本周风险成员`.
2. Wait for `/admin/users/{id}` to load.
3. Inspect the banner near the top of the page.
4. Inspect the supervisor-focus form.
5. **Expected:** the detail page shows `本周经营名单来源`, the badge is `本周风险成员`, the description references the same issue family that the weekly pack showed, and the `主管说明` textarea is prefilled with the carried note instead of falling back to a generic default.

### 4. Inactive and improving drill-ins keep their own bucket identity

1. From the weekly `本周连续未练` list, click `查看详情` for one member.
2. Confirm the user detail banner describes the inactive bucket rather than a risk-family issue.
3. Return to the weekly page and do the same for a member in `本周显著回升`.
4. **Expected:** inactive drill-ins talk about restoring cadence; improving drill-ins talk about consolidating the recent gain. Neither path should incorrectly inject a risk-family label or auto-convert the user into a `证据补强` focus.

### 5. Unified report and intervention-result drill-ins stay aligned with the weekly pack vocabulary

1. Open a user detail page that already has a persisted intervention result.
2. Inspect the current intervention card and its latest-result status.
3. Click `查看对应统一报告`.
4. **Expected:** the result card reads as one of `已改善 / 仍卡住 / 待判断`, and the linked report opens `/practice/{sessionId}/report` for the relevant resolving session instead of a supervisor-only shadow report.

## Edge Cases

### Latest pass should remove a user from the current-risk list

1. Use a seeded user who failed earlier in the 7-day window but whose latest evaluable completed session passed.
2. Refresh `/admin/analytics`.
3. **Expected:** the user may still contribute to historical cohort counts, but they must not appear in the current `本周风险成员` list.

### Not-evaluable sessions stay visible without polluting risk/score semantics

1. Use a seeded user whose recent completed session is `INSUFFICIENT_TURN_DATA` (or another not-evaluable reason).
2. Refresh `/admin/analytics` and inspect the weekly summary plus department breakdowns.
3. **Expected:** the session increases `证据不足` counts and reason buckets, but it does not silently lower the average score and does not by itself put the user into the `未达标` manager list.

## Failure Signals

- The weekly pack treats any old failure in the window as current risk, so members who already recovered still appear in `本周风险成员`.
- User detail drill-ins lose the issue family and fall back to a generic `evidence_gap` focus when opened from the weekly risk list.
- Department cards merge evidence-insufficient/degraded sessions into the average-score story instead of keeping them as separate diagnostics.
- The weekly pack disappears or changes semantics when the main analytics time-range filter is changed.
- Weekly report/intervention drill-ins open a non-canonical report surface instead of `/practice/{sessionId}/report`.

## Requirements Proved By This UAT

- none — this UAT proves the slice-level admin operating-pack and drill-in behavior, but it does not by itself retire a top-level product requirement.

## Not Proven By This UAT

- A full organization workflow across analytics → user drill-in → focus/reminder → report/replay review → weekly pack close-out on one real team; S05 still owns that end-to-end proof.
- Production-scale data freshness, reminder delivery outside the current admin surfaces, or any mobile/admin experience beyond the current desktop admin routes.

## Notes for Tester

- The weekly pack is intentionally fixed to a 7-day cadence even if the broader analytics widgets are switched to 30/90/all-time.
- When validating risk drill-ins, prefer seeded users whose latest evaluable completed session clearly differs from older outcomes; that makes it obvious whether the list is honoring the latest-session rule.
- If the page shows no current-risk/improving/inactive examples, confirm the seed data first rather than treating an empty state as a regression.
