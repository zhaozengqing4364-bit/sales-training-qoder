# Audit 26 Phase 1-2 contract and boundary review

Date: 2026-04-20  
Worker: worker-3  
Scope source: `.omx/plans/ralplan-audit-26-remediation-plan.md`, PRD, test spec, and `.omx/context/audit-26-remediation-plan-20260420T025004Z.md`  
Execution scope: review/documentation only; no Docker, deployment, operations, or infrastructure changes.

## Scope reviewed

This review covers the documentation deliverables from the first executable tranche:

1. **Issue 7 / high-complexity file risk** — freeze the current realtime/practice boundary, outward message/API contract, and targeted regression list before any later extraction.
2. **Issue 10 / today retry foundation** — freeze the `/recommendations/latest` retry-task contract so the dashboard can evolve into a “今日复练” task card without each page inventing its own eligibility or routing rules.
3. **Phase 1-2 quality guardrail** — identify the seams that must not be widened by worker lanes A-D/E without leader coordination.

No business source files were changed in this slice. The goal is to reduce integration risk for the implementation and test lanes.

## Source evidence snapshot

| Area | Evidence read | Current state |
| --- | --- | --- |
| Realtime handler | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | Single `StepFunRealtimeHandler` remains large, but its outward protocol is documented in the class docstring: incoming `audio_chunk/audio_end/text/control/user_speaking/interrupt`, outgoing `asr_transcript/status/tts_audio/error/heartbeat`; it also emits score/fuzzy/action-card style runtime messages from helper methods. |
| Practice lifecycle | `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` | REST lifecycle owns start/pause/resume/end and navigates only after server terminal status. It currently stops recording before report navigation but does not yet wait for continuous-audio bounded flush. |
| Continuous audio audit | `web/src/hooks/use-continuous-audio-uploader.ts` | Segment signing, OSS PUT, register, and failure-register all go through the unified API client/backend endpoints, but `stopUpload()` currently only waits one tick for the final blob and does not expose `pendingUploads` or `flushAndStop()`. |
| Recommendation backend | `backend/src/common/api/dashboard.py` | `/recommendations/latest` already returns sales retry and PPT page retry branches using `Recommendation` plus `PracticeRetryEntryAssembler`, with fallback recommendations for no/weak/recent sessions. |
| Recommendation frontend | `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/app/(dashboard)/page.tsx` | Frontend consumes the unified client `api.dashboard.getRecommendation()` and currently recognizes `sales_retry` and `presentation_page_retry` source copy. |
| Retry focus intent | `backend/src/common/services/practice_session_service.py`, report/replay/dashboard pages | Canonical sales retry focus intent is `retry_focus_v1` with sanitized `source_session_id`, `main_issue`, and `next_goal`; report/replay already pass it into focused retry entry routes. |

## Boundary map for Issue 7

### 1. Backend realtime boundary

**Current owner:** `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` and existing component helpers under `backend/src/sales_bot/websocket/components/`.

**Stable outward contract:**

- Incoming frontend JSON message types that must remain accepted: `audio_chunk`, `audio_end`, `text`, `control`, `user_speaking`, `interrupt`.
- Binary audio frames remain the preferred PCM path and must continue to map to upstream realtime audio append without changing frontend framing.
- Outgoing event families that must remain shape-compatible for `web/src/hooks/use-practice-websocket.ts` and `web/src/hooks/websocket/message-handlers.ts`:
  - `asr_transcript` for interim/final transcript projection.
  - `status` for `session_status`, `ai_state`, `turn_count`, `trace_id`.
  - `tts_audio` / streaming audio chunk events for playback.
  - `error` for user-visible realtime errors and blocked input states.
  - `heartbeat` for liveness.
  - Current extended runtime events such as `score_update`, `fuzzy_detection`, action cards, interruptions, reconnect state, and coach-health updates.

**Do not split yet:** Phase 1-2 must not extract StepFun responsibilities unless a test first locks the outward WebSocket contract. Later extraction should move only one internal responsibility per slice, for example:

1. policy/runtime config resolution;
2. input routing and lifecycle-gated input rejection;
3. score/action/fuzzy emission;
4. upstream disconnect recovery;
5. transcript persistence and message normalization.

Each extraction must keep the message names and payload keys stable unless a migration plan updates both backend and frontend tests in the same slice.

### 2. Practice page/frontend boundary

**Current owners:**

- `web/src/app/(user)/practice/[sessionId]/page.tsx` — visible practice shell and state composition.
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` — REST lifecycle orchestration and report navigation.
- `web/src/hooks/use-practice-websocket.ts` plus `web/src/hooks/websocket/*` — WebSocket connection, outbound pacing, and inbound projection.
- `web/src/hooks/use-continuous-audio-uploader.ts` — durable audio audit upload trail.

**Phase 2 allowed change boundary:**

- Add `PracticeFaultPanel` or equivalent UI composition beside the practice shell without changing WebSocket protocol keys.
- Extend lifecycle/uploader coordination for bounded flush, but preserve existing uploader signing/PUT/register/failure-register behavior.
- Do not modify dashboard recommendation contracts from this lane; route cross-cutting type/API changes through the leader or Lane E.

**Known gap to close in implementation lanes:**

- `usePracticeSessionLifecycle` navigates to `/practice/{sessionId}/report` as soon as server status is `completed` or `scoring`; it stops the live recorder but does not await durable audio segment registration.
- `useContinuousAudioUploader.stopUpload()` stops the recorder and waits only a short timer before clearing state. It should evolve into `flushAndStop()` with bounded pending-upload accounting and explicit `completed | failed | timed_out` outcome for the practice page/report explanation.

### 3. Backend practice REST boundary

**Current owners:**

- `backend/src/common/api/practice.py` — session lifecycle, report, history, audio segment upload/register APIs.
- `backend/src/common/services/practice_session_service.py` — create/lifecycle application services and retry-entry assembler.

**Stable API surfaces for Phase 1-2:**

- Existing practice session lifecycle endpoints and response payloads stay compatible.
- Existing report/replay retry entry shape stays compatible.
- Audio segment APIs remain the durable evidence path; implementation lanes may add explicit flush status consumption in the frontend but should not rename backend audio endpoints.

## `/recommendations/latest` contract snapshot for Issue 10

### Current response envelope

The current frontend API client calls `GET /recommendations/latest` through `api.dashboard.getRecommendation()` and expects the normal API client to unwrap the backend envelope into a `Recommendation` object. The object currently contains:

| Field | Required now | Meaning |
| --- | --- | --- |
| `title` | yes | Card title. |
| `reason` | yes | User-visible recommendation reason. |
| `action_label` | yes | CTA text. |
| `target_path` | yes | Internal learner route. |
| `score_basis` | optional | Evidence basis, currently used for sales retry source copy. |
| `recommendation_kind` | optional | Current known values: `sales_retry`, `presentation_page_retry`. |
| `scenario_type` | optional | Current known values: `sales`, `presentation`. |
| `source_session_id` | optional | Source practice session for retry/report context. |
| `focus_page` | optional | PPT page retry focus. |

### Phase 3-ready fields to add without breaking current clients

When the “今日复练” task card is implemented, add these fields as optional first on both backend and frontend types:

| Field | Type | Rule |
| --- | --- | --- |
| `due_reason` | string \| null | Short label for why this is due today, e.g. `上次主问题`, `PPT 第 5 页缺口`, `完成一次可评估训练`. |
| `focus` | object \| null | Display-safe focus summary. For sales, include sanitized `main_issue`/`next_goal`; for PPT, include `page_number` and missing-point summary. Do not expose raw evaluator payloads. |
| `suggested_duration_minutes` | number \| null | UI hint only; safe defaults: sales retry 10, PPT page retry 5, first practice 10. |
| `is_due_today` | boolean | `true` only for retry-eligible completed/evaluable evidence or explicit “start first eligible practice” task; `false` for generic weak-score/frequency suggestions. |
| `eligibility` | `retry_eligible` \| `score_eligible` \| `explanation_only` \| null | Optional but recommended to prevent growth UI from treating evidence-poor sessions as achievements. |

These additions must be backward compatible: the existing dashboard should still render using `title`, `reason`, `action_label`, and `target_path` if the new fields are absent.

### Branch rules

1. **Sales retry (`sales_retry`)**
   - Source: last completed sales session with sanitized `main_issue` or `next_goal`.
   - Route: `/agents/{agent_id}?persona_id={persona_id}&focus_intent={encoded retry_focus_v1}` when both IDs and focus intent exist; otherwise `/training/sales` with reason explaining that the learner must reselect missing configuration.
   - Eligibility: `retry_eligible`; also `score_eligible` only if the source session is completed and evaluable.

2. **PPT page retry (`presentation_page_retry`)**
   - Source: last completed presentation session with `presentation_review.page_summaries` containing missing required points or issue clusters.
   - Route: `/practice/{source_session_id}/report?focus=presentation_page&page={focus_page}` for the first/safest page-level task.
   - Eligibility: `retry_eligible`; page-level retry can be valid even if it is not a sales-score event.

3. **No completed/evaluable record**
   - Route: `/training` or a specific training lobby route.
   - Eligibility: `explanation_only` until the learner completes a practice with enough evidence.
   - UI copy must not display zero stats or low-score shame; it should explain that a complete practice creates the first reviewable report.

4. **Generic weak-score/frequency fallback**
   - Keep as a recommendation but do not mark it as a “today due retry” unless it has `source_session_id` plus a concrete focus.
   - If exposed in the today card, label it as “建议练习” instead of “复练任务”.

## Regression list to lock before later extraction

### Backend targeted checks

| Surface | Command | Acceptance |
| --- | --- | --- |
| Dashboard recommendation contract | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_dashboard_recommendation.py -x -q` | Collects/runs without `rank_bm25`/`jwt` import blockers after Lane A dependency work; covers sales retry, PPT page retry, no-record fallback. |
| Audio segment API | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_audio_audit_contract.py -x -q` | Signing/register/failure-register contract remains stable. |
| Lifecycle API | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q` | Start/pause/resume/end state transitions remain compatible. |
| WebSocket status/reconnect | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -x -q` | Message/status/reconnect payloads remain stable. |

### Frontend targeted checks

| Surface | Command | Acceptance |
| --- | --- | --- |
| Dashboard today retry card | `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx"` | Existing sales/PPT retry tests keep passing; new `due_reason`, `focus`, duration, and due-today rendering are added when fields land. |
| Practice multi-fault panel | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx"` | Connection, microphone, lifecycle, session, and audio upload errors are visible together. |
| Lifecycle bounded flush | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts" "src/hooks/use-continuous-audio-uploader.test.ts"` | End-session waits for bounded audio flush outcome before report navigation or records explicit failure/timeout state. |
| WebSocket projection | `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/hooks/websocket/message-handlers.test.ts"` | Existing realtime message names and projection behavior stay stable. |
| Type/lint gate | `npm --prefix web exec tsc -- --noEmit` and `npm --prefix web exec eslint -- . --quiet` | Required before merging frontend API type changes. |

### Static review gates

- `rg -n "NEXT_PUBLIC_API_URL.*fetch|fetch\(.*NEXT_PUBLIC_API_URL" web/src/app web/src/components web/src/lib` should not find new direct backend fetches outside approved low-level API client or special presigned upload cases.
- `rg -n "class RoleChecker|RoleChecker" backend/src backend/tests` should either be empty or point to a real denying wrapper plus tests, never an always-allow helper.
- `rg -n "recommendation_kind|focus_intent|retry_entry" backend/src/common web/src` should show one canonical producer path and no page-local incompatible focus schemas.

## Integration notes for leader

- Treat `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, and `backend/src/common/api/dashboard.py` as shared files. If Lane D adds the dashboard card while Lane E adds backend contract fields, merge through the leader to avoid divergent optional-field names.
- Keep today retry fields optional until both backend and frontend tests land. That lets current dashboard behavior remain compatible during incremental integration.
- Do not use Issue 10 to implement all Phase 3 growth UI. The first safe cut is contract + dashboard card only; history aggregation, sales combination reordering, and report next-action card remain follow-up phases unless separately approved.
- Do not use Issue 7 as permission for a large realtime split. The next code slice should be a test-locking or one-responsibility extraction only.

## Verification evidence for this documentation slice

- Plan/PRD/test-spec/context read: `.omx/plans/ralplan-audit-26-remediation-plan.md`, `.omx/plans/prd-audit-26-remediation-plan.md`, `.omx/plans/test-spec-audit-26-remediation-plan.md`, `.omx/context/audit-26-remediation-plan-20260420T025004Z.md`.
- Code evidence inspected: realtime handler symbols and protocol helpers, practice lifecycle/uploader hooks, dashboard recommendation backend/frontend types/tests, retry-entry assembler, report/replay retry references.
- Source changes: documentation only (`docs/plans/2026-04-20-audit-26-contract-boundary-review.md`).

## Post-integration review addendum — worker-2

Date: 2026-04-20  
Reviewer: worker-2  
Scope: task-3 code-quality/documentation review after Lane A/B/C/D integration checkpoints currently present in this worktree. This addendum does not broaden Phase 1-2 scope and does not introduce Docker, deployment, operations, or infrastructure guidance.

### Review result

No blocking review findings were found in the current Phase 1-2 slice. The current changes keep the planned boundaries mostly intact:

- **Admin TTS preview** now uses the unified frontend API client seam for settings and persona preview audio. The admin pages no longer construct `NEXT_PUBLIC_API_URL` fetches directly, so base URL resolution, cookie credentials, CSRF header attachment, loopback fallback, and `ApiRequestError` normalization stay centralized.
- **RoleChecker always-allow risk** is removed from `backend/src/common/middleware/auth.py`; the remaining `RoleChecker` reference is a unit guard asserting the helper is absent.
- **Response envelope helper** exists at `backend/src/common/api/response.py`, and the dashboard touched endpoints import that helper. Existing local helpers still remain in broader legacy endpoints such as `practice.py`, `training.py`, `users.py`, and `knowledge_debug.py`; that is acceptable for the approved minimal slice because the plan explicitly rejects a full envelope migration in Phase 1-2.
- **Today retry foundation** keeps retry fields optional on the frontend type and dashboard rendering, preserving current recommendation compatibility while enabling the future “今日复练” card.
- **Practice audio flush work** remains frontend-bounded and does not rename backend audio segment endpoints, preserving the durable evidence API surface documented above.

### Non-blocking risks to carry forward

1. `web/src/lib/api/client.ts` is still a shared high-churn file. Future admin/export/blob endpoints should reuse the existing low-level helpers instead of adding page-local fetches.
2. Backend response helper adoption is intentionally partial. Do not treat the new helper as permission for a broad legacy endpoint migration without endpoint-specific contract tests.
3. The practice audio flush state is user-visible and should remain covered by focused hook/page tests whenever the report navigation timing changes.
4. The dashboard today-retry copy should continue to distinguish retry-eligible evidence from generic recommendations; missing evidence must stay explanatory rather than gamified.

### Additional review gates run by this addendum

- Direct admin preview fetch gate: `rg -n 'NEXT_PUBLIC_API_URL|fetch\(' web/src/app/admin/settings web/src/app/admin/personas -g '*.ts*'` should return no matches.
- RoleChecker guard: `rg -n 'class RoleChecker|RoleChecker' backend/src backend/tests` should only find the absence guard test.
- Response helper adoption check: `rg -n 'from common.api.response|common.api.response' backend/src/common/api backend/tests/unit/common -g '*.py'` should include `dashboard.py`, `server_error.py`, and `test_api_response.py`.
