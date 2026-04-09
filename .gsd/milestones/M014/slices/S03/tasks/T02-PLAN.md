---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 补齐 learner 统一帮助/反馈入口

在 learner shell 或首页/profile 合适位置增加统一帮助/反馈入口与最小角色/权限说明，优先复用现有 sidebar/home 卡片模式。

## Inputs

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/page.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`

## Expected Output

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/*`
- `web/src/components/dashboard/*`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"

## Observability Impact

none
