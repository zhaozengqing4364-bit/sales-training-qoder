---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 梳理 practice preflight 与 interruption 当前表面

Why: 先把 practice 页面已有的 persona/scenario 信息与 interruption 表面盘清，避免重复实现已经存在的上下文卡片或错误提示。

Do:
1. 阅读 practice page、lifecycle hook 和 websocket hook 中当前的 preflight/interruption 表面。
2. 梳理训练前已经可获得的 persona、scenario、goal、评分维度信息。
3. 记录暂停/恢复/结束失败现在如何呈现，以及 `test-mic` 如何被 learner 发现。

Done when: 后续实现能复用真实现有数据和 UI seam，而不是新建额外入口。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
- `web/src/hooks/use-practice-websocket.ts`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
- `web/src/hooks/use-practice-websocket.ts`

## Verification

rg -n "pause|resume|end|test-mic|persona|scenario|goal" web/src/app/\(user\)/practice/\[sessionId\]/page.tsx web/src/hooks/use-practice-websocket.ts

## Observability Impact

形成 practice preflight 与 interruption 当前表面清单。
