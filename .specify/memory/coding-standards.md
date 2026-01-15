# AI 智能演练系统 - 编码规范

**项目**: Enterprise AI Intelligent Practice System
**技术栈**: Python 3.11+, FastAPI, WebSocket, ChromaDB, LangChain
**核心原则**: 实时性 (<300ms)、零用户可见错误、模块化场景独立

---

## 核心原则

### 1. SOLID 原则

**Single Responsibility (单一职责)**
- 每个服务类只负责一个场景: `PresentationCoachService` 或 `SalesBotService`
- 错误处理与业务逻辑分离: `ErrorHandler` 类统一处理所有异常
- 不混合关注点: WebSocket 连接管理与业务逻辑分离

**Open/Closed (开闭原则)**
- 新增演练场景通过继承 `BaseScenario` 类,不修改现有代码
- 新增 TTS 提供商通过实现 `TTSProvider` 接口
- 使用策略模式处理不同类型的中断检测

**Liskov Substitution (里氏替换)**
- 所有场景服务可以互换使用 `BaseScenario` 接口
- 所有 TTS 提供商可以互换使用 `TTSProvider` 接口

**Interface Segregation (接口隔离)**
- WebSocket handler 只处理连接,不处理业务逻辑
- ASR/TTS 服务接口最小化,只暴露必要方法

**Dependency Inversion (依赖倒置)**
- 服务层依赖抽象接口 (`IAIProvider`, `IVectorStore`),不依赖具体实现
- 使用依赖注入而非硬编码依赖

### 2. 实时性优先原则

**零用户可见错误 (NON-NEGOTIABLE)**
- 所有异常必须被捕获并转换为优雅降级
- 禁止向前端抛出任何技术性错误
- 使用 fallback 链: 主方案 → 备选方案 → 默认响应

**异步优先**
- 所有 I/O 操作必须使用 `async/await`
- 禁止使用同步阻塞调用
- WebSocket 消息处理必须非阻塞

**性能目标**
- 端到端延迟 <300ms (95th percentile)
- ASR 流式延迟 <200ms
- 中断检测 <100ms

### 3. 模块化场景独立

- `presentation_coach/` 和 `sales_bot/` 完全独立
- 共享代码放在 `common/`
- 不允许跨场景直接导入

---

## Python/FastAPI 规范

### 异步编程

**✅ 正确做法**
```python
# 所有 I/O 必须异步
async def get_presentation(presentation_id: UUID) -> Presentation:
    async with db.session() as session:
        result = await session.execute(
            select(Presentation).where(Presentation.id == presentation_id)
        )
        return result.scalar_one()

# 并行处理多个异步任务
async def process_interruption(session_id: UUID):
    asr_task = asyncio.create_task(asr.transcribe(audio))
    llm_task = asyncio.create_task(llm.generate(prompt))
    results = await asyncio.gather(asr_task, llm_task, return_exceptions=True)
```

**❌ 错误做法**
```python
# 禁止同步 I/O
def get_presentation(presentation_id: UUID):  # ❌ 缺少 async
    result = db.session.execute(...)  # ❌ 同步调用

# 禁止阻塞循环
async def process_audio(audio_chunks: List[bytes]):
    for chunk in audio_chunks:
        result = blocking_function(chunk)  # ❌ 阻塞事件循环
```

### 错误处理 (无用户可见错误)

**分层错误处理策略**

```python
# 1. 服务层: 捕获所有异常,返回 Result 类型
class Result(T):
    def __init__(self, value: T = None, error: Exception = None, fallback: Any = None):
        self.value = value
        self.error = error
        self.fallback = fallback

    @property
    def is_success(self) -> bool:
        return self.error is None

async def transcribe_audio(audio: bytes) -> Result[str]:
    try:
        text = await asr_service.transcribe(audio)
        return Result(value=text)
    except ASRServiceUnavailable:
        logger.warning("ASR unavailable, using fallback", extra={"trace_id": trace_id})
        return Result(fallback="[USE_BROWSER_ASR]")
    except Exception as e:
        logger.error(f"ASR failed: {e}", extra={"trace_id": trace_id})
        return Result(fallback="[RETRY]")

# 2. WebSocket 层: 检查 Result,发送优雅降级
@router.websocket("/ws/presentation")
async def presentation_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            audio = await websocket.receive_bytes()
            result = await transcribe_audio(audio)

            if result.fallback == "[USE_BROWSER_ASR]":
                # 通知客户端切换到浏览器 ASR
                await websocket.send_json({
                    "type": "error",
                    "data": {
                        "code": "ASR_FALLBACK",
                        "user_action": "switch_to_browser_asr"
                    }
                })
            elif result.value:
                # 正常处理
                await websocket.send_json({
                    "type": "transcript",
                    "data": {"text": result.value}
                })
    except Exception as e:
        # 永远不向前端抛出异常
        logger.critical(f"WebSocket error: {e}", exc_info=True)
        await websocket.close(code=1000)  # 静默关闭
```

### WebSocket 最佳实践

```python
# ✅ 正确: 非阻塞消息处理
@router.websocket("/ws/presentation")
async def presentation_websocket(websocket: WebSocket):
    await websocket.accept()
    session_id = websocket.query_params.get("session_id")

    try:
        # 使用队列处理消息,避免阻塞
        message_queue = asyncio.Queue()

        async def receive_messages():
            async for message in websocket.iter_json():
                await message_queue.put(message)

        async def process_messages():
            while True:
                message = await message_queue.get()
                await handle_message(message, websocket)

        # 并行运行接收和处理
        await asyncio.gather(
            receive_messages(),
            process_messages()
        )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        # 触发重连逻辑,不报错
    except Exception as e:
        logger.error(f"WebSocket error: {e}", extra={"session_id": session_id})
        # 静默处理,不向前端暴露错误

# ❌ 错误: 阻塞消息处理
@router.websocket("/ws/presentation")
async def presentation_websocket(websocket: WebSocket):
    await websocket.accept()
    while True:
        message = await websocket.receive_json()  # ❌ 阻塞其他连接
        await slow_sync_function(message)  # ❌ 阻塞事件循环
```

### 依赖注入

```python
# 使用 FastAPI Depends
from fastapi import Depends

async def get_db_session():
    async with db.session() as session:
        yield session

async def get_asr_service() -> ASRService:
    return asr_service_instance

@router.post("/sessions")
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db_session),
    asr: ASRService = Depends(get_asr_service)
):
    # 注入的依赖可以在测试中替换为 mock
    return await session_service.create(session_data, db, asr)
```

---

## ChromaDB 向量数据库规范

### Metadata Filtering (必需)

```python
# ✅ 正确: 使用 metadata 过滤
results = collection.query(
    query_texts=["用户问题"],
    where={
        "presentation_id": str(presentation_id),
        "page_number": current_page
    },
    n_results=3
)

# ❌ 错误: 查询后过滤 (性能差,违反原则)
all_results = collection.query(query_texts=["用户问题"])
filtered = [r for r in all_results if r.metadata["page"] == current_page]
```

### 错误处理

```python
async def search_knowledge(query: str, page: int) -> Result[List[str]]:
    try:
        results = await collection.query(
            query_texts=[query],
            where={"page": page},
            n_results=3
        )
        return Result(value=[r["text"] for r in results])
    except ChromaDBError:
        logger.warning("Vector DB failed, using keyword search")
        # 降级到关键词搜索
        return Result(fallback="[USE_KEYWORD_SEARCH]")
    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return Result(fallback="[EMPTY_RESPONSE]")
```

---

## LangChain AI 集成规范

### Prompt 模板管理

```python
# 使用 Pydantic 管理 prompts
class PromptTemplate(BaseModel):
    system: str
    user: str
    interruption: str

PRESENTATION_COACH_PROMPT = PromptTemplate(
    system="你是一个专业的演讲教练...",
    user="用户说了: {user_text}, 当前在第 {page} 页",
    interruption="检测到用户使用了禁忌词,请礼貌提醒..."
)

# 使用模板
async def generate_interruption(forbidden_word: str) -> str:
    prompt = PRESENTATION_COACH_PROMPT.interruption.format(
        word=forbidden_word
    )
    return await llm.ainvoke(prompt)
```

### 超时与重试

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5)
)
async def call_llm_with_timeout(prompt: str) -> Result[str]:
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(prompt),
            timeout=5.0  # 5秒超时
        )
        return Result(value=response.content)
    except asyncio.TimeoutError:
        logger.warning("LLM timeout, using fallback")
        # 返回预定义的"垫场话术"
        return Result(fallback="[FILLER_PHRASE]")
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return Result(fallback="[RETRY]")
```

---

## 测试规范

### 测试金字塔

- **70% 单元测试**: 测试独立函数/类
- **20% 集成测试**: 测试 WebSocket → ASR → LLM → TTS 流程
- **10% 性能测试**: 测试 50 并发连接

### 单元测试示例

```python
import pytest
from src.presentation_coach.services.interruption_detector import InterruptionDetector

def test_detect_forbidden_word_immediate():
    """测试禁忌词检测在100ms内完成"""
    detector = InterruptionDetector()

    start_time = time.time()
    result = detector.check_forbidden_words("我不知道这个问题的答案")
    latency = (time.time() - start_time) * 1000

    assert result is not None
    assert latency < 100, f"Detection took {latency}ms, expected <100ms"

def test_detect_vague_response_with_llm():
    """测试语义分析使用异步 LLM 调用"""
    detector = InterruptionDetector()

    async def run_test():
        result = await detector.check_semantic_vagueness("这个产品挺好的")
        assert result.should_interrupt is True
        assert "具体" in result.interruption_message

    asyncio.run(run_test())
```

### 集成测试示例

```python
import pytest
from httpx import AsyncWebSocketClient

@pytest.mark.asyncio
async def test_websocket_full_flow():
    """测试完整的 WebSocket 流程"""
    async with AsyncWebSocketClient(app=app, url="/ws/presentation") as ws:
        # 连接
        await ws.send_json({
            "type": "client_ready",
            "data": {"session_id": test_session_id}
        })

        # 发送音频
        await ws.send_bytes(test_audio_chunk)

        # 接收转录
        response = await ws.receive_json()
        assert response["type"] == "asr_transcript"
        assert "text" in response["data"]

        # 验证无错误消息
        assert response["type"] != "error"
```

### 性能测试示例

```python
import pytest
import asyncio

@pytest.mark.asyncio
@pytest.mark.performance
async def test_fifty_concurrent_websockets():
    """测试50个并发 WebSocket 连接"""
    async def single_session():
        async with AsyncWebSocketClient(app=app) as ws:
            await ws.send_bytes(test_audio)
            response = await ws.receive_json()
            assert "type" in response

    # 并发执行50个会话
    tasks = [single_session() for _ in range(50)]
    await asyncio.gather(*tasks)
```

---

## 代码组织

### 目录结构

```
backend/src/
├── presentation_coach/          # PPT 演练场景 (独立)
│   ├── models/
│   │   └── presentation.py
│   ├── services/
│   │   ├── coach_service.py     # 只处理 PPT 演练逻辑
│   │   └── page_tracker.py
│   ├── api/
│   │   └── presentations.py
│   └── websocket/
│       └── presentation_ws.py
├── sales_bot/                   # 销售对练场景 (独立)
│   ├── services/
│   │   └── sales_service.py     # 只处理销售对练逻辑
│   └── websocket/
│       └── sales_ws.py
└── common/                      # 共享模块
    ├── audio/
    │   ├── asr_provider.py      # ASR 抽象接口
    │   ├── tts_provider.py      # TTS 抽象接口
    │   └── qwen_asr.py          # qwen3-asr-flash 实现
    ├── ai/
    │   ├── llm_provider.py      # LLM 抽象接口
    │   └── langchain_wrapper.py
    ├── knowledge/
    │   └── vector_store.py      # ChromaDB 封装
    ├── error_handling/
    │   ├── error_handler.py     # 统一错误处理
    │   ├── fallback_chain.py    # Fallback 逻辑
    │   └── exceptions.py        # 自定义异常
    └── monitoring/
        ├── logger.py            # 结构化日志
        └── metrics.py           # 延迟追踪
```

### 模块独立性检查

```python
# ✅ 正确: presentation_coach 不依赖 sales_bot
from presentation_coach.services.coach_service import CoachService
from common.audio.asr_provider import ASRProvider  # OK: 使用 common

# ❌ 错误: presentation_coach 导入 sales_bot
from presentation_coach.services.coach_service import CoachService
from sales_bot.services.sales_service import SalesService  # ❌ 违反独立原则
```

---

## 性能优化

### 延迟追踪

```python
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def track_latency(operation_name: str):
    start = time.time()
    try:
        yield
    finally:
        latency_ms = (time.time() - start) * 1000
        logger.info(
            f"{operation_name} latency",
            extra={
                "operation": operation_name,
                "latency_ms": latency_ms,
                "trace_id": current_trace_id
            }
        )
        if latency_ms > 300:
            logger.warning(f"High latency detected: {latency_ms}ms")

# 使用
async def process_interruption(text: str):
    async with track_latency("interruption_detection"):
        result = await detector.check(text)
```

### 批处理优化

```python
# ✅ 正确: 批量获取必讲点
async def get_required_points(page_ids: List[UUID]) -> List[RequiredPoint]:
    async with db.session() as session:
        result = await session.execute(
            select(RequiredPoint)
            .where(RequiredPoint.page_id.in_(page_ids))
        )
        return result.scalars().all()

# ❌ 错误: N+1 查询
async def get_required_points(page_ids: List[UUID]) -> List[RequiredPoint]:
    points = []
    for page_id in page_ids:  # ❌ N 次查询
        point = await session.get(RequiredPoint, page_id)
        points.append(point)
    return points
```

---

## 安全规范

### 敏感数据处理

```python
# ✅ 正确: 日志中不包含敏感信息
logger.info("User authentication", extra={"user_id": user.id})
# ❌ 错误: 日志中包含 token
logger.info(f"User logged in with token: {token}")  # ❌

# ✅ 正确: 错误消息中不包含内部细节
return JSONResponse(
    status_code=500,
    content={"message": "Internal error"}  # 通用消息
)
# ❌ 错误: 暴露内部错误
return JSONResponse(
    status_code=500,
    content={"error": "Database connection failed: postgresql://..."}  # ❌
)
```

### 输入验证

```python
from pydantic import BaseModel, Field, validator

class SessionCreate(BaseModel):
    scenario_type: str = Field(..., regex="^(presentation|sales)$")
    presentation_id: Optional[UUID] = None

    @validator('presentation_id')
    def validate_presentation_for_scenario(cls, v, values):
        if values.get('scenario_type') == 'presentation' and not v:
            raise ValueError('presentation_id required for presentation scenario')
        return v
```

---

## 代码审查清单

### 实时性检查

- [ ] 所有 I/O 使用 `async/await`?
- [ ] 没有同步阻塞调用?
- [ ] WebSocket 处理非阻塞?
- [ ] 延迟追踪已添加?

### 错误处理检查

- [ ] 所有异常都被捕获?
- [ ] 没有 `raise` 抛向前端?
- [ ] Fallback 链已实现?
- [ ] 日志中不包含敏感信息?

### 模块化检查

- [ ] 场景之间无直接依赖?
- [ ] 共享代码在 `common/`?
- [ ] 接口与实现分离?

### 测试检查

- [ ] 单元测试覆盖核心逻辑?
- [ ] 集成测试覆盖 WebSocket 流程?
- [ ] 性能测试通过 (50 并发)?
- [ ] 延迟测试通过 (<300ms)?

---

## 记住

**最重要的三个原则**:

1. **零用户可见错误** - 无论发生什么,用户永远看不到错误弹窗
2. **实时性** - 95% 的交互延迟 <300ms
3. **模块独立** - PPT 演练和销售对练互不干扰

所有其他规范都是为了支持这三个核心原则。
