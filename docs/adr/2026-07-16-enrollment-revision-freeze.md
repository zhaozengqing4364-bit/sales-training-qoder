# ADR：Enrollment 默认冻结 PathRevision

- 日期：2026-07-16
- 状态：Implemented by Slice 2（取代 2026-07-13 全量自动迁移决策）
- Supersedes：[`2026-07-13-newcomer-training-live-enrollment-rollout.md`](./2026-07-13-newcomer-training-live-enrollment-rollout.md)

## 决策

`Cohort` 绑定一个已发布 `PathRevision`，由 Cohort 创建的 `Enrollment` 默认冻结该修订。发布新修订只影响之后创建或明确选择该修订的 Cohort/Enrollment；Journey 读取不得自修复到“最新发布修订”。

在学人员迁移只能通过显式 `MigrateEnrollmentRevision` 命令：先预览差异、受影响 Attempt、阻塞项与人数，再由有权限的操作者提供原因和 `expected_version` 确认。迁移保留原 Attempt、Outcome 和证据快照，写审计与 `EnrollmentRevisionMigrated` Outbox 事件；重复幂等键返回原结果。

## 原因与后果

训练依据必须在一次 Enrollment 内可解释。Slice 2 的 `newcomer_training.PathEnrollmentService` 已成为 Path、Cohort、Enrollment 与显式迁移的正式写权威；新 Journey 只读取 Enrollment 冻结的 `path_revision_id`。旧 `EnrollmentRepository.get_or_create()` 指针改写、`sync_active_path_revision()` 和旧 Path writer 已从新人训练挂载链路移除，不作为兼容写入口。

## 实现与验证证据

- 数据库：`newcomer_enrollments_v2.path_revision_id` 保存冻结修订；`newcomer_enrollment_migrations` 保存 preview、影响 hash、过期、确认幂等和逐项结果。
- 命令：`POST /enrollments/{enrollment_id}/revision-migrations/preview` 与 `POST /enrollments/{enrollment_id}/commands/migrate-revision`；confirm 要求同一 preview token、impact hash、`If-Match`、原因和 capability。
- 一致性：成功迁移、`EnrollmentRevisionMigrated` Outbox 与审计在同一事务；并发版本变化只使对应 Enrollment 失败，不把批次伪装成全成功。
- 回归：`tests/unit/newcomer_training/test_enrollment_freeze.py` 覆盖发布不自动迁移；`tests/integration/newcomer_training/test_journey_learning_postgres.py` 覆盖 PostgreSQL 局部失败、幂等回放和版本变化。
