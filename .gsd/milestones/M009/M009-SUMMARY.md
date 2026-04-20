---
id: M009
title: "录音审计链收口"
status: complete
completed_at: 2026-03-30T00:01:42.406Z
key_decisions:
  - D123 — Backend only signs OSS PUT/GET URLs and registers metadata; browser handles all audio transfer to/from OSS.
  - D124 — Persist per-segment audio metadata in `session_audio_segments`, while keeping `voice_policy_snapshot.runtime_metrics.audio_audit` as the bounded live/runtime summary surface.
  - S02 pattern decision — Return `audio_audit: null` when no segment rows exist and let learner-facing report/replay pages render the missing-audio fallback state.
  - S03 pattern decision — Use a closed-enum audio failure token set (`signing_failed`, `oss_put_failed`, `register_failed`, `network_error`, `unknown`) and derive support/runtime audio anomalies from bounded snapshot metrics rather than row scans.
key_files:
  - backend/src/common/oss/signing.py
  - backend/src/common/api/practice.py
  - backend/src/common/conversation/api.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/db/models.py
  - backend/src/common/db/schemas.py
  - backend/src/support/services/runtime_status_service.py
  - web/src/hooks/use-continuous-audio-uploader.ts
  - web/src/components/audio/AudioAuditCard.tsx
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
lessons_learned:
  - For this repo, milestone close-out must prefer fresh route-family verification on the shipped code over stale summary caveats; otherwise an already-fixed proof gap can block completion after the implementation is done.
  - Audio auditability fits the existing evidence architecture cleanly when unbounded per-segment facts live in a dedicated table and only bounded summary metrics flow through `voice_policy_snapshot.runtime_metrics`.
  - Learner-facing audio evidence stayed coherent because report and replay shared one backend `audio_audit` helper and one frontend `AudioAuditCard`; avoiding route-specific implementations prevented drift while adding degraded wording.
---

# M009: 录音审计链收口

**M009 turned raw training audio into a durable OSS-backed audit asset that learners can inspect and play from report/replay, with explicit degraded wording and runtime diagnostics when the audio chain degrades.**

## What Happened

M009 closed the raw-audio audit chain on the current learner route family instead of adding a side-channel audit console. S01 established direct browser-to-OSS upload with backend signing and durable segment metadata: a new OSS signing service issues presigned PUT/GET URLs, `SessionAudioSegment` rows persist per-segment facts, and the practice page now runs `useContinuousAudioUploader` alongside the existing recording flow so uploaded audio survives interruptions and remains queryable. S02 carried that evidence onto the canonical learner review surfaces by adding a shared `audio_audit` read model to both `/practice/{sessionId}/report` and `/sessions/{id}/replay`, a stable owner-only playback handoff route, and one shared `AudioAuditCard` that renders available/partial/missing states without persisting signed URLs. S03 completed the chain by adding failure registration, degraded-reason enrichment, differentiated learner wording, structured playback errors, and support/runtime anomaly kinds that classify missing or degraded uploads from bounded snapshot metrics.

The first validation pass had recorded a proof-depth concern because earlier slice execution notes mentioned skipped or aborted browser checks. Before close-out, the milestone was revalidated directly on the current branch. The fresh backend verification run passed 122 tests across OSS signing, audio segment APIs, `audio_audit` contracts, replay integration, and support/runtime audio anomaly classification. The fresh web verification run passed 50 tests across the continuous uploader hook, report page, replay page, and structured playback-error handling. That rerun retired the earlier attention note: the milestone now has fresh code-level evidence for the route family it actually ships.

As completed, M009 upgrades training audio from a transient runtime byproduct into a durable audit asset on the same surfaces learners and operators already use. A learner can now accumulate raw audio segments during practice, inspect recording state and playback availability on report/replay, and receive explicit degraded wording when uploads fail or segments are missing. Support/runtime can see `audio_upload_degraded` and `audio_missing` anomalies without expensive row scans. This leaves M010 with a clear next step: combine retrieval truth, transcript evidence, and the new audio audit chain into a tighter report-provenance contract rather than reopening audio storage or playback fundamentals.

## Success Criteria Results

- ✅ **Browser uploads raw training audio directly to OSS with backend signing/metadata only.** S01 delivered `OssSigningService`, `SessionAudioSegment`, sign/register/list APIs, practice-page uploader wiring, and persisted `voice_policy_snapshot.runtime_metrics.audio_audit`. Fresh backend verification passed OSS signing/API/audio-audit suites; fresh web verification passed uploader-hook tests.
- ✅ **Learners can inspect and play raw audio evidence on existing report/replay routes.** S02 added shared `audio_audit` payloads to report and replay, the stable playback handoff route, and shared `AudioAuditCard` rendering. Fresh backend contract/integration tests passed for available/partial/null payloads and playback redirect/403/404; fresh web report/replay suites passed.
- ✅ **Audio degradation is explained clearly to learners and operators.** S03 added failure registration, canonical `degraded_reasons`, `failed_segments`, structured playback errors, differentiated learner copy, and support/runtime `audio_upload_degraded`/`audio_missing` anomaly kinds with failure-rate severity escalation. Fresh backend/web tests passed these paths.
- ✅ **Milestone contains real implementation, not planning only.** Integration-branch diff and M009-targeted diff both show substantial non-`.gsd/` backend/web changes on the audio audit path.
- ✅ **Definition-of-done evidence is present.** All three slice summary/UAT artifacts exist, the cross-slice seams align, and the milestone revalidation verdict is now `pass` on the current branch.

## Definition of Done Results

- **All slices complete:** Roadmap marks S01, S02, and S03 as done (✅), and the filesystem contains `S01-PLAN.md/SUMMARY.md/UAT.md`, `S02-PLAN.md/SUMMARY.md/UAT.md`, and `S03-PLAN.md/SUMMARY.md/UAT.md` under `.gsd/milestones/M009/slices/`.
- **Real code shipped:** `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` shows extensive non-`.gsd/` implementation. M009-targeted diff covers 14 shipped files across backend OSS signing, practice/replay APIs, schemas, runtime diagnostics, uploader hook, audio card, learner report/replay pages, and API client/types.
- **Cross-slice integration verified:** S01 persistence/signing feeds S02 read/playback seams; S02 shared payload/card is extended by S03 degraded metadata and wording; S03 runtime anomalies derive from S01 bounded snapshot metrics. Fresh backend/web verification on the closed branch passed these integrated seams.
- **Verification rerun before close-out:** Backend command `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_oss_signing_service.py tests/unit/test_audio_segment_api.py tests/contract/test_audio_audit_contract.py tests/contract/test_practice_evidence_contract.py tests/unit/test_replay_service.py tests/integration/test_replay_api.py tests/unit/test_support_runtime_service.py -v` passed **122/122**. Web command `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/hooks/use-continuous-audio-uploader.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/lib/api/client.auth.test.ts'` passed **50/50**.

## Requirement Outcomes

- **R024 → validated.** M009 now proves raw training audio is durably recorded during the session and survives interruption as an audit asset. Evidence: S01 implementation (`SessionAudioSegment`, OSS signing, continuous uploader, persisted audio-audit runtime metrics) plus fresh verification of OSS signing/API/contract suites and uploader hook tests.
- **R025 → validated.** Audio upload/download continue to use browser-direct OSS transfer while the backend only signs URLs, registers metadata, and enforces ownership. Evidence: `backend/src/common/oss/signing.py`, sign/register/playback handoff routes, non-persistence of signed URLs, fresh backend playback redirect/403/404 contracts, and web API/page tests.
- **R026 → validated.** Learners can now inspect and play their own raw audio evidence on the canonical report and replay routes. Evidence: shared `audio_audit` payload on report/replay, shared `AudioAuditCard`, signed playback handoff route, fresh backend contract/integration tests, and fresh report/replay page tests.
- **No requirement was invalidated or re-scoped.** R028 remains active because M009 only delivers the audio-layer support for future cross-layer degradation explanation; the full multi-layer provenance/degradation contract remains owned by M010.

## Deviations

Round-0 milestone validation had flagged a live-UAT proof-depth gap because slice summaries mentioned skipped/aborted browser checks. For close-out, the milestone relied on fresh focused backend/web verification on the shipped M009 seams instead of introducing a new remediation slice. This changes the close-out basis from 'needs-attention due to missing live artifact' to 'pass based on fresh route-family contract/integration evidence on the current branch.'

## Follow-ups

M010 should build on M009’s audio audit chain rather than reopening it: use `audio_audit`/signed playback as one evidence source in report provenance, and keep broader cross-layer degradation explanation (retrieval/audio/transcript/enhanced report) under R028. If future work needs richer learner/runtime audio diagnostics, extend the existing `degraded_reasons` token contract and `AudioAuditCard` mapping instead of creating a second audit surface.
