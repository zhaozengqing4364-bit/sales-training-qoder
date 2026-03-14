# Persona 管理 API 契约

> 状态: ✅ 已实现（2026-02-16 更新）
>
> 后端实现: `backend/src/agent/api/personas.py`
>
> 关联实现: `backend/src/agent/api/agent_personas.py`
>
> 相关 Schema: `backend/src/agent/schemas.py`

## 概览

- 基础路径: `/api/v1`
- 认证方式: `Authorization: Bearer <token>`
- 响应包裹: 统一为 `{ "success": true, "data": ... }`
- 本文覆盖两组接口：
  - Persona 本体管理（`/admin/personas`）
  - Agent-Persona 关联管理（`/admin/agents/{agent_id}/personas`）

---

## 关键模型

### `PersonaResponse`

```typescript
interface PersonaResponse {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  category: "customer" | "interviewer" | "coach" | "examiner";
  difficulty: "easy" | "medium" | "hard";
  system_prompt: string;
  traits: Record<string, string>;
  knowledge_base_ids: string[];
  persona_policy: {
    version: number;
    system_prompt: string;
    knowledge_base_ids: string[];
    tool_policy: Record<string, unknown>;
    [key: string]: unknown;
  };
  behavior_config: Record<string, unknown>;
  scoring_weights?: Record<string, number>;
  tts_config?: Record<string, unknown>;
  is_public: boolean;
  status: "active" | "inactive";
  created_by?: string;
  created_at: string;
  updated_at: string;
}
```

### `CreateAgentPersonaRequest`

```typescript
interface CreateAgentPersonaRequest {
  persona_id: string;
  display_order?: number;
  is_default?: boolean;
  override_config?: Record<string, unknown>;
}
```

### `AgentPersonaResponse`

```typescript
interface AgentPersonaResponse {
  id: string;
  agent_id: string;
  persona_id: string;
  display_order: number;
  is_default: boolean;
  override_config?: Record<string, unknown>;
  created_at: string;
}
```

---

## 已实现接口清单

### Persona 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/admin/personas` | 创建 Persona |
| `GET` | `/api/v1/admin/personas` | 分页查询 Persona |
| `GET` | `/api/v1/admin/personas/policy-health` | 角色策略健康审计报告 |
| `GET` | `/api/v1/admin/personas/{persona_id}` | 查询 Persona 详情 |
| `PUT` | `/api/v1/admin/personas/{persona_id}` | 更新 Persona |
| `DELETE` | `/api/v1/admin/personas/{persona_id}` | 删除 Persona |
| `POST` | `/api/v1/admin/personas/{persona_id}/duplicate` | 复制 Persona |

### Agent-Persona 关联管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/admin/agents/{agent_id}/personas` | 添加 Persona 到 Agent |
| `GET` | `/api/v1/admin/agents/{agent_id}/personas` | 查询 Agent 关联 Persona 列表 |
| `PUT` | `/api/v1/admin/agents/{agent_id}/personas/{persona_id}` | 更新关联配置 |
| `DELETE` | `/api/v1/admin/agents/{agent_id}/personas/{persona_id}` | 删除关联 |

---

## 角色中心策略约束

- Persona 的 `persona_policy` 是角色提示词与知识库绑定的单一事实源（source-of-truth）。
- 兼容字段 `system_prompt`、`knowledge_base_ids` 仍会返回，但后端会与 `persona_policy` 同步。
- 推荐写法：
  - 始终在 `POST /admin/personas`、`PUT /admin/personas/{persona_id}` 显式提交 `persona_policy`。
  - `persona_policy.system_prompt` 与 `persona_policy.knowledge_base_ids` 作为生效值。

## 生命周期约束（1.7 新增）

- Persona 默认状态为 `active`，可通过 `PUT /api/v1/admin/personas/{persona_id}` 更新为 `inactive`。
- `inactive` Persona 不能被新增到 Agent 关联（`POST /api/v1/admin/agents/{agent_id}/personas`）。
- 训练会话在增强模式（`agent_id + persona_id`）下，若引用 `inactive` Persona，必须拒绝创建并返回错误码。
- Agent 若处于 `archived` 状态，禁止新建/更新 Agent-Persona 关联配置。
- 增强模式建会话读取到关联 `override_config` 时，应将其写入会话快照 `voice_policy_snapshot.agent_persona_override_config`。

---

## 典型请求与响应

### 创建 Persona

```http
POST /api/v1/admin/personas
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "name": "怀疑型客户",
  "description": "关注证据与数据的高压客户",
  "icon": "😤",
  "category": "customer",
  "difficulty": "hard",
  "system_prompt": "你是一个重视证据的客户...",
  "traits": {
    "性格": "谨慎",
    "关注点": "ROI、案例、风控"
  },
  "knowledge_base_ids": ["kb-product-001"],
  "persona_policy": {
    "version": 1,
    "system_prompt": "你是一个重视证据的客户...",
    "knowledge_base_ids": ["kb-product-001"],
    "tool_policy": {
      "retrieval_priority": "kb_only",
      "require_kb_grounding": true
    }
  },
  "behavior_config": {
    "response_length": "medium",
    "challenge_frequency": 0.8,
    "interruption_triggers": ["对比", "证据"],
    "typical_questions": ["有没有真实案例？"]
  },
  "is_public": true
}
```

```json
{
  "success": true,
  "data": {
    "id": "persona-uuid-001",
    "name": "怀疑型客户",
    "status": "active",
    "created_at": "2026-02-10T10:00:00Z"
  }
}
```

### 获取 Persona 列表

```http
GET /api/v1/admin/personas?page=1&page_size=20&category=customer&difficulty=hard&status=active
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "persona-uuid-001",
        "name": "怀疑型客户",
        "description": "关注证据与数据的高压客户",
        "icon": "😤",
        "category": "customer",
        "difficulty": "hard",
        "is_public": true,
        "usage_count": 18,
        "agent_count": 3
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 复制 Persona

```http
POST /api/v1/admin/personas/{persona_id}/duplicate
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "id": "persona-uuid-002",
    "name": "怀疑型客户 (副本)",
    "status": "active",
    "created_at": "2026-02-10T11:00:00Z"
  }
}
```

### 查询 Persona 策略健康报告

```http
GET /api/v1/admin/personas/policy-health?sample_limit=50
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "generated_at": "2026-02-16T12:00:00+00:00",
    "summary": {
      "total": 18,
      "healthy": 16,
      "with_issues": 2
    },
    "issue_type_counts": {
      "missing_policy": 1,
      "kb_lock_unbound": 1
    },
    "sample_issues": [
      {
        "persona_id": "persona-uuid-001",
        "persona_name": "怀疑型客户",
        "issue_types": ["kb_lock_unbound"],
        "policy_version": 1,
        "require_kb_grounding": true
      }
    ]
  }
}
```

### 添加 Persona 到 Agent

```http
POST /api/v1/admin/agents/{agent_id}/personas
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "persona_id": "persona-uuid-001",
  "display_order": 1,
  "is_default": true,
  "override_config": {
    "challenge_frequency": 0.7
  }
}
```

```json
{
  "success": true,
  "data": {
    "id": "link-uuid-001",
    "agent_id": "agent-uuid-001",
    "persona_id": "persona-uuid-001",
    "display_order": 1,
    "is_default": true,
    "override_config": {
      "challenge_frequency": 0.7
    },
    "created_at": "2026-02-10T11:30:00Z"
  }
}
```

### 查询 Agent 关联 Persona 列表

```http
GET /api/v1/admin/agents/{agent_id}/personas
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "link-uuid-001",
        "agent_id": "agent-uuid-001",
        "persona_id": "persona-uuid-001",
        "display_order": 1,
        "is_default": true,
        "override_config": null,
        "created_at": "2026-02-10T11:30:00Z",
        "persona": {
          "id": "persona-uuid-001",
          "name": "怀疑型客户",
          "description": "关注证据与数据的高压客户",
          "icon": "😤",
          "category": "customer",
          "difficulty": "hard",
          "is_public": true,
          "usage_count": 18,
          "agent_count": 3
        }
      }
    ]
  }
}
```

---

## 错误码（当前实现）

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `[PERSONA_NOT_FOUND]` | `404` | Persona 不存在 |
| `[PERSONA_IN_USE]` | `400` | Persona 已被 Agent 关联，禁止删除 |
| `[PERSONA_ALREADY_LINKED]` | `400` | 关联重复创建 |
| `[AGENT_NOT_FOUND]` | `404` | 关联管理时 Agent 不存在 |
| `[AGENT_ARCHIVED]` | `400` | Agent 已归档，禁止保存关联配置 |
| `[PERSONA_INACTIVE]` | `400` | Persona 已停用，禁止新建关联或会话引用 |
| `[PERSONA_CREATE_FAILED]` | `400` | 创建失败（服务层返回） |
| `[PERSONA_DUPLICATE_FAILED]` | `404` | 复制失败（服务层返回） |

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-02-10 | 契约状态改为已实现 | 对齐 `personas.py` 与 `agent_personas.py` |
| 2026-02-10 | 补齐关联接口返回结构 | 明确 `persona` 嵌套详情与关联字段 |
| 2026-02-10 | 清理历史规划引用 | 移除已废弃 roadmap 引用与旧示例 |
| 2026-02-11 | 补充 Persona 生命周期约束 | 新增 `[PERSONA_INACTIVE]` 拒绝语义，明确停用 Persona 不可新建关联/会话 |
| 2026-02-11 | 补充关联可用性与会话应用约束 | 新增 `[AGENT_ARCHIVED]`，并约定会话快照写入 `agent_persona_override_config` |
| 2026-02-16 | 收敛角色策略到 `persona_policy` | 明确 `persona_policy` 为角色提示词/知识库/工具策略唯一事实源 |
| 2026-02-16 | 新增 Persona 策略健康审计接口 | 提供 `/admin/personas/policy-health` 统计缺失策略、漂移与 KB 锁未绑定问题 |
