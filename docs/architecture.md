# 系统架构

企业级 AI 智能演练系统的架构文档。描述整体架构、核心模块、关键数据流和设计原则。

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                         AI Practice System                               │
│                                                                           │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────────────┐  │
│  │   Auth   │  │   Admin      │  │   User Facing                      │  │
│  │  ─────── │  │  ─────────   │  │  ──────────                        │  │
│  │ SharedPW │  │ Agents       │  │ Dashboard / Training               │  │
│  │ WeCom SSO│  │ Personas     │  │ Practice Session                   │  │
│  │ JWT      │  │ Knowledge    │  │ Session Report                     │  │
│  │          │  │ Prompts      │  │ Replay / Evidence                  │  │
│  │          │  │ Scoring      │  │ Learning Path / Study              │  │
│  │          │  │ Users/Record │  │ Curriculum Exam                    │  │
│  │          │  │ Config Bund. │  │ Supervisor Review                  │  │
│  │          │  │ Governance   │  │ Growth Center                      │  │
│  │          │  │ Business Ru. │  │                                    │  │
│  └──────────┘  └──────────────┘  └────────────────────────────────────┘  │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    WebSocket Layer (3+ 通道)                       │  │
│  │                                                                   │  │
│  │  /ws/presentation    /ws/sales/*    /ws/curriculum/examiner       │  │
│  │       │                  │                   │                    │  │
│  │  ┌────┴────┐     ┌──────┴──────┐     ┌──────┴──────┐             │  │
│  │  │ PPT     │     │ Sales       │     │ Curriculum  │             │  │
│  │  │ Coach   │     │ Training    │     │ Examiner    │             │  │
│  │  │ Handler │     │ Handler(s)  │     │ Handler     │             │  │
│  │  └─────────┘     └─────────────┘     └─────────────┘             │  │
│  │                                                                   │  │
│  │  All extend BaseWebSocketHandler with:                            │  │
│  │  - async message queue (backpressure)                             │  │
│  │  - heartbeat (30s timeout)                                        │  │
│  │  - session state save/restore (reconnection)                      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Voice Runtime                                  │  │
│  │                                                                   │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │  │
│  │  │  Legacy      │    │  StepFun     │    │  TTS 降级链      │   │  │
│  │  │  ASR→LLM→TTS│    │  Realtime    │    │                  │   │  │
│  │  │  pipeline    │    │  dual-track  │    │  Aliyun →        │   │  │
│  │  │              │    │  speech      │    │  Edge →          │   │  │
│  │  │              │    │              │    │  Browser         │   │  │
│  │  └──────────────┘    └──────────────┘    └──────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Evaluation & Scoring Framework (统一评估)       │  │
│  │                                                                   │  │
│  │  ┌──────────────────────────────────────────────────────────┐    │  │
│  │  │ Effectiveness (common/effectiveness/)                     │    │  │
│  │  │ CanonicalEvaluationKernel → SurfaceReaders               │    │  │
│  │  │ Rollup: logic / accuracy / completeness                   │    │  │
│  │  │ Sales coaching dimensions + ActionCards                  │    │  │
│  │  │ StagedEvaluation + Triggers (keyword/turn/time/stage)    │    │  │
│  │  └──────────────────────────────────────────────────────────┘    │  │
│  │                      ↓                                           │  │
│  │  SessionEvidence → EvaluationRun → TrainingReportSnapshot        │  │
│  │       ↑              ↑                          ↑               │  │
│  │   Conversation   Scoring Rulesets           Config Bundle        │  │
│  │   Messages       + Effectiveness           Snapshot (frozen)     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Knowledge Layer                                │  │
│  │                                                                   │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐   │  │
│  │  │ KB Lock    │  │ Knowledge    │  │ KnowledgeAnswer        │   │  │
│  │  │ Guard      │  │ Service      │  │ Engine (Haystack)      │   │  │
│  │  │ (grounding)│  │ (ChromaDB)   │  │                        │   │  │
│  │  │ strict/    │  │ parse→chunk  │  │ Intent→Retrieval→      │   │  │
│  │  │ coach_mode │  │ →embed→store │  │ Rerank→Assemble        │   │  │
│  │  └────────────┘  └──────────────┘  └────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Agent + Curriculum Platform                    │  │
│  │                                                                   │  │
│  │  Agent → Persona → Capabilities (ASR/TTS/LLM/Scoring/...)        │  │
│  │  Curriculum: ExaminerAgent → QuestionBank → ExamSession           │  │
│  │  LearningPath: Content → Study → Practice → Assessment           │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Supervisor System                              │  │
│  │                                                                   │  │
│  │  TrainingReportViewModel → Review → ScoreCalibration → Decision  │  │
│  │                                         ↓                        │  │
│  │                                  RetrainingTask (复训)            │  │
│  │  TeamInsights: readiness / weaknesses / retraining candidates     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 1. 架构概览

系统采用**模块化单体**架构，后端 Python/FastAPI 提供 REST API 和 WebSocket 端点，前端 Next.js/React 提供 Web UI。两个核心演练场景（PPT 演练、销售对练）独立部署在同一个应用中，通过 `backend/src/presentation_coach/` 和 `backend/src/sales_bot/` 模块隔离。系统围绕四个主要领域构建：**演练运行时**（语音交互）、**知识引擎**（RAG grounding）、**评估评分**（效果衡量）、**主管审核**（人机闭环）。

### 1.1 设计原则

- **场景隔离**：两核心场景禁止互相引用，共享逻辑放入 `common/` 模块
- **降级优先**：所有外部依赖（TTS、ASR、LLM）必须有降级链，不以弹窗报错中断用户体验
- **驱动配置化**：运行时配置从数据库读取，支持热更新，无需重启
- **严格接地**：KB Lock 确保 AI 回答必须基于知识库，禁止臆测
- **不可变报告**：TrainingReportSnapshot 在生成时冻结配置版本，历史报告永不重算
- **规范评估**：Effectiveness 评估体系基于 Canonical 内核，所有消费者（报告/回放/分析/管理后台）使用统一投影

### 1.2 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI | 0.115+ |
| Python | 3.11+ | async/await |
| ORM | SQLAlchemy 2.0+ | async |
| 数据库 | PostgreSQL | via asyncpg |
| 缓存 | Redis | |
| 向量存储 | ChromaDB | |
| LLM | DashScope / StepFun | |
| TTS | Aliyun → Edge → Browser | 降级链 |
| 前端 | Next.js | 16.2.3 |
| UI 库 | React | 19.2.3 |
| 样式 | Tailwind CSS | 4.x |

---

## 2. 应用骨架

### 2.1 启动流程

`main.py` → `create_app()` 工厂函数组装应用：

1. 加载 `.env` 环境变量，配置结构化日志
2. 注册中间件：ErrorHandler → Metrics → CORS → CSRF
3. 注册 HTTP 路由（约 40 个子路由，见 2.5）
4. 注册 WebSocket 路由（3 条通道）
5. lifespan 启动：初始化数据库、ConfigManager、ASR 预加载、SessionManager 和归档调度

### 2.2 关键文件

| 文件 | 职责 |
|------|------|
| `main.py` | 应用入口，兼容旧导入 |
| `app_factory.py` | FastAPI 工厂，中间件 + 路由聚合 |
| `app_lifespan.py` | 启动/关闭生命周期事件 |
| `http_routes.py` | /health, /metrics, /dev-login |
| `router_registry.py` | 40+ 个 API 子路由统一挂载 |
| `websocket_routes.py` | 3 条 WebSocket 路由 + 验证逻辑 |

### 2.3 健康检查

`GET /health` 返回数据库就绪状态和整体 readiness 信号。Prometheus 指标在 `GET /metrics` 暴露。

### 2.4 认证

支持三种认证方式：
- **共享口令**：静态 `AUTH_SHARED_PASSWORD`，适用于受控环境（如内网 SSO 不可用）
- **用户覆盖**：`AUTH_USER_PASSWORDS_JSON` 按账号设定独立口令
- **企业微信 SSO**：WeCom OAuth 登录（生产推荐）

所有登录颁发 JWT，前后端通过 cookie 或 Authorization header 传递。CSRF 保护对所有非豁免路径强制验证。

### 2.5 API 路由总览

系统对外暴露约 40 个子路由组，按领域划分：

| 路由前缀 | 领域 |
|---------|------|
| `/api/v1/agents` | Agent 场景管理 |
| `/api/v1/admin/agents` | Agent 管理后台 |
| `/api/v1/admin/personas` | 角色管理 |
| `/api/v1/admin/knowledge` | 知识库管理 |
| `/api/v1/admin/presentations` | PPT 管理 |
| `/api/v1/admin/presentation-ai` | PPT AI 策略管理 |
| `/api/v1/admin/scoring-rulesets` | 评分规则集 |
| `/api/v1/admin/voice-runtime` | 语音运行时配置 |
| `/api/v1/admin/settings` | 系统设置 |
| `/api/v1/admin/config-center` | 配置中心 |
| `/api/v1/admin/business-rules` | 业务规则管理 |
| `/api/v1/admin/governance` | AI 治理 |
| `/api/v1/admin/audit-trail` | 审计追踪 |
| `/api/v1/admin/analytics` | 管理分析 |
| `/api/v1/admin/knowledge-answer` | 知识问答配置 |
| `/api/v1/admin/rag-profiles` | RAG 配置画像 |
| `/api/v1/admin/model-configs` | 模型配置 |
| `/api/v1/admin/users` | 用户管理 |
| `/api/v1/admin/training-records` | 训练记录 |
| `/api/v1/admin/curriculum-practice` | 课程考核管理 |
| `/api/v1/admin/learning-contents` | 学习内容管理 |
| `/api/v1/admin/test-bank` | 题库管理 |
| `/api/v1/admin/interventions` | 干预管理 |
| `/api/v1/admin/system-logs` | 系统日志 |
| `/api/v1/admin/release-verification` | 发布验证 |
| `/api/v1/practice` | 演练操作 |
| `/api/v1/training` | 训练入口 |
| `/api/v1/training-tasks` | 训练任务 |
| `/api/v1/sessions` | 会话管理(含报告) |
| `/api/v1/sessions/{id}/replay` | 对话回放 |
| `/api/v1/supervisor/team/reports` | 团队报告(主管) |
| `/api/v1/evaluation` | 评估引擎 |
| `/api/v1/growth` | 成长中心 |
| `/api/v1/business-rules` | 业务规则(用户) |
| `/api/v1/scenarios` | 场景列表(用户) |
| `/api/v1/curriculum/learning-path` | 学习路径(用户) |
| `/api/v1/curriculum/study` | 学习内容(用户) |
| `/api/v1/prompt-templates` | 提示词模板 |
| `/api/v1/support/runtime` | 运行状态(运维) |
| `/api/v1/dashboard` | 仪表盘 |
| `/api/v1/analytics` | 分析与排行榜 |

详见 `docs/api-contract/`。

---

## 3. WebSocket 层

### 3.1 架构模式

所有 WebSocket handler 继承 `BaseWebSocketHandler`，提供：

```text
连接建立
  ↓
验证 token + 解析用户身份
  ↓
检查 session 归属（owner 验证）
  ↓
检查 KB Lock 绑定状态（PPT 演练专有）
  ↓
会话状态恢复（重连检测）
  ↓
消息循环（30s 心跳 + 异步队列处理）
  ↓
断开时保存状态
```

### 3.2 三条通道

| 端点 | 场景 | Handler | 消息协议 |
|------|------|---------|----------|
| `/ws/presentation` | PPT 演练 | `PresentationWebSocketHandler` / `PresentationStepFunRealtimeHandler` | JSON 消息 |
| `/ws/sales/{session_id}` | 销售对练 | `StepFunRealtimeHandler` / `Phase4LocalProviderHandler` | StepFun Realtime 协议 |
| `/ws/curriculum/examiner/{session_id}` | 课程考核 | `ExaminerWebSocketHandler` | JSON 消息 |

### 3.3 消息队列与反压

每个 handler 维护一个 `asyncio.Queue`，消息生产（接收）与消费（处理）解耦：

- 队列上限：可配置（默认 300），防内存泄漏
- 溢出策略：`drop_newest`（默认）或 `drop_oldest`
- 反压通知：队列满时向客户端发送 `backpressure` 消息

### 3.4 重连恢复

连接建立时查询 `SessionStateService` 检查是否已有保存的状态。若有，自动恢复：

```
session_id → SessionStateService.get_state()
                    ↓
           ┌─ exists → restore + send "reconnected"
           └─ absent → fresh start
```

### 3.5 会话生命周期控制

`SessionLifecycleService` 提供 REST API 驱动会话状态迁移：

```text
preparing → in_progress → paused → in_progress → completed
                            ↓
                        failed / cancelled
```

状态迁移通过 WebSocket 的 `sync_lifecycle_transition` 同步给运行中的 handler。

---

## 4. 语音运行时

### 4.1 两种模式

系统支持两种语音运行时模式，在会话级别通过 `voice_mode` 字段选择：

| 模式 | 架构 | 适用场景 |
|------|------|---------|
| `legacy` | ASR → LLM → TTS 串行管道 | 浏览器兼容性优先（已逐步弃用） |
| `stepfun_realtime` | StepFun 端到端语音模型，双轨语音流 | 低延迟实时体验（默认模式） |

**StepFun Realtime 模式**：
- 前端通过单条 WebSocket 发送音频 PCM 数据
- 后端代理到 StepFun Realtime API（WebSocket 上行链路）
- StepFun 同时处理 ASR 和 LLM，返回文本 + 音频双轨
- 下行音频流通过同一 WebSocket 返回给前端
- 支持函数调用（知识检索、评分等）和工具链编排

### 4.2 TTS 降级链

```
阿里云流式 TTS (主) → Edge-TTS (备用) → 浏览器 TTS (最终降级)
```

每次降级记录 metrics。最终降级时向前端返回 `[USE_BROWSER_TTS]` 指令，而非抛出异常。

TTS 提供商选择在运行时通过 `TTSProvider` 动态解析，支持从 DB 运行时配置读取（`config_manager`）和从环境变量降级。

### 4.3 ASR

- **阿里云 ASR**：基于 DashScope 的实时语音识别，支持流式
- **本地 ASR**：开发/测试环境使用的本地替代方案
- 自动降级：主服务失败时切换备用

### 4.4 语音运行时配置

语音运行时策略通过 `voice_runtime_policy.py` 和 `voice_instruction_compiler.py` 配置：

- 运行时配置文件定义：TTS 语速、音量、角色声音
- AI 角色的语音指令编译（system prompt + voice 参数合成）
- 管理后台支持动态切换语音运行时配置

---

## 5. 知识层

### 5.1 知识服务 (ChromaDB)

`backend/src/common/knowledge/` 提供文档全生命周期管理：

```text
文档上传（DOCUMENT_STORAGE_PATH）
    ↓
Parse: PDF/Word/PPT/TXT → ParsedElement（结构化元素）
    ↓
Chunk: 语义分块 + 段落分割
    ↓
Embedding → ChromaDB 向量存储
    ↓
检索: 向量检索 + BM25 混合检索 → 排序
```

- `processor.py`：文档解析引擎，支持格式检测、文本提取、分块策略
- `ingestion_service.py`：摄入调度，支持异步批量处理
- `vector_store.py`：ChromaDB 封装，支持 collection 管理和 CRUD
- `bm25_index.py`：关键词检索备用，低配环境不依赖向量

### 5.2 KB Lock 守门机制

KB Lock 是防 AI 臆测的核心机制。当配置了 `require_kb_grounding=true`，AI 回答必须基于知识库，否则被阻止：

```text
用户发言
    ↓
require_kb_grounding?
  ├─ 否 → 正常回答
  └─ 是 → 检查知识库绑定状态
           ├─ 未绑定 → 返回 blocked_no_kb
           ├─ 检索失败 → 返回 blocked_search_failed
           ├─ 结果为空 → 返回 blocked_empty
           └─ 有结果 → 构建 grounding_context 注入 LLM
```

两种模式：
- **strict_audit**：严格模式，检索不足时阻止生成
- **coach_mode**：宽松模式，检索不足时禁止编造但允许给出表达层面的反馈

状态码体系：`blocked_no_kb`、`blocked_not_ready`、`blocked_search_failed`、`blocked_empty`、`pass`

### 5.3 知识问答引擎 (KnowledgeAnswerEngine, Haystack)

`backend/src/common/knowledge_engine/` 提供高质量 RAG 管道：

```text
用户问题
    ↓
IntentClassifier → 问题意图分类
    ↓
EntityResolver → 实体解析（产品名、版本号等）
    ↓
RetrievalPlanner → 多源检索规划
    ↓
HaystackAdapter → Haystack 管道执行（可替换 pipeline 工厂）
    ↓
CrossEncoderReranker → 重排序
    ↓
AnswerabilityEvaluator → 可回答性评估
    ├─ grounded → 有充分依据
    ├─ partial → 部分支持（触发 OutputGuard 裁剪）
    ├─ ungrounded → 无依据（标记非内部确认）
    └─ blocked → 完全阻止
    ↓
Assembler → 组装最终答案 + 引用
```

设计为插件化架构，每阶段可独立配置和替换（RAG Profile 系统）。

### 5.4 RAG Profile & Knowledge Answer Config

RAG Profile 定义检索策略的参数集合（top_k、score threshold、reranker 配置等），通过管理后台 `admin/rag-profiles` 和 `admin/knowledge-answer` 进行可视化配置。支持运行历史追踪和 A/B 比较。

---

## 6. Effectiveness 评估体系

Effectiveness 是系统的核心评估框架，`backend/src/common/effectiveness/` 提供服务端评估逻辑，所有消费者（报告、回放、历史、管理后台）使用统一投影。

### 6.1 体系结构

```text
                         CanonicalEvaluationKernel (v1)
                         ┌──────────────────────────┐
                         │  Dimensions (定义+权重)   │
                         │  Rollup (logic/accuracy/  │
                         │          completeness)    │
                         │  SurfaceReaders (投影器)  │
                         └──────────────────────────┘
                               ↓   ↓   ↓   ↓
                    ┌──────────────────────────────┐
                    │      Surface 消费者           │
                    │  RealtimeScoring              │
                    │  TrainingReportViewModel      │
                    │  Replay Evidence              │
                    │  History Entries              │
                    │  Admin Analytics              │
                    └──────────────────────────────┘
```

### 6.2 维度与汇总

- 销售场景定义 5 个教练维度：`价值表达`、`客户收益连接`、`证据使用`、`异议处理`、`推进下一步`
- 每个维度贡献到 3 个汇总轴：`logic`（逻辑性）、`accuracy`（准确性）、`completeness`（完整性）
- 维度定义包含 `source_aliases` 和 `legacy_field_aliases`，确保新旧兼容

### 6.3 ActionCard 与 PassFlags

评估结果以结构化卡片输出：

- `ActionCard`：可操作的建议卡片（issue / suggestion / next action）
- `PassFlags`：通过/失败标志，定义各维度的达标条件
- `MainIssue`：本轮/本次演练的主要问题诊断
- `NextGoal`：基于表现的下一步发展目标

### 6.4 场景适配

```text
Sales:
  build_sales_effectiveness_metrics() → 5 维度评分
  build_sales_rollup_scores() → 3 轴汇总
  evaluate_pass_flags() → 通过/未通过判定
  build_action_card() → 教练建议卡
  resolve_sales_coaching_focus() → 弱点诊断

Presentation:
  （通过 Canonical kernel 投影，维度定义不同但投影框架一致）
```

---

## 7. 分阶段评估与触发器

### 7.1 评估触发器

`backend/src/evaluation/triggers/` 定义触发式阶段评估：

| 触发器 | 文件 | 触发条件 |
|--------|------|---------|
| 关键词触发 | `keyword.py` | 用户/AI 消息包含配置的关键词 |
| 阶段转移 | `stage_transition.py` | 对话阶段发生转移 |
| 时间间隔 | `time_interval.py` | 自上次评估以来超过设定时间 |
| 轮次数 | `turn_count.py` | 对话轮次达到设定值 |

所有触发器继承 `BaseTrigger`，实现 `should_trigger(context)` 接口，支持冷却期（cooldown）避免频繁触发。

### 7.2 阶段配置

`staged_evaluation.py` 将对话按阶段评分：

```text
StageConfig:
  stage_number
  name ("开场破冰" / "需求挖掘" / "方案呈现" / "异议处理" / "促成成交")
  description
  evaluation_prompt_type
  triggers [keyword, stage_transition, time_interval, turn_count]
  start_turn / end_turn
```

每个阶段使用独立 LLM prompt 进行评分，返回 `StageEvaluationResult`（scores、strengths、weaknesses、suggestions）。

### 7.3 评估数据流

```text
对话消息 → Trigger 检测 → StageEvaluation (LLM)
    ↓
EvaluationRun (持久化评估结果，含 config_bundle_id)
    ↓
SessionEvidence (统一证据投影)
    ↓
TrainingReportSnapshot (不可变快照，冻结配置+评分)
```

### 7.4 评分规则集

`scoring_rulesets.py` 提供可配置的评分规则系统：

- 定义评分维度、权重、通过阈值
- 与 `ConfigBundle` 关联，支持版本管理
- `ScoringRuleset` 数据库实体持久化规则定义
- 管理后台可视化编辑

---

## 8. 训练运行时

### 8.1 统一运行时主语

`TrainingRuntimeDescriptor` 是所有训练会话的标准描述符：

```text
subject: training_scenario_runtime  (固定值，不再分叉)
session_id: str
scenario_type: "sales" | "presentation"
agent_id: str | None
persona_id: str | None
presentation_id: str | None
voice_mode: str | None ("legacy" | "stepfun_realtime")
runtime_profile_id: str | None
focus_intent: dict | None
training_task_id: str | None
```

确保所有下游模块使用一致的语言引用运行时，避免场景分支判断。详见 ADR `2026-03-14-training-runtime-subject.md`。

### 8.2 训练任务体系

| 实体 | 归属 | 职责 |
|------|------|------|
| `TrainingTask` | `common/` | 训练组织的最小调度单位，状态机：assigned → in_progress → completed |
| `RetrainingTask` | `supervisor/` | 主管判定 needs_retraining 后的二次训练任务 |
| `PracticeSession` | `common/` | 一次训练运行的物理承载，包含 state、时间线 |
| `TrainingRuntimeDescriptor` | `training_runtime/` | 运行时描述符，统一下游投影 |

**生命周期控制**：
- REST API 端点支持外部触发状态迁移（开始/暂停/恢复/强制完成）
- 状态迁移通过 WebSocket 的 `sync_lifecycle_transition` 同步给运行中 handler

---

## 9. Supervisor 主管审核系统

`backend/src/supervisor/` 提供演练报告审阅、评分校准和复训任务管理，是 Phase 3 的核心交付。

### 9.1 数据流

```text
TrainingReportViewModel (完整视图，包含证据链)
    ↓
SupervisorReview (主管审阅记录)
    ↓
SupervisorScoreCalibration (评分校准，按维度调整)
    ↓
SupervisorReviewDecision (审核决策: approve / needs_retraining)
    ↓ (needs_retraining)
RetrainingTask (复训任务创建)
    ↓
PracticeSession (复训会话) → 新报告 → 对比(before/after)
```

### 9.2 TrainingReportViewModel

主管审阅界面依赖的完整视图模型，包含：

- `TrainingReportTrainee`：学员信息
- `TrainingReportDimensionScore`：各维度评分及证据
- `TrainingReportEvidenceItem`：证据项（引用原文 + 页面归属）
- `TrainingReportIssue`：问题标记（含风险等级）
- `TrainingReportNextAction`：建议操作
- `TrainingReportRiskFlag`：风险标记
- `TrainingReportThinkingEvidence`：AI 思考过程追迹
- `BeforeAfterComparison`：复训前后对比

### 9.3 团队洞察

Supervisor 还提供团队级分析，供管理者和培训主管使用：

- **TeamInsightsResponse**：团队完成度、弱项分布、重训候补
- **TeamInsightsReadiness**：各学员 readiness 评分
- **TeamInsightsWeakness**：常见弱项分析（按维度统计）
- **CertificationReviewQueueItem**：认证审核队列

### 9.4 API 端点

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/supervisor/team/reports` | 团队报告列表 |
| GET | `/supervisor/report/{session_id}` | 单份报告视图 |
| POST | `/supervisor/review` | 创建审阅记录 |
| PUT | `/supervisor/review/{review_id}/decision` | 更新审阅决策 |
| POST | `/supervisor/score-calibration` | 提交评分校准 |
| POST | `/supervisor/retraining-task` | 创建复训任务 |
| POST | `/supervisor/retraining-task/{task_id}/start` | 启动复训 |
| POST | `/supervisor/retraining-task/{task_id}/complete` | 完成复训 |

---

## 10. Curriculum Practice 课程考核系统

`backend/src/curriculum_practice/` 提供结构化课程考核，是近期新增的独立领域。

### 10.1 模块结构

| 子模块 | 职责 |
|--------|------|
| `services/examiner_agents.py` | Examiner Agent（考官）CRUD + 发布门禁 |
| `services/learning_contents.py` | 学习内容管理 |
| `services/learning_path.py` | 学习路径编排 |
| `services/learning_progress_service.py` | 学习进度追踪 |
| `services/test_bank.py` | 题库管理 + 题目生成 |
| `services/question_generation.py` | AI 辅助出题 |
| `services/practice_templates.py` | 演练模板管理 |
| `services/content_assets.py` | 内容资产管理 |
| `services/learner_profiles.py` | 学员画像 |
| `services/publishing_gates.py` | 发布门禁审批 |
| `services/session_snapshots.py` | 考核会话快照 |
| `services/voice_clone.py` | 声音克隆 |
| `websocket/examiner_runtime.py` | 考核运行时（WebSocket） |

### 10.2 Examiner Agent

考官 Agent 定义考核场景的配置：

- 关联评分规则集（ScoringRuleset）
- 题库绑定（QuestionItem 定义题干/参考标准/评分方式）
- 发布门禁：draft → pending_review → published → archived
- `PublishGateDecision`：发布前的合规检查结果

### 10.3 WebSocket 考核运行时

`examiner_runtime.py` 实现考核会话的实时交互：

- `FrozenExamQuestion`：题目在考核开始时冻结（防中途修改）
- `ExamScorer` protocol：评分策略注入接口（默认基于关键词覆盖）
- `ExamCompletionWriter` protocol：完成回调（写入评分结果）
- 会话状态管理：question → answer → score → next

### 10.4 学习路径

学习路径编排从 `learning_path.py` 管理，支持：

- 内容 → 学习 → 演练/考核 的完整学习流
- 进度追踪（`LearningProgressService`）
- 与 `curriculum_analytics/` 配合提供课程分析

### 10.5 管理与用户 API

- 管理端：`admin/curriculum-practice/` 下管理 Examiner Agent、内容资产、模板
- 用户端：`/api/v1/curriculum/learning-path` 查看路径，`/api/v1/curriculum/study` 学习内容

---

## 11. Prompt Templates 提示词系统

`backend/src/prompt_templates/` 提供提示词的全生命周期管理。

### 11.1 系统架构

```text
PromptTemplate (存储)
    ↓
Loader (从 DB + 文件系统加载)
    ↓
Renderer (变量替换 → 最终 prompt)
    ↓
CompiledContract (编译契约，版本 hash)
    ↓
PromptTemplateService (编排 + 治理)
```

### 11.2 核心概念

- **PromptType**：提示词类型分类（evaluation、report、stage、scoring、realtime_scoring 等）
- **ScenarioPrompt**：场景特定的提示词绑定（一个场景可以绑定多个提示词类型）
- **CompiledPromptContract**：编译后的提示词契约，包含版本 hash 和诊断信息
- **治理机制**：提示词变更记录审计日志，支持回滚。变更时触发 `PROMPT_GOVERNANCE_AUDIT_ACTION`

### 11.3 业务规则

- 销售场景只允许特定提示词类型（`SALES_PROMPT_SCOPE_ALLOWED_TYPES`）
- 渲染时支持变量替换（`render_template()`）
- 管理后台提供编辑、版本对比、回滚界面

---

## 12. Business Rules & Growth Center

### 12.1 业务规则系统

`backend/src/common/business_rules/` 提供可配置的业务规则引擎：

| 规则领域 | 配置键 | 说明 |
|---------|--------|------|
| 销售话术组合规则 | `sales_combination_rules` | 销售策略组合配置 |
| Objection Ledger | `objection_ledger_rules` | 异议处理台账规则 |
| AI 教练规则 | `ai_coach_rules` | 教练行为规则 |
| 成长成就规则 | `achievement_rules` | 成就达成条件 |
| 下一次练习推荐 | `next_practice_rules` | 推荐算法参数 |

规则通过 `BusinessRuleConfigService` CRUD，支持草稿 → 发布的版本管理。

### 12.2 Growth Center

`backend/src/common/growth/` 提供用户成长中心：

- **Achievement**：成就系统，基于规则集触发
- **UserGoal**：用户目标管理
- **Notification**：通知推送
- **AICoachRules**：AI 教练行为配置
- **SafetyPolicies**：安全策略（防止滥用）
- **NextPractice**：基于表现的练习推荐算法

### 12.3 Objection Ledger

异议处理台账是销售对练特有的反馈机制，在演练过程中记录用户对异议的处理情况，包含：

- 异议类型识别（roi_proof / price_pressure / competitor_alternative / implementation_risk）
- 处理质量评估（evidence_gap / objection_handling_gap）
- 与 Scoring 系统联动，影响评分维度

---

## 13. Config Bundles 配置域版本管理

`backend/src/admin/config_bundles/` 提供配置域的版本化生命周期管理。

### 13.1 体系结构

```text
DomainRegistry (领域定义)
    ↓
ConfigBundle (配置域 + 当前版本)
    ↓
ConfigVersion (具体版本内容)
    ↓
ConfigBundleLifecycleService (生命周期管理)
    ↓
ConfigBundleAdapter (适配器: 旧配置 → bundle 格式)
```

### 13.2 领域定义

预注册的配置域（`DOMAIN_REGISTRY`）：

| 域名 | 说明 | 迁移状态 |
|------|------|---------|
| `training_content` | 训练内容 | not_started |
| `customer_simulation` | 客户模拟 | not_started |
| `scoring` | 评分 | read_only |
| `coach_behavior` | 教练行为 | not_started |
| `voice_policy` | 语音策略 | read_only |
| `knowledge_grounding` | 知识接地 | not_started |

### 13.3 生命周期

```
create_draft → preview → publish → deprecate
                        ↓
                  ConfigVersion 冻结
                        ↓
                  ConfigBundleAuditLog 记录
```

每次发布生成新的 ConfigVersion，旧版本不删除。AuditLog 记录 before/after snapshot、操作人、原因。

---

## 14. Agent 平台

Agent 平台提供演练场景的声明式配置和管理：

- **Agent**：一个完整的演练场景定义，包含 Persona、Capabilities、Knowledge 等
- **Persona**：AI 角色的性格、语气、知识策略配置（通过 `persona_policy.py` 治理）
- **Capability**：可插拔的能力模块：

| Capability | 职责 |
|-----------|------|
| `ASR` | 语音识别 |
| `TTS` | 语音合成 |
| `LLM` | 语言模型推理 |
| `RealtimeScoring` | 实时评分 |
| `FuzzyDetection` | 模糊/敷衍回答检测 |
| `SalesStage` | 销售阶段识别 |
| `KnowledgeRetrieval` | 知识检索 |

- **CapabilityRunner**：按顺序编排执行能力链
- **Persona Migration**：`migrations/migrate_persona_policy.py` 支持 persona 配置的迁徙

Agent 管理 API 位于 `backend/src/agent/`，面向管理员。

---

## 15. 前端架构

### 15.1 路由分组

```
(app)/auth/       → 登录/密码重置
(app)/dashboard/  → 用户仪表盘、训练入口、历史、排行榜
(app)/user/       → 演练会话(Practice)、学习路径(Study)、考核(Exam)、报告、回放
admin/            → 全功能管理后台（Agent/Prompt/Knowledge/User/Scoring/ Analytics 等）
```

### 15.2 演练页面状态机

`use-practice-session-lifecycle.ts` 和 `use-recording-state-machine.ts` 管理复杂的前端演练状态：

```
初始化 → 连接 WS → 开始演练 → 录制中 → 暂停/继续 → 结束 → 报告页
```

关键 hook：
- `use-practice-websocket.ts`：WebSocket 连接管理，消息分发
- `use-examiner-websocket.ts`：考核专用 WebSocket 连接
- `use-audio-recorder.ts`：音频录制与 PCM 编码
- `use-recording-state-machine.ts`：录音状态机
- `use-continuous-audio-uploader.ts`：连续音频上传
- `use-streaming-audio-player.ts`：流式音频播放
- `use-training-preferences.ts`：训练偏好（语速、音色等）

### 15.3 错误边界

根组件和演练页面分别包裹 `ErrorBoundary` 和 `ClientErrorBoundary`。所有错误以状态指示器形式展示，禁止弹窗报错。

### 15.4 关键组件

- `components/practice/`：演练 UI（PPT SlideViewer、PageNavigator、ScorePanel、实时反馈）
- `components/highlights/`：高光时刻选择与展示
- `components/analytics/`：排行榜、趋势图、评分分布
- `components/layout/`：后台管理 shell、侧边栏
- `components/ui/`：通用 UI（GlassCard、GlassModal、ChatBubble 等）

---

## 16. 核心实体关系

```text
TrainingTask 1──0..N PracticeSession 1──0..N ConversationMessage
                                   │
                                   1──0..1 EvaluationRun 1──0..1 TrainingReportSnapshot
                                   │
                                   1──0..N ScoreSnapshot
                                   │
                                   0..N SupervisorReview 1──N SupervisorScoreCalibration
                                                           1──0..N RetrainingTask (复训)
                                   │
                                   0..N KnowledgeRetrievalRecord
```

| 实体 | 说明 |
|------|------|
| `User` | 用户（admin/user/support 角色） |
| `Agent` | 演练场景配置 |
| `Persona` | AI 角色配置（含语气/知识策略） |
| `Scenario` | 场景定义（sales/presentation） |
| `PracticeSession` | 训练会话（运行时主语） |
| `ConversationMessage` | 对话消息（AI 和用户） |
| `StageEvaluationResult` | 阶段评估结果 |
| `EvaluationRun` | 评估运行结果（链接 config_bundle） |
| `TrainingReportSnapshot` | 不可变报告快照 |
| `TrainingTask` | 训练任务（分配/复训） |
| `RetrainingTask` | 主管复训任务（与 TrainingTask 独立） |
| `SupervisorReview` | 主管审阅记录 |
| `SupervisorScoreCalibration` | 评分校准（按维度调整） |
| `ScoreSnapshot` | 评分快照 |
| `ScoringRuleset` | 评分规则集（版本化） |
| `ConfigBundle` | 配置域版本管理 |
| `KnowledgeBase` | 知识库集合 |
| `KnowledgeDocument` | 知识文档（分块后） |
| `PromptTemplate` | 提示词模板 |
| `ScenarioPrompt` | 场景提示词绑定 |
| `ExaminerAgent` | 考官 Agent 配置 |
| `QuestionItem` | 题库题目（含参考标准） |
| `LearningContent` | 学习内容 |
| `Achievement` | 成就定义 |
| `UserGoal` | 用户目标 |
| `BusinessRuleConfig` | 业务规则配置 |

---

## 17. 模块边界

| 目录 | 领域 | 允许依赖 |
|------|------|---------|
| `common/` | 共享平台层 | 三方库 |
| `presentation_coach/` | PPT 演练 | `common/` |
| `sales_bot/` | 销售对练 | `common/` |
| `evaluation/` | 评估引擎 | `common/` + `prompt_templates/` |
| `agent/` | Agent 平台 | `common/` |
| `admin/` | 管理后台 | `common/` |
| `supervisor/` | 主管审核 | `common/` + `evaluation/` |
| `prompt_templates/` | 提示词系统 | `common/ai/` |
| `curriculum_practice/` | 课程考核 | `common/` + `evaluation/` |
| `curriculum_analytics/` | 课程分析 | `common/` |
| `training_runtime/` | 运行时主语 | `common/` |
| `support/` | 运维支撑 | `common/` |
| `common/effectiveness/` | 评估框架核心 | `common/` |
| `common/growth/` | 成长中心 | `common/` |
| `common/knowledge_engine/` | 知识问答引擎 | `common/` |
| `common/business_rules/` | 业务规则引擎 | `common/` |

**禁止**：
- `presentation_coach/` 和 `sales_bot/` 互不引用
- 跨域访问其他模块的 DB 模型（只能通过 `common/db/models.py` 访问）
- 场景特定字段泄露到共享实体

---

## 18. 配置分层

```text
运行时数据库配置 (DB config_manager / ConfigBundle)
        ↓ 优先
ConfigBundle 版本化配置
        ↓
环境变量 (.env)
        ↓
代码默认值
```

- 敏感字段（API Key、secret）使用 Fernet 加密存储
- ConfigManager 启动时加载默认配置，运行时支持热更新
- ConfigBundle 提供版本管理：create_draft → publish → deprecate
- BusinessRuleConfig 提供业务规则的独立版本管理

---

## 19. 部署架构

```text
Nginx/反向代理
    ↓
FastAPI (uvicorn, 端口 3444)
    ├── PostgreSQL (状态/配置/记录)
    ├── Redis (缓存/会话)
    ├── ChromaDB (向量存储)
    └── 外部服务
        ├── DashScope API (ASR/LLM)
        ├── StepFun API (实时语音)
        └── 企业微信 SSO
    ↓
Next.js (端口 3445)
```

---

## 20. 可观测性

- **结构化日志**：JSON 格式，所有日志包含 `trace_id`，敏感字段脱敏
- **Prometheus 指标**：请求计数、延迟分布、降级触发次数、KB Lock 决策
- **OpenTelemetry**：链路追踪（通过 `initialize_otel` 启动）
- **健康检查**：`/health` 查询数据库就绪状态
- **NFR 报告**：`nfr_reporter.py` 生成非功能性需求验证报告
- **系统日志**：`admin/api/system_logs.py` 提供管理后台日志查看

---

## 21. 关键 ADR

| ADR | 决策 |
|-----|------|
| `2026-03-14-training-runtime-subject` | 运行时主语收敛为 `training_scenario_runtime` |
| `2026-04-21-growth-deferred-slices` | 成长中心延迟发布切片 |
| `2026-04-24-scoring-ruleset-governance` | 评分规则集采用版本化治理 |
| `2026-04-27-local-venv-repair-policy` | 本地虚拟环境修复策略 |
| `2026-04-27-python-runtime-policy` | Python 运行时策略 |
| `2026-05-11-architecture-boundary-domain-contract` | 领域边界与契约锁定（PRD #23） |
| `2026-05-11-curriculum-practice-boundary-contract` | 课程考核模块边界契约 |
| `2026-05-12-case-item-role-profile-pilot-contract` | 案例/角色/画像试点契约 |

详见 `docs/adr/`。

---

## 22. 与相关文档的关系

| 文档 | 关系 |
|------|------|
| `docs/api-contract/` | 本架构文档描述模块和链路，API 契约文档描述具体端点的请求/响应 |
| `docs/adr/` | 本架构文档记录当前状态，ADR 记录决策过程和理由 |
| `docs/setup/` | 本架构文档描述系统结构，setup 文档描述如何部署和配置 |
| `docs/backup-recovery-runbook.md` | 灾备恢复的操作手册 |
| `docs/agents/` | Agent 工作指南（issue-tracker、triage-labels、domain） |
| `CLAUDE.md` | 项目概览、开发命令和约束 |
| `AGENTS.md` | Agent 协作行为准则 |
