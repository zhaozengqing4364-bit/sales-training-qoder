---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T03: 为首页闭环补 focused proof

Why: 首页闭环很容易在后续 dashboard 视觉或文案改动中再次退回空壳，需要 focused proof 锁住。

Do:
1. 补 focused 测试或更新现有测试。
2. 锁定首页无空壳主按钮、首屏有 onboarding、至少一条 CTA 通向真实训练入口。
3. 明确不把 report export 等已知缺失 affordance 重新放回可点击状态。

Done when: focused dashboard tests 能稳定证明首页闭环仍然存在。

## Inputs

- `web/src/app/(dashboard)/**/*.test.tsx`

## Expected Output

- `web/src/app/(dashboard)/**/*.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"

## Observability Impact

首页 learner 闭环可由 focused dashboard tests 直接回归。
