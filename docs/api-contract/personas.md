# Persona 管理 API 契约

> 状态: 📋 计划中
> 
> 参考: `docs/roadmap/backend-gap-analysis.md` - 2.2 Persona 管理 API

## 数据模型

### Persona 实体

```typescript
interface Persona {
  id: string;                              // UUID
  name: string;                            // 名称，最大 100 字符
  description: string;                     // 描述，最大 500 字符
  icon: string;                            // emoji 或图标名
  category: 'customer' | 'interviewer' | 'coach' | 'examiner';
  difficulty: 'easy' | 'medium' | 'hard';
  
  system_prompt: string;                   // 核心: 角色提示词
  traits: Record<string, string>;          // 角色特征
  knowledge_base_ids: string[];            // 专属知识库 ID 列表
  behavior_config: BehaviorConfig;         // 行为配置
  scoring_weights?: Record<string, number>; // 评分权重覆盖
  
  is_public: boolean;                      // 是否公开可用
  status: 'active' | 'inactive';
  
  created_by: string;
  created_at: string;
  updated_at: string;
}
```

### 行为配置

```typescript
interface BehaviorConfig {
  response_length: 'short' | 'medium' | 'long';  // 回复长度
  challenge_frequency: number;                    // 挑战频率 0-1
  interruption_triggers: string[];                // 打断触发词
  typical_questions: string[];                    // 典型问题
}

// 示例
{
  "response_length": "medium",
  "challenge_frequency": 0.7,
  "interruption_triggers": ["竞品", "对比", "优势"],
  "typical_questions": [
    "你说的这个数据有什么依据？",
    "你们和XX公司比有什么优势？"
  ]
}
```

### Agent-Persona 关联

```typescript
interface AgentPersona {
  id: string;
  agent_id: string;
  persona_id: string;
  display_order: number;                   // 显示顺序
  is_default: boolean;                     // 是否默认选中
  override_config?: Record<string, unknown>; // 覆盖配置
}
```

---

## API 端点

### 管理端 API

#### 创建 Persona

```http
POST /api/v1/admin/personas
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体:**
```json
{
  "name": "怀疑型客户",
  "description": "对销售人员说的每句话都要求证据，喜欢质疑",
  "icon": "😤",
  "category": "customer",
  "difficulty": "hard",
  "system_prompt": "你是一个非常怀疑的客户，有以下特点:\n1. 对销售人员说的每句话都持怀疑态度\n2. 经常要求提供数据、案例或证据来支持说法\n3. 会主动提出竞品对比的问题",
  "traits": {
    "性格": "怀疑、谨慎",
    "关注点": "证据、数据、案例",
    "沟通风格": "追问细节、要求证明"
  },
  "knowledge_base_ids": ["kb-product", "kb-competitor"],
  "behavior_config": {
    "response_length": "medium",
    "challenge_frequency": 0.8,
    "interruption_triggers": ["竞品", "对比", "优势", "证据"],
    "typical_questions": [
      "你说的这个数据有什么依据？",
      "你们和XX公司比有什么优势？",
      "能给我看看具体的客户案例吗？"
    ]
  },
  "scoring_weights": {
    "专业度": 0.3,
    "异议处理": 0.4,
    "沟通技巧": 0.2,
    "成交能力": 0.1
  }
}
```

**响应 (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": "persona-uuid-001",
    "name": "怀疑型客户",
    "status": "active",
    "created_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 获取 Persona 列表

```http
GET /api/v1/admin/personas?page=1&page_size=20&category=customer&difficulty=hard
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "persona-uuid-001",
        "name": "怀疑型客户",
        "description": "对销售人员说的每句话都要求证据",
        "icon": "😤",
        "category": "customer",
        "difficulty": "hard",
        "is_public": true,
        "usage_count": 234,
        "agent_count": 3
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  },
  "trace_id": "abc123"
}
```

#### 获取 Persona 详情

```http
GET /api/v1/admin/personas/{persona_id}
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "persona-uuid-001",
    "name": "怀疑型客户",
    "description": "对销售人员说的每句话都要求证据",
    "icon": "😤",
    "category": "customer",
    "difficulty": "hard",
    "system_prompt": "你是一个非常怀疑的客户...",
    "traits": {
      "性格": "怀疑、谨慎",
      "关注点": "证据、数据、案例"
    },
    "knowledge_base_ids": ["kb-product", "kb-competitor"],
    "behavior_config": {
      "response_length": "medium",
      "challenge_frequency": 0.8,
      "interruption_triggers": ["竞品", "对比"],
      "typical_questions": [...]
    },
    "scoring_weights": {...},
    "is_public": true,
    "status": "active",
    "created_by": "user-001",
    "created_at": "2025-01-11T10:00:00Z",
    "updated_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 更新 Persona

```http
PUT /api/v1/admin/personas/{persona_id}
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体 (部分更新):**
```json
{
  "difficulty": "medium",
  "behavior_config": {
    "challenge_frequency": 0.6
  }
}
```

#### 删除 Persona

```http
DELETE /api/v1/admin/personas/{persona_id}
Authorization: Bearer <token>
```

#### 复制 Persona

```http
POST /api/v1/admin/personas/{persona_id}/duplicate
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "persona-uuid-002",
    "name": "怀疑型客户 (副本)",
    "created_at": "2025-01-11T11:00:00Z"
  },
  "trace_id": "abc123"
}
```

---

### Agent-Persona 关联 API

#### 添加 Persona 到 Agent

```http
POST /api/v1/admin/agents/{agent_id}/personas
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体:**
```json
{
  "persona_id": "persona-uuid-001",
  "display_order": 1,
  "is_default": true,
  "override_config": {
    "difficulty": "medium"
  }
}
```

#### 获取 Agent 的 Persona 列表

```http
GET /api/v1/admin/agents/{agent_id}/personas
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "ap-001",
        "agent_id": "agent-uuid-001",
        "persona_id": "persona-uuid-001",
        "persona": {
          "id": "persona-uuid-001",
          "name": "怀疑型客户",
          "icon": "😤",
          "difficulty": "hard"
        },
        "display_order": 1,
        "is_default": true,
        "override_config": null
      }
    ]
  },
  "trace_id": "abc123"
}
```

#### 更新 Agent-Persona 关联

```http
PUT /api/v1/admin/agents/{agent_id}/personas/{persona_id}
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体:**
```json
{
  "display_order": 2,
  "is_default": false
}
```

#### 移除 Persona 从 Agent

```http
DELETE /api/v1/admin/agents/{agent_id}/personas/{persona_id}
Authorization: Bearer <token>
```

---

## 错误码

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `[PERSONA_NOT_FOUND]` | 404 | Persona 不存在 |
| `[PERSONA_NAME_EXISTS]` | 400 | Persona 名称已存在 |
| `[PERSONA_IN_USE]` | 400 | Persona 正在被使用，无法删除 |
| `[PERSONA_ALREADY_LINKED]` | 400 | Persona 已关联到该 Agent |
| `[INVALID_BEHAVIOR_CONFIG]` | 400 | 行为配置无效 |

---

## 前端类型定义

参考: `frontend/src/types/api-future.ts`

```typescript
// 已定义类型
export interface APIPersona { ... }
export interface APIPersonaListItem { ... }
export interface APIPersonaBehaviorConfig { ... }
export interface APICreatePersonaRequest { ... }
export interface APIAgentPersona { ... }
```
