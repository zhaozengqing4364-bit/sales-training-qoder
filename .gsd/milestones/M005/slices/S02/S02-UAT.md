# S02: 系统内主管重点与提醒闭环 — UAT

**Milestone:** M005
**Written:** 2026-03-26T08:14:57.702Z

# S02: 系统内主管重点与提醒闭环 — UAT

**Milestone:** M005
**Written:** 2026-03-26

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: This slice changed both persistent admin contracts and the existing admin user-detail / manager-lite surfaces. Focused backend and web tests already prove the persistence and projection edges; this UAT confirms that a supervisor can complete the intended in-product workflow on the shipped admin surfaces.

## Preconditions

- Backend is migrated to Alembic head, including revision `20260326_1000_021`.
- Backend and web are running against the same environment.
- You can log in as an admin user.
- There is at least one learner with:
  - a visible admin user detail page,
  - at least one completed sales session with a canonical report,
  - ideally one manager-lite “未达标名单” entry so the deep-link launcher path can be exercised.
- If you want to verify the “已改善” result case, prepare a learner who already has:
  - one intervention created earlier, and
  - a later completed **evaluable** session whose main issue family shifted away from the intervention family or whose session passed.

## Smoke Test

1. Open the current admin users detail page for a learner.
2. Set a主管重点 with a note.
3. **Expected:** A new intervention card appears immediately on the same page with the chosen issue family, the note, and an initial reminder state of “未提醒” / due state of “待跟进”.

## Test Cases

### 1. Manager-lite deep link pre-fills the current user-detail intervention form

1. Open the current admin manager-lite surface that shows the “未达标名单”.
2. Pick a learner row and click **查看并设重点**.
3. Confirm the browser lands on `/admin/users/{id}` instead of a new workflow console.
4. On the detail page, verify the **主管重点** select is already set from the launcher query string.
5. Verify the **主管说明** textarea is already prefilled with the launcher note.
6. Click **设为主管重点**.
7. **Expected:**
   - A success notice appears.
   - A new intervention card is inserted on the same detail page.
   - The card shows the selected issue family and the prefilled note.
   - No separate admin workflow page or modal is required.

### 2. Supervisor can record a reminder on an existing intervention card

1. Open `/admin/users/{id}` for a learner who already has at least one intervention card.
2. Find an open intervention card with a visible **记录提醒** button.
3. Click **记录提醒**.
4. Wait for the action to complete.
5. **Expected:**
   - A success notice appears on the same page.
   - The same intervention card updates to show **提醒已发送**.
   - If the card was not already resolved, its due-state badge now reads **待提醒**.
   - The page stays on the current user detail surface; no separate reminder console opens.

### 3. Supervisor can inspect the latest linked result and drill into the authoritative report

1. Open `/admin/users/{id}` for a learner with an existing intervention and at least one later completed evaluable session.
2. Locate the intervention card.
3. Inspect the linked result block under that card.
4. Verify the result block shows one of the explicit statuses:
   - **最近结果：已改善**
   - **最近结果：仍卡住**
   - **最近结果：待判断**
5. If a linked session is shown, click **查看对应统一报告**.
6. **Expected:**
   - The intervention card explains the result in plain supervisor language.
   - The result is tied to one later completed session, not an abstract score-only judgment.
   - The report link opens `/practice/{sessionId}/report` for that linked session.
   - The report page is the same authoritative learner/supervisor report surface already used elsewhere in the product.

### 4. Current user-detail page still holds the complete in-product supervisor loop

1. Open `/admin/users/{id}` directly, without coming from manager-lite.
2. Create a new intervention from the page.
3. On the newly created card, use **记录提醒**.
4. Refresh the page.
5. **Expected:**
   - The newly created intervention is still present after refresh.
   - Its latest reminder status is preserved.
   - The workflow remains inside the existing user-detail page from create → remind → inspect.

## Edge Cases

### Latest post-intervention session is not evaluable

1. Use a learner whose latest completed session after the intervention is thin / evidence-insufficient.
2. Open the corresponding intervention card on `/admin/users/{id}`.
3. **Expected:**
   - The result block says **最近结果：待判断**.
   - The summary explains that the latest completed session does not yet provide enough evidence.
   - The UI does not falsely claim improvement or closure.

### A newer thin session exists after an earlier evaluable improvement

1. Use a learner with this sequence after intervention creation:
   - first a later completed **evaluable** session showing improvement,
   - then a newer completed **not evaluable** thin session.
2. Open `/admin/users/{id}` and inspect the same intervention card.
3. **Expected:**
   - The card still uses the latest meaningful evaluable result for the improvement judgment.
   - It does not downgrade an already proven improvement just because a thinner completed session happened later.

### No existing interventions yet

1. Open `/admin/users/{id}` for a learner with no manager interventions.
2. Scroll to the supervisor section.
3. **Expected:**
   - The page shows the explicit empty state for supervisor focus records.
   - The create form is still immediately usable.

## Failure Signals

- Clicking **查看并设重点** opens a different workflow surface or loses the intended prefilled focus/note.
- Creating a focus succeeds in the UI but the intervention disappears on refresh.
- Clicking **记录提醒** does not change the card to **提醒已发送** / **待提醒**.
- The intervention result block disappears even though the learner has later completed sessions.
- A later thin `INSUFFICIENT_TURN_DATA` session incorrectly overwrites an earlier evaluable improvement.
- **查看对应统一报告** does not open the canonical `/practice/{sessionId}/report` route.

## Requirements Proved By This UAT

- None — this UAT proves the M005/S02 roadmap slice goal on current admin surfaces, but it does not change the status of a tracked requirement in `.gsd/REQUIREMENTS.md` by itself.

## Not Proven By This UAT

- Actual external reminder delivery through email / WeCom / another notification transport.
- Automatic intervention resolution writes back into `due_state="resolved"` when a later session improves.
- Team-level cohort rollups or weekly operating summaries; those belong to later M005 slices.

## Notes for Tester

- If `/admin/users/{id}` or `/api/v1/admin/users/{id}/sessions` suddenly fails with what looks like a frontend/network problem, check Alembic first; this slice depends on the post-`20260317_2310_020` projection path and the new `manager_interventions` table migration.
- For this slice, the authoritative result linkage lives on the current user sessions/read-model path. If the intervention card result looks wrong, inspect `/api/v1/admin/users/{id}/sessions` before assuming the UI is at fault.
- The product copy deliberately keeps manager-lite as a launcher and `/admin/users/[id]` as the single supervisor authority surface. Seeing everything happen on the detail page is the expected outcome, not a missing dashboard.
