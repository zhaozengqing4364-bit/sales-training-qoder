---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T02: 实现 websocket reconnect/backpressure/interrupt 收口

Why: reconnect/backpressure/interrupt 是 practice 主链路里最容易靠经验式 patch 堆积复杂度的地方，必须统一收口。

Do:
1. 按真实 seam 调整 reconnect 策略、队列清理和 interrupt 处理。
2. 必要时拆分 hook 内部职责，但不引入重量级状态机框架。
3. 保持 practice 页面现有主链路和 focused tests 仍然可证明通过。

Done when: focused websocket + practice tests 通过，reconnect/backpressure/interrupt contract 更清晰。

## Inputs

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/**/*`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`

## Expected Output

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/**/*`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`

## Verification

npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"

## Observability Impact

reconnect 退出条件、队列清理和 interrupt 行为都变成可测试 contract。
