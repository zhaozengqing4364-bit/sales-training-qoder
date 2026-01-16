# 语音演练模块优化实施计划

## 概述

本文档定义了企业 AI 智能实战系统中语音实战模块的优化需求，涵盖 7 个核心优化点：
1. AudioWorklet 降级策略
2. 流式 TTS 播放 (MediaSource API)
3. 完整打断处理 (<100ms 响应)
4. 背压控制 (100 chunk 队列限制)
5. 高质量音频重采样 (OfflineAudioContext)
6. 二进制 WebSocket 传输 (可选，降低 33% 带宽)
7. 性能监控增强 (trace_id 全链路追踪)

---

## 一、现状分析

### 1.1 现有实现评估

| 功能模块 | 实现状态 | 完成度 | 关键文件 |
|---------|---------|--------|---------|
| AudioWorklet | ✅ 已实现 | 90% | `/web/public/audio-worklet-processor.js` |
| Streaming TTS | ⚠️ 部分实现 | 40% | `/web/src/hooks/use-streaming-audio-player.ts` |
| ASR 队列管理 | ⚠️ 设计完成 | 60% | `/backend/src/common/audio/asr_alibaba.py` |
| 打断处理 | ❌ 未完成 | 20% | `/backend/src/sales_bot/websocket/enhanced_handler.py` |
| 高质量重采样 | ❌ 待升级 | 30% | `/web/src/hooks/use-audio-recorder.ts` |
| 二进制传输 | ❌ 未实现 | 0% | `/web/src/hooks/use-practice-websocket.ts` |
| 性能监控 | ⚠️ 部分实现 | 50% | 分散在各文件 |

### 1.2 依赖关系

```
AudioWorklet降级 → 高质量重采样 → ASR队列管理 → 打断处理 → Streaming TTS → 二进制传输
                                    ↑
                            性能监控 (贯穿全流程)
```

---

## 二、优先级排序

| 优先级 | 任务 | 影响力 | 延迟改善 |
|--------|------|--------|---------|
| **P0** | 打断处理完善 | 极高 | -150ms |
| **P0** | ASR队列背压控制 | 极高 | -50ms |
| **P1** | Streaming TTS | 高 | -200ms |
| **P1** | 高质量重采样 | 高 | 音质提升 |
| **P2** | AudioWorklet降级 | 中 | 稳定性 |
| **P3** | 二进制传输 | 低 | -30ms |
| **贯穿** | 性能监控增强 | 极高 | 可观测性 |

---

## 三、详细实施方案

### P0-1: 打断处理完善 (<100ms 响应目标)

**目标**: 从检测到用户打断 → 停止 AI 播放 → 清空队列，全程 <100ms

**前端修改** (`/web/src/hooks/use-streaming-audio-player.ts`):
- 添加 `interrupt()` 方法：立即停止 AudioBufferSourceNode
- 清空 `audioQueue` 数组
- 重置 MediaSource 状态
- 添加状态标记 `isInterrupted: boolean`

**后端修改** (`/backend/src/sales_bot/websocket/enhanced_handler.py`):
- 添加 `self._tts_task: Optional[asyncio.Task]` 跟踪
- 在 `handle_user_interrupt` 中取消 TTS 任务：
  ```python
  if self._tts_task and not self._tts_task.done():
      self._tts_task.cancel()
  ```

**WebSocket 优化** (`/web/src/hooks/use-practice-websocket.ts`):
- 打断消息直接发送，不经过队列
- 添加 `priority` 字段

### P0-2: ASR 队列背压控制

**目标**: 队列稳定在 <80 块，防止内存溢出

**后端修改** (`/backend/src/common/audio/asr_alibaba.py`):
- 当队列 > 80 块时发送 `{"type": "backpressure", "action": "slow_down"}`
- 当队列 < 50 块时发送 `{"type": "backpressure", "action": "resume"}`

**前端响应** (`/web/src/hooks/use-audio-recorder.ts`):
- 监听 `system_backpressure` 消息
- `slow_down`: 停止发送，缓存到本地队列 (最大 200 块)
- `resume`: 批量发送缓存的音频块 (间隔 50ms 限流)

### P1-1: Streaming TTS 实现

**目标**: 首字延迟 <500ms

**后端重构** (`/backend/src/common/audio/tts_service.py`):
- 使用 `edge_tts.Communicate.stream()` 获取二进制流
- 每收到 chunk 立即 yield，不等待整句完成
- 添加 `{"seq": int, "data": bytes, "is_final": bool}` 格式

**WebSocket 转发** (`/backend/src/sales_bot/websocket/enhanced_handler.py`):
- 每收到 TTS chunk 立即通过 WebSocket 发送

**前端播放** (`/web/src/hooks/use-streaming-audio-player.ts`):
- 收到 `audio_chunk` → 解码 → 追加到 SourceBuffer
- 首块到达时立即开始播放
- 检查 seq 序列号连续性

### P1-2: 高质量音频重采样

**目标**: 提升 ASR 准确率 >5%

**前端重构** (`/web/src/hooks/use-audio-recorder.ts`):
- 删除现有线性插值 `resampleBuffer` 函数
- 使用 OfflineAudioContext 进行高质量重采样：
  ```typescript
  const offlineCtx = new OfflineAudioContext(1, targetLength, 16000);
  // ... 创建 buffer, source, 渲染
  const renderedBuffer = await offlineCtx.startRendering();
  ```
- 可选：添加低通滤波器 (7500Hz) 防止混叠

### P2: AudioWorklet 降级策略

**目标**: 旧浏览器自动降级到 ScriptProcessor

**前端修改** (`/web/src/hooks/use-audio-recorder.ts`):
- 启动时检测 `AudioWorkletNode` 支持
- 不支持时自动使用 ScriptProcessorNode
- 设置状态 `this.processorType = 'worklet' | 'script'`
- 显示非侵入式通知

### P3: 二进制 WebSocket 传输

**目标**: 带宽降低 33%

**前端修改** (`/web/src/hooks/use-practice-websocket.ts`):
- 连接时协商 `{"type": "negotiate", "prefer_binary": true}`
- 启用后使用 `websocket.send(arrayBuffer)` 发送音频

**后端修改** (`/backend/src/sales_bot/websocket/enhanced_handler.py`):
- 区分文本消息和二进制消息
- 二进制格式：`[message_type: 1 byte][payload: N bytes]`

### 贯穿: 性能监控增强

**关键埋点**:

| 埋点位置 | 日志内容 | 文件 |
|---------|---------|------|
| 前端开始录音 | `audio_capture_start` | `use-audio-recorder.ts` |
| 后端收到音频 | `audio_received` | `enhanced_handler.py` |
| ASR 返回结果 | `asr_complete` | `asr_alibaba.py` |
| LLM 首字输出 | `llm_first_token` | `ai_service.py` |
| TTS 首块发送 | `tts_first_chunk` | `enhanced_handler.py` |
| 前端开始播放 | `audio_playback_start` | `use-streaming-audio-player.ts` |

**新建文件**: `/backend/src/common/monitoring/latency_tracker.py`
- 计算端到端延迟
- 每 100 次交互输出 P50/P95/P99 统计
- 超过 500ms 时触发告警

---

## 四、关键文件修改清单

### 前端核心文件

| 文件 | 修改类型 | 关键变更 |
|-----|---------|---------|
| `/web/src/hooks/use-audio-recorder.ts` | 重构 | 高质量重采样、背压响应、降级策略 |
| `/web/src/hooks/use-streaming-audio-player.ts` | 完善 | MediaSource 流式播放、打断处理 |
| `/web/src/hooks/use-practice-websocket.ts` | 新增 | 二进制传输协商、打断优先级 |

### 后端核心文件

| 文件 | 修改类型 | 关键变更 |
|-----|---------|---------|
| `/backend/src/common/audio/asr_alibaba.py` | 完善 | 队列背压信号 |
| `/backend/src/common/audio/tts_service.py` | 重构 | 流式生成 |
| `/backend/src/sales_bot/websocket/enhanced_handler.py` | 重构 | 打断处理、流式转发、二进制解析 |

### 新建文件

| 文件 | 用途 |
|-----|------|
| `/backend/src/common/monitoring/latency_tracker.py` | 延迟追踪服务 |

---

## 五、测试验收标准

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| 端到端延迟 P95 | <300ms | 100 次交互统计 |
| 打断响应 P95 | <100ms | 50 次打断测试 |
| 50 并发稳定性 | 无崩溃 | 持续 5 分钟 |
| TTS 首字延迟 | <500ms | LLM 输出到播放 |
| ASR 队列 | <80 块 | 压力测试 |

---

## 六、实施顺序建议

1. **第一阶段 (P0)**: 打断处理 + ASR 背压控制 + 性能监控基础
2. **第二阶段 (P1)**: Streaming TTS + 高质量重采样
3. **第三阶段 (P2/P3)**: AudioWorklet 降级 + 二进制传输

**预期成果**: 端到端延迟从当前 ~800ms 降低至 <300ms (P95)
