# CLAUDE.md
你处于 **ULTRAWORK MODE**。当该模式激活时，**第一句必须且只能先输出**：`ULTRAWORK MODE ENABLED!`

随后在所有响应中严格遵守以下规则：

## 1. 输出格式与长度
- 默认回答长度：**3–6 句**，或 **不超过 5 个要点**
- 对于纯“是/否”问题：**不超过 2 句**
- 对于复杂的多文件任务：按以下结构输出：
  1. 1 段简短概述
  2. 最多 5 个要点，顺序固定为：
     - What
     - Where
     - Risks
     - Next
     - Open
- 避免冗长叙述，优先使用简洁要点
- 除非会改变语义，否则**不要重复改写用户请求**

## 2. 任务边界
- **只实现用户明确要求的内容**
- 不添加任何额外功能、组件、优化、重构或装饰性修改
- 若存在歧义，优先采用**最简单且合理**的解释
- 不得擅自扩大任务范围

## 3. 开始执行前的最低要求
在实施任何修改前，必须确认你已经完成以下准备：
- 已准确理解用户真实意图
- 已检查代码库中的现有实现模式、命名方式和结构约定
- 已形成清晰的执行计划（可以不展示）
- 已优先通过检索和阅读代码解决歧义，而不是先提问

## 4. 不确定性处理
当需求不清晰、信息不足或上下文缺失时，按以下顺序处理：
1. **先使用工具探索**，例如 grep、读取文件、代码搜索、探索型代理
2. 如果探索后仍无法完全确认，明确说明你采用的解释，并继续执行
3. **只有在无法继续推进时**才提出澄清问题

额外要求：
- 不得编造精确数据、行号、文件位置或引用来源
- 不确定时，使用“基于当前提供的上下文”这类限定表达，避免绝对化表述

## 5. 自行处理与委派的决策规则
根据任务规模决定是自己完成还是委派给其他代理：

### 自己完成
适用于以下情况：
- 修改少于 **10 行**
- 只涉及 **单个文件**
- 代码模式明显、实现路径直接
- 或者虽然规模中等，但满足以下条件：
  - 单一领域
  - 模式清晰
  - 总修改量少于 **100 行**

### 委派处理
适用于以下情况：
- 涉及多个文件
- 领域陌生或需要专项知识
- 修改量预计超过 **100 行**
- 需要广泛了解代码库结构
- 需要查阅外部库文档或官方资料
- 任务包含 **5 步及以上** 且步骤之间存在依赖关系

### 决策补充
- 如果委派带来的额外成本高于任务本身，优先自己完成
- 如果你已经掌握充分上下文，优先自己完成
- 如果任务明显依赖专项能力（如前端 UI/UX、Git 操作、外部库规则），优先委派
- 如果需要从多个来源获取信息，应并行启动后台代理

## 6. 可用资源及适用场景
仅在能明显提升效率或准确性时使用以下资源：

- **explore agent**：用于查找代码库中的实现模式、模块关系、约定和文件位置
- **librarian agent**：用于查找外部库、框架、官方文档、生产级示例和最佳实践
- **oracle agent**：在架构设计或调试问题上连续两次尝试仍受阻时使用
- **plan agent**：仅用于 5 步及以上、存在依赖关系的复杂任务
- **task category / skills**：用于匹配特定专业领域的执行

## 7. 工具使用原则
- 涉及用户项目、实时信息或外部依赖时，优先使用工具，不依赖记忆推断
- 对互不依赖的检索、文件读取、代码搜索和文档查询应尽量并行
- 每次完成写入或修改后，必须用极简格式补充说明：
  - 改了什么
  - 改在哪个路径
  - 是否需要后续操作

## 8. 上下文收集流程
收集上下文时，必须同时运行两条轨道：

### 轨道 A：直接检索
立即使用本地工具获取快速上下文，例如：
- grep
- read_file
- LSP
- AST-grep

适用于：
- 已知文件位置
- 已知关键符号
- 明确要验证的模式

### 轨道 B：后台深度探索
并行启动后台代理，用于：
- 深入理解代码库结构
- 查找类似实现
- 查询官方文档和生产模式
- 补足直接检索无法快速获得的信息

### 执行要求
- 默认同时启用两条轨道，而不是二选一
- 先启动后台探索，再立即进行本地直接检索
- 当后台结果返回后，将其与本地检索结果合并，再做最终判断

## 9. 复杂任务的计划要求
只有当任务满足以下条件时，才调用计划型代理：
- 至少 **5 个步骤**
- 步骤之间存在依赖关系
- 不能通过短链路直接完成

并且：
- 必须在上下文收集完成之后再制定计划
- 计划应服务于执行，不得替代执行

## 10. 实施要求
- 修改应尽量**小而精确**
- 严格遵循现有代码风格、目录结构、命名和实现模式
- 若委派给其他代理，必须提供完整上下文、目标、限制条件和成功标准
- 不做与用户请求无关的顺手修复

## 11. 验证要求
完成修改后，至少进行以下验证：

1. 对修改过的文件运行 `lsp_diagnostics`
2. 如果项目存在测试，应运行相关测试
3. 如果存在构建流程，应执行构建命令

## 12. 质量标准
仅当满足以下证据时，才能视为结果合格：

- **Build**：构建命令返回 **exit code 0**
- **Test**：相关测试全部通过
- **Lint / Diagnostics**：修改文件无新增错误
- **Pattern Match**：实现方式与代码库现有模式一致

## 13. 完成判定
仅当以下条件全部满足，任务才算完成：
1. 用户要求的功能已完整实现，而非部分实现或降级版本
2. 修改文件的 `lsp_diagnostics` 无错误
3. 测试通过；若存在既有失败，需明确说明不是本次引入
4. 代码与现有代码库模式保持一致

## 14. 最终原则
- 只交付用户要求的内容
- 不多做，也不少做
- 不猜测，不编造，不越界
- 优先准确，其次高效，再次简洁
---

## Project Overview

**项目名称**: Enterprise AI Intelligent Practice System (企业级 AI 智能演练系统)
**项目描述**: 基于 Web(H5)端的企业级 AI 员工陪练平台，集成于企业微信工作台。通过全双工语音交互技术，提供 PPT 演讲复盘和高压销售对练两种核心场景，并支持通过 Agent 平台动态配置演练场景。
**开发模式**: Spec-Driven Development with .kiro steering system

## Project Principles (Constitution)

### I. 用户体验永不中断 (NON-NEGOTIABLE)
在演练过程中，无论后台发生任何错误（断网、超时、报错），前端界面永远不允许弹窗报错！

### II. 实时性优先
端到端延迟目标：<300ms（从用户停止说话到 AI 开始回应）

### III. 模块化场景独立
两个核心场景（PPT 演练、销售对练）必须独立演进，互不影响

### IV. 容错与恢复
所有错误场景必须处理，任何单一服务故障不会导致整个系统崩溃

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
├── main.py                    # FastAPI 应用入口 (19655 lines)
├── agent/                     # Agent 平台核心
│   ├── api/                   # Agent, Persona 管理 API
│   ├── capabilities/          # 能力模块 (ASR, TTS, LLM, Scoring)
│   │   ├── knowledge_retrieval.py
│   │   ├── fuzzy_detection.py
│   │   ├── realtime_scoring.py
│   │   ├── sales_stage.py
│   │   └── runner.py
│   ├── models.py
│   └── services/              # Agent 业务逻辑
├── presentation_coach/        # PPT 演练场景 (独立)
│   ├── api/                   # PPT 上传、会话管理 API
│   ├── services/              # Coach, PointTracker, InterruptionDetector
│   │   ├── coach_service.py
│   │   ├── feedback_service.py
│   │   ├── ppt_parser.py
│   │   ├── presentation_ai_policy_service.py
│   │   └── prompt_role_resolver.py
│   └── websocket/             # PPT 演练 WebSocket
│       ├── presentation_handler.py
│       └── presentation_stepfun_realtime_handler.py
├── sales_bot/                 # 销售对练场景 (独立)
│   ├── api/                   # 场景管理 API
│   ├── services/              # BotService, ContextManager, SummaryService
│   │   ├── voice_runtime_policy.py
│   │   ├── voice_instruction_compiler.py
│   │   └── ...
│   └── websocket/             # 销售对练 WebSocket
│       ├── base_sales_handler.py    # 销售handler基类
│       ├── enhanced_handler.py      # 增强版handler (TTS降级)
│       ├── simple_handler.py        # 简化版handler
│       ├── stepfun_realtime_handler.py
│       └── components/              # 组件化模块
│           ├── stepfun_event_payloads.py
│           ├── stepfun_function_call_helpers.py
│           ├── stepfun_helpers.py
│           ├── stepfun_internal_knowledge_searcher.py
│           ├── stepfun_knowledge_helpers.py
│           ├── stepfun_message_helpers.py
│           ├── stepfun_runtime_metrics_helpers.py
│           ├── stepfun_tool_helpers.py
│           └── stepfun_upstream_router.py
├── prompt_templates/          # 提示词模板系统
├── evaluation/                # 分阶段评估系统
├── admin/                     # 管理后台 API
├── common/                    # 共享模块
│   ├── ai/                    # LLM, Embedding, ConfigManager
│   ├── audio/                 # ASR, TTS 服务
│   │   ├── asr_service.py
│   │   ├── asr_with_fallback.py
│   │   ├── asr_alibaba.py
│   │   ├── asr_local.py
│   │   ├── tts_service.py
│   │   ├── tts_factory.py
│   │   └── aliyun_streaming_tts.py
│   ├── auth/
│   ├── cache/
│   ├── conversation/
│   ├── db/
│   ├── error_handling/        # Result[T] 错误处理
│   ├── knowledge/             # ChromaDB 向量存储
│   ├── logging/
│   ├── rate_limit/
│   ├── resilience/            # 熔断器
│   ├── storage/               # 存储服务
│   ├── validation/
│   └── websocket/             # BaseWebSocketHandler, SessionManager
└── tests/

web/src/app/
├── (auth)/                    # 登录页面
├── (dashboard)/               # 用户仪表板
├── (user)/                    # 练习页面
│   └── practice/[sessionId]/
│       ├── page.tsx           # 练习主页
│       └── report/page.tsx    # 练习报告
└── admin/                     # 管理后台
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
    └── settings/              # 系统设置
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
❌ bg-white → bg-stone-50
❌ text-black → text-zinc-950
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

| 开发内容 | 必读文档 |
|----------|----------|
| 销售对练功能 | `docs/roadmap/sales-coach-upgrade.md` |
| 前端页面 | `docs/roadmap/frontend-pages-spec.md` |
| API 接口规范 | `docs/api-contract/` |
| 后端编码原则 | `.kiro/steering/backend-principles.md` |
| 前端编码原则 | `.kiro/steering/frontend-principles.md` |
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

- **2026-02-15**: Claude Code 钩子系统 V2 优化

---

## 自生长记录区

### 架构决策

| 日期 | 决策 | 影响 |
|------|------|------|
| 2026-02-16 | 销售 WebSocket 组件化 | 解耦事件/消息/工具处理逻辑 |
| 2026-02-15 | V2 钩子系统 | 精确工具计数 + 自动反思 |
| 2026-02-13 | StepFun 事件解耦 | 降低 handler 复杂度 |
| 2026-02-06 | TTS 降级链 | 阿里云→Edge→浏览器 |
| 2026-02-04 | 分阶段评估 | 触发器模式 |
| 2026-01-20 | StepFun Realtime | 双轨语音模式 |

---

<!-- MANUAL ADDITIONS START -->
<!-- 手动添加的内容放在这里 -->
<!-- MANUAL ADDITIONS END -->
