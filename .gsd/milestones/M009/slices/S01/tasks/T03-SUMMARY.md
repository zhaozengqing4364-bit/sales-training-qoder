---
id: T03
parent: S01
milestone: M009
provides: []
requires: []
affects: []
key_files: ["web/src/app/(user)/practice/[sessionId]/page.tsx", "backend/src/common/api/practice.py", "backend/tests/contract/test_audio_audit_contract.py", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Reused the existing recording toggle as the single orchestration point so realtime recording and continuous OSS uploads stay in lockstep.", "Persisted audio-audit observability by merging `voice_policy_snapshot.runtime_metrics.audio_audit` into the existing snapshot instead of overwriting the full snapshot.", "Contract tests patch `common.oss.signing` directly and must provide `ALI_OSS_BUCKET` to reach the mocked OSS layer."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Focused verification passed for both required checks. `backend/tests/contract/test_audio_audit_contract.py` passed 6/6 and proved sign → register → list plus persisted `voice_policy_snapshot.runtime_metrics.audio_audit`. `web/src/hooks/use-continuous-audio-uploader.test.ts` passed 13/13 after the page integration, covering uploader lifecycle and error handling. No local browser UAT server was running during this unit, so browser verification was not added beyond the page integration readback."
completed_at: 2026-03-29T21:19:41.999Z
blocker_discovered: false
---

# T03: Practice sessions now mirror live recording into OSS audio-audit uploads and persist segment runtime metrics with backend contract coverage.

> Practice sessions now mirror live recording into OSS audio-audit uploads and persist segment runtime metrics with backend contract coverage.

## What Happened
---
id: T03
parent: S01
milestone: M009
key_files:
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - backend/src/common/api/practice.py
  - backend/tests/contract/test_audio_audit_contract.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Reused the existing recording toggle as the single orchestration point so realtime recording and continuous OSS uploads stay in lockstep.
  - Persisted audio-audit observability by merging `voice_policy_snapshot.runtime_metrics.audio_audit` into the existing snapshot instead of overwriting the full snapshot.
  - Contract tests patch `common.oss.signing` directly and must provide `ALI_OSS_BUCKET` to reach the mocked OSS layer.
duration: ""
verification_result: passed
completed_at: 2026-03-29T21:19:42.001Z
blocker_discovered: false
---

# T03: Practice sessions now mirror live recording into OSS audio-audit uploads and persist segment runtime metrics with backend contract coverage.

**Practice sessions now mirror live recording into OSS audio-audit uploads and persist segment runtime metrics with backend contract coverage.**

## What Happened

Integrated `useContinuousAudioUploader` into the practice-session page so the uploader starts with the existing microphone recorder, stops with it, restarts after successful permission recovery, and is shut down if the session becomes terminal while uploads are active. On the backend, updated audio-segment registration to merge `voice_policy_snapshot.runtime_metrics.audio_audit` into the persisted session snapshot after each successful segment registration, preserving existing runtime metrics while tracking segment count, total bytes, latest sequence, object key, and storage prefix. Added a focused backend contract suite that proves signing, metadata registration, ordered listing, outsider denial, idempotent re-registration, first-segment `audio_url` initialization, and persisted audio-audit metrics. Also corrected the OSS test fixture to use `ALI_OSS_BUCKET`, which is the actual env key expected by the signing service.

## Verification

Focused verification passed for both required checks. `backend/tests/contract/test_audio_audit_contract.py` passed 6/6 and proved sign → register → list plus persisted `voice_policy_snapshot.runtime_metrics.audio_audit`. `web/src/hooks/use-continuous-audio-uploader.test.ts` passed 13/13 after the page integration, covering uploader lifecycle and error handling. No local browser UAT server was running during this unit, so browser verification was not added beyond the page integration readback.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd /Users/zhaozengqing/github/销售训练qoder/backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/contract/test_audio_audit_contract.py -v` | 0 | ✅ pass | 6540ms |
| 2 | `cd /Users/zhaozengqing/github/销售训练qoder/web && /usr/bin/time -p npx vitest run src/hooks/use-continuous-audio-uploader.test.ts` | 0 | ✅ pass | 1680ms |


## Deviations

Skipped browser UAT because no local verification server was listening on the repository ports during this unit; retired the runtime proof with focused backend contract coverage instead.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `backend/src/common/api/practice.py`
- `backend/tests/contract/test_audio_audit_contract.py`
- `.gsd/KNOWLEDGE.md`


## Deviations
Skipped browser UAT because no local verification server was listening on the repository ports during this unit; retired the runtime proof with focused backend contract coverage instead.

## Known Issues
None.
