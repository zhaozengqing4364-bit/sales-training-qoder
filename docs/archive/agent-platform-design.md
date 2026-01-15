# Agent 配置平台设计方案

## 1. 核心理念

将对话能力抽象为**可配置的 Agent**，管理员通过后台界面：
- 创建 Agent
- 选择/组合能力模块
- 配置 Prompt 和规则
- 发布上线

无需写代码，纯配置驱动。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         管理后台 (Admin UI)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Agent管理   │  │ 能力模块    │  │ 知识库管理  │  │ 数据分析    │    │
│  │ (创建/编辑) │  │ (选择/配置) │  │ (上传/索引) │  │ (使用统计)  │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Agent 配置存储                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  {                                                               │   │
│  │    "agent_id": "sales-coach-001",                               │   │
│  │    "name": "销售教练",                                           │   │
│  │    "capabilities": ["asr", "llm", "tts", "interruption"],       │   │
│  │    "knowledge_base": "sales_handbook",                          │   │
│  │    "system_prompt": "你是一位资深销售教练...",                   │   │
│  │    "rules": [...],                                              │   │
│  │    "scoring_config": {...}                                      │   │
│  │  }                                                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Agent 运行时引擎                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    AgentRuntime                                  │   │
│  │  根据配置动态加载能力模块，组装成可运行的 Agent                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         能力模块库 (Capabilities)                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │   ASR   │ │   LLM   │ │   TTS   │ │ 知识检索 │ │ 打断检测 │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ 评分系统 │ │ 情绪分析 │ │ 要点追踪 │ │ 禁用词  │ │ 计时器  │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 能力模块定义

### 3.1 模块清单

| 模块ID | 名称 | 说明 | 配置项 |
|--------|------|------|--------|
| `asr` | 语音识别 | 实时语音转文字 | 语言、方言 |
| `tts` | 语音合成 | 文字转语音 | 音色、语速 |
| `llm` | 大模型对话 | AI对话生成 | 模型、温度 |
| `knowledge` | 知识库检索 | RAG知识增强 | 知识库ID |
| `interruption` | 打断检测 | 实时打断用户 | 触发条件 |
| `scoring` | 评分系统 | 多维度评分 | 评分维度 |
| `point_tracking` | 要点追踪 | 检查必讲要点 | 要点列表 |
| `forbidden_words` | 禁用词检测 | 检测禁用表达 | 词库 |
| `emotion` | 情绪分析 | 分析用户情绪 | 敏感度 |
| `timer` | 计时器 | 限时/提醒 | 时长 |
| `persona` | 角色扮演 | AI扮演特定角色 | 角色设定 |

### 3.2 模块接口定义

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class CapabilityConfig:
    """能力模块配置"""
    enabled: bool = True
    params: Dict[str, Any] = None

@dataclass  
class CapabilityResult:
    """能力模块执行结果"""
    success: bool
    data: Any = None
    should_interrupt: bool = False
    feedback: Optional[str] = None
    fallback: Optional[str] = None  # 失败时的降级代码，如 [ASR_FAILED]

class BaseCapability(ABC):
    """能力模块基类"""
    
    capability_id: str  # 模块唯一标识
    name: str           # 显示名称
    description: str    # 描述
    config_schema: dict # 配置项JSON Schema
    
    def __init__(self, config: CapabilityConfig):
        self.config = config
    
    @abstractmethod
    async def execute(
        self, 
        context: "AgentContext",
        input_data: Any
    ) -> CapabilityResult:
        """执行能力"""
        pass
    
    @abstractmethod
    async def on_session_start(self, context: "AgentContext"):
        """会话开始时调用"""
        pass
    
    @abstractmethod
    async def on_session_end(self, context: "AgentContext") -> Dict[str, Any]:
        """会话结束时调用，返回统计数据"""
        pass
```

### 3.3 具体能力实现示例

```python
class ASRCapability(BaseCapability):
    """语音识别能力"""
    
    capability_id = "asr"
    name = "语音识别"
    description = "实时语音转文字"
    config_schema = {
        "type": "object",
        "properties": {
            "language": {"type": "string", "default": "zh-CN"},
            "dialect": {"type": "string", "enum": ["mandarin", "cantonese"]},
            "enable_punctuation": {"type": "boolean", "default": True},
            "timeout_ms": {"type": "number", "default": 5000}
        }
    }
    
    async def execute(self, context, audio_data) -> CapabilityResult:
        """执行语音识别 - 遵循规范的错误处理"""
        try:
            async with asyncio.timeout(self.config.params.get("timeout_ms", 5000) / 1000):
                transcript = await self.asr_service.transcribe(
                    audio_data,
                    language=self.config.params.get("language", "zh-CN")
                )
            return CapabilityResult(success=True, data=transcript)
        except TimeoutError:
            logger.warning("ASR timeout", session_id=context.session_id)
            return CapabilityResult(success=False, fallback="[USE_BROWSER_ASR]")
        except Exception as e:
            logger.error(f"ASR failed: {e}", session_id=context.session_id)
            return CapabilityResult(success=False, fallback="[USE_BROWSER_ASR]")
    
    async def on_session_start(self, context: "AgentContext"):
        """会话开始初始化"""
        context.state["asr_initialized"] = True
        context.state["asr_transcripts"] = []
    
    async def on_session_end(self, context: "AgentContext") -> Dict[str, Any]:
        """会话结束，返回统计"""
        return {
            "total_transcripts": len(context.state.get("asr_transcripts", [])),
            "asr_errors": context.state.get("asr_errors", 0)
        }


class InterruptionCapability(BaseCapability):
    """打断检测能力"""
    
    capability_id = "interruption"
    name = "打断检测"
    description = "根据规则实时打断用户"
    config_schema = {
        "type": "object",
        "properties": {
            "triggers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"enum": ["keyword", "regex", "semantic"]},
                        "pattern": {"type": "string"},
                        "response": {"type": "string"}
                    }
                },
                "maxItems": 50  # 边界限制
            },
            "cooldown_seconds": {"type": "number", "default": 5, "minimum": 1, "maximum": 30}
        }
    }
    
    async def execute(self, context, user_text) -> CapabilityResult:
        """执行打断检测 - 必须 <100ms"""
        try:
            # 检查冷却时间
            last_interrupt = context.state.get("last_interrupt_time")
            cooldown = self.config.params.get("cooldown_seconds", 5)
            if last_interrupt and (datetime.utcnow() - last_interrupt).seconds < cooldown:
                return CapabilityResult(success=True, should_interrupt=False)
            
            for trigger in self.config.params.get("triggers", []):
                if self._match_trigger(trigger, user_text):
                    context.state["last_interrupt_time"] = datetime.utcnow()
                    context.state["interrupt_count"] = context.state.get("interrupt_count", 0) + 1
                    return CapabilityResult(
                        success=True,
                        should_interrupt=True,
                        feedback=trigger["response"]
                    )
            return CapabilityResult(success=True, should_interrupt=False)
        except Exception as e:
            logger.error(f"Interruption check failed: {e}")
            return CapabilityResult(success=True, should_interrupt=False)  # 失败时不打断
    
    def _match_trigger(self, trigger: dict, text: str) -> bool:
        """匹配触发条件"""
        trigger_type = trigger.get("type", "keyword")
        pattern = trigger.get("pattern", "")
        
        if trigger_type == "keyword":
            return any(kw in text for kw in pattern.split("|"))
        elif trigger_type == "regex":
            return bool(re.search(pattern, text))
        return False
    
    async def on_session_start(self, context):
        context.state["interrupt_count"] = 0
        context.state["last_interrupt_time"] = None
    
    async def on_session_end(self, context) -> Dict[str, Any]:
        return {"total_interrupts": context.state.get("interrupt_count", 0)}


class KnowledgeCapability(BaseCapability):
    """知识库检索能力"""
    
    capability_id = "knowledge"
    name = "知识库检索"
    description = "基于知识库的RAG增强"
    config_schema = {
        "type": "object",
        "properties": {
            "knowledge_base_id": {"type": "string"},
            "top_k": {"type": "number", "default": 3, "minimum": 1, "maximum": 10},
            "similarity_threshold": {"type": "number", "default": 0.7, "minimum": 0, "maximum": 1},
            "timeout_seconds": {"type": "number", "default": 5}
        },
        "required": ["knowledge_base_id"]
    }
    
    async def execute(self, context, query) -> CapabilityResult:
        """执行知识库检索 - 带超时和降级"""
        try:
            async with asyncio.timeout(self.config.params.get("timeout_seconds", 5)):
                results = await self.vector_store.search(
                    collection=self.config.params["knowledge_base_id"],
                    query=query,
                    top_k=self.config.params.get("top_k", 3)
                )
            
            # 过滤低相似度结果
            threshold = self.config.params.get("similarity_threshold", 0.7)
            filtered = [r for r in results if r.score >= threshold]
            
            context.state["knowledge_queries"] = context.state.get("knowledge_queries", 0) + 1
            return CapabilityResult(success=True, data=filtered)
            
        except TimeoutError:
            logger.warning("Knowledge search timeout", session_id=context.session_id)
            return CapabilityResult(success=False, fallback="[USE_KEYWORD_SEARCH]")
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return CapabilityResult(success=False, fallback="[USE_KEYWORD_SEARCH]")
    
    async def on_session_start(self, context):
        context.state["knowledge_queries"] = 0
    
    async def on_session_end(self, context) -> Dict[str, Any]:
        return {"total_queries": context.state.get("knowledge_queries", 0)}
```

---

## 4. Agent 数据模型

### 4.1 数据库模型

```python
class Agent(Base):
    """Agent 配置表"""
    __tablename__ = "agents"
    
    agent_id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    icon = Column(String(200))  # 图标URL
    
    # 状态
    status = Column(String(20), default="draft")  # draft/published/archived
    version = Column(Integer, default=1)
    
    # 基础配置
    system_prompt = Column(Text)  # 系统提示词
    welcome_message = Column(String(500))  # 开场白
    
    # 能力配置 (JSON)
    capabilities_config = Column(JSON)  # {"asr": {...}, "llm": {...}}
    
    # 规则配置 (JSON)
    rules_config = Column(JSON)  # 打断规则、评分规则等
    
    # 关联
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id"))
    created_by = Column(String(36), ForeignKey("users.user_id"))
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    published_at = Column(DateTime)


class AgentCapability(Base):
    """Agent 启用的能力"""
    __tablename__ = "agent_capabilities"
    
    id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey("agents.agent_id"))
    capability_id = Column(String(50))  # asr, llm, tts, etc.
    enabled = Column(Boolean, default=True)
    config = Column(JSON)  # 能力特定配置
    priority = Column(Integer, default=0)  # 执行优先级


class KnowledgeBase(Base):
    """知识库"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100))
    description = Column(String(500))
    document_count = Column(Integer, default=0)
    vector_collection = Column(String(100))  # ChromaDB collection name
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 4.2 Agent 配置示例

```json
{
  "agent_id": "sales-coach-001",
  "name": "销售教练",
  "description": "帮助销售人员提升沟通技巧",
  "icon": "/icons/sales.png",
  "status": "published",
  
  "system_prompt": "你是一位资深销售教练，负责训练销售人员的沟通技巧。你会扮演不同类型的客户，给出挑战性的问题，并在用户表现不佳时给出指导。",
  
  "welcome_message": "你好！我是你的销售教练。今天我们来练习一下客户沟通。我会扮演一位挑剔的客户，准备好了吗？",
  
  "capabilities_config": {
    "asr": {
      "enabled": true,
      "language": "zh-CN"
    },
    "tts": {
      "enabled": true,
      "voice": "zh-CN-YunxiNeural",
      "rate": "+10%"
    },
    "llm": {
      "enabled": true,
      "model": "deepseek-chat",
      "temperature": 0.8,
      "max_tokens": 500
    },
    "interruption": {
      "enabled": true,
      "triggers": [
        {
          "type": "keyword",
          "pattern": "大概|可能|也许",
          "response": "客户不喜欢模糊的回答，请给出具体的数据或案例"
        },
        {
          "type": "semantic",
          "pattern": "价格太贵",
          "response": "当客户说贵的时候，不要直接降价，先了解他的预算和需求"
        }
      ]
    },
    "scoring": {
      "enabled": true,
      "dimensions": [
        {"name": "专业度", "weight": 0.3},
        {"name": "说服力", "weight": 0.3},
        {"name": "应变能力", "weight": 0.2},
        {"name": "沟通技巧", "weight": 0.2}
      ]
    },
    "persona": {
      "enabled": true,
      "personas": [
        {
          "id": "skeptical",
          "name": "怀疑型客户",
          "prompt": "你是一个非常怀疑的客户，对销售人员说的每句话都要求证据"
        },
        {
          "id": "price_focused",
          "name": "价格敏感型",
          "prompt": "你只关心价格，不断要求折扣"
        }
      ]
    }
  },
  
  "knowledge_base_id": "kb-sales-handbook"
}
```

---

## 5. Agent 运行时引擎

### 5.1 核心引擎

```python
class AgentRuntime:
    """Agent 运行时引擎"""
    
    def __init__(self):
        self.capability_registry: Dict[str, Type[BaseCapability]] = {}
        self.active_agents: Dict[str, "AgentInstance"] = {}
        self._register_builtin_capabilities()
    
    def _register_builtin_capabilities(self):
        """注册内置能力模块"""
        self.capability_registry = {
            "asr": ASRCapability,
            "tts": TTSCapability,
            "llm": LLMCapability,
            "knowledge": KnowledgeCapability,
            "interruption": InterruptionCapability,
            "scoring": ScoringCapability,
            "point_tracking": PointTrackingCapability,
            "forbidden_words": ForbiddenWordsCapability,
            "emotion": EmotionCapability,
            "timer": TimerCapability,
            "persona": PersonaCapability,
        }
    
    async def load_agent(self, agent_id: str) -> "AgentInstance":
        """从数据库加载 Agent 配置并实例化"""
        # 从数据库获取配置
        agent_config = await self._get_agent_config(agent_id)
        
        # 实例化能力模块
        capabilities = {}
        for cap_id, cap_config in agent_config.capabilities_config.items():
            if cap_config.get("enabled", True):
                cap_class = self.capability_registry.get(cap_id)
                if cap_class:
                    capabilities[cap_id] = cap_class(
                        CapabilityConfig(enabled=True, params=cap_config)
                    )
        
        # 创建 Agent 实例
        instance = AgentInstance(
            agent_id=agent_id,
            config=agent_config,
            capabilities=capabilities
        )
        
        self.active_agents[agent_id] = instance
        return instance
    
    async def create_session(
        self, 
        agent_id: str, 
        user_id: str,
        options: Dict[str, Any] = None
    ) -> str:
        """创建对话会话"""
        # 加载 Agent
        if agent_id not in self.active_agents:
            await self.load_agent(agent_id)
        
        agent = self.active_agents[agent_id]
        session_id = str(uuid.uuid4())
        
        # 创建会话上下文
        context = AgentContext(
            session_id=session_id,
            agent_id=agent_id,
            user_id=user_id,
            config=agent.config,
            options=options or {}
        )
        
        # 初始化各能力模块
        for cap in agent.capabilities.values():
            await cap.on_session_start(context)
        
        agent.sessions[session_id] = context
        return session_id


@dataclass
class AgentInstance:
    """Agent 实例"""
    agent_id: str
    config: AgentConfig
    capabilities: Dict[str, BaseCapability]
    sessions: Dict[str, "AgentContext"] = field(default_factory=dict)


@dataclass
class AgentContext:
    """会话上下文"""
    session_id: str
    agent_id: str
    user_id: str
    config: AgentConfig
    options: Dict[str, Any]
    history: List[Dict] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
```

### 5.2 消息处理流水线

```python
class AgentMessagePipeline:
    """消息处理流水线"""
    
    def __init__(self, agent: AgentInstance):
        self.agent = agent
    
    async def process(
        self, 
        context: AgentContext, 
        input_type: str,  # "audio" | "text"
        input_data: Any
    ) -> AgentResponse:
        """处理用户输入"""
        
        # 1. 语音识别 (如果是音频输入)
        if input_type == "audio" and "asr" in self.agent.capabilities:
            asr_result = await self.agent.capabilities["asr"].execute(
                context, input_data
            )
            user_text = asr_result.data
        else:
            user_text = input_data
        
        # 2. 打断检测 (并行执行)
        interrupt_response = None
        if "interruption" in self.agent.capabilities:
            interrupt_result = await self.agent.capabilities["interruption"].execute(
                context, user_text
            )
            if interrupt_result.should_interrupt:
                interrupt_response = interrupt_result.feedback
        
        # 3. 知识库检索 (如果启用)
        knowledge_context = ""
        if "knowledge" in self.agent.capabilities:
            knowledge_result = await self.agent.capabilities["knowledge"].execute(
                context, user_text
            )
            knowledge_context = self._format_knowledge(knowledge_result.data)
        
        # 4. LLM 生成响应
        llm_response = await self._generate_llm_response(
            context, user_text, knowledge_context, interrupt_response
        )
        
        # 5. 评分更新 (如果启用)
        if "scoring" in self.agent.capabilities:
            await self.agent.capabilities["scoring"].execute(
                context, {"user_text": user_text, "ai_response": llm_response}
            )
        
        # 6. 语音合成 (如果启用)
        audio_data = None
        if "tts" in self.agent.capabilities:
            tts_result = await self.agent.capabilities["tts"].execute(
                context, llm_response
            )
            audio_data = tts_result.data
        
        # 7. 更新历史
        context.history.append({
            "role": "user",
            "content": user_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        context.history.append({
            "role": "assistant", 
            "content": llm_response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return AgentResponse(
            text=llm_response,
            audio=audio_data,
            interrupted=interrupt_response is not None,
            interrupt_reason=interrupt_response
        )
```

---

## 6. 管理后台 API

### 6.1 Agent 管理 API

```python
# backend/src/admin/api/agents.py

@router.get("/admin/agents")
async def list_agents(
    status: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """获取 Agent 列表"""
    return await agent_service.list_agents(status=status)


@router.post("/admin/agents")
async def create_agent(
    request: CreateAgentRequest,
    current_user: User = Depends(require_admin)
):
    """创建新 Agent"""
    return await agent_service.create_agent(
        name=request.name,
        description=request.description,
        system_prompt=request.system_prompt,
        capabilities=request.capabilities,
        created_by=current_user.user_id
    )


@router.put("/admin/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    current_user: User = Depends(require_admin)
):
    """更新 Agent 配置"""
    return await agent_service.update_agent(agent_id, request)


@router.post("/admin/agents/{agent_id}/publish")
async def publish_agent(
    agent_id: str,
    current_user: User = Depends(require_admin)
):
    """发布 Agent"""
    return await agent_service.publish_agent(agent_id)


@router.get("/admin/agents/{agent_id}/test")
async def test_agent(
    agent_id: str,
    current_user: User = Depends(require_admin)
):
    """获取测试会话"""
    session_id = await agent_runtime.create_session(
        agent_id=agent_id,
        user_id=current_user.user_id,
        options={"test_mode": True}
    )
    return {"session_id": session_id}


@router.get("/admin/capabilities")
async def list_capabilities():
    """获取可用能力模块列表"""
    return {
        "capabilities": [
            {
                "id": "asr",
                "name": "语音识别",
                "description": "实时语音转文字",
                "config_schema": ASRCapability.config_schema
            },
            {
                "id": "tts",
                "name": "语音合成", 
                "description": "文字转语音",
                "config_schema": TTSCapability.config_schema
            },
            {
                "id": "llm",
                "name": "大模型对话",
                "description": "AI对话生成",
                "config_schema": LLMCapability.config_schema
            },
            # ... 其他能力
        ]
    }
```

### 6.2 知识库管理 API

```python
@router.post("/admin/knowledge-bases")
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    current_user: User = Depends(require_admin)
):
    """创建知识库"""
    return await knowledge_service.create_knowledge_base(
        name=request.name,
        description=request.description
    )


@router.post("/admin/knowledge-bases/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: UploadFile,
    current_user: User = Depends(require_admin)
):
    """上传文档到知识库"""
    return await knowledge_service.ingest_document(kb_id, file)


@router.delete("/admin/knowledge-bases/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(require_admin)
):
    """删除文档"""
    return await knowledge_service.delete_document(kb_id, doc_id)
```

---

## 7. 管理后台界面设计

### 7.1 Agent 列表页

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent 管理                                           [+ 创建 Agent]    │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🎯 销售教练                                    [已发布] [编辑]   │   │
│  │ 帮助销售人员提升沟通技巧                                         │   │
│  │ 能力: ASR | TTS | LLM | 打断检测 | 评分                         │   │
│  │ 使用次数: 1,234  平均评分: 4.5                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 📊 PPT演讲教练                                 [已发布] [编辑]   │   │
│  │ PPT演讲技能训练                                                  │   │
│  │ 能力: ASR | LLM | 要点追踪 | 禁用词 | 评分                       │   │
│  │ 使用次数: 856   平均评分: 4.3                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 📚 商务知识问答                                [草稿] [编辑]     │   │
│  │ 商务知识测试与学习                                               │   │
│  │ 能力: ASR | TTS | LLM | 知识库                                   │   │
│  │ 使用次数: -     平均评分: -                                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Agent 编辑页

```
┌─────────────────────────────────────────────────────────────────────────┐
│  编辑 Agent: 销售教练                              [保存] [测试] [发布] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  基本信息                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 名称: [销售教练                                              ]   │   │
│  │ 描述: [帮助销售人员提升沟通技巧                              ]   │   │
│  │ 图标: [🎯] [选择]                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  系统提示词                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 你是一位资深销售教练，负责训练销售人员的沟通技巧。              │   │
│  │ 你会扮演不同类型的客户，给出挑战性的问题...                     │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  能力模块                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [✓] 语音识别 (ASR)                                    [配置 ▼]  │   │
│  │     语言: 中文  方言: 普通话                                     │   │
│  │ [✓] 语音合成 (TTS)                                    [配置 ▼]  │   │
│  │     音色: 云希  语速: +10%                                       │   │
│  │ [✓] 大模型对话 (LLM)                                  [配置 ▼]  │   │
│  │     模型: deepseek-chat  温度: 0.8                               │   │
│  │ [✓] 打断检测                                          [配置 ▼]  │   │
│  │     触发词: 大概, 可能, 也许...                                  │   │
│  │ [✓] 评分系统                                          [配置 ▼]  │   │
│  │     维度: 专业度(30%), 说服力(30%), 应变(20%), 沟通(20%)        │   │
│  │ [ ] 知识库检索                                        [配置 ▼]  │   │
│  │ [ ] 情绪分析                                          [配置 ▼]  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  角色设定 (Persona)                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [+ 添加角色]                                                     │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ 怀疑型客户                                          [删除] │   │   │
│  │ │ 你是一个非常怀疑的客户，对销售人员说的每句话都要求证据     │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ 价格敏感型                                          [删除] │   │   │
│  │ │ 你只关心价格，不断要求折扣                                 │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 用户端 API

### 8.1 获取可用 Agent

```python
@router.get("/api/v1/agents")
async def list_available_agents(
    current_user: User = Depends(get_current_user)
):
    """获取用户可用的 Agent 列表"""
    agents = await agent_service.list_published_agents()
    return {
        "agents": [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "description": a.description,
                "icon": a.icon,
                "welcome_message": a.welcome_message
            }
            for a in agents
        ]
    }


@router.post("/api/v1/agents/{agent_id}/sessions")
async def create_agent_session(
    agent_id: str,
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user)
):
    """创建 Agent 对话会话"""
    session_id = await agent_runtime.create_session(
        agent_id=agent_id,
        user_id=current_user.user_id,
        options=request.options
    )
    
    return {
        "session_id": session_id,
        "websocket_url": f"/ws/agent/{session_id}"
    }
```

### 8.2 统一 WebSocket 端点

```python
@app.websocket("/ws/agent/{session_id}")
async def agent_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...)
):
    """统一的 Agent WebSocket 端点"""
    handler = AgentWebSocketHandler()
    await handler.handle_connection(websocket, session_id, token)


class AgentWebSocketHandler(BaseWebSocketHandler):
    """Agent WebSocket 处理器"""
    
    def __init__(self):
        super().__init__("agent")
        self.runtime = get_agent_runtime()
    
    async def handle_message(self, message: dict):
        session_id = message.get("session_id")
        msg_type = message.get("type")
        
        if msg_type == "audio":
            # 处理音频输入
            response = await self.runtime.process_message(
                session_id=session_id,
                input_type="audio",
                input_data=message.get("data")
            )
        elif msg_type == "text":
            # 处理文本输入
            response = await self.runtime.process_message(
                session_id=session_id,
                input_type="text", 
                input_data=message.get("text")
            )
        elif msg_type == "end":
            # 结束会话
            report = await self.runtime.end_session(session_id)
            await self.send_session_report(report)
            return
        
        # 发送响应
        await self.send_response(response)
```

---

## 9. 目录结构

```
backend/src/
├── main.py
├── common/
│   ├── ai/
│   ├── audio/
│   ├── db/
│   └── ...
├── agent/                          # 新增: Agent 平台核心
│   ├── __init__.py
│   ├── models.py                   # Agent 数据模型
│   ├── runtime.py                  # Agent 运行时引擎
│   ├── pipeline.py                 # 消息处理流水线
│   ├── capabilities/               # 能力模块
│   │   ├── __init__.py
│   │   ├── base.py                 # 能力基类
│   │   ├── asr.py                  # 语音识别
│   │   ├── tts.py                  # 语音合成
│   │   ├── llm.py                  # 大模型对话
│   │   ├── knowledge.py            # 知识库检索
│   │   ├── interruption.py         # 打断检测
│   │   ├── scoring.py              # 评分系统
│   │   ├── point_tracking.py       # 要点追踪
│   │   ├── forbidden_words.py      # 禁用词检测
│   │   ├── emotion.py              # 情绪分析
│   │   ├── timer.py                # 计时器
│   │   └── persona.py              # 角色扮演
│   ├── api/
│   │   └── agents.py               # 用户端 API
│   └── websocket/
│       └── agent_handler.py        # WebSocket 处理
├── admin/
│   └── api/
│       ├── admin.py
│       ├── agents.py               # 新增: Agent 管理 API
│       └── knowledge_bases.py      # 新增: 知识库管理 API
└── presentation_coach/             # 保留: 可作为预置 Agent
└── sales_bot/                      # 保留: 可作为预置 Agent
```

---

## 10. 实施计划

### 第一阶段: 核心框架 (2周)

```
1. 能力模块基础设施
   ├── BaseCapability 抽象类
   ├── 能力注册机制
   └── 配置 Schema 定义

2. Agent 运行时引擎
   ├── AgentRuntime 核心类
   ├── 消息处理流水线
   └── 会话管理

3. 数据模型
   ├── Agent 表
   ├── AgentCapability 表
   └── KnowledgeBase 表
```

### 第二阶段: 能力模块迁移 (2周)

```
1. 迁移现有能力
   ├── ASR → ASRCapability
   ├── TTS → TTSCapability
   ├── LLM → LLMCapability
   └── 打断检测 → InterruptionCapability

2. 新增能力
   ├── KnowledgeCapability (RAG)
   ├── ScoringCapability
   └── PersonaCapability
```

### 第三阶段: 管理后台 (2周)

```
1. 后端 API
   ├── Agent CRUD
   ├── 能力配置
   └── 知识库管理

2. 前端界面
   ├── Agent 列表页
   ├── Agent 编辑页
   └── 测试对话界面
```

### 第四阶段: 迁移现有场景 (1周)

```
1. PPT演讲教练 → 预置 Agent
2. 销售对练 → 预置 Agent
3. 验证兼容性
```

---

## 11. 规范遵循说明

本设计遵循 `.kiro/steering/agent-platform.md` 中定义的开发规范：

### 11.1 核心原则遵循

| 原则 | 实现方式 |
|------|----------|
| 用户体验永不中断 | 所有能力模块返回 `CapabilityResult`，失败时返回 `fallback` 代码 |
| 实时优先 | ASR/打断检测设置超时，并行执行独立操作 |
| 可追踪性 | `AgentContext` 包含 `session_id`，所有日志附加 |
| 容错与降级 | 每个能力都有 fallback 策略 |
| 成本控制 | `AgentContext.state` 追踪 token 使用 |

### 11.2 边界条件

```python
# 必须在实现时遵循的限制
AGENT_LIMITS = {
    "name_max_length": 100,
    "description_max_length": 500,
    "system_prompt_max_length": 4000,
    "welcome_message_max_length": 500,
    "max_capabilities": 15,
    "max_personas": 10,
    "max_interruption_triggers": 50,
    "max_scoring_dimensions": 10,
}

SESSION_LIMITS = {
    "max_duration_seconds": 1800,  # 30分钟
    "max_history_messages": 100,
    "max_message_length": 2000,
    "max_tokens_per_session": 5000,
    "warning_tokens_threshold": 4000,
}

PERFORMANCE_TARGETS = {
    "asr_latency_ms": 200,
    "interruption_latency_ms": 100,
    "llm_timeout_seconds": 10,
    "websocket_heartbeat_seconds": 30,
}
```

### 11.3 Fallback 代码映射

| 代码 | 触发条件 | 前端处理 |
|------|----------|----------|
| `[USE_BROWSER_ASR]` | ASR 服务超时/失败 | 切换到 Web Speech API |
| `[USE_BROWSER_TTS]` | TTS 服务失败 | 切换到浏览器 TTS |
| `[FALLBACK_RESPONSE]` | LLM 超时 | 显示预定义响应 |
| `[USE_KEYWORD_SEARCH]` | 向量检索失败 | 降级到关键词匹配 |
| `[SESSION_EXPIRED]` | 会话超时 | 提示重新开始 |
| `[TOKEN_LIMIT_WARNING]` | 接近 token 限制 | 显示警告 |
| `[TOKEN_LIMIT_EXCEEDED]` | 超出 token 限制 | 强制结束会话 |

---

## 12. 总结

这个设计让你可以：

1. **后台可视化配置** - 管理员无需写代码，通过界面创建 Agent
2. **能力模块化** - ASR、TTS、LLM、知识库等能力像积木一样组合
3. **快速扩展** - 新增场景只需配置，不需要开发
4. **统一运行时** - 所有 Agent 共用一套引擎，维护成本低
5. **灵活定制** - 每个 Agent 可以有不同的能力组合和配置
6. **规范一致** - 遵循统一的错误处理、日志、性能标准

这样你就可以轻松创建：
- 商务知识问答 Agent
- 技术面试 Agent  
- 客服培训 Agent
- 产品演示 Agent
- 任何你想要的对话场景！