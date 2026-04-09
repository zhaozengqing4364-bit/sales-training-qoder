# S04: 训练前预期管理与中断恢复 UX 收口

**Goal:** 补齐 practice 页的训练前目标/评价标准/角色简介最小预告，以及暂停/恢复/结束失败的用户可理解文案
**Demo:** After this: 用户在开始录音前能理解本次练习目标，暂停/恢复/结束失败时有清晰指引

## Tasks
- [ ] **T01: 梳理 practice preflight 与 interruption 当前表面** — 阅读 practice page、lifecycle hook、websocket hook，梳理训练前可用的 persona/scenario 信息以及暂停/恢复/结束失败目前如何呈现。
  - Estimate: 30m
  - Files: web/src/app/(user)/practice/[sessionId]/page.tsx, web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
  - Verify: rg -n "pause|resume|end|test-mic|persona|scenario|goal" web/src/app/\(user\)/practice/\[sessionId\]/page.tsx web/src/hooks/use-practice-websocket.ts
- [ ] **T02: 实现 practice preflight 与 interruption UX 收口** — 在现有页面内增加训练前目标/评价标准/角色简介预告，并补清晰的暂停/恢复/结束失败文案；把 test-mic 标记为开发工具或隐藏出 learner 主路径。
  - Estimate: 1h
  - Files: web/src/app/(user)/practice/[sessionId]/page.tsx, web/src/app/(user)/practice/test-mic/*
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"
- [ ] **T03: 为 practice preflight/interruption UX 补 proof** — 补 focused tests，锁定训练前预告、中断错误提示和 test-mic 非主路径暴露规则。
  - Estimate: 35m
  - Files: web/src/app/(user)/practice/[sessionId]/page.test.tsx, web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"
