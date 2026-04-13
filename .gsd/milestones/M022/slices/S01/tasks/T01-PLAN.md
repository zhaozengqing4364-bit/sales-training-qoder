---
estimated_steps: 2
estimated_files: 5
skills_used: []
---

# T01: 定义首轮方法论-aware rubric contract

- 结合当前 sales_stage/realtime_scoring/effectiveness_snapshot 与 report surfaces，选定首轮方法论维度映射。
- 写出 rubric contract：方法论概念、可观察证据、评分/建议映射、兼容当前 score schema 的方式。

## Inputs

- `M021 canonical kernel`
- `current sales scoring/stage surfaces`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/common/effectiveness/*`
- `docs/api-contract/*`

## Verification

rg -n "sales_stage|realtime_scoring|effectiveness|main_issue|next_goal|dimension_scores" backend/src/common backend/src/agent docs/api-contract
