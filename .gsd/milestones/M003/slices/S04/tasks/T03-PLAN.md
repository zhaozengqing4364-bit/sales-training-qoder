---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T03: Show claim-truth states on current report and replay routes

Render the truth states on the existing learner-facing read surfaces so users can tell whether a statement lacked evidence, had weak evidence, or was verified. Update current report/replay UI and focused tests without adding a separate knowledge-debug page.

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/lib/session-evidence.ts`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
