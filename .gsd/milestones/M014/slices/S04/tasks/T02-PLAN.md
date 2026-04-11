---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T02: 实现 practice preflight 与 interruption UX 收口

Why: learner 在真正开练前必须被告知这次练什么、失败时该怎么办，否则主链路仍然割裂。

Do:
1. 在现有 practice 页面内增加训练前目标、评价标准和角色简介的最小预告。
2. 为暂停/恢复/结束失败补清晰的 learner-facing 文案和下一步动作提示。
3. 把 `test-mic` 标记为开发工具或从 learner 主路径隐藏。
4. 复用现有 overlay/banner/panel，不新增复杂 preflight route。

Done when: practice 主页面在开练前和中断失败时都能给出可理解指导，且 focused tests 保持通过。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/test-mic/*`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/test-mic/*`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"

## Observability Impact

practice 页面中断态与 preflight 信息变成稳定可见的 learner surface。
