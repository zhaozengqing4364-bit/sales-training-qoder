---
estimated_steps: 28
estimated_files: 3
skills_used: []
---

# T03: Focused contract regression for audio-audit evidence chain

Add dedicated backend contract tests proving the audio-audit read model, playback handoff, and ownership semantics. Add frontend test assertions proving report and replay render audio audit sections correctly.

## Steps

1. Add backend contract tests in `backend/tests/contract/test_practice_evidence_contract.py` (extend existing file):
   - Test that report payload for a session with uploaded audio segments includes audio_audit with correct summary (status=available, segment count, total bytes)
   - Test that report payload for a session with no segments includes audio_audit with status=missing
   - Test that report payload for a session with partial uploads shows status=partial
   - Test that replay payload after completion includes the same audio_audit structure
   - Test that segment playback route returns signed redirect (307) for uploaded segment with correct ownership
   - Test that segment playback route returns 404 for non-existent segment sequence
   - Test that outsider user gets 403 on playback route
   - Test that signed GET URLs are never persisted in DB state

2. Add frontend test assertions in report page test:
   - Add audio_audit to baseReport mock with available status and 2 segments
   - Assert "原始录音" heading is visible
   - Assert segment count is displayed
   - Assert play buttons are rendered
   - Add test for missing audio state: no audio_audit → renders "本次训练未录制原始音频"
   - Assert existing report assertions still pass

3. Add frontend test assertions in replay page test:
   - Add audio_audit to baseReplayData mock
   - Assert audio audit section renders without breaking highlights/full-dialogue
   - Assert existing blocked replay behavior still renders the current explicit message

## Must-Haves

- [ ] Backend contract tests for report/replay audio_audit inclusion with available/partial/missing states
- [ ] Backend contract tests for playback handoff (signed redirect, 404, 403)
- [ ] Frontend report test asserts audio audit section renders
- [ ] Frontend replay test asserts audio audit section renders without regressions
- [ ] All existing tests continue to pass

## Inputs

- `backend/tests/contract/test_practice_evidence_contract.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Expected Output

- `backend/tests/contract/test_practice_evidence_contract.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k audio_audit
