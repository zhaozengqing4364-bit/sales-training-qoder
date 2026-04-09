---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: 实现 practice preflight 与 interruption UX 收口

在现有页面内增加训练前目标/评价标准/角色简介预告，并补清晰的暂停/恢复/结束失败文案；把 test-mic 标记为开发工具或隐藏出 learner 主路径。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/test-mic/*`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/test-mic/*`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"

## Observability Impact

失败提示与下一步动作可见
