---
estimated_steps: 4
estimated_files: 7
---

# T03: 让训练页只信服务端生命周期并显式暴露结束失败

**Slice:** S01 — 多轮会话稳定化与运行时状态收口
**Milestone:** M001

## Description

前端当前还会用本地乐观状态猜测 pause / resume / end，且结束失败后无论如何都跳报告页。这个任务要把训练页改成只跟随服务端 `status` / `reconnected` / `session_ended` 事件，并把结束失败留在现有错误提示面上，让用户可以重试或重连，而不是把运行时异常伪装成“报告页问题”。

## Steps

1. 收窄 `web/src/hooks/use-practice-websocket.ts` 中 lifecycle 的本地乐观写入，让暂停 / 恢复 / 结束的 UI 状态以服务端 `status`、`reconnected`、`session_ended` 为准，只保留真正需要的音频本地清理。
2. 更新 `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` 与 `page.tsx`：结束失败时停留在训练页、暴露错误消息与重试路径，只有在服务端确认终态后才跳转报告页。
3. 扩展 `use-practice-session-lifecycle.test.ts`、`use-practice-websocket.test.ts`、`message-handlers.test.ts`，覆盖结束失败不跳转、`reconnected` 恢复状态、暂停时音频门禁仍跟随后端状态。
4. 运行针对性 vitest，修正状态标签、错误展示与重连恢复回归，直到前端生命周期状态完全跟随后端事件。

## Must-Haves

- [ ] 结束失败时不会跳转到 `/practice/{sessionId}/report`，用户能在训练页看到错误并执行重试 / 重连。
- [ ] 训练页上的 `sessionStatus`、`aiState` 与音频发送门禁以服务端事件为准，不再由本地 `sendControl()` 乐观写入主导。

## Verification

- `cd web && npm test -- --run src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
- 检查测试明确断言：end 失败时 `router.push` 未发生，`reconnected` 恢复 `sessionStatus` / `aiState` 后 UI 才允许继续训练。

## Observability Impact

- Signals added/changed: 训练页结束失败错误态、重连恢复后的 UI 状态同步、服务端终态确认后的唯一跳转时机。
- How a future agent inspects this: 通过 Vitest 回归、训练页现有错误提示面与重连按钮，即可确认 UI 是否仍在本地猜状态。
- Failure state exposed: 如果结束失败、重连恢复不完整或本地状态再次漂移，用户和测试都能直接看到错误而不是被静默跳转掩盖。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` — 当前 end flow 在 finally 中无条件跳报告页。
- `web/src/hooks/use-practice-websocket.ts` / `web/src/hooks/websocket/message-handlers.ts` — 当前仍存在 lifecycle 乐观写入与恢复事件消费。
- `T01` / `T02` 产出 — 前端要跟随的服务端终态与 `reconnected` 合约基线。

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` / `page.tsx` — 失败可见、终态确认后才跳转的训练页生命周期 UI。
- `web/src/hooks/use-practice-websocket.ts` / `web/src/hooks/websocket/message-handlers.ts` — 只信服务端状态的前端运行时收口。
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts` / `web/src/hooks/use-practice-websocket.test.ts` / `web/src/hooks/websocket/message-handlers.test.ts` — 结束失败与重连恢复回归保护。
