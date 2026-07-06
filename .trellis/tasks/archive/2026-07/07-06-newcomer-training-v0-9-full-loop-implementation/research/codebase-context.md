# 新人训练 V0.9 代码现状调查

## 调查结论

当前仓库已经有新人训练路径、训练记录、AI Coach、商务礼仪测验、录音提交、实时对练准入、操作日志和后台训练记录管理等底座。V0.9 的主要缺口不是重新发明训练流程，而是在 `sales_trainer` 域内补一个产品化聚合层：

- 单人训练达标档案：把路径进度、提交证据、AI/规则评分、能力项、重练和复核记录汇总成可判断的 ViewModel。
- 培训负责人达标验收工作台：按待复核、未达标、需重练、已达标、配置异常分组。
- 复核动作：确认达标、要求重练、标记需人工跟进，必须由后端校验权限并写审计。
- 准入说明：真实语音对练只作为后续阶段入口，训练未达标、待人工复核、配置异常或 provider 未就绪时锁定并解释原因。

## 已有后端能力

- `backend/src/sales_trainer/services/training_journey_service.py`
  - 已以 active path revision 为唯一真源生成学员旅程。
  - 已聚合 audio、quiz、business etiquette quiz、AI Coach session、realtime outcome、regrade outcome。
  - 已有状态语义：`not_started`、`in_progress`、`waiting_upload`、`processing`、`scored`、`passed`、`failed`、`needs_remediation`、`manual_review`、`disabled`、`archived`、`error_terminal`、`error_transient`。
  - 配置缺失时 fail-closed，例如 active revision 缺失返回 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`。

- `backend/src/sales_trainer/services/training_record_service.py`
  - 已统一训练记录查询，覆盖 audio、quiz、AI Coach、business etiquette quiz、realtime。
  - 可作为档案证据链来源。

- `backend/src/sales_trainer/services/operation_log_service.py`
  - 已有 `OperationLogService.record(...)` 和 `list_logs(...)`。
  - 适合 V0.9 先承载复核动作审计，避免为第一片闭环立即引入迁移。

- `backend/src/sales_trainer/models.py`
  - 已有 `SalesTrainerAudioSubmission`、`SalesTrainerQuizAttempt`、`SalesTrainerBusinessEtiquetteQuizAttempt`、`SalesTrainerAiCoachSession`、`SalesTrainerOperationLog`。
  - 已保留 material snapshot、score scheme snapshot、task brief snapshot、capability scores、weak capability keys 等证据需要的基础字段。

- `backend/src/supervisor/`
  - 已有 `SupervisorReview`、`RetrainingTask`、`ReadinessStatus`、`CertificationReviewQueue` 等概念。
  - 这些是 supervisor 域能力，不应直接硬套到 sales_trainer 新人路径，除非后续确认字段与权限边界一致。

## 已有前端能力

- `web/src/app/(dashboard)/sales-trainer/page.tsx`
  - 新人端已读取 Journey，并以 active revision 为唯一真源。
  - 已显示模块状态、下一步动作和 realtime roleplay 启动/锁定。

- `web/src/app/admin/sales-trainer/`
  - 已有模块总览、训练记录、分析、路径配置等页面。
  - 缺少达标验收工作台和单人训练达标档案页。

- `web/src/lib/api/domains/sales-trainer.ts`
  - 已有 learner/admin sales trainer API client。
  - 新增 dossier/workbench API 应放在 admin domain 下，保持 snake_case 契约。

## 实现约束

- `sales_trainer/api.py` 保持 thin route，业务放在 `services/*`。
- 权限继续使用 `permissions.py` 和既有 `_require_records_viewer`、团队 scope 校验。
- 新增 API 必须更新 `docs/api-contract/sales-trainer.md`。
- 前端普通用户界面不得展示 raw JSON、trace、Prompt、模型细节；档案只展示业务化证据和快照摘要。
- 配置异常必须显式进入配置异常分组，不能伪装成学员未完成。

