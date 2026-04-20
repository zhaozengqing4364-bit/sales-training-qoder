# S04: AI quality/cost/failure events 与 knowledge path 收口 — UAT

**Milestone:** M021
**Written:** 2026-04-14T04:47:44.677Z

# S04 UAT — AI runtime events, knowledge path mode, and explicit degraded/failure proof

## Preconditions
- Backend is running with the S04 code and test data/fixtures that can produce: (a) a completed session with knowledge diagnostics, (b) a support/runtime fault item, and (c) a report/replay response that exercises `compatibility_reader` and retrieval failure copy.
- Web app is running against the same backend build.
- Use the existing routes and diagnostics surfaces; do **not** rely on ad-hoc logs or temporary debug endpoints.

## Test Case 1 — Knowledge-check exposes unified runtime events and explicit path mode
1. Open a session whose knowledge-answer diagnostics are available through `GET /api/v1/practice/sessions/{sessionId}/knowledge-check`.
2. Inspect the response and locate `runtime_events` (or the mirrored runtime diagnostics block that now carries those events).
3. Confirm there is a `knowledge_answer_path_mode` event.
4. Confirm that event uses:
   - `category = "mode"`
   - `status = "live"` or `"compat"`
   - an explanatory `summary`
5. Confirm at least one knowledge-quality / claim-truth event is also present when the fixture includes degraded or failure conditions.
6. Confirm `details` and `metrics` contain only allowlisted diagnostics and do **not** expose secrets such as provider tokens, raw request bodies, or `base_url`.

**Expected result:** knowledge-check shows one explicit runtime-event line that makes both provenance (`live|compat`) and degraded/failure state inspectable without reading fallback copy or hidden logs.

## Test Case 2 — Support/runtime faults reuse the same event contract
1. Open `/api/v1/support/runtime/faults` for a session/fault fixture that includes S04 runtime diagnostics.
2. Pick one fault item and inspect `items[].diagnostics.runtime_events[]`.
3. Verify the event objects use the documented S04 schema:
   - `event_id`
   - `category`
   - `severity`
   - `status`
   - `source`
   - `summary`
   - `details`
   - `metrics`
   - `occurred_at`
4. Confirm there is no second support-only status payload for the same AI/runtime condition.
5. Confirm failure and degraded semantics are explicit on the events themselves (for example knowledge failure, kb lock degradation, claim-truth degradation, or report-generation failure) rather than implied through a vague status string.
6. Confirm no secret-bearing fields are leaked.

**Expected result:** support/runtime faults read the same runtime-event truth line as knowledge-check/websocket diagnostics, and operators can distinguish `mode`, `degraded`, `failure`, and `cost` without reverse-engineering raw payloads.

## Test Case 3 — Learner report keeps compatibility reads explicit
1. Open `/practice/{sessionId}/report` for a completed session whose score rollups come from the compatibility reader path.
2. Inspect the score/evidence source marker already used by the page (`data-contract-source`).
3. Confirm the page marks the source as `compatibility_reader` instead of pretending the canonical kernel was present.
4. Confirm the report still renders the existing compatibility badge / explicit source cue instead of silently flattening everything into a generic success state.
5. If the same session also has retrieval degradation/failure, confirm the report copy remains explicit about the failure reason rather than phrasing it like a normal low-quality success.

**Expected result:** report proof makes compat source and failure semantics explicit on the existing page contract, with no new hidden fallback path.

## Test Case 4 — Learner replay mirrors the same compat/failure proof
1. Open `/practice/{sessionId}/replay` for a completed session that uses compatibility-reader score fallback.
2. Confirm replay exposes the same explicit source cue (`data-contract-source="compatibility_reader"`) instead of silently translating it into a canonical read.
3. Validate that replay and report agree on the visible compat/failure semantics for the same session.
4. Open a still-incomplete session and confirm replay remains explicitly blocked with the existing completion-gated message rather than rendering a partial replay that looks successful.

**Expected result:** replay stays aligned with report on compat/failure truth, and unfinished-session blocking remains explicit rather than becoming a silent degraded success.

## Edge Case Checks
- **Retrieval/search failure:** a `search_failed` or analogous degraded/failure knowledge event must stay explicit on diagnostics/read-side surfaces; it must not collapse into a normal hit/miss success explanation.
- **LLM fallback/default-score path:** if evaluation/report generation falls back, the runtime-event line must expose an explicit degraded/failure or cost signal rather than leaving only a generic filler sentence.
- **Fixture/schema drift:** if support/runtime fault verification fails before reaching your intended assertion because a test DB lacks `knowledge_bases`, treat that as fixture/schema drift. Re-run with KB-free fixtures or seed the KB tables, then verify the runtime-event contract itself.
