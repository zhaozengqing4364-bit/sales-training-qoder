# ADR：受治理 AI 调用与持久化任务分离

- 日期：2026-07-16
- 状态：Accepted（切片 1 平台已实现；业务消费者按后续切片迁移）

## 决策

所有 LLM 与 ASR 调用通过 `AIInvocationPort`；业务模块拥有业务目的、Prompt 变量、输入/输出 Schema、Rubric 与失败政策，`ai_platform` 拥有 Provider、模型路由、超时、重试、限流、预算、血缘、输出校验和观测。模型原始输出不能直接改变正式状态，也不得用固定 60/70 分伪造成功。

音频处理、简答评分、题目批量生成、报告与知识处理通过 PostgreSQL 真源的 `TaskRuntimePort` 执行。API 与 Worker 分进程；任务支持租约、重试等待、取消请求、死信、进度和结果引用。业务写与 Outbox 同事务，消费者至少一次且幂等；Redis 和进程内队列不是事实权威。

## 原因与后果

现有同步音频处理、进程内 BackgroundTask、直接 Provider/LLM 调用和仅有状态合同但无存储/Worker 的实现均为迁移来源。切片 0 不创建任务表或 Worker；具体状态和 AI 合同分别见 [`../architecture/newcomer-foundation-state-machines.md`](../architecture/newcomer-foundation-state-machines.md) 与 [`../ai-governance.md`](../ai-governance.md)。

## 切片 1 实现说明

平台以 `durable_tasks`、独立 `task_attempts`/`task_leases`、进度、结果引用和事务 Outbox 为
PostgreSQL 真源。唯一任务状态是 `queued`、`running`、`retry_wait`、
`cancel_requested`、`cancelled`、`succeeded`、`dead_letter`；Lease 不是状态，
`partial_success`/`waiting_input` 是结果分类。旧
[`2026-07-06-persistent-background-task-contract.md`](2026-07-06-persistent-background-task-contract.md)
已被本 ADR 取代，其 import surface 只保留为 canonical 合同的兼容 facade。

独立进程与故障处置见
[`../setup/durable-task-worker-runbook.md`](../setup/durable-task-worker-runbook.md)。

## 切片 3 录音流水线落实

`audio_assessment.pipeline.process` 已作为独立 Worker Handler 注册。`finalize_upload` 只验证会话/part 登记并排入持久任务；对象 HEAD、分片物化、ffprobe/ffmpeg、ASR、评分和 Outcome 对账均由 Worker 分阶段执行，且外部 IO 不跨数据库事务。每阶段保存明确恢复位置，同一业务键和 Invocation/reconcile 重放不追加重复结果。

为避免引入云厂商专属 multipart SDK，同时满足 100MB 完整文件、断点续传和对象完整性，首发采用应用级 multipart：后端生成组织/Run/UploadSession 隔离的不可变 part key 和签名上传地址，客户端只上传服务端声明的 part，服务端登记及 Worker 处理时重新 HEAD 并校验大小/SHA-256。`local` adapter 通过受保护 API 流式落盘；OSS/COS 直接上传，API 不转发完整云文件。过期/取消 part 由部署级有界清理命令使用行锁、stale claim 和 token fencing 删除，正式 Artifact 不属于该清理范围。

音频 ASR 使用受治理 ProfileRevision 且不携带 Prompt lineage；语言评分必须引用精确已发布 PromptRevision。由于 Prompt 合同包含本次场景、Transcript 和 rubric 的真实渲染变量，`prompt_contract_hash` 在每次调用前通过同一 `StrictPromptCompiler` 动态计算并写入 Invocation，而不是预先冻结一个静态 hash。Prompt/route/Schema/Provider 缺失或输出不合法都 fail closed 到可恢复状态；领域服务在 Schema、证据引用和确定性规则通过后才追加 ScoreOutcomeVersion。

具体运行、清理、数据保留与回滚见 [`../setup/foundation-audio-assessment-runbook.md`](../setup/foundation-audio-assessment-runbook.md)。
