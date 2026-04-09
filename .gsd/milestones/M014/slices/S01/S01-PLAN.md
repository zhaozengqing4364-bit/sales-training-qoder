# S01: 首页硬编码与空壳动作收口

**Goal:** 清理 dashboard 首页静态更新内容、无动作按钮、假筛选与缺少 onboarding 的问题
**Demo:** After this: 首页不再有“点了没反应”的主按钮/CTA，首屏有最小 onboarding 指引

## Tasks
- [ ] **T01: 清点首页空壳动作并确定收口策略** — 逐项清点 dashboard 首页按钮、版本弹窗、筛选弹窗、分享/设定目标类 CTA，按“实现 / 深链 / disabled 文案 / 删除”形成动作收口策略表。优先确认 report export 继续保持缺失。
  - Estimate: 30m
  - Files: web/src/app/(dashboard)/page.tsx, .gsd/plans/GSD_PLAN_system-audit-repair.md
  - Verify: rg -n "导出报告|设定目标|分享分析|筛选" web/src/app/\(dashboard\)/page.tsx
- [ ] **T02: 实现首页 CTA 收口与 onboarding 最小指引** — 按策略修改首页：动态化硬编码内容，清理空壳 CTA，必要时增加最小 onboarding 卡片或深链入口。优先复用现有 dashboard 组件模式。
  - Estimate: 45m
  - Files: web/src/app/(dashboard)/page.tsx, web/src/components/dashboard/*
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"
- [ ] **T03: 为首页闭环补 focused proof** — 补 focused 测试或更新现有测试，锁定首页无空壳主按钮、首屏有 onboarding、至少一条 CTA 通向真实训练入口。
  - Estimate: 30m
  - Files: web/src/app/(dashboard)/**/*.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"
