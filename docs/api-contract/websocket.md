# WebSocket 消息契约

> 状态: 部分 ✅ 已实现，部分 📋 计划中
> 
> 参考: `docs/roadmap/sales-coach-upgrade.md` - 8. WebSocket 消息协议扩展

## 连接建立

### PPT 演练
```
wss://api.your-domain.com/ws/presentation/{session_id}?token={jwt_token}
```

### 销售对练
```
wss://api.your-domain.com/ws/sales/{session_id}?token={jwt_token}
```

### 连接成功响应
```json
{
  "type": "connected",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {
    "session_id": "session-uuid-001",
    "agent_id": "agent-uuid-001",
    "persona_id": "persona-uuid-001"
  }
}
```

---

## 消息格式规范

### 基础消息结构

```typescript
interface WebSocketMessage<T = unknown> {
  type: string;                // 消息类型
  timestamp: string;           // ISO8601 时间戳
  trace_id?: string;           // 追踪 ID (服务端消息)
  data: T;                     // 消息数据
}
```

---

## 客户端 → 服务端消息

### audio_chunk (✅ 已实现)

发送音频数据块 (流式)

```json
{
  "type": "audio_chunk",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {
    "audio": "base64_encoded_audio_data",
    "sample_rate": 16000,
    "interrupt": false
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| audio | string | ✅ | Base64 编码的 16-bit PCM 音频数据 |
| sample_rate | number | ❌ | 采样率，默认 16000 |
| interrupt | boolean | ❌ | 是否打断当前 AI 播放 |

### audio_end (✅ 已实现)

音频发送结束信号 (用户停止说话时发送)

```json
{
  "type": "audio_end",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {}
}
```

**重要**: 后端收到 `audio_end` 后会触发 ASR 的 `commit` 操作，告诉 ASR "没有更多音频了，给我最终结果"。

### user_speaking (✅ 已实现)

用户开始/停止说话状态

```json
{
  "type": "user_speaking",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {
    "speaking": true
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| speaking | boolean | ✅ | true=开始说话 (启动流式 ASR), false=停止说话 (触发 commit) |

**流程**:
1. `speaking: true` - 后端建立与 ASR 服务的 WebSocket 连接
2. 前端发送 `audio_chunk` - 后端实时转发给 ASR
3. `audio_end` 或 `speaking: false` - 后端触发 ASR commit，获取最终结果

### text (✅ 已实现)

发送文本消息 (用于调试或文字输入模式)

```json
{
  "type": "text",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {
    "content": "你好，我想了解一下你们的产品"
  }
}
```

### page_change (✅ 已实现)

PPT 翻页

```json
{
  "type": "page_change",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {
    "page_number": 2
  }
}
```

### control (✅ 已实现)

控制消息

```json
{
  "type": "control",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {
    "action": "pause" | "resume" | "end"
  }
}
```

---

## 音频传输协议

### 流式处理架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     流式音频处理 (真正的实时)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  前端              后端 Handler           ASR WebSocket                  │
│    │                │                       │                           │
│    │ (用户按下按钮)  │                       │                           │
│    │── speaking:T ─>│ 建立 ASR 连接         │                           │
│    │                │────── connect ───────>│                           │
│    │                │<───── session.ok ─────│                           │
│    │                │                       │                           │
│    │── chunk[1] ───>│────── append ────────>│ 开始处理                  │
│    │<── interim ────│<───── stash ──────────│ "你"                      │
│    │── chunk[2] ───>│────── append ────────>│                           │
│    │<── interim ────│<───── stash ──────────│ "你好"                    │
│    │── chunk[3] ───>│────── append ────────>│                           │
│    │<── interim ────│<───── stash ──────────│ "你好我想"                │
│    │                │                       │                           │
│    │ (用户松开按钮)  │                       │                           │
│    │── audio_end ──>│────── commit ────────>│ 知道结束了                │
│    │                │                       │                           │
│    │<── final ──────│<───── completed ──────│ "你好我想了解产品"        │
│    │                │                       │                           │
│    │                │ 处理最终文本           │                           │
│    │                │ → LLM 生成回复         │                           │
│    │                │ → TTS 合成语音         │                           │
│    │<── tts_audio ──│                       │                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 关键设计点

1. **边收边发** - 前端每收到一个音频块，立即发送给后端，后端立即转发给 ASR
2. **实时反馈** - ASR 返回的中间结果 (stash) 实时发送给前端显示
3. **显式结束** - `audio_end` 触发 ASR 的 `commit`，告诉 ASR "我说完了"
4. **延迟最小化** - 用户说话时就能看到识别结果，不需要等到说完

### 采样率处理

- 浏览器 AudioContext 默认使用 44100Hz 或 48000Hz
- 前端负责重采样到 16000Hz
- 音频格式: 16-bit PCM, 单声道, Little-Endian

---

## 服务端 → 客户端消息

### asr_transcript (✅ 已实现)

语音识别结果

> 注意: 后端发送 `asr_transcript`，前端应同时兼容 `transcript` 和 `asr_transcript`

```json
{
  "type": "asr_transcript",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "text": "你好，我想了解一下你们的产品",
    "is_final": true,
    "confidence": 0.95
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| text | string | 识别文本 |
| is_final | boolean | 是否最终结果 |
| confidence | number | 置信度 0-1 |

### response (✅ 已实现)

AI 文本回复

```json
{
  "type": "response",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "text": "你好！很高兴为您介绍我们的产品...",
    "role": "assistant"
  }
}
```

### tts_audio (✅ 已实现)

TTS 语音数据

```json
{
  "type": "tts_audio",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "audio": "base64_encoded_audio",
    "text": "你好！很高兴为您介绍...",
    "duration_ms": 3500
  }
}
```

### feedback (✅ 已实现)

AI 反馈/打断

```json
{
  "type": "feedback",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "interruption": true,
    "reason": "forbidden_word" | "missing_point" | "vague_response",
    "trigger": "大概",
    "message": "您使用了模糊词'大概'，建议给出具体数据"
  }
}
```

### status (✅ 已实现)

状态更新

```json
{
  "type": "status",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "session_status": "in_progress",
    "ai_state": "listening" | "thinking" | "speaking",
    "current_page": 2,
    "interruption_count": 3
  }
}
```

### heartbeat (✅ 已实现)

心跳消息 (每 30 秒)

```json
{
  "type": "heartbeat",
  "timestamp": "2025-01-11T10:00:00Z",
  "data": {}
}
```

### error (✅ 已实现)

错误消息

```json
{
  "type": "error",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "code": "[PROCESSING_ERROR]",
    "message": "语音识别失败，请重试",
    "user_action": "switch_to_browser_asr",
    "fallback_text": "抱歉，我没有听清，请再说一遍"
  }
}
```

| 错误码 | 说明 | user_action |
|--------|------|-------------|
| `[PROCESSING_ERROR]` | 处理错误 | - |
| `[TIMEOUT]` | 超时 | - |
| `[ASR_FAILED]` | ASR 失败 | `switch_to_browser_asr` |
| `[TTS_FAILED]` | TTS 失败 | `use_browser_tts` |
| `[SESSION_EXPIRED]` | 会话过期 | - |

---

## 增强模式消息类型 (✅ EnhancedHandler 已实现)

> 以下消息类型仅在增强模式 (带 agent_id + persona_id) 下可用

### fuzzy_detection (✅ 已实现)

模糊词检测结果

```json
{
  "type": "fuzzy_detection",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "detections": [
      {
        "category": "uncertain",
        "matched": ["大概", "可能"],
        "suggestion": "请给出具体数据或案例",
        "severity": "high"
      },
      {
        "category": "filler",
        "matched": ["嗯", "那个"],
        "suggestion": "减少填充词，保持表达流畅",
        "severity": "low"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| category | string | 类别: uncertain/filler/vague |
| matched | string[] | 匹配到的词 |
| suggestion | string | 改进建议 |
| severity | string | 严重程度: high/medium/low |

### stage_update (✅ 已实现)

销售阶段更新

```json
{
  "type": "stage_update",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "current_stage": "presentation",
    "stage_name": "方案呈现",
    "key_actions": ["匹配需求", "展示价值", "提供案例"],
    "guidance": "客户已表达需求，现在是展示产品价值的好时机",
    "progress": 0.6
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| current_stage | string | 阶段 ID |
| stage_name | string | 阶段名称 |
| key_actions | string[] | 关键动作 |
| guidance | string | 指导建议 |
| progress | number | 进度 0-1 |

**销售阶段定义:**

| ID | 名称 | 说明 |
|-----|------|------|
| opening | 开场破冰 | 建立信任，了解客户背景 |
| discovery | 需求挖掘 | 深入了解客户痛点和需求 |
| presentation | 方案呈现 | 展示产品价值和解决方案 |
| objection | 异议处理 | 处理客户疑虑和反对意见 |
| closing | 促成成交 | 推动决策，达成合作 |

### score_update (✅ 已实现，增强版)

实时评分更新

```json
{
  "type": "score_update",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "overall": 72,
    "dimensions": [
      {
        "name": "专业度",
        "score": 80,
        "trend": "up",
        "delta": 5
      },
      {
        "name": "沟通技巧",
        "score": 65,
        "trend": "down",
        "delta": -3
      },
      {
        "name": "销售流程",
        "score": 70,
        "trend": "stable",
        "delta": 0
      },
      {
        "name": "异议处理",
        "score": 75,
        "trend": "up",
        "delta": 2
      },
      {
        "name": "成交能力",
        "score": 68,
        "trend": "stable",
        "delta": 0
      }
    ],
    "feedback": "注意减少模糊表达，多使用具体数据"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| overall | number | 综合分数 0-100 |
| dimensions | array | 各维度评分 |
| dimensions[].name | string | 维度名称 |
| dimensions[].score | number | 分数 0-100 |
| dimensions[].trend | string | 趋势: up/down/stable |
| dimensions[].delta | number | 变化值 |
| feedback | string | 反馈建议 |

### knowledge_context (调试用)

知识库检索结果

```json
{
  "type": "knowledge_context",
  "timestamp": "2025-01-11T10:00:00Z",
  "trace_id": "abc123",
  "data": {
    "query": "产品价格",
    "results": [
      {
        "content": "标准版: ¥9,999/年",
        "score": 0.92,
        "source": "定价方案.docx"
      }
    ]
  }
}
```

---

## 前端类型定义

参考: `frontend/src/types/api-future.ts`

```typescript
// 已定义类型
export interface APIFuzzyDetectionMessage { ... }
export interface APIFuzzyDetectionData { ... }
export interface APISalesStageUpdateMessage { ... }
export interface APISalesStageUpdateData { ... }
export interface APIScoreUpdateMessage { ... }
export interface APIScoreUpdateData { ... }
export interface APIDimensionScore { ... }
export interface APIKnowledgeContextMessage { ... }
```

---

## 心跳与重连

### 心跳机制
- 服务端每 30 秒发送 heartbeat
- 客户端应在 60 秒内响应或发送任意消息
- 超时后服务端关闭连接

### 重连策略
- 断开后立即尝试重连
- 使用指数退避: 1s, 2s, 4s, 8s, 最大 30s
- 最多重试 5 次
- 重连时携带 last_sequence 恢复状态
