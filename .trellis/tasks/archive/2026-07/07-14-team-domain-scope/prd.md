# 团队领域与权限

## Goal

以显式团队关系替代部门字符串授权，建立可审计、可迁移、可供所有训练服务复用的对象级 Team Scope Policy。

## Scope

* Team、TeamMembership、TeamLeaderAssignment 模型及有效期。
* 一名学员一个有效主团队、团队一名有效主组长的数据库与并发约束。
* 主组长、协同/代理组长以及组长跨多个团队的关系规则。
* 部门到团队 dry-run、冲突报告、可重复 migration 和 ADR。
* journey、training task、team insights 共用 TeamScopePolicy。

## Acceptance Criteria

* [x] 部门字段变化不会授予团队权限。
* [x] 跨团队列表和直接详情访问均被后端拒绝。
* [x] 调组、授权和撤权立即生效并保留历史审计。
* [x] 并发写入不会产生双主团队或双主组长。
* [x] migration 可 dry-run、重复执行和通过 feature flag 回滚读取路径。

## Dependencies

* Parent: `../07-14-account-team-lead/prd.md`
* Requires: `../07-14-account-role-foundation/prd.md`
