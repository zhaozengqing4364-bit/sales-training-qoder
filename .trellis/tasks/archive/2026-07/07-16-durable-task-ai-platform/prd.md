# 切片 1：持久化任务运行时与 AI 平台

## Goal

建立所有长耗时训练能力共用的持久化任务运行时和受治理 AI 调用平台，让录音转写、录音评分、短答评分、AI Coach、题目生成、重评和后台发布检查都具备可恢复、可追踪、可取消、可重试、可审计和可降级的基础能力。

本切片只提供平台能力，不承载具体训练业务判断。

## Dependencies

- 必须先完成切片 0 的契约冻结。
- 必须复用切片 0 定义的状态、错误、事件、权限和 Outbox 契约。

## Current Gap

- 当前部分长任务依赖 FastAPI `BackgroundTasks`、进程内异步任务或请求内同步执行。
- 进程退出、发布重启、网络断开后，任务状态和业务结果可能不一致。
- AI 调用散落在业务 Service，Prompt、模型、超时、重试、预算和日志口径不完全统一。
- 前端缺乏稳定的任务状态、部分成功、取消、恢复和结果位置契约。

## Requirements

### R1. Durable Task Domain

- 建立 `DurableTask`、`TaskAttempt`、`TaskLease`、`TaskProgress`、`TaskResultRef` 领域模型。
- `DurableTask` 生命周期严格复用切片 0 和父架构冻结的状态：
  - `queued`；
  - `running`；
  - `retry_wait`；
  - `cancel_requested`；
  - `cancelled`；
  - `succeeded`；
  - `dead_letter`。
- 不得再引入同义生命周期状态：`leased` 属于 `TaskLease/TaskAttempt` 元数据；`waiting_retry` 统一为 `retry_wait`；`cancelling` 统一为 `cancel_requested`；可重试 `failed` 进入 `retry_wait`，不可重试或耗尽进入 `dead_letter`。
- `waiting_input` 与 `partially_succeeded` 是有类型 `TaskResultRef`/业务对象结果分类，不是第二套 Task 生命周期状态；Task 在平台工作安全完成后进入 `succeeded` 并引用持久业务结果位置，正式业务状态仍由业务模块拥有。
- 状态转移由集中式状态机控制。
- 每个任务保存 task type、schema version、tenant/org scope、actor、resource reference、idempotency key、priority、deadline、attempt limit、next run time 和 correlation id。

### R2. PostgreSQL Truth And Worker Leasing

- PostgreSQL 是任务和结果真源。
- Worker 使用可恢复 Lease 领取任务；Lease 有超时、续租和抢占恢复。
- 使用 `FOR UPDATE SKIP LOCKED` 或仓库认可的等价机制避免重复领取。
- Worker 崩溃后任务可由其他 Worker 在 Lease 过期后恢复。
- Redis 仅用于唤醒、通知和缓存，不决定最终状态。

### R3. Idempotency And Exactly-Once Effects

- 任务创建支持显式 `idempotency_key`。
- 相同组织、任务类型、业务对象和幂等键只能产生一个逻辑任务。
- 外部调用、业务写入、Outbox 发布和重试必须设计幂等。
- 不承诺传输层 exactly-once；通过幂等消费和唯一约束实现业务效果一次。
- 重放任务不能重复扣预算、重复创建正式 Question、重复写 ActivityOutcome 或重复通知。

### R4. Retry, Timeout, Cancellation And Compensation

- 任务类型声明 timeout、max attempts、backoff、retryable error codes 和 terminal error codes。
- 区分 Provider 临时失败、输入错误、权限失败、业务冲突和系统缺陷。
- 支持用户或管理员发起取消；Worker 在安全点响应取消。
- 已产生部分结果时，Task 通过 `TaskResultRef.result_kind=partial_success` 返回已保存、未完成和可重试项；平台工作安全结束后 Task 为 `succeeded`，不得用 Task 状态替代业务结果状态。
- 对无法原子回滚的外部效果定义补偿或人工处理队列。

### R5. Task Registry

- 使用显式 Task Registry 注册 task type、input schema、handler、result schema、policy 和 metrics。
- 禁止动态字符串 import Handler。
- Handler 只依赖稳定 Port；不得直接越过模块读取其他域 ORM。
- 未注册 task type 必须 fail closed 并产生可定位错误。

### R6. Outbox And Domain Event Delivery

- 任务状态和业务事件使用同事务写入 Outbox。
- Outbox Dispatcher 支持重试、幂等消费、失败隔离和可观测 lag。
- 消费者记录 event id / handler version，避免重复副作用。
- 事件 payload 不携带敏感原文、完整录音、Token 或模型密钥。

### R7. Task API And Projection

- 任务创建通过业务 Application Command 调用 `TaskRuntimePort.enqueue()`；不得向学员或普通调用者开放可任意指定 `task_type`、Handler 或 payload 的通用 HTTP 创建接口。
- 首发学员契约只提供 `/api/v1/newcomer-training/tasks/{task_id}` 查询与 `request-cancel`，由后续业务切片挂接并做业务对象授权；Slice 1 提供可复用 Query/Command 应用接口和受 System Admin capability、组织/对象范围保护的运维列表、详情、暂停/恢复 task type 与 dead-letter redrive API。
- 学员只能查询自己有权访问的任务；管理员按 capability 和组织范围查询。
- Task ViewModel 提供：
  - 用户可理解状态；
  - 当前步骤；
  - 进度与估计区间（无法可靠估计时不伪造百分比）；
  - 可取消/可重试能力；
  - 部分成功说明；
  - 结果对象位置；
  - 最近错误及下一步；
  - 最后更新时间和 stale 提示。
- 重要结果必须落在业务对象中，Toast 或任务日志不能成为唯一记录。

### R8. Worker Operations

- API 和 Worker 可独立启动、健康检查和扩缩容。
- 提供 ready/liveness、队列深度、Lease 超时、重试率、死信数和处理时延指标。
- 支持按 task type 暂停、限流和恢复。
- 支持优雅停机：停止领取新任务，续租或释放在途任务，避免不明确终止。
- 提供开发环境一键启动和 deterministic fake worker。

### R9. AI Invocation Port

- 业务模块统一通过 `AIInvocationPort` 或等价应用服务调用模型。
- 输入契约包含 prompt revision、contract hash、model policy、tenant、actor、purpose、data classification、timeout 和 budget scope。
- 输出契约包含 provider/model、usage、latency、finish reason、structured payload、validation result、evidence refs 和 error classification。
- 禁止业务模块直接持有 Provider SDK Client。

### R10. Prompt Compilation And Versioning

- Prompt 由已发布 PromptTemplateRevision 编译。
- 记录模板、输入 schema、输出 schema、contract hash、模型策略和运行参数快照。
- 缺失模板、未发布修订、schema 不兼容或非法变量必须 fail closed。
- Prompt 预览和正式调用使用同一编译器。
- Prompt 原文和业务输入按数据分级做脱敏、保留期和访问控制。

### R11. Model Routing, Budget And Rate Limit

- 模型路由基于 use case policy，不由页面或业务函数写死。
- 配置默认模型、fallback、temperature、token limit、timeout、重试和 circuit breaker。
- 支持组织级、用户级、use case 级预算和 rate limit。
- 失败回退不得改变输出契约或静默降低正式结论可信度。
- 超预算或限流返回明确可恢复状态，不伪装成模型错误。

### R12. Structured Output And Safety

- 所有业务 AI 用例必须使用结构化输出 schema 和运行时校验。
- schema 校验失败按策略重试有限次数，随后进入可恢复失败或人工队列。
- 模型返回的 HTML、JavaScript、命令和工具参数不得直接执行。
- 工具调用需要 input schema、权限、对象范围、幂等、preview、confirm、timeout、audit 和补偿。

### R13. AI Observability And Audit

- 每次调用记录 invocation id、task id、业务对象、prompt revision、model policy、provider/model、延迟、tokens、成本、重试和结果分类。
- 默认不记录完整敏感输入输出；调试采样受权限和保留期控制。
- 指标支持按 use case、provider、model、tenant 和结果分类聚合。
- 审计必须能回答：谁、何时、基于哪个 Prompt/模型/输入范围、产生哪个业务草稿或建议。

### R14. Provider Fakes And Contract Tests

- 提供 AI、ASR 和对象存储的 deterministic fake adapter 模式或测试桩接口。
- Provider contract tests 验证超时、限流、非法结构、空响应、重复回调和部分失败。
- 本地和 CI 不依赖真实外部 Provider 才能验证业务状态机。

## Data And Migration

- 新建任务、任务尝试、Lease、进度、Outbox、AI invocation、usage ledger 等必要表。
- 唯一约束覆盖幂等键、Outbox event id 和消费记录。
- 大字段或原始 Provider payload 不直接塞入高频任务表；使用受控 artifact reference。
- migration 支持 upgrade/downgrade 或明确的补偿脚本。
- 当前开发数据可重建，但 migration 测试必须覆盖空库和旧 schema 升级。

## Acceptance Criteria

- [x] API 进程被终止后，已排队和运行中的任务能在 Lease 过期后恢复。
- [x] 同一幂等键并发提交只创建一个逻辑任务。
- [x] Worker 重试不会重复写业务结果、Outbox 或预算账。
- [x] 取消、超时、死信和人工恢复均有 Task 状态与 API；部分成功/等待输入通过有类型 TaskResultRef 和业务对象状态表达，不引入第二套 Task 生命周期。
- [x] 未注册 Task Type、非法 schema 和跨组织访问被明确拒绝。
- [x] 任务状态写入与 Outbox 事件在同一事务。
- [x] 业务模块可通过 fake AI Provider 完成 deterministic 集成测试。
- [x] Prompt revision、model policy、contract hash、usage 和结果分类可追溯。
- [x] 业务代码中不新增直接 Provider SDK 调用。
- [x] AI 输出 schema 失败不会被当作成功，不会直接改变正式达标状态。
- [x] 指标可观察队列深度、Lease 超时、重试、死信、AI 延迟、Token 和成本。
- [x] API、Worker、migration、contract tests 和并发测试通过。

## Verification

- PostgreSQL 集成测试：领取、续租、过期恢复、并发幂等、Outbox。
- Worker 故障注入：处理前、外部调用后、业务提交前、提交后崩溃。
- AI Provider contract tests：正常、超时、429、5xx、schema invalid、空输出。
- 权限测试：本人、同组织管理员、跨组织、无 capability。
- 性能基线：任务创建与查询不因队列规模线性退化；关键索引有 explain 证据。

## Definition Of Done

- 平台能力可被后续 Audio、Quiz、AI Coach 和题目生成切片直接复用。
- 没有业务特定状态或评分规则进入 task runtime。
- API 与 Worker 可独立运行并安全停机。
- 关键失败均可恢复或进入显式人工队列。
- 文档、运维命令、指标、告警和回滚步骤齐全。

## Out Of Scope

- 不实现具体录音转写或评分算法。
- 不实现题目候选审核、AI Coach 卡片或达标复核。
- 不引入独立消息中间件或微服务拆分。
- 不实现 Realtime 音频流处理。

## Risk And Rollback

- 风险等级：P1。
- 最大风险是任务状态与业务状态双权威；业务最终状态必须由业务模块写入，Task 仅保存执行状态与结果引用。
- 使用 feature flag 按 task type 启用新 Worker。
- 回滚时停止新任务创建、等待或安全取消在途任务，再回退 API/Worker；保留任务表用于审计和恢复。
