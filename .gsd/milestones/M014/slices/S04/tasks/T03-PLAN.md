---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: 为 practice preflight/interruption UX 补 proof

补 focused tests，锁定训练前预告、中断错误提示和 test-mic 非主路径暴露规则。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx`

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"

## Observability Impact

none
