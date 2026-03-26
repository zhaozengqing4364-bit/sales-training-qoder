---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: Build the regression net for the current learning-loop routes

Build the regression net for the current learning chain so report, replay, history, highlights, and retry remain on one vocabulary and one route family. Reuse focused backend/web suites instead of adding a new acceptance framework.

## Inputs

- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`

## Expected Output

- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_practice_evidence_flow.py`
- `npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'`
