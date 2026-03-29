---
estimated_steps: 36
estimated_files: 7
skills_used: []
---

# T02: Frontend types + shared AudioAuditCard + report/replay integration

Extend frontend TypeScript types for the new audio_audit payload, create a shared AudioAuditCard component, and integrate it into both report and replay pages.

## Steps

1. Extend `SessionEvidenceContract` in `web/src/lib/api/types.ts` to add `audio_audit?: AudioAuditPayload | null` where AudioAuditPayload mirrors the backend schema:
   - AudioAuditSegment: segment_sequence, created_at, duration_ms, size_bytes, upload_status, playback_path
   - AudioAuditSummary: recording_status, total_segments, uploaded_segments, total_bytes, latest_segment_sequence, storage_prefix, last_uploaded_at, status (available|partial|missing)
   - AudioAuditPayload: summary + AudioAuditSegment[]

2. Add `getSegmentAudioBlobUrl` method to `web/src/lib/api/client.ts` in the sessions namespace:
   - Takes sessionId + segmentSequence
   - Fetches `/sessions/{sessionId}/audio-segments/{segmentSequence}` with credentials
   - Returns blob URL (same pattern as existing getAudioBlobUrl for messages)

3. Create `web/src/components/audio/AudioAuditCard.tsx` — a shared component that:
   - Accepts `audioAudit: AudioAuditPayload | null | undefined`
   - When null/undefined or status=missing: renders "本次训练未录制原始音频" with a brief explanation
   - When status=available/partial: renders a card with:
     - Summary line: "原始录音" + segment count + total duration (formatted mm:ss from ms)
     - Status badge: "完整" for available, "部分" for partial
     - Ordered list of segments, each with play button using the playback handoff route
     - Audio playback uses HTML5 Audio element with blob URL from getSegmentAudioBlobUrl
   - Handles missing duration_ms gracefully (shows "未知时长")
   - Follows existing GlassCard/section styling from HighlightList

4. Integrate AudioAuditCard into `web/src/app/(user)/practice/[sessionId]/report/page.tsx`:
   - Add AudioAuditCard after the existing highlights/comprehensive-insights area
   - Pass report.audio_audit

5. Integrate AudioAuditCard into `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`:
   - Add AudioAuditCard between highlights and full-dialogue sections
   - Pass replayData.audio_audit

6. Update report page test to add audio_audit to baseReport mock and assert the audio audit section renders.

7. Update replay page test to add audio_audit to baseReplayData mock and assert the audio audit section renders.

## Must-Haves

- [ ] TypeScript types for AudioAuditPayload mirroring backend contract
- [ ] getSegmentAudioBlobUrl client method
- [ ] Shared AudioAuditCard component with available/partial/missing states
- [ ] Report page renders AudioAuditCard from report.audio_audit
- [ ] Replay page renders AudioAuditCard from replayData.audio_audit
- [ ] Empty/no-audio state is non-fatal and clear
- [ ] Existing report/replay functionality unaffected

## Inputs

- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Expected Output

- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `web/src/components/audio/AudioAuditCard.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
