---
estimated_steps: 2
estimated_files: 2
skills_used: []
---

# T03: 把 org-boundary plan 写成下一轮企业化 roadmap 输入

- 把这份 org target-state plan 绑定到下一轮 roadmap 入口，明确什么情况下继续留在 modular monolith，什么情况下才值得拆服务。
- 记录 out-of-scope：当前不做多租户实现、不接 SSO/CRM、不改外部集成。

## Inputs

- `T01/T02 outputs`
- `current future roadmap stub`

## Expected Output

- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- `.codex/roadmap/PROJECT_FUTURE.md`

## Verification

rg -n "organization|team|tenant|monolith|service split|out-of-scope|SSO|CRM" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .codex/roadmap/PROJECT_FUTURE.md
