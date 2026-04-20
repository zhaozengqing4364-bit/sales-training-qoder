# 项目审查报告：Enterprise AI Intelligent Practice System

**审查日期**：2026-04-14
**审查分支**：gsd/M001/S04
**审查方法**：基于代码证据的静态审查 + 构建/测试验证

---

# 1. 项目总体判断

## 技术栈
- **前端**：Next.js 16.2.3 + React 19.2.3 + TypeScript 5 + Tailwind CSS 4 + Zustand + TanStack Query + Recharts
- **后端**：FastAPI + SQLAlchemy 2.0 + Pydantic 2.0 + Alembic（数据库迁移）+ PostgreSQL/SQLite + Redis + ChromaDB
- **AI/语音**：StepFun Realtime API、阿里云 DashScope（ASR/TTS）、Edge-TTS、FunASR
- **测试**：pytest（后端）、vitest（前端）
- **部署**：Docker Compose

## 核心模块
1. **Agent 平台**（agent/）— 智能体、角色管理
2. **销售对练**（sales_bot/）— WebSocket 实时语音对话
3. **PPT 演练**（presentation_coach/）— PPT 上传、解析、演讲陪练
4. **管理后台**（admin/）— 用户、数据、配置、日志
5. **公共基础设施**（common/）— 鉴权、数据库、错误处理、监控
6. **评估系统**（evaluation/）— 分阶段评估、综合报告

## 当前真实完成度判断
系统呈现出**"前端页面高度完整、后端 API 框架完整、核心业务流程基本打通，但认证层是 mock、测试覆盖极低、构建存在类型错误"**的特征。
代码量不能代表完成度：后端 239 个 Python 文件、核心服务层 13,893 行，前端 39 个页面，但测试覆盖率仅 11%，前端无法通过生产构建，WeChat 企微登录仍是 mock。
**从"真实可工作的业务闭环"角度判断，系统约为 55%–60% 真实完成度**，而非表面代码量暗示的 70%+。

## 当前系统最主要的 3~5 个风险
1. **P0 — 前端生产构建失败**：`web/src/app/(dashboard)/page.tsx:440` 存在 Button `variant="default"` 类型不兼容错误，直接阻塞构建和部署。
2. **P0 — 企微 SSO 是 mock 实现**：`backend/src/common/auth/service.py` 明确标记 "For now, this is a mock implementation" 和 "TODO: Implement actual WeChat SSO API call"。若目标环境需要真实企微登录，这是上线阻塞项。
3. **P1 — 测试体系形同虚设**：后端 pytest 因环境缺失 `jwt` 模块（PyJWT）无法收集测试；历史覆盖率报告显示整体仅 11%。无法依赖测试保障回归。
4. **P1 — 错误处理模式混用**：虽然项目宪法要求使用 `Result[T]`，但大量 API 层（如 `backend/src/agent/api/agents.py`、`backend/src/admin/api/voice_runtime.py`）仍直接 `raise HTTPException`，导致前后端错误契约不一致。
5. **P2 — WebSocket 实时链路复杂度极高**：`backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 达 4,569 行，集成上游 StepFun Realtime、知识检索、TTS 降级、中断检测、会话状态恢复等多重逻辑，是潜在的稳定性热点，但目前缺乏充分的集成测试覆盖。

## 是否适合进入联调
**基本适合，但有前置条件**。
- 前后端主要 CRUD 接口已对齐，Agent/Persona/PPT/知识库/练习会话等链路可联调。
- **前置条件**：修复前端构建错误；确认登录使用 dev-login 还是必须完成企微 SSO。

## 是否适合进入测试
**不适合**。
- 测试无法运行（PyJWT 缺失），覆盖率 11%。
- 必须先修复测试环境、补齐核心链路测试，才能进入有意义的系统测试。

## 是否适合试上线
**不适合**。
- 前端构建失败 + 认证 mock + 测试缺失，不满足试上线的最低质量标准。

## 总体结论
这是一个**"页面和接口看起来很完整，但工程化基础设施薄弱"**的系统。核心业务功能（Agent 管理、销售对练、PPT 演练、报告生成）的代码框架已搭建完成，部分链路甚至相当精致（如前端练习页面的 UX、WebSocket 组件化设计）。然而，**构建、认证、测试这三根支柱存在明显缺口**，导致系统目前处于"演示可用、生产不稳"的状态。建议优先修复 P0 阻塞项，再补齐 P1 测试与契约一致性，最后进入联调和系统测试。

---

# 2. 系统模块完成度表

| 模块名 | 模块职责 | 当前状态 | 关键证据 | 存在问题 | 风险等级 | 备注 |
|--------|---------|---------|---------|---------|---------|------|
| **前端构建系统** | Next.js 编译、类型检查、打包 | 表面实现但未打通 | `web/package.json` 依赖 Next.js 16.2.3；`npm run build` 失败 | `web/src/app/(dashboard)/page.tsx:440` Button `variant="default"` 不被 `Button` 组件接受，类型检查失败 | P0 | 阻塞任何生产部署 |
| **用户认证/登录** | JWT 鉴权、企微 SSO、Cookie/CSRF | 部分实现 | `backend/src/common/auth/service.py` 完整实现了 JWT、Cookie、CSRF、密码校验 | 第 24–25 行明确注释 "For now, this is a mock implementation" 和 "TODO: Implement actual WeChat SSO API call" | P0 | dev-login 可用，真实 SSO 未接 |
| **Agent 管理** | 智能体 CRUD、发布/归档 | 已实现且基本可用 | `backend/src/agent/api/agents.py` 实现 create/list/get/update/delete/publish/archive/unpublish；`web/src/app/admin/agents/page.tsx` 完整对接 | 无严重功能缺失；API 仍混用 HTTPException | P2 | 前后端闭环完整 |
| **Persona 管理** | 角色配置、难度、策略 | 已实现且基本可用 | `backend/src/agent/api/personas.py`；`web/src/app/admin/personas/page.tsx` | 无明显断点 | P2 | 与 Agent 联动可用 |
| **PPT 演练** | PPT 上传、OCR、页级要点、演讲练习 | 已实现且基本可用 | `backend/src/presentation_coach/api/presentations.py`；`backend/src/presentation_coach/services/coach_service.py`；`web/src/app/(user)/practice/[sessionId]/page.tsx` 支持 presentation 模式 | 无严重功能缺失 | P2 | 上传解析链路完整 |
| **销售对练 (Legacy)** | ASR→LLM→TTS 管道式对话 | 已实现且基本可用 | `backend/src/sales_bot/services/bot_service.py` 使用 LangChain ConversationChain 实现基础对话 | 实现较浅（固定 persona prompt + ConversationChain），无复杂销售阶段追踪 | P2 | 可用但智能化程度有限 |
| **销售对练 (Realtime)** | StepFun Realtime 双轨语音 | 部分实现 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 达 4,569 行，组件化拆分完整 | 代码量巨大，集成点过多，缺乏性能/稳定性测试覆盖 | P1 | 架构完整但需大量实战验证 |
| **练习页面/前端** | WebSocket 连接、录音、实时面板、状态管理 | 已实现且基本可用 | `web/src/app/(user)/practice/[sessionId]/page.tsx` 896 行，功能非常完整 | 依赖 `usePracticeWebSocket`、`useAudioRecorder` 等 hooks，需确认后端契约一致性 | P2 | UX 完成度很高 |
| **报告/回放** | 会话回放、综合报告、分阶段评估 | 已实现且基本可用 | `backend/src/common/db/models.py` 有 `ComprehensiveReport`、`StagedEvaluationResult`；`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 和 `replay/page.tsx` | 评估算法质量需人工校验 | P2 | 数据表和页面均已存在 |
| **知识库** | 文档上传、向量检索、KB Lock | 已实现且基本可用 | `backend/src/common/knowledge/`；`web/src/app/admin/knowledge/page.tsx` | 无明显断点 | P2 | 与对话链路已打通 |
| **管理后台 — 数据分析** | 系统概览、趋势、排行榜、导出 | 已实现且基本可用 | `backend/src/admin/api/analytics.py`；`web/src/app/admin/analytics/page.tsx` 840 行 | 无严重功能缺失 | P2 | 前后端数据契约完整 |
| **管理后台 — 用户管理** | 用户 CRUD、角色变更、导出 | 已实现且基本可用 | `backend/src/admin/api/users.py`；`web/src/app/admin/users/page.tsx` | 无严重功能缺失 | P2 | 含审计日志记录 |
| **管理后台 — 系统设置** | 模型配置、语音运行时 | 已实现且基本可用 | `backend/src/admin/api/model_configs.py`、`voice_runtime.py`；`web/src/app/admin/settings/page.tsx` | 设置项较多，需验证变更是否实时生效 | P2 | 页面功能完整 |
| **管理后台 — 记录/日志** | 训练记录、系统日志 | 已实现且基本可用 | `backend/src/admin/api/training_records.py`、`system_logs.py`；`web/src/app/admin/records/page.tsx` | 无明显断点 | P2 | 查询和删除可用 |
| **测试体系** | 单元测试、集成测试、契约测试 | 表面实现但未打通 | `backend/tests/` 目录下有 50+ 个测试文件；`pytest --collect-only` 因 `ModuleNotFoundError: No module named 'jwt'` 失败 | 覆盖率历史报告仅 11%；核心服务大量 0% 覆盖 | P1 | 有测试代码但无法执行 |
| **数据库迁移** | Alembic schema 版本管理 | 已实现且基本可用 | `backend/alembic/versions/` 下有 34 个迁移文件 | 无严重问题 | P3 | 迁移历史完整 |
| **部署配置** | Docker Compose、CI/CD | 部分实现 | 根目录有 `docker-compose.yml`、`.github/workflows/` | 未在本次审查中验证容器内构建和运行 | P2 | 配置文件存在 |

---

# 3. 核心业务链路审查

## 链路 1：登录 / 认证

- **链路名称**：用户登录与鉴权
- **当前状态**：部分实现
- **已完成部分**：
  - JWT token 生成与校验（`backend/src/common/auth/service.py`）
  - Cookie + CSRF 防护完整实现
  - 开发模式 dev-login（`backend/src/main.py:344-377`）
  - 前端登录页（`web/src/app/(auth)/login/page.tsx`）
- **缺失部分**：
  - 真实企微 SSO 对接
- **断点位置**：`backend/src/common/auth/service.py:24-25`
- **断点原因**：代码注释明确说明是 mock 实现，TODO 标记未完成
- **关键证据**：
  - `backend/src/common/auth/service.py:24` — "For now, this is a mock implementation"
  - `backend/src/common/auth/service.py:25` — "TODO: Implement actual WeChat SSO API call"
- **风险判断**：P0（若目标用户通过企微登录，则此链路不可用于生产）

## 链路 2：Agent / Persona 管理

- **链路名称**：Agent 和 Persona 的 CRUD + 发布
- **当前状态**：已实现且基本可用
- **已完成部分**：
  - 后端 CRUD、发布/归档/取消发布（`backend/src/agent/api/agents.py`）
  - 前端列表、创建、删除、状态切换（`web/src/app/admin/agents/page.tsx`）
  - Persona 的独立管理和与 Agent 的关联（`backend/src/agent/api/personas.py`）
- **缺失部分**：
  - 无明显缺失
- **断点位置**：无
- **断点原因**：无
- **关键证据**：
  - `backend/src/agent/api/agents.py:68-315` 实现完整的 admin router
  - `web/src/app/admin/agents/page.tsx:74-163` 调用 `api.admin.getAgents/createAgent/deleteAgent/publishAgent` 等
- **风险判断**：P2（API 层仍混用 HTTPException，但不影响功能）

## 链路 3：练习会话创建 → WebSocket 连接 → 实时对话

- **链路名称**：销售对练 / PPT 演练的完整练习流程
- **当前状态**：已实现且基本可用
- **已完成部分**：
  - 会话创建 API（`backend/src/common/api/practice.py`）
  - 前端练习页面：WebSocket 连接、音频录制、状态管理、实时面板、暂停/结束（`web/src/app/(user)/practice/[sessionId]/page.tsx`）
  - Legacy 模式销售 bot（`backend/src/sales_bot/services/bot_service.py`）
  - StepFun Realtime 模式 handler（`backend/src/sales_bot/websocket/stepfun_realtime_handler.py`）
  - PPT 演练 coach service（`backend/src/presentation_coach/services/coach_service.py`）
- **缺失部分**：
  - StepFun Realtime 模式的端到端稳定性验证
  - 复杂销售阶段追踪在 Legacy 模式中未深度实现
- **断点位置**：无（功能代码完整）
- **断点原因**：无
- **关键证据**：
  - `web/src/app/(user)/practice/[sessionId]/page.tsx:62-895` 完整实现练习 UX
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:177-` StepFunRealtimeHandler 定义
  - `backend/src/common/api/practice.py:84-` 会话创建和生命周期管理
- **风险判断**：P1（Realtime 模式代码量巨大但缺乏测试，存在稳定性风险）

## 链路 4：会话结束 → 报告生成 → 回放

- **链路名称**：报告生成与回放查看
- **当前状态**：已实现且基本可用
- **已完成部分**：
  - 数据库表：`comprehensive_reports`、`staged_evaluation_results`、`conversation_messages`（`backend/src/common/db/models.py`）
  - 会话结束触发报告生成（`backend/src/common/api/practice.py`）
  - 回放 API（`backend/src/common/conversation/api/`）
  - 前端报告页和回放页（`web/src/app/(user)/practice/[sessionId]/report/page.tsx`、`replay/page.tsx`）
- **缺失部分**：
  - 评估算法的准确性需人工验证
- **断点位置**：无
- **断点原因**：无
- **关键证据**：
  - `backend/src/common/db/models.py:559-595` StagedEvaluationResult / ComprehensiveReport 模型
  - `backend/src/common/conversation/api/` 回放路由
- **风险判断**：P2（功能链路完整，算法质量待验证）

## 链路 5：PPT 上传 → 解析 → 演练

- **链路名称**：PPT 上传和演讲陪练
- **当前状态**：已实现且基本可用
- **已完成部分**：
  - PPT 上传 API（`backend/src/presentation_coach/api/presentations.py`）
  - PPT 解析服务（`backend/src/presentation_coach/services/ppt_parser.py`）
  - 页级要点和禁用词管理
  - 前端 PPT 管理页（`web/src/app/admin/presentations/page.tsx`）
- **缺失部分**：
  - 无明显缺失
- **断点位置**：无
- **断点原因**：无
- **关键证据**：
  - `backend/src/presentation_coach/services/coach_service.py:38-109` 创建 presentation 练习会话
  - `backend/src/presentation_coach/api/presentations.py` 上传路由
- **风险判断**：P2

## 链路 6：数据分析 / 排行榜

- **链路名称**：管理员查看系统数据、趋势、排行榜
- **当前状态**：已实现且基本可用
- **已完成部分**：
  - 后端 analytics service（`backend/src/common/analytics/admin_analytics_service.py`）
  - 前端数据分析页（`web/src/app/admin/analytics/page.tsx` 840 行）
  - 排行榜、趋势图、Agent 排名、导出
- **缺失部分**：
  - 无明显缺失
- **断点位置**：无
- **断点原因**：无
- **关键证据**：
  - `backend/src/admin/api/analytics.py:143-` overview/trends/agents/leaderboard/export 端点
  - `web/src/app/admin/analytics/page.tsx:86-161` 并发调用 7 个 API 加载数据
- **风险判断**：P2

---

# 4. 高优先级问题清单

## P0

### P0-1：前端生产构建因类型错误失败
- **问题标题**：Button variant="default" 类型不兼容导致 `next build` 失败
- **严重级别**：P0
- **所在模块**：前端 Dashboard 页面
- **所属业务链路**：用户首页/仪表盘
- **具体表现**：运行 `npm run build` 时，TypeScript 报错：`Type '"outline" | "default"' is not assignable to type '"primary" | "secondary" | "outline" | "ghost" | "danger" | "destructive" | undefined'`
- **为什么是问题**：任何生产构建和部署都无法进行
- **影响范围**：阻塞所有前端发布流程
- **代码证据**：`web/src/app/(dashboard)/page.tsx:440`
- **修复建议**：将 `variant="default"` 改为 `variant="primary"` 或更新 Button 组件类型定义

### P0-2：WeChat 企微 SSO 是 mock 实现
- **问题标题**：企业微信单点登录未真实对接，当前为 mock
- **严重级别**：P0
- **所在模块**：common/auth
- **所属业务链路**：登录/认证
- **具体表现**：`common/auth/service.py` 中的 WeChat 认证逻辑直接返回 mock 用户，不调用任何外部 SSO API
- **为什么是问题**：若系统目标环境是企业微信工作台，则登录链路在生产的根本不可用
- **影响范围**：所有用户登录、权限隔离、数据安全
- **代码证据**：`backend/src/common/auth/service.py:24-25` — "For now, this is a mock implementation" / "TODO: Implement actual WeChat SSO API call"
- **修复建议**：明确是否需要真实企微 SSO。若需要，接入企业微信 OAuth2 / JS-SDK；若暂不需要，需文档化并设置明确的完成里程碑。

## P1

### P1-1：后端测试无法运行，覆盖率仅 11%
- **问题标题**：pytest 因缺失 PyJWT 依赖无法收集测试，历史覆盖率仅 11%
- **严重级别**：P1
- **所在模块**：测试体系
- **所属业务链路**：全系统质量保证
- **具体表现**：`pytest --collect-only` 报错 `ModuleNotFoundError: No module named 'jwt'`；覆盖率报告显示大量核心模块 0% 覆盖，TOTAL 11%
- **为什么是问题**：没有可运行的测试意味着任何代码修改都无法进行回归验证，缺陷只能靠手工发现
- **影响范围**：全系统稳定性、后续迭代信心、上线评审
- **代码证据**：`pytest` 输出 "ModuleNotFoundError: No module named 'jwt'"；覆盖率报告 TOTAL 11%
- **修复建议**：1) 安装 `PyJWT`（已在 `requirements.txt` 中声明，检查虚拟环境）；2) 优先为核心链路（会话创建、WebSocket 连接、报告生成）补齐集成测试；3) 将测试通过纳入 CI 门禁

### P1-2：错误处理模式混用（HTTPException 与 Result[T]）
- **问题标题**：项目宪法要求使用 Result[T]，但 API 层大量直接 raise HTTPException
- **严重级别**：P1
- **所在模块**：多个 API 路由文件
- **所属业务链路**：全系统错误处理
- **具体表现**：`agent/api/agents.py`、`admin/api/voice_runtime.py` 等文件中，服务层返回 Result 后，路由层仍直接 `raise HTTPException(status_code=404/400, detail=...)`，导致前端收到的错误结构不一致
- **为什么是问题**：破坏宪法原则 I（用户体验永不中断）和统一错误契约，前端难以一致处理错误
- **影响范围**：所有 API 调用的错误处理逻辑
- **代码证据**：`backend/src/agent/api/agents.py:83-84` `raise HTTPException(status_code=400, detail=result.fallback)`；`backend/src/admin/api/voice_runtime.py:179` `raise HTTPException(status_code=400, detail=str(exc))`
- **修复建议**：统一将路由层的 HTTPException 替换为 `error_response()` 或 `build_server_error()` 返回，保持与 Constitution 一致

### P1-3：StepFun Realtime WebSocket Handler 过于庞大且缺乏测试
- **问题标题**：`stepfun_realtime_handler.py` 4,569 行，集成复杂度极高但测试覆盖不足
- **严重级别**：P1
- **所在模块**：sales_bot/websocket
- **所属业务链路**：销售对练实时对话
- **具体表现**：单个文件承担上游路由、事件分类、知识检索、TTS 降级、中断检测、会话恢复等十几项职责；虽有组件化拆分（components/ 目录），但主 handler 仍是超大体量
- **为什么是问题**：高复杂度 + 低测试覆盖 = 高概率生产故障；调试和迭代成本极高
- **影响范围**：销售对练核心体验、线上稳定性
- **代码证据**：`backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 4,569 行；`backend/tests/integration/test_sales_realtime_reconnect_flow.py` 等仅有少量集成测试
- **修复建议**：1) 将 handler 中更多逻辑下沉到独立 service；2) 为核心状态流转编写单元测试；3) 增加 StepFun Realtime 的端到端集成测试（含断网重连场景）

## P2

### P2-1：Sales Bot Service (Legacy) 实现较浅
- **问题标题**：Legacy 销售对练使用简单的 LangChain ConversationChain + 固定 prompt，缺乏深度销售能力
- **严重级别**：P2
- **所在模块**：sales_bot/services/bot_service.py
- **所属业务链路**：销售对练（Legacy 模式）
- **具体表现**：`bot_service.py` 仅使用 4 个固定 persona prompt 和 ConversationChain，没有利用 Agent 配置、知识库内容或销售阶段追踪来动态调整行为
- **为什么是问题**：产品宣称的"Agent 平台动态配置场景"在 Legacy 模式下未充分体现
- **影响范围**：Legacy 模式下的对话质量和场景可配置性
- **代码证据**：`backend/src/sales_bot/services/bot_service.py:54-75` 固定 prompt 字典；`process_user_input` 直接使用 chain.predict
- **修复建议**：让 Legacy 模式也能读取 Agent 的系统提示词、Persona 配置和知识库内容，提升与 Realtime 模式的能力对齐

### P2-2：前端 admin/settings 页面模型配置类型与后端可能不一致
- **问题标题**：settings 页面中大量模型配置类型在前端本地定义，未确认与后端 schema 同步
- **严重级别**：P2
- **所在模块**：web/admin/settings
- **所属业务链路**：系统设置
- **具体表现**：`web/src/app/admin/settings/page.tsx:45-108` 本地定义了 `ModelType`、`ModelProvider`、`ModelConfigItem` 等接口，而不是复用 `api/types.ts` 中的共享类型
- **为什么是问题**：后端 schema 变更时前端类型不会自动报错，容易引入运行时错误
- **影响范围**：系统设置页面的可维护性
- **代码证据**：`web/src/app/admin/settings/page.tsx:45-108` 本地类型定义
- **修复建议**：将模型配置相关类型统一收敛到 `web/src/lib/api/types.ts`，与后端 Pydantic schema 保持一致

## P3

### P3-1：代码中存在少量 mock/stub 注释
- **问题标题**：`common/auth/service.py` 和 `evaluation/services/staged_evaluation.py` 中存在 TODO/mock 标记
- **严重级别**：P3
- **所在模块**：auth、evaluation
- **所属业务链路**：认证、评估
- **具体表现**：`evaluation/services/staged_evaluation.py` 中有 `scenario_type="sales"  # TODO: parameterize`
- **为什么是问题**：不影响当前功能，但标记了未来扩展债务
- **影响范围**：局部
- **代码证据**：`backend/src/evaluation/services/staged_evaluation.py` TODO 注释
- **修复建议**：按计划参数化或清理注释

---

# 5. 架构与代码质量评价

## 模块边界是否清晰
**评价**：较好。
项目严格按场景拆分：`sales_bot/`、`presentation_coach/`、`agent/`、`admin/`、`common/`，彼此之间不直接引用，共享逻辑放在 `common/`。WebSocket handler 进一步拆分为 `components/` 子模块（`stepfun_event_payloads.py`、`stepfun_message_helpers.py`、`stepfun_tool_helpers.py` 等），体现了组件化思维。
**问题**：`common/` 目录过于庞大（包含 auth、db、websocket、ai、knowledge、analytics 等），随着功能增长可能需要进一步拆分。

## 前后端契约是否清晰
**评价**：基本清晰，但存在局部不一致。
前端 `web/src/lib/api/types.ts` 和后端 Pydantic schema（`common/db/schemas.py`、`agent/schemas.py`）有对应关系，API 统一返回 `{"success": true/false, "data": ..., "trace_id": ...}` 结构。
**问题**：
1. `admin/settings/page.tsx` 本地定义了大量模型配置类型，未与 `types.ts` 对齐。
2. 错误处理契约不统一：部分 API 返回 JSON 错误对象，部分直接 raise HTTPException 导致 FastAPI 生成不同的错误结构。

## 数据模型设计是否合理
**评价**：合理且较完整。
`backend/src/common/db/models.py`（1,113 行）覆盖了用户、会话、消息、PPT、评估报告、知识库、系统日志、发布验证等 20+ 张表。使用了 SQLAlchemy 2.0 风格、CheckConstraint、索引优化。Alembic 迁移历史有 34 个版本。
**问题**：部分字段为 JSON 类型（如 `voice_policy_snapshot`、`effectiveness_snapshot`），缺乏结构化约束，长期可能产生数据一致性问题。

## 错误处理是否充分
**评价**：框架层面充分，执行层面有混用。
项目定义了 `Result[T]` 模式（`common/error_handling/result.py`）， Constitution 明确要求所有用户-facing 代码使用 Result。全局异常中间件（`ErrorHandlerMiddleware`）和 `build_server_error()` 也体现了这一设计。
**问题**：大量路由层仍直接 `raise HTTPException`，破坏了统一错误契约，前端需要处理两种错误结构。

## 鉴权与权限体系是否完整
**评价**：技术框架完整，业务集成不完整。
JWT + Cookie + CSRF 三位一体已实现，RBAC（user/admin/support）有中间件支持（`require_role`、`get_current_admin_user`），密码使用 pbkdf2_sha256/bcrypt 哈希。
**问题**：WeChat SSO 是 mock，这是认证链路上最大的缺口。此外，部分 admin 路由历史遗留使用 `get_current_user` 而非 `get_current_admin_user`（注释中已自审：`M016/S03/T01 auth/RBAC baseline`）。

## 状态管理是否清晰
**评价**：清晰。
前端使用 Zustand（轻量）+ TanStack Query（服务端状态），练习页面通过自定义 hooks（`usePracticeWebSocket`、`useAudioRecorder`、`usePracticeSessionLifecycle`）将状态隔离，避免了组件级别的状态污染。WebSocket 状态（`connectionState`、`sessionStatus`、`aiState`）有明确的类型定义和流转规则。

## 可维护性如何
**评价**：中等偏上，但有明显热点。
- **优点**：组件化拆分、类型提示完整、结构化日志、Alembic 迁移规范。
- **缺点**：
  - `stepfun_realtime_handler.py` 4,569 行仍是维护噩梦；
  - `main.py` 779 行（含大量路由注册），随着模块增加会越来越臃肿；
  - 测试缺失导致重构风险极高。

## 扩展性如何
**评价**：较好。
Agent 平台设计支持动态配置场景和角色，语音运行时策略支持 profile 覆盖，提示词模板系统支持变量替换。新场景理论上可通过新增 scenario_type + handler 扩展。

## 是否存在明显技术债
**评价**：存在以下技术债：
1. **WeChat SSO mock** — 最大的功能性技术债。
2. **HTTPException 与 Result 混用** — 架构一致性债务。
3. **测试覆盖率 11%** — 质量保障债务。
4. **超大文件** — `stepfun_realtime_handler.py`、`main.py` 需要持续拆分。

## 是否存在后续高返工风险
**评价**：存在。
如果当前以"页面可用"为标准推进，而不修复测试、统一错误契约、拆分超大模块，那么进入真实用户测试后会暴露出大量边界问题，届时需要在紧张的时间表下同时修复 bug 和重构架构，返工成本将成倍增加。

---

# 6. 真实完成度结论

## 哪些部分可视为真实完成
（定义为：前后端已打通，数据链路闭环，基本功能可工作）

1. **Agent / Persona 管理**：完整的 CRUD、发布/归档、前后端分页和筛选。
2. **PPT 演练链路**：上传、解析、创建会话、练习、结束、报告查看，前后端均已打通。
3. **练习页面 UX**：WebSocket 连接、音频录制、实时面板、暂停/结束、错误提示，前端实现非常完整。
4. **管理后台的数据分析、用户管理、记录管理、知识库管理**：页面完整，API 完整，数据可真实读写。
5. **数据库模型与迁移**：表结构设计较完整，Alembic 迁移历史规范。

## 哪些部分只是看起来完成
（定义为：有代码/有页面，但存在关键缺口导致不能稳定工作）

1. **测试体系**：有 50+ 个测试文件，但测试环境跑不起来，覆盖率 11%，无法提供质量保障。
2. **StepFun Realtime 销售对练**：有 4,569 行的复杂 handler 和组件化拆分，但缺乏充分的集成测试和真实场景验证，稳定性未知。
3. **系统设置（模型配置）**：前端页面功能很多，但部分类型在前端本地定义，与后端 schema 同步性存疑。

## 哪些部分明显未完成

1. **WeChat 企微 SSO 登录**：明确为 mock，TODO 标记未完成。
2. **前端生产构建**：存在类型错误，`npm run build` 失败。
3. **测试执行环境**：PyJWT 依赖问题导致 pytest 无法收集测试。

## 距离可联调版本还差什么
- ✅ 已具备联调基础（前后端接口基本对齐）
- ⚠️ 需要明确：联调时使用 dev-login 还是必须完成企微 SSO？
- ⚠️ 建议先修复前端构建错误，避免联调时页面无法编译

## 距离可测试版本还差什么
1. **修复测试环境**：安装/配置 PyJWT，使 pytest 可运行。
2. **补齐核心链路测试**：至少覆盖会话创建、WebSocket 连接、报告生成、Agent CRUD。
3. **提升覆盖率目标**：从 11% 提升到至少 60%（核心模块）。
4. **统一错误契约**：清理 HTTPException 混用问题，确保前端错误处理可预测。

## 距离可上线版本还差什么
1. **解决 P0 阻塞项**：前端构建失败 + 企微 SSO（如需要）。
2. **建立可运行的 CI/CD 门禁**：构建 + 类型检查 + 测试通过 + 覆盖率检查。
3. **StepFun Realtime 稳定性验证**：在真实网络环境下进行压力测试和断网重连测试。
4. **安全审计**：检查 JWT Secret 配置、CSRF 策略、管理员权限矩阵。
5. **性能与成本验证**：确认单次演练成本 < ¥1 的预算目标可达成。

---

# 7. 建议的整改顺序

## 第一阶段：打通工程化基础设施（目标：解除上线阻塞）
**时间建议**：1–2 天

1. **修复前端构建错误**：`web/src/app/(dashboard)/page.tsx:440` 将 `variant="default"` 修正为 `variant="primary"`，运行 `npm run build` 确保通过。
2. **修复后端测试环境**：检查虚拟环境中 PyJWT 是否正确安装（`requirements.txt` 已声明），运行 `pytest --collect-only` 确认测试可收集。
3. **明确认证方案**：与产品确认是否必须企微 SSO。若是，制定企微对接计划；若否，文档化当前 dev-login 的适用范围，并设置明确的 SSO 完成里程碑。

**验收标准**：
- `npm run build` 成功
- `pytest` 可正常运行（至少收集测试不报错）
- 认证方案文档化

## 第二阶段：补齐核心链路闭环与契约一致性（目标：达到可测试状态）
**时间建议**：1 周

1. **统一错误处理契约**：扫描所有 API 路由文件，将直接 `raise HTTPException` 替换为 `error_response()` 或 `build_server_error()` 返回。
2. **补齐核心集成测试**：
   - 练习会话创建 → 结束 → 报告生成
   - WebSocket 连接与消息流转（Legacy 模式）
   - Agent / Persona CRUD
   - PPT 上传与解析
3. **提升测试覆盖率**：核心模块（practice、agent、sales_bot、presentation_coach）覆盖率达到 60% 以上。
4. **收敛前端类型**：将 `admin/settings/page.tsx` 中本地定义的模型配置类型迁移到 `lib/api/types.ts`。

**验收标准**：
- pytest 全部通过
- 核心模块覆盖率 ≥ 60%
- 前后端类型/契约一致性无明显缺口

## 第三阶段：优化架构热点与稳定性验证（目标：达到可上线状态）
**时间建议**：1–2 周

1. **拆分超大文件**：将 `stepfun_realtime_handler.py` 中更多逻辑（如状态恢复、知识检索编排）下沉到独立 service。
2. **StepFun Realtime 稳定性验证**：
   - 端到端延迟测试（目标 < 300ms）
   - 断网重连测试
   - 高并发压力测试
3. **完成企微 SSO（如需要）**：接入企业微信 OAuth2 / JS-SDK，替换 mock 实现。
4. **安全与合规审计**：
   - JWT Secret 生产环境强制校验（`main.py` 中已有校验逻辑，确认生效）
   - 演练记录访问权限审计（仅本人和管理员）
   - 日志脱敏检查
5. **成本验证**：监控单次演练的 API 调用成本，确认在 ¥1 预算内。

**验收标准**：
- 生产构建成功且部署无报错
- 核心实时链路通过稳定性测试
- 安全审计无高危问题
- 成本符合预算约束
