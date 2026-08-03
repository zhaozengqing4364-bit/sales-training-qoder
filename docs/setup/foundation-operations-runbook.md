# 新人基础训练运营与事故 Runbook

最后更新：2026-07-18  
适用范围：Foundation 首发的 API、Durable Task、录音上传、受治理 AI、Evidence/Dossier、ReleasePlan 及权限边界  
不包含：实时客户语音对练

## 1. 事实源与关联键

- HTTP 入口指标由 `/metrics` 暴露：`http_requests_total` 与 `http_request_duration_seconds`。告警必须按归一化路由聚合，不得把对象 ID 当 label。
- Durable Task 事实源是 PostgreSQL。System Admin 使用 `GET /api/v1/admin/task-runtime/health?organization_id=<org>` 查看队列、运行、重试、死信、过期 Lease、Outbox lag、15 分钟重试率和平均处理耗时；Worker/Dispatcher 进程另查 `/live`、`/ready`、`/status`。
- AI/ASR 事实源是 `ai_invocations` 聚合读模型，按 organization、business purpose、provider、model、result classification、currency 查询调用量、失败、降级、延迟、Token 和成本。禁止从原始响应或 Prompt 正文做监控。
- Foundation 运营工作台 `/admin/newcomer-training` 聚合发布失败、题目待审、长时间任务、死信、档案待审/陈旧/投影失败、Coach 人工接手和批量分配失败。
- 关键链路使用 `request_id/trace_id → task_id → invocation_id → enrollment/attempt/submission/session/dossier/release_plan` 关联。日志只记录 opaque ID、安全错误分类、状态与耗时；不得记录录音、答案、转写全文、手机号、签名 URL、Token、密钥、Prompt 或模型原文。

## 2. 首发告警矩阵

阈值是首发默认值；变更必须走受审计配置/ADR，不得在查询或业务代码中临时硬编码。除安全事件外，告警连续命中两个窗口才 page；同 organization + task type + error classification 聚合，恢复通知只发一次。

| ID | 信号与默认阈值 | 责任角色 | 降噪与升级 |
|---|---|---|---|
| FND-API-01 | Foundation 路由 5xx 比例 `>2%/5m`，或普通 API p95 `>500ms/10m` | 平台值班 | 排除主动探针；连续 2 窗口 page，30 分钟未恢复升级后端负责人 |
| FND-TASK-01 | `dead_letter_count>0`、`expired_lease_count>0`、`outbox_lag_seconds>60`，或 retry rate `>10%/15m` | 平台值班 | 按 task type/错误分类合并；发布维护窗口只抑制预期停机，不抑制 dead-letter |
| FND-TASK-02 | 最老 queued/running 超过该类型 SLO；Audio finalize→Outcome p95 `>90s` | 训练平台值班 | 先区分容量、Provider 和数据对账；连续 2 窗口升级领域负责人 |
| FND-UPLOAD-01 | 分片确认失败 `>2%/10m`、cleanup `failed_count>0`，或 expired session 超过 30 分钟未清理 | 存储/平台值班 | 网络抖动按 organization 聚合；对象校验失败不自动重试成成功 |
| FND-AI-01 | 同 purpose Provider 失败 `>5%/15m`、平均延迟超过路由 timeout 的 80%、Schema invalid/degradation 激增 | AI 平台值班 | 按 provider/model/purpose 聚合；不以 fallback 成功掩盖正式路由失败 |
| FND-AI-02 | Token/成本超过已批准日预算 80% warning、100% page，或币种/成本缺失 | AI 平台负责人 | 预算按 organization/purpose；禁止用估算币种混合求和 |
| FND-DOSSIER-01 | `projection_failed>0`、Evidence→Dossier lag `>5m`、ready/stale 档案等待 `>24h` | 训练运营 | 技术失败 page 平台；纯等待进入运营待办，不逐学员 page |
| FND-RELEASE-01 | ReleasePlan `failed/blocked` 新增，或 active pointer 与 published plan 不一致 | 发布负责人 | 每个 plan 一条；失败旧版本仍有效时不触发全站事故，但阻塞继续扩围 |
| FND-SEC-01 | 跨组织/对象权限拒绝异常增长、签名 URL 越权、Prompt 管理越权或敏感信息扫描命中 | 安全值班 | 不等待第二窗口，立即 page；证据访问最小化并保全审计 |

## 3. 通用诊断顺序

1. 冻结范围：确认 organization、task type、PathRevision/ReleasePlan 和开始时间；不先重放、不手工改表。
2. 查用户结果位置：运营工作台、Activity Workspace、Dossier 或发布记录，确认输入/结果是否已持久化以及用户看到的恢复动作。
3. 查平台健康：API `/metrics`、Worker/Dispatcher probes、Task health、AIInvocation 聚合；用关联键定位到安全错误分类。
4. 判定责任面：容量、数据库/Lease、对象存储、Provider、Schema/Prompt、reconcile、权限或发布闭包。
5. 只执行下列受保护命令；每次命令填写 reason、Idempotency-Key、expected version/preview token（适用时），保留审计。
6. 以业务事实源验证恢复，不以“进程恢复/HTTP 200”作为完成。

## 4. 处置卡

### OPS-01 Worker 队列堆积或 Worker 重启

- 观察：`/ready`、`/status`、Task health 的 queue/running/retry/dead-letter/expired lease/outbox lag，按 task type 查看最老任务。
- 安全动作：修复数据库/Provider/容量后横向扩 Worker；Lease 到期由其他实例接管。需要隔离故障类型时，以受保护 Operator 命令暂停对应 task type；不得 `UPDATE durable_tasks`。
- 升级：过期 Lease 或 Outbox lag 持续 10 分钟升级平台负责人；同类 Provider 错误转 OPS-02。
- 恢复验证：Worker `/ready=200`；queue 持续下降；旧 task_id 到达唯一终态或明确 dead-letter；无重复业务结果。详细合同见 [`durable-task-worker-runbook.md`](durable-task-worker-runbook.md)。

### OPS-02 AI/ASR Provider 故障或成本异常

- 观察：AIInvocation 聚合中的 purpose/provider/model、失败分类、降级、p95/平均延迟、Token/成本；Task retry/dead-letter；Gold Set 与真实 Provider staging 证据。
- 安全动作：停止受影响 task type 的新领取或回滚已发布 Prompt/ModelRoutingRevision；保留输入、Invocation 和任务结果位置。服务恢复后仅 redrive dead-letter 或从业务精确阶段重试。
- 禁止：业务模块直连备用 Provider、固定分、把无效 Schema 当成功、把测试 fake 用于正式结果。
- 升级：跨 purpose 失败或预算 100% 时立即升级 AI 平台负责人和发布负责人。
- 恢复验证：受控 staging 通过；新 Invocation 精确引用批准 revision/hash；旧输入只产生一个正式 Outcome，确定性学习/人工复核仍可用。

### OPS-03 对象存储故障

- 观察：上传签名/HEAD/hash/download/write 错误、`failed_recoverable`、最老 uploading、对象存储服务状态。
- 安全动作：暂停新录音 task type 或受影响 Cohort 的新录音；保留浏览器草稿、已确认 parts、Artifact 引用和 Submission。恢复后从 validation/normalization/transcription 精确重试。
- 升级：确认跨组织 key、对象丢失或签名 URL 越权时转 OPS-09；否则 15 分钟未恢复升级存储负责人。
- 恢复验证：原 parts 可校验；同 UploadSession 不重复 complete；正式 Artifact/Transcript/Score/证据未被 cleanup 删除。

### OPS-04 上传 orphan/过期草稿清理

- 观察：expired/cancelled session、stale cleanup claim、cleanup `failed_count` 和最老未清理时间。
- 命令：`cd backend && PYTHONPATH=src .venv/bin/python scripts/cleanup_foundation_audio_uploads.py --limit 100`。
- 安全动作：允许定时任务重复运行；claim token/fencing 保护并发。不得删除 finalized session、正式 Artifact、Transcript、ScoreOutcome 或审计。
- 升级：重复两轮仍失败升级存储负责人；对象范围不清楚时停止，不扩大 prefix。
- 恢复验证：命令退出 0、failed=0、过期对象清理完成、正式结果引用仍可读取。

### OPS-05 Task 成功但 reconcile/业务投影失败

- 观察：task completed 但 Submission `reconciling`、Outcome 缺失、Dossier lag 或 Outbox lag；检查 result refs 和业务对象版本。
- 安全动作：修复事实源/Outbox 后调用领域 repair/rebuild 或受保护 redrive；reconcile 必须 effect-once。Task Runtime redrive 路径为 `POST /api/v1/admin/task-runtime/tasks/{task_id}/redrive`。
- 禁止：把 task success 直接写成业务完成、删除旧 Attempt/Outbox receipt、手工补 Outcome。
- 升级：出现重复正式 Outcome/Evidence 立即升级数据负责人。
- 恢复验证：唯一业务 Outcome、Evidence lineage 完整、Dossier 指向新快照、旧任务和修复审计均保留。

### OPS-06 Evidence/Dossier 延迟、失败或重建

- 观察：档案 `projection_failed/stale`、Evidence→Dossier lag、当前 snapshot/evidence set hash、申诉与补练状态。
- 安全动作：有 `readiness.rebuild` 且对象 scope 正确的操作者调用 `POST /api/v1/admin/newcomer-training/reviews/{dossier_id}/rebuild`；新证据到达冻结快照时先标 stale，再人工重开。
- 升级：无效/跨组织 Evidence 或重复 active decision 转数据/安全负责人；AI 摘要失败不阻塞基础档案和人工复核。
- 恢复验证：新不可变 snapshot、旧 snapshot 标 stale、Evidence 引用完整；`foundation_ready` 仍只由具备权限的人工作出。

### OPS-07 发布失败与 ReleasePlan 回滚

- 观察：发布记录 `blocked/failed`、validation report、dependency graph、impact hash、active plan/published revision 和既有 Enrollment frozen revision。
- 安全动作：失败时保持旧 active plan；修复 working dependency 后重新 preview。错误版本已发布时按 [`foundation-release-runbook.md`](foundation-release-runbook.md) 执行 rollback preview + confirm。
- 升级：active pointer 不一致、跨组织目标或部分发布立即升级发布/数据负责人。
- 恢复验证：目标稳定计划重新 active；既有 Enrollment、Attempt、录音、答案、Evidence、审计不变；新 Enrollment 使用恢复后的 revision。

### OPS-08 Prompt/模型回滚

- 观察：Gold Set 回归、真实 staging、Schema invalid、事实/幻觉、延迟和成本；定位 PromptRevision、ModelRoutingRevision 与 contract hash。
- 安全动作：停止受影响新任务，重新激活上一个已批准 revision/route，跑 deterministic Gold Set 和受控真实 Provider staging，再恢复领取。旧 Invocation 不改写。
- 升级：涉及正式评分漂移、越界引用或隐私暴露时同时通知训练治理/安全负责人。
- 恢复验证：阈值全部通过；新 Invocation 只引用回滚后批准版本；人工复核看到事实、推断和建议分层。

### OPS-09 数据泄露、权限或对象范围事件

- 观察：对象级 403/404 审计、跨组织 ID、导出/签名 URL、Prompt 管理、日志与前端 payload 敏感扫描。
- 安全动作：立即撤销 session/scope/capability，暂停相关导出、下载或 task type；保全审计、请求和对象版本，限制证据访问；必要时回滚应用/ReleasePlan。
- 禁止：在工单粘贴录音、答案、转写、Token、Secret 或原始 Prompt/Provider payload；不得删除审计来“消除暴露”。
- 升级：立即 page 安全负责人和数据责任人，按组织事故流程评估通知与删除/保留义务。
- 恢复验证：旧授权已撤销、跨组织请求持续 fail closed、合法对象仍可用、secret scan 通过、补偿和通知有审计。

### OPS-10 快速关闭 Activity Type

- 观察：确定受影响 organization、Cohort、PathRevision、task type、在途任务和用户输入位置。
- 安全动作：回滚当前 ReleasePlan/暂停新 Cohort 分配；用受保护 Operator 命令 `POST /api/v1/admin/task-runtime/task-types/{task_type}/pause` 暂停后台领取，填写 reason。允许在途任务在安全 checkpoint 完成或协作取消。
- 禁止：恢复已退役环境 flag、删除 PathRevision 活动、隐式迁移 Enrollment、重启旧 writer 或双写。
- 升级：没有稳定 ReleasePlan 或停用影响法定/安全义务时由发布负责人决策。
- 恢复验证：新任务不再创建/领取；历史输入和结果可查；恢复时使用 `/resume` 受审计命令并确认队列按原幂等键收敛。

## 5. 发布班次检查与关闭条件

发布/扩围前依次确认：migration/seed、Foundation Gold Set、受控真实 Provider staging、reset 双循环、ReleasePlan 发布/回滚、Worker/Provider 故障恢复、核心 E2E、性能 SLO、secret scan 和本 Runbook 合同测试。任何 `skipped`、`configuration_error`、真实 Provider 失败或 disposable reset 未清理都不能作为发布通过。

事故只有在以下事实同时成立时关闭：用户输入未丢失；每个业务命令只有一个正式结果；任务/Invocation/业务对象/审计可关联；权限恢复且无越界；告警回落两个窗口；运营工作台无本事故遗留高优先级项；发现项和阈值调整进入后续任务或 ADR。
