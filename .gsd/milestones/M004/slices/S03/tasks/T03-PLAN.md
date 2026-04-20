---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: Show the carry-forward focus on the current practice page

Make the existing practice entry chain display the carry-forward focus so the learner knows this is a targeted retry and not a generic new session. Reuse current runtime descriptor/practice page state; do not build a separate onboarding step.

## Inputs

- `backend/src/training_runtime/service.py`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/hooks/use-practice-websocket.test.ts`

## Expected Output

- `backend/src/training_runtime/service.py`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/hooks/use-practice-websocket.test.ts`

## Verification

cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'
