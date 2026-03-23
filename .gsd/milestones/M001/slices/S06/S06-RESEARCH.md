# S06 — Research

**Date:** 2026-03-23

## Summary

S06 is not greenfield. The repository already has a supervisor-facing user detail surface at `web/src/app/admin/users/[id]/page.tsx`, a dedicated backend route at `GET /api/v1/admin/users/{user_id}/progress`, and projection-backed completed-session previews from S03 in `GET /api/v1/admin/users/{user_id}/sessions`. The slice blocker is that the continuous-change surfaces still bypass the S02/S03 fact line: `backend/src/admin/api/users.py` computes both `/stats` and `/progress` directly from `PracticeSession.logic_score/accuracy_score/completeness_score` with the legacy `0.4/0.3/0.3` weighting and date-grouped SQL averages. The session table can already show projection-backed `overall_result` / `main_issue` / `next_goal`, but the trend card and chart are still driven by a different truth.

The lowest-risk path is to make S06 an aggregation/read-model slice, not a new scoring slice. `backend/src/common/analytics/history_service.py` already owns completed-session projection, evaluable gating, statistics payloads, and per-session trend points backed by `SessionEvidenceService`. `backend/src/common/effectiveness/evaluator.py` already emits stable sales `issue_type` / `goal_type` keys (`value_translation_gap`, `evidence_gap`, `objection_handling_gap`, `next_step_gap`, etc.). Reusing those layers lets S06 answer “有没有进步 / 总卡在哪 / 要不要换训练重点” without inventing a second supervisor scorer.

Following `safe-grow`, keep the slice centered on `/admin/users/[id]` and its API contract instead of widening into `/admin/analytics` manager-lite. Following `baseline-ui` / `accessibility`, extend the existing `GlassCard` / `Button` / text surfaces with local empty/error states and visible labels rather than redesigning the whole page or hiding failures behind console-only logging.

## Recommendation

Build a projection-backed **supervisor progress snapshot** in `HistoryService`, then make `GET /api/v1/admin/users/{id}/progress` read from it. That snapshot should:

- derive score trend from `HistorySessionSummary` / `build_trend_points`, not raw `PracticeSession` score columns;
- filter score-improvement math to completed + `evaluable=true` sessions, while still exposing not-evaluable session count explicitly;
- aggregate repeated `main_issue.issue_type` and `next_goal.goal_type` over recent evaluable sessions;
- return one deterministic coaching recommendation / `should_switch_focus` signal based on repeated issue persistence plus weak recent improvement.

Because the admin user detail page also shows average / best / worst score cards, the score-bearing part of `GET /api/v1/admin/users/{id}/stats` should be aligned to the same projection-backed summaries; otherwise S06 will still ship mixed facts on one page. Keep agent/persona usage counts on the existing raw query if needed, but do not leave score cards on legacy weighting while the chart moves to projection-backed math.

Do not compute trend math directly inside `backend/src/admin/api/users.py`, and do not make the frontend infer repeated blockers from the sessions table. Keep `/admin/users/[id]` as the single primary S06 surface unless scope is explicitly widened later.

## Implementation Landscape

### Key Files

- `backend/src/common/analytics/history_service.py` — Canonical completed-session summaries, evaluability gating, statistics payloads, and per-session trend points. Best home for the new supervisor aggregation helper because it already centralizes session loading, message loading, and `SessionEvidenceService` projection.
- `backend/src/admin/api/users.py` — Current admin user detail routes. `/sessions` is already projection-backed and should be the pattern to follow. `/progress` is still legacy weighted SQL aggregation and currently ignores its `granularity` query param. `/stats` also uses raw weighted averages and will drift unless its score fields are aligned.
- `backend/src/common/effectiveness/evaluator.py` — Authoritative stable vocabulary for cross-session buckets. Use `main_issue.issue_type` and `next_goal.goal_type` from here instead of inventing new supervisor-only categories.
- `backend/src/common/conversation/session_evidence.py` — Underlying shared evidence projection. S06 should consume this indirectly through `HistoryService`, not duplicate projection logic in the route.
- `web/src/lib/api/types.ts` — `UserProgressResponse` only contains `{ trend_data, improvement_rate, total_data_points }` today. It needs richer supervisor fields for repeated blockers / repeated goals / focus recommendation.
- `web/src/lib/api/client.ts` — `api.admin.getUserProgress()` is already the single client entrypoint for the page; only its response type/consumer should change.
- `web/src/app/admin/users/[id]/page.tsx` — Existing supervisor detail page. Session table already renders projection-backed `feedback_summary` / `next_goal`; progress card and chart remain generic score visuals, and `loadData()` currently collapses all failures into a single console log.
- `web/src/lib/session-evidence.ts` — Shared frontend evidence-formatting helpers. Extend here if issue / goal bucket labels need one canonical formatter instead of hardcoding copy inside the page.
- `backend/tests/unit/test_history_service_evidence_projection.py` — Existing unit coverage around projection-backed stats/trends. Natural place for new supervisor aggregation tests.
- `backend/tests/integration/test_admin_users_api.py` — Existing integration coverage for projection-backed `/sessions`; add `/progress` and any `/stats` alignment proof here.
- `web/src/app/admin/users/[id]/page.test.tsx` — Current page test only asserts unified preview copy + report CTA. Expand it to lock the S06 continuous-change UI.

### Build Order

1. **Add backend aggregation in `HistoryService` first.**
   - Prove it reads completed sessions through projection-backed summaries.
   - Keep score improvement math gated to `evaluable=true` sessions.
   - Still count/report not-evaluable sessions explicitly so supervisors can tell “没进步” apart from “证据不足”.

2. **Rewire `backend/src/admin/api/users.py`.**
   - Replace `/progress` route-level SQL averaging with the new history-service snapshot.
   - Align the score-bearing fields in `/stats` to the same summaries if the page keeps showing average/best/worst score cards.
   - Preserve user existence validation and non-score usage breakdowns.

3. **Extend frontend contract types.**
   - Update `UserProgressResponse` and `api.admin.getUserProgress()` to the richer payload.
   - Add any shared issue/goal label helpers in `web/src/lib/session-evidence.ts`.

4. **Update `/admin/users/[id]` UI.**
   - Keep the current page shell and session table.
   - Replace the score-only “进步率 + 折线图” story with a supervisor-readable summary: trend, repeated blocker, repeated next goal, and a “是否该切换训练重点” recommendation.
   - Add local empty/error states near the progress surface instead of relying on `console.error`.

5. **Lock the slice with focused tests.**
   - Unit tests for the new history-service aggregation.
   - Integration tests for `/admin/users/{id}/progress` and any `/stats` score alignment.
   - Component tests for the admin user detail page rendering the new summary.

### Verification Approach

Current focused baseline checks still pass and are safe reruns before/after S06 work:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py -k projection_backed_preview_fields`
- `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'`

Planned slice verification:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py`
- `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'`

Optional runtime/UAT proof after backend is runnable:

- `cd backend && venv/bin/alembic upgrade head`
- Open `/admin/users/{id}` and confirm the progress summary uses the same `overall_result` / `main_issue` / `next_goal` vocabulary as the session table and report drill-ins.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Projection-backed cross-session comparison | `backend/src/common/analytics/history_service.py` + `backend/src/common/conversation/session_evidence.py` | Already solves ordered message loading, evaluability gating, score normalization, and projection diagnostics. |
| Repeated blocker / next-step taxonomy | `backend/src/common/effectiveness/evaluator.py` (`issue_type`, `goal_type`) | Stable canonical keys already feed report and admin session preview; reusing them avoids supervisor-only vocabulary drift. |

## Constraints

- R007 is the owned active requirement for S06. The slice must let a supervisor judge improvement across recent sessions, repeated blocker classes, and whether focus should change; a prettier chart alone is not enough.
- S03 already stabilized the supervisor vocabulary: `overall_result`, `evaluable`, `not_evaluable_reason`, `main_issue`, `next_goal`, `feedback_summary`. S06 should aggregate these fields, not recompute a different supervisor language from raw scores.
- `GET /api/v1/admin/users/{id}/progress` exposes `granularity` today but the current implementation ignores it. Either implement truthful grouping or avoid pretending weekly granularity exists.
- Local admin/runtime verification can still be blocked by schema drift: missing Alembic revision `20260317_2310_020` breaks admin evidence reads with `conversation_messages.transcript_metadata does not exist`.
- Local browser proof of `/admin/users/[id]` is sensitive to auth-cookie host alignment. API/integration tests and focused component tests are the more reliable proof surface.

## Common Pitfalls

- **Fixing only the frontend chart** — If `/progress` keeps using raw weighted SQL averages, the page will still mix two truths even if the UI copy improves.
- **Aligning `/progress` but not `/stats`** — The admin user detail page shows average/best/worst score cards; leaving those on legacy weighting preserves factual drift on the same screen.
- **Aggregating from raw `effectiveness_snapshot` or route-level SQL instead of `HistoryService`** — That bypasses S02’s projection contract and reintroduces the exact drift S02/S03 removed.
- **Treating not-evaluable sessions as noise** — Thin-evidence completed sessions are a real business state. Supervisors need to see evidence shortage separately from lack of progress.
- **Keeping progress failures console-only** — The current page has one catch-all `console.error`. Any new progress surface should show a local inline failure/empty state near the chart/summary.

## Open Risks

- The exact heuristic for “是否该切换训练重点” is a product threshold choice, not a technical one. The safest starting rule is deterministic and conservative: e.g. last 3 evaluable completed sessions keep the same `main_issue.issue_type`, `overall_result` remains fail/pass-flat, and overall score delta stays small.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — not installed (`npx skills add wshobson/agents@fastapi-templates`) |
| Recharts | `ansanabria/skills@recharts` | available — not installed (`npx skills add ansanabria/skills@recharts`) |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — not installed (`npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm`) |