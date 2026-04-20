---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T03: 为 websocket orchestration contract 补 proof

Why: websocket orchestration contract 如果没有 focused proof，很容易在下一次 runtime 调整时再次膨胀或回归。

Do:
1. 补 focused tests，锁定 reconnect 退出条件、backpressure 清理和 interrupt contract。
2. 保持断言关注 learner 可见行为和 hook outward contract，不写死内部实现。
3. 让 future agents 能通过一组 focused tests 重建当前 websocket 设计边界。

Done when: websocket orchestration contract 有稳定 focused proof，可防止复杂度回流。

## Inputs

- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`

## Expected Output

- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"

## Observability Impact

websocket contract 的回归可由 focused tests 直接暴露。
