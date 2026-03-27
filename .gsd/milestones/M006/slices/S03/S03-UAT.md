# S03: 主管 workflow service seam 抽取 — UAT

**Milestone:** M006
**Written:** 2026-03-27T10:38:56.602Z

# S03: 主管 workflow service seam 抽取 — UAT

**Milestone:** M006  
**Written:** 2026-03-27

## UAT Type

- UAT mode: focused supervisor-workflow regression + localhost authority-surface proof
- Why this mode is sufficient: S03 intentionally keeps the existing admin routes and UI contract stable while moving workflow rules behind dedicated write/read seams. The acceptance question is whether supervisors can still create / remind / read intervention results from the current `/admin/users/[id]` surface with the same semantics after extraction.

## Preconditions

- Repo root: `/Users/zhaozengqing/github/销售训练qoder`
- Backend dependencies installed in `backend/venv`; frontend dependencies installed in `web/node_modules`.
- For browser proof, run:
  - `cd backend && PYTHONPATH=src venv/bin/uvicorn main:app --port 3444`
  - `cd web && pnpm exec next dev -p 3445`
- Use an admin session. In local development, `POST http://localhost:3444/api/v1/auth/dev-login` may be used first; the dev user must have admin role if you rely on that shortcut.
- Seed data should include:
  - learner `0a0af6d4-d7cb-4ec8-be9f-f44288b10be2` (`S03 验证学员`) with one newer intervention that has **no** follow-up completed session yet, so the pending branch can be inspected live,
  - at least one earlier completed session for the same learner so the page still has existing session-report drill-ins on the session table,
  - automated fixture coverage for an intervention that **does** have a later evaluable completed session and for a later thin non-evaluable session.
- Automated proof commands available from repo root:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py tests/integration/test_admin_users_api.py`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'`

## Smoke Test

1. Run the backend verification command.
2. **Expected:** all 23 focused backend tests pass, including route-to-service delegation and latest-evaluable intervention-result resolution.
3. Run the web verification command.
4. **Expected:** the focused `/admin/users/[id]` page suite passes, including the pending-result/no-report-link branch.
5. Start backend and web on `localhost:3444` and `localhost:3445`.
6. Log in as an admin, then open `http://localhost:3445/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2`.
7. **Expected:** the page loads successfully and shows `主管重点与提醒` without console/network failures.

## Test Cases

### 1. Create a supervisor focus from the current user-detail page

1. Open `/admin/users/{id}` for the seeded learner.
2. In `主管重点与提醒`, choose a focus family such as `证据补强重点`.
3. Enter a concrete note, e.g. `先补 ROI 与客户案例证据。`.
4. Click `设为主管重点`.
5. **Expected:** the page shows success feedback such as `主管重点已记录，可继续发送提醒。`.
6. **Expected:** the new intervention card appears on the same page with the selected focus family and note.
7. **Expected:** API-side contract remains stable — no new response envelope or route was required after the service extraction.

### 2. Send a reminder against the latest open intervention

1. On an existing intervention card, click `记录提醒`.
2. **Expected:** the page shows success feedback such as `已记录提醒，当前重点仍保持在主管视图中。`.
3. **Expected:** the card still represents the same intervention, but reminder state is updated to sent and the note remains intact.
4. Repeat the reminder flow through the backend regression path that omits `intervention_id`.
5. **Expected:** the latest open intervention for that learner is updated, proving the extracted write service still owns the manager-lite reminder shortcut.

### 3. Read an improved or still-blocked result through the shared read-side seam

1. Use the focused backend suite fixture that creates an intervention followed by later completed sessions.
2. Inspect `/api/v1/admin/users/{id}/sessions`.
3. **Expected:** `manager_intervention_results` is present on the current authority path; no second supervisor-only read route was introduced.
4. **Expected:** when there is a later evaluable completed session after intervention creation, that session is used to derive the result.
5. **Expected:** if a later thin non-evaluable completed session also exists, it does **not** override the earlier evaluable outcome.
6. **Expected:** improved/still-blocked/not-evaluable semantics continue to carry `session_id`, `main_issue`, `next_goal`, and report drill-in eligibility exactly as before.

### 4. Pending result branch stays visible without inventing a report drill-in

1. Log in locally as admin and open `http://localhost:3445/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2`.
2. Find the latest intervention card.
3. **Expected:** the card shows `最近结果：等待新训练`.
4. **Expected:** the explanation text reads `主管重点建立后，还没有新的已完成训练可用于判断结果。`.
5. Search the same card for `查看对应统一报告`.
6. **Expected:** no such link is rendered for the pending branch.
7. Reload the page.
8. **Expected:** the same waiting-state semantics remain visible, confirming the behavior is read-side contract, not local transient state.

### 5. Resolving-session guard still rejects mismatched users

1. Through the backend update path, attempt to set `resolving_session_id` on an intervention using a session that belongs to a different learner.
2. **Expected:** the request fails with the existing mismatch error (`[INTERVENTION_RESOLVING_SESSION_USER_MISMATCH]`).
3. Repeat by trying to mark an intervention resolved without providing a resolving session.
4. **Expected:** the request fails with `[INTERVENTION_RESOLVING_SESSION_REQUIRED]`.
5. **Expected:** the service extraction did not relax these lifecycle guards.

## Edge Cases

### Latest evaluable result wins over a later thin non-evaluable session

1. Use the focused backend regression fixture that places an evaluable completed session after intervention creation and then a later non-evaluable completed session.
2. Inspect `manager_intervention_results`.
3. **Expected:** the outcome still points at the evaluable session and keeps the meaningful improved/still-blocked conclusion, rather than regressing to a generic `待判断` / `not_evaluable` state.

### Pending branch must not reuse a pre-intervention report

1. Open a learner page where the latest intervention is newer than all completed sessions.
2. Inspect the intervention card.
3. **Expected:** the page stays on the pending branch and does not link to any earlier `/practice/{sessionId}/report` route, because no post-intervention completed evidence exists yet.

## Failure Signals

- `/api/v1/admin/interventions` handlers regain workflow logic and stop delegating to the extracted service seam.
- `/api/v1/admin/users/{id}/sessions` starts choosing the last completed session indiscriminately instead of the latest evaluable completed session after intervention creation.
- The pending branch renders a `查看对应统一报告` link even though no post-intervention completed session exists.
- Reminder or resolving-session state transitions drift from the existing create/update/remind contract.
- `/admin/users/[id]` shows console/network failures or silently loses the supervisor result card after page reload.

## Requirements Proved By This UAT

- None directly change status in this slice. S03 preserves and hardens the supervisor workflow seam on already-validated admin surfaces.

## Not Proven By This UAT

- Asset registry / adapter seam planned for S04.
- Full shared admin read-model regression closure planned for S05.

## Notes for Tester

- Keep frontend and backend on the same loopback host (`localhost` ↔ `localhost`, not `localhost` ↔ `127.0.0.1`) during browser proof; otherwise host-only auth cookies can create fake login/permission noise.
- If you use the local dev-login shortcut for browser proof, ensure the dev user has admin role before judging `/admin/users/[id]` access behavior.
- The acceptance bar is semantic preservation plus seam extraction: supervisors should still create, remind, and inspect intervention outcomes from the current user-detail page, but the route handlers and HistoryService should no longer own the underlying workflow rules themselves.
