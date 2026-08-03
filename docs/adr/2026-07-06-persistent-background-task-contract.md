# ADR-2026-07-06：进程内异步任务持久化契约

## Status

Superseded by
[`2026-07-16-governed-ai-and-durable-tasks.md`](2026-07-16-governed-ai-and-durable-tasks.md)。
本文只保留为历史方案记录；其中 `persistent_tasks`、6 状态、内嵌 Lease 与 SQLite 兼容目标均不再
是实现合同。当前唯一权威是 `task_runtime` 的 `durable_tasks`、7 状态和独立 Lease/Attempt。
`backend/src/common/jobs/persistent_task_contract.py` 仅保留兼容 import，不维护第二套真源。

## 背景

2026-07-03 架构审计指出，当前仍有多条用户可感知或运维关键链路依赖进程内后台任务：

- `sales_trainer` 录音提交：`sales_trainer/api.py` 通过 FastAPI `BackgroundTasks` 调用 `sales_trainer/tasks/process_audio.py`，完成转写与评分。
- 知识库文档处理：`common/knowledge/api.py` 上传/重处理后通过 `BackgroundTasks` 调用 `process_document_background()`，完成解析、切片、向量写入和状态更新。
- 报告生成：`common/db/session_lifecycle.py` 在会话结束后 `asyncio.create_task(trigger_report_generation(...))`，`evaluation/services/report_generation_trigger.py` 更新 `PracticeSession.report_status`。
- 音频归档：`common/jobs/audio_archival.py` 使用 lifespan-owned process-local scheduler 定期归档历史音频。

这些任务已经有局部状态字段和部分重试，但没有统一投递确认、跨进程恢复、租约、死信、补偿和任务查询。进程重启、滚动发布、多实例部署或 worker 崩溃时，任务可能丢失、卡在处理中或只能靠人工推断。

## 决策

采用“持久任务表优先，队列框架后置”的路线：

1. 新增数据库持久任务契约，第一阶段以 PostgreSQL/SQLite 兼容表承载任务投递、租约、重试、死信和事件审计。
2. 每个业务任务仍调用原有 domain service，不把转写、文档解析、报告生成或归档逻辑复制到通用层。
3. Worker 通过窄接口消费 `persistent_tasks`，按 `task_type` 分发到显式登记的 handler。
4. RQ/Arq 不作为当前首选实现。等任务吞吐、延迟或隔离需求超过数据库轮询能力后，再用同一 enqueue/handler 契约替换底层 broker。
5. 当前代码切片只冻结状态机、首批任务类型、表字段下限和重试分类，避免在脏工作区内一次性引入 migration、worker 和运行时接管。

## 数据结构

### `persistent_tasks`

最小字段契约由 `PERSISTENT_TASK_REQUIRED_COLUMNS` 锁定：

| 字段 | 语义 |
| --- | --- |
| `task_id` | UUID 主键 |
| `task_type` | 任务类型，首批见下文 |
| `business_key` | 面向业务的稳定键，例如 `submission:{id}`、`document:{id}`、`session:{id}` |
| `target_type` / `target_id` | 业务对象类型与对象 ID |
| `idempotency_key` | 幂等键，建议唯一约束 `(task_type, idempotency_key)` |
| `payload_json` | handler 所需最小输入，不保存密钥、Cookie、JWT、完整 prompt 或上游 raw payload |
| `status` | `queued`、`running`、`retry_wait`、`succeeded`、`dead_letter`、`cancelled` |
| `priority` | 同一 `next_run_at` 下的调度优先级 |
| `attempt_count` / `max_attempts` | 已失败尝试次数与最大尝试次数 |
| `next_run_at` | 可被 worker 获取的时间 |
| `lease_owner` / `lease_expires_at` | worker 租约，防止多实例重复执行 |
| `last_error_code` / `last_error_message` | 最近失败摘要，用户安全、运维可读 |
| `dead_letter_reason` | 死信原因：`terminal_failure`、`retry_exhausted`、`lease_expired` 等 |
| `trace_id` | 投递或最近执行 trace |
| `created_at` / `updated_at` / `started_at` / `completed_at` | 生命周期时间 |

建议索引：

- `(status, next_run_at, priority, created_at)`：worker 获取任务。
- `(task_type, business_key)`：业务对象查询任务。
- `(task_type, idempotency_key)` unique：投递幂等。
- `(lease_expires_at)` where `status='running'`：租约恢复扫描。
- `(status, updated_at)`：dead-letter 与卡住任务运维查询。

### `persistent_task_events`

建议新增 append-only 事件表：

| 字段 | 语义 |
| --- | --- |
| `event_id` | UUID 主键 |
| `task_id` | 任务 ID |
| `event_type` | `enqueued`、`claimed`、`succeeded`、`retry_scheduled`、`dead_lettered`、`cancelled`、`requeued` |
| `from_status` / `to_status` | 状态迁移 |
| `attempt_count` | 事件发生时尝试次数 |
| `actor_id` / `worker_id` | 人工或 worker 来源 |
| `error_code` / `message` | 失败摘要 |
| `trace_id` | 关联追踪 |
| `created_at` | 事件时间 |

## 状态机

状态机由 `ALLOWED_STATUS_TRANSITIONS` 锁定：

```text
queued -> running
queued -> cancelled
running -> succeeded
running -> retry_wait
running -> dead_letter
running -> cancelled
retry_wait -> queued
retry_wait -> dead_letter
retry_wait -> cancelled
```

`succeeded`、`dead_letter`、`cancelled` 是 terminal status，不允许再自动迁移。人工重投必须创建事件并显式从 `dead_letter` 复制 payload 生成新任务，或由受控管理命令将同一行 `requeued`，不能静默改状态。

租约恢复规则：

- worker 原子获取 `queued where next_run_at <= now`，写入 `running`、`lease_owner`、`lease_expires_at`、`started_at`。
- 执行时间超过 `lease_expires_at` 的 `running` 任务由 sweeper 分类为 transient：若未耗尽重试，进入 `retry_wait`；否则进入 `dead_letter`。
- handler 必须幂等，因为租约过期和 worker 崩溃后可能出现“已执行外部副作用但未写成功状态”的窗口。

## 重试与死信

默认 `TaskRetryPolicy(max_attempts=3, initial_delay_seconds=30, max_delay_seconds=900, backoff_multiplier=2)`。失败分类：

- Terminal：配置缺失、非法状态、权限/对象不存在、文件格式不可处理、Prompt 未发布等不可通过重试修复的问题，直接 `dead_letter`。
- Transient：外部服务超时、网络抖动、临时限流、数据库死锁、租约过期等可恢复问题，进入 `retry_wait`。
- Voluntary：人工取消或任务已被业务对象终止，进入 `cancelled`，不计故障。

死信必须保留 payload 摘要、错误码、trace_id、尝试次数和最近事件。普通业务页面不得展示内部 payload；管理/运维面板可以按权限查看。

## 首批接入顺序

1. `sales_trainer.audio_submission.process`  
   替换录音提交的 `BackgroundTasks` 投递。原因：已有 `uploaded/transcribing/transcribed/scoring/scored/*_failed` 业务状态和人工 retry 入口，用户可感知，幂等边界清晰。`idempotency_key = submission:{submission_id}:process:v1`。

2. `knowledge.document.process`  
   替换知识库 upload/reprocess 后的 `BackgroundTasks`。原因：已有 `pending/processing/ready/failed` 文档状态和 reprocess 入口；需要防止重启后文档永久 pending/processing。`idempotency_key = knowledge-document:{doc_id}:process:{content_hash}`。

3. `practice_report.generate`  
   替换会话结束后的 `asyncio.create_task`。原因：已有 `PracticeSession.report_status/report_error/report_retryable`，但投递本身会丢；接入时必须保持“会话结束响应不被报告生成阻塞”。`idempotency_key = report:{session_id}:{scenario_type}:v1`。

4. `audio_archive.batch`  
   替换 lifespan-owned scheduler 的实际批处理执行。原因：归档可重跑、用户直接感知低，适合最后接入；先保留一个轻量 scheduler 只负责定时 enqueue，真正归档由持久任务 worker 执行。

## 迁移计划

### Phase 0：契约冻结（本次）

- 新增 ADR、runbook、状态机 helper 和 unit tests。
- 不新增 migration，不接管现有调度。

### Phase 1：表与 repository

- Alembic 新增 `persistent_tasks`、`persistent_task_events`。
- 新增 repository/service：`enqueue_task()`、`claim_next_task()`、`mark_succeeded()`、`mark_failed()`、`requeue_dead_letter()`。
- 只跑契约测试和 repository SQLite 集成测试，不启用 worker。

### Phase 2：worker dry-run

- 新增 `PersistentTaskWorker`，支持单次 `run_once()` 和有限循环。
- 在非生产或 shadow flag 下只消费测试任务类型，验证租约、重试、死信和事件。

### Phase 3：按任务类型接入

- 按首批接入顺序逐个替换投递点。
- 每个切片先 enqueue，保留 domain service 不变。
- 每个切片新增“投递幂等、worker 成功、terminal 死信、transient 重试、对象状态不泄露”的 targeted tests。

### Phase 4：观测与管理

- 暴露运维查询：按 `task_type/status/business_key/trace_id` 查看。
- 增加 dead-letter 告警、卡住任务指标、重试耗时指标。
- 管理重投必须有权限、原因、审计事件和幂等检查。

## 回滚

- 运行时开关：按任务类型关闭 worker 消费，回到 legacy `BackgroundTasks` / `create_task` / scheduler 路径。
- 数据回滚：保留任务表作为审计，不删除业务对象状态；如必须回滚 schema，先确认无 `queued/running/retry_wait` 行。
- 接入切片回滚：仅恢复投递点，不修改 domain service。已成功的任务按业务对象幂等处理；dead-letter 行保留供复盘。
- 外部队列回滚：若未来接入 RQ/Arq，必须继续维护数据库任务行作为 source of truth 或 outbox；broker 只做执行加速，不能成为唯一状态源。

## 备选方案

### 方案 A：继续使用进程内任务

改动最小，但无法覆盖滚动发布、worker 崩溃、多实例和死信查询。本轮拒绝作为长期方案。

### 方案 B：直接引入 RQ

RQ 成熟、运维简单，但依赖 Redis。当前审计同一批整改正在处理 Redis 启动硬依赖，直接把 P1 可靠性债转移到 Redis broker 会扩大部署风险。本轮不采用为首选。

### 方案 C：直接引入 Arq

Arq 与 async Python 贴合，但同样依赖 Redis，并需要额外 worker 部署、序列化、重试和观测约定。适合后续高吞吐阶段，不适合当前最小闭环。

### 方案 D：数据库持久任务表

采用。优点是复用现有 DB、迁移可控、便于与业务对象事务/审计关联，足够覆盖当前低到中吞吐后台任务。缺点是轮询和锁竞争需要治理，后续可用同一契约迁移到 broker。

## 影响

- 后端：新增通用任务契约，后续会引入 common jobs repository/worker；业务 handler 仍在各自 domain。
- 数据：后续需要 Alembic migration；当前不改 schema。
- 权限：重投、取消、查看 payload 必须走管理/运维权限，不允许 learner 直接操作任务表。
- 可观测性：任务必须记录 trace_id、error_code、attempt_count、dead_letter_reason，并输出 Prometheus/日志指标。
- 安全：payload 不保存密钥、Authorization/Cookie/JWT、完整 prompt、完整外部请求/响应或敏感原文。
- 前端：普通用户只看到业务对象状态；运维后台可查看任务诊断。

## 后续任务与验收标准

1. 新增持久任务表 migration 与 repository。验收：SQLite/PostgreSQL 兼容测试覆盖 enqueue 幂等、claim 租约、状态迁移、事件写入。
2. 新增 worker `run_once()`。验收：不依赖外部服务的测试覆盖 success、transient retry、terminal dead-letter、lease expired recovery。
3. 接入 `sales_trainer.audio_submission.process`。验收：上传后产生持久任务；worker 成功后状态到 `scored` 或业务失败态；进程重启不丢任务；重复投递不重复评分。
4. 接入 `knowledge.document.process`。验收：上传/重处理均入队；失败进入 `failed` + dead-letter；人工 reprocess 可生成新任务。
5. 接入 `practice_report.generate`。验收：会话结束只负责提交任务；报告生成失败可查询、可重试、不会阻塞会话结束响应。
6. 接入 `audio_archive.batch`。验收：scheduler 只 enqueue；worker 执行批处理；归档失败可死信和重投。

## 回滚判定

如果任一接入切片出现重复外部副作用、任务卡住导致用户主流程不可完成、或 dead-letter 无法解释业务对象状态，应立即关闭该 `task_type` worker，恢复 legacy 投递路径，并保留任务表证据用于修复。
