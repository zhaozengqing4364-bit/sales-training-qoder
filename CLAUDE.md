---
description: 
alwaysApply: true
---

# CLAUDE.md

本文件是 **本仓库的 L3 操作手册**（命令、目录、产品宪法、Issue 流程）。
**工程原则与 AI 协作宪章**见 [AGENTS.md](AGENTS.md)（L0，优先适用）。

---

## Agent 协作（本仓库偏好）

- 解释与汇报使用**简体中文**。
- 回答宜简洁；复杂任务可用「概述 + What / Where / Risks / Next / Open」。
- 写代码前已读 [AGENTS.md](AGENTS.md)；触及会话、实时连接、多入口创建时，遵守宪章 §IV、§V（探索宽、交付窄、症状修复须披露）。
- 工具与验证：并行检索；改后跑相关测试与 lint；完成时给出证据，不编造未执行的检查。

---
## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `zhaozengqing4364-bit/sales-training-qoder` using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This repo uses a single-context domain-doc layout: root `CONTEXT.md` when present, with architectural decisions in `docs/adr/`. See `docs/agents/domain.md`.
---

## Project Overview

**项目名称**: Enterprise AI Intelligent Practice System (企业级 AI 智能演练系统)
**项目描述**: 基于 Web(H5)端的企业级 AI 员工陪练平台，集成于企业微信工作台。通过全双工语音交互技术，提供 PPT 演讲复盘和高压销售对练两种核心场景，并支持通过 Agent 平台动态配置演练场景。
**开发模式**: Spec-Driven Development with .kiro steering system

## Project Principles (Constitution)

### I. 用户体验永不中断 (NON-NEGOTIABLE)
演练进行中：**禁止** `alert` / `confirm` / 阻塞式弹窗。可恢复故障用状态条、故障面板等非阻塞反馈；**不可恢复**（鉴权、契约不满足、未配置）须明确、稳定地失败，**禁止**无限重连掩盖（与 [AGENTS.md](AGENTS.md) §IV 一致）。

### II. 实时性优先
端到端延迟目标：<300ms（从用户停止说话到 AI 开始回应）

### III. 模块化场景独立
多轨演练场景（PPT 演练 `presentation_coach/`、销售对练 `sales_bot/`、新人训练路径 `sales_trainer/`、课程考核 `curriculum_practice/`、运行时主语 `training_runtime/`）必须**独立演进、互不引用**；共享逻辑下沉到 `common/`，跨域访问需通过 `common/api/` 或 `common/db/models.py` 中转。详见 [docs/architecture.md](docs/architecture.md) §17 模块边界 与 [backend/src/*/AGENTS.md](backend/src/) 各子域契约。

### IV. 容错与恢复
区分可恢复与不可恢复错误；单一依赖故障不得拖垮全站。可恢复：有限重试与降级；不可恢复：快速失败 + 可操作提示，不在连接层盲目重试。

### V. 成本控制
单次演练成本 <¥1（包含所有 API 调用）

### VI. 数据隐私与合规
演练记录只能被本人和管理员访问

### VII. 可观测性
结构化日志，所有日志包含 trace_id

## Commands

### 环境配置
```bash
# 后端环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 配置必要的环境变量

# 前端环境变量
cp web/.env.example web/.env.local
# 编辑 web/.env.local 配置 API 地址等
```

**关键环境变量** (完整配置见 `backend/.env.example`):

```bash
# ============================================
# 阿里云配置 (TTS/ASR)
# ============================================
DASHSCOPE_API_KEY=replace-with-dashscope-api-key
MODEL_CONFIG_ENCRYPTION_KEY=replace-with-fernet-key

# TTS 提供商选择: aliyun | edge | browser
TTS_PROVIDER=aliyun
TTS_VOICE=longxiaochun              # 龙小春 (温柔女声)
TTS_SAMPLE_RATE=16000

# TTS 降级配置
TTS_ENABLE_FALLBACK=true
TTS_FALLBACK_CHAIN=aliyun,edge,browser
TTS_TIMEOUT=10
TTS_CONNECTION_POOL_SIZE=10
TTS_ENABLE_WARMUP=true

# ============================================
# StepFun Realtime（双轨语音模式）
# ============================================
STEPFUN_API_KEY=replace-with-stepfun-api-key
STEPFUN_REALTIME_URL=wss://api.stepfun.com/v1/realtime
STEPFUN_REALTIME_MODEL=step-audio-2  # step-audio-2 | step-audio-2-mini
DEFAULT_VOICE_MODE=stepfun_realtime  # legacy | stepfun_realtime
STEPFUN_REALTIME_VOICE=qingchunshaonv
STEPFUN_REALTIME_OUTPUT_SAMPLE_RATE=24000

# ============================================
# 数据库与缓存
# ============================================
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
REDIS_URL=redis://localhost:6379/0
CHROMADB_PERSIST_DIR=./data/chromadb

# ============================================
# Auth（受控登录）
# ============================================
AUTH_SHARED_PASSWORD=change-me
AUTH_USER_PASSWORDS_JSON={}         # 可选：按账号覆盖口令

# ============================================
# 日志与调试
# ============================================
LOG_LEVEL=INFO
WEBSOCKET_DEBUG=false
ENABLE_TRACING=true
```

### Backend
```bash
cd backend

# 环境设置
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 数据库迁移 (Alembic)
alembic upgrade head       # 应用所有迁移
alembic revision --autogenerate -m "描述"  # 创建新迁移

# 开发 (端口 3444)
python -m uvicorn src.main:app --reload --port 3444

# 测试
pytest                           # 运行所有测试
pytest tests/unit/              # 单元测试
pytest tests/integration/       # 集成测试
pytest tests/performance/       # 性能测试 (50 并发)
pytest tests/unit/test_asr.py   # 运行单个测试文件
pytest tests/unit/test_asr.py -v -k "test_transcribe"  # 运行特定测试
pytest -cov=src --cov-report=html  # 生成覆盖率报告

# 代码质量
ruff check src/                 # 检查代码规范
ruff format src/                # 格式化代码
mypy src/                       # 类型检查
```

### Frontend
```bash
cd web

# 开发 (端口 3445)
npm run dev

# 生产构建
npm run build
npm run start

# 测试
npm run test                    # 运行所有测试
npm run test:watch              # 监视模式
npm run test:coverage           # 生成覆盖率报告

# 代码检查
npm run lint                    # 运行 ESLint
```

### Docker
```bash
# 启动所有服务 (后端 3444, 前端 3445)
docker-compose up -d

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 停止服务
docker-compose down

# 重建并启动
docker-compose up -d --build
```

### 服务端口
| 服务 | 端口 | 说明 |
|------|------|------|
| Backend API | 3444 | FastAPI 后端服务 |
| Frontend Dev | 3445 | Next.js 开发服务器 |
| PostgreSQL | 5432 | 数据库 (Docker) |

## Project Structure & Architecture

```
backend/src/
├── main.py                    # FastAPI 应用入口 (75 行兼容 shim, 实际装配见下)
├── app_factory.py             # create_app() 工厂: middleware + 路由 + lifespan 装配
├── app_lifespan.py            # lifespan 上下文: DB/Redis/Chroma/SessionManager/ConfigManager 初始化
├── http_routes.py             # HTTP 顶层注册 (health / metrics / dev-login)
├── websocket_routes.py        # WebSocket 顶层注册 (3+ 通道统一挂载)
├── router_registry.py         # 30+ HTTP APIRouter 集中挂载 + knowledge-bases 别名镜像
├── agent/                     # Agent 平台核心
│   ├── api/                   # Agent, Persona 管理 API
│   ├── capabilities/          # 能力模块 (ASR, TTS, LLM, Scoring)
│   │   ├── base.py                  # Capability 抽象基类
│   │   ├── registry.py              # 能力注册表
│   │   ├── runner.py                # 链式编排执行器
│   │   ├── knowledge_retrieval.py
│   │   ├── fuzzy_detection.py
│   │   ├── realtime_scoring.py
│   │   └── sales_stage.py
│   ├── models.py
│   ├── context.py
│   └── services/              # Agent 业务逻辑
│       ├── agent_service.py
│       ├── agent_persona_service.py
│       ├── persona_service.py
│       ├── persona_policy.py
│       └── industry_pack_contract.py
├── prompt_templates/          # 提示词模板系统 (含 api/routes.py + scenario 绑定)
├── evaluation/                # 分阶段评估系统 (含 triggers/ 与 staged_evaluation)
├── sales_trainer/             # 【新人训练路径】异步学习/录音/考卷 (与 sales_bot 实时对练**分离**)
│   ├── api.py                 # Router surface (含 user/admin_router)
│   ├── article_api.py / paper_api.py / regrade_api.py / unit_api.py
│   ├── models.py / schemas.py / permissions.py / rules.py
│   ├── router_registration.py # 12 子路由集中注册
│   ├── services/              # 56 个 service (含 audio_submission, paper_revision, material_publish)
│   └── tasks/                 # 异步评分/转写入口
├── curriculum_practice/       # 【课程闭环】templates / 考官 WS / test bank
│   ├── api.py                 # 9 router 在 2542 行文件中
│   ├── models.py / schemas.py
│   ├── services/              # practice_templates / examiner_agents / publishing_gates / snapshots / ...
│   └── websocket/             # /ws/curriculum/examiner/{session_id}
├── training_runtime/          # 【运行时主语】TrainingRuntimeDescriptor + plugin dispatch
│   ├── models.py / service.py
│   ├── plugins.py             # dispatch_scenario_plugin (含 LEGACY_SALES_HANDLER_MODULES 禁单)
│   └── stepfun_transport.py
├── supervisor/                # 【主管审核】TrainingReportViewModel + 复训任务
├── curriculum_analytics/      # 课程数据聚合 (与 admin/api/analytics_curriculum.py 配合)
├── support/                   # 运维支撑 (runtime_status_service 等)
├── admin/                     # 管理后台 API (governance / config_center / config_bundles / voice_runtime / ...)
├── presentation_coach/        # PPT 演练场景 (独立)
│   ├── api/                   # PPT 上传、会话管理 API
│   ├── services/              # Coach, PointTracker, InterruptionDetector (13 文件)
│   │   ├── coach_service.py
│   │   ├── feedback_service.py
│   │   ├── ppt_parser.py
│   │   ├── presentation_ai_policy_service.py
│   │   ├── presentation_report_service.py
│   │   ├── prompt_role_resolver.py
│   │   ├── point_tracker.py
│   │   ├── point_extraction.py
│   │   ├── semantic_point_tracker.py
│   │   ├── user_presentation_progress.py
│   │   ├── interruption_detector.py
│   │   ├── aho_matcher.py
│   │   └── forbidden_matcher.py
│   └── websocket/             # PPT 演练 WebSocket
│       ├── presentation_handler.py            # legacy 模式入口
│       └── presentation_stepfun_realtime_handler.py  # StepFun 变体 (复用 sales transport + PPT 上下文)
├── sales_bot/                 # 销售对练场景 (独立) — **仅 StepFun-Realtime** 模式
│   ├── api/                   # 场景管理 API (scenarios / bot_service)
│   ├── services/              # BotService, ContextManager, SummaryService (9 文件)
│   │   ├── bot_service.py             # (内含 _build_legacy_langchain_chain 残留, 确认无人调用后可清)
│   │   ├── context_manager.py
│   │   ├── roleplay_compliance_checker.py
│   │   ├── summary_service.py
│   │   ├── transcript_normalization.py
│   │   ├── vagueness_detector.py
│   │   ├── voice_instruction_compiler.py
│   │   ├── voice_policy_monitor.py
│   │   └── voice_runtime_policy.py
│   └── websocket/             # 销售对练 WebSocket (StepFun Realtime 单一权威)
│       ├── router.py                       # /ws/sales/{session_id} 入口
│       ├── stepfun_realtime_handler.py     # 1157 行主 handler, 6 mixin 组合 (复杂度热点)
│       ├── stepfun_realtime_state.py       # 类型边界 (typed state base)
│       ├── stepfun_realtime_connection.py  # transport mixin
│       ├── stepfun_realtime_policy.py      # 语音策略 + 客户端消息分发 (60KB)
│       ├── stepfun_realtime_upstream.py    # 上游事件路由/函数调用/响应生命周期 (115KB)
│       ├── stepfun_realtime_feedback.py    # 实时反馈仲裁 (53KB)
│       ├── stepfun_realtime_sales_stage.py # sales stage capability (17KB)
│       ├── stepfun_realtime_constants.py
│       ├── stepfun_runtime_types.py
│       ├── stepfun_tool_execution.py
│       ├── voice_runtime_profile.py
│       ├── session_control_adapter.py
│       ├── grounding_decision_pipeline.py
│       ├── phase4_local_provider.py        # phase4 local fallback
│       ├── realtime_audio_flow.py
│       ├── realtime_feedback_arbiter.py
│       ├── realtime_turn_coordinator.py
│       ├── sales_handler.py.deprecated     # ⚠️ 已弃用, training_runtime/plugins.py 显式禁用
│       └── components/                     # 解耦组件 (22 个 stepfun_* / capability_* helper)
│           ├── capability_processor.py
│           ├── curriculum_stage_runtime.py
│           ├── message_persistence.py
│           ├── objection_ledger_helpers.py
│           ├── score_processor.py
│           ├── stepfun_asr_fallback.py
│           ├── stepfun_emotion_analyzer.py
│           ├── stepfun_event_payloads.py
│           ├── stepfun_function_call_helpers.py
│           ├── stepfun_helpers.py
│           ├── stepfun_internal_knowledge_searcher.py
│           ├── stepfun_knowledge_helpers.py
│           ├── stepfun_message_helpers.py
│           ├── stepfun_runtime_metrics_helpers.py
│           ├── stepfun_thinking_capture.py
│           ├── stepfun_tool_helpers.py
│           ├── stepfun_tts_contracts.py
│           ├── stepfun_upstream_router.py
│           ├── stepfun_voice_errors.py
│           ├── stepfun_voice_selection.py
│           └── tts_component.py
├── common/                    # 共享模块 (27 子包 + config.py)
│   ├── ai/                    # LLM, Embedding, ConfigManager, encryption
│   ├── analytics/             # 公共分析 (与 admin/analytics 区分)
│   ├── api/                   # 公共 REST 路由 (training, practice, dashboard, ...)
│   ├── audio/                 # ASR/TTS 服务 (10 文件)
│   │   ├── asr_service.py / asr_with_fallback.py
│   │   ├── asr_alibaba.py / asr_base.py / asr_local.py / asr_streaming.py
│   │   ├── pcm_duration.py
│   │   ├── tts_service.py / tts_factory.py
│   │   └── aliyun_streaming_tts.py
│   ├── auth/                  # JWT + shared password + WeCom SSO
│   ├── business_rules/        # 业务规则引擎
│   ├── cache/                 # Redis 封装
│   ├── config.py              # 全局配置常量
│   ├── conversation/          # 对话消息存储/回放/证据
│   ├── cos/                   # 阿里云 OSS 兼容层
│   ├── db/                    # SQLAlchemy session + models
│   ├── e2e/                   # 端到端测试 fixture
│   ├── effectiveness/         # Canonical 评估内核
│   ├── error_handling/        # Result[T] + middleware
│   ├── growth/                # 成长中心
│   ├── jobs/                  # 异步任务 (RQ/Celery 包装)
│   ├── knowledge/             # ChromaDB 封装 + KB Lock guard
│   ├── knowledge_engine/      # Haystack 知识问答引擎
│   ├── logging/               # 日志脱敏
│   ├── middleware/            # 通用中间件
│   ├── monitoring/            # Prometheus + structlog 配置
│   ├── oss/                   # 通用 OSS 抽象
│   ├── ppt/                   # PPT 解析共享
│   ├── rate_limit/            # api_limiter / session_limiter
│   ├── recommendations/       # 推荐算法
│   ├── resilience/            # circuit_breaker / backoff
│   ├── services/              # runtime_gate / practice_session / session_runtime_* 等高阶 service
│   ├── storage/               # 存储 (document / audio / presentation)
│   ├── training_tasks/        # 训练任务 (TrainingTask 状态机)
│   ├── validation/            # input_validator / file_validator / html_sanitizer
│   └── websocket/             # BaseWebSocketHandler + SessionManager + SessionStateService
└── tests/

web/src/app/
├── (auth)/                    # 登录页面
├── (dashboard)/               # 用户仪表板
├── (user)/                    # 练习页面
│   └── practice/[sessionId]/
│       ├── page.tsx           # 练习主页
│       └── report/page.tsx    # 练习报告
└── admin/                     # 管理后台 (22+ 路由族)
    ├── page.tsx               # 管理首页
    ├── agents/                # Agent 管理
    ├── personas/              # Persona 管理
    ├── presentations/         # PPT 管理
    ├── presentation-ai/       # PPT AI 策略管理
    ├── prompts/               # 提示词管理
    ├── voice-runtime/         # 语音运行时配置
    ├── knowledge/             # 知识库管理
    ├── users/                 # 用户管理
    ├── records/               # 演练记录
    ├── analytics/             # 数据分析
    ├── settings/              # 系统设置
    ├── business-rules/        # 业务规则配置
    ├── curriculum-practice/   # 课程考核管理
    ├── governance/            # AI 治理
    ├── learning-contents/     # 学习内容管理
    ├── logs/                  # 系统日志
    ├── rag-profiles/          # RAG 配置画像
    ├── retrieval-strategies/  # 检索策略
    ├── sales-trainer/         # 新人训练路径管理
    ├── scoring-rulesets/      # 评分规则集
    ├── supervisor-training/   # 主管培训/复训
    └── test-bank/             # 题库管理
```

## Active Technologies

### 后端
- Python 3.11+ with async/await
- FastAPI, SQLAlchemy 2.0+, Pydantic 2.0+
- FunASR / 阿里云 ASR, Edge-TTS / 阿里云流式 TTS
- StepFun Realtime API (双轨语音)
- ChromaDB, PostgreSQL, Redis
- structlog, tenacity, aiohttp, dashscope

### 前端
- Next.js 16.2.3, React 19.2.3, TypeScript 5+
- Tailwind CSS 4+, Radix UI, Zustand, Vitest

## Code Style

### Python (Ruff)
- 88 字符行宽, 4 空格缩进, 双引号优先
- 类型提示必需, 使用 `ruff format`

### TypeScript
- 2 空格缩进, 单引号优先, 分号必需

## 禁止事项

```
后端:
❌ print() → logger.info()
❌ session.query(Model) → select(Model)
❌ orm_mode = True → from_attributes = True
❌ @app.on_event("startup") → lifespan
❌ raise HTTPException(500) → Result.fail()

前端:
❌ bg-white（全页背景）→ bg-slate-50
❌ text-black → text-slate-900
❌ 猜测 API → 查 docs/api-contract/
❌ alert/popup → 状态指示器
```

## 核心架构模式

### 错误处理: Result[T]
```python
from common.error_handling.result import Result

async def process() -> Result[str]:
    try:
        return Result.ok(await do_work())
    except SomeError:
        return Result.fail("[ERROR_CODE]")
```

### WebSocket: BaseWebSocketHandler
```python
class MyHandler(BaseWebSocketHandler):
    async def handle_message(self, message: dict):
        pass
```

### 前端 API 客户端
```typescript
import { api } from '@/lib/api/client';
const data = await api.module.getEndpoint();
```

## 开发前必读文档

| 系统架构 | `docs/architecture.md` |
| API 接口规范 | `docs/api-contract/` |
| 后端编码原则 | `.kiro/steering/backend-principles.md` |
| 前端编码原则 | `.kiro/steering/frontend-principles.md` |
| 架构决策 | `docs/adr/` |
| 快速参考 | `.kiro/steering/QUICK-REFERENCE.md` |

## 提交前检查

```
□ ruff check 通过
□ ruff format 已执行
□ mypy 类型检查通过
□ 无 print() 语句
□ 使用 Result[T] 包装错误
□ 前端无 alert/popup
□ 单元测试通过
```

## 最近更新

- **2026-02-16**: CLAUDE.md 更新
  - 销售对练 WebSocket 组件化 (stepfun_* 模块拆分)
  - PPT 演练增强 (presentation_ai_policy, prompt_role_resolver)
  - TTS 服务工厂化 (tts_factory, aliyun_streaming_tts)
  - 前端新增 presentation-ai 管理页面

- **2026-05 ~ 2026-06**: 多模块增量
  - 新人训练路径 `sales_trainer/` 落地（异步学习/录音/考卷/重判，与销售实时对练**分离**）
  - 课程闭环 `curriculum_practice/` + 考官 WS + test bank + publish gate
  - 训练运行时主语 `training_runtime/`（`TrainingRuntimeDescriptor` + `dispatch_scenario_plugin`）
  - 主管审核 `supervisor/`（TrainingReportViewModel + 复训任务）
  - 课程分析 `curriculum_analytics/` + `admin/analytics_curriculum/`
  - 运维支撑 `support/`
  - `app_factory.py` / `app_lifespan.py` / `http_routes.py` / `websocket_routes.py` 装配入口分离
  - `BaseWebSocketHandler` 收敛 + `RuntimeGate.admit_session` 统一 admission
  - Config Asset B2 HITL 治理 ADR（2026-05-27）
  - routing audit 闭环 (Phase 1.2)

- **2026-02-15**: Claude Code 钩子系统 V2 优化

---

## 自生长记录区

### 架构决策

| 日期 | 决策 | 影响 |
|------|------|------|
| 2026-05-27 | Config Asset B2 HITL 治理 | 配置变更审批边界（AFK / HITL-Notify / HITL-Approve / HITL-Block） |
| 2026-05-26 | Roleplay Contract 治理 | Situation Pack 不得脱离统一配置治理 |
| 2026-05-12 | Case Item + Role Profile 试点契约 | 最小内容资产 (Proposed, 待 HITL 批准) |
| 2026-05-11 | 领域边界与契约锁定 (PRD #23) | TrainingTask / PracticeSession / EvaluationRun / ConfigBundle 边界 |
| 2026-05-11 | curriculum_practice 边界契约 | 内容资产 + RuntimeSnapshotService + 统一 *_ref JSON |
| 2026-04-24 | 评分规则集治理 | versioned ruleset + 报告口径固化 + dry-run + 发布审计 |
| 2026-04-21 | 成长中心延迟切片 | G-04 / G-08 / G-10 推迟到 Lane E |
| 2026-03-14 | 训练运行时主语收敛 | `training_scenario_runtime` 单一主语, 避免场景分支 |
| 2026-02-16 | 销售 WebSocket 组件化 | 解耦事件/消息/工具处理逻辑 |
| 2026-02-15 | V2 钩子系统 | 精确工具计数 + 自动反思 |
| 2026-02-13 | StepFun 事件解耦 | 降低 handler 复杂度 |
| 2026-02-06 | TTS 降级链 | 阿里云→Edge→浏览器 |
| 2026-02-04 | 分阶段评估 | 触发器模式 |
| 2026-01-20 | StepFun Realtime | 双轨语音模式 |

> 完整 ADR 见 [docs/adr/](docs/adr/)（10 个 ADR, 2026-03-14 ~ 2026-05-27）。

---

<!-- MANUAL ADDITIONS START -->
<!-- 手动添加的内容放在这里 -->
<!-- MANUAL ADDITIONS END -->
