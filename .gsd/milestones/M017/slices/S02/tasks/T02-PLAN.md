---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 实现 websocket reconnect/backpressure/interrupt 收口

按真实 seam 收口 reconnect 策略、backpressure/队列清理和 interrupt 处理；必要时拆分 hook 内部职责，但不引入重量级状态机框架。

## Inputs

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`

## Expected Output

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/**/*`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`

## Verification

npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"

## Observability Impact

reconnect / queue cleanup 行为更清晰
