---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 识别 websocket hook 的真实职责边界

盘点 use-practice-websocket 当前已承载的 reconnect/backpressure/interrupt/binary frame negotiation 事实，找出真实 seam，而不是仅因文件大而拆分。

## Inputs

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`

## Expected Output

- `websocket seam inventory`

## Verification

rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts

## Observability Impact

current websocket contract inventory
