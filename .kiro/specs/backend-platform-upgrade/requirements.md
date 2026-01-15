# Requirements Document

## Introduction

本文档定义了 AI 练习平台后端升级的需求，从基础的"对讲机模式"语音对话系统升级到完整的 AI 练习平台。升级包括 Agent 管理、Persona 管理、知识库管理、实时反馈能力和对话回放功能。

**关键参考文档：**
- API 契约: `docs/api-contract/` 目录
- 现有数据库 schema: `backend/src/common/db/schemas.py`
- 现有 WebSocket 实现: `backend/src/sales_bot/websocket/simple_handler.py`
- 开发规范: `.kiro/steering/backend-principles.md`

## Glossary

- **Agent**: 可配置的 AI 训练场景（如销售教练、演讲教练），包含特定能力和行为配置
- **Persona**: 用户在练习中交互的 AI 角色（如怀疑型客户、价格敏感型买家）
- **Knowledge_Base**: 用于为 AI 对话提供上下文和信息的文档集合
- **Capability**: 可为 Agent 启用/配置的模块化功能（如模糊词检测、评分）
- **Session**: 用户与 AI Persona 在 Agent 上下文中的练习对话
- **Fuzzy_Word**: 应在专业沟通中避免的模糊或不确定表达（如"大概"、"可能"）
- **Sales_Stage**: 销售对话流程中的阶段（opening, discovery, presentation, objection, closing）
- **Conversation_Message**: 练习对话中的单轮消息，包含文本、音频和分析数据
- **Result_T**: 用于 API 错误处理的标准响应包装模式
- **BehaviorConfig**: Persona 的行为配置，包含 response_length、challenge_frequency 等

## Requirements

### Requirement 1: Agent 管理 - 管理端 API

**User Story:** 作为管理员，我希望创建和管理 AI 训练 Agent，以便为用户配置不同的练习场景。

#### Acceptance Criteria

1. WHEN 管理员通过 POST /api/v1/admin/agents 创建 Agent, THE Agent_Service SHALL 存储 Agent 并设置 status 为 "draft"，返回包含 id、name、status、created_at 的响应
2. WHEN 管理员通过 GET /api/v1/admin/agents 请求列表, THE Agent_Service SHALL 返回分页结果，支持 page、page_size、category、status 筛选参数
3. WHEN 管理员通过 GET /api/v1/admin/agents/{agent_id} 请求详情, THE Agent_Service SHALL 返回完整的 Agent 信息，包括 system_prompt 和 capabilities_config
4. WHEN 管理员通过 PUT /api/v1/admin/agents/{agent_id} 更新 Agent, THE Agent_Service SHALL 支持部分更新并验证 capabilities_config 格式
5. WHEN 管理员通过 POST /api/v1/admin/agents/{agent_id}/publish 发布 Agent, THE Agent_Service SHALL 将 status 改为 "published" 并设置 published_at
6. WHEN 管理员通过 POST /api/v1/admin/agents/{agent_id}/archive 归档 Agent, THE Agent_Service SHALL 将 status 改为 "archived"
7. WHEN 管理员通过 DELETE /api/v1/admin/agents/{agent_id} 删除有关联会话的 Agent, THE Agent_Service SHALL 返回错误码 [AGENT_CANNOT_DELETE]
8. THE Agent 数据模型 SHALL 包含: id(UUID), name(100字符), description(500字符), icon, category(sales|presentation|interview|customer_service), system_prompt, welcome_message, capabilities_config(JSON), default_knowledge_base_ids(JSON), status(draft|published|archived), version, created_by, created_at, updated_at, published_at

### Requirement 2: Agent 管理 - 用户端 API

**User Story:** 作为用户，我希望浏览已发布的 Agent 列表，以便选择练习场景。

#### Acceptance Criteria

1. WHEN 用户通过 GET /api/v1/agents 请求列表, THE Agent_Service SHALL 仅返回 status 为 "published" 的 Agent，支持 category 筛选
2. WHEN 用户通过 GET /api/v1/agents/{agent_id} 请求详情, THE Agent_Service SHALL 返回用户可见信息（不含 system_prompt），包括 welcome_message 和 capabilities 列表
3. WHEN 用户通过 GET /api/v1/agents/{agent_id}/personas 请求角色列表, THE Agent_Service SHALL 返回关联的 Persona 列表，按 display_order 排序

### Requirement 3: Persona 管理 - 管理端 API

**User Story:** 作为管理员，我希望创建和管理 AI 角色，以便定义用户可以练习的不同对话伙伴。

#### Acceptance Criteria

1. WHEN 管理员通过 POST /api/v1/admin/personas 创建 Persona, THE Persona_Service SHALL 存储 Persona 并设置 status 为 "active"
2. WHEN 管理员通过 GET /api/v1/admin/personas 请求列表, THE Persona_Service SHALL 返回分页结果，支持 category、difficulty 筛选，包含 usage_count 和 agent_count
3. WHEN 管理员通过 GET /api/v1/admin/personas/{persona_id} 请求详情, THE Persona_Service SHALL 返回完整信息，包括 system_prompt、traits、behavior_config、scoring_weights
4. WHEN 管理员通过 PUT /api/v1/admin/personas/{persona_id} 更新 Persona, THE Persona_Service SHALL 验证 behavior_config 格式并支持部分更新
5. WHEN 管理员通过 POST /api/v1/admin/personas/{persona_id}/duplicate 复制 Persona, THE Persona_Service SHALL 创建副本，name 后缀 "(副本)"
6. WHEN 管理员删除被 Agent 关联的 Persona, THE Persona_Service SHALL 返回错误码 [PERSONA_IN_USE]
7. THE Persona 数据模型 SHALL 包含: id(UUID), name(100字符), description(500字符), icon, category(customer|interviewer|coach|examiner), difficulty(easy|medium|hard), system_prompt, traits(JSON), knowledge_base_ids(JSON), behavior_config(JSON), scoring_weights(JSON), is_public, status(active|inactive), created_by, created_at, updated_at
8. THE BehaviorConfig SHALL 包含: response_length(short|medium|long), challenge_frequency(0-1), interruption_triggers(string[]), typical_questions(string[])

### Requirement 4: Agent-Persona 关联 API

**User Story:** 作为管理员，我希望将 Persona 关联到 Agent，以便用户在每个训练场景中选择不同的练习伙伴。

#### Acceptance Criteria

1. WHEN 管理员通过 POST /api/v1/admin/agents/{agent_id}/personas 添加关联, THE Agent_Service SHALL 创建 AgentPersona 记录，包含 display_order、is_default、override_config
2. WHEN 管理员通过 GET /api/v1/admin/agents/{agent_id}/personas 请求列表, THE Agent_Service SHALL 返回关联的 Persona 详情，按 display_order 排序
3. WHEN 管理员通过 PUT /api/v1/admin/agents/{agent_id}/personas/{persona_id} 更新关联, THE Agent_Service SHALL 允许修改 display_order、is_default、override_config
4. WHEN 管理员通过 DELETE /api/v1/admin/agents/{agent_id}/personas/{persona_id} 移除关联, THE Agent_Service SHALL 删除 AgentPersona 记录
5. WHEN 管理员设置某 Persona 为 default, THE Agent_Service SHALL 确保每个 Agent 只有一个 default Persona
6. IF Persona 已关联到该 Agent, THEN THE Agent_Service SHALL 返回错误码 [PERSONA_ALREADY_LINKED]
7. THE AgentPersona 数据模型 SHALL 包含: id(UUID), agent_id, persona_id, display_order(int), is_default(bool), override_config(JSON)

### Requirement 5: 知识库管理 API

**User Story:** 作为管理员，我希望管理知识库和文档，以便 AI 在对话中引用相关信息。

#### Acceptance Criteria

1. WHEN 管理员通过 POST /api/v1/admin/knowledge 创建知识库, THE Knowledge_Service SHALL 创建对应的向量集合并存储元数据
2. WHEN 管理员通过 GET /api/v1/admin/knowledge 请求列表, THE Knowledge_Service SHALL 返回分页结果，包含 document_count 和 total_chunks
3. WHEN 管理员通过 POST /api/v1/admin/knowledge/{id}/documents 上传文档, THE Knowledge_Service SHALL 接受 PDF、DOCX、TXT、MD 文件（最大 50MB），返回 202 Accepted
4. WHEN 文档上传后, THE Knowledge_Service SHALL 异步处理：pending → processing → ready/failed
5. WHEN 管理员通过 GET /api/v1/admin/knowledge/{id}/documents/{docId}/preview 预览文档, THE Knowledge_Service SHALL 返回分块内容和元数据
6. WHEN 管理员删除被 Agent 或 Persona 引用的知识库, THE Knowledge_Service SHALL 返回错误码 [KNOWLEDGE_BASE_IN_USE]
7. IF 文件类型不支持, THEN THE Knowledge_Service SHALL 返回错误码 [UNSUPPORTED_FILE_TYPE]
8. IF 文件过大, THEN THE Knowledge_Service SHALL 返回错误码 [FILE_TOO_LARGE]
9. THE KnowledgeBase 数据模型 SHALL 包含: id(UUID), name(100字符), description(500字符), category(product|competitor|faq|policy), vector_collection, embedding_model, document_count, total_chunks, status(active|archived), created_at, updated_at
10. THE KnowledgeDocument 数据模型 SHALL 包含: id(UUID), knowledge_base_id, title(200字符), file_type, file_url, file_size, status(pending|processing|ready|failed), chunk_count, error_message, created_at

### Requirement 6: 模糊词检测能力

**User Story:** 作为用户，我希望在使用模糊表达时收到实时反馈，以便提高沟通精确度。

#### Acceptance Criteria

1. WHEN 用户语音被转录后, THE Fuzzy_Detection_Capability SHALL 分析文本中的模糊词模式
2. WHEN 检测到模糊词, THE Fuzzy_Detection_Capability SHALL 返回 category(uncertain|filler|vague)、matched(string[])、suggestion、severity(high|medium|low)
3. THE Fuzzy_Detection_Capability SHALL 支持通过 capabilities_config 配置检测模式和冷却时间
4. WHEN 检测到模糊词, THE WebSocket_Handler SHALL 发送 "fuzzy_detection" 消息，格式符合 docs/api-contract/websocket.md 定义
5. THE Fuzzy_Detection_Capability SHALL 遵循 .kiro/templates/backend/capability.py 模板实现

### Requirement 7: 销售阶段识别能力

**User Story:** 作为练习销售对话的用户，我希望看到当前处于销售流程的哪个阶段，以便应用适当的技巧。

#### Acceptance Criteria

1. WHEN 对话进行中, THE Sales_Stage_Capability SHALL 分析对话历史以确定当前阶段
2. THE Sales_Stage_Capability SHALL 识别五个阶段: opening(开场破冰), discovery(需求挖掘), presentation(方案呈现), objection(异议处理), closing(促成成交)
3. WHEN 阶段变化, THE WebSocket_Handler SHALL 发送 "stage_update" 消息，包含 current_stage、stage_name、key_actions、guidance、progress(0-1)
4. THE Sales_Stage_Capability SHALL 可通过 Agent 的 capabilities_config 配置
5. THE stage_update 消息格式 SHALL 符合 docs/api-contract/websocket.md 定义

### Requirement 8: 实时评分能力

**User Story:** 作为用户，我希望看到实时更新的表现分数，以便在练习中跟踪进步。

#### Acceptance Criteria

1. WHEN 用户完成一轮对话, THE Realtime_Scoring_Capability SHALL 计算配置维度的分数
2. THE Realtime_Scoring_Capability SHALL 支持配置维度和权重（如专业度: 0.25, 沟通技巧: 0.25, 销售流程: 0.20, 异议处理: 0.15, 成交能力: 0.15）
3. WHEN 计算分数后, THE Realtime_Scoring_Capability SHALL 包含 trend(up|down|stable) 和 delta
4. WHEN 分数更新, THE WebSocket_Handler SHALL 发送 "score_update" 消息，包含 overall、dimensions 数组、feedback
5. THE Realtime_Scoring_Capability SHALL 优先使用 Persona 的 scoring_weights，否则使用 Agent 默认配置
6. THE score_update 消息格式 SHALL 符合 docs/api-contract/websocket.md 定义

### Requirement 9: 对话消息存储

**User Story:** 作为用户，我希望练习对话被保存，以便稍后回顾。

#### Acceptance Criteria

1. WHEN 会话中交换消息, THE Message_Storage_Service SHALL 持久化消息，包含 turn_number、role(user|assistant)、content、timestamp
2. WHEN 有音频可用, THE Message_Storage_Service SHALL 存储 audio_url 和 duration_ms
3. WHEN 执行实时分析, THE Message_Storage_Service SHALL 存储 fuzzy_words、sales_stage、score_snapshot、ai_feedback
4. THE Message_Storage_Service SHALL 将重要时刻标记为 highlight，包含 highlight_type(good|bad|neutral) 和 highlight_reason
5. THE ConversationMessage 数据模型 SHALL 符合 docs/api-contract/replay.md 定义

### Requirement 10: 对话回放 API

**User Story:** 作为用户，我希望回放练习对话并查看时间轴标记，以便回顾关键时刻并从反馈中学习。

#### Acceptance Criteria

1. WHEN 用户通过 GET /api/v1/sessions/{session_id}/messages 请求消息列表, THE Replay_Service SHALL 返回分页消息，包含所有分析数据
2. WHEN 用户通过 GET /api/v1/sessions/{session_id}/replay 请求回放数据, THE Replay_Service SHALL 返回消息和 timeline_markers（阶段变化、高亮、模糊词）
3. WHEN 用户通过 GET /api/v1/sessions/{session_id}/highlights 请求关键时刻, THE Replay_Service SHALL 仅返回标记为 highlight 的消息，包含 suggested_response
4. WHEN 用户通过 GET /api/v1/sessions/{session_id}/audio/{message_id} 请求音频, THE Replay_Service SHALL 返回音频文件或重定向到存储 URL
5. IF 会话未完成, THEN THE Replay_Service SHALL 返回错误码 [SESSION_NOT_COMPLETED]
6. THE API 响应格式 SHALL 符合 docs/api-contract/replay.md 定义

### Requirement 11: WebSocket 消息扩展

**User Story:** 作为前端开发者，我希望 WebSocket 支持新的消息类型，以便向用户显示实时反馈。

#### Acceptance Criteria

1. THE WebSocket_Handler SHALL 支持发送 "fuzzy_detection" 消息，包含 detections 数组（category、matched、suggestion、severity）
2. THE WebSocket_Handler SHALL 支持发送 "stage_update" 消息，包含 current_stage、stage_name、key_actions、guidance、progress
3. THE WebSocket_Handler SHALL 支持发送 "score_update" 消息，包含 overall、dimensions 数组（name、score、trend、delta）、feedback
4. THE WebSocket_Handler SHALL 在所有服务端消息中包含 trace_id 用于调试
5. THE WebSocket_Handler SHALL 扩展现有 simple_handler.py 实现，保持向后兼容
6. THE 消息格式 SHALL 严格符合 docs/api-contract/websocket.md 定义

### Requirement 12: 会话管理增强

**User Story:** 作为用户，我希望使用特定的 Agent 和 Persona 开始练习会话，以便选择训练场景。

#### Acceptance Criteria

1. WHEN 通过 POST /api/v1/sessions 创建会话, THE Session_Service SHALL 接受 agent_id 和 persona_id 参数
2. WHEN 创建会话, THE Session_Service SHALL 验证 Persona 已关联到该 Agent
3. WHEN 会话完成, THE Session_Service SHALL 生成增强报告，包含 dimension_scores、strengths、improvements、suggestions、highlights
4. WHEN 用户通过 GET /api/v1/sessions/stats 请求统计, THE Session_Service SHALL 返回 total_sessions、weekly_sessions、average_score
5. THE practice_sessions 表 SHALL 扩展包含: agent_id、persona_id 字段

### Requirement 13: 数据库迁移

**User Story:** 作为系统管理员，我希望数据库迁移安全且增量进行，以便保留现有数据。

#### Acceptance Criteria

1. WHEN 创建新表, THE Migration SHALL 使用 Alembic 并提供 upgrade 和 downgrade 脚本
2. WHEN 修改现有表, THE Migration SHALL 保留现有数据，新增列设为 nullable 或有默认值
3. THE Migration SHALL 在常用查询列（status、category、created_at）上创建索引
4. THE Migration SHALL 创建外键约束，使用适当的 ON DELETE 行为
5. THE 新增表 SHALL 包含: agents、personas、agent_personas、knowledge_bases、knowledge_documents、conversation_messages
