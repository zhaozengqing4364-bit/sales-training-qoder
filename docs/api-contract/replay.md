# 对话回放 API 契约

> 状态: ✅ 已实现（含会话策略快照引用）
>
> 目标: 回放/高光/消息读取统一引用 `practice_sessions.voice_policy_snapshot`，不在读取链路重算策略

## 访问控制

- 所有回放接口要求有效登录态，支持 `Authorization: Bearer <token>` 或 `HttpOnly` session cookie
- 仅会话 owner 或 admin 可访问
- 未认证返回 `401`
- 越权返回 `403`（`[ACCESS_DENIED]`）

## 统一响应格式

```json
{
  "success": true,
  "data": {},
  "trace_id": "trace-xxx"
}
```

## 数据模型（关键）

### `voice_policy_snapshot_ref`

```json
{
  "voice_mode": "stepfun_realtime",
  "runtime_profile_id": "uuid-or-null",
  "tool_policy": {
    "enable_internal_retrieval": true
  },
  "knowledge_base_ids": ["kb-001"],
  "source": {
    "runtime_profile": "system_default",
    "voice_mode": "session_override"
  },
  "resolved_at": "2026-02-11T12:00:00+00:00",
  "agent_persona_override_config": {
    "response_length": "short"
  }
}
```

> 说明: 该对象来自会话创建时的快照基线；读取接口不重新解析策略。

## API 端点

### 1) 获取消息列表

`GET /api/v1/sessions/{session_id}/messages?page=1&page_size=50`

返回:

```json
{
  "messages": [
    {
      "id": "msg-001",
      "session_id": "session-uuid",
      "turn_number": 1,
      "role": "assistant",
      "content": "你好...",
      "timestamp": "2026-02-11T12:00:00+00:00",
      "duration_ms": 3200,
      "sales_stage": "opening",
      "is_highlight": false
    }
  ],
  "total": 12
}
```

### 2) 获取单条消息详情

`GET /api/v1/sessions/{session_id}/messages/{message_id}`

### 3) 获取回放数据

`GET /api/v1/sessions/{session_id}/replay`

返回关键字段:

```json
{
  "session_id": "session-uuid",
  "agent_name": "销售教练",
  "persona_name": "怀疑型客户",
  "voice_policy_snapshot_ref": {
    "voice_mode": "stepfun_realtime",
    "runtime_profile_id": "uuid-or-null",
    "tool_policy": {},
    "knowledge_base_ids": [],
    "source": {},
    "resolved_at": "2026-02-11T12:00:00+00:00"
  },
  "total_duration_ms": 512000,
  "messages": [],
  "timeline_markers": [],
  "stage_summary": []
}
```

### 4) 获取高光片段

`GET /api/v1/sessions/{session_id}/highlights`

### 5) 获取消息音频

`GET /api/v1/sessions/{session_id}/audio/{message_id}`

- 远程 URL 返回重定向
- 本地文件返回音频流

## 错误码

| 错误码 | HTTP 状态 | 说明 |
|---|---:|---|
| `[ACCESS_DENIED]` | 403 | 非 owner/admin 访问 |
| `[SESSION_NOT_FOUND]` | 404 | 会话不存在 |
| `[SESSION_NOT_COMPLETED]` | 400 | 会话未完成，不能回放 |
| `[MESSAGE_NOT_FOUND]` | 404 | 消息不存在 |
| `[AUDIO_NOT_AVAILABLE]` | 404 | 音频不存在 |

## 一致性约束

- 回放接口中的 `voice_policy_snapshot_ref` 必须与会话详情/报告返回一致
- 允许追加 `runtime_metrics`，但不得改写策略基线字段
- 所有字段保持 `snake_case`
