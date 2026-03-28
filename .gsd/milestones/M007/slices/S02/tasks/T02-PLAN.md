---
estimated_steps: 3
estimated_files: 8
skills_used:
  - react-best-practices
  - verification-before-completion
---

# T02: Carry the live conclusion summary through the learner websocket contract and render a stable same-session cue

Once backend authority is stable, surface it on the learner route without creating a second interpretation layer. Steps: 1. Extend the typed websocket/reducer contract so the live same-session summary survives `score_update` handling and final-transcript cleanup without piggybacking on transient action-card text. 2. Reuse a shared learner/report vocabulary helper where needed so the practice page renders issue/goal/claim-truth copy from backend authority rather than inferring it from score or stage labels. 3. Prove the learner route keeps current score, stage, and coach-health guidance visible while the stable same-session cue updates turn-by-turn and clears safely when live authority disappears. Must-haves: the stable cue comes from backend payload fields, not a frontend-only mapping; final transcript still clears transient `actionCard` / `fuzzyDetections` while leaving the stable same-session cue intact; no extra fetch or local storage path is introduced. Failure modes: reducer drops the new summary field, learner UI persists a stale prior-turn cue, or page-level code re-derives family labels from score/stage text and drifts from report/replay. Load profile: every `score_update` remains a cheap state update with no additional network request or expensive recomputation. Negative tests: `score_update` without live summary fields, replacement of an older cue by a newer turn, and final-transcript cleanup preserving the stable cue while clearing transient coaching affordances.

## Inputs

- ``web/src/hooks/websocket/types.ts``
- ``web/src/hooks/websocket/message-handlers.ts``
- ``web/src/lib/session-evidence.ts``
- ``web/src/components/practice/RightPanelContent.tsx``
- ``web/src/app/(user)/practice/[sessionId]/page.tsx``

## Expected Output

- ``web/src/hooks/websocket/types.ts``
- ``web/src/hooks/websocket/message-handlers.ts``
- ``web/src/lib/session-evidence.ts``
- ``web/src/components/practice/RightPanelContent.tsx``
- ``web/src/app/(user)/practice/[sessionId]/page.test.tsx``

## Verification

npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'

## Observability Impact

Makes the learner-visible same-session conclusion traceable back to a concrete websocket payload field, so browser/UI regressions can be diagnosed from reducer state instead of guessing from rendered copy.
