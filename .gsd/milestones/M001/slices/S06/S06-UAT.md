# S06: 连续变化视图（主管判断是否进步） — UAT

**Milestone:** M001
**Written:** 2026-03-24T09:21:47+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S06 changes backend evidence aggregation, admin `/stats` + `/progress` contracts, and the live admin page state model. Passing tests alone would not prove that a real supervisor page can answer “有没有进步 / 卡在哪 / 要不要换重点” or that progress-only failures degrade locally without taking down the rest of the page.

## Preconditions

- Backend is running locally on `http://localhost:3444`.
- Web is running locally on `http://localhost:3445`.
- Run `cd backend && venv/bin/alembic upgrade head` before judging `/admin/users/{id}`.
- Dev login works through `POST /api/v1/auth/dev-login`.
- Preferred seeded target user for the live success-path check: `repair@example.com` / `89e31f06-6393-42b6-877e-5a007803136a`.
- The target user should have at least:
  - 2 completed evaluable sessions
  - 1 completed not-evaluable session
  - 1 or more unfinished sessions
- If `/admin/users/{id}` or `/api/v1/admin/users/{id}/sessions` fails with a complaint about `conversation_messages.transcript_metadata`, treat it as a migration blocker, not a frontend regression.
- For progress-only degraded-state checks, use the page-local `window.fetch` override described below. Do **not** rely on cross-origin route mocks against `localhost:3444`.

## Smoke Test

1. Open `http://localhost:3445/login`.
2. In the browser console, run:
   ```js
   await fetch('http://localhost:3444/api/v1/auth/dev-login', {
     method: 'POST',
     credentials: 'include',
   })
   ```
3. Navigate to `http://localhost:3445/admin/users/89e31f06-6393-42b6-877e-5a007803136a`.
4. Read the `连续变化判断` card and the top `训练建议` card.
5. **Expected:** the page directly answers the supervisor questions instead of showing only a generic line chart:
   - visible trend judgment such as `最近基本持平`
   - visible recommendation such as `继续观察当前重点`
   - explicit evidence-insufficient copy such as `已完成训练里有 1 次仍证据不足`
   - explicit excluded-session copy such as `另外还有 8 次未完成训练暂不纳入连续变化判断`
   - the session table and `查看报告` links remain available below the progress summary

## Test Cases

### 1. Live success path: the page must give a readable supervisor judgment

1. Complete the smoke test.
2. Stay on `30天` (or reselect it if necessary).
3. Read the top summary cards and the `连续变化判断` panel.
4. **Expected:**
   - the top card shows `训练建议` rather than only a raw percentage
   - the main panel shows `最近趋势`, `训练建议`, `反复卡点`, `重复下一轮重点`, and `证据不足 / 未纳入趋势`
   - the page explains the state in plain language, for example `最近基本持平` + `继续观察当前重点`
   - if there is no stable repeated blocker or next goal yet, the page says so explicitly instead of inventing one
   - the chart is clearly secondary (`辅助趋势`) rather than the only source of truth

### 2. Live API alignment: `/progress`, `/stats`, and the page cards must agree

1. With the same page open, run these in the browser console:
   ```js
   const progress = await fetch(
     'http://localhost:3444/api/v1/admin/users/89e31f06-6393-42b6-877e-5a007803136a/progress?time_range=30d',
     { credentials: 'include' },
   ).then((r) => r.json())

   const stats = await fetch(
     'http://localhost:3444/api/v1/admin/users/89e31f06-6393-42b6-877e-5a007803136a/stats?time_range=30d',
     { credentials: 'include' },
   ).then((r) => r.json())

   console.log(progress.data ?? progress, stats.data ?? stats)
   ```
2. Compare the API payloads with the rendered cards and summary copy.
3. **Expected:**
   - `/progress` returns projection-backed supervisor fields such as `granularity`, `evaluable_session_count`, `not_evaluable_session_count`, `non_completed_session_count`, `repeated_main_issues`, `repeated_next_goals`, `should_switch_focus`, and `recommendation`
   - `/stats` returns `average_score`, `best_score`, and `worst_score` values that match the page cards for the same time range
   - the session table still uses the same canonical report drill-in path (`/practice/{sessionId}/report`) for completed sessions
   - the page is not mixing one set of numbers in the cards and another set in the progress copy

### 3. Switch-focus branch: mocked repeated blocker + repeated goal should render the supervisor recommendation

1. Keep the same admin user-detail page open.
2. In the browser console, install a progress-only override:
   ```js
   window.__origFetch ??= window.fetch.bind(window)
   window.fetch = async (...args) => {
     const [input, init] = args
     const url = typeof input === 'string' ? input : input.url
     if (url.includes('/api/v1/admin/users/89e31f06-6393-42b6-877e-5a007803136a/progress')) {
       return new Response(JSON.stringify({
         success: true,
         data: {
           granularity: 'week',
           trend_data: [
             {
               date: '2026-03-02T00:00:00+00:00',
               sessions_count: 3,
               evaluable_session_count: 2,
               not_evaluable_session_count: 1,
               average_score: 60,
               logic_score: 55,
               accuracy_score: 61,
               completeness_score: 64,
               overall_result: 'fail',
               evaluable: true,
               not_evaluable_reason: null,
               main_issue: {
                 issue_type: 'objection_response',
                 issue_text: '异议回应不够具体。',
                 recovery_rule: '先回应风险，再补证据。',
               },
               next_goal: {
                 goal_type: 'objection_response_drill',
                 goal_text: '下一轮继续把异议回应说完整。',
                 rule: '至少完成 1 次完整异议回应。',
               },
               stage_summary: [],
               evidence_completeness: { complete: true, missing_fields: [], message_count: 6 },
             },
             {
               date: '2026-03-09T00:00:00+00:00',
               sessions_count: 1,
               evaluable_session_count: 1,
               not_evaluable_session_count: 0,
               average_score: 40,
               logic_score: 38,
               accuracy_score: 42,
               completeness_score: 40,
               overall_result: 'fail',
               evaluable: true,
               not_evaluable_reason: null,
               main_issue: {
                 issue_type: 'objection_response',
                 issue_text: '异议回应不够具体。',
                 recovery_rule: '先回应风险，再补证据。',
               },
               next_goal: {
                 goal_type: 'objection_response_drill',
                 goal_text: '下一轮继续把异议回应说完整。',
                 rule: '至少完成 1 次完整异议回应。',
               },
               stage_summary: [],
               evidence_completeness: { complete: true, missing_fields: [], message_count: 3 },
             },
           ],
           improvement_rate: -33.3,
           total_data_points: 2,
           completed_session_count: 4,
           evaluable_session_count: 3,
           not_evaluable_session_count: 1,
           non_completed_session_count: 1,
           repeated_main_issues: [
             {
               issue_type: 'objection_response',
               issue_text: '异议回应不够具体。',
               count: 3,
             },
           ],
           repeated_next_goals: [
             {
               goal_type: 'objection_response_drill',
               goal_text: '下一轮继续把异议回应说完整。',
               count: 3,
             },
           ],
           should_switch_focus: true,
           recommendation: {
             reason: 'stalled_repeated_focus',
             summary: '最近多次训练仍卡在同一重点且没有改善，建议切换训练重点或训练方法。',
           },
         },
       }), {
         status: 200,
         headers: { 'Content-Type': 'application/json' },
       })
     }
     return window.__origFetch(input, init)
   }
   ```
3. Click the page `刷新` button.
4. **Expected:**
   - the page now shows `建议切换训练重点`
   - the repeated blocker text `异议回应不够具体。` is visible
   - the repeated next-goal text `下一轮继续把异议回应说完整。` is visible
   - the recommendation summary `最近多次训练仍卡在同一重点且没有改善，建议切换训练重点或训练方法。` is visible
   - the rest of the page shell and `查看报告` links stay intact

### 4. Empty-state branch: progress with no evaluable sessions must stay local to the panel

1. Replace the progress-only override with:
   ```js
   window.fetch = async (...args) => {
     const [input, init] = args
     const url = typeof input === 'string' ? input : input.url
     if (url.includes('/api/v1/admin/users/89e31f06-6393-42b6-877e-5a007803136a/progress')) {
       return new Response(JSON.stringify({
         success: true,
         data: {
           granularity: 'day',
           trend_data: [],
           improvement_rate: 0,
           total_data_points: 0,
           completed_session_count: 2,
           evaluable_session_count: 0,
           not_evaluable_session_count: 2,
           non_completed_session_count: 0,
           repeated_main_issues: [],
           repeated_next_goals: [],
           should_switch_focus: false,
           recommendation: {
             reason: 'insufficient_evaluable_history',
             summary: '最近完成的训练里仍有证据不足的会话，先补齐有效互动再判断是否切换重点。',
           },
         },
       }), {
         status: 200,
         headers: { 'Content-Type': 'application/json' },
       })
     }
     return window.__origFetch(input, init)
   }
   ```
2. Click `刷新`.
3. **Expected:**
   - the progress panel shows `暂无可评估训练数据`
   - the page explains why with copy such as `最近 2 次已完成训练仍证据不足`
   - the recommendation summary is visible
   - the overall page shell, stats cards, session table, and `查看报告` links remain visible

### 5. Error-state branch: a progress fetch failure must not collapse the page

1. Replace the progress-only override with:
   ```js
   window.fetch = async (...args) => {
     const [input, init] = args
     const url = typeof input === 'string' ? input : input.url
     if (url.includes('/api/v1/admin/users/89e31f06-6393-42b6-877e-5a007803136a/progress')) {
       throw new TypeError('Failed to fetch')
     }
     return window.__origFetch(input, init)
   }
   ```
2. Click `刷新`.
3. **Expected:**
   - the page shows `连续变化视图加载失败：网络连接失败，请检查后端服务或网络设置后重试。`
   - the page keeps the top shell, the stats cards, the session table, and `查看报告`
   - the failure is local to the progress region rather than replacing the whole page with a generic hard-error state

### 6. Cleanup: restore the page to live data

1. In the browser console, run:
   ```js
   if (window.__origFetch) {
     window.fetch = window.__origFetch
   }
   ```
2. Click `刷新`.
3. **Expected:**
   - the page returns to the live success state from test case 1
   - mocked progress content is gone

## Edge Cases

### Migration drift looks like a frontend failure

1. Open `/admin/users/{id}` on a local backend that has not run the latest Alembic migrations.
2. **Expected:** if the failure mentions missing `conversation_messages.transcript_metadata`, classify it as an environment/migration blocker and rerun `alembic upgrade head` before judging the slice.

### Mixed completed + unfinished history

1. Use a learner with completed, not-evaluable, and unfinished sessions.
2. **Expected:**
   - completed evaluable sessions drive the score trend and recommendation
   - completed not-evaluable sessions are counted explicitly in the evidence-insufficient copy
   - unfinished sessions are counted explicitly as excluded from the trend

### Completed-session drill-in survives degraded progress state

1. While in either the mocked empty or mocked error state, click a completed-session `查看报告` link.
2. **Expected:** the canonical `/practice/{sessionId}/report` drill-in still works; the progress failure does not remove the supervisor’s access to single-session evidence.

## Failure Signals

- The admin page still behaves like a generic score chart instead of explicitly answering whether the learner is improving, what keeps repeating, and whether focus should change.
- `/stats` cards show numbers that disagree with `/stats?time_range=...` or with the projection-backed completed-session previews on the same page.
- The progress panel invents blockers or goals when the backend reports none.
- Empty/error progress conditions collapse the whole page or remove `查看报告` drill-ins.
- A migration problem gets misclassified as a frontend/CORS regression.
- Testers try to use cross-origin route mocks and get `ERR_FAILED`, then misjudge the slice as broken.

## Requirements Proved By This UAT

- R007 — supervisors can now judge recent change, repeated blockers, and whether to change focus from `/admin/users/{id}`.
- R011 — advanced: cross-session supervisor summaries now stay on the same projection-backed evidence line as completed-session previews and canonical reports.

## Not Proven By This UAT

- System-internal supervisor task assignment / follow-through (still deferred).
- S07 PPT unified post-session review quality.
- S08 milestone-wide release readiness / observability closure across all local-runtime failure modes.

## Notes for Tester

- Judge S06 from the authoritative surfaces first: `/admin/users/{id}`, `/api/v1/admin/users/{id}/progress`, `/api/v1/admin/users/{id}/stats`, and `/api/v1/admin/users/{id}/sessions`.
- The browser-side `window.fetch` override is part of the intended local UAT method for this page’s degraded states; it avoids cross-origin mocking noise and exercises the real page refresh path.
- Restore `window.fetch` after the mocked checks so later browser work does not inherit the override.
