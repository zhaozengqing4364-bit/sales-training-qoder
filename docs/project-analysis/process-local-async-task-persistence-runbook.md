# 进程内异步任务持久化整改 Runbook

本文是 `docs/adr/2026-07-06-persistent-background-task-contract.md` 的执行手册。当前仓库已冻结任务状态机与契约 helper，但尚未接管运行时调度；本文中的 SQL/worker 命令适用于后续 `persistent_tasks` 表和 worker 落地后。

## 适用范围

首批治理对象：

| 任务类型 | 当前入口 | 当前风险 | 首个验收目标 |
| --- | --- | --- | --- |
| `sales_trainer.audio_submission.process` | `sales_trainer/api.py` 的 FastAPI `BackgroundTasks` | 进程退出后录音可能停在 `uploaded/transcribing/scoring` | 上传后任务可查、可重试、不会重复评分 |
| `knowledge.document.process` | `common/knowledge/api.py` 的 `BackgroundTasks` | 文档可能永久 `pending/processing`，向量写入失败不可死信 | 文档处理有租约、失败原因和 reprocess 新任务 |
| `practice_report.generate` | `SessionLifecycleService._trigger_report_generation()` 的 `asyncio.create_task` | 会话结束后投递丢失，报告状态只能局部推断 | 会话结束响应不阻塞，报告任务可恢复 |
| `audio_archive.batch` | `AudioArchivalScheduler` 进程内循环 | 多实例重复/遗漏批处理，失败只能看日志 | scheduler 只 enqueue，worker 执行并记录死信 |

## 上线前检查

1. 确认 migration 已创建 `persistent_tasks` 与 `persistent_task_events`。
2. 确认 `PersistentTaskType` 枚举包含本次启用的 `task_type`。
3. 确认 handler 只调用原 domain service，不复制业务逻辑。
4. 确认 payload 不包含密钥、Authorization/Cookie/JWT、完整 prompt、完整外部 request/response。
5. 确认每个 handler 有幂等检查：
   - 音频：`scored` 或已有成功 score result 时跳过。
   - 知识文档：`ready` 且 chunk/vector 完整时跳过。
   - 报告：`report_status=completed` 且 snapshot 存在时跳过。
   - 归档：`archived=true` 或文件已在归档路径时跳过。
6. 确认 worker 可按 `task_type` 开关启停。

## 标准操作

### 查看待执行任务

```sql
select task_id, task_type, business_key, status, attempt_count, next_run_at, trace_id
from persistent_tasks
where status in ('queued', 'retry_wait')
order by next_run_at asc, priority desc, created_at asc
limit 50;
```

### 查看卡住的 running 任务

```sql
select task_id, task_type, business_key, lease_owner, lease_expires_at, attempt_count
from persistent_tasks
where status = 'running'
  and lease_expires_at < now()
order by lease_expires_at asc;
```

处理原则：

- 未超过 `max_attempts`：由 sweeper 写入 `retry_wait`，不要人工直接改为 `queued`。
- 已超过 `max_attempts`：进入 `dead_letter`，保留原因。
- 如果业务对象已完成，标记 `succeeded` 并写事件，不能让 worker 再执行外部副作用。

### 查看死信

```sql
select task_id, task_type, business_key, last_error_code, dead_letter_reason,
       attempt_count, max_attempts, trace_id, updated_at
from persistent_tasks
where status = 'dead_letter'
order by updated_at desc
limit 100;
```

死信处理必须先判断 failure 类型：

- Terminal：修配置/数据后创建新任务或执行业务 reprocess/retry 入口。
- Transient：确认外部服务恢复后可重投。
- Voluntary：不重投。

### 重投死信

推荐通过后续管理命令或 API 执行，必须带 `actor_id` 和 `reason`。命令落地前，禁止在生产环境手写 SQL 重投。

预期命令形态：

```bash
cd backend
PYTHONPATH=src uv run python scripts/requeue_persistent_task.py \
  --task-id <task_id> \
  --actor-id <admin_user_id> \
  --reason "外部 ASR 服务已恢复"
```

命令验收：

- 校验任务当前为 `dead_letter`。
- 校验 payload schema 仍与 handler 兼容。
- 写入 `persistent_task_events(event_type='requeued')`。
- 重置 `status='queued'`、`next_run_at=now()`、`lease_owner=null`、`lease_expires_at=null`。
- 不清空历史 `attempt_count`，或显式写入 `requeue_count`，避免掩盖反复失败。

## 任务类型处理手册

### `sales_trainer.audio_submission.process`

投递点：录音上传或直接注册提交完成后。

最小 payload：

```json
{
  "submission_id": "...",
  "actor_id": "...",
  "requested_by": "learner|admin_retry",
  "schema_version": 1
}
```

失败分类建议：

| 错误 | 类型 | 处理 |
| --- | --- | --- |
| `[AUDIO_SUBMISSION_NOT_FOUND]` | Terminal | dead-letter |
| `[AUDIO_TRANSCRIPT_REQUIRED]` | Terminal | dead-letter 或转写子任务补偿 |
| `[SCORING_PROMPT_REQUIRED]` / `[SCORING_PROMPT_NOT_PUBLISHED]` | Terminal | 修配置后人工重投 |
| ASR/LLM timeout、限流、网络失败 | Transient | retry_wait |
| 用户/管理员取消提交 | Voluntary | cancelled |

验收测试：

- 上传同一 submission 不产生重复活跃任务。
- worker 重跑不会生成重复成功 score result。
- terminal 配置错误进入 dead-letter，业务对象保持用户可理解失败态。

### `knowledge.document.process`

投递点：文档上传成功提交 DB 后、文档 reprocess 重置状态后。

最小 payload：

```json
{
  "doc_id": "...",
  "knowledge_base_id": "...",
  "file_path": "...",
  "file_type": "pdf|docx|txt|md|xlsx|xls",
  "vector_collection": "...",
  "content_hash": "...",
  "schema_version": 1
}
```

失败分类建议：

| 错误 | 类型 | 处理 |
| --- | --- | --- |
| 文件不存在、格式不支持、KB 不存在 | Terminal | dead-letter + document `failed` |
| 向量库短暂不可用、语义缓存不可用 | Transient | retry_wait；缓存失效失败不得阻断 ready |
| 管理员删除文档后任务到达 | Voluntary | cancelled |

验收测试：

- 上传后 `pending -> running -> ready/failed` 可查。
- reprocess 生成新幂等键，不复用旧 dead-letter 行伪成功。
- 进程重启后 queued/retry_wait 任务可继续。

### `practice_report.generate`

投递点：会话结束事务提交后。

最小 payload：

```json
{
  "session_id": "...",
  "scenario_type": "sales|presentation",
  "schema_version": 1
}
```

失败分类建议：

| 错误 | 类型 | 处理 |
| --- | --- | --- |
| session 不存在或已删除 | Terminal | dead-letter |
| evidence 不可评估但可生成 non-evaluable snapshot | 业务成功 | succeeded |
| LLM/报告服务 timeout | Transient | retry_wait |
| prompt/config 缺失 | Terminal | dead-letter + `report_status=failed` |

验收测试：

- 会话结束接口不等待报告生成。
- 重复投递不会覆盖已完成报告 snapshot。
- 报告 dead-letter 可由管理端看到 session_id、error_code、trace_id。

### `audio_archive.batch`

投递点：scheduler tick。scheduler 不执行归档，只 enqueue 一个批任务。

最小 payload：

```json
{
  "retention_days": 365,
  "batch_size": 100,
  "schema_version": 1
}
```

失败分类建议：

| 错误 | 类型 | 处理 |
| --- | --- | --- |
| 源文件不存在且 DB 未归档 | Terminal 或 warning | 按策略记录 failed_count，不阻断整批 |
| 目标目录暂不可写 | Transient | retry_wait |
| session 已归档 | 业务成功 | 跳过 |

验收测试：

- 多实例 scheduler 不会生成同一时间窗口的重复活跃批任务。
- worker 归档部分失败时返回可解释 stats，并按严重程度决定 retry/dead-letter。

## 回滚流程

1. 关闭对应 `task_type` worker 开关。
2. 确认没有 `running` 行；如有，等待租约过期或人工标记 cancelled。
3. 恢复 legacy 投递点或关闭新投递 flag。
4. 保留任务表和事件表，作为审计证据。
5. 对用户可见业务对象执行一致性修复：
   - 音频：卡住的 `transcribing/scoring` 改为对应失败态并提示可重试。
   - 文档：卡住的 `processing` 改为 `failed`，保留 reprocess。
   - 报告：卡住的 `processing` 改为 `failed` + `report_retryable=true`。
   - 归档：不需要改业务状态，等待下一轮 legacy scheduler。

## 验收矩阵

| 场景 | 必须覆盖 |
| --- | --- |
| 投递 | 幂等键唯一、payload schema、trace_id、业务对象不存在 |
| 获取 | 多 worker 并发 claim、租约写入、priority/next_run_at 排序 |
| 成功 | terminal status、completed_at、事件、业务对象最终态 |
| 失败 | terminal dead-letter、transient retry_wait、重试耗尽 |
| 恢复 | lease expired sweeper、worker 重启、重复执行幂等 |
| 运维 | dead-letter 查询、重投审计、取消审计、payload 脱敏 |
| 安全 | learner 无法查看任务 payload；管理员操作留痕 |

## 当前已落地证据

- ADR：`docs/adr/2026-07-06-persistent-background-task-contract.md`
- 状态机 helper：`backend/src/common/jobs/persistent_task_contract.py`
- 契约测试：`backend/tests/unit/common/jobs/test_persistent_task_contract.py`
