---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: Carry unresolved objection evidence onto current learner and read-side surfaces

Expose the unresolved objection family on the existing learner/read-side surfaces so the user can still see what kept blocking the conversation. Reuse the current practice reducer/right panel and session-evidence/report paths; do not add a separate objection UI.

## Inputs

- `backend/src/common/conversation/session_evidence.py`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/components/practice/RightPanelContent.tsx`

## Expected Output

- `backend/src/common/conversation/session_evidence.py`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/components/practice/RightPanelContent.test.tsx`

## Verification

cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'
