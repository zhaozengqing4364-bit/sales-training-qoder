# S02: Practice WebSocket 复杂度与重连策略收口

**Goal:** 把当前 practice websocket orchestrator 的复杂度、重连策略和 backpressure 规则再收口一轮。
**Demo:** practice websocket 的 reconnect/backpressure/interrupt contract 更清晰，测试保持通过。

## Must-Haves

- `use-practice-websocket` 的 reconnect、backpressure、interrupt 职责边界被澄清。
- 重连退出条件、队列清理和 interrupt 行为有 focused proof。
- 收口后的复杂度来自真实 seam，而不是单纯按文件大小拆分。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 在 S01 已证明的 lifecycle 终态上锁定 websocket reconnect/backpressure/interrupt seam，为 S03 的 upload/resource race discovery 留出清晰边界。

## Verification

- future agents 可通过 websocket focused tests 与 practice 页面断言快速判断问题出在 reconnect、队列清理、interrupt 还是更下游的 runtime。

## Tasks

- [x] **T01: 识别 websocket hook 的真实职责边界** `est:35m`
  Why: 先识别 websocket hook 真实职责边界，才能避免“文件大就拆”的假重构。

Do:
1. 盘点 `use-practice-websocket` 当前承载的 reconnect/backpressure/interrupt/binary negotiation 事实。
2. 标出真正需要收口的 seam。
3. 区分复杂度问题与只是职责集中但仍合理的部分。

Done when: 已明确 hook 的真实职责边界，后续实现不会为了拆分而拆分。
  - Files: `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
  - Verify: rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts

- [x] **T02: 实现 websocket reconnect/backpressure/interrupt 收口** `est:1.5h`
  Why: reconnect/backpressure/interrupt 是 practice 主链路里最容易靠经验式 patch 堆积复杂度的地方，必须统一收口。

Do:
1. 按真实 seam 调整 reconnect 策略、队列清理和 interrupt 处理。
2. 必要时拆分 hook 内部职责，但不引入重量级状态机框架。
3. 保持 practice 页面现有主链路和 focused tests 仍然可证明通过。

Done when: focused websocket + practice tests 通过，reconnect/backpressure/interrupt contract 更清晰。
  - Files: `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/**/*`, `web/src/app/(user)/practice/[sessionId]/page.tsx`
  - Verify: npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"

- [x] **T03: 为 websocket orchestration contract 补 proof** `est:40m`
  Why: websocket orchestration contract 如果没有 focused proof，很容易在下一次 runtime 调整时再次膨胀或回归。

Do:
1. 补 focused tests，锁定 reconnect 退出条件、backpressure 清理和 interrupt contract。
2. 保持断言关注 learner 可见行为和 hook outward contract，不写死内部实现。
3. 让 future agents 能通过一组 focused tests 重建当前 websocket 设计边界。

Done when: websocket orchestration contract 有稳定 focused proof，可防止复杂度回流。
  - Files: `web/src/hooks/use-practice-websocket.test.ts`, `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`, `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
  - Verify: npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"

## Files Likely Touched

- web/src/hooks/use-practice-websocket.ts
- web/src/hooks/use-practice-websocket.test.ts
- web/src/hooks/use-practice-websocket.presentation-flow.test.ts
- web/src/hooks/**/*
- web/src/app/(user)/practice/[sessionId]/page.tsx
- web/src/app/(user)/practice/[sessionId]/page.test.tsx
