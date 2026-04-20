---
id: S06
parent: M001
milestone: M001
provides:
  - Projection-backed supervisor progress and aligned admin stats/report drill-ins on `/admin/users/[id]`, including repeated blocker/next-goal buckets, explicit not-evaluable counts, and inline degraded states.
requires:
  - slice: S02
    provides: Unified SessionEvidence/HistoryService projection baseline for completed-session scores, evaluability, and comparable cross-session facts.
  - slice: S03
    provides: Single-session supervisor-readable judgment dimensions and canonical `/practice/{sessionId}/report` drill-in targets.
affects:
  - S08
key_files:
  - backend/src/common/analytics/history_service.py
  - backend/src/admin/api/users.py
  - backend/tests/unit/test_history_service_evidence_projection.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
key_decisions:
  - D027
patterns_established:
  - Supervisor score-bearing aggregates must come from HistoryService projection helpers so `/stats`, `/progress`, completed-session previews, and canonical reports stay on one evidence line.
  - Admin user-detail degraded-state UAT is most reliable with an in-page `window.fetch` override plus the page `刷新` action; direct cross-origin route mocks can fail as misleading `ERR_FAILED` noise.
observability_surfaces:
  - practice_history_projection_query (`query_name=admin_user_progress` / `admin_user_projection_scores`)
  - GET /api/v1/admin/users/{id}/progress
  - GET /api/v1/admin/users/{id}/stats
  - GET /api/v1/admin/users/{id}/sessions
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - Live browser review on `/admin/users/{id}`
drill_down_paths:
  - .gsd/milestones/M001/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S06/tasks/T02-SUMMARY.md
duration: 3h
verification_result: passed
completed_at: 2026-03-24T09:21:47+08:00
---

# S06: 连续变化视图（主管判断是否进步）

**Projection-backed supervisor progress now lets `/admin/users/[id]` answer whether a learner is improving, what keeps repeating, and whether focus should change, without drifting away from the canonical single-session evidence line.**

## What Happened

S06 closed the last supervisor-side gap between the single-session report work from S02/S03 and the admin user detail page. On the backend, `HistoryService` gained a supervisor progress snapshot built from the same completed-session projection already used by session previews. That snapshot now owns truthful `day/week` grouping, evaluable vs not-evaluable completed-session counts, repeated `main_issue.issue_type` / `next_goal.goal_type` buckets, and the conservative `should_switch_focus` recommendation. `GET /api/v1/admin/users/{id}/progress` now reads that snapshot directly, and the score-bearing fields in `GET /api/v1/admin/users/{id}/stats` were moved onto the same projection-backed summary so the page no longer mixes preview facts with legacy route-local 0.4/0.3/0.3 SQL math.

On the web side, `/admin/users/[id]` now consumes the richer supervisor contract instead of treating progress as a generic percentage + line chart. The page keeps the existing shell and completed-session `查看报告` drill-in, but the progress region now tells a supervisor what matters: recent trend, repeated blocker categories, repeated next-goal categories, evidence-insufficient counts, and whether the trainee should keep the same focus or switch. When progress has no evaluable history or fails to load, the page holds the surrounding shell steady and shows a local inline empty/error state instead of collapsing the whole page or hiding the report table.

This closer turn also confirmed the assembled slice against live runtime rather than trusting task artifacts alone. The admin page was reopened against local backend/web servers after an idempotent Alembic upgrade to head, the real `/progress` and `/stats` endpoints were checked from the browser session, and the page’s success, empty, and error states were all re-proven with fresh evidence.

## Verification

Fresh slice-level verification passed end to end:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py -k 'progress or stats'`
- `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'`
- `cd backend && /usr/bin/time -p venv/bin/alembic upgrade head`
- Live browser/runtime review on `http://localhost:3445/admin/users/89e31f06-6393-42b6-877e-5a007803136a` after `POST /api/v1/auth/dev-login`

Operational proof from the live review:

- The real page showed a supervisor-readable success state with `最近基本持平`, `继续观察当前重点`, `已完成训练里有 1 次仍证据不足`, and `另外还有 8 次未完成训练暂不纳入连续变化判断`.
- Direct browser-side reads of the real endpoints confirmed the slice contract: `/progress?time_range=30d` returned `granularity=day`, `evaluable_session_count=2`, `not_evaluable_session_count=1`, `non_completed_session_count=8`, `should_switch_focus=false`; `/stats?time_range=30d` returned `average_score=87.3`, `best_score=100`, `worst_score=74.7`, matching the page cards.
- A progress-only `window.fetch` override plus the page `刷新` action reproduced the local inline empty state (`暂无可评估训练数据`) without collapsing the rest of the page.
- A second progress-only override that forced a network failure reproduced the inline error copy (`连续变化视图加载失败：网络连接失败，请检查后端服务或网络设置后重试。`) while leaving the shell and `查看报告` drill-ins intact.

## Requirements Advanced

- R011 — S06 extended the S02 evidence baseline into supervisor-facing `/progress` and score-bearing `/stats` reads, so cross-session management views now use the same projection-backed facts as completed-session previews and canonical reports.

## Requirements Validated

- R007 — Fresh backend projection/admin-user suites, the focused admin page test, Alembic-at-head confirmation, and live browser review together proved that a supervisor can now judge recent change, repeated problems, and whether focus should change from `/admin/users/{id}`.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none — no requirement scope changed during S06 execution.

## Deviations

T02’s production web implementation was already present in the working tree when the closer turn began, so the second half of the slice became verification-and-artifact closure rather than additional feature coding. The slice still required fresh runtime proof because the plan promised operational behavior, not just file existence.

## Known Limitations

- The continuous-change view is advisory only. Supervisors can now judge whether to change focus, but system-internal task assignment and management follow-through remain deferred to later work.
- Trend scoring and recommendation logic only use completed evaluable sessions. Not-evaluable and non-completed sessions are explained explicitly, but they do not produce blocker/goal buckets or score movement.

## Follow-ups

- S07 should verify that PPT post-session `main_issue` / `next_goal` outputs remain compatible with the same supervisor progress contract, so mixed sales/PPT histories do not reintroduce a second truth line.
- S08 should include `/admin/users/{id}` in milestone-level release UAT and watch `practice_history_projection_query` for drift between `/progress`, `/stats`, and completed-session previews under real traffic.

## Files Created/Modified

- `backend/src/common/analytics/history_service.py` — added the projection-backed supervisor snapshot, truthful day/week grouping, repeated issue/goal buckets, and recommendation logging.
- `backend/src/admin/api/users.py` — moved admin `/progress` and score-bearing `/stats` reads onto HistoryService projection helpers.
- `backend/tests/unit/test_history_service_evidence_projection.py` — locked supervisor snapshot grouping, repeated-bucket, and recommendation semantics.
- `backend/tests/integration/test_admin_users_api.py` — locked `/progress` and `/stats` alignment against projection-backed completed-session previews.
- `web/src/lib/api/types.ts` — carries the richer supervisor progress contract used by the admin user-detail page.
- `web/src/lib/session-evidence.ts` — supplies label helpers for issue/goal/not-evaluable vocabulary used in the continuous-change summary.
- `web/src/app/admin/users/[id]/page.tsx` — renders supervisor-readable trend, repeated blocker/goal, and inline empty/error states while preserving report drill-ins.
- `web/src/app/admin/users/[id]/page.test.tsx` — covers switch-focus, empty-state, and progress-only failure behavior.
- `.gsd/REQUIREMENTS.md` — marked R007 validated and recorded that R011 is reinforced by S06.
- `.gsd/milestones/M001/M001-ROADMAP.md` — marked S06 complete.
- `.gsd/PROJECT.md` — updated current project state to include the shipped supervisor trend view.
- `.gsd/milestones/M001/slices/S06/S06-SUMMARY.md` — recorded the slice-level outcome and forward guidance.
- `.gsd/milestones/M001/slices/S06/S06-UAT.md` — captured the tailored supervisor-progress UAT script.

## Forward Intelligence

### What the next slice should know
- `/admin/users/[id]` now assumes a projection-backed supervisor contract from `/progress` (`repeated_main_issues`, `repeated_next_goals`, `not_evaluable_session_count`, `non_completed_session_count`, `should_switch_focus`, `recommendation`). Extend that contract if S07/S08 need more supervisor signal; do not bolt on a parallel summary source.

### What's fragile
- Local admin progress UAT is fragile if the database is not at Alembic head or if you try to use cross-origin Playwright route mocks for `/progress` — both failure modes look like frontend regressions even when the page logic is correct.

### Authoritative diagnostics
- `practice_history_projection_query` with `query_name=admin_user_progress` / `admin_user_projection_scores`, plus `GET /api/v1/admin/users/{id}/progress` and `GET /api/v1/admin/users/{id}/stats`, are the first places to inspect because they come from the same HistoryService projection helpers that now feed the page, the stats cards, and completed-session previews.

### What assumptions changed
- We started with the implicit assumption that route-local weighted SQL could coexist with projection-backed completed-session previews on the same admin page. S06 proved that assumption false: mixed score truths were already visible, so all score-bearing supervisor surfaces now need to route through HistoryService/SessionEvidence projection helpers.
