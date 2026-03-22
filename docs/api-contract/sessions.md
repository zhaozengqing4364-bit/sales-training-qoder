# 会话管理 API 契约

> 状态: ✅ 已实现（2026-02-22 更新）
>
> 后端实现: `backend/src/common/api/practice.py`
>
> 相关 Schema: `backend/src/common/db/schemas.py`

## 目标与范围

- 统一会话创建入口: `POST /api/v1/practice/sessions`
- 创建时固化 `voice_policy_snapshot`，后续读取统一引用该快照基线
- 策略优先级固定: `会话覆盖 > Agent 策略 > 系统默认配置档`
- 销售场景统一采用 `agent_id + persona_id` 配对创建

## 领域语言收敛

- 管理面仍保留 `Scenario`、`Agent`、`Presentation` 等配置实体。
- 运行时对外统一主语为 `training_scenario_runtime`，避免会话接口、权限校验、统计口径继续按实体类型分叉。
- `PracticeSession` 是运行时事实锚点；配置实体只负责提供运行参数，不直接充当运行时主语。

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
  scenario_id?: string;
  agent_id?: string;
  persona_id?: string;
  voice_mode?: "legacy" | "stepfun_realtime";
  runtime_profile_id?: string;
}
```

> 说明: `sales_persona` 字段已废弃，若继续传入将返回 `[FIELD_DEPRECATED_PERSONA_CENTERED]`。

### `SessionLifecycleRequest`

```typescript
interface SessionLifecycleRequest {
  action: "start" | "pause" | "resume" | "end";
}
```

### `TrainingRuntimeDescriptor`

```typescript
interface TrainingRuntimeDescriptor {
  subject: "training_scenario_runtime";
  session_id: string;
  scenario_type: "sales" | "presentation";
  agent_id?: string | null;
  persona_id?: string | null;
  presentation_id?: string | null;
  voice_mode?: string | null;
  runtime_profile_id?: string | null;
}
```

### `voice_policy_snapshot_ref`

```typescript
interface VoicePolicySnapshotReference {
  voice_mode?: string | null;
  runtime_profile_id?: string | null;
  instruction_contract_hash?: string | null;
  network_access_mode?: "off" | "controlled" | string | null;
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
  runtime_subject: "training_scenario_runtime";
  runtime_descriptor?: TrainingRuntimeDescriptor | null;
  runtime_profile_id?: string | null;
  voice_policy_snapshot?: Record<string, unknown> | null;
  voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
  effectiveness_snapshot?: {
    pass_flags: {
      pass_3min_flow: boolean;
      pass_5turn_defense: boolean;
      pass_4step_structure: boolean;
    };
    main_capability_passed: boolean;
    overall_result: "pass" | "strong_pass" | "fail";
    main_issue: {
      issue_type: string;
      issue_text: string;
      recovery_rule: string;
    };
    metrics: {
      continuous_speech_seconds: number;
      filler_rate_per_100_words: number;
      offtopic_turn_count: number;
      offtopic_max_streak: number;
      structure_coverage: number;
    };
    next_goal: {
      goal_type: string;
      goal_text: string;
      rule: string;
    };
    version: string;
    evaluable: boolean;
  } | null;
  status: "preparing" | "in_progress" | "paused" | "completed" | "scoring";
  start_time: string;
  end_time?: string | null;
}
```

> 兼容说明：`voice_runtime_profile_id` 已停止对外返回，请统一使用 `runtime_profile_id`。
>
> 认证说明：浏览器场景推荐使用 `HttpOnly` session cookie；下文 `Authorization: Bearer <token>` 仅作为脚本/非浏览器调用示例。

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

### 报告字段补充（沟通闭环）

`GET /api/v1/practice/sessions/{session_id}/report` 额外返回：

- `effectiveness_snapshot`: 会话效果快照（统一真值源）
- `pass_flags`: 三项硬指标通过情况
- `overall_result`: `pass | strong_pass | fail`
- `main_issue`: 本场唯一主问题（用于报告页直达修正）
- `next_goal`: 下一轮唯一目标
- `retry_entry`: 报告页一键再练参数（scenario/agent/persona/presentation）

### 历史列表字段补充（首页最近记录）

`GET /api/v1/practice/history` 的 `items[]` 额外返回：

- `effectiveness_snapshot`: 本次会话效果快照（若已生成）
- `feedback_summary`: 快速反馈摘要（优先取 `main_issue.issue_text`，缺失时回退 `next_goal.goal_text`）

---

## 创建会话契约要点

### 1) 入参约束

- `agent_id` 与 `persona_id` 必须成对提供
- `sales` 场景必须传 `agent_id + persona_id`
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
    "runtime_subject": "training_scenario_runtime",
    "runtime_descriptor": {
      "subject": "training_scenario_runtime",
      "session_id": "session-uuid",
      "scenario_type": "sales",
      "agent_id": "agent-uuid",
      "persona_id": "persona-uuid",
      "presentation_id": null,
      "voice_mode": "stepfun_realtime",
      "runtime_profile_id": "profile-uuid"
    },
    "runtime_profile_id": "profile-uuid",
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
      "instruction_contract_hash": "sha256:xxxx",
      "network_access_mode": "off",
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
    "runtime_subject": "training_scenario_runtime",
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

- 所有会话接口要求有效登录态，支持 `Authorization: Bearer <token>` 或 `HttpOnly` session cookie
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
| `[PRESENTATION_ID_REQUIRED]` | `400` | `presentation` 场景未传 `presentation_id` |
| `[FIELD_DEPRECATED_PERSONA_CENTERED]` | `400` | 请求中仍传入已废弃的 `sales_persona` |
| `[SESSION_CREATE_FAILED]` | `500` | 建会话失败 |

---

## 向后兼容说明

- `sales_persona` 仅保留为兼容入参占位，不再支持创建路径
- 新增字段全部为 additive（不会破坏既有消费方）
- 契约回归覆盖:
  - `backend/tests/contract/test_sessions.py`
  - `backend/tests/contract/test_sales_sessions.py`

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-02-22 | 收敛销售建会话入参 | `sales` 场景必须使用 `agent_id + persona_id`，`sales_persona` 标记废弃并返回明确错误码 |
| 2026-02-11 | 补充生命周期状态机细节 | 明确 start/pause/resume/end 允许来源状态、幂等语义、终态差异（sales=scoring、presentation=completed） |
| 2026-02-11 | 补充 lifecycle 对应 WS 契约 | 增加 `status` / `session_ended` 广播事件结构，统一 REST 与实时通道语义 |
| 2026-02-11 | 新增 lifecycle 契约 | 补齐 `POST /practice/sessions/{session_id}/lifecycle` 请求/响应与错误语义 |
| 2026-02-11 | 新增 sessions 契约文档 | 对齐会话创建快照固化与读取一致性语义 |
| 2026-02-11 | 补充访问控制与错误码 | 覆盖增强模式校验、legacy 兼容和权限边界 |
