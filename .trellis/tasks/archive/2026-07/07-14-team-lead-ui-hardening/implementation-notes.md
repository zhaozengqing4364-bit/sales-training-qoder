# Implementation Notes

## Completed

- `/team` 重构为 Dashboard–Drilldown 只读工作台，明确本期不能发布或修改任务。
- 多团队、周期、同期、搜索、风险筛选进入 URL；详情保留路径活动和管理员任务来源语义。
- 后端封锁组长创建、批量分配、修改、取消、完成和代启动任务的写入口。
- 完成 TypeScript、ESLint、Vitest、后端权限/事务测试与 Next.js 生产构建。
- 使用 `EXPLICIT_TEAM_SCOPE_ENABLED` 作为安全灰度/回滚开关。

## Deviations

- 未对共享外部数据库执行迁移或创建真实账号；迁移和真实账号 E2E 留到受控发布环境。
