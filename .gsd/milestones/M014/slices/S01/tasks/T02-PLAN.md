---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: 实现首页 CTA 收口与 onboarding 最小指引

按策略修改首页：动态化硬编码内容，清理空壳 CTA，必要时增加最小 onboarding 卡片或深链入口。优先复用现有 dashboard 组件模式。

## Inputs

- `web/src/app/(dashboard)/page.tsx`
- `web/src/components/layout/sidebar.tsx`

## Expected Output

- `web/src/app/(dashboard)/page.tsx`
- `web/src/components/dashboard/*`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"

## Observability Impact

none
