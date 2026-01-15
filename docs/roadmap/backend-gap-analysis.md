# 后端能力差距分析

> 基于前端页面需求 (`frontend-pages-spec.md`) 和技术方案 (`sales-coach-upgrade-plan.md`)，分析后端目前缺失的能力

## 1. 差距总览

### 1.1 现有能力 vs 需要能力

| 模块 | 现有状态 | 需要状态 | 差距 |
|------|----------|----------|------|
| **用户认证** | ✅ 基础认证 | ✅ 基础认证 | 无 |
| **Agent 管理** | ❌ 无 | 需要完整 CRUD | 🔴 全新开发 |
| **Persona 管理** | ⚠️ 硬编码 | 需要动态配置 | 🟡 重构 |
| **知识库管理** | ⚠️ 仅 PPT | 需要通用知识库 | 🟡 扩展 |
| **会话管理** | ✅ 基础 | 需要增强 | 🟡 扩展 |
| **实时反馈** | ❌ 无 | 模糊词/阶段/评分 | 🔴 全新开发 |
| **对话回放** | ❌ 无 | 完整回放功能 | 🔴 全新开发 |
| **排行榜** | ✅ 基础 | ✅ 基础 | 无 |
| **数据分析** | ✅ 基础 | 需要增强 | 🟡 扩展 |

### 1.2 优先级分类

```
🔴 P0 - 核心缺失 (必须开发)
🟡 P1 - 需要扩展 (现有基础上增强)
🟢 P2 - 可选优化 (锦上添花)
```

---

## 2. 详细差距分析

### 2.1 🔴 Agent 管理 API (全新)

**前端需求**: `/admin/agents`, `/admin/agents/:id`

**现有状态**: 无 Agent 管理 API，当前 `scenarios` 是硬编码的

**需要开发的 API**:

```python
# Agent CRUD
POST   /api/v1/admin/agents              # 创建 Agent
GET    /api/v1/admin/agents              # 列表 (分页、筛选)
GET    /api/v1/admin/agents/:id          # 详情
PUT    /api/v1/admin/agents/:id          # 更新
DELETE /api/v1/admin/agents/:id          # 删除

# Agent 状态管理
POST   /api/v1/admin/agents/:id/publish  # 发布
POST   /api/v1/admin/agents/:id/archive  # 归档

# 用户端
GET    /api/v1/agents                    # 获取已发布的 Agent 列表
GET    /api/v1/agents/:id                # 获取 Agent 详情
GET    /api/v1/agents/:id/personas       # 获取 Agent 下的角色列表
```

**需要的数据模型**:

```python
class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    icon = Column(String(200))
    category = Column(String(50))  # sales | presentation | interview
    
    system_prompt = Column(Text)
    welcome_message = Column(String(500))
    capabilities_config = Column(JSON)  # 能力模块配置
    default_knowledge_base_ids = Column(JSON)  # 默认知识库
    
    status = Column(String(20), default="draft")  # draft | published | archived
    version = Column(Integer, default=1)
    
    created_by = Column(String(36))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    published_at = Column(DateTime)
```

---

### 2.2 🔴 Persona 管理 API (重构)

**前端需求**: `/admin/personas`, `/admin/personas/:id`

**现有状态**: `scenarios.py` 中硬编码了 4 个 persona

**需要开发的 API**:

```python
# Persona CRUD
POST   /api/v1/admin/personas              # 创建角色
GET    /api/v1/admin/personas              # 列表 (分页、筛选)
GET    /api/v1/admin/personas/:id          # 详情
PUT    /api/v1/admin/personas/:id          # 更新
DELETE /api/v1/admin/personas/:id          # 删除

# Persona 状态
POST   /api/v1/admin/personas/:id/publish  # 发布
POST   /api/v1/admin/personas/:id/duplicate # 复制
```

**需要的数据模型**:

```python
class Persona(Base):
    __tablename__ = "personas"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    icon = Column(String(50))
    category = Column(String(50))  # customer | interviewer | coach
    difficulty = Column(String(20))  # easy | medium | hard
    
    system_prompt = Column(Text, nullable=False)  # 核心: 角色提示词
    traits = Column(JSON)  # 角色特征
    knowledge_base_ids = Column(JSON)  # 专属知识库
    behavior_config = Column(JSON)  # 行为配置
    
    # 评分权重覆盖
    scoring_weights = Column(JSON)  # {"专业度": 0.3, "异议处理": 0.4, ...}
    
    is_public = Column(Boolean, default=True)
    status = Column(String(20), default="active")
    created_by = Column(String(36))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class AgentPersona(Base):
    """Agent 与 Persona 关联表"""
    __tablename__ = "agent_personas"
    
    id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey("agents.id"))
    persona_id = Column(String(36), ForeignKey("personas.id"))
    display_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    override_config = Column(JSON)  # 覆盖配置
```

---

### 2.3 🔴 知识库管理 API (扩展)

**前端需求**: `/admin/knowledge`, `/admin/knowledge/:id`

**现有状态**: 
- 有 `ingestion_service` 用于 PPT 文档
- 有 ChromaDB 向量存储
- 缺少通用知识库管理 API

**需要开发的 API**:

```python
# 知识库 CRUD
POST   /api/v1/admin/knowledge              # 创建知识库
GET    /api/v1/admin/knowledge              # 列表
GET    /api/v1/admin/knowledge/:id          # 详情
PUT    /api/v1/admin/knowledge/:id          # 更新
DELETE /api/v1/admin/knowledge/:id          # 删除

# 文档管理
POST   /api/v1/admin/knowledge/:id/documents      # 上传文档
GET    /api/v1/admin/knowledge/:id/documents      # 文档列表
DELETE /api/v1/admin/knowledge/:id/documents/:docId  # 删除文档
GET    /api/v1/admin/knowledge/:id/documents/:docId/preview  # 预览
```

**需要的数据模型**:

```python
class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    category = Column(String(50))  # product | competitor | faq | policy
    
    vector_collection = Column(String(100), unique=True)
    embedding_model = Column(String(100))
    
    document_count = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    
    status = Column(String(20), default="active")
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    
    id = Column(String(36), primary_key=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id"))
    
    title = Column(String(200))
    file_type = Column(String(20))  # pdf | docx | txt | md
    file_url = Column(String(500))
    file_size = Column(Integer)
    
    status = Column(String(20))  # pending | processing | ready | failed
    chunk_count = Column(Integer, default=0)
    
    created_at = Column(DateTime)
```

---

### 2.4 🔴 实时反馈能力模块 (全新)

**前端需求**: 练习会话页的实时提示面板

**现有状态**: 无

**需要开发的能力模块**:

#### 2.4.1 模糊词检测 (FuzzyDetectionCapability)

```python
class FuzzyDetectionCapability(BaseCapability):
    """实时检测模糊表达"""
    
    capability_id = "fuzzy_detection"
    
    config_schema = {
        "fuzzy_patterns": [
            {"pattern": "大概|可能|也许", "category": "uncertain", 
             "suggestion": "请给出具体数据", "severity": "high"}
        ],
        "detection_mode": "realtime",
        "cooldown_seconds": 10
    }
    
    async def execute(self, context, text) -> CapabilityResult:
        """检测文本中的模糊词"""
        detections = []
        for pattern in self.config["fuzzy_patterns"]:
            matches = re.findall(pattern["pattern"], text)
            if matches:
                detections.append({
                    "category": pattern["category"],
                    "matched": matches,
                    "suggestion": pattern["suggestion"],
                    "severity": pattern["severity"]
                })
        return CapabilityResult(success=True, data={"detections": detections})
```

#### 2.4.2 销售阶段识别 (SalesStageCapability)

```python
class SalesStageCapability(BaseCapability):
    """识别当前销售阶段"""
    
    capability_id = "sales_stage"
    
    STAGES = [
        {"id": "opening", "name": "开场破冰", "key_actions": ["建立信任", "了解背景"]},
        {"id": "discovery", "name": "需求挖掘", "key_actions": ["深入痛点", "确认需求"]},
        {"id": "presentation", "name": "方案呈现", "key_actions": ["匹配需求", "展示价值"]},
        {"id": "objection", "name": "异议处理", "key_actions": ["处理疑虑", "提供证据"]},
        {"id": "closing", "name": "促成成交", "key_actions": ["推动决策", "行动号召"]}
    ]
    
    async def execute(self, context, conversation_history) -> CapabilityResult:
        """基于对话历史判断当前阶段"""
        # 使用 LLM 或规则引擎判断
        ...
```

#### 2.4.3 实时评分 (RealtimeScoringCapability)

```python
class RealtimeScoringCapability(BaseCapability):
    """多维度实时评分"""
    
    capability_id = "realtime_scoring"
    
    config_schema = {
        "dimensions": [
            {"name": "专业度", "weight": 0.25},
            {"name": "沟通技巧", "weight": 0.25},
            {"name": "销售流程", "weight": 0.20},
            {"name": "异议处理", "weight": 0.15},
            {"name": "成交能力", "weight": 0.15}
        ]
    }
    
    async def execute(self, context, turn_data) -> CapabilityResult:
        """计算本轮评分"""
        scores = {}
        for dim in self.config["dimensions"]:
            score = await self._evaluate_dimension(dim["name"], turn_data)
            scores[dim["name"]] = {
                "score": score,
                "trend": self._calculate_trend(context, dim["name"], score)
            }
        return CapabilityResult(success=True, data=scores)
```

---

### 2.5 🔴 对话回放 API (全新)

**前端需求**: `/history/:sessionId` 回放页面

**现有状态**: 无对话轮次存储

**需要开发的 API**:

```python
# 对话消息
GET    /api/v1/sessions/:id/messages           # 获取对话消息列表
GET    /api/v1/sessions/:id/messages/:msgId    # 获取单条消息详情
GET    /api/v1/sessions/:id/audio/:msgId       # 获取单条语音

# 回放数据
GET    /api/v1/sessions/:id/replay             # 获取回放数据 (含时间轴标记)
GET    /api/v1/sessions/:id/highlights         # 获取关键时刻
```

**需要的数据模型**:

```python
class ConversationMessage(Base):
    """对话消息"""
    __tablename__ = "conversation_messages"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("practice_sessions.session_id"))
    turn_number = Column(Integer)
    role = Column(String(20))  # user | assistant
    content = Column(Text)
    audio_url = Column(String(500))
    timestamp = Column(DateTime)
    duration_ms = Column(Integer)  # 音频时长
    
    # 分析数据
    fuzzy_words = Column(JSON)  # 检测到的模糊词
    sales_stage = Column(String(50))  # 当前销售阶段
    score_snapshot = Column(JSON)  # 该轮次的评分快照
    ai_feedback = Column(Text)  # AI 点评
    
    # 标记
    is_highlight = Column(Boolean, default=False)  # 是否关键时刻
    highlight_type = Column(String(20))  # good | bad | neutral
    highlight_reason = Column(String(200))
```

---

### 2.6 🟡 会话管理 API (扩展)

**前端需求**: 会话创建、报告生成

**现有状态**: 基础会话 CRUD 已有

**需要扩展**:

```python
# 现有 API 需要增强
POST   /api/v1/sessions                    # 创建会话 (需支持 agent_id + persona_id)
GET    /api/v1/sessions/:id/report         # 获取报告 (需要增强报告内容)

# 新增 API
GET    /api/v1/sessions/stats              # 获取用户统计 (总次数、本周、平均分)
```

**报告增强**:

```python
class SessionReport(BaseModel):
    session_id: UUID
    
    # 基础信息
    agent_name: str
    persona_name: str
    duration_seconds: int
    turn_count: int
    
    # 综合评分
    overall_score: float
    score_level: str  # excellent | good | fair | poor
    
    # 多维度评分
    dimension_scores: List[DimensionScore]
    
    # 详细分析
    strengths: List[str]  # 做得好
    improvements: List[str]  # 需改进
    suggestions: List[str]  # 建议
    
    # 关键时刻
    highlights: List[Highlight]
    
    # 模糊词统计
    fuzzy_word_count: int
    fuzzy_word_details: List[FuzzyWordDetail]
```

---

### 2.7 🟡 WebSocket 消息扩展

**现有状态**: 基础音频/文本消息

**需要扩展的消息类型**:

```python
# 服务端 → 客户端 (新增)

# 模糊词检测
{
    "type": "fuzzy_detection",
    "data": {
        "detections": [
            {"category": "uncertain", "matched": ["大概"], 
             "suggestion": "请给出具体数据", "severity": "high"}
        ]
    }
}

# 销售阶段更新
{
    "type": "stage_update",
    "data": {
        "current_stage": "presentation",
        "stage_name": "方案呈现",
        "key_actions": ["匹配需求", "展示价值"],
        "guidance": "客户已表达需求，现在是展示产品价值的好时机"
    }
}

# 实时评分更新
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
```

---

### 2.8 🟡 数据分析 API (扩展)

**现有状态**: 基础统计已有

**需要扩展**:

```python
# 管理后台统计
GET    /api/v1/admin/analytics/overview    # 系统概览 (总用户、今日活跃、总练习)
GET    /api/v1/admin/analytics/trends      # 趋势数据
GET    /api/v1/admin/analytics/agents      # 各 Agent 使用统计
GET    /api/v1/admin/analytics/export      # 导出报表
```

---

## 3. 开发优先级排序

### 3.1 Phase 1: 核心管理 (2周)

| 任务 | 优先级 | 预估 | 依赖 |
|------|--------|------|------|
| Agent 数据模型 | P0 | 1天 | 无 |
| Agent CRUD API | P0 | 2天 | 数据模型 |
| Persona 数据模型 | P0 | 1天 | 无 |
| Persona CRUD API | P0 | 2天 | 数据模型 |
| Agent-Persona 关联 | P0 | 1天 | 两者模型 |
| 知识库数据模型 | P1 | 1天 | 无 |
| 知识库 CRUD API | P1 | 2天 | 数据模型 |

### 3.2 Phase 2: 实时反馈 (2周)

| 任务 | 优先级 | 预估 | 依赖 |
|------|--------|------|------|
| 模糊词检测能力 | P0 | 2天 | 无 |
| 销售阶段识别能力 | P1 | 3天 | 无 |
| 实时评分能力 | P1 | 2天 | 无 |
| WebSocket 消息扩展 | P0 | 2天 | 能力模块 |
| 能力模块集成到运行时 | P0 | 1天 | 能力模块 |

### 3.3 Phase 3: 对话回放 (1.5周)

| 任务 | 优先级 | 预估 | 依赖 |
|------|--------|------|------|
| 对话消息数据模型 | P1 | 1天 | 无 |
| 消息存储服务 | P1 | 2天 | 数据模型 |
| 回放 API | P1 | 2天 | 存储服务 |
| 音频存储优化 | P2 | 2天 | 无 |

### 3.4 Phase 4: 增强功能 (1周)

| 任务 | 优先级 | 预估 | 依赖 |
|------|--------|------|------|
| 会话报告增强 | P1 | 2天 | 实时反馈 |
| 用户统计 API | P2 | 1天 | 无 |
| 管理后台统计 | P2 | 2天 | 无 |

---

## 4. 技术实现建议

### 4.1 数据库迁移

```bash
# 需要新增的表
- agents
- personas
- agent_personas
- knowledge_bases
- knowledge_documents
- conversation_messages

# 需要修改的表
- practice_sessions (添加 agent_id, persona_id)
```

### 4.2 目录结构建议

```
backend/src/
├── agent/                    # Agent 平台核心 (新增)
│   ├── models.py             # Agent, Persona 数据模型
│   ├── schemas.py            # API Schema
│   ├── api/
│   │   ├── agents.py         # Agent CRUD
│   │   ├── personas.py       # Persona CRUD
│   │   └── knowledge.py      # 知识库管理
│   ├── services/
│   │   ├── agent_service.py
│   │   ├── persona_service.py
│   │   └── knowledge_service.py
│   ├── capabilities/         # 能力模块
│   │   ├── base.py
│   │   ├── fuzzy_detection.py
│   │   ├── sales_stage.py
│   │   └── realtime_scoring.py
│   └── runtime.py            # Agent 运行时
├── common/
│   ├── conversation/         # 对话管理 (新增)
│   │   ├── models.py         # ConversationMessage
│   │   ├── storage.py        # 消息存储
│   │   └── replay.py         # 回放服务
```

### 4.3 API 路由注册

```python
# main.py 需要新增
from agent.api import agents, personas, knowledge

app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(personas.router, prefix="/api/v1", tags=["personas"])
app.include_router(knowledge.router, prefix="/api/v1/admin", tags=["knowledge"])
```

---

## 5. 总结

### 5.1 工作量估算

| 类别 | 工作量 | 说明 |
|------|--------|------|
| 🔴 全新开发 | ~4周 | Agent/Persona/知识库管理、实时反馈、对话回放 |
| 🟡 扩展增强 | ~1.5周 | 会话管理、WebSocket、数据分析 |
| 🟢 优化调整 | ~0.5周 | 现有代码重构、测试 |
| **总计** | **~6周** | 1人全职开发 |

### 5.2 关键依赖

1. **数据模型先行**: Agent/Persona/KnowledgeBase 模型是其他功能的基础
2. **能力模块框架**: 需要先设计好 BaseCapability 接口
3. **WebSocket 扩展**: 实时反馈依赖消息协议扩展
4. **存储策略**: 音频存储需要考虑成本和保留期限

### 5.3 风险点

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据迁移复杂 | 现有数据兼容 | 增量迁移，保留旧表 |
| 实时评分准确性 | 用户体验 | 先用规则引擎，后续优化 |
| 音频存储成本 | 运营成本 | 压缩存储，设置保留期限 |
| 能力模块性能 | 实时性 | 并行执行，设置超时 |
