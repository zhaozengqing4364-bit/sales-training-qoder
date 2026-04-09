# S02: 审计相关验证基线补齐

**Goal:** 为后续所有 repair slice 锁定可复用的 web/backend focused 验证命令集合
**Demo:** After this: 每个后续 slice 至少有一条已存在的 focused verification command 可直接执行

## Tasks
- [x] **T01: Added a repo-root focused verification matrix to the audit remediation plan so later repair slices can reuse real web/backend commands by surface.** — 盘点现有 web/backend focused tests，把 auth/dashboard/history/profile/practice/lifecycle/websocket/admin 这几类验证面各自映射到一组真实命令。优先复用现有 focused tests，不引入大规模新测试。
  - Estimate: 30m
  - Files: docs/plans/2026-04-08-system-audit-remediation-plan.md
  - Verify: rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" docs/plans/2026-04-08-system-audit-remediation-plan.md
- [x] **T02: Added an explicit repo-root serial backend pytest contract to both audit remediation plans so downstream slices can reuse focused commands without false auto-mode failures.** — 把 repo-root 可直接执行的 backend pytest 命令与必须串行的约束写进 remediation plan，避免 auto-mode 把 `cd backend && pytest` 拆散后误报失败。
  - Estimate: 20m
  - Files: docs/plans/2026-04-08-system-audit-remediation-plan.md, .gsd/plans/GSD_PLAN_system-audit-repair.md
  - Verify: rg -n "串行|coverage|backend/venv/bin/python -m pytest -c backend/pyproject.toml" docs/plans/2026-04-08-system-audit-remediation-plan.md .gsd/plans/GSD_PLAN_system-audit-repair.md
- [x] **T03: Added a centralized downstream verification baseline map for M014-M018 so later repair slices can reuse real focused proof commands directly.** — 把每个后续 slice 所需的 focused command 回填到里程碑/切片计划中，形成统一 verification contract。
  - Estimate: 25m
  - Files: docs/plans/2026-04-08-system-audit-remediation-plan.md, .gsd/milestones/M013/M013-ROADMAP.md
  - Verify: rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" .gsd/milestones/M01{4,5,6,7,8}*/**/*.md docs/plans/2026-04-08-system-audit-remediation-plan.md
