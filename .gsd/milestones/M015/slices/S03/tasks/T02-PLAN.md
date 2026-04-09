---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: 补齐 learner route fallbacks 并修低风险 UX 问题

为核心 learner routes 补 route-level error/loading fallback，优先复用现有 shared components；顺手修复明确的低风险 responsive/a11y/timezone 问题。

## Inputs

- `web/src/app/(dashboard)`
- `web/src/app/(auth)`
- `web/src/components`

## Expected Output

- `web/src/app/(dashboard)/**/error.tsx`
- `web/src/app/(dashboard)/**/loading.tsx`
- `web/src/app/(auth)/**`
- `web/src/components/**/*`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

## Observability Impact

错误/加载状态可视化
