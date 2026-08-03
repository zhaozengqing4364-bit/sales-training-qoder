# 新人销售基础训练公开事件合同

> 状态：Accepted target contract（schema v1）；切片 0 不创建 Outbox 表或消费者。

## 统一信封

所有公开事件均包含：`event_id`、`event_type`、`schema_version`、`occurred_at`、`organization_id`、`actor_id`（系统可空）、`trace_id`、`correlation_id`、`causation_id`、`idempotency_key`、`aggregate_type`、`aggregate_id`、`aggregate_version`、`payload`。

- Producer 在业务写事务内追加同库 Outbox；Redis/进程队列只可唤醒，不是事实权威。
- 投递语义是至少一次。消费者以 `(consumer_name, event_id)` 唯一去重；不得宣称 Exactly Once。
- Replay 只重建声明为可重放的投影。通知、外部调用等副作用默认 `replay_policy=skip_side_effects`。
- payload 不含音频、完整转写、题目答案、Prompt 正文、Raw AI Response、密钥或大 JSON；敏感对象只放授权后可解析的 ID/版本引用。
- 兼容新增字段；删除、重命名或改变语义必须升 `schema_version` 并提供双版本消费者的有界退役期。

## v1 事件目录

| 事件 | Producer / 事务边界 | Consumers | 幂等键 | Replay | v1 payload |
|---|---|---|---|---|---|
| `ActivityOutcomeRecorded` | 活动所有者写 Outcome，并由 `newcomer_training` 在同事务附加 Attempt 引用与 Outbox | Journey、competency evidence intake、通知 | `attempt_id:outcome_version` | 可重建 Journey/Evidence；跳过通知 | `attempt_id`、`enrollment_id`、`activity_id`、`activity_type`、`outcome_id`、`outcome_version`、`assessment_result`、`evidence_refs[]`、`degraded` |
| `CompetencyEvidenceUpdated` | `competency_evidence` 追加证据/有效性记录与 Outbox 同事务 | readiness projection、admin queue | `evidence_id:validity_version` | 可重建 Dossier | `learner_id`、`competency_id`、`evidence_id`、`validity_version`、`source_type`、`source_ref`、`confidence_band`、`effective_at` |
| `JourneyProgressChanged` | `newcomer_training` 更新 Attempt/Gate 投影与 Outbox 同事务 | learner/admin Journey projection、通知 | `enrollment_id:journey_version` | 可重建投影；跳过重复通知 | `enrollment_id`、`path_revision_id`、`journey_version`、`current_stage_id`、`primary_activity_id`、`progress_state` |
| `ReadinessReviewRequested` | `readiness` 固化 DossierSnapshot、创建 Review Queue item 与 Outbox 同事务 | manager queue、通知 | `dossier_id:snapshot_version` | 可重建队列；跳过通知 | `dossier_id`、`learner_id`、`snapshot_version`、`risk_band`、`missing_evidence_codes[]`、`assigned_team_id` |
| `ReviewDecisionRecorded` | `readiness` 追加不可变 ReviewDecision、更新 dossier pointer 与 Outbox 同事务 | Journey result projection、notifications、audit projection | `decision_id` | 可重建正式结论投影 | `decision_id`、`dossier_id`、`learner_id`、`decision_type`、`decision_version`、`reason_code`、`effective_at` |
| `RetrainingAssigned` | `readiness` 创建 RetrainingAssignment 与 Outbox 同事务 | newcomer journey、notifications、manager queue | `assignment_id` | 可重建任务；跳过通知 | `assignment_id`、`learner_id`、`competency_ids[]`、`source_evidence_refs[]`、`target_activity_refs[]`、`due_at` |
| `EnrollmentRevisionMigrated` | `newcomer_training` 显式迁移 Enrollment revision、审计与 Outbox 同事务 | Journey、readiness stale marker、admin impact projection | `enrollment_id:migration_version` | 可重建 revision 历史/投影 | `enrollment_id`、`path_id`、`from_revision_id`、`to_revision_id`、`migration_version`、`impact_hash`、`reason_code` |

## 消费失败

- 可重试失败保持 Outbox/Delivery 可见并指数退避；超过上限进入死信，不修改业务事实。
- schema 不支持、组织范围缺失或引用越权属于非重试失败，记录安全事件并停止该消费者。
- 某消费者失败不回滚已提交的 Producer 业务事务；用户可见投影需显示 stale/degraded，而不是伪装最新。
