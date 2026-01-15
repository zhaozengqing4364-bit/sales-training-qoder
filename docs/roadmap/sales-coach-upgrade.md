# 销售教练升级技术方案

> 基于现有 Agent 配置平台设计，整合销售对练功能升级需求

## 1. 项目背景

### 1.1 当前状态

销售对练功能已实现基础能力：
- ✅ ASR 语音识别 (阿里云 Manual 模式)
- ✅ TTS 语音合成 (Edge-TTS)
- ✅ LLM 对话生成 (DeepSeek/Qwen)
- ✅ WebSocket 实时通信
- ✅ 多角色 Persona 选择
- ✅ 会话评分报告

### 1.2 核心问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 多轮对话 Bug | 第二轮录音无法正常工作 | P0 |
| 无实时反馈 | 用户只能在结束后看到评价 | P1 |
| 无产品知识库 | AI 客户无法讨论具体产品 | P1 |
| 评分维度单一 | 当前评分过于抽象 | P2 |
| 无对话回放 | 无法复盘学习 | P2 |

### 1.3 目标

将销售对练升级为**智能销售教练**，具备：
1. 实时指导能力 (模糊词检测、话术建议)
2. 产品知识增强 (RAG)
3. 结构化销售流程引导
4. 完整的复盘回放功能


---

## 2. 架构设计

### 2.1 整体架构 (基于 Agent 配置平台)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         管理后台 (Admin UI)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Agent管理   │  │ 能力模块    │  │ 知识库管理  │  │ 数据分析    │    │
│  │ (销售教练)  │  │ (选择/配置) │  │ (产品资料)  │  │ (使用统计)  │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Agent 运行时引擎                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    AgentRuntime                                  │   │
│  │  根据配置动态加载能力模块，组装成可运行的销售教练                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         能力模块库 (Capabilities)                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │   ASR   │ │   LLM   │ │   TTS   │ │ 知识检索 │ │模糊词检测│          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │销售阶段 │ │ 评分系统 │ │ 角色扮演 │ │对话回放 │ │ 计时器  │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流架构

```
用户语音 ──▶ ASR识别 ──▶ 文本分析 ──┬──▶ 模糊词检测 ──▶ 实时提示
                            │       │
                            │       ├──▶ 知识库检索 ──▶ 增强上下文
                            │       │
                            │       └──▶ 销售阶段 ──▶ 流程引导
                            │
                            ▼
                       LLM生成 ──▶ TTS播放 ──▶ AI客户回复
                            │
                            ▼
                       评分更新 ──▶ 实时反馈
```


---

## 3. 能力模块设计

### 3.1 模块清单

| 模块ID | 名称 | 说明 | 状态 |
|--------|------|------|------|
| `asr` | 语音识别 | 阿里云 Manual 模式 | ✅ 已实现 |
| `tts` | 语音合成 | Edge-TTS | ✅ 已实现 |
| `llm` | 大模型对话 | DeepSeek/Qwen | ✅ 已实现 |
| `persona` | 角色扮演 | AI 客户角色 | ✅ 已实现 |
| `knowledge` | 知识库检索 | RAG 产品知识 | 🔨 待实现 |
| `fuzzy_detection` | 模糊词检测 | 实时检测模糊表达 | 🔨 待实现 |
| `sales_stage` | 销售阶段 | 流程引导 | 🔨 待实现 |
| `scoring` | 评分系统 | 多维度评分 | 🔧 需升级 |
| `replay` | 对话回放 | 逐句回放+点评 | 🔨 待实现 |

### 3.2 模糊词检测能力 (FuzzyDetectionCapability)

**功能**: 实时检测销售话术中的模糊表达，给出改进建议

**配置项**:
```python
config_schema = {
    "fuzzy_patterns": [
        {"pattern": "大概|可能|也许|应该", "category": "uncertain", 
         "suggestion": "请给出具体数据或案例", "severity": "high"},
        {"pattern": "嗯|啊|那个|就是说", "category": "filler",
         "suggestion": "减少填充词，保持表达流畅", "severity": "low"},
        {"pattern": "不太清楚|不确定|不好说", "category": "vague",
         "suggestion": "如不确定，可以说'我确认后回复您'", "severity": "medium"}
    ],
    "detection_mode": "realtime",  # realtime | post_turn
    "cooldown_seconds": 10  # 同类提示冷却时间
}
```

**实现要点**:
- 前端本地检测 (低延迟) + 后端验证
- 高严重度触发实时打断提示
- 统计模糊词使用频率，纳入评分

### 3.3 产品知识库能力 (KnowledgeCapability)

**功能**: 基于 RAG 的产品知识增强，让 AI 客户能讨论具体产品

**技术方案**:
- 使用现有 ChromaDB 向量存储
- 支持上传产品手册、FAQ、竞品对比等文档
- 检索结果注入 LLM 上下文

**配置项**:
```python
config_schema = {
    "knowledge_base_id": "product_catalog",
    "top_k": 3,
    "similarity_threshold": 0.7,
    "inject_mode": "context"  # system_prompt | context | both
}
```

### 3.4 销售阶段能力 (SalesStageCapability)

**功能**: 识别当前销售阶段，提供流程引导

**销售阶段定义**:
1. **开场破冰** - 建立信任，了解客户背景
2. **需求挖掘** - 深入了解客户痛点和需求
3. **方案呈现** - 展示产品价值和解决方案
4. **异议处理** - 处理客户疑虑和反对意见
5. **促成成交** - 推动决策，达成合作

**实现要点**:
- 使用 LLM 判断阶段转换信号
- 每个阶段提供关键动作提示
- 记录阶段转换历史，用于评分


---

## 4. 评分系统升级

### 4.1 多维度评分

| 维度 | 权重 | 评估内容 |
|------|------|----------|
| 专业度 | 25% | 产品知识准确性、行业术语使用 |
| 沟通技巧 | 25% | 提问技巧、倾听反馈、语言流畅度 |
| 销售流程 | 20% | 阶段把控、需求挖掘深度 |
| 异议处理 | 15% | 应对客户质疑的能力 |
| 成交能力 | 15% | 促成意愿、行动号召 |

### 4.2 实时评分反馈

```typescript
interface RealtimeScore {
  dimension: string;
  score: number;
  trend: 'up' | 'down' | 'stable';
  feedback?: string;
}

// WebSocket 消息
{
  "type": "score_update",
  "data": {
    "overall": 78,
    "dimensions": [
      {"dimension": "专业度", "score": 85, "trend": "up"},
      {"dimension": "沟通技巧", "score": 72, "trend": "stable", 
       "feedback": "注意减少填充词"}
    ]
  }
}
```

---

## 5. 对话回放功能

### 5.1 数据存储

```python
class ConversationTurn(Base):
    """对话轮次"""
    __tablename__ = "conversation_turns"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("practice_sessions.session_id"))
    turn_number = Column(Integer)
    role = Column(String(20))  # user | assistant
    content = Column(Text)
    audio_url = Column(String(500))  # 音频文件 URL
    timestamp = Column(DateTime)
    
    # 分析数据
    fuzzy_words = Column(JSON)  # 检测到的模糊词
    sales_stage = Column(String(50))  # 当前销售阶段
    score_snapshot = Column(JSON)  # 该轮次的评分快照
    ai_feedback = Column(Text)  # AI 点评
```

### 5.2 回放界面功能

- 逐句播放音频
- 显示每句的 AI 点评
- 标注模糊词和改进建议
- 显示销售阶段进度
- 对比优秀话术示例


---

## 6. 销售教练 Agent 配置示例

```json
{
  "agent_id": "sales-coach-v2",
  "name": "智能销售教练",
  "description": "帮助销售人员提升沟通技巧的 AI 教练",
  "status": "published",
  
  "system_prompt": "你是一位资深销售教练，负责训练销售人员的沟通技巧。你会扮演不同类型的客户，给出挑战性的问题，并在用户表现不佳时给出指导。",
  
  "welcome_message": "你好！我是你的销售教练。今天我们来练习一下客户沟通。我会扮演一位挑剔的客户，准备好了吗？",
  
  "capabilities_config": {
    "asr": {
      "enabled": true,
      "mode": "manual",
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
    "knowledge": {
      "enabled": true,
      "knowledge_base_id": "product_catalog",
      "top_k": 3
    },
    "fuzzy_detection": {
      "enabled": true,
      "detection_mode": "realtime",
      "cooldown_seconds": 10
    },
    "sales_stage": {
      "enabled": true
    },
    "scoring": {
      "enabled": true,
      "dimensions": [
        {"name": "专业度", "weight": 0.25},
        {"name": "沟通技巧", "weight": 0.25},
        {"name": "销售流程", "weight": 0.20},
        {"name": "异议处理", "weight": 0.15},
        {"name": "成交能力", "weight": 0.15}
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
        },
        {
          "id": "busy_ceo",
          "name": "急躁CEO",
          "prompt": "你是一位时间紧迫的CEO，要求简洁明了，不喜欢废话"
        },
        {
          "id": "tech_cto",
          "name": "技术CTO",
          "prompt": "你是技术背景的CTO，关注技术细节，不接受营销话术"
        }
      ]
    }
  },
  
  "knowledge_base_id": "product_catalog"
}
```

---

## 7. 前端界面设计

### 7.1 实时反馈面板

```
┌─────────────────────────────────────────────────────────────┐
│  销售对练                                    [结束练习]      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  AI 客户: 怀疑型客户                                 │   │
│  │  "你们的产品真的能解决我的问题吗？有什么证据？"       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  [🎤 按住说话]                                       │   │
│  │  ════════════════════════════════ (音频波形)         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  💡 实时提示                                         │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ ⚠️ 检测到模糊词 "大概"                        │    │   │
│  │  │ 建议: 请给出具体数据或案例                    │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ 📊 当前阶段: 方案呈现                         │    │   │
│  │  │ 关键动作: 匹配需求、展示价值、提供案例        │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📈 实时评分                                         │   │
│  │  专业度: ████████░░ 80  ↑                           │   │
│  │  沟通技巧: ██████░░░░ 60  ↓                         │   │
│  │  销售流程: ███████░░░ 70  →                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 对话回放界面

```
┌─────────────────────────────────────────────────────────────┐
│  对话回放                                    [返回]         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  销售阶段进度:                                              │
│  [开场破冰] ─── [需求挖掘] ─── [方案呈现] ─── [异议处理]    │
│      ✓            ✓            ●                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  轮次 3 / 8                              [▶️] [⏭️]    │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  👤 用户:                                            │   │
│  │  "我们的产品大概能帮您节省30%的成本"                  │   │
│  │                                                      │   │
│  │  ⚠️ 模糊词: "大概"                                   │   │
│  │  💡 改进建议: 使用具体数据，如"根据XX客户案例，       │   │
│  │     平均节省32.5%的运营成本"                         │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  🤖 AI 点评:                                         │   │
│  │  这轮回答展示了产品价值，但使用了模糊表达。          │   │
│  │  建议引用具体客户案例增强说服力。                    │   │
│  │  评分: 专业度 -5, 沟通技巧 -3                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📊 优秀话术参考:                                    │   │
│  │  "根据我们服务的XX公司案例，他们在使用我们产品后，   │   │
│  │   第一季度就实现了32.5%的成本节省，具体来说..."      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```


---

## 8. WebSocket 消息协议扩展

### 8.1 新增消息类型

#### 服务端 → 客户端

```typescript
// 模糊词检测结果
{
  "type": "fuzzy_detection",
  "data": {
    "detections": [
      {
        "category": "uncertain",
        "matched": ["大概"],
        "suggestion": "请给出具体数据或案例",
        "severity": "high"
      }
    ]
  }
}

// 销售阶段更新
{
  "type": "stage_update",
  "data": {
    "current_stage": "presentation",
    "stage_name": "方案呈现",
    "key_actions": ["匹配需求", "展示价值", "提供案例"],
    "guidance": "客户已表达需求，现在是展示产品价值的好时机"
  }
}

// 实时评分更新
{
  "type": "score_update",
  "data": {
    "overall": 72,
    "dimensions": [
      {"name": "专业度", "score": 80, "trend": "up", "delta": 5},
      {"name": "沟通技巧", "score": 65, "trend": "down", "delta": -3}
    ],
    "feedback": "注意减少模糊表达"
  }
}

// 知识库检索结果 (调试用)
{
  "type": "knowledge_context",
  "data": {
    "query": "产品价格",
    "results": [
      {"content": "标准版: ¥9,999/年", "score": 0.92}
    ]
  }
}
```

---

## 9. 实施路线图

### 9.1 Phase 1: 基础修复 (1周)

| 任务 | 优先级 | 预估 |
|------|--------|------|
| 修复多轮对话 Bug | P0 | 2天 |
| 优化录音组件稳定性 | P0 | 1天 |
| 添加详细日志追踪 | P1 | 1天 |
| 单元测试补充 | P1 | 1天 |

### 9.2 Phase 2: 实时反馈 (2周)

| 任务 | 优先级 | 预估 |
|------|--------|------|
| 模糊词检测能力实现 | P1 | 3天 |
| 前端实时提示组件 | P1 | 2天 |
| 销售阶段检测能力 | P2 | 3天 |
| 实时评分系统升级 | P2 | 2天 |

### 9.3 Phase 3: 知识增强 (2周)

| 任务 | 优先级 | 预估 |
|------|--------|------|
| 产品知识库管理界面 | P1 | 3天 |
| RAG 检索集成 | P1 | 3天 |
| 知识注入 LLM 上下文 | P1 | 2天 |
| 知识库效果测试 | P2 | 2天 |

### 9.4 Phase 4: 复盘回放 (2周)

| 任务 | 优先级 | 预估 |
|------|--------|------|
| 对话轮次数据存储 | P2 | 2天 |
| 回放界面开发 | P2 | 4天 |
| AI 点评生成 | P2 | 2天 |
| 优秀话术推荐 | P3 | 2天 |

---

## 10. 技术风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 模糊词检测延迟 | 实时反馈体验差 | 前端本地检测 + 后端验证 |
| RAG 检索准确率低 | 知识增强效果差 | 调优 embedding 模型，增加人工标注 |
| LLM 阶段判断不准 | 流程引导混乱 | 结合规则引擎 + LLM 双重判断 |
| 音频存储成本高 | 回放功能成本 | 压缩存储，设置保留期限 |

---

## 11. 成功指标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 多轮对话成功率 | ~50% | >95% |
| 用户练习完成率 | 60% | >80% |
| 平均练习时长 | 3分钟 | >8分钟 |
| 用户满意度 | - | >4.0/5.0 |
| 模糊词使用减少 | - | >30% |

---

## 12. 参考文档

- [Agent 配置平台设计](./agent-platform-design.md)
- [通用对话引擎设计](./conversation-engine-design.md)
- [系统架构文档](./architecture.md)
- [阿里云实时语音识别 API](../实时语音识别.md)


---

## 13. 角色与知识库配置设计

### 13.1 核心概念关系

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           实体关系图                                     │
│                                                                         │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐       │
│  │ KnowledgeBase│◀───────│   Persona   │────────▶│    Agent    │       │
│  │  (知识库)    │  N:N   │  (AI角色)   │   N:N   │ (训练场景)  │       │
│  └─────────────┘         └─────────────┘         └─────────────┘       │
│        │                       │                       │               │
│        │                       │                       │               │
│        ▼                       ▼                       ▼               │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐       │
│  │  Document   │         │PromptTemplate│        │ Capability  │       │
│  │  (文档)     │         │ (提示词模板) │        │ (能力模块)  │       │
│  └─────────────┘         └─────────────┘         └─────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

关系说明:
- Persona 可以绑定多个 KnowledgeBase (如: 怀疑型客户 + 产品知识 + 竞品知识)
- Agent 可以包含多个 Persona 供用户选择
- Agent 也可以有自己的默认 KnowledgeBase
- 能力模块在 Agent 级别配置，所有 Persona 共享
```

### 13.2 数据模型设计

```python
# ==================== 知识库相关 ====================

class KnowledgeBase(Base):
    """知识库 - 独立管理，可被多个 Persona/Agent 引用"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)  # 如: "产品手册-企业版"
    description = Column(String(500))
    category = Column(String(50))  # product | competitor | faq | policy
    
    # ChromaDB 配置
    vector_collection = Column(String(100), unique=True)
    embedding_model = Column(String(100), default="text-embedding-ada-002")
    
    # 统计
    document_count = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    
    # 状态
    status = Column(String(20), default="active")  # active | archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # 关系
    documents = relationship("Document", back_populates="knowledge_base")


class Document(Base):
    """知识库文档"""
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id"))
    
    title = Column(String(200))
    file_type = Column(String(20))  # pdf | docx | txt | md
    file_url = Column(String(500))
    
    # 处理状态
    status = Column(String(20), default="pending")  # pending | processing | ready | failed
    chunk_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")


# ==================== 角色相关 ====================

class Persona(Base):
    """AI 角色 - 独立管理，可被多个 Agent 引用"""
    __tablename__ = "personas"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)  # 如: "怀疑型客户"
    description = Column(String(500))
    icon = Column(String(50))  # emoji 或图标名
    category = Column(String(50))  # customer | interviewer | coach | examiner
    difficulty = Column(String(20), default="medium")  # easy | medium | hard
    
    # 核心: 角色提示词
    system_prompt = Column(Text, nullable=False)
    
    # 角色特征 (JSON)
    traits = Column(JSON)  # {"性格": "急躁", "关注点": "价格", "沟通风格": "直接"}
    
    # 角色专属知识库 (可选)
    knowledge_base_ids = Column(JSON)  # ["kb-product", "kb-competitor"]
    
    # 对话行为配置
    behavior_config = Column(JSON)
    # {
    #   "response_length": "short",  # short | medium | long
    #   "challenge_frequency": 0.7,  # 挑战用户的频率
    #   "interruption_triggers": ["价格", "折扣"],  # 触发打断的关键词
    #   "typical_questions": ["你们和XX比有什么优势?", "能便宜点吗?"]
    # }
    
    # 状态
    is_public = Column(Boolean, default=True)  # 是否公开可用
    status = Column(String(20), default="active")
    created_by = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


# ==================== Agent 相关 ====================

class Agent(Base):
    """训练场景 Agent - 组合能力模块和角色"""
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)  # 如: "销售对练"
    description = Column(String(500))
    icon = Column(String(200))
    category = Column(String(50))  # sales | presentation | interview | customer_service
    
    # 基础配置
    system_prompt = Column(Text)  # Agent 级别的系统提示词
    welcome_message = Column(String(500))
    
    # 能力模块配置 (JSON)
    capabilities_config = Column(JSON)
    # {
    #   "asr": {"enabled": true, "mode": "manual"},
    #   "tts": {"enabled": true, "voice": "zh-CN-YunxiNeural"},
    #   "llm": {"enabled": true, "model": "deepseek-chat"},
    #   "fuzzy_detection": {"enabled": true},
    #   "scoring": {"enabled": true, "dimensions": [...]}
    # }
    
    # Agent 默认知识库 (所有角色共享)
    default_knowledge_base_ids = Column(JSON)  # ["kb-company-intro"]
    
    # 状态
    status = Column(String(20), default="draft")  # draft | published | archived
    version = Column(Integer, default=1)
    
    created_by = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    published_at = Column(DateTime)


class AgentPersona(Base):
    """Agent 与 Persona 的关联表"""
    __tablename__ = "agent_personas"
    
    id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey("agents.id"))
    persona_id = Column(String(36), ForeignKey("personas.id"))
    
    # 在该 Agent 中的配置覆盖
    display_order = Column(Integer, default=0)  # 显示顺序
    is_default = Column(Boolean, default=False)  # 是否默认选中
    
    # 可覆盖角色的部分配置
    override_config = Column(JSON)  # 如覆盖 difficulty 或添加额外知识库
    
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 13.3 知识库绑定策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        知识库绑定层级                                    │
│                                                                         │
│  优先级: Persona 专属 > Agent 默认 > 全局公共                            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  会话开始时，知识库合并逻辑:                                      │   │
│  │                                                                  │   │
│  │  1. 获取 Agent 默认知识库                                        │   │
│  │     └─ ["kb-company-intro", "kb-product-overview"]              │   │
│  │                                                                  │   │
│  │  2. 获取选中 Persona 的专属知识库                                 │   │
│  │     └─ ["kb-competitor-analysis"] (怀疑型客户需要竞品知识)        │   │
│  │                                                                  │   │
│  │  3. 合并去重                                                     │   │
│  │     └─ ["kb-company-intro", "kb-product-overview",              │   │
│  │         "kb-competitor-analysis"]                                │   │
│  │                                                                  │   │
│  │  4. RAG 检索时从所有绑定的知识库中检索                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**知识库类型建议**:

| 类型 | 绑定层级 | 示例 |
|------|----------|------|
| 公司介绍 | Agent 默认 | 公司背景、发展历程 |
| 产品知识 | Agent 默认 | 产品功能、定价、案例 |
| 竞品分析 | Persona 专属 | 怀疑型客户需要 |
| 价格政策 | Persona 专属 | 价格敏感型客户需要 |
| 技术文档 | Persona 专属 | 技术 CTO 需要 |
| FAQ | Agent 默认 | 常见问题解答 |

### 13.4 管理后台界面设计

#### 13.4.1 角色管理页面

```
┌─────────────────────────────────────────────────────────────────────────┐
│  角色管理                                              [+ 创建角色]      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  筛选: [全部▼] [客户类▼] [面试官类▼]              搜索: [________]      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 😤 怀疑型客户                              难度: ⭐⭐⭐ [编辑]    │   │
│  │ 对销售人员说的每句话都要求证据，喜欢质疑                         │   │
│  │ 绑定知识库: 产品手册 | 竞品分析                                  │   │
│  │ 使用次数: 234  被 3 个 Agent 引用                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 💰 价格敏感型                              难度: ⭐⭐ [编辑]      │   │
│  │ 只关心价格，不断要求折扣和优惠                                   │   │
│  │ 绑定知识库: 产品手册 | 价格政策                                  │   │
│  │ 使用次数: 189  被 2 个 Agent 引用                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ⏰ 急躁 CEO                                难度: ⭐⭐⭐⭐ [编辑]  │   │
│  │ 时间紧迫，要求简洁明了，不喜欢废话                               │   │
│  │ 绑定知识库: 产品手册                                             │   │
│  │ 使用次数: 156  被 2 个 Agent 引用                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 13.4.2 角色编辑页面

```
┌─────────────────────────────────────────────────────────────────────────┐
│  编辑角色: 怀疑型客户                                [保存] [测试]       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  基本信息                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 名称: [怀疑型客户                                            ]   │   │
│  │ 图标: [😤] [选择]                                                │   │
│  │ 分类: [客户类 ▼]                                                 │   │
│  │ 难度: [⭐⭐⭐ 困难 ▼]                                             │   │
│  │ 描述: [对销售人员说的每句话都要求证据，喜欢质疑              ]   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  角色提示词 (核心)                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 你是一个非常怀疑的客户，有以下特点:                              │   │
│  │ 1. 对销售人员说的每句话都持怀疑态度                              │   │
│  │ 2. 经常要求提供数据、案例或证据来支持说法                        │   │
│  │ 3. 会主动提出竞品对比的问题                                      │   │
│  │ 4. 不轻易相信"行业领先"、"最好"等营销话术                        │   │
│  │ 5. 喜欢追问细节，如"具体是多少？"、"有案例吗？"                  │   │
│  │                                                                  │   │
│  │ 你的典型问题:                                                    │   │
│  │ - "你说的这个数据有什么依据？"                                   │   │
│  │ - "你们和XX公司比有什么优势？"                                   │   │
│  │ - "能给我看看具体的客户案例吗？"                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  角色特征                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 性格: [怀疑、谨慎                    ]                           │   │
│  │ 关注点: [证据、数据、案例            ]                           │   │
│  │ 沟通风格: [追问细节、要求证明        ]                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  绑定知识库                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [+ 添加知识库]                                                   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ 📚 产品手册-企业版                                  [移除] │   │   │
│  │ │ 包含产品功能、定价、技术规格                               │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ 📊 竞品分析报告                                     [移除] │   │   │
│  │ │ 主要竞品对比、优劣势分析                                   │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  行为配置                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 回复长度: [中等 ▼]                                               │   │
│  │ 挑战频率: [████████░░] 80%                                       │   │
│  │ 打断触发词: [竞品, 对比, 优势, 证据] [+ 添加]                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 13.4.3 Agent 编辑页面 (角色选择部分)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  编辑 Agent: 销售对练                              [保存] [测试] [发布] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ... (基本信息、能力模块配置) ...                                       │
│                                                                         │
│  默认知识库 (所有角色共享)                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [+ 添加知识库]                                                   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ 📚 公司介绍                                         [移除] │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ 📚 产品概览                                         [移除] │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  可选角色                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [+ 添加角色]                                                     │   │
│  │                                                                  │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ [✓] 😤 怀疑型客户                    [默认] [↑] [↓] [移除] │   │   │
│  │ │ 难度: ⭐⭐⭐  专属知识库: 竞品分析                          │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ [✓] 💰 价格敏感型                          [↑] [↓] [移除] │   │   │
│  │ │ 难度: ⭐⭐   专属知识库: 价格政策                           │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ [✓] ⏰ 急躁 CEO                            [↑] [↓] [移除] │   │   │
│  │ │ 难度: ⭐⭐⭐⭐ 专属知识库: 无                               │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ [✓] 🔧 技术 CTO                            [↑] [↓] [移除] │   │   │
│  │ │ 难度: ⭐⭐⭐⭐ 专属知识库: 技术文档                         │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.5 运行时知识库合并逻辑

```python
class AgentRuntime:
    """Agent 运行时引擎"""
    
    async def get_session_knowledge_bases(
        self, 
        agent_id: str, 
        persona_id: str
    ) -> List[str]:
        """获取会话需要使用的知识库列表"""
        
        # 1. 获取 Agent 默认知识库
        agent = await self.get_agent(agent_id)
        kb_ids = set(agent.default_knowledge_base_ids or [])
        
        # 2. 获取 Persona 专属知识库
        persona = await self.get_persona(persona_id)
        if persona.knowledge_base_ids:
            kb_ids.update(persona.knowledge_base_ids)
        
        # 3. 检查 AgentPersona 关联表是否有覆盖配置
        agent_persona = await self.get_agent_persona(agent_id, persona_id)
        if agent_persona and agent_persona.override_config:
            extra_kbs = agent_persona.override_config.get("extra_knowledge_bases", [])
            kb_ids.update(extra_kbs)
        
        return list(kb_ids)
    
    async def build_rag_context(
        self, 
        query: str, 
        knowledge_base_ids: List[str],
        top_k: int = 3
    ) -> str:
        """从多个知识库检索并构建上下文"""
        
        all_results = []
        
        for kb_id in knowledge_base_ids:
            results = await self.vector_store.search(
                collection=kb_id,
                query=query,
                top_k=top_k
            )
            all_results.extend(results)
        
        # 按相似度排序，取 top_k
        all_results.sort(key=lambda x: x.score, reverse=True)
        top_results = all_results[:top_k]
        
        # 格式化为上下文
        if not top_results:
            return ""
        
        context_parts = ["[参考知识]"]
        for r in top_results:
            context_parts.append(f"- {r.content}")
        
        return "\n".join(context_parts)
```

### 13.6 场景复用示例

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        场景复用示例                                      │
│                                                                         │
│  共享能力模块:                                                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │   ASR   │ │   LLM   │ │   TTS   │ │ 评分系统 │ │模糊词检测│          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│       │           │           │           │           │                │
│       └───────────┴───────────┴───────────┴───────────┘                │
│                               │                                         │
│              ┌────────────────┼────────────────┐                        │
│              ▼                ▼                ▼                        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐           │
│  │  销售对练 Agent  │ │ 客服培训 Agent  │ │ 技术面试 Agent  │           │
│  ├─────────────────┤ ├─────────────────┤ ├─────────────────┤           │
│  │ 角色:           │ │ 角色:           │ │ 角色:           │           │
│  │ - 怀疑型客户    │ │ - 投诉客户      │ │ - 严格面试官    │           │
│  │ - 价格敏感型    │ │ - 咨询客户      │ │ - 友好面试官    │           │
│  │ - 急躁CEO       │ │ - 退款客户      │ │ - 压力面试官    │           │
│  ├─────────────────┤ ├─────────────────┤ ├─────────────────┤           │
│  │ 默认知识库:     │ │ 默认知识库:     │ │ 默认知识库:     │           │
│  │ - 产品手册      │ │ - 服务政策      │ │ - 技术题库      │           │
│  │ - 公司介绍      │ │ - FAQ           │ │ - 评分标准      │           │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**复用优势**:
1. **能力模块复用** - ASR、TTS、LLM 等基础能力一次开发，所有 Agent 共享
2. **角色复用** - 同一个角色可被多个 Agent 引用
3. **知识库复用** - 产品知识库可被销售、客服等多个场景使用
4. **配置驱动** - 新建场景只需配置，无需写代码


---

## 14. 深度分析：遗漏与待完善点

### 14.1 对话状态与上下文管理

**问题**: 当前设计没有详细说明对话上下文如何在多轮对话中维护和传递。

```
┌─────────────────────────────────────────────────────────────────────────┐
│  需要考虑的上下文类型                                                    │
│                                                                         │
│  1. 对话历史 (Conversation History)                                     │
│     - 用户说了什么、AI 回复了什么                                        │
│     - 需要限制长度，避免 token 超限                                      │
│     - 摘要策略: 超过 N 轮后自动摘要压缩                                  │
│                                                                         │
│  2. 会话状态 (Session State)                                            │
│     - 当前销售阶段                                                      │
│     - 已覆盖的要点                                                      │
│     - 累计评分                                                          │
│     - 模糊词使用统计                                                    │
│                                                                         │
│  3. 角色记忆 (Persona Memory)                                           │
│     - AI 角色在对话中"记住"的信息                                       │
│     - 如: 用户提到的预算、痛点、决策时间线                               │
│     - 用于后续追问和挑战                                                │
│                                                                         │
│  4. 知识检索缓存 (Knowledge Cache)                                      │
│     - 避免重复检索相同内容                                              │
│     - 会话级别缓存                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

**补充设计**:

```python
@dataclass
class ConversationContext:
    """完整的对话上下文"""
    session_id: str
    agent_id: str
    persona_id: str
    user_id: str
    
    # 对话历史 (带摘要)
    history: List[Message]
    history_summary: Optional[str] = None  # 超过阈值后的摘要
    
    # 会话状态
    state: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "current_stage": "discovery",
    #   "covered_points": ["公司介绍", "产品功能"],
    #   "fuzzy_word_count": 3,
    #   "scores": {"专业度": 75, "沟通技巧": 68}
    # }
    
    # 角色记忆 (AI 从对话中提取的关键信息)
    persona_memory: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "user_budget": "50万以内",
    #   "pain_points": ["效率低", "成本高"],
    #   "decision_timeline": "Q2",
    #   "competitors_mentioned": ["竞品A"]
    # }
    
    # 知识检索缓存
    knowledge_cache: Dict[str, List[str]] = field(default_factory=dict)
```

### 14.2 Persona 行为一致性

**问题**: 仅靠提示词控制 AI 角色行为，可能出现"人设崩塌"。

**风险场景**:
- 怀疑型客户突然变得很好说话
- 价格敏感型客户不再关心价格
- AI 角色忘记之前说过的话

**补充设计**:

```python
class PersonaBehaviorGuard:
    """角色行为守卫 - 确保 AI 行为符合角色设定"""
    
    def __init__(self, persona: Persona):
        self.persona = persona
        self.behavior_rules = self._build_rules()
    
    def _build_rules(self) -> List[BehaviorRule]:
        """根据角色特征构建行为规则"""
        rules = []
        
        # 怀疑型客户: 必须在回复中包含质疑
        if "怀疑" in self.persona.traits.get("性格", ""):
            rules.append(BehaviorRule(
                name="must_question",
                check=lambda response: any(q in response for q in ["?", "？", "为什么", "怎么证明"]),
                fallback_prompt="记住你是怀疑型客户，请在回复中加入质疑或追问"
            ))
        
        # 价格敏感型: 必须提及价格相关
        if "价格" in self.persona.traits.get("关注点", ""):
            rules.append(BehaviorRule(
                name="price_focus",
                check=lambda response: any(w in response for w in ["价格", "费用", "成本", "折扣", "优惠"]),
                fallback_prompt="记住你非常关注价格，请在回复中体现对价格的关注"
            ))
        
        return rules
    
    async def validate_and_fix(self, response: str, context: ConversationContext) -> str:
        """验证并修复不符合角色的回复"""
        for rule in self.behavior_rules:
            if not rule.check(response):
                # 重新生成，加入强化提示
                response = await self._regenerate_with_hint(response, rule.fallback_prompt, context)
        return response
```

### 14.3 评分公平性与可解释性

**问题**: 当前评分设计缺乏透明度，用户不知道为什么得分高/低。

**补充设计**:

```python
@dataclass
class ScoreExplanation:
    """评分解释"""
    dimension: str
    score: int
    max_score: int
    
    # 得分项
    positive_factors: List[Dict]
    # [{"factor": "使用了具体数据", "points": +5, "evidence": "提到了32%的成本节省"}]
    
    # 扣分项
    negative_factors: List[Dict]
    # [{"factor": "使用模糊词", "points": -3, "evidence": "说了'大概'"}]
    
    # 改进建议
    suggestions: List[str]


class TransparentScoring:
    """透明评分系统"""
    
    async def calculate_with_explanation(
        self, 
        turn: ConversationTurn,
        context: ConversationContext
    ) -> Tuple[Dict[str, int], List[ScoreExplanation]]:
        """计算评分并生成解释"""
        
        explanations = []
        scores = {}
        
        # 专业度评分
        prof_score, prof_explain = await self._score_professionalism(turn, context)
        scores["专业度"] = prof_score
        explanations.append(prof_explain)
        
        # ... 其他维度
        
        return scores, explanations
    
    async def _score_professionalism(self, turn, context) -> Tuple[int, ScoreExplanation]:
        """专业度评分"""
        base_score = 70
        positive = []
        negative = []
        
        # 检查是否使用了产品术语
        product_terms = await self._extract_product_terms(turn.content, context)
        if product_terms:
            base_score += 5
            positive.append({
                "factor": "正确使用产品术语",
                "points": 5,
                "evidence": f"提到了: {', '.join(product_terms)}"
            })
        
        # 检查是否有数据支撑
        if self._has_specific_data(turn.content):
            base_score += 8
            positive.append({
                "factor": "使用具体数据",
                "points": 8,
                "evidence": "引用了具体数字或案例"
            })
        
        # 检查模糊词
        fuzzy_words = self._detect_fuzzy_words(turn.content)
        if fuzzy_words:
            penalty = min(len(fuzzy_words) * 3, 15)
            base_score -= penalty
            negative.append({
                "factor": "使用模糊表达",
                "points": -penalty,
                "evidence": f"使用了: {', '.join(fuzzy_words)}"
            })
        
        return base_score, ScoreExplanation(
            dimension="专业度",
            score=base_score,
            max_score=100,
            positive_factors=positive,
            negative_factors=negative,
            suggestions=self._generate_suggestions(positive, negative)
        )
```

### 14.4 对话结束条件

**问题**: 什么时候结束对话？当前没有明确定义。

**补充设计**:

```python
class SessionEndConditions:
    """会话结束条件"""
    
    # 硬性条件 (任一满足即结束)
    MAX_TURNS = 15  # 最大轮次
    MAX_DURATION_MINUTES = 20  # 最大时长
    MAX_TOKENS = 8000  # 最大 token 消耗
    
    # 软性条件 (建议结束)
    SUGGESTED_TURNS = 8  # 建议轮次
    ALL_STAGES_COVERED = True  # 所有销售阶段都经历过
    
    # 自然结束信号
    NATURAL_END_SIGNALS = [
        "好的，我考虑一下",
        "我需要和团队商量",
        "发个资料给我看看",
        "下次再聊"
    ]
    
    async def should_end(self, context: ConversationContext) -> Tuple[bool, str]:
        """判断是否应该结束"""
        
        # 硬性条件
        if len(context.history) >= self.MAX_TURNS * 2:
            return True, "已达到最大对话轮次"
        
        duration = (datetime.utcnow() - context.created_at).total_seconds() / 60
        if duration >= self.MAX_DURATION_MINUTES:
            return True, "已达到最大时长"
        
        # 自然结束信号
        last_ai_message = context.history[-1].content if context.history else ""
        for signal in self.NATURAL_END_SIGNALS:
            if signal in last_ai_message:
                return True, "对话自然结束"
        
        # 建议结束
        if len(context.history) >= self.SUGGESTED_TURNS * 2:
            stages_covered = len(set(context.state.get("stage_history", [])))
            if stages_covered >= 4:  # 经历了大部分阶段
                return False, "建议结束，已完成主要销售流程"
        
        return False, ""
```

### 14.5 异常处理与降级策略

**问题**: 各种服务失败时如何处理？

```
┌─────────────────────────────────────────────────────────────────────────┐
│  异常场景与降级策略                                                      │
│                                                                         │
│  场景                    │ 降级策略                                     │
│  ───────────────────────┼────────────────────────────────────────────  │
│  ASR 识别失败            │ 提示用户重说，或切换到文字输入                 │
│  LLM 响应超时            │ 返回预设的"思考中"回复，后台重试               │
│  LLM 响应不符合角色      │ 重新生成，最多 2 次，否则用模板回复            │
│  知识库检索失败          │ 不注入知识，仅用基础 prompt                   │
│  TTS 合成失败            │ 只显示文字，不播放语音                        │
│  WebSocket 断开          │ 自动重连，恢复会话状态                        │
│  评分计算失败            │ 跳过本轮评分，不影响对话                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**补充设计**:

```python
class GracefulDegradation:
    """优雅降级处理"""
    
    # LLM 降级回复模板
    LLM_FALLBACK_RESPONSES = {
        "skeptical": [
            "嗯，你说的这个我需要再想想...",
            "这个说法我持保留意见",
            "能再详细说说吗？"
        ],
        "price_focused": [
            "价格方面还能再谈谈吗？",
            "这个价格对我们来说还是有点高",
            "有没有更优惠的方案？"
        ],
        "default": [
            "嗯，继续说",
            "然后呢？",
            "我在听，请继续"
        ]
    }
    
    async def handle_llm_failure(
        self, 
        persona_id: str, 
        context: ConversationContext,
        retry_count: int = 0
    ) -> str:
        """处理 LLM 失败"""
        
        if retry_count < 2:
            # 重试
            await asyncio.sleep(1)
            return None  # 返回 None 表示需要重试
        
        # 使用降级回复
        persona_type = self._get_persona_type(persona_id)
        responses = self.LLM_FALLBACK_RESPONSES.get(
            persona_type, 
            self.LLM_FALLBACK_RESPONSES["default"]
        )
        return random.choice(responses)
```

### 14.6 多租户与权限控制

**问题**: 如果要支持多个企业/团队使用，权限如何设计？

```
┌─────────────────────────────────────────────────────────────────────────┐
│  多租户权限模型                                                          │
│                                                                         │
│  ┌─────────────┐                                                        │
│  │   Tenant    │  租户 (企业)                                           │
│  │  (企业A)    │                                                        │
│  └──────┬──────┘                                                        │
│         │                                                               │
│    ┌────┴────┐                                                          │
│    ▼         ▼                                                          │
│  ┌─────┐  ┌─────┐                                                       │
│  │Admin│  │User │  角色                                                 │
│  └──┬──┘  └──┬──┘                                                       │
│     │        │                                                          │
│     ▼        ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  权限矩阵                                                        │   │
│  │                                                                  │   │
│  │  资源              │ Admin │ User │ 说明                         │   │
│  │  ─────────────────┼───────┼──────┼─────────────────────────────  │   │
│  │  Agent 管理        │  ✓    │  ✗   │ 创建/编辑/发布 Agent          │   │
│  │  Persona 管理      │  ✓    │  ✗   │ 创建/编辑角色                 │   │
│  │  知识库管理        │  ✓    │  ✗   │ 上传/删除文档                 │   │
│  │  使用 Agent        │  ✓    │  ✓   │ 进行练习                     │   │
│  │  查看自己的记录    │  ✓    │  ✓   │ 历史、评分                   │   │
│  │  查看团队数据      │  ✓    │  ✗   │ 排行榜、统计                 │   │
│  │  导出数据          │  ✓    │  ✗   │ 导出练习记录                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  数据隔离:                                                              │
│  - 每个租户的 Agent、Persona、知识库相互隔离                             │
│  - 可以有"公共"资源供所有租户使用                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 14.7 数据分析与洞察

**问题**: 收集了这么多数据，如何产生价值？

**补充设计**:

```python
class AnalyticsService:
    """数据分析服务"""
    
    async def get_user_insights(self, user_id: str) -> UserInsights:
        """用户个人洞察"""
        return UserInsights(
            # 能力雷达图
            skill_radar={
                "专业度": 78,
                "沟通技巧": 65,
                "异议处理": 72,
                "成交能力": 58
            },
            
            # 常见问题
            common_issues=[
                {"issue": "模糊表达过多", "frequency": 0.4, "trend": "improving"},
                {"issue": "缺乏数据支撑", "frequency": 0.3, "trend": "stable"},
            ],
            
            # 进步曲线
            progress_curve=[
                {"date": "2025-01-01", "score": 65},
                {"date": "2025-01-08", "score": 72},
                {"date": "2025-01-11", "score": 78},
            ],
            
            # 个性化建议
            recommendations=[
                "建议多练习'怀疑型客户'场景，提升应对质疑的能力",
                "尝试在回答中加入更多具体数据和案例"
            ]
        )
    
    async def get_team_insights(self, tenant_id: str) -> TeamInsights:
        """团队洞察"""
        return TeamInsights(
            # 团队平均水平
            team_average_scores={...},
            
            # 最常见的问题
            top_issues=[...],
            
            # 最有效的角色 (哪个角色训练效果最好)
            most_effective_personas=[...],
            
            # 知识库使用情况
            knowledge_usage_stats={...}
        )
```

### 14.8 Prompt 版本管理

**问题**: Persona 的提示词修改后，如何追踪效果变化？

**补充设计**:

```python
class PromptVersion(Base):
    """提示词版本管理"""
    __tablename__ = "prompt_versions"
    
    id = Column(String(36), primary_key=True)
    persona_id = Column(String(36), ForeignKey("personas.id"))
    version = Column(Integer)
    
    system_prompt = Column(Text)
    change_description = Column(String(500))  # 修改说明
    
    # 效果指标 (自动统计)
    usage_count = Column(Integer, default=0)
    avg_session_score = Column(Float)
    avg_user_satisfaction = Column(Float)
    behavior_consistency_rate = Column(Float)  # 角色一致性
    
    created_by = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 状态
    is_active = Column(Boolean, default=False)  # 当前生效版本
```

### 14.9 实时反馈的时机与方式

**问题**: 实时反馈什么时候给？怎么给才不打断用户思路？

```
┌─────────────────────────────────────────────────────────────────────────┐
│  实时反馈策略                                                            │
│                                                                         │
│  反馈类型        │ 时机                    │ 方式                        │
│  ───────────────┼────────────────────────┼───────────────────────────  │
│  模糊词提示      │ 用户说完一句话后        │ 小气泡提示，不打断           │
│  阶段引导        │ 阶段切换时              │ 顶部横幅，3秒后消失          │
│  评分变化        │ 每轮结束后              │ 侧边栏实时更新               │
│  严重问题        │ 立即                    │ 震动 + 醒目提示              │
│  鼓励反馈        │ 表现好时                │ 小动画 + 正向文案            │
│                                                                         │
│  反馈频率控制:                                                          │
│  - 同类型反馈间隔至少 10 秒                                              │
│  - 单轮最多 2 条反馈                                                    │
│  - 用户可设置反馈强度 (高/中/低/关闭)                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 14.10 移动端适配

**问题**: 当前设计主要考虑桌面端，移动端体验如何保证？

**补充考虑**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  移动端特殊考虑                                                          │
│                                                                         │
│  1. 录音交互                                                            │
│     - 按住说话 vs 点击开始/结束                                          │
│     - 手机麦克风权限处理                                                 │
│     - 后台切换时的录音中断处理                                           │
│                                                                         │
│  2. 界面布局                                                            │
│     - 实时反馈面板需要折叠/展开                                          │
│     - 评分显示简化                                                      │
│     - 对话气泡优先，其他信息次要                                         │
│                                                                         │
│  3. 网络处理                                                            │
│     - 弱网环境下的音频压缩                                               │
│     - 断网重连机制                                                      │
│     - 离线缓存对话记录                                                  │
│                                                                         │
│  4. 性能优化                                                            │
│     - 音频波形渲染优化                                                  │
│     - 减少不必要的重渲染                                                │
│     - 内存管理 (长对话)                                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 14.11 总结：优先级排序

| 遗漏点 | 重要性 | 紧急性 | 建议阶段 |
|--------|--------|--------|----------|
| 对话上下文管理 | 高 | 高 | Phase 1 |
| 异常处理与降级 | 高 | 高 | Phase 1 |
| 对话结束条件 | 中 | 高 | Phase 1 |
| Persona 行为一致性 | 高 | 中 | Phase 2 |
| 评分可解释性 | 中 | 中 | Phase 2 |
| 实时反馈策略 | 中 | 中 | Phase 2 |
| Prompt 版本管理 | 中 | 低 | Phase 3 |
| 数据分析洞察 | 中 | 低 | Phase 3 |
| 多租户权限 | 低 | 低 | Phase 4 |
| 移动端优化 | 中 | 低 | Phase 4 |


---

## 14.1 补充说明：会话级上下文（无跨会话记忆）

### 设计原则

```
┌─────────────────────────────────────────────────────────────────────────┐
│  上下文生命周期                                                          │
│                                                                         │
│  会话 A                        会话 B                                   │
│  ┌─────────────────────┐      ┌─────────────────────┐                  │
│  │ 开始 → 对话 → 结束  │      │ 开始 → 对话 → 结束  │                  │
│  │                     │      │                     │                  │
│  │ 上下文在内存中维护   │      │ 全新的上下文        │                  │
│  │ 会话结束后释放       │      │ 不继承会话A的任何   │                  │
│  └─────────────────────┘      └─────────────────────┘                  │
│           │                            │                               │
│           ▼                            ▼                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    持久化存储 (用于回放/分析)                     │   │
│  │  - 对话记录 (conversation_turns)                                 │   │
│  │  - 评分结果 (session_scores)                                     │   │
│  │  - 统计数据 (模糊词次数、阶段转换等)                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 简化后的上下文设计

```python
@dataclass
class SessionContext:
    """会话级上下文 - 仅在单次会话内有效"""
    
    # 会话标识
    session_id: str
    agent_id: str
    persona_id: str
    user_id: str
    created_at: datetime
    
    # 对话历史 (本次会话内)
    history: List[Message] = field(default_factory=list)
    
    # 会话状态 (本次会话内)
    state: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "current_stage": "discovery",      # 当前销售阶段
    #   "turn_count": 5,                   # 对话轮次
    #   "fuzzy_word_count": 2,             # 模糊词使用次数
    #   "scores": {"专业度": 75, ...},     # 实时评分
    #   "knowledge_cache": {...}           # 知识检索缓存
    # }
    
    # 角色在本次对话中提取的信息 (用于更智能的追问)
    extracted_info: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "user_mentioned_budget": "50万",   # 用户提到的预算
    #   "user_pain_points": ["效率低"],    # 用户提到的痛点
    #   "products_discussed": ["企业版"]   # 讨论过的产品
    # }


class SessionContextManager:
    """会话上下文管理器"""
    
    def __init__(self):
        # 内存中的活跃会话 (session_id -> SessionContext)
        self._active_sessions: Dict[str, SessionContext] = {}
    
    async def create_session(
        self, 
        agent_id: str, 
        persona_id: str, 
        user_id: str
    ) -> SessionContext:
        """创建新会话 - 全新的上下文"""
        session_id = str(uuid.uuid4())
        
        context = SessionContext(
            session_id=session_id,
            agent_id=agent_id,
            persona_id=persona_id,
            user_id=user_id,
            created_at=datetime.utcnow()
        )
        
        self._active_sessions[session_id] = context
        return context
    
    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        """获取会话上下文"""
        return self._active_sessions.get(session_id)
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """结束会话 - 持久化数据后释放内存"""
        context = self._active_sessions.get(session_id)
        if not context:
            return {}
        
        # 1. 持久化对话记录 (用于回放)
        await self._save_conversation_turns(context)
        
        # 2. 持久化评分结果
        await self._save_session_scores(context)
        
        # 3. 生成会话报告
        report = await self._generate_session_report(context)
        
        # 4. 释放内存
        del self._active_sessions[session_id]
        
        return report
    
    async def cleanup_stale_sessions(self, max_idle_minutes: int = 30):
        """清理超时的会话"""
        now = datetime.utcnow()
        stale_sessions = []
        
        for session_id, context in self._active_sessions.items():
            idle_time = (now - context.state.get("last_activity", context.created_at))
            if idle_time.total_seconds() > max_idle_minutes * 60:
                stale_sessions.append(session_id)
        
        for session_id in stale_sessions:
            await self.end_session(session_id)
```

### 对话历史管理

```python
class ConversationHistoryManager:
    """对话历史管理 - 处理 token 限制"""
    
    MAX_HISTORY_TURNS = 20  # 最多保留的轮次
    MAX_TOKENS = 4000       # 历史部分的最大 token
    
    def get_history_for_llm(self, context: SessionContext) -> List[Message]:
        """获取用于 LLM 的对话历史"""
        history = context.history
        
        # 如果历史太长，只保留最近的 N 轮
        if len(history) > self.MAX_HISTORY_TURNS * 2:
            # 保留第一轮 (开场) + 最近的轮次
            history = history[:2] + history[-(self.MAX_HISTORY_TURNS * 2 - 2):]
        
        return history
    
    def add_turn(self, context: SessionContext, user_msg: str, ai_msg: str):
        """添加一轮对话"""
        context.history.append(Message(role="user", content=user_msg))
        context.history.append(Message(role="assistant", content=ai_msg))
        context.state["turn_count"] = context.state.get("turn_count", 0) + 1
        context.state["last_activity"] = datetime.utcnow()
```

### 与持久化的关系

```
┌─────────────────────────────────────────────────────────────────────────┐
│  数据存储策略                                                            │
│                                                                         │
│  内存 (SessionContext)          │  数据库 (持久化)                       │
│  ─────────────────────────────┼────────────────────────────────────── │
│  对话历史 (实时)               │  conversation_turns (会话结束后保存)   │
│  实时评分                      │  session_scores (会话结束后保存)       │
│  销售阶段                      │  practice_sessions (会话元数据)        │
│  模糊词统计                    │  (汇总到 session 记录)                 │
│  知识检索缓存                  │  不保存                               │
│  提取的用户信息                │  不保存 (隐私考虑)                     │
│                                                                         │
│  生命周期:                                                              │
│  - 会话开始: 创建 SessionContext                                        │
│  - 会话进行: 更新内存中的状态                                            │
│  - 会话结束: 持久化必要数据，释放内存                                    │
│  - 新会话: 完全独立，不继承任何上下文                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 这样设计的好处

1. **简单** - 不需要复杂的长期记忆管理
2. **隐私友好** - 用户信息不跨会话保留
3. **资源高效** - 会话结束即释放内存
4. **每次练习独立** - 符合"练习"场景的特点，每次都是新的开始
5. **仍支持回放** - 对话记录持久化，可以回看历史会话


---

## 15. 原子能力模块完整清单

基于前面的设计分析，整理出完整的原子能力模块清单：

### 15.1 能力模块总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         能力模块分类                                     │
│                                                                         │
│  基础能力 (已有)              │  新增能力                               │
│  ─────────────────────────── │ ─────────────────────────────────────── │
│  ✅ asr (语音识别)            │  🔨 info_extractor (信息提取)           │
│  ✅ tts (语音合成)            │  🔨 behavior_guard (行为守卫)           │
│  ✅ llm (大模型对话)          │  🔨 session_timer (会话计时)            │
│  ✅ persona (角色扮演)        │  🔨 turn_analyzer (轮次分析)            │
│                              │  🔨 report_generator (报告生成)         │
│  待实现能力                   │  🔨 feedback_controller (反馈控制)      │
│  ─────────────────────────── │  🔨 history_manager (历史管理)          │
│  🔨 knowledge (知识库检索)    │  🔨 graceful_degradation (优雅降级)     │
│  🔨 fuzzy_detection (模糊词)  │                                        │
│  🔨 sales_stage (销售阶段)    │                                        │
│  🔨 scoring (多维评分)        │                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```


### 15.2 新增能力模块详细设计

#### 1. 信息提取能力 (InfoExtractorCapability)

**用途**: 从用户发言中提取关键信息，供 AI 角色后续追问使用

```python
class InfoExtractorCapability(BaseCapability):
    """信息提取能力 - 从对话中提取关键业务信息"""
    
    capability_id = "info_extractor"
    name = "信息提取"
    
    config_schema = {
        "extract_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},  # 字段名
                    "description": {"type": "string"},  # 描述
                    "examples": {"type": "array"}  # 示例值
                }
            },
            "default": [
                {"field": "budget", "description": "预算金额", "examples": ["50万", "100万以内"]},
                {"field": "pain_points", "description": "痛点问题", "examples": ["效率低", "成本高"]},
                {"field": "timeline", "description": "决策时间", "examples": ["Q2", "下个月"]},
                {"field": "competitors", "description": "提到的竞品", "examples": ["竞品A", "XX公司"]}
            ]
        }
    }
    
    async def execute(self, context: SessionContext, user_text: str) -> CapabilityResult:
        """提取信息并更新上下文"""
        # 使用 LLM 提取结构化信息
        extracted = await self._extract_with_llm(user_text, self.config.params["extract_fields"])
        
        # 更新到会话上下文
        for field, value in extracted.items():
            if value:
                context.extracted_info[field] = value
        
        return CapabilityResult(success=True, data=extracted)
```

**应用场景**: AI 角色可以基于提取的信息进行更智能的追问，如"你刚才提到预算是50万，那..."


#### 2. 行为守卫能力 (BehaviorGuardCapability)

**用途**: 确保 AI 角色的回复符合角色设定，防止"人设崩塌"

```python
class BehaviorGuardCapability(BaseCapability):
    """行为守卫能力 - 验证并修复不符合角色的回复"""
    
    capability_id = "behavior_guard"
    name = "行为守卫"
    
    config_schema = {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "persona_trait": {"type": "string"},  # 角色特征
                    "check_pattern": {"type": "string"},  # 检查模式
                    "fix_prompt": {"type": "string"}  # 修复提示
                }
            }
        },
        "max_retries": {"type": "number", "default": 2}
    }
    
    async def execute(self, context: SessionContext, ai_response: str) -> CapabilityResult:
        """验证 AI 回复是否符合角色"""
        persona = await self._get_persona(context.persona_id)
        violations = []
        
        # 检查各项规则
        for rule in self._build_rules(persona):
            if not rule.check(ai_response):
                violations.append(rule)
        
        if violations:
            # 需要重新生成
            return CapabilityResult(
                success=False,
                data={"violations": violations},
                feedback=violations[0].fix_prompt
            )
        
        return CapabilityResult(success=True, data={"valid": True})
```

**应用场景**: 怀疑型客户的回复必须包含质疑，价格敏感型必须提及价格


#### 3. 会话计时能力 (SessionTimerCapability)

**用途**: 管理会话时长，提供时间相关的控制和提醒

```python
class SessionTimerCapability(BaseCapability):
    """会话计时能力 - 时长控制和提醒"""
    
    capability_id = "session_timer"
    name = "会话计时"
    
    config_schema = {
        "max_duration_minutes": {"type": "number", "default": 15},
        "warning_at_minutes": {"type": "number", "default": 12},
        "max_turns": {"type": "number", "default": 15},
        "suggested_turns": {"type": "number", "default": 8}
    }
    
    async def execute(self, context: SessionContext) -> CapabilityResult:
        """检查会话状态"""
        duration = (datetime.utcnow() - context.created_at).total_seconds() / 60
        turn_count = context.state.get("turn_count", 0)
        
        status = "normal"
        message = None
        
        # 硬性限制
        if duration >= self.config.params["max_duration_minutes"]:
            status = "must_end"
            message = "已达到最大时长"
        elif turn_count >= self.config.params["max_turns"]:
            status = "must_end"
            message = "已达到最大轮次"
        # 警告
        elif duration >= self.config.params["warning_at_minutes"]:
            status = "warning"
            message = f"练习已进行 {int(duration)} 分钟"
        # 建议结束
        elif turn_count >= self.config.params["suggested_turns"]:
            status = "suggest_end"
            message = "已完成建议轮次，可以结束或继续"
        
        return CapabilityResult(success=True, data={"status": status, "message": message})
```


#### 4. 轮次分析能力 (TurnAnalyzerCapability)

**用途**: 分析每轮对话，生成详细的评价和建议

```python
class TurnAnalyzerCapability(BaseCapability):
    """轮次分析能力 - 分析单轮对话质量"""
    
    capability_id = "turn_analyzer"
    name = "轮次分析"
    
    config_schema = {
        "analyze_dimensions": {
            "type": "array",
            "default": ["clarity", "relevance", "persuasiveness", "professionalism"]
        },
        "generate_suggestions": {"type": "boolean", "default": True}
    }
    
    async def execute(self, context: SessionContext, user_text: str) -> CapabilityResult:
        """分析本轮用户发言"""
        analysis = {
            "turn_number": context.state.get("turn_count", 0),
            "text_length": len(user_text),
            "dimensions": {},
            "highlights": [],  # 亮点
            "issues": [],      # 问题
            "suggestions": []  # 建议
        }
        
        # 分析各维度
        for dim in self.config.params["analyze_dimensions"]:
            score, feedback = await self._analyze_dimension(dim, user_text, context)
            analysis["dimensions"][dim] = {"score": score, "feedback": feedback}
        
        # 生成建议
        if self.config.params["generate_suggestions"]:
            analysis["suggestions"] = await self._generate_suggestions(analysis, context)
        
        return CapabilityResult(success=True, data=analysis)
```

**应用场景**: 用于会话结束后的详细报告，以及对话回放时的逐句点评


#### 5. 报告生成能力 (ReportGeneratorCapability)

**用途**: 会话结束时生成完整的练习报告

```python
class ReportGeneratorCapability(BaseCapability):
    """报告生成能力 - 生成会话总结报告"""
    
    capability_id = "report_generator"
    name = "报告生成"
    
    config_schema = {
        "include_sections": {
            "type": "array",
            "default": ["summary", "scores", "highlights", "improvements", "next_steps"]
        },
        "generate_ai_comment": {"type": "boolean", "default": True}
    }
    
    async def execute(self, context: SessionContext) -> CapabilityResult:
        """生成会话报告"""
        report = {
            "session_id": context.session_id,
            "duration_seconds": (datetime.utcnow() - context.created_at).total_seconds(),
            "turn_count": context.state.get("turn_count", 0),
            "persona_name": await self._get_persona_name(context.persona_id),
            
            # 评分汇总
            "scores": context.state.get("scores", {}),
            "overall_score": self._calculate_overall(context.state.get("scores", {})),
            
            # 亮点和问题
            "highlights": await self._extract_highlights(context),
            "issues": await self._extract_issues(context),
            
            # 改进建议
            "improvements": await self._generate_improvements(context),
            
            # AI 总评
            "ai_comment": await self._generate_ai_comment(context) if self.config.params["generate_ai_comment"] else None
        }
        
        return CapabilityResult(success=True, data=report)
```


#### 6. 反馈控制能力 (FeedbackControllerCapability)

**用途**: 控制实时反馈的时机、频率和方式

```python
class FeedbackControllerCapability(BaseCapability):
    """反馈控制能力 - 管理实时反馈的展示"""
    
    capability_id = "feedback_controller"
    name = "反馈控制"
    
    config_schema = {
        "cooldown_seconds": {"type": "number", "default": 10},
        "max_feedbacks_per_turn": {"type": "number", "default": 2},
        "priority_order": {
            "type": "array",
            "default": ["critical", "warning", "info", "encouragement"]
        },
        "user_preference": {
            "type": "string",
            "enum": ["high", "medium", "low", "off"],
            "default": "medium"
        }
    }
    
    async def execute(self, context: SessionContext, feedbacks: List[Dict]) -> CapabilityResult:
        """过滤和排序反馈"""
        if self.config.params["user_preference"] == "off":
            return CapabilityResult(success=True, data=[])
        
        # 按优先级排序
        sorted_feedbacks = self._sort_by_priority(feedbacks)
        
        # 应用冷却时间过滤
        filtered = self._apply_cooldown(sorted_feedbacks, context)
        
        # 限制数量
        max_count = self._get_max_count_by_preference()
        final = filtered[:max_count]
        
        # 记录已发送的反馈
        self._record_sent_feedbacks(final, context)
        
        return CapabilityResult(success=True, data=final)
```

**应用场景**: 避免反馈过于频繁打断用户，根据用户偏好调整反馈强度


#### 7. 历史管理能力 (HistoryManagerCapability)

**用途**: 管理对话历史，处理 token 限制，支持回放

```python
class HistoryManagerCapability(BaseCapability):
    """历史管理能力 - 对话历史的存储和检索"""
    
    capability_id = "history_manager"
    name = "历史管理"
    
    config_schema = {
        "max_history_turns": {"type": "number", "default": 20},
        "max_tokens_for_llm": {"type": "number", "default": 4000},
        "persist_audio": {"type": "boolean", "default": True},
        "audio_retention_days": {"type": "number", "default": 30}
    }
    
    async def execute(self, context: SessionContext, action: str, data: Any = None) -> CapabilityResult:
        """历史管理操作"""
        if action == "add_turn":
            return await self._add_turn(context, data)
        elif action == "get_for_llm":
            return await self._get_history_for_llm(context)
        elif action == "persist":
            return await self._persist_to_db(context)
        elif action == "get_replay_data":
            return await self._get_replay_data(context.session_id)
        
        return CapabilityResult(success=False, data={"error": "Unknown action"})
    
    async def _get_history_for_llm(self, context: SessionContext) -> CapabilityResult:
        """获取用于 LLM 的历史（处理 token 限制）"""
        history = context.history
        max_turns = self.config.params["max_history_turns"]
        
        if len(history) > max_turns * 2:
            # 保留开头 + 最近的轮次
            history = history[:2] + history[-(max_turns * 2 - 2):]
        
        return CapabilityResult(success=True, data=history)
```


#### 8. 优雅降级能力 (GracefulDegradationCapability)

**用途**: 处理各种服务失败，提供降级方案

```python
class GracefulDegradationCapability(BaseCapability):
    """优雅降级能力 - 服务失败时的降级处理"""
    
    capability_id = "graceful_degradation"
    name = "优雅降级"
    
    config_schema = {
        "fallback_responses": {
            "type": "object",
            "default": {
                "skeptical": ["嗯，你说的这个我需要再想想...", "能再详细说说吗？"],
                "price_focused": ["价格方面还能再谈谈吗？", "有没有更优惠的方案？"],
                "default": ["嗯，继续说", "然后呢？"]
            }
        },
        "retry_config": {
            "type": "object",
            "default": {
                "llm": {"max_retries": 2, "delay_ms": 1000},
                "asr": {"max_retries": 1, "delay_ms": 500},
                "tts": {"max_retries": 1, "delay_ms": 500}
            }
        }
    }
    
    async def execute(self, context: SessionContext, service: str, error: Exception) -> CapabilityResult:
        """处理服务失败"""
        retry_config = self.config.params["retry_config"].get(service, {})
        
        if service == "llm":
            # LLM 失败：使用降级回复
            persona_type = await self._get_persona_type(context.persona_id)
            responses = self.config.params["fallback_responses"].get(
                persona_type, 
                self.config.params["fallback_responses"]["default"]
            )
            return CapabilityResult(
                success=True, 
                data={"fallback_response": random.choice(responses)}
            )
        
        elif service == "asr":
            # ASR 失败：提示用户重说或切换文字输入
            return CapabilityResult(
                success=True,
                data={"action": "prompt_retry", "message": "没听清，请再说一遍"}
            )
        
        elif service == "tts":
            # TTS 失败：只显示文字
            return CapabilityResult(
                success=True,
                data={"action": "text_only"}
            )
        
        return CapabilityResult(success=False)
```


### 15.3 能力模块完整清单汇总

| 模块ID | 名称 | 类型 | 状态 | 说明 |
|--------|------|------|------|------|
| `asr` | 语音识别 | 基础 | ✅ 已有 | 阿里云 Manual 模式 |
| `tts` | 语音合成 | 基础 | ✅ 已有 | Edge-TTS |
| `llm` | 大模型对话 | 基础 | ✅ 已有 | DeepSeek/Qwen |
| `persona` | 角色扮演 | 基础 | ✅ 已有 | AI 角色提示词 |
| `knowledge` | 知识库检索 | 业务 | 🔨 待实现 | RAG 产品知识 |
| `fuzzy_detection` | 模糊词检测 | 业务 | 🔨 待实现 | 实时检测模糊表达 |
| `sales_stage` | 销售阶段 | 业务 | 🔨 待实现 | 流程引导 |
| `scoring` | 多维评分 | 业务 | 🔧 需升级 | 5维度+可解释 |
| `info_extractor` | 信息提取 | 辅助 | 🔨 待实现 | 提取用户关键信息 |
| `behavior_guard` | 行为守卫 | 辅助 | 🔨 待实现 | 防止人设崩塌 |
| `session_timer` | 会话计时 | 辅助 | 🔨 待实现 | 时长控制 |
| `turn_analyzer` | 轮次分析 | 辅助 | 🔨 待实现 | 单轮详细分析 |
| `report_generator` | 报告生成 | 辅助 | 🔨 待实现 | 会话总结报告 |
| `feedback_controller` | 反馈控制 | 辅助 | 🔨 待实现 | 控制反馈频率 |
| `history_manager` | 历史管理 | 辅助 | 🔨 待实现 | 对话历史+回放 |
| `graceful_degradation` | 优雅降级 | 辅助 | 🔨 待实现 | 服务失败处理 |

### 15.4 能力模块依赖关系

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         能力模块依赖图                                   │
│                                                                         │
│                        ┌─────────────┐                                  │
│                        │     llm     │                                  │
│                        └──────┬──────┘                                  │
│                               │                                         │
│         ┌─────────────────────┼─────────────────────┐                   │
│         │                     │                     │                   │
│         ▼                     ▼                     ▼                   │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐           │
│  │  knowledge  │       │   persona   │       │behavior_guard│           │
│  └─────────────┘       └─────────────┘       └─────────────┘           │
│         │                     │                                         │
│         └──────────┬──────────┘                                         │
│                    ▼                                                    │
│             ┌─────────────┐                                             │
│             │info_extractor│                                            │
│             └─────────────┘                                             │
│                                                                         │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐           │
│  │     asr     │──────▶│fuzzy_detect │──────▶│   scoring   │           │
│  └─────────────┘       └─────────────┘       └─────────────┘           │
│                               │                     │                   │
│                               ▼                     ▼                   │
│                        ┌─────────────┐       ┌─────────────┐           │
│                        │ sales_stage │       │turn_analyzer│           │
│                        └─────────────┘       └─────────────┘           │
│                                                    │                    │
│                                                    ▼                    │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐           │
│  │     tts     │       │session_timer│       │report_gener │           │
│  └─────────────┘       └─────────────┘       └─────────────┘           │
│                                                                         │
│  横向支撑:                                                              │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐           │
│  │history_mgr  │       │feedback_ctrl│       │graceful_deg │           │
│  └─────────────┘       └─────────────┘       └─────────────┘           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 15.5 能力模块实现优先级

**Phase 1 (基础修复 + 核心能力)**
1. `history_manager` - 对话历史管理是基础
2. `graceful_degradation` - 异常处理保证稳定性
3. `session_timer` - 会话控制

**Phase 2 (实时反馈)**
4. `fuzzy_detection` - 模糊词检测
5. `feedback_controller` - 反馈频率控制
6. `sales_stage` - 销售阶段识别

**Phase 3 (智能增强)**
7. `knowledge` - 知识库检索
8. `info_extractor` - 信息提取
9. `behavior_guard` - 行为守卫
10. `scoring` - 多维评分升级

**Phase 4 (报告回放)**
11. `turn_analyzer` - 轮次分析
12. `report_generator` - 报告生成
