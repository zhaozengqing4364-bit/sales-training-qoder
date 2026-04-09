---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: 梳理 practice preflight 与 interruption 当前表面

阅读 practice page、lifecycle hook、websocket hook，梳理训练前可用的 persona/scenario 信息以及暂停/恢复/结束失败目前如何呈现。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`

## Verification

rg -n "pause|resume|end|test-mic|persona|scenario|goal" web/src/app/\(user\)/practice/\[sessionId\]/page.tsx web/src/hooks/use-practice-websocket.ts

## Observability Impact

current preflight/interruption UX inventory
