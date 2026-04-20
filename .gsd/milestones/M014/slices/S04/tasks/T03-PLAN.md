---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: 为 practice preflight/interruption UX 补 proof

Why: preflight 信息和 interruption 提示都是容易在后续 practice 改动中消失的 UI contract，需要 focused proof 锁住。

Do:
1. 补 focused tests，覆盖训练前预告、中断错误提示与 `test-mic` 非主路径暴露规则。
2. 让断言针对 learner 可见行为，不绑死实现细节。
3. 保持与现有 practice/lifecycle focused suite 同步，不新增臃肿 umbrella test。

Done when: focused proof 能稳定证明开练前说明、中断提示和 test-mic 暴露边界仍然成立。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"

## Observability Impact

practice preflight/interruption contract 可由 focused tests 直接回归。
