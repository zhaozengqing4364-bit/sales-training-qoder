# 新人基础训练干净切换清单

> 状态：Foundation 首发 Clean Cut 已完成（2026-07-18）。下表保留切片 0 的迁移设计与删除顺序作为审计历史；实际关闭证据由运行时 OpenAPI、Architecture Guard、`backend/tests/integration/newcomer_training/test_foundation_release_migration.py`、`.sisyphus/evidence/foundation-reset-rehearsal.json` 和最终质量门禁提供。生产历史数据破坏性迁移不在父任务范围；缺完整 lineage 的开发旧数据通过受保护 launch reset 重建，保留项均只读且不得恢复旧 writer。

## 规则

- 每个切片先建立并验证新写权威，再在同一切片删除对应旧写入；禁止长期双写/双读。
- 旧数据先运行只读 inventory 与验证查询；空库和旧开发库必须给出确定结果。
- 开发环境清理只能复用 `launch_reset inspect -> dry-run -> apply -> verify`，不得临时 `drop_all` 或手工 SQL。
- 下表中以“计划”命名的 artifact 是切片 0 的历史候选名；最终实现以当前仓库测试、运行时 OpenAPI、Guard 和上述发布证据为准，不得据此假定不存在的脚本已经交付。

## 数据与写权威

| Legacy 项 | 新权威 | 保留/转换 | 计划脚本与验证 | 删除时点 / 回滚 |
|---|---|---|---|---|
| `sales_trainer_asset_revisions` 中 `resource_type=newcomer_training_path_orchestration` 的 v1 payload | `newcomer_training.Path/PathRevision` | 开发数据不原地保留；只读 JSON/hash 导出作审计，随后标准包重 seed | 计划 `backend/scripts/migrations/foundation_path_inventory.py`；`backend/tests/migration/test_foundation_path_clean_cut.py` 在空库与旧库断言 target payload 的 Phase/Module/Realtime 命中数均为 0 | Slice 2 新 Path/Journey E2E 通过后停 `TrainingPathRevisionService` 旧写；回滚只允许受保护 reset 到上一 baseline + 旧 seed |
| `newcomer_training_enrollments` 与 `EnrollmentRepository.get_or_create()`、`TrainingPathRevisionService.sync_active_path_revision()` 的自动移动 | 新冻结 Enrollment | 旧开发 Enrollment 清理重建；不伪造历史迁移事件 | 计划 `backend/tests/migration/test_foundation_enrollment_freeze.py`：发布前后 active Enrollment 的 revision id/hash 不变；只有显式命令生成一条审计与 `EnrollmentRevisionMigrated` | Slice 2 删除上述 sync/self-heal 调用；回滚上一部署前先写保护，禁止旧代码改动新 Enrollment |
| `newcomer_training_activity_attempts` v1 | 新通用 Attempt + immutable ActivityOutcome ref | 开发数据默认重建；需要留存的行只导出为 Legacy 审计，不写入正式 Outcome | 计划 `backend/scripts/migrations/foundation_attempt_inventory.py` 与 `backend/tests/migration/test_foundation_attempt_clean_cut.py`，断言 `(enrollment,activity,attempt_no)` 唯一、冻结 revision/hash 完整、Outcome ref 不悬空 | 对应活动切片建立单写后删除旧 Handler 写入；回滚只读导出，不开启双写 |
| `question_items` 及当前直接 create/update/publish/archive 路径 | Candidate -> QuestionRevision -> ReleasePlan | 已审核示例内容以 source revision/hash 重新导入并重新审核；未审核候选在开发 reset 中删除 | 计划 `backend/scripts/migrations/foundation_question_inventory.py` 与 `backend/tests/migration/test_foundation_question_lineage.py`，断言 candidate→revision lineage、红线确认和 ReleasePlan 闭包 | Slice 2 建立新 QuestionRevision writer 后删除旧 question publish writer；回滚从导出重建 working revision，不回写旧表 |
| `sales_trainer_audio_transcripts` / `sales_trainer_audio_score_results` 单行结果 | `audio_assessment` 的 TranscriptRevision / ScoreOutcomeVersion | 当前处于开发阶段，按已确认 clean reset 决策不把缺完整 lineage 的旧行转换成正式证据；旧表仅作只读诊断，标准训练包重建新数据 | `backend/tests/migrations/test_audio_assessment_migration.py` 证明目标表/约束和 Attempt outcome 扩展可建；Slice 8 inventory gate 证明无旧写消费者和正式数据误导入 | Slice 3 新 Revision/Version 单写已建立；回滚仅开放旧表只读诊断，不覆盖新版本或恢复旧 writer |
| `sales_trainer_ai_coach_sessions`、`sales_trainer_ai_coach_turns`，写入者 `AiCoachSessionService`，模型调用 `AiCoachScoringService(LLMService)` | 结构化 AiCoachSession/TrainingCard/RemediationCycle + AIInvocation | 旧会话只读审计或开发 reset；`raw_model_output` 不转换为正式证据 | 计划 `backend/scripts/migrations/foundation_ai_coach_inventory.py` 与 `backend/tests/migration/test_foundation_ai_coach_clean_cut.py`，断言旧行不进入 CompetencyEvidence、目标 card schema 封闭、Prompt/model lineage 完整 | Slice 4 建立新 writer 后删除旧 session/turn 写入；回滚只读旧会话 |
| `ReadinessDossierService` 从 Attempt/Audio 等表即时投影，复核写入 `sales_trainer_operation_logs` 的 `newcomer_activity.readiness_reviewed` action | CompetencyEvidence Store + versioned Dossier + immutable ReviewDecision | 只转换有 organization、Enrollment、source revision/hash 的 evidence refs；旧 operation log 保留审计但不冒充 ReviewDecision | 计划 `backend/scripts/migrations/foundation_readiness_inventory.py` 与 `backend/tests/migration/test_foundation_readiness_clean_cut.py`，断言 evidence lineage、Dossier 重建一致、Decision append-only/supersede history | Slice 5 建立 evidence/dossier/decision 单写，Slice 6 切管理入口；回滚只读旧投影，不把 log 写回新 Decision |

## 路由、Facade、种子与执行器

| Legacy 项 | 新权威 / 转换 | 删除时点 | 验证与恢复 |
|---|---|---|---|
| [`newcomer-training-v2.md` §5](../api-contract/newcomer-training-v2.md#5-旧-api-退役点) 列出的 current Path、Module、subtype、paper/unit/regrade、journey/readiness、audio/training-record routes | v2 paths/releases/resources/generic activity/task/review commands | 各行指定 Slice；Slice 8 收口 | `backend/tests/contract/test_newcomer_v2_openapi_retirement.py` 对 §5 exact route set 做 deletion allowlist；`web/tests/contract/newcomer-v2-importer-retirement.test.ts` 证明无消费者；回滚部署上一版本但写保护新表 |
| `POST /api/v1/newcomer-training/activities/{activity_id}/realtime/sessions`、`RealtimeRoleplayActivityHandler`、`realtime-roleplay-renderer.tsx`、seed `realtime_roleplay` binding | 首发无替代；Realtime 产品代码留在 `sales_bot`/practice 原域 | Slice 2 从新人 Path/导航/seed/权限/OpenAPI 移除 | `test_foundation_activity_union.py`、前端 registry contract 与 seed verify 均断言 exactly five 且无 realtime |
| `backend/scripts/seed_newcomer_training_path.py` v1 | Slice 2 标准 Foundation 包 seed | Slice 2，最终 Slice 8 dead-code gate | seed 两次幂等 + verify-only |
| `LessonActivityHandler`、`QuizActivityHandler`、`AudioAssessmentActivityHandler`、`AiCoachActivityHandler`、`AssignmentActivityHandler`、`RealtimeRoleplayActivityHandler` 及 `orchestration/learner_api.py` concrete imports | 五个目标 ActivityRuntime Adapter + application root 显式注册；Realtime 不注册进 foundation union | Lesson/Quiz Slice 2，Audio/Assignment Slice 3，Coach Slice 4，Slice 8 收口 | `test_foundation_activity_registry.py` 断言 exactly five、无 dynamic import/concrete delivery import；五类 E2E |
| `web/src/lib/api/client.ts`/`types.ts` 巨型兼容面及 `client-domains.ts` | newcomer domain Client/DTO/Presenter，外层 `api` 仍是 transport seam | Slice 7 渐进迁移，Slice 8 删除无消费者旧导出 | importer inventory、TypeScript、Vitest、build |
| `/training`、`/learning-path`、自由 practice 与新人入口竞争 | `/newcomer-training` 单一新人入口；Realtime practice 仍属独立产品 | Slice 7/8 | 路由/导航 E2E；不以永久 redirect 代替删除 |

## 直接 AI/Provider 与后台任务

| 当前事实 | 目标 | Owner / 切片 | 退出验证 |
|---|---|---|---|
| `curriculum_practice/services/question_generation.py` 直接取 LLMService | `AIInvocationPort` + DurableTask | learning / Slice 2（依赖 Slice 1） | Guard 无业务直连；Fake Provider contract |
| `sales_trainer/services/audio_submission_service.py` 请求内处理且构造 `DeucateScoringService` | `audio_assessment.pipeline.process` 分阶段 Task + AI Invocation | audio / Slice 3（已切换） | finalize 只排队；故障注入覆盖重试；Outcome reconcile 幂等 |
| `transcription_service.py` 直接构造 Paraformer Provider | 业务只调用 AIInvocation；文件 ASR 位于组合根受治理 Provider Adapter | audio/ai_platform / Slice 3（已切换） | Provider fake/Schema 合同；业务模块无 Provider SDK import |
| `sales_trainer/services/ai_coach_session_service.py::submit_activity_turn` 调用 `AiCoachScoringService.score_turn()`，后者直接持有 `LLMService` | AIInvocationPort + 输入保存优先的 DurableTask | ai_coach / Slice 4 | 集成测试断言 learner response 先提交、Provider 失败可恢复、无固定分、schema invalid 进入显式失败/人工状态 |
| `common/jobs/persistent_task_contract.py` 仅合同无 DB/Worker | `task_runtime` 真源 | platform / Slice 1 | lease/retry/cancel/dead-letter/outbox 集成测试 |
| `sales_trainer/api.py::_schedule_audio_processing` 及 `upload_audio_file`/`register_audio_submission` 的 FastAPI `BackgroundTasks` | audio TaskRuntime pipeline | Slice 3（旧写函数/任务模块已删除） | 持久任务恢复与同业务键单 Outcome 测试；旧录音提交写路由退役合同 |
| `common/knowledge/api.py::{upload_document,reprocess_document}` 的 FastAPI `BackgroundTasks` 与 `common/knowledge/service.py` 的 `asyncio.create_task` | knowledge ingestion TaskRuntime | knowledge owner；基础训练消费前完成，Slice 8 检查 | 进程重启、重复领取、失败重试/死信；foundation SourceDocument 不依赖进程内 future |
| `common/jobs/audio_archival.py::AudioArchivalScheduler` 的 process-local `asyncio.create_task` | 有 lease 的 retention DurableTask 或部署级受治理 scheduler adapter | storage/task_runtime owner；Slice 8 | 两副本不重复删除、lease 过期可重领、留存审计完整；旧 process-local scheduler 未挂载 |

## 统一验收查询语义

每个切片的 migration test 必须证明：新表空库可建；旧开发库要么按已声明转换成功，要么在任何写前以稳定错误拒绝；新旧写权威不同时活跃；数量、唯一约束、revision/hash/organization 引用一致；回滚不会覆盖新证据。不存在“未知数据以后再看”的分支。
