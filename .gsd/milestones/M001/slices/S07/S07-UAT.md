# S07: PPT 对练会后统一复盘可用化 — UAT

**Milestone:** M001
**Written:** 2026-03-24T12:06:53+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S07 changes three layers at once — runtime evidence persistence, the canonical shared report API contract, and the shared learner report page. Passing tests alone would not prove that a real page-turn presentation session can finish, retain page evidence, degrade safely when history is incomplete, and render the PPT branch without slipping back into sales-only UI.

## Preconditions

- Backend is running locally on `http://localhost:3444`.
- Web is running locally on `http://localhost:3445`.
- **Use the same host on both sides.** For this UAT, keep everything on `localhost`; do not mix `localhost` and `127.0.0.1`.
- `POST /api/v1/auth/dev-login` works and returns a usable cookie/token.
- Published presentation agent exists: `7199854c-3921-4d9f-9833-fe99ca209c59` (`ppt训练`).
- Default linked persona exists: `4c99d4d0-965b-439b-b746-33d2e1c55073` (`石犀专家`).
- Ready S07 verification deck exists: `750be5ad-41b6-4752-b772-b4fce6cb9c16` (`S07 演讲复盘验证课件 dd32398d`, 2 pages).
- For the live audio-runtime proof, local tooling can generate audio (`say`, `ffmpeg`) and the backend has the same StepFun/local env dependencies used by the running app.
- Historical reference sessions remain available for direct API/page checks:
  - happy-path reference: `8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b`
  - degraded reference: `ec5b7b03-a83a-4ee6-bc33-d768ccfec610`
- If you intentionally script the presentation websocket for local proof, **do not** use the `type:"text"` shortcut; use real audio chunks plus `page_change`, otherwise the session can complete while still degrading to `missing_page_metadata`.

## Smoke Test

1. Open `http://localhost:3445/login`.
2. In the browser console, run:
   ```js
   await fetch('http://localhost:3444/api/v1/auth/dev-login', {
     method: 'POST',
     credentials: 'include',
   })
   ```
3. Open `http://localhost:3445/practice/8531c7f6-50da-4934-9fd4-63784c791edf/report`.
4. **Expected:** the page opens directly into the PPT branch and shows:
   - `PPT 复盘报告`
   - `PPT 表达能力总览`
   - `逐页总结`
   - `要点覆盖与表达诊断`
   - `按目标再练一轮`
   - no `销售推进结果` / `销售推进基线` / `知识库命中检测`

## Test Cases

### 1. Fresh live session: page-turn runtime must produce a complete presentation review

1. Get a dev token:
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:3444/api/v1/auth/dev-login | jq -r '.data.access_token')
   ```
2. Create a fresh presentation session bound to the published presentation agent/persona and the ready 2-page S07 deck:
   ```bash
   curl -s http://localhost:3444/api/v1/practice/sessions \
     -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{
       "scenario_type":"presentation",
       "presentation_id":"750be5ad-41b6-4752-b772-b4fce6cb9c16",
       "agent_id":"7199854c-3921-4d9f-9833-fe99ca209c59",
       "persona_id":"4c99d4d0-965b-439b-b746-33d2e1c55073",
       "voice_mode":"stepfun_realtime"
     }'
   ```
3. Connect to the real presentation websocket for the returned `session_id`:
   ```text
   ws://localhost:3444/ws/presentation?session_id=<SESSION_ID>&token=<TOKEN>&voice_mode=stepfun_realtime
   ```
4. Send `{"type":"control","data":{"action":"start"}}`.
5. Send real audio chunks for page 1 (16 kHz mono PCM16) describing page 1 content, then send `{"type":"audio_end","data":{}}`.
6. Wait until page 1 user evidence is persisted and the runtime returns to listening.
7. Send `{"type":"page_change","data":{"page_number":2}}` and confirm the websocket emits page-2 context (`slide_update` with `current_page=2`).
8. Send real audio chunks for page 2, then send `{"type":"audio_end","data":{}}`.
9. Send `{"type":"control","data":{"action":"end"}}` and wait for session end / report generation.
10. Call:
    ```bash
    curl -s http://localhost:3444/api/v1/practice/sessions/<SESSION_ID>/report \
      -H "Authorization: Bearer $TOKEN" | jq '.'
    ```
11. **Expected:**
    - `data.scenario_type == "presentation"`
    - `data.presentation_review` exists
    - `data.evidence_completeness.page_metadata_complete == true`
    - `data.presentation_review.page_summaries | length == 2`
    - `data.presentation_review.required_talking_points.status == "complete"`
    - `data.evidence_completeness.degraded_reasons == []`
    - `data.main_issue == null` and `data.next_goal == null`
    - `data.retry_entry.presentation_id == "750be5ad-41b6-4752-b772-b4fce6cb9c16"`

### 2. Shared report page happy path: the learner report must stay PPT-shaped

1. Dev-login in the browser on `localhost` as in the smoke test.
2. Open the fresh happy-path session report (from test case 1) or the reference happy session:
   ```text
   http://localhost:3445/practice/8531c7f6-50da-4934-9fd4-63784c791edf/report
   ```
3. Read the report top section and the first screen below it.
4. **Expected:**
   - top of page says `PPT 复盘报告`
   - report explains PPT scoring semantics instead of sales semantics
   - `PPT 表达能力总览` shows six dimensions including `流畅连贯性`, `准确性`, `专业性`, `生动性`, `互动问答`, `其他表现`
   - `逐页总结` shows page-specific entries (for the reference session, page 1 and page 2 both render)
   - `要点覆盖与表达诊断` shows coverage counts and issue counts
   - `按目标再练一轮` is visible
   - `销售推进结果`, `销售推进基线`, and `知识库命中检测` are absent
   - the page stays useful even if highlights are empty or enhanced insights are unavailable

### 3. Historical degraded path: missing page evidence must remain presentation-shaped

1. Call the canonical report route for the historical degraded session:
   ```bash
   curl -s http://localhost:3444/api/v1/practice/sessions/ec5b7b03-a83a-4ee6-bc33-d768ccfec610/report \
     -H "Authorization: Bearer $TOKEN" | jq '.'
   ```
2. **Expected:**
   - `data.scenario_type == "presentation"`
   - `data.presentation_review.coverage_status == "degraded"`
   - `data.presentation_review.required_talking_points.status == "degraded"`
   - `data.evidence_completeness.page_metadata_complete == false`
   - `data.evidence_completeness.degraded_reasons` is non-empty (`missing_page_metadata`)
   - `data.main_issue == null`
   - `data.next_goal == null`
   - the response does **not** fall back to sales-only judgment language
3. Open the degraded session page in the browser:
   ```text
   http://localhost:3445/practice/ec5b7b03-a83a-4ee6-bc33-d768ccfec610/report
   ```
4. **Expected:**
   - the page still renders the PPT branch
   - it shows presentation-specific degraded copy about missing page evidence
   - it does not render sales-only cards or knowledge-check UI

### 4. Retry continuity: the next session must stay on the same presentation line

1. On the happy-path report page, click `按目标再练一轮`.
2. Wait for navigation.
3. **Expected:**
   - browser moves to a new `/practice/<NEW_SESSION_ID>` URL
   - URL keeps `scenario_type=presentation`
   - URL keeps `presentation_id=750be5ad-41b6-4752-b772-b4fce6cb9c16`
   - if agent/persona are present on the source session, the URL also preserves `agent_id` and `persona_id`
   - the new page opens as a presentation practice session rather than redirecting to a sales flow or losing the deck binding

## Edge Cases

### Host mismatch creates a false report-auth regression

1. Dev-login on `http://127.0.0.1:3444` but open the web app on `http://localhost:3445` (or the reverse).
2. **Expected:** the report page may 401 because the host-only auth cookie is attached to the other loopback host. Treat this as an environment/UAT setup failure, not a product regression.

### Text shortcut falsely “passes” runtime while still degrading the report

1. Create a presentation session and drive the StepFun websocket with `{"type":"text"}` messages plus `page_change`, instead of real audio chunks.
2. **Expected:** the session may still complete, but `/practice/sessions/{id}/report` can return `missing_page_metadata` degraded output. Do not accept this as proof that page-level evidence is working.

### Optional enhanced layers are missing but the canonical report still works

1. Load a happy-path report where `/evaluation/.../report` or `/sessions/{id}/highlights` is slow, empty, or unavailable.
2. **Expected:** the page keeps the canonical PPT report visible; optional enhancement copy may degrade, but the base PPT review remains readable and authoritative.

## Failure Signals

- `/api/v1/practice/sessions/{id}/report` returns `scenario_type="sales"` for a presentation session.
- Historical missing-page sessions fall back to sales `main_issue`, `next_goal`, or sales-only sections.
- Fresh page-turn runtime sessions end with `page_metadata_complete=false` when driven through the real audio path.
- Shared report page shows `销售推进结果`, `销售推进基线`, or `知识库命中检测` for presentation sessions.
- Retry CTA drops `presentation_id` or navigates into a sales session.
- Browser report fetches 401 because localhost/127 hosts are mixed during UAT.

## Requirements Proved By This UAT

- R008 — a learner can finish a PPT practice and receive a usable, page-aware unified review from the shared report entrypoint.
- R011 — advanced: presentation sessions now project review facts and degraded completeness onto the same canonical report route used elsewhere in the product.

## Not Proven By This UAT

- Real-time interruption coaching during PPT delivery (still deferred).
- Milestone-wide release readiness across all sales + supervisor + PPT paths (belongs to S08).
- Long-run operational observability for every optional enhancement endpoint under production traffic.

## Notes for Tester

- Start from the canonical surfaces in this order: `/practice/sessions/{id}/report`, focused backend tests, then the browser report page.
- For the live runtime proof, reuse the actual S07 verification deck and published agent/persona pair above rather than guessing IDs from other materials.
- Keep the UAT honest: if you use the websocket `type:"text"` shortcut, record that as a degraded local probe, not as slice proof.
- When you finish, stop any local backend/web servers or websocket probes you started so later auto-mode health checks do not inherit stale processes.
