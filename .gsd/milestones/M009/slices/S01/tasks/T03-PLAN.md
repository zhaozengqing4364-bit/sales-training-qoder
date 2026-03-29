---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: Integrate uploader into practice session page and add contract tests

Wire useContinuousAudioUploader into the practice session page alongside the existing useAudioRecorder. When recording starts, also start the continuous uploader. When recording stops, finalize the last segment. Add backend+frontend contract tests proving the full cycle: backend signs URL -> mock upload -> metadata registered -> segments queryable.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/hooks/use-continuous-audio-uploader.ts`
- `backend/src/common/api/practice.py`
- `backend/src/common/oss/signing.py`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `backend/tests/contract/test_audio_audit_contract.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_audio_audit_contract.py -v && cd ../web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts

## Observability Impact

Integration adds runtime_metrics.audio_audit to voice_policy_snapshot on segment registration. Contract test proves the full signing -> upload -> metadata -> query cycle.
