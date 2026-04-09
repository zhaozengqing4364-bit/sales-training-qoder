# S02: Practice WebSocket 复杂度与重连策略收口

**Goal:** 把当前 practice websocket orchestrator 的复杂度、重连策略和 backpressure 规则再收口一轮
**Demo:** After this: practice websocket 的 reconnect/backpressure/interrupt contract 更清晰，测试保持通过

## Tasks
- [ ] **T01: 识别 websocket hook 的真实职责边界** — 盘点 use-practice-websocket 当前已承载的 reconnect/backpressure/interrupt/binary frame negotiation 事实，找出真实 seam，而不是仅因文件大而拆分。
  - Estimate: 35m
  - Files: web/src/hooks/use-practice-websocket.ts, web/src/hooks/use-practice-websocket.test.ts, web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  - Verify: rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts
- [ ] **T02: 实现 websocket reconnect/backpressure/interrupt 收口** — 按真实 seam 收口 reconnect 策略、backpressure/队列清理和 interrupt 处理；必要时拆分 hook 内部职责，但不引入重量级状态机框架。
  - Estimate: 1.5h
  - Files: web/src/hooks/use-practice-websocket.ts, web/src/hooks/**/*, web/src/app/(user)/practice/[sessionId]/page.tsx
  - Verify: npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"
- [ ] **T03: 为 websocket orchestration contract 补 proof** — 补 focused tests，锁定 reconnect 退出条件、backpressure 清理和 interrupt contract，不让复杂度回流。
  - Estimate: 40m
  - Files: web/src/hooks/use-practice-websocket.test.ts, web/src/hooks/use-practice-websocket.presentation-flow.test.ts, web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - Verify: npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"
