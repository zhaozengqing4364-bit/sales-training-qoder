---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T02: 实现首页 CTA 收口与 onboarding 最小指引

Why: learner 首屏只有把 CTA 收口并补上最小 onboarding，才算从“演示首页”变成“能开练的首页”。

Do:
1. 按策略修改首页，动态化硬编码内容并清理空壳 CTA。
2. 增加最小 onboarding 卡片或深链入口，告诉用户如何开始练习。
3. 优先复用现有 dashboard 组件模式，不新建独立 onboarding 子系统。
4. 保持至少一条 CTA 指向真实训练入口。

Done when: 首页主 CTA 都有真实动作或诚实禁用态，且首屏出现最小 onboarding 指引。

## Inputs

- `web/src/app/(dashboard)/page.tsx`
- `web/src/components/dashboard/*`

## Expected Output

- `web/src/app/(dashboard)/page.tsx`
- `web/src/components/dashboard/*`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"

## Observability Impact

首页 CTA 与 onboarding 形成稳定 learner-visible surface。
