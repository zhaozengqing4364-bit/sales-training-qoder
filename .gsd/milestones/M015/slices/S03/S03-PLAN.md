# S03: Learner error/loading 覆盖与 responsive/a11y/timezone baseline

**Goal:** 补齐 learner 路由簇中缺失的 error/loading 壳层，并对响应式、a11y、时区问题形成最小基线
**Demo:** After this: learner 核心路由都有 error/loading fallback，且 baseline responsive/a11y/timezone 风险有记录和低风险修复

## Tasks
- [ ] **T01: 建立 learner error/loading 与 lightweight UX baseline matrix** — 枚举 learner route family 当前已有的 error.tsx / loading.tsx，并标记缺口；同时记录 responsive/a11y/timezone 的明显风险点，但只选低风险高价值项进入修复。
  - Estimate: 30m
  - Files: web/src/app/(dashboard)/**/error.tsx, web/src/app/(dashboard)/**/loading.tsx, web/src/app/(auth)/**
  - Verify: find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort
- [ ] **T02: 补齐 learner route fallbacks 并修低风险 UX 问题** — 为核心 learner routes 补 route-level error/loading fallback，优先复用现有 shared components；顺手修复明确的低风险 responsive/a11y/timezone 问题。
  - Estimate: 1h
  - Files: web/src/app/(dashboard)/**/error.tsx, web/src/app/(dashboard)/**/loading.tsx, web/src/app/(auth)/**, web/src/components/**/*
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
- [ ] **T03: 锁定 learner shell baseline proof 与剩余风险** — 记录 remaining responsive/a11y/timezone 风险的 disposition，并补 focused proof，确保 baseline 闭合但不扩 scope。
  - Estimate: 25m
  - Files: web/src/app/**/*.test.tsx
  - Verify: find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
