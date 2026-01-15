# 通用对话引擎设计方案

## 1. 核心理念

将现有的 PPT 演讲教练和销售对练抽象为一个**通用对话引擎**，支持任意对话场景的快速扩展。

### 1.1 抽象层次

```
┌─────────────────────────────────────────────────────────────┐
│                    业务场景层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PPT演讲教练│  │ 销售对练 │  │商务知识问答│  │技术面试  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   对话引擎核心                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ConversationEngine                      │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │   │
│  │  │会话管理 │  │消息路由 │  │状态追踪 │  │评分系统 │ │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    基础服务层                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐    │
│  │ ASR服务 │  │ LLM服务 │  │ TTS服务 │  │ WebSocket   │    │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心组件设计

### 2.1 对话引擎核心 (ConversationEngine)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class ConversationMode(str, Enum):
    """对话模式"""
    COACHING = "coaching"        # 教练模式 (PPT演讲)
    ROLEPLAY = "roleplay"        # 角色扮演 (销售对练)
    QA = "qa"                    # 问答模式 (知识问答)
    INTERVIEW = "interview"      # 面试模式
    DEBATE = "debate"            # 辩论模式

@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    user_id: str
    mode: ConversationMode
    scenario_config: Dict[str, Any]  # 场景特定配置
    knowledge_base: Optional[str] = None  # 知识库ID
    persona: Optional[str] = None         # AI角色
    rules: List[str] = None              # 对话规则
    metadata: Dict[str, Any] = None      # 扩展元数据

@dataclass
class ConversationMessage:
    """对话消息"""
    content: str
    message_type: str  # "user" | "assistant" | "system"
    timestamp: datetime
    metadata: Dict[str, Any] = None

@dataclass
class ConversationResponse:
    """对话响应"""
    text: str
    should_interrupt: bool = False
    feedback_type: Optional[str] = None  # "correction" | "encouragement" | "challenge"
    confidence: float = 1.0
    next_action: Optional[str] = None
    metadata: Dict[str, Any] = None
```

### 2.2 场景处理器接口

```python
class ConversationHandler(ABC):
    """对话处理器基类 - 每个场景实现此接口"""
    
    @abstractmethod
    async def initialize_session(self, context: ConversationContext) -> Dict[str, Any]:
        """初始化会话"""
        pass
    
    @abstractmethod
    async def process_user_input(
        self, 
        context: ConversationContext,
        user_input: str,
        history: List[ConversationMessage]
    ) -> ConversationResponse:
        """处理用户输入"""
        pass
    
    @abstractmethod
    async def should_interrupt(
        self, 
        context: ConversationContext,
        user_input: str
    ) -> bool:
        """判断是否需要打断"""
        pass
    
    @abstractmethod
    async def calculate_score(
        self,
        context: ConversationContext,
        history: List[ConversationMessage]
    ) -> Dict[str, float]:
        """计算评分"""
        pass
    
    @abstractmethod
    async def end_session(
        self,
        context: ConversationContext,
        history: List[ConversationMessage]
    ) -> Dict[str, Any]:
        """结束会话，生成报告"""
        pass
```
---

## 3. 具体场景实现示例

### 3.1 PPT 演讲教练处理器

```python
class PresentationCoachHandler(ConversationHandler):
    """PPT演讲教练处理器"""
    
    async def initialize_session(self, context: ConversationContext) -> Dict[str, Any]:
        # 加载PPT内容和要点
        presentation_id = context.scenario_config.get("presentation_id")
        required_points = await self._load_required_points(presentation_id)
        forbidden_words = await self._load_forbidden_words(presentation_id)
        
        return {
            "required_points": required_points,
            "forbidden_words": forbidden_words,
            "current_page": 1,
            "covered_points": []
        }
    
    async def process_user_input(
        self, 
        context: ConversationContext,
        user_input: str,
        history: List[ConversationMessage]
    ) -> ConversationResponse:
        
        # 检查禁用词
        if await self._contains_forbidden_words(user_input, context):
            return ConversationResponse(
                text="请避免使用填充词，保持表达简洁",
                should_interrupt=True,
                feedback_type="correction"
            )
        
        # 检查要点覆盖
        missing_points = await self._check_missing_points(user_input, context)
        if missing_points:
            return ConversationResponse(
                text=f"别忘了提到：{missing_points[0]}",
                should_interrupt=True,
                feedback_type="reminder"
            )
        
        # 正面反馈
        return ConversationResponse(
            text="很好，继续",
            should_interrupt=False,
            feedback_type="encouragement"
        )
```

### 3.2 商务知识问答处理器

```python
class BusinessQAHandler(ConversationHandler):
    """商务知识问答处理器"""
    
    async def initialize_session(self, context: ConversationContext) -> Dict[str, Any]:
        # 加载知识库
        knowledge_base = context.scenario_config.get("knowledge_base", "business_general")
        topics = await self._load_knowledge_topics(knowledge_base)
        
        return {
            "knowledge_base": knowledge_base,
            "available_topics": topics,
            "current_topic": None,
            "question_count": 0,
            "correct_answers": 0
        }
    
    async def process_user_input(
        self, 
        context: ConversationContext,
        user_input: str,
        history: List[ConversationMessage]
    ) -> ConversationResponse:
        
        # 如果是回答问题
        if self._is_answering_question(history):
            is_correct = await self._evaluate_answer(user_input, context)
            
            if is_correct:
                next_question = await self._generate_next_question(context)
                return ConversationResponse(
                    text=f"正确！下一个问题：{next_question}",
                    feedback_type="encouragement"
                )
            else:
                correct_answer = await self._get_correct_answer(context)
                return ConversationResponse(
                    text=f"不太准确。正确答案是：{correct_answer}",
                    feedback_type="correction"
                )
        
        # 如果是提问
        else:
            question = await self._generate_question_from_topic(user_input, context)
            return ConversationResponse(
                text=question,
                feedback_type="challenge"
            )
```

### 3.3 技术面试处理器

```python
class TechnicalInterviewHandler(ConversationHandler):
    """技术面试处理器"""
    
    async def initialize_session(self, context: ConversationContext) -> Dict[str, Any]:
        tech_stack = context.scenario_config.get("tech_stack", ["python", "javascript"])
        difficulty = context.scenario_config.get("difficulty", "intermediate")
        
        return {
            "tech_stack": tech_stack,
            "difficulty": difficulty,
            "current_question": None,
            "question_history": [],
            "performance_score": 0
        }
    
    async def process_user_input(
        self, 
        context: ConversationContext,
        user_input: str,
        history: List[ConversationMessage]
    ) -> ConversationResponse:
        
        # 评估技术回答
        evaluation = await self._evaluate_technical_answer(user_input, context)
        
        if evaluation["score"] >= 0.8:
            follow_up = await self._generate_follow_up_question(user_input, context)
            return ConversationResponse(
                text=f"很好！让我们深入一点：{follow_up}",
                feedback_type="challenge"
            )
        elif evaluation["score"] >= 0.5:
            hint = await self._generate_hint(context)
            return ConversationResponse(
                text=f"思路对了，但可以更具体一些。提示：{hint}",
                feedback_type="guidance"
            )
        else:
            explanation = await self._generate_explanation(context)
            return ConversationResponse(
                text=f"让我解释一下这个概念：{explanation}",
                feedback_type="teaching"
            )
```

---

## 4. 引擎核心实现

### 4.1 对话引擎主类

```python
class ConversationEngine:
    """通用对话引擎"""
    
    def __init__(self):
        self.handlers: Dict[ConversationMode, ConversationHandler] = {}
        self.active_sessions: Dict[str, ConversationSession] = {}
        self.llm_service = get_llm_service()
        self.asr_service = get_asr_service()
    
    def register_handler(self, mode: ConversationMode, handler: ConversationHandler):
        """注册场景处理器"""
        self.handlers[mode] = handler
    
    async def create_session(
        self,
        user_id: str,
        mode: ConversationMode,
        scenario_config: Dict[str, Any]
    ) -> str:
        """创建对话会话"""
        session_id = str(uuid.uuid4())
        
        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            mode=mode,
            scenario_config=scenario_config
        )
        
        handler = self.handlers.get(mode)
        if not handler:
            raise ValueError(f"No handler registered for mode: {mode}")
        
        # 初始化会话
        session_data = await handler.initialize_session(context)
        
        session = ConversationSession(
            context=context,
            handler=handler,
            data=session_data,
            history=[],
            created_at=datetime.utcnow()
        )
        
        self.active_sessions[session_id] = session
        return session_id
    
    async def process_message(
        self,
        session_id: str,
        user_input: str
    ) -> ConversationResponse:
        """处理用户消息"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # 添加用户消息到历史
        user_message = ConversationMessage(
            content=user_input,
            message_type="user",
            timestamp=datetime.utcnow()
        )
        session.history.append(user_message)
        
        # 处理消息
        response = await session.handler.process_user_input(
            session.context,
            user_input,
            session.history
        )
        
        # 添加AI响应到历史
        ai_message = ConversationMessage(
            content=response.text,
            message_type="assistant",
            timestamp=datetime.utcnow(),
            metadata={"feedback_type": response.feedback_type}
        )
        session.history.append(ai_message)
        
        return response
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """结束会话"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # 生成会话报告
        report = await session.handler.end_session(
            session.context,
            session.history
        )
        
        # 清理会话
        del self.active_sessions[session_id]
        
        return report

@dataclass
class ConversationSession:
    """对话会话"""
    context: ConversationContext
    handler: ConversationHandler
    data: Dict[str, Any]
    history: List[ConversationMessage]
    created_at: datetime
```
---

## 5. 新场景扩展示例

### 5.1 添加"客服培训"场景

```python
class CustomerServiceHandler(ConversationHandler):
    """客服培训处理器"""
    
    async def initialize_session(self, context: ConversationContext) -> Dict[str, Any]:
        # 加载客服场景配置
        scenarios = [
            "投诉处理", "退款申请", "产品咨询", 
            "技术支持", "账户问题"
        ]
        
        return {
            "available_scenarios": scenarios,
            "current_scenario": None,
            "customer_satisfaction": 5.0,  # 初始满意度
            "resolution_time": 0,
            "empathy_score": 0
        }
    
    async def process_user_input(
        self, 
        context: ConversationContext,
        user_input: str,
        history: List[ConversationMessage]
    ) -> ConversationResponse:
        
        # 分析用户情绪
        emotion = await self._analyze_emotion(user_input)
        
        # 检查是否使用了同理心语言
        empathy_detected = await self._detect_empathy(user_input)
        
        # 检查解决方案是否合理
        solution_quality = await self._evaluate_solution(user_input, context)
        
        if emotion == "angry" and not empathy_detected:
            return ConversationResponse(
                text="客户很生气，记得先表达理解和歉意",
                should_interrupt=True,
                feedback_type="correction"
            )
        
        if solution_quality < 0.6:
            return ConversationResponse(
                text="这个解决方案可能不够完善，考虑提供更多选择",
                feedback_type="guidance"
            )
        
        return ConversationResponse(
            text="处理得很好，继续保持专业态度",
            feedback_type="encouragement"
        )
```

### 5.2 添加"产品演示"场景

```python
class ProductDemoHandler(ConversationHandler):
    """产品演示处理器"""
    
    async def initialize_session(self, context: ConversationContext) -> Dict[str, Any]:
        product_info = context.scenario_config.get("product_info", {})
        demo_script = context.scenario_config.get("demo_script", [])
        
        return {
            "product_info": product_info,
            "demo_script": demo_script,
            "current_step": 0,
            "key_features_mentioned": [],
            "customer_questions": [],
            "engagement_level": 5.0
        }
    
    async def process_user_input(
        self, 
        context: ConversationContext,
        user_input: str,
        history: List[ConversationMessage]
    ) -> ConversationResponse:
        
        # 检查是否按演示脚本进行
        script_adherence = await self._check_script_adherence(user_input, context)
        
        # 检查是否提到关键特性
        features_mentioned = await self._extract_features(user_input, context)
        
        # 检查是否回答了客户问题
        questions_addressed = await self._check_question_handling(user_input, context)
        
        if script_adherence < 0.5:
            return ConversationResponse(
                text="记得按照演示脚本的顺序介绍产品",
                feedback_type="guidance"
            )
        
        if not features_mentioned:
            return ConversationResponse(
                text="别忘了强调这个功能的核心价值",
                feedback_type="reminder"
            )
        
        return ConversationResponse(
            text="演示很流畅，客户看起来很感兴趣",
            feedback_type="encouragement"
        )
```

---

## 6. 统一 API 接口

### 6.1 REST API

```python
# 新的统一API路由
@router.post("/api/v1/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user)
):
    """创建对话会话"""
    session_id = await conversation_engine.create_session(
        user_id=current_user.user_id,
        mode=request.mode,
        scenario_config=request.config
    )
    
    return {
        "session_id": session_id,
        "websocket_url": f"/ws/conversation/{session_id}"
    }

@router.get("/api/v1/conversations/modes")
async def get_conversation_modes():
    """获取支持的对话模式"""
    return {
        "modes": [
            {
                "id": "coaching",
                "name": "演讲教练",
                "description": "PPT演讲技能训练",
                "config_schema": {...}
            },
            {
                "id": "roleplay", 
                "name": "角色扮演",
                "description": "销售对练、客服培训等",
                "config_schema": {...}
            },
            {
                "id": "qa",
                "name": "知识问答", 
                "description": "商务知识、技术知识问答",
                "config_schema": {...}
            },
            {
                "id": "interview",
                "name": "模拟面试",
                "description": "技术面试、HR面试模拟",
                "config_schema": {...}
            }
        ]
    }
```

### 6.2 WebSocket 统一处理

```python
@app.websocket("/ws/conversation/{session_id}")
async def conversation_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...)
):
    """统一的对话WebSocket端点"""
    handler = ConversationWebSocketHandler()
    await handler.handle_connection(websocket, session_id, token)

class ConversationWebSocketHandler(BaseWebSocketHandler):
    """统一对话WebSocket处理器"""
    
    def __init__(self):
        super().__init__("conversation")
        self.engine = get_conversation_engine()
    
    async def handle_message(self, message: dict):
        msg_type = message.get("type")
        session_id = message.get("session_id")
        
        if msg_type == "audio":
            # 语音识别
            audio_data = message.get("data")
            transcript = await self.asr_service.transcribe(audio_data)
            
            # 处理对话
            response = await self.engine.process_message(session_id, transcript)
            
            # 发送响应
            await self.send_response(response)
        
        elif msg_type == "text":
            # 文本输入
            text = message.get("text")
            response = await self.engine.process_message(session_id, text)
            await self.send_response(response)
        
        elif msg_type == "end_session":
            # 结束会话
            report = await self.engine.end_session(session_id)
            await self.send_session_report(report)
```

---

## 7. 配置驱动的场景定义

### 7.1 场景配置文件

```yaml
# scenarios/business_qa.yaml
name: "商务知识问答"
mode: "qa"
description: "商务相关知识的问答练习"

config:
  knowledge_base: "business_general"
  difficulty_levels: ["beginner", "intermediate", "advanced"]
  topics:
    - "市场营销"
    - "财务管理" 
    - "项目管理"
    - "商务谈判"
  
  scoring:
    accuracy_weight: 0.6
    speed_weight: 0.2
    completeness_weight: 0.2

prompts:
  system: |
    你是一位资深的商务顾问，负责测试用户的商务知识。
    根据用户的回答给出专业的评价和建议。
  
  question_templates:
    - "在{scenario}情况下，你会如何{action}？"
    - "请解释{concept}的核心要点"
    - "分析{case_study}中的关键成功因素"

rules:
  - "问题难度应该循序渐进"
  - "给出具体的改进建议"
  - "鼓励深入思考"
```

### 7.2 动态场景加载

```python
class ScenarioManager:
    """场景管理器"""
    
    def __init__(self):
        self.scenarios: Dict[str, Dict] = {}
        self.load_scenarios()
    
    def load_scenarios(self):
        """从配置文件加载场景"""
        scenario_dir = Path("scenarios")
        for config_file in scenario_dir.glob("*.yaml"):
            with open(config_file) as f:
                config = yaml.safe_load(f)
                self.scenarios[config["name"]] = config
    
    def create_handler(self, scenario_name: str) -> ConversationHandler:
        """根据配置创建处理器"""
        config = self.scenarios.get(scenario_name)
        if not config:
            raise ValueError(f"Scenario not found: {scenario_name}")
        
        mode = ConversationMode(config["mode"])
        
        if mode == ConversationMode.QA:
            return BusinessQAHandler(config)
        elif mode == ConversationMode.COACHING:
            return PresentationCoachHandler(config)
        elif mode == ConversationMode.ROLEPLAY:
            return RoleplayHandler(config)
        # ... 其他模式
        
        raise ValueError(f"Unsupported mode: {mode}")
```
---

## 8. 实施路线图

### 8.1 第一阶段：重构现有功能

```
1. 抽取通用对话引擎核心
   ├── 创建 ConversationEngine 基类
   ├── 定义 ConversationHandler 接口
   └── 实现统一的会话管理

2. 重构现有场景
   ├── PresentationCoachHandler (PPT演讲教练)
   ├── SalesBotHandler (销售对练)
   └── 保持现有API兼容性

3. 统一WebSocket处理
   ├── 合并现有的WebSocket处理器
   └── 实现统一的消息路由
```

### 8.2 第二阶段：扩展新场景

```
1. 商务知识问答
   ├── BusinessQAHandler
   ├── 知识库集成 (ChromaDB)
   └── 智能问题生成

2. 技术面试模拟
   ├── TechnicalInterviewHandler  
   ├── 多技术栈支持
   └── 代码评估能力

3. 客服培训
   ├── CustomerServiceHandler
   ├── 情绪分析
   └── 满意度评估
```

### 8.3 第三阶段：高级功能

```
1. 配置驱动的场景定义
   ├── YAML配置文件
   ├── 动态场景加载
   └── 可视化场景编辑器

2. 多模态支持
   ├── 视频分析 (表情、手势)
   ├── 屏幕共享
   └── 文档协作

3. 高级AI能力
   ├── 多Agent协作
   ├── 长期记忆
   └── 个性化学习路径
```

---

## 9. 技术优势

### 9.1 可扩展性

```
新增场景只需要：
1. 实现 ConversationHandler 接口
2. 定义场景配置文件
3. 注册到引擎中

无需修改核心代码，完全插件化
```

### 9.2 复用性

```
通用能力复用：
├── ASR/TTS 语音处理
├── LLM 对话生成  
├── WebSocket 实时通信
├── 评分系统
├── 会话管理
└── 用户认证
```

### 9.3 一致性

```
统一的：
├── API 接口规范
├── WebSocket 消息格式
├── 错误处理机制
├── 日志追踪
└── 性能监控
```

---

## 10. 使用示例

### 10.1 添加新场景：产品培训

```python
# 1. 实现处理器
class ProductTrainingHandler(ConversationHandler):
    async def initialize_session(self, context):
        return {
            "product_catalog": await load_products(),
            "training_modules": ["features", "pricing", "competition"],
            "current_module": 0,
            "knowledge_score": 0
        }
    
    async def process_user_input(self, context, user_input, history):
        # 检查产品知识准确性
        accuracy = await self._check_product_knowledge(user_input)
        
        if accuracy < 0.7:
            return ConversationResponse(
                text="这个产品信息不太准确，让我纠正一下...",
                feedback_type="correction"
            )
        
        return ConversationResponse(
            text="很好！你对产品的理解很到位",
            feedback_type="encouragement"
        )

# 2. 注册到引擎
conversation_engine.register_handler(
    ConversationMode.TRAINING, 
    ProductTrainingHandler()
)

# 3. 创建会话
session_id = await conversation_engine.create_session(
    user_id="user123",
    mode=ConversationMode.TRAINING,
    scenario_config={
        "product_line": "enterprise_software",
        "difficulty": "intermediate"
    }
)
```

### 10.2 前端集成

```javascript
// 统一的对话客户端
class ConversationClient {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.ws = new WebSocket(`/ws/conversation/${sessionId}`);
    }
    
    sendMessage(text) {
        this.ws.send(JSON.stringify({
            type: "text",
            session_id: this.sessionId,
            text: text
        }));
    }
    
    sendAudio(audioData) {
        this.ws.send(JSON.stringify({
            type: "audio", 
            session_id: this.sessionId,
            data: audioData
        }));
    }
}

// 使用示例
const client = new ConversationClient(sessionId);
client.sendMessage("我想了解产品的核心功能");
```

---

## 11. 总结

通过这个通用对话引擎设计，你可以：

1. **快速扩展新场景** - 只需实现处理器接口
2. **复用核心能力** - ASR、LLM、WebSocket等基础服务
3. **保持一致体验** - 统一的API和交互模式
4. **配置驱动** - 通过配置文件定义场景，无需代码修改
5. **插件化架构** - 新功能以插件形式添加

这样的架构让你的AI对话平台具备了无限的扩展可能性！