# Agent 管理 API 契约

> 状态: ✅ 已实现（2026-02-10 更新）
>
> 后端实现: `backend/src/agent/api/agents.py`
>
> 相关 Schema: `backend/src/agent/schemas.py`

## 概览

- 基础路径: `/api/v1`
- 认证方式: `Authorization: Bearer <token>`
- 响应包裹: 统一为 `{ "success": true, "data": ... }`
- 管理端接口要求管理员身份（`get_current_admin_user`）

---

## 关键模型

### `AgentResponse`（管理端详情）

```typescript
interface AgentResponse {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  category: "sales" | "presentation" | "interview" | "customer_service";
  system_prompt?: string;
  welcome_message?: string;
  capabilities_config: Record<string, unknown>;
  default_knowledge_base_ids: string[];
  status: "draft" | "published" | "archived";
  version: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
  published_at?: string;
}
```

### `AgentUserResponse`（用户端详情）

```typescript
interface AgentUserResponse {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  category: "sales" | "presentation" | "interview" | "customer_service";
  welcome_message?: string;
  capabilities: string[];
}
```

### `PersonaUserListItem`（用户端 Agent 关联角色）

```typescript
interface PersonaUserListItem {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  difficulty: "easy" | "medium" | "hard";
  is_default: boolean;
}
```

---

## 已实现接口清单

### 管理端

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/admin/agents` | 创建 Agent（默认 `draft`） |
| `GET` | `/api/v1/admin/agents` | 分页查询 Agent |
| `GET` | `/api/v1/admin/agents/{agent_id}` | 查询 Agent 详情 |
| `PUT` | `/api/v1/admin/agents/{agent_id}` | 部分更新 Agent |
| `DELETE` | `/api/v1/admin/agents/{agent_id}` | 删除 Agent |
| `POST` | `/api/v1/admin/agents/{agent_id}/publish` | 发布 Agent |
| `POST` | `/api/v1/admin/agents/{agent_id}/archive` | 归档 Agent |
| `POST` | `/api/v1/admin/agents/{agent_id}/unpublish` | 下线 Agent（回退 `draft`） |

### 用户端

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/agents` | 查询已发布 Agent 列表 |
| `GET` | `/api/v1/agents/{agent_id}` | 查询 Agent 详情（不返回 `system_prompt`） |
| `GET` | `/api/v1/agents/{agent_id}/personas` | 查询 Agent 可用 Persona 列表 |

---

## 典型请求与响应

### 创建 Agent

```http
POST /api/v1/admin/agents
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "name": "销售教练",
  "description": "帮助销售人员提升沟通技巧的 AI 教练",
  "icon": "🎯",
  "category": "sales",
  "system_prompt": "你是一位资深销售教练...",
  "welcome_message": "你好！准备好练习了吗？",
  "capabilities_config": {
    "asr": {"enabled": true},
    "tts": {"enabled": true}
  },
  "default_knowledge_base_ids": ["kb-product-001"]
}
```

```json
{
  "success": true,
  "data": {
    "id": "agent-uuid-001",
    "name": "销售教练",
    "status": "draft",
    "created_at": "2026-02-10T10:00:00Z"
  }
}
```

### 获取 Agent 列表（管理端）

```http
GET /api/v1/admin/agents?page=1&page_size=20&category=sales&status=draft
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "agents": [
      {
        "id": "agent-uuid-001",
        "name": "销售教练",
        "description": "帮助销售人员提升沟通技巧",
        "icon": "🎯",
        "category": "sales",
        "status": "draft",
        "persona_count": 2
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 发布 / 归档 / 下线 Agent

```http
POST /api/v1/admin/agents/{agent_id}/publish
POST /api/v1/admin/agents/{agent_id}/archive
POST /api/v1/admin/agents/{agent_id}/unpublish
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "id": "agent-uuid-001",
    "status": "published",
    "published_at": "2026-02-10T12:00:00Z"
  }
}
```

> `archive` / `unpublish` 响应为 `{ "id": "...", "status": "..." }`。

### 获取 Agent 详情（用户端）

```http
GET /api/v1/agents/{agent_id}
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "id": "agent-uuid-001",
    "name": "销售教练",
    "description": "帮助销售人员提升沟通技巧",
    "icon": "🎯",
    "category": "sales",
    "welcome_message": "你好！准备好练习了吗？",
    "capabilities": ["asr", "tts", "llm"]
  }
}
```

### 获取 Agent Persona 列表（用户端）

```http
GET /api/v1/agents/{agent_id}/personas
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "persona-001",
        "name": "怀疑型客户",
        "description": "关注证据与数据",
        "icon": "😤",
        "difficulty": "hard",
        "is_default": true
      }
    ]
  }
}
```

---

## 错误码（当前实现）

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `[AGENT_NOT_FOUND]` | `404` | Agent 不存在 |
| `[AGENT_CANNOT_DELETE]` | `400` | Agent 存在关联会话，无法删除 |
| `[AGENT_ALREADY_PUBLISHED]` | `400` | 重复发布 |
| `[AGENT_ALREADY_DRAFT]` | `400` | 已是草稿状态，再次下线 |
| `[AGENT_CREATE_FAILED]` | `400` | 创建失败（服务层返回） |

> 生命周期约束（跨模块）：
>
> - 当 Agent 状态为 `archived` 时，`POST /api/v1/practice/sessions` 返回 `400` + `[AGENT_ARCHIVED]`，禁止新建训练会话。
> - 启用 Agent/Persona 增强模式时，`agent_id` 与 `persona_id` 必须成对提供；仅传其一将返回 `400` + `[AGENT_PERSONA_PAIR_REQUIRED]`。

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-02-10 | 契约状态改为已实现 | 对齐 `agents.py` 真实路由 |
| 2026-02-10 | 增补 `unpublish` 生命周期接口 | 补齐 `/admin/agents/{agent_id}/unpublish` |
| 2026-02-10 | 清理历史规划引用 | 移除已废弃 roadmap 引用与旧示例 |
| 2026-02-11 | 补充归档场景会话保护约束 | 记录 `archived` Agent 在会话创建入口的拒绝语义 `[AGENT_ARCHIVED]` |
| 2026-02-11 | 补充增强模式参数配对约束 | 记录 `agent_id/persona_id` 需成对传入，错误码 `[AGENT_PERSONA_PAIR_REQUIRED]` |
