# Implementation Tasks

## Overview

本实现计划将后端平台升级分解为 5 个大阶段，每个阶段一次性执行完成。

## Tasks

- [x] 1. 基础设施层 (数据库 + 核心模块 + Schemas)
  - [x] 1.1 创建数据库模型
    - 创建 `backend/src/agent/models.py` - Agent, Persona, AgentPersona 模型
    - 创建 `backend/src/common/knowledge/models.py` - KnowledgeBase, KnowledgeDocument 模型
    - 创建 `backend/src/common/conversation/models.py` - ConversationMessage 模型
    - 扩展 `backend/src/common/db/models.py` - PracticeSession 添加 agent_id, persona_id
    - _Requirements: R13_
    - _Design: Section 13-19, 21_

  - [x] 1.2 创建 Alembic 迁移脚本
    - 按顺序: agents → personas → knowledge_bases → knowledge_documents → agent_personas → conversation_messages → ALTER practice_sessions
    - 运行迁移并验证
    - _Requirements: R13_
    - _Design: Section 21_

  - [x] 1.3 创建 AgentContext 和能力模块基础
    - 创建 `backend/src/agent/context.py` - AgentContext dataclass
    - 创建 `backend/src/agent/capabilities/base.py` - BaseCapability, CapabilityConfig, CapabilityResult
    - 创建 `backend/src/agent/capabilities/registry.py` - CapabilityRegistry 单例
    - 创建 `backend/src/agent/capabilities/runner.py` - CapabilityRunner
    - 单元测试: `backend/tests/unit/test_capability_base.py`
    - _Requirements: R6, R7, R8_
    - _Design: Section 1-3_

  - [x] 1.4 创建 Pydantic Schemas
    - 创建 `backend/src/agent/schemas.py` - Agent, Persona, AgentPersona 的请求/响应 schemas
    - 创建 `backend/src/common/knowledge/schemas.py` - KnowledgeBase, KnowledgeDocument schemas
    - 创建 `backend/src/common/conversation/schemas.py` - ConversationMessage, ReplayData schemas
    - 确保所有 schemas 使用 `model_config = ConfigDict(from_attributes=True)`
    - _Requirements: R1-R5, R9-R10_
    - _Design: Section 13-18_

- [x] 2. Agent/Persona/Knowledge 管理 (Service + API 全套)
  - [x] 2.1 Agent Service
    - 创建 `backend/src/agent/services/agent_service.py`
    - 实现 create() - 创建 Agent，status=draft
    - 实现 list() - 分页列表，支持 category/status 筛选
    - 实现 get_by_id() - 获取详情
    - 实现 update() - 部分更新
    - 实现 delete() - 检查关联会话
    - 实现 publish() - 发布 Agent
    - 实现 archive() - 归档 Agent
    - 实现 get_personas() - 获取关联 Persona
    - 单元测试: `backend/tests/unit/test_agent_service.py`
    - _Requirements: R1, R2_
    - _Design: Section 4_

  - [x] 2.2 Agent API (管理端 + 用户端)
    - 创建 `backend/src/agent/api/agents.py`
    - POST /api/v1/admin/agents - 创建
    - GET /api/v1/admin/agents - 列表
    - GET /api/v1/admin/agents/{id} - 详情
    - PUT /api/v1/admin/agents/{id} - 更新
    - DELETE /api/v1/admin/agents/{id} - 删除
    - POST /api/v1/admin/agents/{id}/publish - 发布
    - POST /api/v1/admin/agents/{id}/archive - 归档
    - GET /api/v1/agents - 已发布 Agent 列表 (用户端)
    - GET /api/v1/agents/{id} - Agent 详情，不含 system_prompt (用户端)
    - GET /api/v1/agents/{id}/personas - 关联 Persona 列表 (用户端)
    - 集成测试: `backend/tests/integration/test_agent_api.py`
    - _Requirements: R1, R2_
    - _Design: Section 4, docs/api-contract/agents.md_

  - [x] 2.3 Persona Service
    - 创建 `backend/src/agent/services/persona_service.py`
    - 实现 create() - 创建 Persona
    - 实现 list() - 分页列表，支持 category/difficulty 筛选
    - 实现 get_by_id() - 获取详情
    - 实现 update() - 部分更新
    - 实现 delete() - 检查 Agent 关联
    - 实现 duplicate() - 复制 Persona
    - 单元测试: `backend/tests/unit/test_persona_service.py`
    - _Requirements: R3_
    - _Design: Section 5_

  - [x] 2.4 Persona API
    - 创建 `backend/src/agent/api/personas.py`
    - POST /api/v1/admin/personas - 创建
    - GET /api/v1/admin/personas - 列表
    - GET /api/v1/admin/personas/{id} - 详情
    - PUT /api/v1/admin/personas/{id} - 更新
    - DELETE /api/v1/admin/personas/{id} - 删除
    - POST /api/v1/admin/personas/{id}/duplicate - 复制
    - 集成测试: `backend/tests/integration/test_persona_api.py`
    - _Requirements: R3_
    - _Design: Section 5, docs/api-contract/personas.md_

  - [x] 2.5 Agent-Persona 关联 API
    - 创建 `backend/src/agent/api/agent_personas.py`
    - POST /api/v1/admin/agents/{id}/personas - 添加关联
    - GET /api/v1/admin/agents/{id}/personas - 获取关联列表
    - PUT /api/v1/admin/agents/{id}/personas/{persona_id} - 更新关联
    - DELETE /api/v1/admin/agents/{id}/personas/{persona_id} - 移除关联
    - 实现 is_default 唯一性检查
    - 集成测试: `backend/tests/integration/test_agent_persona_api.py`
    - _Requirements: R4_
    - _Design: Section 15, docs/api-contract/personas.md_

  - [x] 2.6 Knowledge Service
    - 创建 `backend/src/common/knowledge/service.py`
    - 实现 create() - 创建知识库 + 向量集合
    - 实现 list() - 分页列表
    - 实现 get_by_id() - 获取详情
    - 实现 update() - 更新元数据
    - 实现 delete() - 检查引用 + 删除向量集合
    - 实现 upload_document() - 上传文档 + BackgroundTasks
    - 实现 search() - 向量检索
    - 单元测试: `backend/tests/unit/test_knowledge_service.py`
    - _Requirements: R5_
    - _Design: Section 6, 27_

  - [x] 2.7 Knowledge API
    - 创建 `backend/src/common/knowledge/api.py`
    - POST /api/v1/admin/knowledge - 创建知识库
    - GET /api/v1/admin/knowledge - 列表
    - GET /api/v1/admin/knowledge/{id} - 详情
    - PUT /api/v1/admin/knowledge/{id} - 更新
    - DELETE /api/v1/admin/knowledge/{id} - 删除
    - POST /api/v1/admin/knowledge/{id}/documents - 上传文档 (202 Accepted)
    - GET /api/v1/admin/knowledge/{id}/documents - 文档列表
    - GET /api/v1/admin/knowledge/{id}/documents/{doc_id} - 文档详情
    - DELETE /api/v1/admin/knowledge/{id}/documents/{doc_id} - 删除文档
    - GET /api/v1/admin/knowledge/{id}/documents/{doc_id}/preview - 预览分块
    - 集成测试: `backend/tests/integration/test_knowledge_api.py`
    - _Requirements: R5_
    - _Design: Section 6, docs/api-contract/knowledge.md_

  - [x] 2.8 文档处理后台任务
    - 创建 `backend/src/common/knowledge/processor.py`
    - 实现 process_document() - 读取 → 分块 → 向量化
    - 支持 PDF, DOCX, TXT, MD 格式
    - 更新文档状态: pending → processing → ready/failed
    - 错误处理: 记录 error_message
    - 单元测试: `backend/tests/unit/test_document_processor.py`
    - _Requirements: R5_
    - _Design: Section 27_

- [x] 3. 能力模块 (4 个核心能力)
  - [x] 3.1 模糊词检测能力
    - 创建 `backend/src/agent/capabilities/fuzzy_detection.py`
    - 实现 FuzzyDetectionCapability
    - 默认模糊词模式: uncertain, filler, vague
    - 冷却时间机制
    - 单元测试: `backend/tests/unit/test_fuzzy_detection.py`
    - _Requirements: R6_
    - _Design: Section 8_

  - [x] 3.2 销售阶段识别能力
    - 创建 `backend/src/agent/capabilities/sales_stage.py`
    - 实现 SalesStageCapability
    - 5 个阶段: opening, discovery, presentation, objection, closing
    - 基于关键词的阶段判断
    - 进度计算和指导生成
    - 单元测试: `backend/tests/unit/test_sales_stage.py`
    - _Requirements: R7_
    - _Design: Section 9_

  - [x] 3.3 实时评分能力
    - 创建 `backend/src/agent/capabilities/realtime_scoring.py`
    - 实现 RealtimeScoringCapability
    - 默认 5 维度评分
    - 支持 Persona 权重覆盖
    - 趋势计算 (up/down/stable)
    - 单元测试: `backend/tests/unit/test_realtime_scoring.py`
    - _Requirements: R8_
    - _Design: Section 10_

  - [x] 3.4 知识库检索能力
    - 创建 `backend/src/agent/capabilities/knowledge_retrieval.py`
    - 实现 KnowledgeRetrievalCapability
    - 合并 Agent + Persona 知识库
    - 格式化检索结果为 LLM 上下文
    - 单元测试: `backend/tests/unit/test_knowledge_retrieval.py`
    - _Requirements: R5_
    - _Design: Section 7_

- [x] 4. 对话存储/回放 + WebSocket 增强
  - [x] 4.1 Message Storage Service
    - 创建 `backend/src/common/conversation/storage.py`
    - 实现 save_message() - 保存消息
    - 实现 update_analysis() - 更新分析数据
    - 实现 mark_highlight() - 标记关键时刻
    - 单元测试: `backend/tests/unit/test_message_storage.py`
    - _Requirements: R9_
    - _Design: Section 11_

  - [x] 4.2 Replay Service
    - 创建 `backend/src/common/conversation/replay.py`
    - 实现 get_messages() - 分页获取消息
    - 实现 get_replay_data() - 完整回放数据 + 时间轴标记
    - 实现 get_highlights() - 获取关键时刻
    - 实现 _generate_timeline_markers() - 生成时间轴
    - 单元测试: `backend/tests/unit/test_replay_service.py`
    - _Requirements: R10_
    - _Design: Section 12_

  - [x] 4.3 Replay API
    - 创建 `backend/src/common/conversation/api.py`
    - GET /api/v1/sessions/{id}/messages - 消息列表
    - GET /api/v1/sessions/{id}/replay - 回放数据
    - GET /api/v1/sessions/{id}/highlights - 关键时刻
    - GET /api/v1/sessions/{id}/audio/{message_id} - 音频文件
    - 检查会话状态 (必须 completed)
    - 集成测试: `backend/tests/integration/test_replay_api.py`
    - _Requirements: R10_
    - _Design: Section 12, docs/api-contract/replay.md_

  - [x] 4.4 Enhanced Sales Handler
    - 创建 `backend/src/sales_bot/websocket/enhanced_handler.py`
    - 实现 EnhancedSalesHandler (组合模式)
    - 实现 initialize() - 加载 Agent/Persona 配置
    - 实现 _process_user_text() - 集成能力模块
    - 实现 _send_fuzzy_detection() - 发送模糊词消息
    - 实现 _send_stage_update() - 发送阶段更新
    - 实现 _send_score_update() - 发送评分更新
    - 保持与 SimpleSalesHandler 向后兼容
    - _Requirements: R11_
    - _Design: Section 20_

  - [x] 4.5 WebSocket 路由更新
    - 更新 `backend/src/sales_bot/websocket/router.py`
    - 支持 agent_id, persona_id 参数
    - 根据参数选择 SimpleSalesHandler 或 EnhancedSalesHandler
    - 所有消息包含 trace_id
    - _Requirements: R11_
    - _Design: Section 20, docs/api-contract/websocket.md_

  - [x] 4.6 音频存储配置
    - 创建 `backend/src/common/storage/audio.py`
    - 实现 save_audio() - 保存音频文件
    - 实现 get_audio_url() - 获取音频 URL
    - 配置环境变量: AUDIO_STORAGE_PATH, AUDIO_RETENTION_DAYS
    - 创建清理定时任务 (可选)
    - _Requirements: R9_
    - _Design: Section 23_

  - [x] 4.7 WebSocket E2E 测试
    - 创建 `backend/tests/e2e/test_websocket_flow.py`
    - 测试完整对话流程
    - 验证 fuzzy_detection 消息
    - 验证 stage_update 消息
    - 验证 score_update 消息
    - _Requirements: R11_
    - _Design: Section 26_

- [x] 5. 会话管理 + 数据迁移 + 集成验收
  - [x] 5.1 Session Service 扩展
    - 扩展 `backend/src/common/api/practice.py`
    - POST /api/v1/sessions 支持 agent_id, persona_id
    - 验证 Persona 已关联到 Agent
    - 会话完成时生成增强报告
    - GET /api/v1/sessions/stats - 统计数据
    - _Requirements: R12_
    - _Design: Section 19_

  - [x] 5.2 硬编码 Persona 迁移
    - 创建 `backend/src/agent/migrations/migrate_personas.py`
    - 从 simple_handler.py 提取 PERSONA_CONFIG
    - 迁移到数据库 (幂等)
    - 创建默认 "销售教练" Agent
    - 关联迁移的 Persona 到 Agent
    - 运行迁移脚本
    - _Requirements: R13_
    - _Design: Section 22_

  - [x] 5.3 API 路由注册
    - 更新 `backend/src/main.py`
    - 注册 Agent API 路由
    - 注册 Persona API 路由
    - 注册 Knowledge API 路由
    - 注册 Replay API 路由
    - 更新 OpenAPI 文档
    - _Requirements: R12, R13_

  - [x] 5.4 集成测试
    - 完整 Agent CRUD 流程测试
    - 完整 Persona CRUD 流程测试
    - 完整知识库流程测试 (上传 → 处理 → 检索)
    - 完整会话流程测试 (创建 → 对话 → 回放)
    - _Requirements: R12, R13_

  - [x] 5.5 文档更新
    - 更新 `docs/api.md` - 新增 API 文档
    - 更新 `docs/architecture.md` - 架构变更
    - 更新 README - 新功能说明
    - _Requirements: R12, R13_

## 依赖关系

```
Task 1 (基础设施) ✅
    ↓
Task 2 (Agent/Persona/Knowledge 管理)
    ↓
Task 3 (能力模块)
    ↓
Task 4 (对话存储/回放 + WebSocket)
    ↓
Task 5 (会话管理 + 迁移 + 验收)
```

## 估算工时

| Task | 内容 | 估算工时 |
|------|------|----------|
| Task 1 | 基础设施层 | 4h ✅ |
| Task 2 | Agent/Persona/Knowledge 管理 | 14h |
| Task 3 | 能力模块 | 6h |
| Task 4 | 对话存储/回放 + WebSocket | 10h |
| Task 5 | 会话管理 + 迁移 + 验收 | 9h |
| **总计** | | **~43h** |
