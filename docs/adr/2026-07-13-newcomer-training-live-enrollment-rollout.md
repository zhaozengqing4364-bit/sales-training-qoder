# ADR：新人训练发布同步全部在训学员

- 日期：2026-07-13
- 状态：Superseded（2026-07-16；当前代码仍可能执行本行为，目标合同禁止）
- 取代者：[`2026-07-16-enrollment-revision-freeze.md`](./2026-07-16-enrollment-revision-freeze.md)
- 取代：ADR 2026-07-12 中“Enrollment 永久固定首次 revision”的部分决策

## 决策

训练路径每次发布仍生成不可变 revision，但发布事务会把该路径全部 `active` enrollment 的 `path_revision_id` 原子切换到新 revision。Journey 读取发现 active enrollment 仍指向旧 revision 时会自修复到当前发布 revision，以覆盖发布与读取并发窗口。

ActivityAttempt 不随 enrollment 迁移。它创建时冻结的 `path_revision_id`、`activity_snapshot`、材料/试卷/评分标准版本、提交、评分和外部会话绑定永久保留。

发布操作必须记录 `rollout_scope=all_active_learners` 和同步 enrollment 数量。非 active enrollment 不被批量改写。

## 原因

当前产品仍处于原型期，业务要求管理员修改并发布后所有在训人员立即看到同一份最新训练内容。若 enrollment 永久固定，管理员必须手工迁移学员，容易产生同一团队多版本并存、内容无法及时纠正和运营解释困难。

把“当前应学内容”与“已经发生的证据”分开，可以同时满足实时同步和历史可解释性：Enrollment 是可移动的当前指针，ActivityAttempt 是不可变事实。

## 一致性与失败边界

- revision 激活、active enrollment 批量切换和发布审计处于同一数据库事务；任一步失败则整体回滚。
- 重复发布或重复读取是幂等的；已指向目标 revision 的 enrollment 不重复更新。
- 发布不自动补做新增活动，也不删除旧 attempt；Journey 按新路径重新计算待办，历史记录按 attempt 快照展示。
- 资源自身的发布版本仍遵循各资源治理契约；路径发布只切换路径 revision。

## 被拒绝方案

- 永久固定 enrollment：不符合“所有在训人员同步更新”的原型运营目标。
- 改写 attempt 到新 revision：破坏评分、答卷、录音和外部会话的证据链。
- 前端轮询并本地替换路径：绕过后端权威，无法保证事务、权限和审计。

## 后果

管理员发布前必须清楚看到影响范围；前端确认框明确提示全体在训学员同步。回滚通过把某个历史 revision 恢复为草稿并重新发布完成，同样同步全部 active enrollment，同时保留所有历史 attempt。
