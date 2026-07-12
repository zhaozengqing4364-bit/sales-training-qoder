# 技术设计索引

本任务不复制设计内容，使用以下两份已批准权威：

- `docs/superpowers/specs/2026-07-12-newcomer-training-activity-orchestration-design.md`
- `docs/superpowers/plans/2026-07-12-newcomer-training-activity-orchestration.md`

物理存储复用 `SalesTrainerAssetRevision` / `SalesTrainerAssetActiveRevision` 作为路径 revision 与 active pointer，新增 enrollment 和统一 activity attempt 表，避免第二套发布指针。
