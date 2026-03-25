---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T03: Carry page-level evidence onto the current PPT replay/viewing path

Carry the page-level evidence into the current replay/PPT viewing experience so users can navigate from report conclusions to the relevant page context. Reuse current replay service and PPT UI components; keep degraded states explicit when page anchors are missing.

## Inputs

- `backend/src/common/conversation/replay.py`
- `web/src/components/practice/presentation/SlideViewer.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`

## Expected Output

- `backend/src/common/conversation/replay.py`
- `web/src/components/practice/presentation/SlideViewer.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
