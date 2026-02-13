# 支持角色运行状态 API 契约

> 状态: ✅ 已实现（2026-02-11 更新）
>
> 后端实现: `backend/src/support/api/runtime_status.py`

## 概览

- 基础路径: `/api/v1/support/runtime`
- 认证方式: `Authorization: Bearer <token>`
- 角色要求: `support` 或 `admin`
- 能力边界: **只读**（不包含任何策略变更、发布、回滚写操作）

## 统一响应

```json
{
  "success": true,
  "data": {},
  "trace_id": "abc123"
}
```

---

## 运行概览

```http
GET /api/v1/support/runtime/overview?window_hours=24
```

### Query 参数

- `window_hours` (可选，默认 `24`，范围 `1~168`)

### 响应结构

```json
{
  "generated_at": "2026-02-11T04:00:00Z",
  "window_hours": 24,
  "session_health": {
    "active_sessions": 3,
    "total_sessions_window": 28,
    "completed_sessions_window": 24,
    "completion_rate": 85.71
  },
  "fault_health": {
    "failed_or_warning_logs_window": 5
  }
}
```

---

## 故障摘要

```http
GET /api/v1/support/runtime/faults?limit=20&status=failed
```

### Query 参数

- `limit` (可选，默认 `20`，范围 `1~100`)
- `status` (可选): `failed` / `warning`

### 响应结构

```json
{
  "generated_at": "2026-02-11T04:00:00Z",
  "count": 2,
  "limit": 20,
  "items": [
    {
      "log_id": "0f9b...",
      "action": "admin.user.updated",
      "status": "failed",
      "user_identifier": "admin@example.com",
      "created_at": "2026-02-11T03:58:12Z",
      "details": {
        "reason": "..."
      }
    }
  ]
}
```

---

## 鉴权与错误语义

- 未认证：`401`
- 已认证但角色不满足：`403`
- 非法 `status` 过滤值：`400` + `"[INVALID_STATUS_FILTER]"`（仅允许 `failed` / `warning`）
- 错误响应遵循统一结构，包含 `trace_id`
