# S05: 现有 admin 链路的组织化 UAT

**Milestone:** M005
**Written:** 2026-03-27

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: this slice needs one real admin workflow proof on the shipped routes, but it also depends on the focused regression pack from T01 staying green. The automated pack confirms the analytics/users/interventions surfaces still hold their contract, and the live browser path below proves the same chain works end to end on the current admin UI.

## Preconditions

- Backend is running on `http://127.0.0.1:3444` and web is running on `http://127.0.0.1:3445`.
- `cd backend && venv/bin/alembic upgrade head` has been applied successfully.
- Tester is logged in as an admin user on the current web shell.
- The environment contains the seeded S03 verification records used by the current admin routes:
  - risk user: `S03 验证学员` (`/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2`)
  - latest evaluable completed session: `1398bea9-c25a-454f-ad1c-f645edcb3350`
  - latest evidence-insufficient completed session: `eda38292-9b64-4a8a-a271-c8f237477e9c`
- Supporting T01 regression pack was re-run from repo-root-safe commands before this UAT:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/integration/test_admin_users_api.py backend/tests/integration/test_admin_interventions_api.py`
  - `npm --prefix web test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'`

## Live Workflow Covered

### 1. Weekly operating view on the current analytics route

1. Open `/admin/analytics`.
2. Confirm the page renders `数据分析` and the `本周经营节奏包` section on the same screen.
3. Inspect the manager-lite area inside the weekly pack.
4. **Observed:** the live weekly pack exposed the current risk / inactive / improving lists on the existing analytics route, including a risk entry for `S03 验证学员`, a direct report link to `/practice/1398bea9-c25a-454f-ad1c-f645edcb3350/report`, and a drill-in link to `/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2?...`.

### 2. Drill into the seeded risk user on the current user-detail route

1. From the analytics risk card, open `查看并设重点` for `S03 验证学员`.
2. Wait for `/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2?focusBucket=not_passed&...` to load.
3. Inspect the source banner and focus form.
4. **Observed:** the detail page preserved the weekly context on the shipped route:
   - banner title: `本周经营名单来源`
   - bucket badge: `本周风险成员`
   - description: `当前这条 drill-in 仍落在「核心能力」这个问题家族。`
   - prefilled note: `先对照最近统一报告补证据。`

### 3. Record a supervisor focus and reminder on the same user-detail surface

1. On the same `/admin/users/{id}` page, click `设为主管重点` without leaving the current route.
2. Confirm a persisted intervention card appears.
3. Click `记录提醒` on that new intervention card.
4. **Observed:** the current admin detail surface handled both actions in place:
   - after create: `主管重点已记录，可继续发送提醒。`
   - after remind: `已记录提醒，当前重点仍保持在主管视图中。`
   - reminder state updated to `提醒已发送`
   - the card showed a fresh `最近提醒` timestamp on the same page

### 4. Review the resulting session on the canonical report route

1. From the user-detail session list, open the latest evaluable completed session report: `/practice/1398bea9-c25a-454f-ad1c-f645edcb3350/report`.
2. Inspect the report summary and issue/goal areas.
3. **Observed:** the canonical report route stayed usable and showed the same evidence vocabulary the admin flow used:
   - report title: `训练评估报告`
   - overall score: `50`
   - main issue: `关键异议回应不够具体。`
   - next goal: `下一轮先把异议处理说完整。`
   - replay anchor hint: `未找到精确高光，回放将定位到“异议处理”阶段。`
   - knowledge state: `未绑定知识库`

### 5. Review the same session on the canonical replay route

1. From the report flow, open the replay route for the same session: `/practice/1398bea9-c25a-454f-ad1c-f645edcb3350/replay`.
2. Inspect the replay conclusion block and transcript.
3. **Observed:** replay stayed on the same unified evidence line:
   - page title: `会话回放`
   - same main issue: `关键异议回应不够具体。`
   - same next goal: `下一轮先把异议处理说完整。`
   - stage evidence rendered for `开场破冰` and `异议处理`
   - `完整对话` rendered with the persisted two-message transcript for the session

## Supporting Diagnostics

- Browser console logs confirmed the shipped read path, not a mock path:
  - `[Report] Loaded unified evidence contract`
  - `[Report] Replay anchors loaded` with degraded anchors
  - `[Replay] Loaded unified evidence contract`
  - `[Replay] Applied report anchor deep link`
- Browser timeline artifact was written to:
  - `.artifacts/browser/2026-03-27T01-29-12-526Z-session/m005-s05-t02-timeline.json`

## Non-Blocking Findings

- The newly created intervention card displayed the carried issue family as raw `main_capability_not_passed` text instead of a localized label like `核心能力` / `证据补强`. The drill-in banner was localized correctly, so this is a copy-normalization gap on the persisted intervention display, not a broken route.
- The report page emitted optional enhancement failures while still rendering the canonical unified evidence view:
  - `GET /api/v1/evaluation/sessions/{id}/report` returned `404 [REPORT_NOT_FOUND]`
  - `POST /api/v1/evaluation/sessions/{id}/report` returned `500 [REPORT_GENERATION_FAILED]` with `[NO_STAGE_RESULTS]`
  - despite that, `/practice/{id}/report` and `/practice/{id}/replay` remained usable on the unified contract and the replay review still completed.

## Result

The current shipped admin chain is sufficient for one real supervisor workflow on existing routes:

`/admin/analytics` weekly pack → `/admin/users/{id}` drill-in with carried context → in-place focus/reminder action → `/practice/{sessionId}/report` review → `/practice/{sessionId}/replay` review.

This slice now has live proof that the workflow can be completed without switching to a separate acceptance-only surface or a shadow admin tool.
