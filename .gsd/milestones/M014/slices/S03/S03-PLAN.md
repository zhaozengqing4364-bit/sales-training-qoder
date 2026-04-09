# S03: Learner 导航、反馈入口与系统壳层补齐

**Goal:** 补齐 learner 侧统一反馈入口、角色/使用说明、缺失导航和壳层级帮助信息
**Demo:** After this: 从首页/profile/history 任一页都能找到帮助/反馈入口

## Tasks
- [ ] **T01: 定位 learner shell 帮助与导航缺口** — 盘点 learner shell、首页、profile、history 当前可见导航与帮助入口，确认缺口集中在哪个 shared shell seam，而不是散页缺按钮。
  - Estimate: 20m
  - Files: web/src/components/layout/sidebar.tsx
  - Verify: rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)
- [ ] **T02: 补齐 learner 统一帮助/反馈入口** — 在 learner shell 或首页/profile 合适位置增加统一帮助/反馈入口与最小角色/权限说明，优先复用现有 sidebar/home 卡片模式。
  - Estimate: 35m
  - Files: web/src/components/layout/sidebar.tsx, web/src/app/(dashboard)/*, web/src/components/dashboard/*
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"
- [ ] **T03: 为 learner shell 帮助入口补 proof** — 补或更新 focused UI proof，锁定从首页/profile/history 任一页都能找到帮助入口。
  - Estimate: 20m
  - Files: web/src/app/(dashboard)/**/*.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"
