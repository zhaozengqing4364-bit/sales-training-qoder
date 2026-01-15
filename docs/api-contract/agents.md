# Agent 管理 API 契约

> 状态: 📋 计划中
> 
> 参考: `docs/roadmap/backend-gap-analysis.md` - 2.1 Agent 管理 API

## 数据模型

### Agent 实体

```typescript
interface Agent {
  id: string;                              // UUID
  name: string;                            // 名称，最大 100 字符
  description: string;                     // 描述，最大 500 字符
  icon: string;                            // 图标 URL 或 emoji
  category: 'sales' | 'presentation' | 'interview' | 'customer_service';
  
  system_prompt: string;                   // 系统提示词
  welcome_message: string;                 // 欢迎消息
  capabilities_config: Record<string, CapabilityConfig>;  // 能力配置
  default_knowledge_base_ids: string[];    // 默认知识库 ID 列表
  
  status: 'draft' | 'published' | 'archived';
  version: number;
  
  created_by: string;                      // 创建者 user_id
  created_at: string;                      // ISO8601
  updated_at: string;                      // ISO8601
  published_at?: string;                   // ISO8601，发布时间
}
```

### 能力配置

```typescript
interface CapabilityConfig {
  enabled: boolean;
  [key: string]: unknown;
}

// 示例
{
  "asr": {
    "enabled": true,
    "mode": "manual",
    "language": "zh-CN"
  },
  "tts": {
    "enabled": true,
    "voice": "zh-CN-YunxiNeural",
    "rate": "+10%"
  },
  "llm": {
    "enabled": true,
    "model": "deepseek-chat",
    "temperature": 0.8,
    "max_tokens": 500
  },
  "fuzzy_detection": {
    "enabled": true,
    "detection_mode": "realtime",
    "cooldown_seconds": 10
  },
  "scoring": {
    "enabled": true,
    "dimensions": [
      {"name": "专业度", "weight": 0.25},
      {"name": "沟通技巧", "weight": 0.25}
    ]
  }
}
```

---

## API 端点

### 管理端 API

#### 创建 Agent

```http
POST /api/v1/admin/agents
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体:**
```json
{
  "name": "销售教练",
  "description": "帮助销售人员提升沟通技巧的 AI 教练",
  "icon": "🎯",
  "category": "sales",
  "system_prompt": "你是一位资深销售教练...",
  "welcome_message": "你好！准备好练习了吗？",
  "capabilities_config": {
    "asr": {"enabled": true, "mode": "manual"},
    "tts": {"enabled": true, "voice": "zh-CN-YunxiNeural"}
  },
  "default_knowledge_base_ids": ["kb-product-001"]
}
```

**响应 (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": "agent-uuid-001",
    "name": "销售教练",
    "status": "draft",
    "created_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 获取 Agent 列表 (管理端)

```http
GET /api/v1/admin/agents?page=1&page_size=20&category=sales&status=draft
Authorization: Bearer <token>
```

**响应:**
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
        "persona_count": 4
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  },
  "trace_id": "abc123"
}
```

#### 获取 Agent 详情 (管理端)

```http
GET /api/v1/admin/agents/{agent_id}
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "agent-uuid-001",
    "name": "销售教练",
    "description": "帮助销售人员提升沟通技巧",
    "icon": "🎯",
    "category": "sales",
    "system_prompt": "你是一位资深销售教练...",
    "welcome_message": "你好！准备好练习了吗？",
    "capabilities_config": {...},
    "default_knowledge_base_ids": ["kb-product-001"],
    "status": "draft",
    "version": 1,
    "created_by": "user-001",
    "created_at": "2025-01-11T10:00:00Z",
    "updated_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 更新 Agent

```http
PUT /api/v1/admin/agents/{agent_id}
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体 (部分更新):**
```json
{
  "name": "智能销售教练 v2",
  "capabilities_config": {
    "fuzzy_detection": {"enabled": true}
  }
}
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "agent-uuid-001",
    "name": "智能销售教练 v2",
    "updated_at": "2025-01-11T11:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 删除 Agent

```http
DELETE /api/v1/admin/agents/{agent_id}
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "deleted": true
  },
  "trace_id": "abc123"
}
```

#### 发布 Agent

```http
POST /api/v1/admin/agents/{agent_id}/publish
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "agent-uuid-001",
    "status": "published",
    "published_at": "2025-01-11T12:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 归档 Agent

```http
POST /api/v1/admin/agents/{agent_id}/archive
Authorization: Bearer <token>
```

---

### 用户端 API

#### 获取已发布 Agent 列表

```http
GET /api/v1/agents?category=sales
Authorization: Bearer <token>
```

**响应:**
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
        "persona_count": 4
      }
    ],
    "total": 1
  },
  "trace_id": "abc123"
}
```

#### 获取 Agent 详情 (用户端)

```http
GET /api/v1/agents/{agent_id}
Authorization: Bearer <token>
```

**响应:**
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
    "capabilities": ["语音对话", "实时反馈", "多维评分"]
  },
  "trace_id": "abc123"
}
```

#### 获取 Agent 角色列表

```http
GET /api/v1/agents/{agent_id}/personas
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "persona-001",
        "name": "怀疑型客户",
        "description": "对销售人员说的每句话都要求证据",
        "icon": "😤",
        "difficulty": "hard",
        "is_default": true
      },
      {
        "id": "persona-002",
        "name": "价格敏感型",
        "description": "只关心价格，不断要求折扣",
        "icon": "💰",
        "difficulty": "medium",
        "is_default": false
      }
    ]
  },
  "trace_id": "abc123"
}
```

---

## 错误码

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `[AGENT_NOT_FOUND]` | 404 | Agent 不存在 |
| `[AGENT_NAME_EXISTS]` | 400 | Agent 名称已存在 |
| `[AGENT_CANNOT_DELETE]` | 400 | Agent 有关联会话，无法删除 |
| `[AGENT_ALREADY_PUBLISHED]` | 400 | Agent 已发布 |
| `[INVALID_CAPABILITY_CONFIG]` | 400 | 能力配置无效 |

---

## 前端类型定义

参考: `frontend/src/types/api-future.ts`

```typescript
// 已定义类型
export interface APIAgent { ... }
export interface APIAgentListItem { ... }
export interface APICreateAgentRequest { ... }
export interface APIUpdateAgentRequest { ... }
export interface APIAgentListResponse { ... }
```
