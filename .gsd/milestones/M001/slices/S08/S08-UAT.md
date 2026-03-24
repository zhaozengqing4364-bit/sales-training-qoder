# S08: 桌面端发布验收与可观测性收口 — UAT

**Milestone:** M001
**Written:** 2026-03-24T16:20:00+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S08 是 M001 的 release-closure slice。它既要重跑 backend/web 自动化回归，也要在真实 localhost stack 上把 sales runtime、canonical report、主管趋势、PPT postmortem、support runtime 五条桌面端路径重新串成一条发布故事，并确认 support/runtime 的 blocking / warning 语义与这些真实 failure mode 一致。

## Preconditions

- Backend runs locally on `http://localhost:3444` with `ENVIRONMENT=development`.
  - Recommended command: `cd backend && ENVIRONMENT=development PYTHONPATH=src venv/bin/uvicorn main:app --host localhost --port 3444`
- Web runs locally on `http://localhost:3445`.
  - Recommended command: `cd web && npm run dev`
- Run `cd backend && venv/bin/alembic upgrade head` before judging projection-backed admin/support/report surfaces.
- Keep frontend and backend on the **same loopback host** during browser UAT: `localhost` ↔ `localhost`. Do not mix with `127.0.0.1`.
- Dev login works through `POST /api/v1/auth/dev-login`.
- If the sales realtime websocket loops on `1006` and backend logs mention SOCKS proxy support, install `python-socks` before calling it a regression.
- For PPT runtime proof, do **not** use the websocket `type:"text"` shortcut. Use real audio chunks plus `page_change`, otherwise the session can complete while still degrading to `missing_page_metadata`.
- For `/support/runtime` or `/admin/users/{id}` local degraded-state browser checks, prefer an in-page `window.fetch` override plus the page’s own `刷新` action. Do not rely on cross-origin route mocks against `http://localhost:3444`.
- Existing proven anchors reused by this wave:
  - S06 supervisor user: `89e31f06-6393-42b6-877e-5a007803136a` (`repair@example.com`)
  - S07 PPT happy reference session: `8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b`
  - S07 PPT degraded reference session: `ec5b7b03-a83a-4ee6-bc33-d768ccfec610`

## Smoke Test

1. Start local backend + web on `localhost`.
2. Dev-login locally.
3. Open `http://localhost:3445/support/runtime`.
4. **Expected:** page shell, `发布健康（只读）` heading, and `刷新` button render without a full-page auth or runtime crash.

## Test Cases

### 1. Wave 1 — sales runtime reconnect / end-failure still holds on the live practice page

1. Dev-login locally and open the sales training flow.
2. Start a realtime sales practice session with a usable published agent/persona.
3. Let the page reach `已连接 • 进行中 • Realtime 模式`.
4. Stop the backend briefly, confirm reconnect copy stays on `/practice/{sessionId}`.
5. Restart the backend on the same `localhost:3444` origin.
6. Confirm the page returns to connected / in-progress state.
7. Trigger `结束练习` and observe either successful terminal transition or retryable on-page failure.
8. **Expected:**
   - reconnect stays on the practice page and backend logs show reconnect restoration
   - end failure, if triggered, stays on `/practice/{sessionId}` with retry UI instead of a fake redirect
   - support/runtime classifies real runtime breakage as blocking/warning consistently with the observed learner-facing state.

### 2. Wave 2 — canonical sales report stays authoritative, optional enhancement failures count only as warning

1. Use a completed sales session with canonical report evidence available.
2. Open `/practice/{sessionId}/report` in the browser.
3. Compare the rendered report with `GET /api/v1/practice/sessions/{sessionId}/report`.
4. Note whether optional comprehensive-report / highlights requests degrade gracefully.
5. **Expected:**
   - report top-line facts come from the unified canonical report contract
   - optional enhancement failures show explicit degraded copy, but the canonical report body remains usable
   - support/runtime surfaces optional-report failures as warning-only, not as a blocking release regression.

### 3. Wave 3 — `/admin/users/{id}` still answers the supervisor question on the shared projection line

1. Dev-login locally and open `http://localhost:3445/admin/users/89e31f06-6393-42b6-877e-5a007803136a`.
2. Read the top cards plus `连续变化判断` panel.
3. Compare the page with `/api/v1/admin/users/{id}/progress` and `/api/v1/admin/users/{id}/stats`.
4. If needed, verify inline degraded behavior using a page-local `window.fetch` override and `刷新`.
5. **Expected:**
   - the page gives a readable supervisor judgment instead of only a generic chart
   - progress/stats/page facts stay aligned on the projection-backed evidence line
   - local progress failure remains local to the progress panel
   - support/runtime only escalates this path when the projection/report truth line is actually degraded.

### 4. Wave 4 — PPT report happy / degraded paths stay presentation-shaped on the shared report route

1. Open the happy PPT reference report `/practice/8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b/report`.
2. Verify the PPT branch (`PPT 复盘报告`, `逐页总结`, `要点覆盖与表达诊断`) and absence of sales-only cards.
3. Open the degraded PPT reference report `/practice/ec5b7b03-a83a-4ee6-bc33-d768ccfec610/report`.
4. Compare with `GET /api/v1/practice/sessions/{id}/report`.
5. **Expected:**
   - happy path stays PPT-shaped and presentation-specific
   - degraded path shows explicit `missing_page_metadata` style degradation instead of falling back to sales semantics
   - support/runtime treats `presentation_degraded_missing_page_metadata` as warning unless the core canonical report is unreadable.

### 5. Wave 5 — `/support/runtime` must surface the same release truth the previous four waves exposed

1. Open `http://localhost:3445/support/runtime` after the first four waves have been exercised.
2. Read release status, blocking/warning counts, scoring separation, and typed anomaly rows.
3. Cross-check `/api/v1/support/runtime/overview` and `/api/v1/support/runtime/faults`.
4. Verify that anomaly kinds / severities line up with the failure modes observed in waves 1-4.
5. If the page needs a local empty/error branch proof, override `window.fetch` in-page and click `刷新`.
6. **Expected:**
   - `status="scoring"` is not counted as healthy completion
   - typed anomaly rows include severity, kind, summary, detected_at, and compact session/scenario diagnostics
   - blocking vs warning semantics match the real path observations from the first four waves
   - if the page and the real-path evidence disagree, treat that as a blocker, not as a soft note.

## Edge Cases

### Local host mismatch causes fake auth failures

1. Dev-login against `127.0.0.1` but browse the app on `localhost` (or the reverse).
2. **Expected:** treat resulting report/admin auth failures as a UAT environment mistake, not a product regression.

### Sales StepFun websocket transport instability hides behind missing local dependency

1. Exercise a realtime sales session.
2. If websocket reconnects with `1006` and backend logs mention SOCKS proxy support, install `python-socks` and rerun.
3. **Expected:** do not classify that environment-only dependency miss as a sales/runtime regression.

### PPT websocket text shortcut yields false-green completion

1. Drive a presentation session via websocket `type:"text"` only.
2. **Expected:** do not accept completion alone as proof; `missing_page_metadata` degradation still means the real audio/page-change path was not validated.

### Support/admin degraded-state mocks should stay page-local

1. Override `window.fetch` only for the target support/admin endpoint on the page.
2. Click `刷新`.
3. **Expected:** local empty/error state appears without introducing cross-origin `ERR_FAILED` / CORS-shaped noise.

## Failure Signals

- `practice/{sessionId}` reconnect or end-failure behavior regresses back to fake terminal states or redirects.
- Canonical sales report becomes unreadable when optional enhancement endpoints fail.
- `/admin/users/{id}` no longer aligns with `/progress` / `/stats`, or a local progress failure collapses the whole page.
- PPT report pages show sales-only UI, or degraded presentation sessions lose `missing_page_metadata` diagnostics.
- `/support/runtime` reports healthy/warning when the real runtime/report/projection path is actually blocking.
- `/support/runtime` exposes raw transcript / KB content / sensitive upstream error detail instead of compact redacted diagnostics.

## Requirements Proved By This UAT

- R001 — desktop sales runtime remains recoverable and diagnosable through reconnect / end-failure paths.
- R002 — runtime failures remain visible and retryable instead of silently ejecting the learner.
- R005 — canonical learner report remains authoritative even when optional enhancement layers degrade.
- R007 — supervisors can still judge recent progress and repeated blockers from `/admin/users/{id}`.
- R008 — PPT practice still yields a usable shared postmortem in both happy and degraded evidence paths.
- R011 — supporting: release observability stays on the same persisted session evidence line instead of inventing a second truth source.

## Not Proven By This UAT

- Production deployment infrastructure outside the local desktop release story.
- Generic `release_verification` subsystem durability or future milestone reuse.
- Long-run operational SLOs under production traffic.

## Notes for Tester

- Treat S08 as a five-wave release proof, not as one more isolated page check.
- Start from the canonical learner/admin/support surfaces listed above, then use backend API inspection to explain mismatches.
- Record exact session/user IDs, browser console/network findings, and backend diagnostics for each wave.
- The final release conclusion must explicitly separate **blocking** from **warning** and say whether `/support/runtime` reflected that distinction correctly.

## Execution Record — 2026-03-24 current run

### Automated verification gate

- `cd backend && venv/bin/alembic upgrade head` — ✅ pass
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py` — ✅ pass
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses` — ✅ pass
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` — ✅ pass
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'` — ❌ fail
  - failing test: `src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - exact failure: sales report page does not render the expected degraded enhancement copy `综合洞察暂不可用，当前页面仅展示统一训练证据。`
  - this is the same neighboring red test carried forward from T02, not a new support/runtime regression.

### Local stack preflight

- Backend server came up clean on `http://localhost:3444` with `ENVIRONMENT=development` and `PYTHONPATH=src`.
- Web server came up clean on `http://localhost:3445`.
- Same-host localhost alignment was preserved for this run.
- Dev-login token flow worked.

### Wave progress captured before context cutoff

#### Wave 1 — sales runtime

- Verified a published sales agent is available:
  - agent: `dee4a877-2f19-47f4-a326-954f2ab554d5` (`语言的魅力`)
  - persona: `4c99d4d0-965b-439b-b746-33d2e1c55073` (`石犀专家`)
- Created a fresh realtime sales session through the real API path:
  - session: `9fcc3299-724b-4bdd-8a8b-22c98d87d97a`
  - request carried `scenario_type="sales"`, the published `agent_id`, the linked `persona_id`, and `voice_mode="stepfun_realtime"`.
- Browser-side reconnect / end-failure proof did **not** run before the context-budget stop signal.

#### Wave 5 anchor — support runtime evidence snapshot

- Sampled `/api/v1/support/runtime/overview` and `/api/v1/support/runtime/faults` against the live localhost backend.
- Current overview result:
  - release status: `blocking`
  - blocking count: `35`
  - warning count: `9`
  - typed anomaly summary shows blocking `stuck_scoring`, `kb_lock_blocked_empty`, `kb_lock_blocked_search_timeout`, `projection_failed`; warning `upstream_unstable`, `presentation_degraded_missing_page_metadata`
- Current fault sample confirms the typed severity split is live and redacted:
  - blocking examples: `stuck_scoring`, `kb_lock_blocked_empty`, `projection_failed`
  - warning examples: `upstream_unstable`, `presentation_degraded_missing_page_metadata`

### Current release conclusion

- **Blocking right now:**
  1. the S08 web verification command is still red because the sales report page is missing the expected degraded enhancement copy.
  2. support/runtime is already reporting real blocking anomalies in persisted session data (`stuck_scoring`, `kb_lock_blocked_*`, `projection_failed`), so the release surface is not falsely green.
- **Warning right now:** support/runtime also shows warning-only anomalies (`upstream_unstable`, `presentation_degraded_missing_page_metadata`) consistent with the intended typed severity model.
- **Support/runtime truth check:** partial evidence says the support/runtime API is surfacing the expected blocking/warning semantics correctly on the backend side, but the remaining learner/admin/browser waves were not completed in this run, so the full cross-surface mapping proof is still pending.
- **Release verdict for this partial run:** **not ready to declare pass**. Resume with the browser/live waves first, then decide whether the remaining blocking state is a real product regression or only the carried-forward web test failure.

### Precise resume notes for next unit

1. Restart backend on `localhost:3444` and web on `localhost:3445`.
2. Dev-login in the browser context.
3. Resume Wave 1 from fresh sales session `9fcc3299-724b-4bdd-8a8b-22c98d87d97a` if it is still usable; otherwise recreate it with:
   - agent `dee4a877-2f19-47f4-a326-954f2ab554d5`
   - persona `4c99d4d0-965b-439b-b746-33d2e1c55073`
   - `voice_mode="stepfun_realtime"`
4. Complete browser/live waves in order:
   - sales runtime reconnect / end-failure
   - canonical sales report
   - `/admin/users/89e31f06-6393-42b6-877e-5a007803136a`
   - PPT happy/degraded reference sessions `8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b` and `ec5b7b03-a83a-4ee6-bc33-d768ccfec610`
   - `/support/runtime`
5. If the web suite failure is investigated, focus on `web/src/app/(user)/practice/[sessionId]/report/page.tsx` vs test expectation at `page.test.tsx:434-436`; do **not** reopen support/runtime unless the runtime API/browser evidence contradicts the current typed severity output.
