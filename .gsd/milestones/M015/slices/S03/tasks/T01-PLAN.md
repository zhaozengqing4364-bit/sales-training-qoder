---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 建立 learner error/loading 与 lightweight UX baseline matrix

枚举 learner route family 当前已有的 error.tsx / loading.tsx，并标记缺口；同时记录 responsive/a11y/timezone 的明显风险点，但只选低风险高价值项进入修复。

## Inputs

- `web/src/app`
- `web/src/components`

## Expected Output

- `learner shell coverage matrix`

## Verification

find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort

## Observability Impact

route coverage matrix 形成基线
