# 会话管理 API 契约

> 状态: ✅ 已实现（2026-02-11 更新）
>
> 后端实现: `backend/src/common/api/practice.py`
>
> 相关 Schema: `backend/src/common/db/schemas.py`

## 目标与范围

- 统一会话创建入口: `POST /api/v1/practice/sessions`
- 创建时固化 `voice_policy_snapshot`，后续读取统一引用该快照基线
- 策略优先级固定: `会话覆盖 > Agent 策略 > 系统默认配置档`
- 兼容 legacy 创建方式（`sales_persona`）

---

## 统一响应格式

```json
{
  "success": true,
  "data": {},
  "trace_id": "trace-xxx"
}
```

错误响应:

```json
{
  "success": false,
  "error": "[ERROR_CODE]",
  "message": "[ERROR_CODE]",
  "trace_id": "trace-xxx"
}
```

---

## 核心模型

### `SessionCreate`

```typescript
interface SessionCreate {
  scenario_type: "sales" | "presentation";
  presentation_id?: string;
  sales_persona?: string; // legacy 模式兼容字段
  scenario_id?: string;
  agent_id?: string;
  persona_id?: string;
  voice_mode?: "legacy" | "stepfun_realtime";
  runtime_profile_id?: string;
}
```

### `SessionLifecycleRequest`

```typescript
interface SessionLifecycleRequest {
  action: "start" | "pause" | "resume" | "end";
}
```

### `voice_policy_snapshot_ref`

```typescript
interface VoicePolicySnapshotReference {
  voice_mode?: string | null;
  runtime_profile_id?: string | null;
  tool_policy: Record<string, unknown>;
  knowledge_base_ids: string[];
  source: Record<string, string>;
  resolved_at?: string | null;
  agent_persona_override_config?: Record<string, unknown> | null;
}
```

### `SessionResponse`（关键字段）

```typescript
interface SessionResponse {
  session_id: string;
  user_id: string;
  scenario_id: string;
  scenario_type?: "sales" | "presentation";
  voice_mode?: string;
  voice_runtime_profile_id?: string | null;
  voice_policy_snapshot?: Record<string, unknown> | null;
  voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
  status: "preparing" | "in_progress" | "paused" | "completed" | "scoring";
  start_time: string;
  end_time?: string | null;
}
```

### `SessionLifecycleResponse`

```typescript
interface SessionLifecycleResponse {
  session_id: string;
  previous_status: "preparing" | "in_progress" | "paused" | "completed" | "scoring";
  status: "preparing" | "in_progress" | "paused" | "completed" | "scoring";
  ai_state: "listening" | "idle";
  changed: boolean;
  scenario_type?: "sales" | "presentation";
  start_time: string;
  end_time?: string | null;
  total_duration_seconds?: number | null;
}
```

### 生命周期状态机（REST + WebSocket 一致）

| 动作 | 允许来源状态 | 目标状态（sales） | 目标状态（presentation） | 说明 |
|------|--------------|-------------------|---------------------------|------|
| `start` | `preparing` / `in_progress` | `in_progress` | `in_progress` | `preparing -> in_progress` 时会设置 `start_time`；`in_progress` 重复调用为幂等（`changed=false`） |
| `pause` | `in_progress` / `paused` | `paused` | `paused` | `in_progress -> paused`；重复 `pause` 幂等 |
| `resume` | `paused` / `in_progress` | `in_progress` | `in_progress` | `paused -> in_progress`；重复 `resume` 幂等 |
| `end` | `in_progress` / `paused` / 终态 | `scoring` | `completed` | 非终态结束时设置 `end_time` 和 `total_duration_seconds`；终态重复 `end` 幂等 |

补充语义:

- `changed=true`: 本次动作引发状态迁移并已持久化。
- `changed=false`: 幂等动作（例如重复 pause/resume/end），会返回当前状态但不重复写入。
- `ai_state`: `in_progress` 对应 `listening`，其余状态对应 `idle`。

---

## 已实现接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/practice/sessions` | 创建会话并固化策略快照 |
| `POST` | `/api/v1/practice/sessions/{session_id}/lifecycle` | 生命周期动作控制（start/pause/resume/end） |
| `GET` | `/api/v1/practice/sessions/{session_id}` | 获取会话详情（含快照引用） |
| `PATCH` | `/api/v1/practice/sessions/{session_id}` | 更新会话状态/当前页 |
| `DELETE` | `/api/v1/practice/sessions/{session_id}` | 结束会话 |
| `GET` | `/api/v1/practice/sessions/{session_id}/report` | 获取会话报告（含快照引用） |
| `GET` | `/api/v1/practice/sessions/{session_id}/knowledge-check` | 获取知识检索运行诊断 |
| `GET` | `/api/v1/practice/history` | 会话历史分页列表 |
| `GET` | `/api/v1/sessions/stats` | 用户会话统计 |

> 说明: lifecycle 动作被处理后，后端会向同会话 WebSocket 广播 `status`，若进入终态还会追加 `session_ended` 事件。

---

## 创建会话契约要点

### 1) 入参约束

- `agent_id` 与 `persona_id` 必须成对提供
- `sales` 场景在未使用增强模式时必须传 `sales_persona`
- `presentation` 场景需要传 `presentation_id`
- 若传入 `scenario_id`，系统会校验该场景存在、启用且与 `scenario_type` 一致，并以该 `scenario_id` 作为会话事实持久化

### 2) 快照固化

- 建会话时统一调用 `VoiceRuntimePolicyService.resolve_effective_policy`
- 返回并持久化:
  - `voice_mode`
  - `runtime_profile_id`
  - `tool_policy`
  - `knowledge_base_ids`
  - `source`
  - `resolved_at`
  - `agent_persona_override_config`（存在关联覆盖时）

### 3) 不可变语义

- 快照策略基线字段不可被后续配置变更覆盖
- 允许在 `runtime_metrics` 子树追加运行观测数据
- 报告与回放必须基于同一会话快照引用，不得在读取时重算策略

---

## 典型请求与响应

### 创建会话（增强模式）

```http
POST /api/v1/practice/sessions
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "scenario_type": "sales",
  "scenario_id": "scenario-uuid",
  "agent_id": "agent-uuid",
  "persona_id": "persona-uuid",
  "voice_mode": "stepfun_realtime"
}
```

```json
{
  "success": true,
  "data": {
    "session_id": "session-uuid",
    "user_id": "user-uuid",
    "scenario_id": "scenario-uuid",
    "voice_mode": "stepfun_realtime",
    "voice_runtime_profile_id": "profile-uuid",
    "voice_policy_snapshot": {
      "voice_mode": "stepfun_realtime",
      "runtime_profile_id": "profile-uuid",
      "tool_policy": {
        "enable_internal_retrieval": true,
        "enable_web_search": false
      },
      "knowledge_base_ids": ["kb_agent_1", "kb_persona_1"],
      "source": {
        "base": "env",
        "runtime_profile": "system_default",
        "voice_mode": "session_override"
      },
      "resolved_at": "2026-02-11T12:00:00+00:00"
    },
    "voice_policy_snapshot_ref": {
      "voice_mode": "stepfun_realtime",
      "runtime_profile_id": "profile-uuid",
      "tool_policy": {
        "enable_internal_retrieval": true,
        "enable_web_search": false
      },
      "knowledge_base_ids": ["kb_agent_1", "kb_persona_1"],
      "source": {
        "base": "env",
        "runtime_profile": "system_default",
        "voice_mode": "session_override"
      },
      "resolved_at": "2026-02-11T12:00:00+00:00"
    },
    "status": "preparing",
    "start_time": "2026-02-11T12:00:00+00:00"
  },
  "trace_id": "trace-xxx"
}
```

### 报告读取（同源快照引用）

```http
GET /api/v1/practice/sessions/{session_id}/report
Authorization: Bearer <token>
```

返回中的 `voice_policy_snapshot_ref` 必须与会话详情 / 回放接口一致。

### 生命周期控制（状态机动作）

```http
POST /api/v1/practice/sessions/{session_id}/lifecycle
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "action": "pause"
}
```

WebSocket 同步事件（由 lifecycle 触发）:

```json
{
  "type": "status",
  "timestamp": "2026-02-11T12:00:01+00:00",
  "trace_id": "trace-xxx",
  "data": {
    "session_status": "paused",
    "ai_state": "idle"
  }
}
```

```json
{
  "type": "session_ended",
  "timestamp": "2026-02-11T12:10:00+00:00",
  "trace_id": "trace-xxx",
  "data": {
    "session_id": "session-uuid",
    "session_status": "scoring"
  }
}
```

```json
{
  "success": true,
  "data": {
    "session_id": "session-uuid",
    "previous_status": "in_progress",
    "status": "paused",
    "ai_state": "idle",
    "changed": true,
    "scenario_type": "sales",
    "start_time": "2026-02-11T12:00:00+00:00",
    "end_time": null,
    "total_duration_seconds": null
  },
  "trace_id": "trace-xxx"
}
```

非法迁移示例（`preparing -> resume`）:

```json
{
  "success": false,
  "error": "[INVALID_SESSION_TRANSITION]",
  "message": "[INVALID_SESSION_TRANSITION] action=resume, from_status=preparing, expected=paused|in_progress, scenario_type=sales",
  "trace_id": "trace-xxx",
  "details": {
    "current_status": "preparing",
    "requested_action": "resume",
    "expected": "paused|in_progress"
  }
}
```

---

## 访问控制

- 所有会话接口需要 JWT
- 会话详情/报告/回放: 仅 owner 或 admin 可访问
- 未认证返回 `401`
- 越权返回 `403`（`[ACCESS_DENIED]`）

---

## 错误码（会话创建相关）

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `[INVALID_SESSION_TRANSITION]` | `409` | 生命周期动作不满足状态机（返回当前状态与期望状态） |
| `[AGENT_PERSONA_PAIR_REQUIRED]` | `400` | 仅传 `agent_id` 或仅传 `persona_id` |
| `[AGENT_NOT_FOUND]` | `404` | Agent 不存在 |
| `[AGENT_ARCHIVED]` | `400` | Agent 已归档 |
| `[AGENT_NOT_PUBLISHED]` | `400` | Agent 未发布 |
| `[PERSONA_NOT_FOUND]` | `404` | Persona 不存在 |
| `[PERSONA_INACTIVE]` | `400` | Persona 已停用 |
| `[PERSONA_NOT_LINKED_TO_AGENT]` | `400` | Persona 未关联到 Agent |
| `[SCENARIO_NOT_FOUND]` | `404` | 传入的 `scenario_id` 不存在 |
| `[SCENARIO_TYPE_MISMATCH]` | `400` | `scenario_id` 与 `scenario_type` 不匹配 |
| `[SCENARIO_INACTIVE]` | `400` | 传入的 `scenario_id` 已停用 |
| `[SALES_PERSONA_REQUIRED]` | `400` | legacy 销售模式缺少 `sales_persona` |
| `[INVALID_PERSONA]` | `400` | legacy `sales_persona` 非法 |
| `[SESSION_CREATE_FAILED]` | `500` | 建会话失败 |

---

## 向后兼容说明

- 继续支持 legacy `sales_persona` 创建路径
- 新增字段全部为 additive（不会破坏既有消费方）
- 契约回归覆盖:
  - `backend/tests/contract/test_sessions.py`
  - `backend/tests/contract/test_sales_sessions.py`

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-02-11 | 补充生命周期状态机细节 | 明确 start/pause/resume/end 允许来源状态、幂等语义、终态差异（sales=scoring、presentation=completed） |
| 2026-02-11 | 补充 lifecycle 对应 WS 契约 | 增加 `status` / `session_ended` 广播事件结构，统一 REST 与实时通道语义 |
| 2026-02-11 | 新增 lifecycle 契约 | 补齐 `POST /practice/sessions/{session_id}/lifecycle` 请求/响应与错误语义 |
| 2026-02-11 | 新增 sessions 契约文档 | 对齐会话创建快照固化与读取一致性语义 |
| 2026-02-11 | 补充访问控制与错误码 | 覆盖增强模式校验、legacy 兼容和权限边界 |
