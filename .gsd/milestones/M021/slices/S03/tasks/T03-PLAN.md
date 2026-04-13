---
estimated_steps: 2
estimated_files: 5
skills_used: []
---

# T03: 让前端读侧显式消费 canonical/compat contract

- 更新 web shared types / report/replay/history/admin focused tests，让页面明确区分 canonical 字段与 compat 字段。
- 文档化 canonical kernel 与 compat reader 的退役计划。

## Inputs

- `T02 backend outputs`
- `current web score consumers`

## Expected Output

- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"
