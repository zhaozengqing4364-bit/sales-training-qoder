# 后端 API 参数文档

> 最后更新: 2026-01-12
> 版本: v1

本文档包含所有后端 API 端点的请求参数和响应格式。

---

## 目录

1. [认证 API](#1-认证-api)
2. [用户 API](#2-用户-api)
3. [仪表盘 API](#3-仪表盘-api)
4. [训练 API](#4-训练-api)
5. [练习会话 API](#5-练习会话-api)
6. [Agent 管理 API](#6-agent-管理-api)
7. [Persona 管理 API](#7-persona-管理-api)
8. [Agent-Persona 关联 API](#8-agent-persona-关联-api)
9. [知识库 API](#9-知识库-api)
10. [会话回放 API](#10-会话回放-api)
11. [演示文稿 API](#11-演示文稿-api)
12. [销售场景 API](#12-销售场景-api)
13. [分析统计 API](#13-分析统计-api)
14. [管理员 API](#14-管理员-api)
15. [WebSocket API](#15-websocket-api)

---

## 统一响应格式

### 成功响应
```json
{
  "success": true,
  "data": { ... },
  "trace_id": "xxx-xxx-xxx"
}
```

### 错误响应
```json
{
  "success": false,
  "error": "[ERROR_CODE]",
  "message": "错误描述",
  "trace_id": "xxx-xxx-xxx"
}
```

### 分页响应格式
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

---

## 1. 认证 API

### POST /api/v1/auth/login

用户登录

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| email | string (EmailStr) | ✅ | 用户邮箱 |
| password | string | ✅ | 用户密码 |

**请求示例:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**响应数据:**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": "uuid",
      "name": "用户名",
      "email": "user@example.com",
      "role": "user"
    }
  }
}
```

---

### POST /api/v1/auth/logout

用户登出 (需要认证)

**请求参数:** 无

**响应数据:**
```json
{
  "success": true,
  "data": {
    "message": "登出成功"
  }
}
```

---

## 2. 用户 API

### GET /api/v1/users/me

获取当前用户信息 (需要认证)

**请求参数:** 无

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "display_name": "用户名",
    "avatar_url": "https://...",
    "role": "user",
    "department": "销售部",
    "settings": {
      "notifications_enabled": true,
      "language": "zh-CN",
      "theme": "light"
    }
  }
}
```

---

## 3. 仪表盘 API

### GET /api/v1/dashboard/stats

获取仪表盘统计数据 (需要认证)

**请求参数:** 无

**响应数据:**
```json
{
  "success": true,
  "data": {
    "weekly_activity": {
      "total_duration_minutes": 120,
      "session_count": 5,
      "trend_percentage": 15.5,
      "trend_direction": "up"
    },
    "last_session": {
      "score": 85.5,
      "percentile": 75,
      "trend": "up"
    }
  }
}
```

---

### GET /api/v1/recommendations/latest

获取训练推荐 (需要认证)

**请求参数:** 无

**响应数据:**
```json
{
  "success": true,
  "data": {
    "title": "提升逻辑性能力",
    "reason": "您上次练习的逻辑性得分为 55 分，建议针对性练习来提升。",
    "action_label": "针对练习",
    "target_path": "/training"
  }
}
```

---

## 4. 训练 API

### GET /api/v1/training-categories

获取训练分类列表

**请求参数:** 无

**响应数据:**
```json
{
  "success": true,
  "data": [
    {
      "id": "sales",
      "title": "销售对练",
      "description": "与AI客户进行销售场景模拟",
      "icon_key": "Briefcase",
      "color_theme": "bg-blue-50 text-blue-600",
      "agent_count": 5,
      "tags": ["销售", "沟通", "谈判"],
      "status": "active"
    }
  ]
}
```

---

### GET /api/v1/sessions

获取会话历史 (需要认证)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| limit | int | ❌ | 20 | 返回数量 (1-100) |
| page | int | ❌ | 1 | 页码 (≥1) |
| page_size | int | ❌ | 20 | 每页数量 (1-100) |
| sort | string | ❌ | "start_time:desc" | 排序字段和方向 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "total": 50,
    "items": [
      {
        "id": "uuid",
        "title": "销售对练 - 急躁CEO",
        "agent_type": "sales",
        "start_time": "2026-01-12T10:00:00Z",
        "duration_seconds": 1800,
        "score": 85.5
      }
    ],
    "page": 1,
    "page_size": 20,
    "has_more": true
  }
}
```

---

## 5. 练习会话 API

### POST /api/v1/practice/sessions

创建练习会话 (需要认证)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| scenario_type | string | ✅ | 场景类型: "presentation" \| "sales" |
| presentation_id | UUID | ❌ | 演示文稿ID (presentation类型必填) |
| sales_persona | string | ❌ | 销售角色 (sales类型，传统模式) |
| scenario_id | UUID | ❌ | 场景ID |
| agent_id | UUID | ❌ | Agent ID (增强模式) |
| persona_id | UUID | ❌ | Persona ID (增强模式) |

**请求示例 (增强模式):**
```json
{
  "scenario_type": "sales",
  "agent_id": "uuid-agent",
  "persona_id": "uuid-persona"
}
```

**响应数据:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "user_id": "uuid",
    "scenario_id": "uuid",
    "status": "preparing",
    "start_time": "2026-01-12T10:00:00Z"
  }
}
```

---

### GET /api/v1/practice/sessions/{session_id}

获取会话详情 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "user_id": "uuid",
    "scenario_id": "uuid",
    "status": "in_progress",
    "start_time": "2026-01-12T10:00:00Z",
    "current_page": 1,
    "interruption_count": 2
  }
}
```

---

### PATCH /api/v1/practice/sessions/{session_id}

更新会话状态 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话ID |

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| status | string | ❌ | 状态: "preparing" \| "in_progress" \| "paused" \| "completed" |
| current_page | int | ❌ | 当前页码 |

---

### DELETE /api/v1/practice/sessions/{session_id}

结束会话并生成报告 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "logic_score": 85,
    "accuracy_score": 80,
    "completeness_score": 90,
    "overall_score": 85,
    "suggestions": ["建议1", "建议2"]
  }
}
```

---

### GET /api/v1/practice/sessions/{session_id}/report

获取会话报告 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话ID |

---

### GET /api/v1/sessions/stats

获取用户会话统计 (需要认证)

**请求参数:** 无

**响应数据:**
```json
{
  "success": true,
  "data": {
    "total_sessions": 50,
    "weekly_sessions": 5,
    "average_score": 82.5,
    "completed_sessions": 45,
    "total_practice_minutes": 1500
  }
}
```

---

### GET /api/v1/sessions/{session_id}/enhanced-report

获取增强会话报告 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "overall_score": 85.5,
    "dimension_scores": [
      {"name": "逻辑性", "score": 85, "weight": 0.33},
      {"name": "准确性", "score": 80, "weight": 0.33},
      {"name": "完整性", "score": 90, "weight": 0.34}
    ],
    "strengths": ["逻辑性表现优秀"],
    "improvements": ["建议加强准确性方面的练习"],
    "suggestions": ["继续保持练习频率"],
    "highlights": [
      {
        "message_id": "uuid",
        "turn_number": 5,
        "highlight_type": "good",
        "reason": "回答清晰有力",
        "content": "..."
      }
    ],
    "total_turns": 20,
    "duration_seconds": 1800,
    "agent_name": "销售教练",
    "persona_name": "急躁CEO"
  }
}
```

---

## 6. Agent 管理 API

### POST /api/v1/admin/agents

创建 Agent (管理员)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | ✅ | Agent名称 (≤100字符) |
| description | string | ❌ | 描述 (≤500字符) |
| icon | string | ❌ | 图标 (≤50字符) |
| category | string | ✅ | 分类: "sales" \| "presentation" \| "interview" \| "customer_service" |
| system_prompt | string | ❌ | 系统提示词 |
| welcome_message | string | ❌ | 欢迎消息 |
| capabilities_config | object | ❌ | 能力模块配置 |
| default_knowledge_base_ids | string[] | ❌ | 默认知识库ID列表 |

**请求示例:**
```json
{
  "name": "销售教练",
  "description": "专业销售技能训练",
  "category": "sales",
  "system_prompt": "你是一个专业的销售教练...",
  "welcome_message": "欢迎开始销售训练！",
  "capabilities_config": {
    "fuzzy_detection": {"enabled": true},
    "sales_stage": {"enabled": true}
  }
}
```

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "销售教练",
    "status": "draft",
    "created_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### GET /api/v1/admin/agents

获取 Agent 列表 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 20 | 每页数量 (1-100) |
| category | string | ❌ | - | 按分类筛选 |
| status | string | ❌ | - | 按状态筛选 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "agents": [
      {
        "id": "uuid",
        "name": "销售教练",
        "description": "...",
        "icon": "🎯",
        "category": "sales",
        "status": "published",
        "persona_count": 5
      }
    ],
    "total": 10,
    "page": 1,
    "page_size": 20
  }
}
```

---

### GET /api/v1/admin/agents/{agent_id}

获取 Agent 详情 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "销售教练",
    "description": "...",
    "icon": "🎯",
    "category": "sales",
    "system_prompt": "你是一个专业的销售教练...",
    "welcome_message": "欢迎开始训练！",
    "capabilities_config": {},
    "default_knowledge_base_ids": [],
    "status": "published",
    "version": 1,
    "created_by": "uuid",
    "created_at": "2026-01-12T10:00:00Z",
    "updated_at": "2026-01-12T10:00:00Z",
    "published_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### PUT /api/v1/admin/agents/{agent_id}

更新 Agent (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

**请求参数 (部分更新):**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | ❌ | Agent名称 |
| description | string | ❌ | 描述 |
| icon | string | ❌ | 图标 |
| category | string | ❌ | 分类 |
| system_prompt | string | ❌ | 系统提示词 |
| welcome_message | string | ❌ | 欢迎消息 |
| capabilities_config | object | ❌ | 能力配置 |
| default_knowledge_base_ids | string[] | ❌ | 知识库ID列表 |

---

### DELETE /api/v1/admin/agents/{agent_id}

删除 Agent (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

**注意:** 如果 Agent 有关联的会话，删除会失败。

---

### POST /api/v1/admin/agents/{agent_id}/publish

发布 Agent (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "published",
    "published_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### POST /api/v1/admin/agents/{agent_id}/archive

归档 Agent (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

---

### GET /api/v1/agents

获取已发布 Agent 列表 (用户)

**Query 参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| category | string | ❌ | 按分类筛选 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "agents": [
      {
        "id": "uuid",
        "name": "销售教练",
        "description": "...",
        "icon": "🎯",
        "category": "sales",
        "welcome_message": "欢迎！",
        "capabilities": ["fuzzy_detection", "sales_stage"]
      }
    ],
    "total": 5
  }
}
```

---

### GET /api/v1/agents/{agent_id}

获取 Agent 详情 (用户，不含 system_prompt)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

---

### GET /api/v1/agents/{agent_id}/personas

获取 Agent 关联的 Persona 列表 (用户)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "uuid",
        "name": "急躁CEO",
        "description": "时间紧迫的决策者",
        "icon": "👔",
        "difficulty": "hard",
        "is_default": true
      }
    ]
  }
}
```

---

## 7. Persona 管理 API

### POST /api/v1/admin/personas

创建 Persona (管理员)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | ✅ | Persona名称 (≤100字符) |
| description | string | ❌ | 描述 (≤500字符) |
| icon | string | ❌ | 图标 (≤50字符) |
| category | string | ✅ | 分类: "customer" \| "interviewer" \| "coach" \| "examiner" |
| difficulty | string | ❌ | 难度: "easy" \| "medium" \| "hard" (默认 medium) |
| system_prompt | string | ✅ | AI角色提示词 |
| traits | object | ❌ | 性格特征 {"性格": "怀疑", "关注点": "证据"} |
| knowledge_base_ids | string[] | ❌ | 知识库ID列表 |
| behavior_config | object | ❌ | 行为配置 |
| scoring_weights | object | ❌ | 评分权重覆盖 |
| is_public | boolean | ❌ | 是否公开 (默认 true) |

**behavior_config 结构:**
```json
{
  "response_length": "medium",
  "challenge_frequency": 0.5,
  "interruption_triggers": ["价格", "折扣"],
  "typical_questions": ["你们的价格是多少？"]
}
```

**请求示例:**
```json
{
  "name": "急躁CEO",
  "description": "时间紧迫，对冗长回答缺乏耐心",
  "category": "customer",
  "difficulty": "hard",
  "system_prompt": "你是一个时间紧迫的CEO...",
  "traits": {
    "性格": "急躁",
    "关注点": "效率"
  },
  "behavior_config": {
    "response_length": "short",
    "challenge_frequency": 0.8
  }
}
```

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "急躁CEO",
    "status": "active",
    "created_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### GET /api/v1/admin/personas

获取 Persona 列表 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 20 | 每页数量 (1-100) |
| category | string | ❌ | - | 按分类筛选 |
| difficulty | string | ❌ | - | 按难度筛选 |
| status | string | ❌ | - | 按状态筛选 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "uuid",
        "name": "急躁CEO",
        "description": "...",
        "icon": "👔",
        "category": "customer",
        "difficulty": "hard",
        "is_public": true,
        "usage_count": 150,
        "agent_count": 3
      }
    ],
    "total": 20,
    "page": 1,
    "page_size": 20
  }
}
```

---

### GET /api/v1/admin/personas/{persona_id}

获取 Persona 详情 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| persona_id | string | Persona ID |

---

### PUT /api/v1/admin/personas/{persona_id}

更新 Persona (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| persona_id | string | Persona ID |

**请求参数 (部分更新):**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | ❌ | 名称 |
| description | string | ❌ | 描述 |
| icon | string | ❌ | 图标 |
| category | string | ❌ | 分类 |
| difficulty | string | ❌ | 难度 |
| system_prompt | string | ❌ | 提示词 |
| traits | object | ❌ | 性格特征 |
| knowledge_base_ids | string[] | ❌ | 知识库ID |
| behavior_config | object | ❌ | 行为配置 |
| scoring_weights | object | ❌ | 评分权重 |
| is_public | boolean | ❌ | 是否公开 |
| status | string | ❌ | 状态: "active" \| "inactive" |

---

### DELETE /api/v1/admin/personas/{persona_id}

删除 Persona (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| persona_id | string | Persona ID |

**注意:** 如果 Persona 已关联到 Agent，删除会失败。

---

### POST /api/v1/admin/personas/{persona_id}/duplicate

复制 Persona (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| persona_id | string | Persona ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "new-uuid",
    "name": "急躁CEO (副本)",
    "status": "active",
    "created_at": "2026-01-12T10:00:00Z"
  }
}
```

---

## 8. Agent-Persona 关联 API

### POST /api/v1/admin/agents/{agent_id}/personas

添加 Persona 到 Agent (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| persona_id | string | ✅ | Persona ID |
| display_order | int | ❌ | 显示顺序 (默认 0) |
| is_default | boolean | ❌ | 是否默认 (默认 false) |
| override_config | object | ❌ | 配置覆盖 |

**请求示例:**
```json
{
  "persona_id": "uuid-persona",
  "display_order": 1,
  "is_default": true,
  "override_config": {
    "challenge_frequency": 0.9
  }
}
```

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-link",
    "agent_id": "uuid-agent",
    "persona_id": "uuid-persona",
    "display_order": 1,
    "is_default": true,
    "override_config": {},
    "created_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### GET /api/v1/admin/agents/{agent_id}/personas

获取 Agent 关联的 Persona 列表 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "personas": [
      {
        "id": "uuid-link",
        "agent_id": "uuid-agent",
        "persona_id": "uuid-persona",
        "display_order": 1,
        "is_default": true,
        "override_config": {},
        "created_at": "2026-01-12T10:00:00Z",
        "persona": {
          "id": "uuid-persona",
          "name": "急躁CEO",
          "description": "...",
          "icon": "👔",
          "category": "customer",
          "difficulty": "hard",
          "is_public": true,
          "usage_count": 150,
          "agent_count": 3
        }
      }
    ]
  }
}
```

---

### PUT /api/v1/admin/agents/{agent_id}/personas/{persona_id}

更新 Agent-Persona 关联 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |
| persona_id | string | Persona ID |

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| display_order | int | ❌ | 显示顺序 |
| is_default | boolean | ❌ | 是否默认 |
| override_config | object | ❌ | 配置覆盖 |

---

### DELETE /api/v1/admin/agents/{agent_id}/personas/{persona_id}

移除 Agent-Persona 关联 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| agent_id | string | Agent ID |
| persona_id | string | Persona ID |

---

## 9. 知识库 API

### POST /api/v1/admin/knowledge

创建知识库 (管理员)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | ✅ | 知识库名称 (≤100字符) |
| description | string | ❌ | 描述 (≤500字符) |
| category | string | ✅ | 分类: "product" \| "competitor" \| "faq" \| "policy" |

**请求示例:**
```json
{
  "name": "产品知识库",
  "description": "包含所有产品信息",
  "category": "product"
}
```

**响应数据 (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "产品知识库",
    "category": "product",
    "vector_collection": "kb_uuid",
    "document_count": 0,
    "status": "active",
    "created_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### GET /api/v1/admin/knowledge

获取知识库列表 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 20 | 每页数量 (1-100) |
| category | string | ❌ | - | 按分类筛选 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "knowledge_bases": [
      {
        "id": "uuid",
        "name": "产品知识库",
        "description": "...",
        "category": "product",
        "document_count": 15,
        "total_chunks": 450,
        "status": "active",
        "updated_at": "2026-01-12T10:00:00Z"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

---

### GET /api/v1/admin/knowledge/{kb_id}

获取知识库详情 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "产品知识库",
    "description": "...",
    "category": "product",
    "vector_collection": "kb_uuid",
    "embedding_model": "text-embedding-ada-002",
    "document_count": 15,
    "total_chunks": 450,
    "status": "active",
    "created_at": "2026-01-12T10:00:00Z",
    "updated_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### PUT /api/v1/admin/knowledge/{kb_id}

更新知识库 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |

**请求参数 (部分更新):**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | ❌ | 名称 |
| description | string | ❌ | 描述 |
| category | string | ❌ | 分类 |

---

### DELETE /api/v1/admin/knowledge/{kb_id}

删除知识库 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |

---

### POST /api/v1/admin/knowledge/{kb_id}/documents

上传文档到知识库 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |

**请求参数 (multipart/form-data):**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| file | File | ✅ | 文档文件 (pdf/docx/txt/md) |
| title | string | ❌ | 文档标题 (默认使用文件名) |

**文件限制:**
- 支持格式: pdf, docx, txt, md
- 最大大小: 50MB

**响应数据 (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "产品手册.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "status": "pending",
    "created_at": "2026-01-12T10:00:00Z"
  }
}
```

---

### GET /api/v1/admin/knowledge/{kb_id}/documents

获取知识库文档列表 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 20 | 每页数量 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "documents": [
      {
        "id": "uuid",
        "title": "产品手册.pdf",
        "file_type": "pdf",
        "file_size": 1024000,
        "status": "ready",
        "chunk_count": 45,
        "created_at": "2026-01-12T10:00:00Z"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20
  }
}
```

---

### GET /api/v1/admin/knowledge/{kb_id}/documents/{doc_id}

获取文档详情 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |
| doc_id | string | 文档 ID |

---

### DELETE /api/v1/admin/knowledge/{kb_id}/documents/{doc_id}

删除文档 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |
| doc_id | string | 文档 ID |

---

### GET /api/v1/admin/knowledge/{kb_id}/documents/{doc_id}/preview

预览文档分块 (管理员)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| kb_id | string | 知识库 ID |
| doc_id | string | 文档 ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "chunks": [
      {
        "index": 0,
        "content": "文档内容片段...",
        "metadata": {
          "page": 1,
          "section": "简介"
        }
      }
    ],
    "total_chunks": 45
  }
}
```

---

## 10. 会话回放 API

### GET /api/v1/sessions/{session_id}/messages

获取会话消息列表 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话 ID |

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 50 | 每页数量 (1-100) |

**注意:** 会话必须是已完成状态

**响应数据:**
```json
{
  "success": true,
  "data": {
    "messages": [
      {
        "id": "uuid",
        "session_id": "uuid",
        "turn_number": 1,
        "role": "user",
        "content": "你好，我想了解一下你们的产品",
        "audio_url": "https://...",
        "timestamp": "2026-01-12T10:00:00Z",
        "duration_ms": 3500,
        "fuzzy_words": [
          {
            "category": "uncertain",
            "matched": ["可能", "大概"],
            "suggestion": "使用更确定的表述",
            "severity": "medium"
          }
        ],
        "sales_stage": "opening",
        "score_snapshot": {
          "overall": 75,
          "dimensions": [
            {"name": "逻辑性", "score": 80, "trend": "up", "delta": 5}
          ]
        },
        "ai_feedback": "开场白清晰，但可以更加自信",
        "is_highlight": false,
        "highlight_type": null,
        "highlight_reason": null
      }
    ],
    "total": 40
  }
}
```

---

### GET /api/v1/sessions/{session_id}/messages/{message_id}

获取单条消息详情 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话 ID |
| message_id | string | 消息 ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "session_id": "uuid",
    "turn_number": 5,
    "role": "user",
    "content": "...",
    "audio_url": "https://...",
    "timestamp": "2026-01-12T10:05:00Z",
    "duration_ms": 5000,
    "fuzzy_words": [],
    "sales_stage": "presentation",
    "score_snapshot": {},
    "ai_feedback": "...",
    "is_highlight": true,
    "highlight_type": "good",
    "highlight_reason": "回答清晰有力",
    "suggested_response": "更好的回答示例..."
  }
}
```

---

### GET /api/v1/sessions/{session_id}/replay

获取完整回放数据 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话 ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "agent_name": "销售教练",
    "persona_name": "急躁CEO",
    "total_duration_ms": 1800000,
    "messages": [...],
    "timeline_markers": [
      {
        "timestamp_ms": 60000,
        "type": "stage_change",
        "label": "进入需求挖掘阶段",
        "message_id": "uuid",
        "highlight_type": null
      },
      {
        "timestamp_ms": 120000,
        "type": "highlight",
        "label": "优秀回答",
        "message_id": "uuid",
        "highlight_type": "good"
      }
    ],
    "stage_summary": [
      {
        "stage": "opening",
        "duration_ms": 60000,
        "score": 80
      },
      {
        "stage": "discovery",
        "duration_ms": 300000,
        "score": 75
      }
    ]
  }
}
```

---

### GET /api/v1/sessions/{session_id}/highlights

获取会话亮点 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话 ID |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "highlights": [
      {
        "id": "uuid",
        "turn_number": 5,
        "role": "user",
        "content": "...",
        "timestamp": "2026-01-12T10:05:00Z",
        "highlight_type": "good",
        "highlight_reason": "回答清晰有力",
        "ai_feedback": "...",
        "suggested_response": "..."
      }
    ]
  }
}
```

---

### GET /api/v1/sessions/{session_id}/audio/{message_id}

获取消息音频文件 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| session_id | string | 会话 ID |
| message_id | string | 消息 ID |

**响应:** 音频文件或重定向到存储URL

---

## 11. 演示文稿 API

### GET /api/v1/presentations

获取演示文稿列表 (需要认证)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| status | string | ❌ | - | 按状态筛选 |
| limit | int | ❌ | 20 | 返回数量 |

---

### POST /api/v1/presentations

上传演示文稿 (需要认证)

**请求参数 (multipart/form-data):**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| title | string | ✅ | 标题 |
| file | File | ✅ | PPT文件 |

---

### GET /api/v1/presentations/{presentation_id}

获取演示文稿详情 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| presentation_id | string | 演示文稿 ID |

---

### DELETE /api/v1/presentations/{presentation_id}

删除演示文稿 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| presentation_id | string | 演示文稿 ID |

---

### GET /api/v1/presentations/{presentation_id}/pages

获取演示文稿页面列表 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| presentation_id | string | 演示文稿 ID |

---

### GET /api/v1/presentations/{presentation_id}/pages/{page_number}/talking-points

获取页面要点 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| presentation_id | string | 演示文稿 ID |
| page_number | int | 页码 |

---

### POST /api/v1/presentations/{presentation_id}/pages/{page_number}/talking-points

添加页面要点 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| presentation_id | string | 演示文稿 ID |
| page_number | int | 页码 |

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| description | string | ✅ | 要点描述 |

---

### GET /api/v1/presentations/{presentation_id}/forbidden-words

获取禁用词列表 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| presentation_id | string | 演示文稿 ID |

---

### POST /api/v1/presentations/{presentation_id}/forbidden-words

添加禁用词 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| presentation_id | string | 演示文稿 ID |

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| phrase | string | ✅ | 禁用词 (≤500字符) |
| suggested_alternative | string | ❌ | 建议替代词 |
| page_id | UUID | ❌ | 关联页面ID (为空则全局生效) |

---

## 12. 销售场景 API

### GET /api/v1/scenarios

获取场景列表 (需要认证)

**Query 参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| scenario_type | string | ❌ | 场景类型: "presentation" \| "sales" |

**响应数据:**
```json
[
  {
    "scenario_id": "uuid",
    "scenario_type": "sales",
    "name": "销售场景1",
    "description": "...",
    "is_active": true,
    "persona_prompt": "..."
  }
]
```

---

### GET /api/v1/scenarios/sales/personas

获取销售角色列表 (需要认证)

**响应数据:**
```json
[
  {
    "id": "impatient_ceo",
    "name": "急躁 CEO",
    "description": "时间紧迫，对冗长回答缺乏耐心",
    "characteristics": ["不喜欢长篇大论", "希望快速得到要点"],
    "difficulty": "hard"
  }
]
```

---

### GET /api/v1/scenarios/{scenario_id}

获取场景详情 (需要认证)

**Path 参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| scenario_id | string | 场景 ID |

---

## 13. 分析统计 API

### GET /api/v1/analytics/leaderboard

获取排行榜 (需要认证)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| scenario_type | string | ❌ | - | 场景类型筛选 |
| time_period | string | ❌ | "all_time" | 时间范围 |
| limit | int | ❌ | 100 | 返回数量 (1-1000) |

**响应数据:**
```json
{
  "scenario_type": "sales",
  "time_period": "all_time",
  "total_users": 500,
  "entries": [
    {
      "rank": 1,
      "user_id": "uuid",
      "username": "用户名",
      "total_sessions": 50,
      "average_score": 92.5,
      "best_score": 98
    }
  ]
}
```

---

### GET /api/v1/analytics/leaderboard/my-rank

获取当前用户排名 (需要认证)

**Query 参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| scenario_type | string | ❌ | 场景类型筛选 |

---

### GET /api/v1/analytics/dashboard

获取仪表盘统计 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| scenario_type | string | ❌ | - | 场景类型筛选 |
| days | int | ❌ | 30 | 统计天数 (1-365) |

**响应数据:**
```json
{
  "scenario_type": "sales",
  "days": 30,
  "total_sessions": 1500,
  "completed_sessions": 1200,
  "completion_rate": 0.8,
  "average_scores": {
    "logic": 78.5,
    "accuracy": 82.3,
    "completeness": 75.8,
    "overall": 78.9
  },
  "engagement": {
    "average_duration_seconds": 1800,
    "average_interruptions_per_session": 2.5
  },
  "quality": {
    "sessions_with_high_vagueness": 150,
    "sessions_with_forbidden_words": 50
  }
}
```

---

### GET /api/v1/analytics/score-distribution

获取分数分布 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| scenario_type | string | ❌ | - | 场景类型筛选 |
| days | int | ❌ | 30 | 统计天数 (1-365) |

**响应数据:**
```json
{
  "scenario_type": "sales",
  "days": 30,
  "distribution": {
    "excellent": 200,
    "good": 500,
    "fair": 400,
    "poor": 100
  }
}
```

---

### GET /api/v1/analytics/trends

获取趋势数据 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| scenario_type | string | ❌ | - | 场景类型筛选 |
| days | int | ❌ | 30 | 统计天数 (1-365) |

---

### GET /api/v1/practice/history

获取练习历史 (需要认证)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| scenario_type | string | ❌ | - | 场景类型筛选 |
| limit | int | ❌ | 20 | 返回数量 (1-100) |
| offset | int | ❌ | 0 | 偏移量 |

---

### GET /api/v1/practice/history/statistics

获取练习统计 (需要认证)

---

### GET /api/v1/practice/history/trends

获取分数趋势 (需要认证)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| days | int | ❌ | 30 | 统计天数 (1-365) |

---

### GET /api/v1/analytics/storage

获取存储统计 (管理员)

---

## 14. 管理员 API

### POST /api/v1/admin/presentations

创建演示文稿 (管理员)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| title | string | ✅ | 标题 |
| description | string | ❌ | 描述 |

---

### POST /api/v1/admin/presentations/upload

上传演示文稿 (管理员)

**请求参数 (multipart/form-data):**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| file | File | ✅ | PPT文件 |
| title | string | ❌ | 标题 |
| description | string | ❌ | 描述 |
| extract_points | boolean | ❌ | 是否自动提取要点 (默认 true) |

---

### GET /api/v1/admin/presentations

获取演示文稿列表 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| limit | int | ❌ | 50 | 返回数量 |

---

### GET /api/v1/admin/presentations/{presentation_id}

获取演示文稿详情 (管理员)

---

### DELETE /api/v1/admin/presentations/{presentation_id}

删除演示文稿 (管理员)

---

### GET /api/v1/admin/presentations/{presentation_id}/pages

获取页面列表 (管理员)

---

### PUT /api/v1/admin/presentations/{presentation_id}/pages/{page_number}

更新页面内容 (管理员)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| title | string | ✅ | 页面标题 |
| content | string | ❌ | 页面内容 |

---

### POST /api/v1/admin/presentations/{presentation_id}/pages/{page_number}/talking-points

添加要点 (管理员)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| point_text | string | ✅ | 要点文本 |
| order | int | ❌ | 排序 (默认 0) |

---

### GET /api/v1/admin/presentations/{presentation_id}/pages/{page_number}/talking-points

获取要点列表 (管理员)

---

### DELETE /api/v1/admin/talking-points/{point_id}

删除要点 (管理员)

---

### POST /api/v1/admin/presentations/{presentation_id}/forbidden-words

添加禁用词 (管理员)

**请求参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| word | string | ✅ | 禁用词 |
| pattern_type | string | ❌ | 匹配类型: "literal" \| "regex" (默认 literal) |

---

### GET /api/v1/admin/presentations/{presentation_id}/forbidden-words

获取禁用词列表 (管理员)

---

### DELETE /api/v1/admin/forbidden-words/{word_id}

删除禁用词 (管理员)

---

### GET /api/v1/admin/users

获取用户列表 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 10 | 每页数量 (1-100) |
| search | string | ❌ | - | 搜索用户名或邮箱 |
| status | string | ❌ | - | 状态筛选: "active" \| "inactive" |
| role | string | ❌ | - | 角色筛选 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "username": "用户名",
        "email": "user@example.com",
        "role": "user",
        "status": "active",
        "last_active_at": "2026-01-12T10:00:00Z",
        "department": "销售部",
        "created_at": "2026-01-01T00:00:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 10,
    "has_more": true
  }
}
```

---

### GET /api/v1/admin/users/{user_id}

获取用户详情 (管理员)

---

### DELETE /api/v1/admin/users/{user_id}

删除用户 (软删除，管理员)

---

### GET /api/v1/admin/training-records

获取训练记录列表 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 10 | 每页数量 (1-100) |
| search | string | ❌ | - | 搜索用户名或场景 |
| status | string | ❌ | - | 状态筛选 |
| scenario_type | string | ❌ | - | 场景类型筛选 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "scenario_type": "sales",
        "title": "销售对练 - 急躁CEO",
        "start_time": "2026-01-12T10:00:00Z",
        "duration_seconds": 1800,
        "overall_score": 85.5,
        "user_id": "uuid",
        "user_name": "用户名",
        "status": "completed",
        "agent_name": "销售教练",
        "persona_name": "急躁CEO"
      }
    ],
    "total": 500,
    "page": 1,
    "page_size": 10,
    "has_more": true
  }
}
```

---

### GET /api/v1/admin/training-records/{record_id}

获取训练记录详情 (管理员)

---

### DELETE /api/v1/admin/training-records/{record_id}

删除训练记录 (管理员)

---

### GET /api/v1/admin/system-logs

获取系统日志列表 (管理员)

**Query 参数:**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| page | int | ❌ | 1 | 页码 |
| page_size | int | ❌ | 10 | 每页数量 (1-100) |
| search | string | ❌ | - | 搜索操作或用户 |
| status | string | ❌ | - | 状态筛选: "success" \| "failed" \| "warning" |
| action | string | ❌ | - | 操作类型筛选 |

**响应数据:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "action": "user_login",
        "user_identifier": "user@example.com",
        "ip_address": "192.168.1.1",
        "status": "success",
        "created_at": "2026-01-12T10:00:00Z",
        "details": "登录成功"
      }
    ],
    "total": 1000,
    "page": 1,
    "page_size": 10,
    "has_more": true
  }
}
```

---

### GET /api/v1/admin/system-logs/{log_id}

获取系统日志详情 (管理员)

---

## 15. WebSocket API

### WS /api/v1/ws/sales/{session_id}

销售练习 WebSocket 连接

**连接参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| session_id | string (path) | ✅ | 会话 ID |
| token | string (query) | ✅ | JWT 认证令牌 |
| agent_id | string (query) | ❌ | Agent ID (增强模式) |
| persona_id | string (query) | ❌ | Persona ID (增强模式) |

**连接模式:**
1. **简单模式**: 不传 agent_id/persona_id，使用硬编码角色
2. **增强模式**: 传 agent_id + persona_id，使用 Agent 平台集成

**连接示例:**
```
ws://localhost:8000/api/v1/ws/sales/uuid-session?token=jwt-token&agent_id=uuid-agent&persona_id=uuid-persona
```

---

### WebSocket 消息格式

#### 客户端 → 服务端

**音频数据:**
```json
{
  "type": "audio",
  "audio": "base64-encoded-audio-data",
  "sequence": 1,
  "sample_rate": 16000
}
```

**用户说话状态:**
```json
{
  "type": "user_speaking",
  "speaking": true
}
```

**页面切换 (演示模式):**
```json
{
  "type": "page_change",
  "page_number": 2
}
```

**暂停/恢复:**
```json
{
  "type": "pause"
}
```
```json
{
  "type": "resume"
}
```

**结束会话:**
```json
{
  "type": "end_session"
}
```

---

#### 服务端 → 客户端

**连接确认:**
```json
{
  "type": "connected",
  "session_id": "uuid",
  "message": "连接成功"
}
```

**ASR 识别结果:**
```json
{
  "type": "asr_result",
  "text": "识别的文本",
  "is_final": true,
  "confidence": 0.95
}
```

**AI 响应:**
```json
{
  "type": "ai_response",
  "text": "AI 回复内容",
  "audio_url": "https://...",
  "turn_number": 5
}
```

**打断事件:**
```json
{
  "type": "interruption",
  "reason": "forbidden_word",
  "trigger": "可能",
  "suggestion": "使用更确定的表述"
}
```

**分数更新 (增强模式):**
```json
{
  "type": "score_update",
  "overall": 75,
  "dimensions": [
    {"name": "逻辑性", "score": 80, "trend": "up"},
    {"name": "准确性", "score": 70, "trend": "stable"}
  ]
}
```

**阶段变化 (增强模式):**
```json
{
  "type": "stage_change",
  "stage": "discovery",
  "previous_stage": "opening"
}
```

**模糊词检测 (增强模式):**
```json
{
  "type": "fuzzy_detected",
  "category": "uncertain",
  "matched": ["可能", "大概"],
  "suggestion": "使用更确定的表述",
  "severity": "medium"
}
```

**会话结束:**
```json
{
  "type": "session_ended",
  "summary": {
    "overall_score": 85,
    "total_turns": 20,
    "duration_seconds": 1800
  }
}
```

**错误:**
```json
{
  "type": "error",
  "code": "[ERROR_CODE]",
  "message": "错误描述"
}
```

---

## 错误码参考

| 错误码 | HTTP状态码 | 描述 |
|--------|-----------|------|
| [INVALID_CREDENTIALS] | 401 | 邮箱或密码错误 |
| [USER_DISABLED] | 401 | 用户已被禁用 |
| [SESSION_NOT_FOUND] | 404 | 会话不存在 |
| [SESSION_NOT_COMPLETED] | 400 | 会话未完成 |
| [AGENT_NOT_FOUND] | 404 | Agent 不存在 |
| [AGENT_NOT_PUBLISHED] | 400 | Agent 未发布 |
| [PERSONA_NOT_FOUND] | 404 | Persona 不存在 |
| [PERSONA_NOT_LINKED_TO_AGENT] | 400 | Persona 未关联到 Agent |
| [PERSONA_IN_USE] | 400 | Persona 正在使用中 |
| [PERSONA_ALREADY_LINKED] | 400 | Persona 已关联 |
| [KNOWLEDGE_BASE_NOT_FOUND] | 404 | 知识库不存在 |
| [DOCUMENT_NOT_FOUND] | 404 | 文档不存在 |
| [INVALID_FILE] | 400 | 无效文件 |
| [UNSUPPORTED_FILE_TYPE] | 400 | 不支持的文件类型 |
| [FILE_TOO_LARGE] | 400 | 文件过大 |
| [ACCESS_DENIED] | 403 | 访问被拒绝 |
| [USER_NOT_FOUND] | 404 | 用户不存在 |
| [CANNOT_DELETE_SELF] | 400 | 不能删除自己 |
| [TRAINING_RECORD_NOT_FOUND] | 404 | 训练记录不存在 |
| [SYSTEM_LOG_NOT_FOUND] | 404 | 系统日志不存在 |

---

## 附录: 枚举值参考

### 场景类型 (ScenarioType)
- `presentation` - 演示练习
- `sales` - 销售对练

### 会话状态 (SessionStatus)
- `preparing` - 准备中
- `in_progress` - 进行中
- `paused` - 已暂停
- `completed` - 已完成
- `scoring` - 评分中

### Agent 状态 (AgentStatus)
- `draft` - 草稿
- `published` - 已发布
- `archived` - 已归档

### Agent 分类 (AgentCategory)
- `sales` - 销售
- `presentation` - 演示
- `interview` - 面试
- `customer_service` - 客服

### Persona 分类 (PersonaCategory)
- `customer` - 客户
- `interviewer` - 面试官
- `coach` - 教练
- `examiner` - 考官

### Persona 难度 (PersonaDifficulty)
- `easy` - 简单
- `medium` - 中等
- `hard` - 困难

### 知识库分类 (KnowledgeBaseCategory)
- `product` - 产品
- `competitor` - 竞品
- `faq` - 常见问题
- `policy` - 政策

### 文档状态 (DocumentStatus)
- `pending` - 待处理
- `processing` - 处理中
- `ready` - 就绪
- `failed` - 失败

### 销售阶段 (SalesStage)
- `opening` - 开场
- `discovery` - 需求挖掘
- `presentation` - 方案展示
- `objection` - 异议处理
- `closing` - 成交

### 亮点类型 (HighlightType)
- `good` - 优秀
- `bad` - 需改进
- `neutral` - 中性
