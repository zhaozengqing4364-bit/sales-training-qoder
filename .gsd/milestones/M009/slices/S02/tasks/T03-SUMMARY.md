---
id: T03
parent: S02
milestone: M009
provides: []
requires: []
affects: []
key_files: ["backend/tests/contract/test_practice_evidence_contract.py", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M009/slices/S02/tasks/T03-SUMMARY.md"]
key_decisions: ["Keep the shipped backend authority seam where sessions with no SessionAudioSegment rows return `audio_audit: null`, and prove the learner-facing missing-audio state in the frontend contract instead of synthesizing a backend `missing` payload.", "Patch `common.oss.signing.get_oss_signing_service` in contract tests so playback handoff assertions verify owner-only signed redirects without persisting signed OSS URLs into DB or report/replay payloads."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Focused backend and frontend verification passed. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k audio_audit` proved the report/replay audio-audit payload cases. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k 'audio_audit or audio_segment_playback or signed_audio_segment_urls'` proved the full evidence chain including signed redirect ownership and non-persistence. `cd web && pnpm exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` passed with the new report missing-audio assertion and the existing shared audio-audit UI assertions."
completed_at: 2026-03-29T22:40:21.128Z
blocker_discovered: false
---

# T03: Added focused audio-audit regressions for report/replay payloads, playback ownership, and missing-audio learner UI.

> Added focused audio-audit regressions for report/replay payloads, playback ownership, and missing-audio learner UI.

## What Happened
---
id: T03
parent: S02
milestone: M009
key_files:
  - backend/tests/contract/test_practice_evidence_contract.py
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M009/slices/S02/tasks/T03-SUMMARY.md
key_decisions:
  - Keep the shipped backend authority seam where sessions with no SessionAudioSegment rows return `audio_audit: null`, and prove the learner-facing missing-audio state in the frontend contract instead of synthesizing a backend `missing` payload.
  - Patch `common.oss.signing.get_oss_signing_service` in contract tests so playback handoff assertions verify owner-only signed redirects without persisting signed OSS URLs into DB or report/replay payloads.
duration: ""
verification_result: passed
completed_at: 2026-03-29T22:40:21.129Z
blocker_discovered: false
---

# T03: Added focused audio-audit regressions for report/replay payloads, playback ownership, and missing-audio learner UI.

**Added focused audio-audit regressions for report/replay payloads, playback ownership, and missing-audio learner UI.**

## What Happened

Extended the backend contract suite with focused audio-audit regressions covering report available/partial states, replay parity, playback redirect ownership, missing-segment 404 handling, outsider 403 handling, and the guarantee that signed GET URLs never leak into persisted state or learner payloads. Updated the report page test suite with an explicit missing raw-audio fallback assertion for `audio_audit: null`, while preserving the existing shared-card assertions already proving available audio on both report and replay pages. Recorded the non-obvious no-segment backend contract seam in project knowledge so future tasks keep the current authority line intact.

## Verification

Focused backend and frontend verification passed. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k audio_audit` proved the report/replay audio-audit payload cases. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k 'audio_audit or audio_segment_playback or signed_audio_segment_urls'` proved the full evidence chain including signed redirect ownership and non-persistence. `cd web && pnpm exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` passed with the new report missing-audio assertion and the existing shared audio-audit UI assertions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k audio_audit` | 0 | ✅ pass | 14600ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k 'audio_audit or audio_segment_playback or signed_audio_segment_urls'` | 0 | ✅ pass | 52200ms |
| 3 | `cd web && pnpm exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 14600ms |


## Deviations

The task plan described a backend "missing" audio-audit status case, but the shipped read model intentionally returns `audio_audit: null` when a session has no `SessionAudioSegment` rows. I locked that real backend contract in the contract suite and added the learner-facing missing-audio UI assertion on the report page instead of synthesizing a backend `learner_status="missing"` payload.

## Known Issues

None.

## Files Created/Modified

- `backend/tests/contract/test_practice_evidence_contract.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M009/slices/S02/tasks/T03-SUMMARY.md`


## Deviations
The task plan described a backend "missing" audio-audit status case, but the shipped read model intentionally returns `audio_audit: null` when a session has no `SessionAudioSegment` rows. I locked that real backend contract in the contract suite and added the learner-facing missing-audio UI assertion on the report page instead of synthesizing a backend `learner_status="missing"` payload.

## Known Issues
None.
