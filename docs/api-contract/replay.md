# 对话回放 API 契约

> 状态: 📋 计划中
> 
> 参考: `docs/roadmap/backend-gap-analysis.md` - 2.5 对话回放 API

## 数据模型

### ConversationMessage 实体

```typescript
interface ConversationMessage {
  id: string;                              // UUID
  session_id: string;                      // 会话 ID
  turn_number: number;                     // 轮次号
  role: 'user' | 'assistant';              // 角色
  content: string;                         // 文本内容
  audio_url?: string;                      // 音频文件 URL
  timestamp: string;                       // ISO8601
  duration_ms?: number;                    // 音频时长 (毫秒)
  
  // 分析数据
  fuzzy_words?: FuzzyDetection[];          // 检测到的模糊词
  sales_stage?: string;                    // 当前销售阶段
  score_snapshot?: ScoreSnapshot;          // 该轮次的评分快照
  ai_feedback?: string;                    // AI 点评
  
  // 标记
  is_highlight: boolean;                   // 是否关键时刻
  highlight_type?: 'good' | 'bad' | 'neutral';
  highlight_reason?: string;
}
```

### TimelineMarker 实体

```typescript
interface TimelineMarker {
  timestamp_ms: number;                    // 时间点 (毫秒)
  type: 'stage_change' | 'highlight' | 'fuzzy_word';
  label: string;                           // 显示标签
  message_id: string;                      // 关联消息 ID
  highlight_type?: 'good' | 'bad' | 'neutral';
}
```

---

## API 端点

### 获取对话消息列表

```http
GET /api/v1/sessions/{session_id}/messages?page=1&page_size=50
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "messages": [
      {
        "id": "msg-001",
        "session_id": "session-uuid-001",
        "turn_number": 1,
        "role": "assistant",
        "content": "你好，我是XX公司的采购负责人，听说你们有一款新产品？",
        "audio_url": "https://storage.example.com/audio/msg-001.mp3",
        "timestamp": "2025-01-11T10:00:00Z",
        "duration_ms": 3500,
        "sales_stage": "opening",
        "is_highlight": false
      },
      {
        "id": "msg-002",
        "session_id": "session-uuid-001",
        "turn_number": 2,
        "role": "user",
        "content": "您好！是的，我们的产品大概能帮您节省30%的成本",
        "audio_url": "https://storage.example.com/audio/msg-002.mp3",
        "timestamp": "2025-01-11T10:00:05Z",
        "duration_ms": 4200,
        "fuzzy_words": [
          {
            "category": "uncertain",
            "matched": ["大概"],
            "suggestion": "请给出具体数据",
            "severity": "high"
          }
        ],
        "sales_stage": "presentation",
        "score_snapshot": {
          "overall": 68,
          "dimensions": [
            {"name": "专业度", "score": 70, "trend": "stable"}
          ]
        },
        "ai_feedback": "使用了模糊词'大概'，建议引用具体客户案例数据",
        "is_highlight": true,
        "highlight_type": "bad",
        "highlight_reason": "模糊词使用"
      }
    ],
    "total": 12
  },
  "trace_id": "abc123"
}
```

### 获取单条消息详情

```http
GET /api/v1/sessions/{session_id}/messages/{message_id}
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "msg-002",
    "session_id": "session-uuid-001",
    "turn_number": 2,
    "role": "user",
    "content": "您好！是的，我们的产品大概能帮您节省30%的成本",
    "audio_url": "https://storage.example.com/audio/msg-002.mp3",
    "timestamp": "2025-01-11T10:00:05Z",
    "duration_ms": 4200,
    "fuzzy_words": [...],
    "sales_stage": "presentation",
    "score_snapshot": {...},
    "ai_feedback": "使用了模糊词'大概'，建议引用具体客户案例数据",
    "is_highlight": true,
    "highlight_type": "bad",
    "highlight_reason": "模糊词使用",
    "suggested_response": "根据我们服务的XX公司案例，他们在使用我们产品后，第一季度就实现了32.5%的成本节省"
  },
  "trace_id": "abc123"
}
```

### 获取回放数据

```http
GET /api/v1/sessions/{session_id}/replay
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "session_id": "session-uuid-001",
    "agent_name": "销售教练",
    "persona_name": "怀疑型客户",
    "total_duration_ms": 512000,
    "messages": [
      {
        "id": "msg-001",
        "turn_number": 1,
        "role": "assistant",
        "content": "你好，我是XX公司的采购负责人...",
        "audio_url": "https://...",
        "timestamp": "2025-01-11T10:00:00Z",
        "duration_ms": 3500,
        "sales_stage": "opening",
        "is_highlight": false
      }
    ],
    "timeline_markers": [
      {
        "timestamp_ms": 0,
        "type": "stage_change",
        "label": "开场破冰",
        "message_id": "msg-001"
      },
      {
        "timestamp_ms": 45000,
        "type": "stage_change",
        "label": "需求挖掘",
        "message_id": "msg-003"
      },
      {
        "timestamp_ms": 120000,
        "type": "fuzzy_word",
        "label": "模糊词: 大概",
        "message_id": "msg-005",
        "highlight_type": "bad"
      },
      {
        "timestamp_ms": 180000,
        "type": "highlight",
        "label": "优秀案例引用",
        "message_id": "msg-007",
        "highlight_type": "good"
      }
    ],
    "stage_summary": [
      {"stage": "opening", "duration_ms": 45000, "score": 75},
      {"stage": "discovery", "duration_ms": 75000, "score": 70},
      {"stage": "presentation", "duration_ms": 120000, "score": 65},
      {"stage": "objection", "duration_ms": 180000, "score": 72},
      {"stage": "closing", "duration_ms": 92000, "score": 68}
    ]
  },
  "trace_id": "abc123"
}
```

### 获取关键时刻

```http
GET /api/v1/sessions/{session_id}/highlights
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "highlights": [
      {
        "id": "msg-002",
        "turn_number": 2,
        "role": "user",
        "content": "我们的产品大概能帮您节省30%的成本",
        "timestamp": "2025-01-11T10:00:05Z",
        "highlight_type": "bad",
        "highlight_reason": "模糊词使用",
        "ai_feedback": "使用了模糊词'大概'，建议引用具体数据",
        "suggested_response": "根据XX公司案例，实现了32.5%的成本节省"
      },
      {
        "id": "msg-007",
        "turn_number": 7,
        "role": "user",
        "content": "根据我们服务的ABC公司案例，他们在第一季度就实现了35%的效率提升",
        "timestamp": "2025-01-11T10:03:00Z",
        "highlight_type": "good",
        "highlight_reason": "优秀案例引用",
        "ai_feedback": "很好地使用了具体案例和数据来支撑论点"
      }
    ]
  },
  "trace_id": "abc123"
}
```

### 获取单条语音

```http
GET /api/v1/sessions/{session_id}/audio/{message_id}
Authorization: Bearer <token>
```

**响应:** 重定向到音频文件 URL 或返回音频流

---

## 错误码

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `[SESSION_NOT_FOUND]` | 404 | 会话不存在 |
| `[MESSAGE_NOT_FOUND]` | 404 | 消息不存在 |
| `[AUDIO_NOT_AVAILABLE]` | 404 | 音频文件不存在 |
| `[SESSION_NOT_COMPLETED]` | 400 | 会话未完成，无法回放 |

---

## 前端类型定义

参考: `frontend/src/types/api-future.ts`

```typescript
// 已定义类型
export interface APIConversationMessage { ... }
export interface APIConversationMessagesResponse { ... }
export interface APIReplayDataResponse { ... }
export interface APITimelineMarker { ... }
export interface APIHighlightsResponse { ... }
```
