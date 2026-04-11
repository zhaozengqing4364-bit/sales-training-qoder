# S01: 首页硬编码与空壳动作收口

**Goal:** 清理 dashboard 首页静态更新内容、无动作按钮、假筛选与缺少 onboarding 的问题。
**Demo:** 首页不再有“点了没反应”的主按钮/CTA，首屏有最小 onboarding 指引

## Must-Haves

- 首页不再存在“点了没反应”的主按钮或主 CTA。
- 首屏有最小 onboarding 指引，至少告诉 learner 如何开始第一轮训练。
- focused proof 能锁定首页至少一条 CTA 通向真实训练入口，且 report export/share/goal 等已知缺失 affordance 不会被误加回。

## Proof Level

- This slice proves: integration

## Integration Closure

S01 先把 learner 首屏 CTA 和 onboarding 收口到真实训练入口，为 M014/S02-S04 的 auth/profile、help shell 与 practice preflight 提供稳定起点。

## Verification

- future agents 可通过 dashboard focused tests 和首页 CTA/onboarding 行为快速判断 learner 首屏仍然是可走通闭环，而不是一组空壳按钮。

## Tasks

- [x] **T01: Documented the dashboard-home CTA closure strategy, kept export/share/goal affordances absent, and fixed the version-dialog dismiss action.** `est:30m`
  Why: 先把 dashboard 首页所有 CTA、版本弹窗与筛选类 affordance 分类清楚，才能避免把 deferred/缺失能力重新伪装成“应该补上”。

Do:
1. 逐项清点首页主按钮、版本弹窗、筛选弹窗和分享/设定目标类 CTA。
2. 按“实现、深链、disabled 文案、删除”四类形成收口策略。
3. 明确 report export、分享分析、设定目标等 affordance 继续保持缺失或诚实禁用。
4. 修正已有版本弹窗等明显的无效交互。

Done when: 首页所有关键 CTA 都有明确 disposition，后续实现不需要再次做策略争论。
  - Files: `web/src/app/(dashboard)/page.tsx`, `.gsd/plans/GSD_PLAN_system-audit-repair.md`
  - Verify: rg -n "导出报告|设定目标|分享分析|筛选" web/src/app/\(dashboard\)/page.tsx

- [ ] **T02: 实现首页 CTA 收口与 onboarding 最小指引** `est:45m`
  Why: learner 首屏只有把 CTA 收口并补上最小 onboarding，才算从“演示首页”变成“能开练的首页”。

Do:
1. 按策略修改首页，动态化硬编码内容并清理空壳 CTA。
2. 增加最小 onboarding 卡片或深链入口，告诉用户如何开始练习。
3. 优先复用现有 dashboard 组件模式，不新建独立 onboarding 子系统。
4. 保持至少一条 CTA 指向真实训练入口。

Done when: 首页主 CTA 都有真实动作或诚实禁用态，且首屏出现最小 onboarding 指引。
  - Files: `web/src/app/(dashboard)/page.tsx`, `web/src/components/dashboard/*`
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"

- [x] **T03: 为首页闭环补 focused proof** `est:30m`
  Why: 首页闭环很容易在后续 dashboard 视觉或文案改动中再次退回空壳，需要 focused proof 锁住。

Do:
1. 补 focused 测试或更新现有测试。
2. 锁定首页无空壳主按钮、首屏有 onboarding、至少一条 CTA 通向真实训练入口。
3. 明确不把 report export 等已知缺失 affordance 重新放回可点击状态。

Done when: focused dashboard tests 能稳定证明首页闭环仍然存在。
  - Files: `web/src/app/(dashboard)/**/*.test.tsx`
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"

## Files Likely Touched

- web/src/app/(dashboard)/page.tsx
- .gsd/plans/GSD_PLAN_system-audit-repair.md
- web/src/components/dashboard/*
- web/src/app/(dashboard)/**/*.test.tsx
