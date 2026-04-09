---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: 为 learner shell 帮助入口补 proof

补或更新 focused UI proof，锁定从首页/profile/history 任一页都能找到帮助入口。

## Inputs

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/*`

## Expected Output

- `web/src/app/(dashboard)/**/*.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"

## Observability Impact

none
