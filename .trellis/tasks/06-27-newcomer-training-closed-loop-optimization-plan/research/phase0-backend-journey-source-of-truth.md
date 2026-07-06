# Phase 0 子代理 A：后端闭环架构 / 真源审计报告

> 日期：2026-06-27
>
> 范围：active path revision、TrainingJourney/状态机、AI Coach、realtime 接入边界、训练记录聚合。
>
> 方法：子代理只读分析，优先使用 CodeGraph CLI；本文件由主 Agent 根据子代理最终报告落盘，未修改业务代码。

## 结论

后端已有新人训练闭环的关键基础：active path revision、路径发布/回滚、音频/考卷/商务礼仪/AI Coach 的 revision lineage、训练记录聚合、RuntimeGate 和 sales_bot StepFun 边界都已经存在。

未闭环的根因是：`sales_trainer` 仍同时支持 active revision 与 legacy `unit_backfill`，还没有 TrainingJourney 聚合/状态机真源，realtime 仍按契约停留在 placeholder，AI Coach 的发布前依赖校验也未完全前移。

## 关键代码事实

### 1. 路径配置已有 active revision，但 learner 仍有 fallback 入口

- `backend/src/sales_trainer/services/path_config_service.py:59`：`SalesTrainerPathConfigService.get_config()` 优先读取 active revision。
- `backend/src/sales_trainer/services/path_config_service.py:68`：无 active 时返回 `source="unit_backfill"`。
- `backend/src/sales_trainer/services/path_config_service.py:74`：无 active 时 `legacy_snapshot_only=True`。
- `backend/src/sales_trainer/services/path_service.py:30`：`SalesTrainerPathService.list_paths_for_user()` 先读 active projection。
- `backend/src/sales_trainer/services/path_service.py:37`：active projection 不存在时仍调用 `_load_published_path_units()` 拼旧路径。

结论：`active path revision 唯一真源` 尚未闭环。当前已有诊断字段基础，但 learner 正式路径仍会 fallback。

### 2. TrainingJourney 尚未成为后端主语

- 子代理在 `backend/src/sales_trainer`、`backend/src/training_runtime`、`backend/src/common` 范围内未找到 `TrainingJourney` / `training_journey` 实体或服务。
- `backend/src/sales_trainer/services/training_record_service.py:38`、`:105`、`:121`：现有聚合由 `TrainingRecordService` union 音频、普通 quiz、AI Coach session。
- `backend/src/sales_trainer/models.py:324`、`backend/src/sales_trainer/services/business_etiquette_quiz_service.py:205`：商务礼仪小测已有独立表和 snapshot，但没有进入统一 TrainingJourney 状态机。

结论：当前是训练记录 read model，不是完整 journey aggregate。状态仍散在各模块。

### 3. 不强制顺序解锁的新决策尚未落到后端状态策略

- `backend/src/sales_trainer/services/path_projection_payloads.py:45`、`:52`、`:54`：projection 仍读取 `unlock_after_unit_ids`，缺前置完成时把 level 改成 `locked`。

结论：这不是单点 bug，而是产品决策变更未反映到后端状态机。后续需要集中状态策略返回“未开放原因/下一步”，而不是硬锁顺序。

### 4. AI Coach 已有 lineage 和训练记录基础，但配置治理仍有 fail-open

- `backend/src/sales_trainer/services/ai_coach_chat_session_creator.py:45`、`:55`、`:59`、`:62`、`:81`：Chat session 创建会冻结 `path_revision_id`、`path_revision_no`、`path_config_snapshot`、`config_snapshot` 并写操作日志。
- `backend/src/sales_trainer/services/training_record_service.py:121`、`:322`：训练记录已把 `ai_coach_session` 纳入 record window。
- `backend/src/sales_trainer/ai_coach_admin_api.py:67`、`:77`、`:80`：admin 读取 AI Coach 配置时，path payload 解析异常会 `pass`，随后返回默认 `AiCoachConfig()`。

结论：AI Coach 已有进入闭环的材料，但坏配置 GET fail-open 与发布前 prompt 依赖校验不足仍是 P1。

### 5. realtime 边界清晰，但尚未接入新人闭环

- `backend/src/sales_trainer/AGENTS.md:54`、`:56`：`sales_trainer` 禁止从本模块 import `sales_bot/`、`training_runtime/` 或创建/修改 realtime session。
- `docs/api-contract/sales-trainer.md:13`、`:15`：API 契约仍规定 realtime 当前只允许 placeholder，不创建 `PracticeSession`、不调用 `sales_bot`。
- `backend/src/training_runtime/plugins.py:99`、`:123`：runtime 侧已有 sales plugin 边界。
- `backend/src/common/services/runtime_gate.py:576`、`:593`、`:615`：RuntimeGate admission 基础存在。
- `backend/src/sales_bot/websocket/router.py:193`、`:196`、`:291`：sales_bot StepFun runtime 入口存在。

结论：realtime 必须先补 ADR/API 契约和 runtime binding 投影，不能在 `sales_trainer` 内直接创建 runtime 会话。

## 根因

根因不是缺少单个接口，而是“闭环真源”尚未升级：新人训练仍由多个局部真源拼接，active path revision 只是路径配置真源，训练完成状态仍散在 audio、quiz、business etiquette、AI Coach、realtime 各自表与 projection 中。只要 TrainingJourney 聚合和状态策略没有成为后端权威，前端看板、权限矩阵、realtime 接入、AI Coach 必过、历史快照都会继续靠局部补丁对齐。

## 推荐阶段任务

### A1. 冻结契约与禁用 learner fallback

- 风险：P0。
- 允许修改：`docs/api-contract/sales-trainer.md`、ADR、`SalesTrainerPathService` learner projection、相关 tests。
- 禁止范围：不改 `sales_bot/`，不创建 realtime session，不提交 migration。
- 成功标准：无 active revision 时 learner 返回 typed diagnostic，不再生成正式训练路径；admin 仍可只读 backfill 迁移。
- 验证命令：
  - `cd backend && pytest tests/integration/test_newcomer_training_path_config_api.py tests/unit/test_newcomer_training_path_config_revision.py`
- 回滚策略：恢复 `SalesTrainerPathService` fallback 分支，但必须标记为 symptom fix，不能作为最终闭环。

### A2. TrainingJourney 投影服务先行

- 风险：P1。
- 建议：先不建表，新增只读 aggregate service 聚合 path revision、audio、paper、business etiquette、AI Coach、realtime placeholder。
- 成功标准：后端返回统一 `ModuleProgress`、`ModuleOutcome`、`TrainingStage`，前端不再自行推断 locked/completed/failed。
- 验证命令：
  - 新增 journey contract/unit tests，覆盖 legacy lineage 与 active revision lineage。
- 回滚策略：read model 可按 API 入口关闭，不改写原始记录。

### A3. AI Coach 发布前依赖校验

- 风险：P1。
- 允许修改：`SalesTrainerPathConfigService._validate_publish_payload()` 或 AI Coach 专用 validator，`ai_coach_admin_api`。
- 成功标准：prompt/scoring prompt 存在、已发布、用途匹配；坏配置在保存/发布或 admin get 时 typed error，不静默默认。
- 验证命令：
  - `cd backend && pytest tests/unit/test_sales_trainer_ai_coach_chat.py tests/unit/test_sales_trainer_ai_coach*.py`
- 回滚策略：保留旧 session 只读兼容；新配置入口 fail-closed。

### A4. realtime 接入 ADR + runtime binding

- 风险：P1，若绕过契约则为 P0 条件风险。
- 允许修改：ADR、API 契约、`sales_trainer` 薄绑定 DTO、projection/API。
- 禁止范围：不直接改 `sales_bot` 业务实现，不从 `sales_trainer` 直接创建 runtime 会话。
- 成功标准：path module 绑定 runtime config，创建 session 仍走现有 practice/runtime 权威，结果回写 Journey projection。
- 验证命令：
  - `cd backend && pytest tests/unit/test_sales_trainer_realtime_binding*.py tests/contract/`
- 回滚策略：module disabled 或 active revision rollback 关闭 realtime 入口。

## 取舍

| 方案 | 优点 | 缺点 |
|---|---|---|
| 先做只读 TrainingJourney projection | 无 migration，快速统一状态语义 | 不能完全解决写入审计和事务一致性 |
| 直接新增 TrainingJourney 表 | 长期更稳，审计/回滚/状态机更清楚 | 需要 migration、backfill、兼容历史数据，风险更高 |
| realtime 直接复用 PracticeSession | 复用 RuntimeGate 和 sales_bot 成熟链路 | 容易绕过 sales_trainer path revision 治理 |
| sales_trainer 内建 realtime runtime | 表面闭环统一 | 违反模块边界，重复 runtime 能力 |

## 暂停条件

- 学员等级来源未定：用户表字段、组织分层、后台配置，还是训练表现计算。
- TrainingJourney 是否允许先做只读 projection，还是必须第一阶段建表。
- realtime 接入方式未定：`training_runtime` 外部 binding 还是 `sales_trainer` 薄投影。
- AI Coach 必过标准未定：完成一次 session，还是达到 mastery threshold。
- 是否允许立即废弃 learner fallback，还是需要迁移窗口和运营提示期。
