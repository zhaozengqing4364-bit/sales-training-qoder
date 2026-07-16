# Implementation Notes

## Completed

- 新增 Team、TeamMembership、TeamLeaderAssignment 及数据库唯一/有效期约束。
- TeamScopePolicy 成为 journey、training task、team insights 的对象级授权入口；部门字段不再授权。
- 支持主组长、代理组长、多团队；调组和撤权即时生效且保留历史。
- 提供默认 dry-run 的部门迁移脚本、冲突跳过、可重复执行与安全失败关闭开关。
- ADR 记录权限、迁移和回滚决策。

## Deviations

- `EXPLICIT_TEAM_SCOPE_ENABLED=false` 采用安全失败关闭，不回退旧部门授权。
