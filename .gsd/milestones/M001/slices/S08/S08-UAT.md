# S08: 桌面端发布验收与可观测性收口 — UAT

**Milestone:** M001
**Written:** 2026-03-24T18:24:30+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S08 是 M001 的 release-closure slice。它既要重跑 backend/web 自动化回归，也要在真实 localhost stack 上重新串起 sales runtime failure-visibility、canonical sales report、主管趋势页、PPT happy/degraded 报告、support runtime anomaly surfacing 五条桌面端路径，并确认 support/runtime 的 blocking / warning 语义与这些真实页面/API观察一致。

## Preconditions

- Backend runs locally on `http://localhost:3444` with `ENVIRONMENT=development`.
  - Command used in this run: `cd backend && PYTHONPATH=src venv/bin/uvicorn main:app --port 3444`
- Web runs locally on `http://localhost:3445`.
  - Command used in this run: `cd web && npm run dev`
- Run `cd backend && venv/bin/alembic upgrade head` before judging admin/report/support projection-backed surfaces.
- Keep frontend and backend on the same loopback host: `localhost` ↔ `localhost`.
- Dev login works through `POST /api/v1/auth/dev-login`.
- Repo-root final gate compatibility must also hold for this repository:
  - `venv/bin/alembic upgrade head`
  - `venv/bin/python -m pytest -c pyproject.toml tests/...`
- Optional report enhancement failures (`/api/v1/evaluation/sessions/{id}/report`, `/highlights`) count as warning-only if the canonical `/api/v1/practice/sessions/{id}/report` body stays readable.
- Local verification data used in this run:
  - admin user: `dev@example.com`
  - seeded learner / supervisor target: `b9b4dd28-75cb-4885-8e87-311c112113a9` (`s08.uat.user@example.com`)
  - runtime page session: `f10c769e-c655-41fb-9478-76bc30f97f3d`
  - canonical sales report session: `56f9a8a7-ba5f-4f65-9adf-ec5600df3f7a`
  - PPT happy session: `31e244b6-1006-4ecd-a15b-7c8a673bff17`
  - PPT degraded session: `0767567f-43ca-493d-a855-5cc6262e19ba`
  - support-runtime blocking anomaly sessions: `9beffdcd-cac2-47cb-ab54-cc4e1dc7c840` (`stuck_scoring`), `cd18a276-980b-4400-9ccc-6c3b24a801d5` (`knowledge_search_failed` + `not_evaluable_completed`)

## Smoke Test

1. Start local backend + web on `localhost`.
2. Navigate to `http://localhost:3445/login`.
3. Execute `POST http://localhost:3444/api/v1/auth/dev-login` in the browser session with `credentials: 'include'`.
4. Open `http://localhost:3445/support/runtime`.
5. **Expected:** page shell renders with `发布健康（只读）`, `刷新`, and anomaly summary cards instead of a blank auth/error page.

## Test Cases

### 1. Wave 1 — sales runtime failure visibility stays on the real practice page

1. Dev-login in the browser session.
2. Open `http://localhost:3445/practice/f10c769e-c655-41fb-9478-76bc30f97f3d`.
3. Observe the page state and websocket console output.
4. **Expected:**
   - URL stays on `/practice/{sessionId}`.
   - The page shows reconnect copy (`网络波动，正在自动重连...`) instead of redirecting away.
   - The page exposes the websocket close reason `AGENT_PERSONA_REQUIRED` directly on the practice surface.
   - Browser console shows reconnect attempts and 4411 close reasons, proving failure stays diagnosable instead of going silent.

### 2. Wave 2 — canonical sales report remains authoritative while enhancement failures degrade to warning

1. Open `http://localhost:3445/practice/56f9a8a7-ba5f-4f65-9adf-ec5600df3f7a/report`.
2. Verify the page shows `训练评估报告`, `销售推进结果`, `下一轮销售目标`, and `知识库命中检测`.
3. Verify the page also shows `综合洞察暂不可用，当前页面仅展示统一训练证据。`.
4. Fetch `GET http://localhost:3444/api/v1/practice/sessions/56f9a8a7-ba5f-4f65-9adf-ec5600df3f7a/report` with browser cookies.
5. Inspect failed network requests for the same page.
6. **Expected:**
   - Canonical report API returns `scenario_type="sales"`, `overall_score=73.67`, main issue `产品价值说得太功能化，还没有翻译成客户收益与 ROI。`, and next goal `补上一条案例或 ROI 证据，并确认下一步动作。`.
   - The browser page renders those canonical facts.
   - Optional enhancement requests may fail (`404` / `500`), but the page remains readable and explicitly degrades instead of collapsing.

### 3. Wave 3 — `/admin/users/{id}` still answers the supervisor question on the projection line

1. Open `http://localhost:3445/admin/users/b9b4dd28-75cb-4885-8e87-311c112113a9`.
2. Verify the page shows `连续变化判断`.
3. Confirm the repeated blocker text `异议回应不够具体。` and repeated next-goal text `下一轮继续把异议回应说完整。` appear on the page.
4. Fetch:
   - `GET http://localhost:3444/api/v1/admin/users/b9b4dd28-75cb-4885-8e87-311c112113a9/progress?time_range=all_time&granularity=day`
   - `GET http://localhost:3444/api/v1/admin/users/b9b4dd28-75cb-4885-8e87-311c112113a9/stats?time_range=all_time`
5. **Expected:**
   - Page and API both reflect the same repeated main issue / next goal.
   - Progress API reports `repeated_main_issues[0].issue_text = 异议回应不够具体。` and `repeated_next_goals[0].goal_text = 下一轮继续把异议回应说完整。`.
   - Stats API returns user-facing totals for the same seeded learner (`total_sessions=10`, `completed_sessions=8`, `average_score=66.3`).

### 4. Wave 4 — PPT happy and degraded reports stay presentation-shaped on the shared report route

1. Open `http://localhost:3445/practice/31e244b6-1006-4ecd-a15b-7c8a673bff17/report`.
2. Verify the page shows `PPT 复盘报告`, `页级证据完整`, `逐页总结`, and `要点覆盖与表达诊断`.
3. Fetch `GET http://localhost:3444/api/v1/practice/sessions/31e244b6-1006-4ecd-a15b-7c8a673bff17/report`.
4. Open `http://localhost:3445/practice/0767567f-43ca-493d-a855-5cc6262e19ba/report`.
5. Verify the page shows `PPT 复盘报告` and `页级证据降级` while staying on the PPT branch.
6. Fetch `GET http://localhost:3444/api/v1/practice/sessions/0767567f-43ca-493d-a855-5cc6262e19ba/report`.
7. **Expected:**
   - Happy path API returns `scenario_type="presentation"`, `overall_score=79.5`, `required_talking_points.status="complete"`, and no degraded reasons.
   - Degraded path API returns `scenario_type="presentation"`, `required_talking_points.status="degraded"`, and `degraded_reasons=["missing_page_metadata"]`.
   - Neither page falls back to sales-only report sections.

### 5. Wave 5 — `/support/runtime` must surface the same release truth the previous waves exposed

1. Open `http://localhost:3445/support/runtime`.
2. Verify the page shows `发布健康（只读）`, `stuck_scoring`, and `presentation_degraded_missing_page_metadata`.
3. Confirm the blocking anomaly list includes session `9beffdcd-cac2-47cb-ab54-cc4e1dc7c840`.
4. Confirm the warning anomaly list includes session `0767567f-43ca-493d-a855-5cc6262e19ba`.
5. Fetch:
   - `GET http://localhost:3444/api/v1/support/runtime/overview`
   - `GET http://localhost:3444/api/v1/support/runtime/faults?severity=blocking&limit=50`
   - `GET http://localhost:3444/api/v1/support/runtime/faults?severity=warning&limit=50`
6. **Expected:**
   - Overview reports `status="blocking"`, `blocking_count=38`, `warning_count=11` for this local run.
   - Blocking faults include:
     - `stuck_scoring` for `9beffdcd-cac2-47cb-ab54-cc4e1dc7c840`
     - `not_evaluable_completed` for `cd18a276-980b-4400-9ccc-6c3b24a801d5`
     - `knowledge_search_failed` for `cd18a276-980b-4400-9ccc-6c3b24a801d5`
   - Warning faults include:
     - `presentation_degraded_missing_page_metadata` for `0767567f-43ca-493d-a855-5cc6262e19ba`
     - `optional_report_failed` for `0767567f-43ca-493d-a855-5cc6262e19ba`
   - The page and API agree on blocking vs warning semantics.

## Edge Cases

### Repo-root verification runs without `cd backend`

1. Run `venv/bin/alembic upgrade head` from repo root.
2. Run repo-root pytest with `-c pyproject.toml tests/...`.
3. **Expected:** both commands pass using the repo-root shims rather than failing on missing Alembic/pytest config.

### Optional enhanced report APIs fail but canonical report stays readable

1. Open the seeded sales report page.
2. Inspect network errors.
3. **Expected:** `GET /api/v1/evaluation/sessions/{id}/report` may return `404` and `POST` generate may return `500 [REPORT_GENERATION_FAILED]`, but the canonical report body remains present with explicit degraded copy.

### Support runtime shows a true blocker after seeded anomalies are inserted

1. Seed the stuck-scoring and search-failed sessions used above.
2. Refresh `/support/runtime`.
3. **Expected:** release status flips/stays `blocking`; this is a correct red signal, not a false-green regression.

## Failure Signals

- `/practice/{sessionId}` redirects away or hides websocket failure state instead of keeping reconnect/error visibility on the practice page.
- Canonical report content disappears when enhanced-report/highlights requests fail.
- `/admin/users/{id}` no longer matches `/progress` repeated issue/next-goal data.
- PPT degraded reports lose `missing_page_metadata` semantics or show sales-only UI.
- `/support/runtime` treats `stuck_scoring` / `knowledge_search_failed` as warning, or treats `presentation_degraded_missing_page_metadata` / `optional_report_failed` as blocking.
- Repo-root final verification fails even though `cd backend` commands are green.

## Requirements Proved By This UAT

- R001 — the live practice page still keeps runtime failure on the learner surface with reconnect/error visibility.
- R002 — runtime/report/admin/support failure modes remain visible, degraded, or retryable instead of silently disappearing.
- R003 — the canonical sales report still speaks in value-expression / ROI / objection semantics.
- R005 — the learner report remains usable and specific even when optional enhancement layers fail.
- R007 — the supervisor page still answers recent-change / repeated-blocker questions from projection-backed evidence.
- R008 — PPT postmortems remain usable on both happy and degraded evidence paths.
- R011 — supporting: support runtime, canonical report, and supervisor progress continue to read the same persisted session evidence line.

## Not Proven By This UAT

- Production deployment infrastructure outside the local desktop release story.
- Long-run SLOs under real traffic.
- A full happy-path upstream sales conversation in this rerun; Wave 1 in this closeout specifically re-proved failure visibility on the live practice page.

## Notes for Tester

- This run intentionally used deterministic seeded sessions so the browser and API checks could be repeated without depending on whatever stale local data already existed.
- A blocking `/support/runtime` result in this run is expected because the verification data intentionally included blocking anomalies, and the local database also contains historical sessions.
- The important release-health assertion is semantic correctness: support runtime must classify the seeded blocking and warning sessions the same way the learner/admin/report surfaces imply.

## Execution Record — 2026-03-24 slice-close rerun

### Automated verification

- Repo-root gate:
  - `venv/bin/alembic upgrade head` — ✅ pass
  - `venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` — ✅ pass
- Slice-plan matrix:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py` — ✅ pass
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses` — ✅ pass
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py` — ✅ pass
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` — ✅ pass
  - `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts'` — ✅ pass
  - `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'` — ✅ pass
  - `cd backend && venv/bin/alembic upgrade head` — ✅ pass

### Live localhost proof

- Wave 1 passed with live browser assertions on `/practice/f10c769e-c655-41fb-9478-76bc30f97f3d`: URL stayed on the practice page, reconnect copy stayed visible, and console logs showed websocket reconnect plus `4411 AGENT_PERSONA_REQUIRED` instead of a fake terminal redirect.
- Wave 2 passed with live browser assertions on `/practice/56f9a8a7-ba5f-4f65-9adf-ec5600df3f7a/report`: canonical body rendered, API returned `overall_score=73.67`, and enhancement failures stayed warning-only (`404 [REPORT_NOT_FOUND]`, `500 [REPORT_GENERATION_FAILED]`).
- Wave 3 passed with live browser assertions on `/admin/users/b9b4dd28-75cb-4885-8e87-311c112113a9`: repeated blocker and repeated next goal matched the `/progress` API, and `/stats` reported `total_sessions=10`, `completed_sessions=8`, `average_score=66.3`.
- Wave 4 passed with live browser assertions on PPT happy/degraded report pages:
  - happy `31e244b6-1006-4ecd-a15b-7c8a673bff17` — `页级证据完整`, API `required_talking_points.status=complete`
  - degraded `0767567f-43ca-493d-a855-5cc6262e19ba` — `页级证据降级`, API `degraded_reasons=["missing_page_metadata"]`
- Wave 5 passed with live browser assertions on `/support/runtime` and API cross-checks:
  - blocking session `9beffdcd-cac2-47cb-ab54-cc4e1dc7c840` surfaced as `stuck_scoring`
  - blocking session `cd18a276-980b-4400-9ccc-6c3b24a801d5` surfaced as both `not_evaluable_completed` and `knowledge_search_failed`
  - warning session `0767567f-43ca-493d-a855-5cc6262e19ba` surfaced as `presentation_degraded_missing_page_metadata` and `optional_report_failed`

### Observability proof

- Backend logs emitted:
  - `practice_session_evidence_projection_built`
  - `practice_session_report_built`
  - `practice_history_projection_query`
  - `support_runtime_release_health_built`
- Those signals appeared during the same live browser run as the seeded report/admin/support checks, confirming the inspection surfaces were active rather than stale.

### Release conclusion for this rerun

- **Blocking anomalies were surfaced truthfully** on `/support/runtime`.
- **Warning-only degradations stayed warning-only** and did not collapse the canonical learner/admin/PPT surfaces.
- **The slice passes** because the release-health surface and the real browser/API observations now agree on the same persisted evidence truth line, and the final auto-verification gate is no longer failing on repo-root layout mismatches.
