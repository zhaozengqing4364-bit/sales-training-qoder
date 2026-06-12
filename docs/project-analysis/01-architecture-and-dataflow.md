# 系统架构与数据流深度分析文档

> 生成时间：2026-06-09
> 分析范围：backend/src + web/src 全量代码（只读分析，零代码修改）
> 技术栈：FastAPI + SQLAlchemy 2.0 (Async) + SQLite/PostgreSQL + Next.js 16 + React 19 + TypeScript + Tailwind CSS v4 + WebSocket

---

## 目录

1. [技术栈总览](#一技术栈总览)
2. [系统分层架构](#二系统分层架构)
3. [核心模块依赖图](#三核心模块依赖图)
4. [数据流全景图](#四数据流全景图)
5. [数据库实体关系](#五数据库实体关系)
6. [运行时架构](#六运行时架构)
7. [部署与基础设施](#七部署与基础设施)

---

## 一、技术栈总览

### 后端 (Backend)

| 层级 | 技术/框架 | 版本/说明 |
|------|----------|----------|
| 运行时 | Python | 3.11 - 3.14 |
| Web 框架 | FastAPI | ASGI，依赖注入，自动 OpenAPI |
| ORM | SQLAlchemy 2.0 | AsyncSession，Declarative Base |
| 数据库 | SQLite (dev) / PostgreSQL (prod) | 通过 DATABASE_URL 切换 |
| 向量数据库 | ChromaDB | 知识库 Embedding 存储 |
| 向量检索 | Haystack AI + rank_bm25 | RAG 检索流水线 |
| 缓存 | 内存单例 + Redis (可选) | SessionStateService 支持 Redis |
| 认证 | PyJWT + 企业微信 OAuth | HS256，24h 过期 |
| 实时通信 | WebSocket (原生) | 非 Socket.IO |
| LLM 编排 | LangChain | ChatOpenAI / Azure / Anthropic |
| 语音 ASR | 阿里云 Cloud ASR / Local Paraformer | 首 token ~200ms |
| 语音 TTS | 阿里云 TTS / Edge-TTS / StepFun 内置 | 降级链 |
| 监控 | Prometheus + structlog + OpenTelemetry | 可观测性内嵌 |
| 测试 | pytest + playwright (e2e) | 覆盖率门槛 48% |

### 前端 (Frontend)

| 层级 | 技术/框架 | 版本/说明 |
|------|----------|----------|
| 框架 | Next.js | 16.2.3 (App Router) |
| UI 库 | React | 19.2.3 |
| 语言 | TypeScript | 5.x |
| 样式 | Tailwind CSS | v4 |
| 状态管理 | @tanstack/react-query (v5) | 服务端状态同步 |
| 动画 | framer-motion | 页面过渡 |
| 图表 | recharts | 数据可视化 |
| 测试 | vitest + playwright | 单元 + e2e |
| AI 组件 | CopilotKit | AI Coach 交互 |

---

## 二、系统分层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Next.js App Router)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   (auth)    │  │ (dashboard) │  │   (user)    │  │       admin         │ │
│  │  登录/注册   │  │  用户仪表盘  │  │  练习/考试   │  │     管理后台         │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│                              传输层                                           │
│  HTTP/1.1  +  WebSocket  +  CSRF防护  +  CORS  +  JWT Bearer/Cookie          │
├─────────────────────────────────────────────────────────────────────────────┤
│                              API 网关层 (FastAPI)                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  router_registry.py — 非 WebSocket API 路由总线                          ││
│  │  websocket_routes.py — WebSocket 路由与准入网关                           ││
│  │  http_routes.py — 核心中间件与基础设施路由                                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────────┤
│                              应用服务层                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   common    │  │    admin    │  │    agent    │  │  curriculum_practice│ │
│  │  通用服务    │  │  配置管理    │  │  Agent平台   │  │    课程练习          │ │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────────────┤ │
│  │ presentation│  │  sales_bot  │  │sales_trainer│  │    evaluation       │ │
│  │   演讲教练   │  │  销售机器人  │  │  销售训练    │  │     评估评分         │ │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────────────┤ │
│  │  supervisor │  │   support   │  │training_run.│  │  prompt_templates   │ │
│  │   督导评审   │  │  运行支持    │  │  训练运行时  │  │    提示词模板        │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│                              领域基础设施层                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   auth      │  │     db      │  │  websocket  │  │    monitoring       │ │
│  │  认证授权    │  │  数据库会话  │  │  WS基础设施  │  │   监控/日志/指标     │ │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────────────┤ │
│  │   ai/llm    │  │  knowledge  │  │   audio     │  │   error_handling    │ │
│  │  LLM服务    │  │  知识库引擎  │  │  音频ASR/TTS│  │    错误处理/降级     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│                              数据持久化层                                      │
│  SQLite/PostgreSQL (SQLAlchemy ORM) + ChromaDB (向量) + OSS/COS (对象存储)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 后端模块职责矩阵

| 模块 | 核心职责 | 关键文件数 | 主要路由前缀 |
|------|---------|-----------|-------------|
| `common` | 认证、数据库、通用服务、监控、错误处理、AI服务、知识库、音频 | 80+ | `/api/v1/auth`, `/api/v1/users`, `/api/v1/practice`, `/api/v1/sessions` |
| `admin` | 管理员API、配置资产管理、配置Bundle生命周期 | 20+ | `/api/v1/admin/*` |
| `agent` | Agent/Persona管理、AI能力插件框架 | 15+ | `/api/v1/admin/agents`, `/api/v1/agents` |
| `curriculum_practice` | 课程模板、考官Agent、题库、学习进度、学习路径 | 15+ | `/api/v1/curriculum-practice/*`, `/api/v1/curriculum/*` |
| `evaluation` | 阶段评估、综合报告、评分规则集、评估运行 | 10+ | `/api/v1/evaluation/*` |
| `presentation_coach` | PPT上传/解析、演讲实时反馈、要点追踪、禁用词 | 15+ | `/api/v1/presentations/*`, `WS /ws/presentation` |
| `sales_bot` | 销售场景对话、StepFun实时语音、销售阶段分析 | 20+ | `/api/v1/scenarios/*`, `WS /ws/sales` |
| `sales_trainer` | 训练单元、试卷、做题、语音作业、AI Coach | 20+ | `/api/v1/sales-trainer/*`, `/api/v1/admin/sales-trainer/*` |
| `training_runtime` | 运行时插件分发、场景处理器选择 | 5+ | 被其他模块引用 |
| `supervisor` | 督导评审、复训任务、评分校准 | 5+ | `/api/v1/supervisor/*`, `/api/v1/retraining/*` |
| `support` | 运行时健康、故障诊断 | 5+ | `/api/v1/support/*` |
| `prompt_templates` | 提示词模板管理、场景绑定、治理 | 5+ | `/api/v1/prompt-templates/*`, `/api/v1/scenario-prompts/*` |

---

## 三、核心模块依赖图

### 3.1 高层依赖拓扑（按层从高到低）

```
main.py
└── app_factory.py
    ├── app_lifespan.py
    │   ├── common/auth/api.py
    │   ├── common/auth/service.py
    │   ├── common/db/session.py (init_db)
    │   ├── common/monitoring/logger.py
    │   ├── common/monitoring/otel.py
    │   ├── common/websocket/session_manager.py
    │   ├── common/websocket/session_state_service.py
    │   └── common/jobs/audio_archival.py
    ├── router_registry.py
    │   ├── <所有业务模块>.router
    │   └── common/auth/service.py (Depends注入)
    ├── http_routes.py
    │   ├── common/auth/service.py
    │   ├── common/db/session.py
    │   └── common/monitoring/*
    ├── websocket_routes.py
    │   ├── common/auth/service.py
    │   ├── common/db/models.py
    │   ├── common/services/runtime_gate.py
    │   ├── training_runtime/plugins.py
    │   ├── curriculum_practice.websocket
    │   └── sales_bot.websocket
    └── common/error_handling/middleware.py

common/services/runtime_gate.py
├── common/ai/llm_service.py
├── common/db/models.py
├── common/knowledge/kb_lock_guard.py
├── curriculum_practice/models.py
└── training_runtime

common/services/practice_session_service.py
├── common/db/models.py
├── common/services/session_runtime_state_service.py
├── curriculum_practice/models.py
├── presentation_coach.services
├── sales_bot.services
└── training_runtime.service
```

### 3.2 关键依赖热力图

```
                 ┌─────────────┐
                 │   users     │ ←──── 30+ 张表外键引用
                 └──────┬──────┘
                        │
    ┌───────────────────┼───────────────────┐
    ▼                   ▼                   ▼
┌─────────┐      ┌─────────────┐      ┌──────────┐
│ practice│      │   training  │      │supervisor│
│sessions │      │    tasks    │      │  reviews │
└────┬────┘      └─────────────┘      └──────────┘
     │
     ├──────────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼
┌─────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│conversation│ │evaluation │  │  reports  │  │  audio    │
│ messages  │  │   runs    │  │ snapshots │  │ segments  │
└─────────┘  └───────────┘  └───────────┘  └───────────┘
```

---

## 四、数据流全景图

### 4.1 用户认证数据流

```
[前端登录页] ──POST /auth/login {email,password}──▶ [auth/api.py]
                                                          │
                                                          ▼
                                              [common/auth/service.py]
                                                          │
                                                          ├──▶ SELECT * FROM users
                                                          │         ▼
                                                          │    [(SQLite/PostgreSQL)]
                                                          │         │
                                                          │    User ORM 对象
                                                          │         │
                                                          ├──▶ verify_password (pbkdf2_sha256/bcrypt)
                                                          │         │
                                                          └──── 成功 ──▶ create_access_token (PyJWT HS256)
                                                                                │
                                                                                ▼
                                                                     JWT + Cookie (HttpOnly Secure SameSite)
                                                                                │
                                                                                ▼
                                                                          [前端登录页]
```

### 4.2 企业微信 SSO 数据流

```
[前端] ──GET /auth/wecom/start──▶ [auth/api.py] ──set state cookie──▶ 307 redirect
                                                                           │
                                                                           ▼
                                                                 [企微授权页]
                                                                           │
                                                                           ▼
[前端] ◀──303 redirect── [auth/api.py] ◀──GET /auth/wecom/callback?code=&state=
                              │
                              ├──▶ 校验 state (hmac.compare_digest)
                              ├──▶ authenticate_wechat(code)
                              │       ├──▶ /cgi-bin/gettoken (corpid+secret)
                              │       ├──▶ /cgi-bin/auth/getuserinfo
                              │       └──▶ /cgi-bin/user/get
                              ├──▶ upsert_wecom_user(db, profile)
                              │       └──▶ [(DB)]
                              └──▶ 签发 JWT → 303 redirect return_to
```

### 4.3 练习会话创建到运行数据流

```
[前端训练大厅]
    │
    ├──▶ POST /practice/sessions
    │         │
    │         ▼
    │    PracticeSessionCreateService
    │         │
    │         ├──▶ 1. 校验 agent/persona ──▶ [agent/models.py]
    │         ├──▶ 2. 解析 VoicePolicy ──▶ voice_policy_snapshot
    │         ├──▶ 3. 应用 curriculum ──▶ curriculum_snapshot
    │         └──▶ 4. INSERT practice_sessions ──▶ [(DB)]
    │                    │
    │                    ▼
    │               session_id
    │                    │
    │    [前端跳转 /practice/:id]
    │                    │
    └──▶ WS Connect /ws/:scenario
                  │
                  ▼
         WebSocket Gateway
                  │
                  ├──▶ RuntimeGate.admit_session() ──▶ 运行时准入检查
                  │         └──▶ 校验 scenario/voice_mode/agent/persona/KB绑定 ──▶ [(DB)]
                  │
                  ├──▶ allowed ──▶ 实例化 Runtime Handler
                  │                    │
                  │                    ▼
                  │           dispatch_scenario_plugin()
                  │                    │
                  │      ┌─────────────┼─────────────┐
                  │      ▼             ▼             ▼
                  │   [sales]     [presentation]  [examiner]
                  │      │             │             │
                  │      ▼             ▼             ▼
                  │ StepFunRealtime  Presentation  ExaminerWebSocket
                  │    Handler        Handler         Handler
                  │
                  └──▶ session_manager.register_session()
                              │
                              ▼
                      handler.handle_connection() → 消息循环
```

### 4.4 销售实时对话数据流（StepFun Realtime）

```
[前端麦克风]
    │
    ├──▶ audio_chunk (binary 0x01 PCM Int16)
    │         │
    │         ▼
    │    WS /ws/sales
    │         │
    │         ▼
    │    StepFunRealtimeHandler
    │         │
    │         ├──▶ _prepare_grounding_context() ──▶ [KnowledgeEngine]
    │         │                                          │
    │         │                                          ▼
    │         │                                     [(ChromaDB)]
    │         │
    │         ├──▶ input_audio_buffer.commit ──▶ [StepFun Upstream WS]
    │         │                                          │
    │         │                                          ▼
    │         │                                    [StepFun API]
    │         │                                    (step-audio-2)
    │         │                                          │
    │         │         ┌────────────────────────────────┘
    │         │         │
    │         │    response.audio.delta ──▶ tts_chunk
    │         │         │
    │         │         ▼
    │         │    [前端扬声器]
    │         │
    │         ├──▶ response.text.delta ──▶ 持久化消息 ──▶ [(conversation_messages)]
    │         │
    │         └──▶ 实时评分 ──▶ [Capability Runner]
    │                           │
    │            ┌──────────────┼──────────────┐
    │            ▼              ▼              ▼
    │      [SalesStage]  [FuzzyDetection] [RealtimeScoring]
    │            │              │              │
    │            └──────────────┴──────────────┘
    │                           │
    │         score_update / stage_update
    │                           │
    │                           ▼
    │                      [前端UI]
```

### 4.5 演讲教练实时反馈数据流

```
[前端麦克风] ──audio_chunk──▶ [PresentationWebSocketHandler]
                                     │
                                     ▼
                              [ASR Service] ──▶ transcript
                                     │
                                     ▼
                              [FeedbackService]
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              [PointTracker]   [ForbiddenMatcher] [InterruptionDetector]
                    │                │                │
                    │                │          should_interrupt?
                    │                │                │
                    │                │          是 ──▶ 生成打断语
                    │                │                │
                    │                │    [PromptTemplateService]
                    │                │    [PresentationPromptRoleResolver]
                    │                │                │
                    │                │         [LLMService]
                    │                │                │
                    │                │          [TTS Service]
                    │                │                │
                    │                │           [前端扬声器]
                    │                │
                    └────────────────┴────────────────┘
                                     │
         send_point_updates / send_forbidden_word_alert
                                     │
                                     ▼
                                [前端UI]
```

### 4.6 综合报告生成数据流

```
[会话结束]
    │
    ├──▶ POST /evaluation/:id/report
    │         │
    │         ▼
    │    ComprehensiveReportService
    │         │
    │         ├──▶ 判断 scenario_type
    │         │         │
    │         │    ┌────┴────┐
    │         │    ▼         ▼
    │         │ [presentation]  [sales]
    │         │    │              │
    │         │    ▼              ▼
    │         │ PresentationReportService  聚合 stage results
    │         │                            │
    │         │                            ├──▶ [StagedEvaluationResult]
    │         │                            │
    │         │                            ├──▶ 维度加权评分 ──▶ scoring_ruleset
    │         │                            │
    │         │                            └──▶ 调用 LLM ──▶ generate_detailed_feedback
    │         │                                          │
    │         │                                    [PromptTemplateService]
    │         │                                          │
    │         │                                    渲染 Jinja2
    │         │                                          │
    │         │                                    [LLMService.generate]
    │         │                                          │
    │         │                                    解析响应
    │         │                                          │
    │         │                                          ▼
    │         │                                    [ComprehensiveReport]
    │         │                                          │
    │         │                                          ▼
    │         │                                    [(comprehensive_reports)]
```

### 4.7 配置资产导入导出数据流

```
[Admin前端]
    │
    ├──▶ POST /config-assets/export
    │         │
    │         ▼
    │    ConfigAssetExportService
    │         │
    │         ├──▶ 拓扑排序 ──▶ Resolver 依赖图
    │         │                    │
    │         │         agent → persona → kb
    │         │                    │
    │         └──▶ 逐实体序列化
    │                    │
    │                    ▼
    │            config-asset-export-v1
    │                    │
    │                    ▼
    │              [JSON下载]
    │
    ├──▶ POST /config-assets/import
              │
              ▼
         ConfigAssetImportService
              │
              ├──▶ 校验 schema ──▶ Schema Validator
              │
              ├──▶ 拓扑排序 ──▶ 按依赖顺序导入
              │
              ├──▶ 冲突策略 ──▶ skip / fail / new_version / replace
              │
              └──▶ 写 audit log ──▶ [(config_bundle_audit_logs)]
```

### 4.8 AI Coach 数据流

```
[学员前端]
    │
    ├──▶ POST /ai-coach/sessions
    │         │
    │         ▼
    │    AICoachSessionService
    │         │
    │         ├──▶ 加载 path_config ──▶ [(path_config_snapshot)]
    │         ├──▶ 加载 article ──▶ [(sales_trainer_asset_revisions)]
    │         └──▶ 创建 session ──▶ [(sales_trainer_ai_coach_sessions)]
    │
    ├──▶ POST /turns/:id
              │
              ▼
         AICoachTurnService
              │
              ├──▶ 渲染 prompt ──▶ [PromptTemplateService]
              │
              ├──▶ LLM生成 ──▶ [LLMService]
              │
              ├──▶ 解析 structured output
              │         │
              │         ▼
              │    评分 + 反馈
              │         │
              │         ▼
              │    [(sales_trainer_ai_coach_turns)]
              │
              └──▶ 返回 next_question ──▶ [前端]
```

---

## 五、数据库实体关系

### 5.1 核心实体关系图（文本形式）

```
users ||--o{ practice_sessions : "creates"
users ||--o{ training_tasks : "assigned"
users ||--o{ notifications : "receives"
users ||--o{ user_achievements : "unlocks"
users ||--o{ user_goals : "sets"
users ||--o{ supervisor_reviews : "as_trainee"
users ||--o{ supervisor_reviews : "as_supervisor"
users ||--o{ sales_trainer_quiz_attempts : "attempts"
users ||--o{ sales_trainer_audio_submissions : "submits"
users ||--o{ sales_trainer_ai_coach_sessions : "coached"

scenarios ||--o{ practice_sessions : "typed_by"
presentations ||--o{ practice_sessions : "used_in"
presentations ||--o{ pages : "contains"
pages ||--o{ required_talking_points : "has"
pages ||--o{ forbidden_words : "page_level"

agents ||--o{ agent_personas : "has"
personas ||--o{ agent_personas : "linked"
agents ||--o| agent_voice_policies : "policy"

practice_sessions ||--o{ conversation_messages : "messages"
practice_sessions ||--o{ interruption_events : "events"
practice_sessions ||--o{ evaluation_runs : "evaluated"
practice_sessions ||--o{ highlight_reviews : "reviewed"
practice_sessions ||--o{ session_audio_segments : "audio"
practice_sessions ||--o{ training_report_snapshots : "reports"
practice_sessions ||--o{ comprehensive_reports : "report"
practice_sessions ||--o{ staged_evaluation_results : "stages"
practice_sessions ||--o{ manager_interventions : "resolves"

achievements ||--o{ user_achievements : "definition"

training_tasks ||--o{ retraining_tasks : "spawns"
training_tasks ||--o| practice_sessions : "results_in"

highlight_reviews ||--o{ highlight_review_items : "items"
highlight_reviews ||--o{ highlight_review_shares : "shares"

supervisor_reviews ||--o{ retraining_tasks : "requires"
supervisor_reviews ||--o{ supervisor_score_calibrations : "calibrations"

config_bundles ||--o{ config_versions : "versions"
config_versions ||--o{ evaluation_runs : "evaluated"
config_versions ||--o{ training_report_snapshots : "snapshotted"

knowledge_bases ||--o{ knowledge_documents : "contains"
knowledge_bases ||--o{ knowledge_dictionary_entries : "terms"
knowledge_bases }o--|| rag_profiles : "configures"

practice_templates ||--o{ practice_sessions : "instantiates"
practice_templates ||--o{ training_tasks : "assigned"
question_categories ||--o{ question_items : "has"
question_categories ||--o{ question_categories : "parent"
question_items ||--o{ sales_trainer_unit_questions : "used_in"
question_items ||--o{ sales_trainer_quiz_answers : "answered"

sales_trainer_units ||--o{ sales_trainer_unit_questions : "questions"
sales_trainer_units ||--o{ sales_trainer_exam_papers : "papers"
sales_trainer_units ||--o{ sales_trainer_quiz_attempts : "attempts"
sales_trainer_units ||--o{ sales_trainer_audio_submissions : "submissions"
sales_trainer_quiz_attempts ||--o{ sales_trainer_quiz_answers : "answers"
sales_trainer_asset_revisions ||--o{ sales_trainer_asset_active_revisions : "active_ref"
sales_trainer_audio_submissions ||--o| sales_trainer_audio_transcripts : "transcript"
sales_trainer_audio_submissions ||--o{ sales_trainer_audio_score_results : "scores"
sales_trainer_ai_coach_sessions ||--o{ sales_trainer_ai_coach_turns : "turns"
```

### 5.2 表数量统计

| 领域 | 表数量 | 核心表 |
|------|--------|--------|
| 核心用户与练习 | ~30 | users, practice_sessions, scenarios, presentations, conversation_messages |
| Agent 与语音 | ~6 | agents, personas, agent_personas, voice_runtime_profiles, agent_voice_policies |
| 知识库 | ~12 | knowledge_bases, knowledge_documents, knowledge_config_versions, knowledge_query_profiles, knowledge_answer_runs |
| 课程练习 | ~14 | practice_templates, examiner_agents, case_items, role_profiles, learning_contents, question_items, situation_packs |
| 销售训练 | ~17 | sales_trainer_units, sales_trainer_quiz_attempts, sales_trainer_audio_submissions, sales_trainer_ai_coach_sessions |
| 配置与审计 | ~15 | config_bundles, config_versions, business_rule_configs, prompt_templates, system_logs, supervisor_reviews |
| **总计** | **~107** | — |

---

## 六、运行时架构

### 6.1 WebSocket 运行时网关

```
┌─────────────────────────────────────────────────────────────────┐
│                     WebSocket 连接建立                            │
│  1. 解析 session_id (UUID 校验)                                   │
│  2. RuntimeGate.admit_session() → Terminal/Transient 分类          │
│  3. 解析 token (Bearer → Cookie → Query 回退)                     │
│  4. verify_token() → JWT 解码                                     │
│  5. 所有权校验 (owner == user_id 或 is_admin)                      │
│  6. dispatch_scenario_plugin() → 选择 Runtime Handler              │
│  7. session_manager.register_session()                            │
│  8. handler.handle_connection() → 消息循环                         │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 运行时准入决策矩阵

| 检查项 | 失败分类 | 关闭码 | 说明 |
|--------|---------|--------|------|
| session_id 格式无效 | Terminal | 4400 | INVALID_SESSION_ID |
| scenario 不匹配 | Terminal | 4413 | RUNTIME_NOT_RUNNABLE |
| voice_mode 不合法 | Terminal | 4413 | VOICE_MODE_INVALID |
| agent/persona 不存在 | Terminal | 4413 | AGENT_NOT_FOUND |
| KB Lock 未绑定 | Terminal | 4413 | KB_LOCK_UNBOUND |
| JWT 无效 | Terminal | 4001 | Unauthorized |
| 所有权不匹配 | Terminal | 4003 | ACCESS_DENIED |
| 网络抖动 | Transient | — | 指数退避重连 |

### 6.3 训练运行时生命周期状态机

```
[draft] --validate()--> [validated] --admit()--> [runnable]
                                            |
                                            | WS connect
                                            ▼
                                      [started] --end()--> [completed]
                                            |                |
                                            | fail()         | fail()
                                            ▼                ▼
                                      [failed] <---------- [failed]
                                            |
                                            | repair()
                                            ▼
                                      [runnable] (从 failed 可恢复)
```

### 6.4 音频流架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│  前端麦克风  │────▶│ WebSocket   │────▶│  StepFun Realtime   │
│  (PCM Int16)│     │  Gateway    │     │  API (step-audio-2) │
└─────────────┘     └──────┬──────┘     └─────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ 本地 ASR   │  │ 知识预取   │  │ 打断检测   │
    │ (备选)     │  │ (KB Lock)  │  │ (VAD)      │
    └────────────┘  └────────────┘  └────────────┘
                           │
                           ▼
                    ┌────────────┐
                    │ TTS 输出流 │────▶ 前端扬声器
                    │ (PCM 24kHz)│
                    └────────────┘
```

---

## 七、部署与基础设施

### 7.1 进程架构

```
┌─────────────────────────────────────────┐
│           Uvicorn (ASGI Server)          │
│  Port 3444                               │
│  ┌─────────────────────────────────────┐ │
│  │  FastAPI Application                 │ │
│  │  - HTTP Routes (REST API)            │ │
│  │  - WebSocket Routes (3条)            │ │
│  │  - Middleware Stack                  │ │
│  │  - Background Tasks (lifespan)       │ │
│  └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌────────┐    ┌──────────┐    ┌──────────┐
│SQLite  │    │ ChromaDB │    │  OSS/COS │
│(文件)  │    │ (本地)   │    │ (对象存储)│
└────────┘    └──────────┘    └──────────┘
```

### 7.2 前端开发服务器

```
Next.js Dev Server
  Port 3445
  ├── Hot Module Replacement
  ├── API Proxy (到 localhost:3444)
  └── React Server Components
```

### 7.3 CORS 策略

| 环境 | 允许来源 | 说明 |
|------|---------|------|
| Development | localhost:3445, 3000, 5173, 127.0.0.1, 192.168.* | 自动注入 |
| Production | CORS_ORIGINS 环境变量 | 必须显式配置，禁止 `*` |

### 7.4 健康检查端点

| 端点 | 方法 | 检查内容 | 状态码 |
|------|------|---------|--------|
| `/health` | GET | 数据库 `select 1` | 200/503 |
| `/metrics` | GET | Prometheus 指标 | 200 |

---

*文档结束。本分析基于 2026-06-09 的代码快照，未修改任何源代码。*
