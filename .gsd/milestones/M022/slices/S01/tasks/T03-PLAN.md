---
estimated_steps: 2
estimated_files: 3
skills_used: []
---

# T03: 把 rubric 语义写回用户/管理面说明

- 更新 learner-facing 和 manager-facing 文档/文案，让方法论语义对用户可解释。
- 写明首轮不覆盖的方法论边界，防止产品话术超过真实能力。

## Inputs

- `T02 outputs`
- `current user-facing copy`

## Expected Output

- `docs/api-contract/*`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "qualification|discovery|value|objection|next-step|rubric" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/app/(user)/practice/[sessionId]/report/page.tsx
