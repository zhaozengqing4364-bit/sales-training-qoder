# 通用编程规则 - 对话提取

本文档记录从实际编程实践中提取的通用规则，适用于任何项目。

---

## 1. Result 模式：显式错误处理

用返回值代替异常处理错误，避免控制流混乱。

### 核心规则

1. **面向用户的函数返回 Result**：公共服务、API handler、业务逻辑层
2. **内部函数可抛异常**：Repository、工具类、第三方库封装
3. **Result 包含两种状态**：`ok(value)` 或 `fail(fallback)`
4. **fallback 是给用户看的**：友好的降级信息或操作指引
5. **禁止空 catch 块**：至少记录日志或返回 Result.fail

### Result 定义

```python
@dataclass
class Result(Generic[T]):
    value: T | None = None
    fallback: str | None = None
    is_success: bool = True

    @classmethod
    def ok(cls, value: T) -> 'Result[T]':
        return cls(value=value, is_success=True)

    @classmethod
    def fail(cls, fallback: str) -> 'Result[T]':
        return cls(fallback=fallback, is_success=False)
```

### 使用场景

| 场景 | 处理方式 |
|------|---------|
| 外部 API 调用 | 返回 Result，网络错误 → fail |
| 文件读写 | 返回 Result，IO 错误 → fail |
| 数据验证 | 返回 Result，验证失败 → fail |
| AI/LLM 调用 | 返回 Result，超时/限流 → fail |

### 反例

```python
# ❌ 异常控制流
def process():
    try:
        data = fetch()
        return transform(data)
    except NetworkError:
        return default_value()  # 吞掉错误
    except TimeoutError:
        return default_value()  # 同样的处理

# ✅ Result 显式返回
def process() -> Result[Data]:
    try:
        data = fetch()
        return Result.ok(transform(data))
    except NetworkError as e:
        logger.error(f"Network error: {e}")
        return Result.fail("[RETRY_LATER] 网络不稳定，请稍后重试")
    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        return Result.fail("[RETRY_LATER] 请求超时，请重试")
```

---

## 2. 降级链模式：服务容错

核心服务必须有降级方案，单一故障不导致系统崩溃。

### 核心规则

1. **关键服务至少两个备选**：主服务 → 备用 → 最终降级
2. **降级顺序**：付费/高质量 → 免费/轻量 → 客户端处理
3. **每次降级记录 metrics**：便于监控和调优
4. **降级指令而非抛异常**：返回统一格式的降级指令

### 降级链模板

```
主服务 → 备用服务1 → 备用服务2 → 客户端降级
```

### 降级指令规范

| 指令格式 | 含义 | 适用场景 |
|---------|------|---------|
| `[USE_FALLBACK_SERVICE]` | 切换到备用服务 | 服务商故障 |
| `[USE_BROWSER_TTS]` | 客户端处理 | 所有服务端不可用 |
| `[RETRY_LATER]` | 临时错误 | 限流/抖动 |
| `[CACHE_FALLBACK]` | 使用缓存 | 数据库不可用 |

### 示例

```python
class TranslationServiceWithFallback:
    async def translate(self, text: str) -> Result[str]:
        # 1. 尝试主服务（付费API）
        if self.premium_available:
            result = await self.premium_api.translate(text)
            if result.is_success:
                self.metrics["premium_success"] += 1
                return result
            self.metrics["premium_failures"] += 1

        # 2. 降级到免费服务
        if self.free_available:
            result = await self.free_api.translate(text)
            if result.is_success:
                self.metrics["free_success"] += 1
                return result

        # 3. 客户端降级
        return Result.fail("[USE_OFFLINE_MODE]")
```

### 熔断器配合

```python
class CircuitBreaker:
    async def call(self, func):
        if self.state == OPEN:
            return Result.fail("[CIRCUIT_OPEN]")

        result = await func()
        if result.is_success:
            self.record_success()
        else:
            self.record_failure()
            if self.failure_count > THRESHOLD:
                self.open_circuit()

        return result
```

---

## 3. 组件化解耦：大型模块组织

将复杂模块拆分为单一职责的组件，提高可维护性。

### 核心规则

1. **单一职责**：每个文件只处理一类逻辑
2. **按功能拆分**：事件处理、消息构建、工具调用、数据处理
3. **主模块导入组件**：handler 导入 helpers，不直接实现
4. **禁止循环依赖**：组件间不能相互引用

### 目录结构模板

```
module/
├── handler.py          # 主处理器，编排逻辑
├── constants.py        # 常量定义
├── exceptions.py       # 自定义异常
└── components/         # 功能组件
    ├── event_handlers.py    # 事件处理
    ├── message_builder.py   # 消息构建
    ├── validators.py        # 数据验证
    └── transformers.py      # 数据转换
```

### 拆分原则

| 原始代码 | 拆分后 |
|---------|--------|
| 500+ 行 handler | 5-10 个组件文件 |
| 多层嵌套 switch/match | 按类型分发到 handler 函数 |
| 重复的数据转换逻辑 | 提取为 transformer 函数 |
| 硬编码的业务规则 | 提取为 validator |

### 示例

```python
# ❌ 大文件：一个 handler 处理所有
class MessageHandler:
    async def handle(self, message: dict):
        msg_type = message.get("type")

        if msg_type == "audio":
            # 50行处理逻辑
            ...
        elif msg_type == "text":
            # 80行处理逻辑
            ...
        elif msg_type == "tool":
            # 120行处理逻辑
            ...

# ✅ 组件化：分发到专用 handler
class MessageHandler:
    def __init__(self):
        self.handlers = {
            "audio": AudioHandler(),
            "text": TextHandler(),
            "tool": ToolHandler(),
        }

    async def handle(self, message: dict):
        msg_type = message.get("type")
        handler = self.handlers.get(msg_type)
        if handler:
            return await handler.handle(message)
        return Result.fail(f"Unknown message type: {msg_type}")
```

---

## 4. 前端错误边界：永不崩溃

前端必须有错误边界，防止局部错误导致白屏或应用崩溃。

### 核心规则

1. **根组件包裹 ErrorBoundary**：最高层级捕获所有异常
2. **功能区域独立边界**：独立功能模块各自捕获错误
3. **禁止弹窗报错**：用状态指示器而非 alert/prompt
4. **错误上报监控**：捕获错误发送到监控系统
5. **提供恢复手段**：重试按钮或刷新页面

### ErrorBoundary 实现

```tsx
class ErrorBoundary extends Component {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // 上报监控系统
    fetch('/api/error', {
      method: 'POST',
      body: JSON.stringify({ error: error.message, stack: error.stack })
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-fallback">
          <p>出错了，请刷新页面</p>
          <button onClick={() => window.location.reload()}>刷新</button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

### 使用规范

```tsx
// ✅ 正确：所有页面包裹边界
<ErrorBoundary>
  <App />
</ErrorBoundary>

// ✅ 正确：独立功能区域各自保护
<ErrorBoundary>
  <ChatPanel />
</ErrorBoundary>

<ErrorBoundary>
  <ScorePanel />
</ErrorBoundary>

// ❌ 错误：禁止弹窗
catch (e) {
  alert("请求失败");  // 不允许
}
```

### 错误提示规范

| 错误类型 | 提示文案 |
|---------|---------|
| 网络错误 | "网络连接不稳定，请检查网络" |
| 服务繁忙 | "服务器繁忙，请稍后重试" |
| 权限不足 | "无权访问该内容" |
| AI无响应 | "AI响应超时，请重试" |

---

## 5. 配置驱动：运行时可调整

配置从外部读取，支持动态调整无需重启。

### 核心规则

1. **配置与代码分离**：配置存数据库/文件/环境变量
2. **运行时加载**：服务启动时读取，支持热更新
3. **层级优先级**：运行时配置 > 环境变量 > 代码默认值
4. **敏感配置加密**：API Key、密码等必须加密存储
5. **配置变更监听**：支持回调通知配置变更

### 配置加载模式

```python
# 1. 定义配置模型
class ServiceConfig(BaseModel):
    provider: str
    api_key: str  # 加密存储
    timeout: int = 30
    retry_count: int = 3

# 2. 配置服务
class ConfigService:
    def get_config(self, key: str) -> ServiceConfig:
        # 优先从运行时配置读取
        runtime = self.db.get(f"config:{key}")
        if runtime:
            return self._parse(runtime)

        # 其次环境变量
        env_key = f"{key.upper()}_CONFIG"
        if env_key in os.environ:
            return self._parse_env(os.environ[env_key])

        # 最后默认值
        return self._default(key)

# 3. 使用配置
config = config_service.get_config("tts")
service = TTSService(provider=config.provider, api_key=config.api_key)
```

---

## 6. 日志规范：可追溯可搜索

结构化日志是排查问题的关键。

### 核心规则

1. **必须包含 trace_id**：请求级别的唯一标识
2. **结构化输出**：JSON 格式而非字符串拼接
3. **敏感字段脱敏**：密码、token、身份证等必须遮蔽
4. **日志级别正确**：ERROR（需处理）vs WARN（需关注）vs INFO（重要事件）
5. **错误日志包含堆栈**：方便定位问题

### 日志格式

```python
# ✅ 正确：结构化日志
logger.info("Request processed", {
    "trace_id": trace_id,
    "user_id": user_id,
    "duration_ms": duration,
    "status": "success"
})

# ❌ 错误：字符串拼接
logger.info(f"Request {trace_id} processed in {duration}ms")
```

### 脱敏处理

```python
def sanitize_log_data(data: dict) -> dict:
    """日志数据脱敏"""
    sensitive_keys = {"password", "token", "api_key", "secret", "credit_card"}
    result = {}
    for k, v in data.items():
        if k.lower() in sensitive_keys:
            result[k] = "****"
        else:
            result[k] = v
    return result
```

---

## 7. 接口稳定性：版本控制

API 必须支持版本控制，保证向后兼容。

### 核心规则

1. **URL 版本前缀**：`/api/v1/resource`
2. **响应结构稳定**：新增字段而非删除/修改
3. **废弃需警告**：旧版本提前通知，保留至少一个版本周期
4. **客户端兼容**：处理响应中的额外字段（忽略未知字段）

### 版本策略

```
版本发布周期：
v1 (当前) → v2 (新功能) → v1 标记废弃 → v1 下线
     ↓         ↓              ↓
  6个月     6个月后         3个月后
```

---

## 8. 幂等性：重复调用安全

接口必须处理重复调用，保证幂等性。

### 核心规则

1. **写操作必须幂等**：POST/PUT/DELETE 设计为可重复调用
2. **使用唯一标识**：业务ID或请求ID去重
3. **先查后写**：重复操作前检查状态
4. **返回操作结果**：即使重复调用也返回成功状态

### 幂等实现

```python
async def create_order(order: OrderCreate) -> Result[Order]:
    # 1. 检查是否已存在（幂等检查）
    existing = await order_repo.find_by_biz_id(order.biz_id)
    if existing:
        return Result.ok(existing)

    # 2. 创建订单
    new_order = await order_repo.create(order)
    return Result.ok(new_order)
```

---

## 9. 限流保护：防止压垮服务

防止突发流量压垮服务。

### 核心规则

1. **全局限流**：API 级别限制总请求数
2. **用户级限流**：单用户请求频率限制
3. **服务级限流**：保护下游服务
4. **限流返回标准错误**：`429 Too Many Requests`

### 限流策略

| 粒度 | 场景 | 限制示例 |
|------|------|---------|
| 全局 | 所有请求 | 1000 QPS |
| 用户 | 单用户 | 60 QPM |
| IP | 单IP | 100 QPM |
| 端点 | 特定API | 100 QPS |

---

## 10. 健康检查：服务可观测

提供服务状态接口，便于监控和负载均衡。

### 核心规则

1. **基础健康检查**：`/health` 返回服务运行状态
2. **依赖检查**：数据库、缓存、外部服务是否可用
3. **检查结果缓存**：避免频繁检查影响性能
4. **返回详细状态**：便于排查问题

### 健康检查接口

```python
@app.get("/health")
async def health_check():
    checks = {
        "status": "healthy",
        "database": await check_database(),
        "cache": await check_cache(),
        "external_api": await check_external_api()
    }

    is_healthy = all(c["status"] == "ok" for c in checks.values())

    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content=checks
    )
```
