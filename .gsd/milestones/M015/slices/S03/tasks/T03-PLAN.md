---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T03: 锁定 learner shell baseline proof 与剩余风险

Why: baseline 风险和剩余 deferred 项如果不记录清楚，后续很容易把 M015 做成新的 audit triage 回合。

Do:
1. 记录 remaining responsive/a11y/timezone 风险的 disposition。
2. 补 focused proof，锁定 learner fallback 仍然覆盖关键 route。
3. 确保 baseline 闭合，但不扩大 scope 到全站治理。

Done when: learner shell baseline 既有测试 proof，也有剩余风险记录，后续 agent 可直接消费。

## Inputs

- `web/src/app/**/*.test.tsx`

## Expected Output

- `web/src/app/**/*.test.tsx`

## Verification

find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

## Observability Impact

learner fallback 覆盖与 remaining baseline 风险都变成可回查事实。
