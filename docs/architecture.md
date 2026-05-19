# 系统架构

企业级 AI 智能演练系统的架构文档。描述整体架构、核心模块、关键数据流和设计原则。

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        AI Practice System                          │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │   Auth   │  │   Admin      │  │   User Facing                │  │
│  │  ─────── │  │  ─────────   │  │  ──────────                  │  │
│  │ SharedPW │  │ Agents       │  │ Dashboard / Training         │  │
│  │ WeCom SSO│  │ Personas     │  │ Practice Session             │  │
│  │ JWT      │  │ Knowledge    │  │ Session Report               │  │
│  │          │  │ Prompts      │  │ Replay                       │  │
│  │          │  │ Scoring      │  │ Learning Path                │  │
│  │          │  │ Users/Record │  │                              │  │
│  └──────────┘  └──────────────┘  └──────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    WebSocket Layer (3 routes)                 │  │
│  │                                                              │  │
│  │  /ws/presentation    /ws/sales/*    /ws/curriculum/examiner   │  │
│  │       │                  │                   │               │  │
│  │  ┌────┴────┐     ┌──────┴──────┐     ┌──────┴──────┐        │  │
│  │  │ PPT     │     │ Sales       │     │ Curriculum  │        │  │
│  │  │ Coach   │     │ Training    │     │ Examiner    │        │  │
│  │  │ Handler │     │ Handler(s)  │     │ Handler     │        │  │
│  │  └─────────┘     └─────────────┘     └─────────────┘        │  │
│  │                                                              │  │
│  │  All extend BaseWebSocketHandler with:                       │  │
│  │  - async message queue (backpressure)                        │  │
│  │  - heartbeat (30s timeout)                                   │  │
│  │  - session state save/restore (reconnection)                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Voice Runtime                              │  │
│  │                                                              │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │  │
│  │  │  Legacy      │    │  StepFun     │    │  TTS Chain   │   │  │
│  │  │  ASR→LLM→TTS│    │  Realtime    │    │              │   │  │
│  │  │  pipeline    │    │  dual-track  │    │  Aliyun →    │   │  │
│  │  │              │    │  speech      │    │  Edge →      │   │  │
│  │  │              │    │              │    │  Browser     │   │  │
│  │  └──────────────┘    └──────────────┘    └──────────────┘   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Evaluation & Scoring                       │  │
│  │                                                              │  │
│  │  SessionEvidence → EvaluationRun → TrainingReportSnapshot    │  │
│  │       ↑              ↑                          ↑           │  │
│  │   Conversation   Scoring Rulesets           Config Bundle    │  │
│  │   Messages       + Effectiveness           Snapshot (frozen) │  │
│  │   (stages)       + Staged Triggers                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Knowledge Layer                            │  │
│  │                                                              │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐   │  │
│  │  │ KB Lock    │  │ Knowledge    │  │ KnowledgeAnswer   │   │  │
│  │  │ Guard      │  │ Service      │  │ Engine (Haystack)  │   │  │
│  │  │ (strict    │  │ (ChromaDB    │  │                    │   │  │
│  │  │  grounding) │  │  ingestion)  │  │ Intent→Retrieval→ │   │  │
│  │  │            │  │              │  │ Rerank→Assemble   │   │  │
│  │  └────────────┘  └──────────────┘  └────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Agent Platform                             │  │
│  │                                                              │  │
│  │  Agent → Persona → Capabilities (ASR/TTS/LLM/Scoring)       │  │
│  │  CapabilityRunner chains: FuzzyDetection → RealtimeScoring  │  │
│  │                              → SalesStage → KnowledgeRetrieval│  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. 架构概览

系统采用**模块化单体**架构，后端 Python/FastAPI 提供 REST API 和 WebSocket 端点，前端 Next.js/React 提供 Web UI。两个核心演练场景（PPT 演练、销售对练）独立部署在同一个应用中，通过 `backend/src/presentation_coach/` 和 `backend/src/sales_bot/` 模块隔离。

### 1.1 设计原则

- **场景隔离**：两核心场景禁止互相引用，共享逻辑放入 `common/` 模块
- **降级优先**：所有外部依赖（TTS、ASR、LLM）必须有降级链，不以弹窗报错中断用户体验
- **驱动配置化**：运行时配置从数据库读取，支持热更新，无需重启
- **严格接地**：KB Lock 确保 AI 回答必须基于知识库，禁止臆测
- **不可变报告**：TrainingReportSnapshot 在生成时冻结配置版本，历史报告永不重算

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
3. 注册 HTTP 路由（约 40 个子路由）
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
- **共享口令**：静态 `AUTH_SHARED_PASSWORD`，适用于受控环境
- **用户覆盖**：`AUTH_USER_PASSWORDS_JSON` 按账号设定独立口令
- **企业微信 SSO**：WeCom OAuth 登录

所有登录颁发 JWT，前后端通过 cookie 或 Authorization header 传递。CSRF 保护对所有非豁免路径强制验证。

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
检查 KB Lock 绑定状态（presentation 专有）
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
| `/ws/sales/{session_id}` | 销售对练 | `StepFunRealtimeHandler` 等 | StepFun Realtime 协议 |
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

---

## 4. 语音运行时

### 4.1 两种模式

系统支持两种语音运行时模式，在会话级别通过 `voice_mode` 字段选择：

| 模式 | 架构 | 适用场景 |
|------|------|---------|
| `legacy` | ASR → LLM → TTS 串行管道 | 浏览器兼容性优先 |
| `stepfun_realtime` | StepFun 端到端语音模型，双轨语音流 | 低延迟实时体验 |

**StepFun Realtime 模式**（默认模式）：
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

### 4.3 ASR

- **阿里云 ASR**：基于 DashScope 的实时语音识别
- **本地 ASR**：开发/测试环境使用的本地替代方案
- 自动降级：主服务失败时切换备用

---

## 5. 知识层

### 5.1 知识服务 (ChromaDB)

`KnowledgeService` 提供文档上传、分块、向量化和检索的完整链路：

```
文档上传 → 分块处理 → Embedding → ChromaDB 存储
                                  ↓
用户查询 → 向量检索 + BM25 混合检索 → 排序 → 结果
```

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

**coach_mode**：一个宽松模式，当检索不足时不阻止回答，但给出严格的 prompt 约束（"禁止编造具体产品事实"）。

### 5.3 知识问答引擎 (KnowledgeAnswerEngine, Haystack)

```text
用户问题
    ↓
IntentClassifier → 问题意图分类
    ↓
EntityResolver → 实体解析（产品名、版本号等）
    ↓
RetrievalPlanner → 多源检索规划
    ↓
HaystackAdapter → Haystack 管道执行
    ↓
CrossEncoderReranker → 重排序
    ↓
AnswerabilityEvaluator → 可回答性评估 (grounded/partial/ungrounded/blocked)
    ↓
Assembler → 组装 final 答案
    ↓
OutputGuard → partial 模式下裁剪未支持的断言
```

设计为插件化架构，每个阶段可独立配置和替换（RAG Profile）。

---

## 6. 评估与评分

### 6.1 数据流

```text
对话消息 → Stage Detection (触发词/轮次/时间)
    ↓
StageEvaluation (LLM 按阶段配置评估)
    ↓
EvaluationRun (持久化评估结果)
    ↓
SessionEvidence (证据投影)
    ↓
TrainingReportSnapshot (配置冻结 + 报告固化)
```

### 6.2 触发式阶段评估

`staged_evaluation.py` 实现分阶段评估：

- **阶段配置**：每个 stage 定义评估提示词类型和触发器
- **触发器类型**：关键词触发、阶段转移、时间间隔、轮次数
- **评估方式**：LLM 基于配置的 prompt 评分，返回 strengths/weaknesses/suggestions

### 6.3 评分规则集

`scoring_rulesets.py` 提供可配置的评分规则系统，与 `ConfigBundle` 关联。评分规则集定义维度、权重、通过阈值，并支持版本管理。

### 6.4 不可变报告

`TrainingReportSnapshotService.ensure_snapshot()`：

- 首次调用创建报告快照，重复调用幂等（返回同一快照）
- 快照包含：`config_bundle_snapshot`、`ruleset_version`、`score_basis`、`evidence_completeness`
- 旧报告（v1 时代）标记为 `legacy_unversioned`
- 不可评估的 session 记录 `non_evaluable_reason`，不给伪分

### 6.5 教练评分

`RealtimeScoringCapability` 在演练运行时实时生成评分。`FuzzyDetectionCapability` 检测模糊/敷衍回答。

---

## 7. 训练运行时

### 7.1 统一运行时主语

`TrainingRuntimeDescriptor` 是所有训练会话的标准描述符：

```text
subject: training_scenario_runtime  (固定值)
session_id: str
scenario_type: "sales" | "presentation"
agent_id: str | None
persona_id: str | None
presentation_id: str | None
voice_mode: str | None
runtime_profile_id: str | None
focus_intent: dict | None
training_task_id: str | None
```

确保所有下游模块使用一致的语言引用运行时，避免场景分支判断。

### 7.2 训练任务体系

| 实体 | 归属 | 职责 |
|------|------|------|
| `TrainingTask` | `common/` | 训练组织的最小调度单位，状态机：assigned→in_progress→completed |
| `RetrainingTask` | `supervisor/` | 主管判定 needs_retraining 后的二次训练任务 |
| `PracticeSession` | `common/` | 一次训练运行的物理承载，包含 state、时间线 |

**生命周期控制**（`SessionLifecycleService`）：
- REST API 端点支持外部触发状态迁移（开始/暂停/恢复/强制完成）
- 状态迁移通过 WebSocket 的 `sync_lifecycle_transition` 同步给运行中 handler

---

## 8. Agent 平台

Agent 平台提供演练场景的声明式配置和管理：

- **Agent**：一个完整的演练场景定义，包含 Persona、Capabilities、Knowledge 等
- **Persona**：AI 角色的性格、语气、知识策略配置
- **Capability**：可插拔的能力模块（ASR、TTS、LLM、Scoring、FuzzyDetection、SalesStage、KnowledgeRetrieval）
- **CapabilityRunner**：按顺序编排执行能力链

Agent 管理 API 位于 `backend/src/agent/`，面向管理员。

---

## 9. 前端架构

### 9.1 路由分组

```
(app)/auth/       → 登录/密码重置
(app)/dashboard/  → 用户仪表盘、训练入口、历史、排行榜
(app)/user/       → 演练会话、学习路径、报告、回放
admin/            → 全功能管理后台
```

### 9.2 演练页面状态机

`use-practice-session-lifecycle.ts` 和 `use-recording-state-machine.ts` 管理复杂的前端演练状态：

```
初始化 → 连接 WS → 开始演练 → 录制中 → 暂停/继续 → 结束 → 报告页
```

### 9.3 错误边界

根组件和演练页面分别包裹 `ErrorBoundary` 和 `ClientErrorBoundary`。所有错误以状态指示器形式展示，禁止弹窗报错。

---

## 10. 核心实体关系

```text
TrainingTask 1──0..N PracticeSession 1──0..N ConversationMessage
                                   │
                                   1──0..1 EvaluationRun 1──0..1 TrainingReportSnapshot
                                   │
                                   1──0..N KB Retrieval Record
                                   │
                                   0..1 ScoreSnapshot
```

| 实体 | 说明 |
|------|------|
| `User` | 用户（admin/user/support 角色） |
| `Agent` | 演练场景配置 |
| `Persona` | AI 角色配置 |
| `Scenario` | 场景定义（sales/presentation） |
| `PracticeSession` | 训练会话（运行时主语） |
| `ConversationMessage` | 对话消息（AI 和用户） |
| `EvaluationRun` | 评估运行结果 |
| `TrainingReportSnapshot` | 不可变报告快照 |
| `TrainingTask` | 训练任务（分配/复训） |
| `RetrainingTask` | 主管复训任务 |
| `ScoreSnapshot` | 评分快照 |
| `KnowledgeBase` | 知识库集合 |
| `KnowledgeDocument` | 知识文档（分块后） |

---

## 11. 模块边界

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
| `support/` | 运维支撑 | `common/` |

**禁止**：
- `presentation_coach/` 和 `sales_bot/` 互不引用
- 跨域访问其他模块的 DB 模型（只能通过 `common/db/models.py` 访问）
- 场景特定字段泄露到共享实体

---

## 12. 配置分层

```text
运行时数据库配置 (DB config_manager)
        ↓ 优先
环境变量 (.env)
        ↓
代码默认值
```

- 敏感字段（API Key、secret）在数据库中使用 Fernet 加密
- ConfigManager 启动时加载默认配置，运行时支持热更新
- 配置变更通过 ConfigBundle 版本管理追踪

---

## 13. 部署架构

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

## 14. 可观测性

- **结构化日志**：JSON 格式，所有日志包含 `trace_id`，敏感字段脱敏
- **Prometheus 指标**：请求计数、延迟分布、降级触发次数、KB Lock 决策
- **OpenTelemetry**：链路追踪（通过 `initialize_otel` 启动）
- **健康检查**：`/health` 查询数据库就绪状态
- **NFR 报告**：`nfr_reporter.py` 生成非功能性需求验证报告

---

## 15. 关键 ADR

| ADR | 决策 |
|-----|------|
| `2026-03-14-training-runtime-subject` | 运行时主语收敛为 `training_scenario_runtime` |
| `2026-04-24-scoring-ruleset-governance` | 评分规则集采用版本化治理 |
| `2026-05-11-architecture-boundary-domain-contract` | 领域边界与契约锁定 |
| `2026-05-11-curriculum-practice-boundary-contract` | 课程考核模块边界契约 |
| `2026-05-12-case-item-role-profile-pilot-contract` | 案例/角色/画像试点契约 |

详见 `docs/adr/`。

---

## 16. 与相关文档的关系

| 文档 | 关系 |
|------|------|
| `docs/api-contract/` | 本架构文档描述模块和链路，API 契约文档描述具体端点的请求/响应 |
| `docs/adr/` | 本架构文档记录当前状态，ADR 记录决策过程和理由 |
| `docs/setup/` | 本架构文档描述系统结构，setup 文档描述如何部署和配置 |
| `docs/backup-recovery-runbook.md` | 灾备恢复的操作手册 |
| `CLAUDE.md` | 项目概览、开发命令和约束 |
