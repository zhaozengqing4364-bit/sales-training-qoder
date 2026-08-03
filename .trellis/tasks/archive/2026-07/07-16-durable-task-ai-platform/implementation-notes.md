# Slice 1 实施记录

## 范围

本切片只实现通用 `task_runtime` 与 `ai_platform`。不实现 Audio、Quiz、AI Coach 的业务 Handler，不迁移后续切片消费者，不修改 Realtime。

## 权威冲突与偏差

- Slice 1 PRD 的任务状态列表与 Slice 0 状态机冲突。按权威顺序采用且只采用：`queued`、`running`、`retry_wait`、`cancel_requested`、`cancelled`、`succeeded`、`dead_letter`。
- `leased` 不是 Task 状态；领取事实保存在 `TaskLease` 与 `TaskAttempt`。
- `waiting_input`、`partially_succeeded` 不是 Task 状态；它们由 `TaskResultRef.classification` 表达，Task 可 `succeeded` 并引用部分结果或待输入位置。
- timeout 按冻结 Task Policy 进入 `retry_wait` 或 `dead_letter`；人工恢复通过 redrive 创建新 Task，旧 dead-letter 行不变。
- 不提供任意 `task_type/payload` 的 HTTP enqueue。创建只经业务 application command 调用 `TaskRuntimePort.enqueue`；学员 HTTP 只有查询与请求取消，平台 Operator 面只开放脱敏查询、redrive、pause/resume 与 health。

## 已确认的代码事实

- `common/jobs/persistent_task_contract.py` 原为 6 状态与旧 `persistent_tasks` 表合同；Slice 1 已将其收敛为 canonical `task_runtime` 的兼容导入 facade，不再维护第二套状态机、重试公式或表合同。
- 当前仓库没有 Outbox 模型或 Dispatcher。
- `PromptTemplateService.compile_runtime_prompt_contract()` 已有严格渲染与 contract hash，但当前 PromptTemplate ORM 没有不可变 published revision。
- `LLMService` 有 20+ 直接调用者；本切片不替换这些后续业务消费者，只新增 `AIInvocationPort` 与平台 Adapter。
- Alembic 当前只有 `20260715_0000_001` Launch Baseline；新增 revision 必须从该 head 继续。
- SQLAlchemy 模型由 `common.db.model_registry.registration.register_all_models()` 在组合根显式注册。
- 当前 User 没有 organization 字段，因此平台 HTTP 必须要求显式组织 scope，并同时校验 Actor/Object；不能从角色猜测跨组织权限。

## TDD Seams

测试只从以下已确认公共 seam 观察：

- `TaskRuntimePort`：`enqueue/get/request_cancel` 与 Operator commands；
- `TaskRegistry`；
- Worker claim/execute/complete application interface；
- Outbox dispatcher/consumer public interface；
- `AIInvocationPort.invoke()`；
- Prompt compiler public interface；
- 受保护 HTTP Task projection。

数据库测试使用真实 PostgreSQL；Provider、时钟与对象存储只在系统边界使用 deterministic fake。

## Tracer Cycles

### Cycle 1：任务合同、持久化与租约

- RED：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training_task_runtime_test' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py --no-cov -q`；按预期在收集阶段失败：`ModuleNotFoundError: No module named 'task_runtime'`。
- GREEN 首次运行：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py --no-cov -q`；真实 PostgreSQL 已进入写入路径，但暴露 `TaskPayloadArtifact` 与 `DurableTask` 同次 flush 没有 ORM 依赖排序，触发外键失败。改为显式生成 artifact ID 并先 flush artifact。
- GREEN：同一命令复跑，`1 passed, 1 warning in 0.79s`。已覆盖进程重建后的 durable get、同业务对象幂等重放、同 key 异载荷冲突；数据库使用隔离 schema `slice1_task_runtime_test`。

### Cycle 2：并发领取、Fence、续租与过期恢复

- RED：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py -q --no-cov`；按预期在公共 Worker Store seam 收集失败：`ModuleNotFoundError: No module named 'task_runtime.worker_store'`。
- GREEN：同一命令复跑，`2 passed, 1 warning in 0.96s`。两个独立 PostgreSQL session 并发领取只返回一个 Claim；续租延长 Lease；错误/旧 fencing token 被拒绝；Lease 过期进入 `retry_wait`，到期释放后由新 Worker 以新 Attempt/Token 恢复，旧 Worker Fence 继续被拒绝。

### Cycle 3：Worker 成功、部分结果、重试、取消与停机

- RED：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py -q --no-cov`；按预期在 Worker 执行失败分类 seam 收集失败：`ImportError: cannot import name 'TaskExecutionError'`。
- GREEN 首次运行：同一命令，`5 passed, 1 warning in 1.52s`。覆盖 handler 输入/结果 schema、typed partial result、transient retry、safe checkpoint cancel 和停止后不再领取。
- 取消语义 RED：`...pytest ...::test_worker_acknowledges_cancel_at_safe_checkpoint -q --no-cov`；按预期失败，暴露复用 failure path 会把正常取消投影成 `cancel_acknowledged` 错误。
- GREEN：专用 cancel acknowledge 清空 error 并完成 Attempt；全文件复跑 `5 passed, 1 warning in 1.51s`。旧 Fence 的 `complete()` 也被同一 PostgreSQL 测试以 `TaskLeaseLostError` 拒绝。

### Cycle 4：事务 Outbox、隔离重试与幂等消费

- RED：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py -q --no-cov`；按预期在公共 Outbox seam 收集失败：`ModuleNotFoundError: No module named 'task_runtime.outbox'`。
- GREEN：同一命令复跑，`6 passed, 1 warning in 2.02s`。覆盖 producer rollback 不留事件、enqueue/claim/succeed 与 Outbox 同事务、payload 不含输入原文、单事件投递失败不阻断同批其他事件、退避后重投，以及 `(consumer_name,event_id)` PostgreSQL 唯一收据保证 handler effect-once；handler 与收据共享事务，失败会一起回滚。
- Registry RED：`./.venv/bin/pytest tests/unit/task_runtime/test_registry.py -q --no-cov`，`2 failed`；暴露 dataclass equality 把同类型新 handler 实例误判为漂移，且字符串 handler 未被拒绝。
- Registry GREEN：同一命令 `2 passed, 1 warning in 0.14s`；同 logical definition 重复 registrar 幂等，schema/policy/handler type 漂移 fail closed，动态字符串 import 入口被拒绝。

### Cycle 5：Operator Scope、暂停恢复、死信 Redrive 与健康投影

- RED：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py -q --no-cov`；按预期在 Operator application seam 收集失败：`ModuleNotFoundError: No module named 'task_runtime.operator_service'`。
- GREEN：同一命令在补齐 service、受保护 HTTP、权限矩阵与并发 control upsert 后复跑，`9 passed, 1 warning in 3.39s`。覆盖本人 TaskRuntime 查询；同组织 capability+服务端 scope；有 capability 无 scope；有 scope 无 capability；跨组织；默认 scope 未配置时 403；受保护 list/detail；不存在通用 HTTP enqueue；pause/resume 影响 claim；首次并发 pause 同命令只产生 version 1；dead-letter redrive 创建新 Task 且旧行保持死信；health 返回 queue/running/retry/dead/expired lease/outbox lag。

### Cycle 6：在途 Heartbeat 与优雅停机

- RED：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py::test_worker_renews_in_flight_lease_during_graceful_stop -q --no-cov`；按预期失败：`TaskWorker.__init__() got an unexpected keyword argument 'sleeper'`，证实长 Handler 尚无 deterministic heartbeat seam。
- GREEN：同一 targeted 命令 `1 passed, 1 warning in 1.17s`；deterministic sleeper 推进 3 个 heartbeat 后超过原 Lease，reaper 仍为 0；stop 后不再 claim，但在途 Handler 继续续租至 safe checkpoint 并成功完成。全 Task Runtime PostgreSQL 文件复跑 `10 passed, 1 warning in 3.38s`。

### Cycle 7：进度、限流、截止时间与热查询性能

- RED：全 Task Runtime PostgreSQL 文件新增 progress、Worker status、并发/速率上限与 deadline 场景后出现 `5 failed`；公共执行上下文缺 `report_progress`，Operator 缺 limits command，health 缺新指标。
- GREEN：实现 fenced progress+Outbox、每组织/任务类型并发和 1 分钟速率闸门、blocked 高优先级任务不饿死其他类型、排队 deadline 回收、15 分钟滚动 retry rate/latency；claim/list/metrics 建立与排序和时间窗口匹配的 PostgreSQL 索引。
- 性能证据：`EXPLAIN (FORMAT JSON)` 在真实 PostgreSQL 分别命中 `ix_durable_tasks_claim`、`ix_durable_tasks_org_updated_keyset`、`ix_task_attempts_started_task`。

### Cycle 8：显式限时 Scope、Payload Guard 与 Generic Outbox

- RED：payload guard 单测首先因 `TaskDefinition` 不支持分类/大小合同失败；HTTP 测试证明仅靠 System Admin 角色会绕过组织 scope；业务域只能调用 task-specific Outbox helper。
- GREEN：移除角色自动 unrestricted；所有 Operator 必须同时具备 capability 与未过期、未撤销的显式 org/object grant。Grant 保存授予者、理由、过期和撤销审计，允许旧授权保留后新增同 scope 授权。
- GREEN：Task registry 在持久化前拒绝完整音频/转写/Prompt/Raw Response/密钥字段（含前后缀变体）、binary、超限 JSON 和未声明分类；`*_artifact_id`/`*_artifact_ref` 引用允许通过。
- GREEN：新增 UoW-bound `OutboxWriterPort.append(event)` 与 generic `DomainEvent`；SQLAlchemy session 仅由 adapter 持有。覆盖 rollback、同逻辑事件重放、异内容冲突、敏感 payload 拒绝、dispatch 与 effect-once consumer。

### Cycle 9：兼容合同与权限种子收敛

- GREEN：旧 `persistent_task_contract` 的 public import surface 改为复用 canonical 7 状态、transition map、terminal set 与 retry 计算，表合同同步为 `durable_tasks`；不再存在第二套生命周期/表真源。
- GREEN：默认角色权限补种不再因权限表已有任意行而提前返回；覆盖 baseline 表非空但缺 `task_runtime.read/operate` 时幂等补齐。
- 验证：`./.venv/bin/pytest tests/unit/task_runtime/test_registry.py tests/unit/common/jobs/test_persistent_task_contract.py tests/unit/test_admin_permissions_rbac.py -q --no-cov` → `19 passed, 1 warning in 2.95s`；`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py -q --no-cov` → `15 passed, 1 warning in 5.94s`。

### Cycle 10：独立 Worker 进程、Probe 与开发运维入口

- RED：`./.venv/bin/pytest tests/unit/task_runtime/test_worker_service.py -q --no-cov` 在收集阶段按预期失败：`ModuleNotFoundError: No module named 'task_runtime.worker_main'`。
- GREEN：新增独立 `python -m task_runtime.worker_main`、并行轮询 service、SIGTERM drain，以及 `/live`、`/ready`、`/status`。`/ready` 在首个 DB maintenance/claim 成功前为 503，迭代异常立即 503，后续成功自动恢复；空 registry、未知类型或无 Handler 配置 fail closed 并非零退出。
- 开发入口：`scripts/dev-up.sh`/`dev-stop.sh` 支持独立 Worker PID、日志和 probe；Slice 1 尚无业务 Handler，因此默认 `TASK_WORKER_ENABLED=0`，后续注册 Handler 后用 `TASK_WORKER_ENABLED=1 bash scripts/dev-up.sh` 一键启用，避免空 Worker 伪 ready。
- 运维文档：新增 `docs/setup/durable-task-worker-runbook.md`，覆盖启动、探针、扩缩容、故障、取消、dead-letter、Outbox、安全、发布与回滚；旧 2026-07-06 ADR 标记 Superseded。
- 验证：`./.venv/bin/pytest tests/unit/task_runtime/test_worker_service.py -q --no-cov` → `4 passed, 1 warning in 0.21s`；`bash -n scripts/dev-up.sh scripts/dev-stop.sh` → exit 0。一次误把 `--help` 传给无 CLI 参数的 `dev-up.sh` 导致本地 API/前端短暂启动，已立即用 `bash scripts/dev-stop.sh` 完整停止并确认 PID 文件清除，未改数据。

### Cycle 11：恢复不变量、版本合同、结果引用与公平领取

- Registry 改为精确 `(task_type, schema_version)` 注册与解析；同一类型多版本可以同时恢复，数据库中存在但部署侧未知的版本会领取后明确进入 dead-letter，不会误交给其他版本 Handler。
- Claim 携带 enqueue 时冻结的 timeout、Lease、max attempts、retry policy 和 deadline。Handler 超时/截止时会取消并等待协程收口，晚到结果不能穿透 Fence；Worker 的领取、heartbeat、complete、fail、cancel-ack 持久化故障都会使 readiness 降级，后续成功数据库操作恢复。
- Redrive 事件和新任务 ID 不依赖重试时钟；取消和 Operator 行为同时校验 capability 与显式组织/对象 scope，列表 scope 使用批量 seam 避免逐行授权查询。
- Claim 使用 aged lane 与 priority lane 两条有界 `SKIP LOCKED` 查询；通用/按类型两组领取索引都存在。空表 PostgreSQL 可能在语义等价的通用与按类型索引间选择，EXPLAIN 测试因此验证实际命中任一匹配排序索引，并独立断言专用索引存在。
- `TaskResultRef` 的三组结果项由 `list[Any]` 收紧为最多 100 项/组、总计 16 KiB 的 `{resource_type, resource_id}` 不透明引用；任意字符串、dict、转写、Provider raw 和超限内容在写入 JSONB 前拒绝，正式结果仍只落业务对象或受控制品。
- 验证：`./.venv/bin/pytest tests/unit/task_runtime/test_registry.py tests/unit/task_runtime/test_task_result_contract.py tests/unit/task_runtime/test_worker_service.py tests/unit/task_runtime/test_outbox_service.py -q --no-cov` → `21 passed, 1 warning in 0.21s`；`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_runtime_postgres.py -q --no-cov` → `19 passed, 1 warning in 8.15s`。

### Cycle 12：单 revision Migration 与独立 Outbox Dispatcher

- 新增单个 `20260716_2300_002` revision，承接 Launch Baseline，一次创建 Task Runtime 与 AI Platform 表、索引、外键及 `task_runtime.read/operate` 固定权限种子；downgrade 只删除本 revision 的固定授权，保留同名自定义数据。
- Migration 测试在隔离 PostgreSQL schema 覆盖空库到 head、零 ORM drift、循环 downgrade/upgrade、重复 upgrade、跨表 FK 和自定义权限保留。
- Outbox Dispatcher 具备独立 service/entrypoint、`/live`/`/ready`/`/status`、SIGTERM 当前批次 drain、单批所有 delivery 完成后再抛故障，以及生产无 EventTransport 时 fail closed。本地 fake 只有 `development/local/test` 加显式双开关时可用。
- `scripts/dev-up.sh` 默认仍只启动 API/前端；Worker 与 Dispatcher 分别 opt-in，`dev-stop.sh` 统一停止并清理 probe。运行手册明确 Slice 1 尚无业务 Handler 和生产 transport adapter。
- 验证：`TASK_RUNTIME_TEST_DATABASE_URL='postgresql+asyncpg:///sales_training' ./.venv/bin/pytest tests/integration/task_runtime/test_task_ai_platform_migration.py -q --no-cov` → `1 passed, 1 warning in 22.32s`；`bash -n scripts/dev-up.sh scripts/dev-stop.sh` → exit 0；Task Runtime 相关 Ruff format/check → exit 0。

### Cycle 13：受治理 AI 调用、Prompt 编译与模型路由

- 建立统一 `AIInvocationPort`，LLM 与 ASR 请求都必须携带精确的业务目的、组织/Actor/对象、Prompt 或 ASR revision、模型路由 revision、输入/输出 schema、预算、超时/重试策略、数据分级与 trace/correlation/causation。业务调用方不能指定 Provider SDK client，也不能使用“latest”隐式解析。
- Prompt 预览与正式调用复用 `StrictPromptCompiler`；已发布 Prompt 与模型路由 snapshot 都以 content hash 校验完整性。缺失、未发布、篡改、变量漂移、schema 不匹配、非法数据分级与未校准正式评分均 fail closed。
- Provider 输出先经过版本化结构 schema；空输出和非法结构按已发布策略做有限重试，不能作为成功或正式达标事实。Fallback 只能由路由策略允许，正式评分的主路由和 fallback 都必须显式校准。
- 新增 LLM、ASR、对象存储 deterministic fake 与 contract tests，覆盖 timeout、429、5xx、空输出、非法 schema、部分结果、重复调用和对象存储部分失败。本地与 CI 不依赖真实 Provider。

### Cycle 14：AI PostgreSQL 真源、幂等效果与审计指标

- `AIInvocationRecord`、Provider Attempt、Usage Ledger、预算预留/窗口、Rate Window、Circuit、受控结果 Artifact、Prompt revision 与 Model Routing revision 进入同一 revision；高频审计表不保存完整业务输入、渲染 Prompt 或 Provider raw payload。
- 并发同一逻辑请求只有一个 owner、一次预算预留和一个 Provider attempt；Provider idempotency key 支持“外部调用已完成、数据库尚未记录”的 lookup/reconcile。Usage ledger 以 attempt/effect key 去重，失败重试和 crash replay 不重复扣费。
- Provider response 覆盖旧 attempt failure 字段；Provider 报告币种必须与路由预算币种一致后才能入账。预算、rate limit 与 circuit key 包含精确路由 revision，策略新旧 revision 不串账；attempt replay 对 provider/model/route 漂移 fail closed。
- AI 指标按 organization、use case、provider、model、结果分类与 currency 聚合，避免跨币种成本相加；审计可回溯 Actor、对象、Prompt/ASR revision、路由 revision、Provider/model、tokens、成本、延迟、重试、证据引用与结果分类。

### Cycle 15：AI admission 与 ownership fencing 加固

- RED 证明本地非法输入原先会先进入 `store.prepare()`，从而占用 rate quota 和预算预留。现将冻结合同、输入 schema、数据分级、Prompt 编译/contract hash 与正式评分校准全部移到 admission 前；失败通过 `reject_before_admission` 原子留审计，但不占配额。并发非法同请求仍只得到一个确定性失败结果，后续合法请求不被前者限流。
- RED 证明 AI owner lease 过期后若尚未被新执行者 reclaim，旧 token 仍可写入晚到 response。InMemory 与 SQLAlchemy adapter 现同时校验 token 和 `owner_expires_at > now`；过期 response/complete 均返回 `AI_INVOCATION_OWNERSHIP_LOST`，Attempt、Invocation 与 Usage Ledger 不被晚到结果修改。
- 成功 Invocation 的受控输出使用 30 天默认 retention artifact；requested Prompt/route ID 不设置强 FK，使“请求引用不存在 revision”的失败本身仍能持久审计。成功路径必须先由精确 resolver 校验 published snapshot 与 content hash；后续发布治理切片负责 catalog 的创建、不可变发布和保留策略。
- 验证：AI unit 最终 `57 passed`；真实 PostgreSQL AI integration 最终 `11 passed, 1 warning in 4.94s`；`mypy src/task_runtime src/ai_platform` → `Success: no issues found in 34 source files`。

### Cycle 16：Slice 1 最终定向门禁与 API Contract

- 首次最终 unit/contract 集合得到 `121 passed, 1 failed`；唯一失败是新增 Task Runtime Admin 路由尚未写入 committed OpenAPI。使用仓库权威生成脚本更新契约后，route integrity 与 `--check` 通过；最终同一集合复跑为 `122 passed, 3 warnings in 22.25s`。
- 最终真实 PostgreSQL：Task Runtime `19 passed, 1 warning in 8.17s`；Task/AI migration roundtrip `1 passed, 1 warning in 22.17s`；AI Platform `11 passed, 1 warning in 4.94s`。
- 最终静态检查：focused Ruff check 全部通过；focused Ruff format check `46 files already formatted`；`mypy` 34 个 Task/AI source files 通过；`bash -n scripts/dev-up.sh scripts/dev-stop.sh` 通过；OpenAPI `--check` 明确为 current。
- CodeGraph affected 因组合根路由与共享权限/模型注册列出 108 个潜在测试。按本任务“最小验证”约束，本切片只运行 Task/AI、RBAC、模型注册、Alembic、App Factory、route/OpenAPI 的定向集合；其余跨业务全量回归保留到切片 8 最终发布门禁。

## 偏离计划

- 一次误把 `--help` 传给无参数的 `dev-up.sh`，短暂拉起本地 API/前端；已立即执行 `dev-stop.sh`，PID 与端口均清理，未执行迁移或改写业务数据。
- 热查询 EXPLAIN 最初把“空表必须选某一个具体索引名”写成断言；PostgreSQL 会在排序兼容的通用/按类型索引间非确定选择。修正为验证实际计划命中匹配索引，并另行验证全部专用索引已建，不把 planner 在空表上的选择误当性能合同。
- 最终检查发现 committed OpenAPI 未包含本切片新增的受保护 Admin Task Runtime 路由；已只用仓库生成器机械更新并通过语义一致性检查，没有手工改写其他 API。

## 验证

- 已完成 focused unit/contract、真实 PostgreSQL Task Runtime、真实 PostgreSQL AI Platform、空库/旧 baseline Migration roundtrip、Mypy、Ruff、OpenAPI 与脚本语法检查；结果见各 Cycle。
- 未运行仓库全量 quality gate、浏览器 UI 或真实外部 Provider；本切片没有用户可见 UI，也没有业务 Handler/生产 EventTransport adapter，发布前仍需由后续业务切片接入并执行全量门禁。

## Trellis Check 与验收关闭

- 独立 `trellis-check` 复核按 R1–R14 检查了 Task Runtime、AI Platform、权限/组织隔离、迁移、运维合同、跨层数据流与测试证据；未发现阻塞项或需要在本切片追加修复的确定性缺陷。
- Acceptance 逐项关闭：Lease 过期恢复；并发幂等创建；Worker/AI/Outbox/Usage Ledger effect-once；取消、超时、死信、redrive、部分成功与等待输入；未注册版本、非法 schema、非法 payload 和跨组织访问拒绝；Task 状态与 Outbox 原子提交；deterministic AI/ASR/Storage fake；Prompt/route/contract/usage/result lineage；业务侧无新增 Provider SDK 直连；schema invalid 不形成成功或正式结论；Task/AI 指标；API、Worker、migration、contract 与并发验证，均有上述源码和测试证据。
- 复核附加命令：focused Ruff 为 `All checks passed!`；`backend/scripts/architecture_dependency_guard.py --check` 为 `[architecture] dependency policy satisfied`；相关 `git diff --check` 与 `py_compile` 均为 exit 0。
- 生产 EventTransport、真实 Provider 和首批业务 Handler 尚未接入；平台组合根按设计 fail closed。这是后续业务切片的显式接入点，不在本切片伪造默认实现。

## Finish Work 偏差

- Trellis 标准收口会提交工作、archive 和 journal；本轮 GOAL 明确禁止在未获授权时自动 commit。故本切片使用 `task.py archive --no-commit` 与 `add_session.py --no-commit` 收口，保留工作区全部现状并继续既定下一切片；不因大量用户未提交改动而擅自暂存或提交。
