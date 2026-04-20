---
estimated_steps: 6
estimated_files: 5
skills_used:
  - react-best-practices
---

# T02: Frontend: consume degraded truth in AudioAuditCard and normalize playback errors

**Slice:** S03 — 音频审计降级与诊断
**Milestone:** M009

## Description

Update AudioAuditCard to consume canonical degraded fields (degraded_reasons, failed_segments, per-segment error_message) from the enriched backend payload. Render differentiated learner-facing wording for partial/failed states. Fix getSegmentAudioBlobUrl to preserve structured error codes instead of collapsing to generic HTTP status.

## Steps

1. Extend `AudioAuditSummary` type in `web/src/lib/api/types.ts` with `failed_segments: number` and `degraded_reasons: string[]`. Extend `AudioAuditSegment` type with `error_message?: string | null`.

2. Update `AudioAuditCardWithSession`: when `learner_status` is `'partial'`, render `degraded_reasons` as human-readable bullet points below the badge. Map reason tokens to Chinese: `upload_failed` → `'部分音频片段上传失败'`, `segments_pending` → `'部分片段尚未上传完成'`. For segments with `upload_status='failed'`, show the segment's `error_message` if available.

3. Fix `getSegmentAudioBlobUrl` in `web/src/lib/api/client.ts`: when response is not OK, parse JSON body to extract `error` or `error_code` field, then throw `Error` with the structured code (e.g. `'SEGMENT_NOT_UPLOADED'`, `'SEGMENT_NOT_FOUND'`, `'SIGNING_FAILED'`). Fall back to generic `'HTTP {status}'` only if JSON parse fails.

4. Update `SegmentPlayer` to differentiate playback error messages based on the structured error code from getSegmentAudioBlobUrl: `SEGMENT_NOT_UPLOADED` → `'该片段未成功上传'`, `SEGMENT_NOT_FOUND` → `'片段记录不存在'`, `SIGNING_FAILED` → `'获取播放地址失败'`, default → `'加载失败'`.

5. Add/update focused tests in `report/page.test.tsx`: mock report API response with `audio_audit` having `learner_status='partial'`, `degraded_reasons=['upload_failed']`, and at least one failed segment. Assert that the page renders the degraded wording (e.g. text containing `'部分音频片段上传失败'`).

6. Add/update focused tests in `replay/page.test.tsx`: same pattern, proving the shared AudioAuditCard renders identical degraded wording in replay context.

## Must-Haves

- [ ] AudioAuditCard renders degraded_reasons as specific Chinese wording for partial/failed states
- [ ] Per-segment error_message displayed for failed segments instead of generic badge
- [ ] getSegmentAudioBlobUrl preserves structured backend error codes in thrown Error
- [ ] SegmentPlayer differentiates playback errors based on error codes
- [ ] Report and replay page tests lock degraded wording assertions

## Verification

- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`
- All tests pass including new degraded-wording assertions

## Inputs

- `web/src/components/audio/AudioAuditCard.tsx` — shared learner component to extend
- `web/src/lib/api/client.ts` — getSegmentAudioBlobUrl to fix error propagation
- `web/src/lib/api/types.ts` — AudioAuditSummary/AudioAuditSegment types to extend
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — report page tests to extend
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — replay page tests to extend

## Expected Output

- `web/src/components/audio/AudioAuditCard.tsx` — enriched degraded wording rendering
- `web/src/lib/api/client.ts` — fixed getSegmentAudioBlobUrl with structured error codes
- `web/src/lib/api/types.ts` — extended TypeScript types matching new backend schema
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — new degraded-wording assertions
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — new degraded-wording assertions
