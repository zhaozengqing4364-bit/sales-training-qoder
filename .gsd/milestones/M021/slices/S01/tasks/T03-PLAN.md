---
estimated_steps: 2
estimated_files: 2
skills_used: []
---

# T03: 输出 live/compat/retire 输入矩阵

- 从 inventory 中筛出必须保留、可兼容、应退役的路径，形成 S02-S04 的输入矩阵。
- 明确不能在本 milestone 中一次性粗暴删除的 legacy consumers。

## Inputs

- `T01/T02 outputs`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`

## Verification

rg -n "must keep|compat|retire candidate|consumer" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md
