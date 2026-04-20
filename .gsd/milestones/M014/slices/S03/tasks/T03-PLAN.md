---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T03: 为 learner shell 帮助入口补 proof

Why: 如果没有 focused proof，帮助入口很容易在后续壳层改动里再次消失。

Do:
1. 补或更新 focused UI proof，覆盖首页、profile、history 等关键 learner 入口。
2. 锁定帮助入口的可见性与基础文案，不要求复杂交互系统。
3. 保持测试针对 shared shell seam，而不是只断言单页面临时实现。

Done when: focused tests 能稳定证明 learner 在多个入口页都能找到帮助/反馈入口。

## Inputs

- `web/src/app/(dashboard)/**/*.test.tsx`

## Expected Output

- `web/src/app/(dashboard)/**/*.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"

## Observability Impact

帮助入口是否存在可由 focused dashboard tests 直接回归。
