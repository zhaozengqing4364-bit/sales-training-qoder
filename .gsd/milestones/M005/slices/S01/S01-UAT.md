# S01: admin analytics / user drill-in 语义收口 — UAT

**Milestone:** M005
**Written:** 2026-03-26T06:44:55.703Z

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: this slice changes the meaning and wording of existing admin analytics/drill-in surfaces, so payload-level proof on the exact backend routes plus route-level UI rendering on the exact pages is sufficient to prove the slice without spinning up a new workflow.

## Preconditions

- Use an admin account that can access `/admin/analytics` and `/admin/users/[id]`.
- Backend and web app are running against data that includes:
  - at least one user with completed evaluable sessions,
  - at least one completed session that is not evaluable,
  - at least one completed session with a canonical `/practice/{sessionId}/report` page.
- If running the artifact-driven proof instead of the live UI path, the following commands must be runnable from the repo:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx'`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`

## Smoke Test

1. Log in as an admin.
2. Open `/admin/analytics`.
3. **Expected:** the page shows a `当前看板口径` card explaining that only evaluable completed sessions are counted in the score line and that evidence-insufficient sessions are tracked separately.

## Test Cases

### 1. Analytics overview uses unified evidence scope instead of legacy weighted wording

1. Open `/admin/analytics`.
2. Read the top summary card and the score-basis card.
3. Confirm the page explains that the score, distribution, and leaderboard only include evaluable completed sessions.
4. Confirm the page also discloses how many completed sessions were excluded because they were evidence-insufficient.
5. **Expected:** the page uses wording equivalent to `统一训练证据 · 仅统计可评估的已完成训练`, explicitly separates not-evaluable sessions from the score line, and does not present the average score as an unexplained generic dashboard number.

### 2. Analytics issue-family and next-goal blocks speak the same evidence language as reports

1. Stay on `/admin/analytics`.
2. Inspect the `反复问题家族` card.
3. Inspect the evidence-insufficient reason card.
4. Inspect the repeated next-goal card and the leaderboard leader summary.
5. **Expected:** the page shows issue-family labels such as `证据支撑`, reason labels such as `对话轮次不足，暂无法形成稳定评估。`, and next-goal language such as `证据补强` instead of legacy generic communication labels.

### 3. Analytics placeholders stay truthful when there is no stable repeated signal

1. Switch to a time range or scenario filter with little or no stable repeated signal.
2. Re-read the issue-family, not-evaluable-reason, and repeated next-goal cards.
3. **Expected:** the page shows explicit placeholders such as “当前时间范围内还没有形成稳定重复的问题家族” or “当前时间范围内没有证据不足会话...”, instead of empty cards, stale previous data, or fallback legacy copy.

### 4. Manager-lite stays on the same truth line and opens the canonical report

1. On `/admin/analytics`, scroll to `主管最小干预面板`.
2. In `未达标名单`, confirm the description says it only counts completed + evaluable + not-passed sessions.
3. Open a `查看统一报告` link from one row.
4. Return to analytics and click `一键提醒` for the same user.
5. **Expected:** the panel explains that fail/improving lists follow the unified evidence line, the report link opens `/practice/{sessionId}/report`, and the reminder action remains available on the current surface.

### 5. Admin user drill-in shows score basis, evaluability counts, and repeated blocker semantics

1. Open `/admin/users/{userId}` for a seeded user with evaluable history.
2. Inspect the `统一综合分` card.
3. Inspect the `连续变化判断` section.
4. Inspect the completed-session preview list.
5. **Expected:**
   - the page shows the unified score basis label,
   - it separately lists evaluable and not-evaluable session counts,
   - it summarizes repeated blocker and next-goal families in supervisor-readable language,
   - completed-session rows expose the canonical `查看统一报告` CTA.

## Edge Cases

### User has only completed but not-evaluable sessions

1. Open `/admin/users/{userId}` for a user whose recent completed sessions are all evidence-insufficient.
2. **Expected:** the page stays mounted, the progress card shows `暂无可评估训练数据`, and the copy explains that the latest completed sessions were not counted into the score trend.

### Progress request fails while stats/session shell still loads

1. Open `/admin/users/{userId}`.
2. Simulate a failure only for `/api/v1/admin/users/{id}/progress`.
3. **Expected:** the page still shows the user shell, statistics, and completed-session preview; only the progress area falls back to an inline error state, and report links remain usable.

## Failure Signals

- `/admin/analytics` shows a score/leaderboard without disclosing evaluability scope.
- Evidence-insufficient completed sessions are mixed into the top-line score with no separate count.
- Analytics, manager-lite, and `/admin/users/[id]` use different labels for the same issue family or next-goal family.
- Manager-lite links to anything other than `/practice/{sessionId}/report`.
- The whole `/admin/users/[id]` page collapses when only the progress request fails.

## Requirements Proved By This UAT

- None — this UAT proves M005/S01 slice acceptance on the current admin routes, but it does not change formal requirement status.

## Not Proven By This UAT

- The supervisor focus/reminder outcome loop planned for S02.
- Asset-impact and health governance planned for S03.
- Weekly operating pack / cohort problem views planned for S04.

## Notes for Tester

- In this environment, the reliable artifact-driven web proof uses `pnpm dlx npm@11.6.1 test -- --run ...` because the global Volta `npm` wrapper is known to be unstable.
- If the live `/admin/users/[id]` page suddenly looks like a frontend regression while loading session previews or progress, check Alembic head first; missing `conversation_messages.transcript_metadata` schema can masquerade as a route/UI failure on this surface.

