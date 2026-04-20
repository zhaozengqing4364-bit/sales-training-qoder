# S03: Learner error/loading 覆盖与 responsive/a11y/timezone baseline

**Goal:** 补齐 learner 路由簇中缺失的 error/loading 壳层，并对响应式、a11y、时区问题形成最小基线。
**Demo:** learner 核心路由都有 error/loading fallback，且 baseline responsive/a11y/timezone 风险有记录和低风险修复。

## Must-Haves

- learner 核心 route family 都有明确的 error/loading fallback。
- responsive/a11y/timezone 风险被记录成 baseline，并只修当前低风险高价值问题。
- focused proof 能覆盖 learner 壳层行为，不需要再从 raw audit 文本重新猜测缺口。

## Proof Level

- This slice proves: integration

## Integration Closure

S03 把 M015 前两块前端一致性工作落到 learner route family，形成后续 auth/runtime 变更可直接复用的壳层保护与 baseline 事实线。

## Verification

- future agents 可通过 route-level fallback 文件、focused learner tests 和 baseline 记录快速判断 learner 壳层是功能缺口还是已知 deferred 风险。

## Tasks

- [x] **T01: 建立 learner error/loading 与 lightweight UX baseline matrix** `est:30m`
  Why: 先建 learner route family 的 fallback/baseline matrix，后续才能有边界地补齐壳层，而不是被移动端/a11y 全面重写吞掉。

Do:
1. 枚举 learner 相关 route 现有 `error.tsx` / `loading.tsx`。
2. 标记真正缺口，以及 responsive/a11y/timezone 的明显风险点。
3. 只挑低风险高价值项进入当前修复，其他保留为 baseline 记录。

Done when: 已有一份 learner fallback + lightweight UX baseline matrix，可直接指导后续补齐。
  - Files: `web/src/app/(dashboard)/**/error.tsx`, `web/src/app/(dashboard)/**/loading.tsx`, `web/src/app/(auth)/**`
  - Verify: find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort

- [x] **T02: 补齐 learner route fallbacks 并修低风险 UX 问题** `est:1h`
  Why: learner 壳层必须先覆盖核心 route，再顺手修掉低风险 UX 问题，避免白屏或明显不可用状态继续残留。

Do:
1. 为核心 learner routes 补 route-level error/loading fallback，优先复用 shared components。
2. 修复明确的低风险 responsive/a11y/timezone 问题。
3. 不扩成全站 mobile/WCAG 重构；只解决当前 learner 主链路风险。

Done when: learner 核心 routes 有稳定 fallback，focused learner tests 通过。
  - Files: `web/src/app/(dashboard)/**/error.tsx`, `web/src/app/(dashboard)/**/loading.tsx`, `web/src/app/(auth)/**`, `web/src/components/**/*`
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

- [x] **T03: 锁定 learner shell baseline proof 与剩余风险** `est:25m`
  Why: baseline 风险和剩余 deferred 项如果不记录清楚，后续很容易把 M015 做成新的 audit triage 回合。

Do:
1. 记录 remaining responsive/a11y/timezone 风险的 disposition。
2. 补 focused proof，锁定 learner fallback 仍然覆盖关键 route。
3. 确保 baseline 闭合，但不扩大 scope 到全站治理。

Done when: learner shell baseline 既有测试 proof，也有剩余风险记录，后续 agent 可直接消费。
  - Files: `web/src/app/**/*.test.tsx`
  - Verify: find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

## Files Likely Touched

- web/src/app/(dashboard)/**/error.tsx
- web/src/app/(dashboard)/**/loading.tsx
- web/src/app/(auth)/**
- web/src/components/**/*
- web/src/app/**/*.test.tsx
