---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T03: 固定 assembled release gate 与 downstream 复用规则

- 把 assembled release gate 写入 architecture scan / plan，明确 downstream milestones 默认复用哪些 commands 和 live surfaces。
- 补 doc/spec drift check 或 inventory proof，让后续 agent 能判断 api-spec/openapi/docs-api-contract 是否与 live routes 一致。
- 如 admin 首页仍有 demo stats/假监控数字，至少把其 truthfulness gap 记录为 M022 输入，不让它继续伪装成 release surface。

## Inputs

- `T01/T02 结果`
- `M022 productization 输入`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`

## Verification

rg -n "release gate|metrics|error reporting|doc contract|repo-root" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md
