---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T01: 盘点当前 backup/recovery 现状

Why: 先盘清当前已有文档、脚本和数据库连接方式，runbook 才不会写成脱离仓库现实的空文档。

Do:
1. 梳理当前部署方式、脚本、数据库连接方式与已知备份事实。
2. 找出 runbook 可以引用的真实命令、路径和证据位置。
3. 记录缺失项，但不在本任务里臆造自动化能力。

Done when: 已有一份 backup/recovery 现状清单，可直接支撑 runbook 编写。

## Inputs

- `docs/*`
- `scripts/*`

## Expected Output

- `docs/*`
- `scripts/*`

## Verification

find docs scripts -maxdepth 2 -type f | sort | head -n 20

## Observability Impact

形成 backup/recovery 当前现状与可引用路径清单。
