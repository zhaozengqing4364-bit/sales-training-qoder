# 支持角色运行状态 API 契约

> 状态: ✅ 已实现（2026-04-14 更新）
>
> 后端实现: `backend/src/support/api/runtime_status.py`
>
> 配套 runtime authority 代码面：
> - `backend/src/common/websocket/session_manager.py`
> - `backend/src/common/websocket/session_state_service.py`

## 概览

- 基础路径: `/api/v1/support/runtime`
- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie
- 角色要求: `support` 或 `admin`
- 能力边界: **只读**（不包含任何策略变更、发布、回滚写操作）
- 当前 API 定位: **release-health / fault summary surface**，不是 cluster-wide websocket runtime truth surface

## 统一响应

```json
{
  "success": true,
  "data": {},
  "trace_id": "abc123"
}
```

---

## Runtime state inspection companion surfaces

`/api/v1/support/runtime/*` 当前返回的是 support/admin 可安全查看的汇总健康状态；它**不会**把 websocket live runtime registry 直接暴露成 HTTP 合同。和 session reconnect / restart / drain 相关的 authority 需要按下面两层理解：

### 1. Process-local live connection authority

来源：`SessionManager.get_stats()`

它能回答的是真正由**当前进程**持有的 live websocket 事实：

- `total_sessions`
- `tracked_sessions[]`
- `connection_visibility.scope = "process_local"`
- `connection_visibility.shared_across_instances = false`
- `connection_visibility.survives_restart = false`
- `tracked_sessions[].runtime_diagnostics.session_status`
- `tracked_sessions[].runtime_diagnostics.ai_state`
- `tracked_sessions[].runtime_diagnostics.current_request_id`
- `tracked_sessions[].runtime_diagnostics.reconnect_state.connection_epoch`
- `tracked_sessions[].runtime_diagnostics.reconnect_state.request_epoch`
- `tracked_sessions[].runtime_diagnostics.reconnect_state.last_disconnect_reason`
- `tracked_sessions[].runtime_diagnostics.reconnect_state.last_error`

解释规则：

- 这些字段只说明“**这个进程**当前看到了什么连接”。
- 在多实例场景里，不能把某一个实例的 `total_sessions = 0` 解释成“整个集群没有活跃 websocket”。
- 进程重启后，这层 state 预期会丢失；空 registry 不代表 session 真正终结，只代表当前进程不再持有 live socket。

### 2. Redis reconnect snapshot authority

来源：`SessionStateService.get_stats()`

它能回答的是**跨实例 / 可跨重启复用**的 reconnect-safe snapshot：

- `snapshot_visibility.scope = "redis_snapshot"`
- `snapshot_visibility.shared_across_instances = true`
- `snapshot_visibility.survives_restart = true`
- `metrics.save_calls / get_calls / delete_calls / healthcheck_failures`
- `last_saved_snapshot`
- `last_loaded_snapshot`
- `last_saved_snapshot.request_epoch`
- `last_saved_snapshot.connection_epoch`
- `last_saved_snapshot.last_disconnect_reason`
- `last_saved_snapshot.last_error`
- `last_error`

解释规则：

- 这是当前唯一可由其他实例读取、并在进程重启后继续解释 session runtime 的 authority。
- 它说明“断线后应该恢复什么”，**不是** live connection truth。
- `current_request_id` / `request_epoch` 是 reconnect-safe 的请求代际信号；`latest_action_card` 故意不进入 snapshot，避免 reconnect 后重放过期教练卡片。

### 3. Support / runbook interpretation rule

- `/overview` 与 `/faults` 用来回答“系统最近是否健康、有哪些 blocking/warning fault”。
- `SessionManager.get_stats()` 用来回答“当前实例还持有哪些 live connections / runtime diagnostics”。
- `SessionStateService.get_stats()` 用来回答“重启后还能依赖哪些 reconnect snapshots / epochs / last_error”。
- 任何 support/runbook 结论都必须明确区分 **process-local active connections** 与 **shared Redis snapshot**，不能把两者混成同一个 runtime truth surface。
- release/recovery proof 也必须成对留证：把 `/support/runtime/*` 的 release-health / fault summary 与 `.dev/recovery-drills/<timestamp>/summary.json`、逐 drill `*.log`、以及 deploy `/health` capture 一起归档；`/overview` 看起来 healthy 并不自动代表 db/auth/redis/oss drills 都通过。

---

## 运行概览

```http
GET /api/v1/support/runtime/overview?window_hours=24
```

### Query 参数

- `window_hours`（可选，默认 `24`，范围 `1~168`）

### 响应结构

```json
{
  "generated_at": "2026-04-14T04:00:00Z",
  "window_hours": 24,
  "session_health": {
    "active_sessions": 3,
    "total_sessions_window": 28,
    "completed_sessions_window": 24,
    "scoring_sessions": 1,
    "stuck_scoring_sessions": 0,
    "not_evaluable_completed_sessions_window": 1,
    "completion_rate": 85.71
  },
  "release_health": {
    "status": "warning",
    "blocking_count": 1,
    "warning_count": 2,
    "typed_anomaly_count": 3,
    "blocking_sessions_count": 1,
    "warning_sessions_count": 2,
    "supplemental_warning_log_count": 0
  },
  "anomaly_summary": {
    "blocking": [
      {
        "kind": "stuck_scoring",
        "count": 1
      }
    ],
    "warning": [
      {
        "kind": "optional_report_failed",
        "count": 2
      }
    ]
  }
}
```

### 字段说明

- `session_health.active_sessions`: 当前窗口内仍处于 `preparing` / `in_progress` / `paused` 的 session 数
- `session_health.scoring_sessions`: 当前停留在 `scoring` 的 session 数
- `session_health.stuck_scoring_sessions`: 超过阈值仍未走到 `completed` 的 scoring session 数
- `session_health.not_evaluable_completed_sessions_window`: 已完成但 unified evidence 标记为不可评估的会话数
- `release_health.status`: `healthy` / `warning` / `blocking`
- `anomaly_summary`: 仅按 kind 聚合数量，不返回每条 fault 的完整 diagnostics

---

## 故障摘要

```http
GET /api/v1/support/runtime/faults?limit=20&severity=warning
```

### Query 参数

- `limit`（可选，默认 `20`，范围 `1~100`）
- `severity`（可选）：`blocking` / `warning`

### 响应结构

```json
{
  "generated_at": "2026-04-14T04:00:00Z",
  "count": 2,
  "limit": 20,
  "severity": "warning",
  "items": [
    {
      "source": "session",
      "severity": "warning",
      "kind": "optional_report_failed",
      "summary": "增强报告生成失败，但 canonical report 仍走统一 evidence 读线。",
      "detected_at": "2026-04-14T03:58:12Z",
      "session_id": "session-123",
      "scenario_type": "presentation",
      "session_status": "completed",
      "report_status": "failed",
      "diagnostics": {
        "report_error_code": "[REPORT_GENERATION_FAILED]"
      }
    }
  ]
}
```

### Fault item 说明

- `source`: 当前可能是 `session` 或 `system_log`
- `severity`: `blocking` / `warning`
- `kind`: 例如 `stuck_scoring`、`knowledge_search_failed`、`optional_report_failed`
- `summary`: 给 support/admin 的可读摘要
- `diagnostics`: allowlist-first 的安全诊断字段，不保证包含 raw backend details

### `diagnostics.runtime_events[]` 读法

当某条 fault 来自 AI / knowledge-answer / report 运行链时，`diagnostics.runtime_events[]` 会附带同一条 allowlist-safe runtime event 线。当前 event shape 如下：

```json
{
  "event_id": "knowledge_answer_path_mode",
  "category": "mode",
  "severity": "info",
  "status": "compat",
  "source": "knowledge_answer",
  "summary": "Knowledge answer served the compatibility path.",
  "details": {
    "rollout_mode": "dual_run"
  },
  "metrics": {},
  "occurred_at": "2026-04-14T04:00:00Z"
}
```

字段解释：

- `event_id`: 稳定事件标识；当前已覆盖 knowledge path mode、knowledge quality、kb lock、claim-truth、LLM cost/failure 等 runtime 事件。
- `category`: 当前约定为 `quality` / `cost` / `failure` / `mode`。
- `severity`: 当前约定为 `info` / `ok` / `degraded` / `failure`。
- `status`: 该事件自己的状态值；例如 knowledge path 会给出 `live` / `compat`，claim-truth 会给出具体 truth 状态，cost 会给出 `tracked` / `budget_warning` 等。
- `source`: 事件 authority seam；当前主要是 `knowledge_answer`、`kb_lock`、`claim_truth`、`llm`。
- `summary`: 支持 support/admin 直接阅读的安全摘要，不需要回看默认分数或 fallback 文案猜状态。
- `details` / `metrics`: allowlist-safe 细节与计量，只保留可对 support/admin 暴露的诊断字段。

解释规则：

- **`category = mode` 说明来源路径，不等于异常。** 例如 `knowledge_answer_path_mode.status = live|compat` 用来回答“当前知识问答是 live 还是 compat”，不是质量判定本身。
- **`severity = degraded` 说明结果仍对外返回，但质量/完整性已经下降。** 例如 knowledge grounding partial、audio upload partial、budget warning、fallback anchor 等都属于 degraded，而不是成功低分。
- **`severity = failure` 说明该运行面无法提供可靠结果。** 例如 `knowledge_answer_quality` 在 `search_failed` / `blocked` / `insufficient` 时会显式落成 failure；support 不应再把这类情况解释成“只是分数一般”。
- **`category = cost` 是观测事件，不自动代表成功。** 成本事件可以与 `degraded` / `failure` 并存，用来回答“这次失败/降级是否仍消耗了 token / session budget”。
- **优先读 runtime event，不要反推默认文案。** 如果 `summary` 或 `details` 已经显式给出 degraded / failure / compat，就不要再用 `overall_score`、fallback 回答文案、`[REPORT_GENERATION_FAILED]` 之类外围信号做二次猜测。

### 已知边界

- 这里不会返回 live websocket connection registry。
- 这里不会返回 cluster-wide active connection count。
- 这里不会返回 raw provider payload、prompt text、token、cookie、stack trace、精确身份信息等 backend-only details。
- 需要定位 reconnect epoch / disconnect reason / last error 时，应回到上面的 companion inspection surfaces，而不是要求 `/faults` 扩成第二套 runtime payload。

---

## 鉴权与错误语义

- 未认证：`401`
- 已认证但角色不满足：`403`
- 非法 `severity` 过滤值：`400` + `"[INVALID_SEVERITY_FILTER]"`（仅允许 `blocking` / `warning`）
- 错误响应遵循统一结构，包含 `trace_id`

## Single-instance / multi-instance / restart 解释约束

- 单实例 / systemd：`/support/runtime/*` 可以提供 release-health 视角，但 live websocket 仍只由当前进程内 `SessionManager` 持有。
- 多实例：需要把 `SessionManager` 结论标记为 **instance-local**；跨实例只应信任共享 Redis snapshot authority。
- 重启后：`SessionManager` registry 归零是预期行为；真正还能解释 reconnect 的是 `SessionStateService` snapshot，而不是 restart 前的 live connection 数。
- drain/restart 相关操作 guidance 以 `docs/backup-recovery-runbook.md` 为准。