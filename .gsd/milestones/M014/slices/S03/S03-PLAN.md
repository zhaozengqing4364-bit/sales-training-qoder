# S03: Learner 导航、反馈入口与系统壳层补齐

**Goal:** 补齐 learner 侧统一反馈入口、角色/使用说明、缺失导航和壳层级帮助信息。
**Demo:** 从首页/profile/history 任一页都能找到帮助/反馈入口

## Must-Haves

- 从首页、profile、history 任一页都能找到稳定的帮助/反馈入口。
- 帮助/反馈入口优先落在 shared learner shell seam，而不是分散的页内特例按钮。
- focused proof 能锁定该入口仍然可见、可理解，且没有重新退回隐性支持路径。

## Proof Level

- This slice proves: integration

## Integration Closure

S03 在现有 learner shell、首页、profile、history 等入口上落统一帮助/反馈 seam，让 M014 的首页、profile 和 practice 体验不再依赖散页补按钮。

## Verification

- future agents 可直接从 learner shell 与 focused dashboard tests 判断帮助入口是否存在、是否仍走同一 shared seam，而不是重新翻每个页面。

## Tasks

- [x] **T01: 定位 learner shell 帮助与导航缺口** `est:20m`
  Why: 先找到 learner shell 里真正缺的是 shared seam 还是散页按钮，避免后续把帮助入口补成到处乱放的临时卡片。

Do:
1. 盘点 sidebar、dashboard 首页、profile、history 当前可见的导航与帮助入口。
2. 确认支持/反馈信息是否已经存在但不可发现，还是根本缺失。
3. 标出最适合承载统一入口的 shared shell seam。

Done when: 后续实现能围绕一个稳定入口收口，而不是在多个页面临时塞按钮。
  - Files: `web/src/components/layout/sidebar.tsx`, `web/src/app/(dashboard)/*`
  - Verify: rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)

- [ ] **T02: 补齐 learner 统一帮助/反馈入口** `est:35m`
  Why: 帮助/反馈入口必须优先收口到 shared learner shell 或共享卡片模式，才能避免之后再次分散。

Do:
1. 在 learner shell 或首页/profile 的合适位置增加统一帮助/反馈入口。
2. 补最小角色/权限说明，让 learner 知道遇到问题时去哪里、为什么有些入口看不到。
3. 优先复用 sidebar/home 卡片模式，不新增完整帮助中心。
4. 保持文案诚实，不承诺未实现的支持系统。

Done when: learner 从主要入口页都能通过同一套模式找到帮助/反馈入口。
  - Files: `web/src/components/layout/sidebar.tsx`, `web/src/app/(dashboard)/*`, `web/src/components/dashboard/*`
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"

- [ ] **T03: 为 learner shell 帮助入口补 proof** `est:20m`
  Why: 如果没有 focused proof，帮助入口很容易在后续壳层改动里再次消失。

Do:
1. 补或更新 focused UI proof，覆盖首页、profile、history 等关键 learner 入口。
2. 锁定帮助入口的可见性与基础文案，不要求复杂交互系统。
3. 保持测试针对 shared shell seam，而不是只断言单页面临时实现。

Done when: focused tests 能稳定证明 learner 在多个入口页都能找到帮助/反馈入口。
  - Files: `web/src/app/(dashboard)/**/*.test.tsx`
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"

## Files Likely Touched

- web/src/components/layout/sidebar.tsx
- web/src/app/(dashboard)/*
- web/src/components/dashboard/*
- web/src/app/(dashboard)/**/*.test.tsx
