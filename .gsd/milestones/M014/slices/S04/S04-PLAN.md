# S04: 训练前预期管理与中断恢复 UX 收口

**Goal:** 补齐 practice 页的训练前目标/评价标准/角色简介最小预告，以及暂停/恢复/结束失败的用户可理解文案。
**Demo:** 用户在开始录音前能理解本次练习目标，暂停/恢复/结束失败时有清晰指引

## Must-Haves

- 用户在开始录音前能看懂本次练习目标、评价标准和角色背景。
- 暂停/恢复/结束失败时页面会给出清晰可理解的下一步提示，而不是只留技术态。
- `test-mic` 不再作为普通 learner 主路径入口暴露。

## Proof Level

- This slice proves: integration

## Integration Closure

S04 把 M014 前三块 learner 入口、auth/profile 与 shell 信息收口到 practice 主链路，形成真正可开练的预期管理与中断恢复 UX。

## Verification

- future agents 可通过 practice 页面 focused tests、lifecycle hook 和 learner UI 状态判断 preflight 信息、中断提示与 test-mic 暴露边界是否仍然成立。

## Tasks

- [ ] **T01: 梳理 practice preflight 与 interruption 当前表面** `est:30m`
  Why: 先把 practice 页面已有的 persona/scenario 信息与 interruption 表面盘清，避免重复实现已经存在的上下文卡片或错误提示。

Do:
1. 阅读 practice page、lifecycle hook 和 websocket hook 中当前的 preflight/interruption 表面。
2. 梳理训练前已经可获得的 persona、scenario、goal、评分维度信息。
3. 记录暂停/恢复/结束失败现在如何呈现，以及 `test-mic` 如何被 learner 发现。

Done when: 后续实现能复用真实现有数据和 UI seam，而不是新建额外入口。
  - Files: `web/src/app/(user)/practice/[sessionId]/page.tsx`, `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`, `web/src/hooks/use-practice-websocket.ts`
  - Verify: rg -n "pause|resume|end|test-mic|persona|scenario|goal" web/src/app/\(user\)/practice/\[sessionId\]/page.tsx web/src/hooks/use-practice-websocket.ts

- [ ] **T02: 实现 practice preflight 与 interruption UX 收口** `est:1h`
  Why: learner 在真正开练前必须被告知这次练什么、失败时该怎么办，否则主链路仍然割裂。

Do:
1. 在现有 practice 页面内增加训练前目标、评价标准和角色简介的最小预告。
2. 为暂停/恢复/结束失败补清晰的 learner-facing 文案和下一步动作提示。
3. 把 `test-mic` 标记为开发工具或从 learner 主路径隐藏。
4. 复用现有 overlay/banner/panel，不新增复杂 preflight route。

Done when: practice 主页面在开练前和中断失败时都能给出可理解指导，且 focused tests 保持通过。
  - Files: `web/src/app/(user)/practice/[sessionId]/page.tsx`, `web/src/app/(user)/practice/test-mic/*`
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"

- [ ] **T03: 为 practice preflight/interruption UX 补 proof** `est:35m`
  Why: preflight 信息和 interruption 提示都是容易在后续 practice 改动中消失的 UI contract，需要 focused proof 锁住。

Do:
1. 补 focused tests，覆盖训练前预告、中断错误提示与 `test-mic` 非主路径暴露规则。
2. 让断言针对 learner 可见行为，不绑死实现细节。
3. 保持与现有 practice/lifecycle focused suite 同步，不新增臃肿 umbrella test。

Done when: focused proof 能稳定证明开练前说明、中断提示和 test-mic 暴露边界仍然成立。
  - Files: `web/src/app/(user)/practice/[sessionId]/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"

## Files Likely Touched

- web/src/app/(user)/practice/[sessionId]/page.tsx
- web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
- web/src/hooks/use-practice-websocket.ts
- web/src/app/(user)/practice/test-mic/*
- web/src/app/(user)/practice/[sessionId]/page.test.tsx
