---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 建立 learner error/loading 与 lightweight UX baseline matrix

Why: 先建 learner route family 的 fallback/baseline matrix，后续才能有边界地补齐壳层，而不是被移动端/a11y 全面重写吞掉。

Do:
1. 枚举 learner 相关 route 现有 `error.tsx` / `loading.tsx`。
2. 标记真正缺口，以及 responsive/a11y/timezone 的明显风险点。
3. 只挑低风险高价值项进入当前修复，其他保留为 baseline 记录。

Done when: 已有一份 learner fallback + lightweight UX baseline matrix，可直接指导后续补齐。

## Inputs

- `web/src/app/(dashboard)/**/error.tsx`
- `web/src/app/(dashboard)/**/loading.tsx`
- `web/src/app/(auth)/**`

## Expected Output

- `web/src/app/(dashboard)/**/error.tsx`
- `web/src/app/(dashboard)/**/loading.tsx`
- `web/src/app/(auth)/**`

## Verification

find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort

## Observability Impact

形成 learner route family 的 fallback 与 baseline 风险矩阵。
