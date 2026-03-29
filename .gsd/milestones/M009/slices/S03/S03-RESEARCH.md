# M009 / S03 — Research

**Date:** 2026-03-28

## Summary

S03 is a targeted closure slice on top of S01/S02, not a new OSS integration. The shipped architecture already has the right user-facing and admin-facing seams:

- learner read side: `backend/src/common/api/practice.py::build_session_audio_audit(...)` feeding both report and replay
- learner UI: shared `web/src/components/audio/AudioAuditCard.tsx`
- admin/support diagnostics: `backend/src/support/services/runtime_status_service.py` → `web/src/app/(dashboard)/support/runtime/page.tsx`

The real gap is not playback wiring; it is **durable failure truth**.

Today the model already supports degraded audio facts:
- `backend/src/common/db/models.py::SessionAudioSegment` has `upload_status` (`pending|uploaded|failed`) and `error_message`

But the shipped write path does not preserve browser failures:
- `web/src/hooks/use-continuous-audio-uploader.ts` only calls `POST /practice/sessions/{id}/audio-segments` after a successful PUT
- `backend/src/common/api/practice.py::register_audio_segment(...)` only writes `upload_status="uploaded"`
- `voice_policy_snapshot.runtime_metrics.audio_audit` only tracks uploaded counts/bytes, not failed counts or last failure reason

Result: report/replay can show `partial` if rows already exist with `pending`, but they cannot explain **why** a session degraded unless test fixtures manually seed those rows. Support runtime cannot classify audio anomalies at all because `RuntimeStatusService` never reads segment state.

This slice supports the M009 requirements from context:
- **R024** 训练原始音频持续留痕并落 OSS
- **R025** 浏览器直连 OSS，服务端不做音频中转
- **R026** 学员在现有 report/replay 路径可反查原始录音证据
- operational closure for partial/missing/failed audio evidence on learner and support surfaces

Skill guidance that matters here:
- **safe-grow**: keep this to one issue family — audio degraded truth — and reuse existing route families instead of adding a new audit console.
- **fastapi-python**: if the audio-segment write contract expands beyond the current ad-hoc dict body, prefer an explicit Pydantic request model over widening raw `dict[str, Any]` parsing further.
- **react-best-practices**: keep degraded wording in the shared `AudioAuditCard` and shared client helper, not duplicated in report and replay pages.

## Recommendation

Plan S03 as three tight seams, in this order:

1. **Backend: persist audio failure/degraded facts on the existing session-audio seam.**
   Extend the existing audio-segment registration flow so browser failures can be recorded durably (`failed` / `pending`, plus compact reason/error token). Also extend bounded `voice_policy_snapshot.runtime_metrics.audio_audit` so support/runtime can classify anomalies without querying full segment catalogs per page load.

2. **Learner read side: enrich shared `audio_audit` payload with explicit degraded reasons.**
   `learner_status` (`available|partial|missing`) is too coarse for S03. The shared payload needs enough summary/segment fields to explain cases like:
   - upload failed during recording
   - some segments missing
   - playback handoff failed / segment not uploaded
   - signing/read failure

3. **Frontend + support runtime: consume the same degraded truth.**
   - `AudioAuditCard` should render learner-facing degraded wording from canonical summary fields, not from page-local heuristics.
   - `RuntimeStatusService` should classify audio anomalies into the existing typed fault list so `/support/runtime` can show them alongside `stuck_scoring`, `knowledge_search_failed`, etc.

Avoid inventing:
- a new admin-only audio route family
- page-local wording drift between report and replay
- OSS-expiry-specific browser UAT as the primary proof; unit/contract tests are more reliable here

## Implementation Landscape

### Key files

- `backend/src/common/db/models.py`
  - `SessionAudioSegment` already has the right storage columns: `upload_status`, `error_message`, `size_bytes`, `duration_ms`, `object_key`, unique `(session_id, segment_sequence)`.
  - This is the durable catalog seam; do not move failure truth into a new table.

- `backend/src/common/api/practice.py`
  - `build_session_audio_audit(...)` is the canonical learner read-side builder for both report and replay.
  - It currently derives:
    - `learner_status = available|partial|missing`
    - per-segment `playback_path` only when `upload_status == "uploaded"`
  - It currently **does not expose** `error_message`, failed counts, or degraded-reason fields.
  - `register_audio_segment(...)` only writes successful uploads and updates snapshot metrics with uploaded counters.

- `backend/src/common/db/schemas.py`
  - `AudioAuditSegmentSchema` exposes `segment_sequence`, timestamps, size, duration, `upload_status`, `playback_path`
  - `AudioAuditSummarySchema` exposes `recording_status`, counts, bytes, prefix, `learner_status`
  - No room yet for `failed_segments`, `degraded_reasons`, `last_error`, etc.

- `backend/src/common/conversation/api.py`
  - `GET /sessions/{session_id}/audio-segments/{segment_sequence}` signs playback handoff at read time.
  - Failure modes already exist and return structured API errors:
    - `[SEGMENT_NOT_FOUND]`
    - `[SEGMENT_NOT_UPLOADED]`
    - `[SIGNING_FAILED]`
  - Good seam for playback diagnostics; no need for a new playback route.

- `web/src/hooks/use-continuous-audio-uploader.ts`
  - Browser-side direct upload pipeline: sign → PUT → register
  - Tracks `lastError`, `uploadStatus`, `segmentCount` in hook state
  - On failure it only updates local state; it does **not** persist a failed segment row or update runtime metrics remotely
  - This is the main reason S03 cannot explain degraded sessions truthfully today.

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
  - Starts/stops `useContinuousAudioUploader` in lockstep with microphone recording
  - Does **not** render `continuousUploader.lastError`, `uploadStatus`, or `segmentCount`
  - This slice does not need to grow live practice UI unless required for recording-status persistence; report/replay/support remain the main target surfaces.

- `web/src/components/audio/AudioAuditCard.tsx`
  - Shared learner component used by both report and replay
  - Current states:
    - no payload / missing → “本次训练未录制原始音频”
    - partial → badge `部分`
    - available → badge `完整`
  - Per-segment playback errors collapse to generic `加载失败` / `播放失败`
  - This is the right place for S03 learner wording.

- `web/src/lib/api/client.ts`
  - `getSegmentAudioBlobUrl(...)` currently does raw `fetch()` and throws `Error("HTTP n")`
  - It loses backend error codes like `[SEGMENT_NOT_UPLOADED]` or `[SIGNING_FAILED]`
  - If S03 wants differentiated learner wording for playback failures, this helper needs normalization similar to the rest of the API client.

- `backend/src/support/services/runtime_status_service.py`
  - Builds typed support/runtime anomalies from session status, projection, knowledge diagnostics, and presentation review
  - Currently no audio-specific anomaly kinds
  - It already accepts flexible `diagnostics` payloads and the frontend renders arbitrary chips from them, so audio can fit this system cleanly.

- `web/src/app/(dashboard)/support/runtime/page.tsx`
  - Renders typed anomalies generically from `kind`, `summary`, and `diagnostics`
  - Likely needs little or no component logic change if backend emits audio kinds.

### What already exists in tests

- `backend/tests/contract/test_practice_evidence_contract.py`
  - proves report/replay parity for `audio_audit`
  - proves `partial` when one row is `uploaded` and another is `pending`
  - does **not** prove learner-facing failed reasons or support-runtime audio anomalies

- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - proves missing-audio fallback copy
  - does not yet lock explicit degraded wording for partial/failed playback cases

- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - proves the audio card renders in replay
  - does not yet lock degraded wording or playback-failure differentiation

- `backend/tests/unit/test_support_runtime_service.py`
  - already uses typed anomaly pattern (`kind`, `severity`, `summary`, `diagnostics`)
  - easiest place to add audio anomaly classification proof

- `web/src/hooks/use-continuous-audio-uploader.test.ts`
  - already proves sign/PUT/register success and that failures stay local without crashing the loop
  - this test file is the best place to lock any new “fire failure metadata to backend” behavior

## Build Order

1. **Backend persistence + read-model extension**
   - Extend the audio-segment write contract so failed or incomplete attempts can be durably registered on the existing `SessionAudioSegment` row.
   - Extend snapshot `runtime_metrics.audio_audit` with bounded failure summary fields suitable for support/runtime.
   - Extend `AudioAuditSummarySchema` / `AudioAuditSegmentSchema` with explicit degraded facts.

2. **Shared learner surface**
   - Update `AudioAuditCard` to consume canonical degraded fields.
   - Update `getSegmentAudioBlobUrl(...)` so playback failures preserve structured error codes instead of collapsing to `HTTP 404`.

3. **Support-runtime classification**
   - Add audio anomaly kinds in `RuntimeStatusService` using bounded snapshot/read-model facts.
   - Reuse existing `/support/runtime` page and test pattern; avoid new admin UI.

## Verification Approach

### Backend

Use focused suites only; this slice is contract/read-side work.

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_audio_segment_api.py backend/tests/unit/test_support_runtime_service.py`
- If write-contract changes land in the uploader path, also run:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_audio_audit_contract.py`

What to prove:
- report and replay expose the same enriched `audio_audit` payload
- failed/pending rows yield explicit degraded reasons, not just `partial`
- playback handoff still never persists signed URLs
- support/runtime emits typed audio anomaly kinds with stable diagnostics

### Frontend

- `pnpm --dir web exec vitest run 'src/hooks/use-continuous-audio-uploader.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'`

What to prove:
- shared `AudioAuditCard` renders degraded wording for partial/failed states
- playback failure messages are specific enough to distinguish unavailable/not-uploaded vs generic load failure
- support runtime renders new audio anomaly rows without client-side severity inference

### Optional live proof

Only if time permits and a local app is already running. Do not make OSS URL expiry the main proof. Safer live checks are:
- seeded session with failed/pending rows opens on `/practice/{sessionId}/report`
- same seeded session opens on `/sessions/{id}/replay`
- `/support/runtime` shows the corresponding typed audio anomaly

## Constraints

- `build_session_audio_audit(...)` returns `None` when there are no segment rows at all. That distinction is already shipped and should stay intact; do not synthesize a fake payload for sessions that never recorded.
- `AudioAuditCard` is the shared learner seam; report/replay pages should keep delegating to it.
- `RuntimeStatusService` currently builds records from sessions + messages, not segment catalogs. If audio anomaly logic needs segment facts, prefer bounded snapshot metrics or one batched aggregate query — do not introduce per-session N+1 segment scans.
- `getSegmentAudioBlobUrl(...)` currently bypasses the structured API error path. Any differentiated playback wording depends on fixing this helper or adding a purpose-built normalized variant.
- The current practice page holds uploader failure state locally but does not surface it. S03 can still complete without a live-practice UI change if the failure truth is persisted and later rendered on report/replay/support.

## Common Pitfalls

- **Assuming `learner_status` is enough.** It only says available/partial/missing; it does not explain *why* the session degraded.
- **Adding page-local wording in report/replay separately.** Use `AudioAuditCard` so copy does not drift.
- **Treating support-runtime as a separate audio console.** Reuse the existing typed anomaly system.
- **Relying on actual signed URL expiry in tests.** Contract/unit tests should simulate `[SEGMENT_NOT_UPLOADED]`, `[SEGMENT_NOT_FOUND]`, and `[SIGNING_FAILED]` directly.
- **Persisting signed GET URLs.** Keep the current read-time handoff pattern.

## Open Risks

- The cleanest backend design is to persist compact failure tokens, not raw browser/network strings. If the implementation stores full free-form errors, learner/admin wording will drift and tests will be brittle.
- If support-runtime audio classification depends on full segment-table scans per session, this slice can accidentally turn a low-risk read-side extension into an expensive N+1 path.
- `recording_status` is present in the schema/read model but I did not find a live writer updating it in the current uploader path. If S03 wants truthful “录制中/已结束/异常中断” wording, that field likely needs real write-side updates rather than more frontend inference.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI / Pydantic | `fastapi-python` | installed (preinstalled) |
| React / Next.js | `react-best-practices` | installed (preinstalled) |
| Alibaba Cloud OSS | `cinience/alicloud-skills@alicloud-storage-oss-ossutil` | installed via `npx skills add ... -g -y`; useful as external OSS prior art, but current repo facts were sufficient for this slice |
