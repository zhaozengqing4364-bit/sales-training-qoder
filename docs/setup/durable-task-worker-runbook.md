# Durable Task Worker 运行手册

## 适用范围

本手册用于独立启动、探测、扩缩容和故障处置 `task_runtime` Worker 与 Outbox Dispatcher。
PostgreSQL 是任务、Lease、Attempt、结果引用与 Outbox 的唯一事实源；Redis 和进程内队列不承担
持久化事实。业务 Handler 与生产 EventTransport 必须在组合根显式注册；进程不接受任意 HTTP
payload 或动态 import。

## 启动前置

Worker 启动只做 schema 校验，不执行 DDL。先由发布流程运行：

```bash
cd backend
alembic upgrade head
```

API、Worker 与 Dispatcher 是三个独立进程。Slice 3 已在生产组合根注册
`learning.question_generation.generate`、`learning.quiz.short_answer_score` 和
`audio_assessment.pipeline.process` 三个 Handler；Worker
启动时会装配真实的受治理 AIInvocation，缺少有效 LLM 连接配置、已发布 Prompt/模型路由或可执行
Handler 时 fail closed，不会退回测试 fake。生产 EventTransport 仍未注册，因此生产 Dispatcher
继续按预期拒绝启动。API 与 Worker 可分别启动：

```bash
cd backend
PYTHONPATH=src python -m uvicorn src.main:app --host 0.0.0.0 --port 3444
PYTHONPATH=src python -m task_runtime.worker_main
```

`configure_application_event_transport(...)` 是生产组合根的集成 seam；Slice 1 尚无生产 adapter，
所以默认 `python -m task_runtime.outbox_main` 会 fail closed。

本地一键启动默认只拉起 API 和前端，Worker 与 Dispatcher 都是显式 opt-in：

```bash
bash scripts/dev-up.sh

# 已配置真实 LLM 连接并发布 Prompt/模型路由后启用 Worker
TASK_WORKER_ENABLED=1 bash scripts/dev-up.sh

# 仅供本地确定性联调：显式启用不会外发事件的 fake transport
ENVIRONMENT=development \
OUTBOX_DISPATCHER_ENABLED=1 \
OUTBOX_DISPATCHER_ALLOW_DEV_FAKE=1 \
bash scripts/dev-up.sh
```

生产环境不得设置 `OUTBOX_DISPATCHER_ALLOW_DEV_FAKE=1`；即使误设，非
`development/local/test` 环境也会拒绝使用 fake。停止时先向 Worker 和 Dispatcher 发
`SIGTERM`：Worker 停止领取并等待在途 Handler；Dispatcher 停止新批次并等待当前批次的每个
投递结果收口。`bash scripts/dev-stop.sh` 已包含该顺序。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TASK_WORKER_ID` | `<hostname>-<pid>` | Lease owner 的可定位实例标识 |
| `TASK_WORKER_TASK_TYPES` | 所有已注册且有 Handler 的类型 | 逗号分隔的领取白名单；未知或无 Handler 时启动失败 |
| `TASK_WORKER_MAX_PARALLELISM` | `4` | 单进程最大并行 `run_once` 数 |
| `TASK_WORKER_POLL_SECONDS` | `1` | 空队列或故障后的轮询间隔 |
| `TASK_WORKER_HEARTBEAT_SECONDS` | 按 Lease 的三分之一 | 显式续租间隔，必须小于 Lease 的一半 |
| `TASK_WORKER_PROBE_HOST` | `127.0.0.1` | Probe 默认仅本机；容器编排需显式覆盖为 `0.0.0.0` |
| `TASK_WORKER_PROBE_PORT` | `3446` | Probe 端口 |

新人训练学习任务的 AI 连接配置优先读取管理后台已启用的默认 LLM `ModelConfig`，数据库凭据解密失败
时才读取环境变量。环境 fallback 合同如下；生产环境不得把密钥写入命令、日志或前端配置：

| 配置 | 必需性 | 说明 |
| --- | --- | --- |
| `LLM_API_KEY` | 远程 Provider 必需 | 首选环境凭据；`OPENAI_API_KEY` 只保留为旧部署 bootstrap fallback |
| `LLM_PROVIDER` | 建议显式设置 | 当前 Worker 只接受 `openai` 或 `alibaba`；其他值拒绝启动 |
| `LLM_BASE_URL` | 必需 | 必须是 endpoint policy 允许的 HTTPS Provider 地址；禁止凭据、query、fragment 和私网地址 |
| `LLM_MODEL` | 环境配置必需 | 连接配置的模型标识；每次业务调用仍以已发布 ModelRoutingRevision 冻结的 provider/model 为准 |
| `LLM_TIMEOUT` / `LLM_TIMEOUT_SECONDS` | 可选 | 环境 fallback 的连接超时；任务自身另有 180/300 秒 durable deadline |
| `LLM_TEMPERATURE`、`LLM_MAX_TOKENS` | 可选 | 环境默认策略；正式调用使用已发布模型路由修订中的冻结值 |

数据库 `ModelConfig.extra_config` 可配置 `currency`、`input_cost_minor_units_per_million` 和
`output_cost_minor_units_per_million`；非法币种长度、负数或非整数计费值会拒绝 Worker 启动。Provider
只接收严格编译的已发布 Prompt 文本和 JSON 输出约束，组合根不会追加未版本化 system message。

两个任务的建议隔离配置：

```bash
TASK_WORKER_TASK_TYPES=learning.question_generation.generate,learning.quiz.short_answer_score \
PYTHONPATH=src python -m task_runtime.worker_main
```

题目生成使用 `question-generation-input-v1` / `question-generation-output-v1`；短答评分使用
`short-answer-input-v1` / `short-answer-output-v1`。Schema 无效、Prompt hash 不匹配、Provider
超时/限流/不可用或无效 JSON 都保留为任务失败/重试状态；不得把短答记为零分或已完成。

完整文件录音建议使用独立 Worker 池，避免 ffmpeg/ASR 长任务占用学习任务并行度：

```bash
TASK_WORKER_TASK_TYPES=audio_assessment.pipeline.process \
PYTHONPATH=src python -m task_runtime.worker_main
```

录音 Worker 还依赖 ffmpeg/ffprobe、对象存储、ASR、动态 Prompt 编译与录音 Schema；配置、清理、
故障恢复和回滚见 [`foundation-audio-assessment-runbook.md`](foundation-audio-assessment-runbook.md)。

Dispatcher 关键配置：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OUTBOX_DISPATCHER_ID` | `<hostname>-<pid>` | Outbox Lease owner 标识 |
| `OUTBOX_DISPATCHER_BATCH_SIZE` | `100` | 单次领取事件上限 |
| `OUTBOX_DISPATCHER_POLL_SECONDS` | `1` | 空批次或失败后的轮询间隔 |
| `OUTBOX_DISPATCHER_LEASE_SECONDS` | `30` | 单事件投递租约 |
| `OUTBOX_DISPATCHER_RETRY_SECONDS` | `5` | 单事件失败后的退避 |
| `OUTBOX_DISPATCHER_MAX_ATTEMPTS` | `10` | 事件进入 dead-letter 前的尝试上限 |
| `OUTBOX_DISPATCHER_PUBLISH_TIMEOUT_SECONDS` | `10` | transport 单次发布超时，必须小于租约 |
| `OUTBOX_DISPATCHER_PROBE_PORT` | `3447` | 独立 Probe 端口 |

## 探针与监控

```bash
curl -fsS http://127.0.0.1:3446/live
curl -fsS http://127.0.0.1:3446/ready
curl -fsS http://127.0.0.1:3446/status

curl -fsS http://127.0.0.1:3447/live
curl -fsS http://127.0.0.1:3447/ready
curl -fsS http://127.0.0.1:3447/status
```

- `/live`：仅表示 Worker 事件循环存活；停止完成后返回 `503`。
- `/ready`：必须已成功完成最近一次数据库维护/领取，且未进入停机；数据库异常后立即 `503`，
  后续成功轮询会自动恢复为 `200`。
- `/status`：始终返回当前 `in_flight`、失败次数、最近错误分类和本进程支持的任务类型；不含
  payload、Token 或用户敏感数据。
- Dispatcher `/ready` 只在至少一个数据库领取/投递循环成功后为 `200`；transport 或数据库异常
  立即降为 `503`，下一次完整成功后恢复。`SIGTERM` 后在途批次会 drain，但不再领取新批次。

System Admin 的运行平台 health API 另提供队列深度、运行/重试/死信数、过期 Lease、Outbox
lag，以及最近 15 分钟的重试率和平均处理延迟。访问必须同时具备权限和未过期、未撤销的显式
组织 scope；角色本身不授予跨组织访问。

## 扩缩容与任务类型隔离

- 多实例共用 PostgreSQL，通过 `FOR UPDATE SKIP LOCKED` 领取；每实例使用唯一 Worker ID。
- 用 `TASK_WORKER_TASK_TYPES` 建独立任务池，避免某类 Provider 阻塞其他任务。
- 每组织、每任务类型可配置暂停、最大并发和每分钟速率。闸门在 PostgreSQL 锁内复核；被限流
  的高优先级类型不会饿死其他可运行类型。
- 扩容前先观察 queue depth、Outbox lag、15 分钟延迟与外部 Provider 限额；不要只看 CPU。

## 故障处置

### `/live=200`、`/ready=503`

查看 Worker 结构化日志中的 `task_worker_iteration_failed` 和 `error_code`，确认 PostgreSQL 网络、
连接池与 Alembic head。不要手工改任务状态；数据库恢复后 Worker 会自动重新轮询并恢复 ready。

### Worker 在执行中退出

Lease 到期后其他实例会恢复任务。可重试任务进入 `retry_wait`；耗尽尝试后进入
`dead_letter`。用户投影只显示“任务执行中断，将自动重试”或“重试次数已用尽”，Lease/Worker
细节仅保留在 Attempt 分类和结构化日志。

### 大量 dead-letter

先按 task type、错误分类和时间窗口定位共同原因。修复根因后使用受保护 Operator redrive；
redrive 创建新任务并保留旧 dead-letter 行作为审计，不能原地重置历史任务。

### Outbox lag 上升

确认 Dispatcher 存活、transport 延迟与 dead-letter event 数。单事件失败按事件独立重试，不应
阻塞同批其他事件。消费者以 `(consumer_name,event_id)` 收据 effect-once；不要删除收据来强制
重放，应使用显式修复命令。

### Dispatcher 启动即退出

若日志提示未配置生产 `EventTransport`，这是 fail-closed 保护。生产组合根必须显式提供 transport；
不要用本地 fake 绕过。开发环境确需只验证数据库领取、重试、probe 和 drain 时，才按“启动前置”
中的双开关命令启动确定性 fake。

### 取消长任务

取消命令只写 `cancel_requested`。运行中 Handler 在 `checkpoint()` 安全确认；未领取任务由
Worker maintenance 确认。不要用数据库直接改成 `cancelled`。

## 数据与安全底线

- Task payload 和 Outbox payload 只保存对象/制品引用；完整音频、转写、Prompt、模型原始响应、
  密钥、Token、bytes 和超限 JSON 会在平台 seam 被拒绝。
- `TaskResultRef` 的已保存、未完成和可重试项只接受至多 100 个/组的
  `{resource_type, resource_id}` 不透明引用，三组序列化总量不超过 16 KiB；正式内容必须写入业务
  对象或受控制品，不能借结果项 JSONB 绕过 payload guard。
- Operator scope 必须包含授予者、原因、过期时间；撤销保留审计，过期后新增授权不覆盖旧记录。
- 生产环境不手工 `UPDATE durable_tasks`、不清空 Outbox、不把 downgrade 当数据恢复方案。

## 发布与回滚

发布顺序：先 `alembic upgrade head`，再部署 API/Worker，观察 probes 和指标，最后按 task type
启用业务 enqueue。回滚时先停止该 task type 的新 enqueue，等待在途完成或发起安全取消，再停
Worker 和回退应用；保留平台表用于审计与后续恢复。只有确认无平台数据且明确接受删除时，才在
非生产环境执行 Alembic downgrade。

## 确定性 Worker 测试适配器

`backend/tests/fakes/task_runtime.py` 提供 `FixedClock`、`ControlledSleeper` 和
`DeterministicTaskHandler`。它们只用于测试边界，不得从生产组合根导入。用真实 PostgreSQL 验证
Lease、heartbeat、deadline、版本恢复与公平领取：

```bash
cd backend
TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' \
./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py -q --no-cov
```
