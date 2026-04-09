---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: 盘点当前 backup/recovery 现状

梳理当前部署方式、脚本、数据库连接方式与已有备份事实，确认 runbook 能引用的真实命令/路径/证据位置。

## Inputs

- `docs/*`
- `scripts/*`
- `.env.example`

## Expected Output

- `backup inventory`

## Verification

find docs scripts -maxdepth 2 -type f | sort | head -n 20

## Observability Impact

current backup/recovery fact inventory
