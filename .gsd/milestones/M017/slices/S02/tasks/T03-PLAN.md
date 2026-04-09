---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: 为 websocket orchestration contract 补 proof

补 focused tests，锁定 reconnect 退出条件、backpressure 清理和 interrupt contract，不让复杂度回流。

## Inputs

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`

## Expected Output

- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"

## Observability Impact

realtime proof strengthened
