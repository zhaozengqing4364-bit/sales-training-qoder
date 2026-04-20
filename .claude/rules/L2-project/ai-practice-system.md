# 项目特定规则 - AI智能演练系统

本文档记录本项目的特定架构模式和规则，补充全局规则。

---

## 1. Result[T] 错误处理模式

**宪法原则 I**: 用户体验永不中断

所有面向用户代码的函数必须返回 `Result` 而非抛出异常。

### 规则

1. 所有用户-facing服务层函数必须返回 `Result[T]`
2. 使用 `Result.ok(value)` 表示成功
3. 使用 `Result.fail(fallback_message)` 表示失败，包含用户可理解的降级信息
4. 禁止在用户-facing代码中使用 `raise` 抛出异常
5. 内部代码（Repository、第三方库）仍可使用异常，但需在边界转换为 Result

### 示例

```python
# ✅ 正确：返回 Result
async def synthesize_speech(text: str) -> Result[bytes]:
    try:
        audio = await tts_service.synthesize(text)
        return Result.ok(audio)
    except ConnectionError:
        return Result.fail("[USE_BROWSER_TTS]")  # 降级指令
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        return Result.fail("[USE_BROWSER_TTS]")

# ❌ 错误：直接抛出异常
async def synthesize_speech(text: str) -> bytes:
    raise RuntimeError("TTS unavailable")  # 不允许
```

### 降级指令格式

| 指令 | 含义 | 客户端行为 |
|------|------|-----------|
| `[USE_BROWSER_TTS]` | TTS服务不可用 | 切换到浏览器TTS |
| `[RETRY_LATER]` | 临时错误 | 显示"请稍后重试" |
| `[FALLBACK_ANSWER]` | AI响应失败 | 返回预设回复 |

---

## 2. 服务降级链模式

核心服务必须实现自动降级链，确保单一服务故障不导致整个系统崩溃。

### TTS 降级链

```
阿里云TTS → Edge-TTS → 浏览器TTS
```

### 规则

1. 关键服务必须实现降级链（至少2个备选）
2. 降级链顺序：主服务 → 免费备用 → 客户端降级
3. 每次降级必须记录 metrics
4. 最终降级返回降级指令，而非抛出异常

### 示例

```python
class TTSServiceWithFallback:
    async def synthesize(self, text: str) -> Result[int]:
        # 1. 尝试阿里云
        if self.primary_available:
            result = await self.primary_service.synthesize(text)
            if result.is_success:
                self.metrics["primary_success"] += 1
                return result

        # 2. 降级到 Edge-TTS
        if self.fallback_available:
            result = await self.fallback_service.synthesize(text)
            if result.is_success:
                self.metrics["fallback_success"] += 1
                return result

        # 3. 最终降级
        self.metrics["browser_fallbacks"] += 1
        return Result.fail("[USE_BROWSER_TTS]")
```

---

## 3. 知识库锁机制 (KB Lock)

确保后端强制 grounding 行为一致性，禁止 AI 臆测。

### 规则

1. 当 `require_kb_grounding=true` 时，AI 必须基于知识库回答
2. 未绑定知识库时，阻止用户发言并返回提示
3. 检索结果为空时，返回提示而非臆测
4. 检索失败时，返回错误提示而非降级到联网搜索

### 决策流程

```
用户发言
    ↓
是否启用KB锁?
    ├─ 否 → 正常AI回答
    ↓ 是
是否绑定知识库?
    ├─ 否 → 阻止发言，提示绑定KB
    ↓ 是
执行知识检索
    ├─ 检索失败 → 提示错误
    ├─ 结果为空 → 提示"无足够依据"
    ↓ 是
返回 grounding_context 给AI
```

### 阻塞状态码

| 状态码 | 含义 | 用户提示 |
|--------|------|---------|
| `blocked_no_kb` | 未绑定知识库 | 请先完成知识库绑定 |
| `blocked_not_ready` | KB文档未处理完成 | 请稍后重试 |
| `blocked_search_failed` | 检索失败 | 请稍后重试或联系管理员 |
| `blocked_empty` | 检索结果为空 | 请提供更具体的产品关键词 |

---

## 4. WebSocket 连接管理

### 规则

1. 所有场景使用 `BaseWebSocketHandler` 基类
2. 消息处理必须经过队列（避免阻塞）
3. 必须实现心跳机制（30s超时）
4. 断开连接前必须保存会话状态
5. 重连时必须恢复会话状态

### 会话状态保存

```python
async def _save_session_state(self):
    snapshot = self._create_state_snapshot()
    result = await self.state_service.save_state(snapshot)
    # 失败仅记录日志，不阻塞断开
```

### 重连恢复

```python
async def handle_connection(self, websocket, session_id, token):
    existing_state = await self.state_service.get_state(session_id)
    is_reconnection = existing_state.is_success and existing_state.value

    if is_reconnection:
        await self._restore_session_state(existing_state.value)
```

---

## 5. 前端错误边界

**宪法原则 I**: 用户体验永不中断

### 规则

1. 根组件必须包裹 `ErrorBoundary`
2. 演练页面必须包裹 `ClientErrorBoundary`
3. 禁止使用 `alert()` 或弹窗报错
4. 错误状态显示友好提示 + 重试/刷新按钮
5. 错误需上报监控系统（Sentry + 自建服务）

### ErrorBoundary 使用

```tsx
// ✅ 正确
<ErrorBoundary>
  <PracticePage />
</ErrorBoundary>

// ❌ 错误 - 禁止弹窗
try {
  await api.call();
} catch (e) {
  alert("请求失败");  // 不允许
}
```

### 错误提示规范

| 场景 | 提示文案 |
|------|---------|
| 网络错误 | "网络连接不稳定，请检查网络后重试" |
| 服务繁忙 | "服务器繁忙，请稍后重试" |
| 会话中断 | "会话已断开，正在重新连接..." |
| AI无响应 | "AI响应超时，请重试" |

---

## 6. 组件化解耦模式

销售对练 WebSocket 处理器采用组件化设计。

### 目录结构

```
sales_bot/websocket/components/
├── stepfun_event_payloads.py     # 事件载荷处理
├── stepfun_function_call_helpers.py  # 函数调用辅助
├── stepfun_message_helpers.py    # 消息构建辅助
├── stepfun_tool_helpers.py       # 工具处理辅助
├── stepfun_knowledge_helpers.py  # 知识检索辅助
└── stepfun_internal_knowledge_searcher.py  # 内部知识搜索
```

### 规则

1. 单一职责：每个文件只处理一类逻辑
2. 事件处理：事件类型 → 专用处理函数
3. 工具调用：工具名 → 专用 handler
4. 消息构建：类型 → 专用 builder

---

## 7. 配置驱动模式

运行时配置从数据库读取，支持动态调整。

### 规则

1. 服务启动时从数据库加载默认配置
2. 配置变更无需重启服务
3. 敏感配置（API Key）需加密存储
4. 配置解析失败使用环境变量兜底

### 配置层级

```
运行时数据库配置 > 环境变量 > 代码默认值
```

---

## 8. 日志与追踪

### 规则

1. 所有日志必须包含 `trace_id`
2. 使用结构化日志（JSON）
3. 敏感字段必须脱敏
4. 错误日志必须包含堆栈信息

### 字段脱敏

```python
def mask_sensitive(data: dict) -> dict:
    """脱敏处理"""
    sensitive_keys = {"password", "token", "api_key", "secret"}
    return {
        k: "****" if k.lower() in sensitive_keys else v
        for k, v in data.items()
    }
```

---

## 9. 熔断器模式

防止故障级联传播。

### 规则

1. 外部依赖（API、数据库）必须使用熔断器
2. 熔断打开后快速失败
3. 半开状态探测服务恢复
4. 记录熔断状态变更

### 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| failure_threshold | 5 | 触发熔断的失败次数 |
| recovery_timeout | 30s | 尝试恢复的间隔 |
| half_open_requests | 3 | 半开状态探测请求数 |

---

## 10. 场景隔离原则

两个核心场景必须独立演进，互不影响。

### 场景划分

| 场景 | 目录 | 共享模块 |
|------|------|---------|
| PPT演练 | `presentation_coach/` | common/* |
| 销售对练 | `sales_bot/` | common/* |

### 规则

1. 场景间禁止直接引用
2. 共享逻辑必须放在 `common/` 模块
3. 数据库表按场景前缀区分
4. WebSocket 路由按场景分流
