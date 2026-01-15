---
inclusion: fileMatch
fileMatchPattern: "**/backend/**/*.py"
---

# 后端开发原则 (元能力版)

> 只保留核心原则，代码模板见 `.kiro/templates/backend/`

---

## 1. 四大核心原则 (Constitution)

### I. 用户体验永不中断
```
所有错误必须优雅降级，永不显示技术错误弹窗
- 使用 Result[T] 包装所有可能失败的操作
- 错误中间件捕获异常，返回 fallback 响应
- Fallback 代码: [USE_BROWSER_ASR], [FALLBACK_RESPONSE], [PLEASE_TRY_AGAIN]
```

### II. 实时优先
```
延迟目标:
- ASR 流式识别: <200ms
- 打断检测: <100ms
- LLM 响应: <300ms
- WebSocket 心跳: 30s
```

### III. 可追踪性
```
每个请求携带 trace_id
- 前端生成，通过 X-Trace-ID 头传递
- 后端用 ContextVar 存储
- 所有日志自动附加 trace_id
```

### IV. 容错与降级
```
服务不可用时:
- LLM 不可用 → 预定义响应
- ASR 不可用 → 本地模型
- WebSocket 断开 → 自动重连 (最多3次)
```

---

## 2. 十大工程原则

| 原则 | 核心要点 |
|------|---------|
| 单一职责 | 一个模块只做一件事，改变理由只有一个 |
| 依赖倒置 | 依赖抽象不依赖具体，换实现不改业务代码 |
| 开闭原则 | 新功能是添加代码，不是修改代码 |
| 显式优于隐式 | 配置集中管理，意图清晰可见 |
| 失败是常态 | 为失败而设计，预期失败准备降级 |
| 可观测性 | 日志、指标、追踪，三者缺一不可 |
| 约定优于配置 | 统一目录结构、命名规范、响应格式 |
| 渐进式复杂度 | 先工作，再正确，最后优化 |
| 测试是文档 | 测试描述系统行为，不是代码实现 |
| 边界清晰 | 模块通过接口通信，不跨模块访问内部状态 |

---

## 3. 防幻觉规则

### 版本敏感
```python
# SQLAlchemy 2.0
from sqlalchemy import select
result = await session.execute(select(User).where(User.id == 1))

# Pydantic v2
class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# FastAPI 0.109+
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
```

### 验证检查清单
```
□ import 的模块存在于项目依赖中？
□ 调用的方法存在于对应的库中？
□ 参数是该方法的有效参数？
□ 语法符合项目使用的库版本？
```

---

## 4. API 响应格式

```python
# 统一格式
{"success": true, "data": {...}, "trace_id": "xxx"}
{"success": false, "error": "[ERROR_CODE]", "trace_id": "xxx"}

# 分页格式
{"items": [...], "total": 100, "page": 1, "page_size": 20, "has_more": true}
```

---

## 5. 边界条件

| 指标 | 限制 | 超限处理 |
|------|------|----------|
| WebSocket 连接数 | 50/实例 | 拒绝新连接 |
| 单会话时长 | 30 分钟 | 自动结束 |
| 单会话 Token | 5000 | 警告，超 8000 强制结束 |
| LLM 响应超时 | 10 秒 | 返回预定义响应 |

---

## 6. 目录结构约定

```
backend/src/
├── common/          # 公共模块 (不依赖业务)
│   ├── ai/          # AI 服务封装
│   ├── audio/       # 音频处理
│   ├── db/          # 数据库
│   └── monitoring/  # 监控日志
├── agent/           # Agent 平台核心
│   ├── capabilities/  # 能力模块
│   ├── api/           # API 路由
│   └── websocket/     # WebSocket
└── {module}/        # 业务模块
```

---

## 7. 命名规范

```
文件: snake_case.py
类: PascalCase
函数: snake_case
常量: UPPER_SNAKE_CASE
私有: _prefix
```
