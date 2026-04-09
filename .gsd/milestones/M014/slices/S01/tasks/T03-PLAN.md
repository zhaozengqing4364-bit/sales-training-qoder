---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: 为首页闭环补 focused proof

补 focused 测试或更新现有测试，锁定首页无空壳主按钮、首屏有 onboarding、至少一条 CTA 通向真实训练入口。

## Inputs

- `web/src/app/(dashboard)/page.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`

## Expected Output

- `web/src/app/(dashboard)/**/*.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"

## Observability Impact

none
