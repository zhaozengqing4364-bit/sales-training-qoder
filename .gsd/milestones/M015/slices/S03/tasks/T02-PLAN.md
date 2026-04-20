---
estimated_steps: 6
estimated_files: 4
skills_used: []
---

# T02: 补齐 learner route fallbacks 并修低风险 UX 问题

Why: learner 壳层必须先覆盖核心 route，再顺手修掉低风险 UX 问题，避免白屏或明显不可用状态继续残留。

Do:
1. 为核心 learner routes 补 route-level error/loading fallback，优先复用 shared components。
2. 修复明确的低风险 responsive/a11y/timezone 问题。
3. 不扩成全站 mobile/WCAG 重构；只解决当前 learner 主链路风险。

Done when: learner 核心 routes 有稳定 fallback，focused learner tests 通过。

## Inputs

- `web/src/app/(dashboard)/**/error.tsx`
- `web/src/app/(dashboard)/**/loading.tsx`
- `web/src/app/(auth)/**`
- `web/src/components/**/*`

## Expected Output

- `web/src/app/(dashboard)/**/error.tsx`
- `web/src/app/(dashboard)/**/loading.tsx`
- `web/src/app/(auth)/**`
- `web/src/components/**/*`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

## Observability Impact

路由级失败时有稳定 fallback surface，而不是白屏或静默失败。
