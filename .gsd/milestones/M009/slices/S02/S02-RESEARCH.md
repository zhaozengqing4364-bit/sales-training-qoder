# M009 / S02 — Research

**Date:** 2026-03-28

## Summary

S02 is the learner-facing read-side half of the audio-audit chain. S01 already delivered the hard storage foundation: browser-side segmented recording, OSS presigned PUTs, durable `session_audio_segments` rows, and bounded `voice_policy_snapshot.runtime_metrics.audio_audit` counters. What is still missing is the read model that turns those stored segments into something report/replay can truthfully expose to learners.

This slice primarily advances **R026** (learner can inspect raw audio evidence from existing report/replay routes), while supporting **R024/R025** by proving the uploaded assets are actually queryable and playable after upload. It also lays the foundation for **R027** by making report conclusions auditable against raw audio, even if full turn-to-conclusion provenance waits for M010.

The most important fact from code inspection: **`PracticeSession.audio_url` is not a playable asset today**. S01 sets it to `audio/{session_id}/`, i.e. an OSS storage prefix, not a signed URL or manifest object. Current report/replay UIs still treat `audio_url` as the old message-level seam, so S02 must not try to “light up raw audio” by reusing `session.audio_url` directly.

A second critical fact: there is already a **message-level playback handoff pattern** in `backend/src/common/conversation/api.py` (`/sessions/{session_id}/audio/{message_id}` → redirect/file response), and there is already an OSS **GET signer** in `backend/src/common/oss/signing.py`. The missing seam is a **session-level audio-audit payload + playback handoff** for `SessionAudioSegment`, not new storage work.

Skill-informed guidance:
- Per **safe-grow**, keep this to one minimal authority extension: don’t invent a second audit console or page-local truth source.
- Per **fastapi-python**, prefer typed Pydantic response models over ad-hoc dict payloads for the new session-audio contract.
- Per **react-best-practices** (`async-parallel`), if frontend still needs a second request, keep it parallel and independent — but the better option is still to centralize the audio-audit contract in backend once.

## Recommendation

**Recommended approach:** add a shared backend **session audio audit read model** and expose it on both canonical learner payloads:
- `GET /api/v1/practice/sessions/{id}/report`
- `GET /api/v1/sessions/{id}/replay`

The shared payload should include:
1. **summary** — recording status, total segment count, uploaded segment count, total bytes, latest segment info, storage prefix, last uploaded time, and a derived learner-facing status such as `available | partial | missing`.
2. **segments** — ordered segment entries with `segment_sequence`, `created_at`, `duration_ms`, `size_bytes`, `upload_status`, and a **stable playback handoff path** per segment.

For playback, prefer a **backend handoff route** over embedding expiring signed OSS GET URLs directly in persisted state. The clean pattern is to mirror the existing message-audio route with something like a session-audio-segment playback endpoint that validates ownership and then issues a short-lived signed GET redirect using `OssSigningService.generate_get_url(...)`.

Why this is the best fit:
- It keeps report and replay on the same truth source instead of having each page manually call `/audio-segments` and assemble its own interpretation.
- It avoids persisting expiring signed URLs.
- It reuses an existing security pattern already present for message audio.
- It leaves S03 room to layer degraded wording and anomaly classification onto the same payload instead of rewriting page logic later.

**Second-best fallback:** if contract churn must stay smaller, add `api.sessions.listAudioSegments(sessionId)` plus a segment playback route and let both pages fetch segments in parallel. This is workable, but weaker: it duplicates load/orchestration across pages and makes drift more likely.

## Implementation Landscape

### Backend authority and storage seams

- `backend/src/common/db/models.py`
  - `SessionAudioSegment` is already the durable source of truth for raw audio segments.
  - Fields already sufficient for S02: `segment_sequence`, `object_key`, `content_type`, `size_bytes`, `duration_ms`, `upload_status`, `error_message`, `created_at`.

- `backend/src/common/oss/signing.py`
  - Already supports `generate_get_url(object_key, expires=3600)`.
  - No new OSS client architecture is needed for S02.

- `backend/src/common/api/practice.py`
  - Already owns learner report route and the S01 segment APIs:
    - `POST /practice/sessions/{id}/audio-upload-urls`
    - `POST /practice/sessions/{id}/audio-segments`
    - `GET /practice/sessions/{id}/audio-segments`
  - Current `list_audio_segments(...)` only returns raw metadata and `object_key`; it does **not** return a playback URL/handoff.
  - Current report payload sets `audio_url=session.audio_url`, which is now only a storage prefix seam.

- `backend/src/common/conversation/replay.py`
  - Current replay payload is assembled here and is the right place to include the same session-level audio-audit payload used by report.
  - Also note: replay/highlights currently enrich message-level `audio_url` only; they know nothing about the new session segment catalog.

- `backend/src/common/conversation/api.py`
  - Existing message playback redirect route is the best design precedent for session-segment playback.
  - S02 should mirror this pattern instead of exposing raw OSS bucket URLs.

- `backend/src/common/conversation/schemas.py`
  - `ReplayDataResponse` currently has no session-audio-audit field.
  - This is the natural typed seam for replay contract extension.

- `backend/src/common/db/schemas.py`
  - `SessionReport` currently has only legacy `audio_url?: str | None`.
  - This is the natural typed seam for report contract extension.

### Frontend typed/API seams

- `web/src/lib/api/types.ts`
  - `PracticeSessionReport` and `ReplayData` both still expose only legacy `audio_url` fields; there is no `audio_audit` or `audio_segments` contract yet.

- `web/src/lib/api/client.ts`
  - Has `getReport`, `getReplay`, `getHighlights`, `getAudioBlobUrl`.
  - Does **not** expose `audio-segments` list or segment playback helpers yet.
  - If planner chooses parallel page fetches, add client methods here — not raw `fetch()` inside pages.

### Learner UI seams

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - Good insertion point for a new raw-audio card: near the existing highlights/comprehensive-insights area.
  - Current page already loads report as canonical truth, plus optional replay anchor/highlights. Audio audit should not depend on highlights being available.

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
  - Good insertion point: between highlights and full dialogue, or adjacent to the “完整对话” section.
  - Current replay page shows only a passive `有音频` badge for message-level `message.audio_url`.

- `web/src/components/highlights/HighlightDetailModal.tsx`
  - Already uses the minimal `new Audio(audioUrl)` pattern and is a good reference for segment playback behavior.
  - No need for waveform/editor work in S02.

- `web/src/components/highlights/HighlightList.tsx`
  - Not directly reusable for raw audio segments, but its `GlassCard`/section structure is a good UI baseline for a new shared audio-audit component.

### Tests already in the blast radius

- Backend:
  - `backend/tests/integration/test_replay_api.py`
  - `backend/tests/contract/test_practice_evidence_contract.py`
  - `backend/tests/unit/test_replay_service.py`
  - `backend/tests/unit/test_oss_signing_service.py`
- Frontend:
  - `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Build Order

1. **Backend contract first**
   - Add typed session-audio-audit models.
   - Build one shared read helper from `SessionAudioSegment` + `voice_policy_snapshot.runtime_metrics.audio_audit`.
   - Extend both report and replay payloads to include that shared payload.

2. **Playback handoff second**
   - Add a session-segment playback route that validates ownership and returns a short-lived signed GET redirect.
   - Use this route in the session-audio-audit payload as stable playback affordance.

3. **Frontend types/client third**
   - Extend `web/src/lib/api/types.ts` for the new payload.
   - If needed, add a client helper for segment blob playback; avoid raw page-local fetches.

4. **Shared learner UI fourth**
   - Add a small reusable raw-audio audit card/component.
   - Report and replay should both consume the same shape with minimal local logic.

5. **Focused regressions last**
   - Backend contract + replay tests first.
   - Then report/replay page tests.

## Verification Approach

### Backend

Run sequentially; do not parallelize backend pytest jobs because this repo can trip on coverage-file combine races.

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py -v`
- If adding dedicated session-audio tests, keep them in the same run or as a separate sequential command.

What to prove:
- report payload includes session-level audio-audit summary/segments for session owner
- replay payload includes the same ordered segment view after completion
- outsider still gets `403`
- playback handoff never exposes permanent OSS URL in DB state
- playback route signs/redirects successfully for uploaded segments and returns a stable 404/diagnostic for missing ones

### Frontend

Use `pnpm --dir web exec vitest run ...` to avoid the broken global npm wrapper on this machine.

- `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`

What to prove:
- report renders a raw-audio audit section with status, count, and playable segments
- replay renders the same raw-audio evidence without breaking existing highlights/full-dialogue flows
- empty/no-audio state is clear and non-fatal
- existing blocked replay behavior (`[SESSION_NOT_COMPLETED]`) still renders the current explicit message

## Constraints

- Keep learner visibility on the existing report/replay route family; do not create a separate audit console.
- `PracticeSession.audio_url` is currently a storage-prefix seam, not a usable playback URL.
- `GET /practice/sessions/{id}/audio-segments` currently returns metadata only; it is not sufficient for playback by itself.
- Signed GETs must remain derived at read time; do not persist them.
- Replay remains completion-gated; report does not. The shared builder should tolerate both contexts.
- Quote Next.js literal paths in verification/search commands (`'(user)'`, `'[sessionId]'`) to avoid shell false failures.

## Common Pitfalls

- Treating `session.audio_url` as if it were a playable session recording.
- Extending only report or only replay, leaving the learner route family inconsistent.
- Letting both pages fetch `/audio-segments` and interpret statuses independently.
- Exposing raw `object_key` as if it were directly browser-playable.
- Reusing message-level `message.audio_url` badges/highlight audio as proof that raw session segments are available; they are different asset lines.
- Persisting or snapshotting signed GET URLs instead of deriving them per read/handoff.

## Open Risks

- If every list/read signs a fresh GET URL per segment, URLs may expire while the page stays open. A handoff route is safer than embedding signed URLs directly in the payload.
- Sessions with many short recordings may produce long segment lists; UI should consider collapse/summary-first presentation instead of rendering an unbounded wall immediately.
- `duration_ms` may be absent on some segment rows; UI must handle missing duration gracefully.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js | `react-best-practices` | installed (preinstalled) |
| FastAPI / Pydantic | `fastapi-python` | installed (preinstalled) |
| Repository safe single-item iteration | `safe-grow` | installed (repo-local) |
| Alibaba Cloud OSS | `cinience/alicloud-skills@alicloud-storage-oss-ossutil` | installed globally during this research; not yet surfaced in current prompt skill list |
