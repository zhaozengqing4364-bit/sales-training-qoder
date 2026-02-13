# CLAUDE.md

## 🤖 AI 开发系统

### 会话启动流程

```
1. pwd
2. git log --oneline -10
3. Read .agent/progress.md
4. Read .agent/tasks.json
5. Read .agent/project-context.md
```

### 核心原则

1. 增量开发 - 每次只处理一个任务
2. 严格测试 - 必须验证才能标记完成
3. 小步提交 - 完成就 commit
4. 清晰记录 - 更新 progress.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

**关键环境变量**:
```bash
# TTS 配置
TTS_PROVIDER=aliyun                    # aliyun | edge | browser
ALIYUN_DASHSCOPE_API_KEY=your_key      # 阿里云 DashScope API Key
ALIYUN_TTS_MODEL=cosyvoice-v1          # TTS 模型
ALIYUN_TTS_VOICE=longxia               # 默认语音

# ASR 配置
ASR_PROVIDER=alibaba                   # alibaba | local
ALIYUN_ASR_API_KEY=your_key            # 阿里云 ASR API Key

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db

# 日志
LOG_LEVEL=INFO
WEBSOCKET_DEBUG=false
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
├── main.py                    # FastAPI 应用入口
├── agent/                     # Agent 平台核心
│   ├── api/                   # Agent, Persona 管理 API
│   ├── capabilities/          # 能力模块 (ASR, TTS, LLM, Scoring)
│   ├── models.py              # Agent 数据模型
│   └── services/              # Agent 业务逻辑
├── presentation_coach/        # PPT 演练场景 (独立)
│   ├── api/                   # PPT 上传、会话管理 API
│   ├── services/              # Coach, PointTracker, InterruptionDetector
│   └── websocket/             # PPT 演练 WebSocket
├── sales_bot/                 # 销售对练场景 (独立)
│   ├── api/                   # 场景管理 API
│   ├── services/              # BotService, ContextManager, SummaryService
│   └── websocket/             # 销售对练 WebSocket
│       ├── base_sales_handler.py    # 销售handler基类
│       ├── enhanced_handler.py      # 增强版handler (TTS降级)
│       ├── simple_handler.py        # 简化版handler
│       └── components/              # 组件化模块
│           ├── capability_processor.py
│           ├── message_persistence.py
│           └── tts_component.py
├── prompt_templates/          # 提示词模板系统 (B1-B10)
│   ├── api/                   # 模板管理API
│   ├── models.py              # PromptTemplate, PromptType 模型
│   ├── service.py             # PromptTemplateService 业务逻辑
│   ├── loader.py              # 模板加载与缓存
│   └── renderer.py            # Jinja2 模板渲染
├── evaluation/                # 分阶段评估系统 (C1-C7)
│   ├── api.py                 # 评估API
│   ├── schemas.py             # 评估数据模型
│   ├── services/              # StagedEvaluationService, ComprehensiveReport
│   └── triggers/              # 触发器 (keyword, time_interval, turn_count, stage_transition)
├── admin/                     # 管理后台 API
│   └── api/                   # users, analytics, model_configs, system_logs
├── common/                    # 共享模块 (不依赖业务)
│   ├── ai/                    # LLM, Embedding, ConfigManager
│   ├── api/                   # 通用API响应格式
│   ├── audio/                 # ASR (FunASR/Alibaba), TTS (Edge-TTS/Aliyun/降级)
│   │   ├── asr_base.py
│   │   ├── asr_service.py
│   │   ├── asr_alibaba.py         # 阿里云ASR
│   │   ├── asr_with_fallback.py   # ASR降级机制
│   │   ├── tts_factory.py         # TTS工厂
│   │   ├── tts_service.py
│   │   └── aliyun_streaming_tts.py # 阿里云流式TTS
│   ├── auth/                  # JWT 认证
│   ├── cache/                 # 缓存 (Redis/内存)
│   ├── conversation/          # 对话引擎、回放
│   ├── db/                    # SQLAlchemy 2.0 会话
│   ├── error_handling/        # Result[T] 错误处理
│   ├── knowledge/             # ChromaDB 向量存储
│   ├── logging/               # 结构化日志 (structlog)
│   ├── rate_limit/            # 限流控制
│   ├── resilience/            # 熔断器、重试
│   ├── validation/            # 输入验证
│   └── websocket/             # BaseWebSocketHandler, SessionManager
└── tests/                     # 测试目录
    ├── unit/                  # 单元测试 (70%)
    ├── integration/           # 集成测试 (20%)
    ├── performance/           # 性能测试 (10%)
    ├── contract/              # API 契约测试
    └── conftest.py            # pytest 配置和 fixtures

web/src/
├── app/                       # Next.js App Router
│   ├── (auth)/                # 认证页面
│   ├── (dashboard)/           # 用户仪表板
│   ├── (user)/                # 练习页面
│   │   └── practice/
│   │       └── [sessionId]/   # 练习会话页面
│   │           ├── page.tsx
│   │           └── report/    # 评估报告页面
│   └── admin/                 # 管理后台
│       ├── knowledge/         # 知识库管理
│       ├── personas/          # Persona管理
│       ├── prompts/           # 提示词模板管理
│       ├── records/           # 演练记录
│       ├── settings/          # 系统设置
│       └── users/             # 用户管理
├── components/
│   ├── analytics/             # 数据分析图表
│   ├── knowledge/             # 知识库组件
│   ├── layout/                # 侧边栏、导航
│   ├── practice/              # 练习相关组件
│   │   ├── presentation/      # PPT演练组件
│   │   └── realtime-feedback.tsx
│   ├── training/              # 训练组件
│   └── ui/                    # 原子组件 (glass-card, button, input, checkbox, status-indicator)
├── hooks/                     # 自定义Hooks
│   ├── websocket/             # WebSocket相关hooks
│   │   ├── types.ts
│   │   ├── message-handlers.ts
│   │   └── use-audio-playback.ts
│   ├── use-audio-recorder.ts
│   ├── use-practice-websocket.ts
│   ├── use-streaming-audio-player.ts
│   ├── use-knowledge-base-linker.ts
│   └── use-debounce-request.ts
├── lib/
│   ├── api/                   # API client (types.ts, client.ts)
│   ├── debug.ts               # 调试工具
│   └── performance.ts         # 性能监控
└── types/                     # TypeScript 类型定义

docs/
├── README.md                  # 文档索引
├── api-contract/              # API 契约
└── roadmap/                   # 规划文档

.kiro/                         # AI 开发指导系统
├── steering/                  # 编码规范 (自动加载)
│   ├── QUICK-REFERENCE.md
│   ├── backend-principles.md
│   └── frontend-principles.md
└── templates/                 # 代码模板
```

## Active Technologies

### 后端
- Python 3.11+ with async/await
- FastAPI (异步 Web 框架)
- SQLAlchemy 2.0+ (async ORM)
- Pydantic 2.0+ (数据验证)
- FunASR 1.1.18 / Alibaba qwen3-asr-flash (流式 ASR)
- Edge-TTS / 阿里云 DashScope TTS (文本转语音，支持自动降级)
- LangChain (AI 编排)
- ChromaDB (向量数据库)
- PostgreSQL (关系数据库)
- structlog (结构化日志)
- tenacity (重试机制)
- aiohttp (异步 HTTP 客户端)

### 前端
- Next.js 16.1.1 (React 框架)
- React 19.2.3
- TypeScript 5+
- Tailwind CSS 4+ (内联 @theme)
- Radix UI (无样式组件)
- Zustand (状态管理)
- Vitest (测试)

## Code Style

### Python (Ruff + Black)
- 88 字符行宽
- 4 空格缩进
- 双引号优先
- 类型提示必需 (async def)
- 使用 `ruff format` 格式化

### TypeScript/JavaScript
- 2 空格缩进
- 单引号优先
- 分号必需
- const/let 优先 (禁用 var)

## 绝对禁止 (后端)

```
❌ print()                    → logger.info()
❌ session.query(Model)       → select(Model)  [SQLAlchemy 2.0]
❌ orm_mode = True            → from_attributes = True  [Pydantic v2]
❌ @app.on_event("startup")   → lifespan 上下文
❌ raise HTTPException(500)   → Result.fail("[ERROR_CODE]")
❌ from sqlalchemy.orm import Session → AsyncSession
❌ 硬编码密钥/配置            → 环境变量
❌ 同步数据库操作             → async/await
```

## 绝对禁止 (前端)

```
❌ bg-white 大背景            → bg-stone-50 或使用 CSS 变量
❌ text-black / #000000       → text-zinc-950
❌ shadow-md/lg/xl            → 使用自定义 @theme shadow
❌ 猜测 API 结构              → 先查 docs/api-contract/
❌ 使用 alert/popup           → 状态指示器优雅降级
```

## 新功能模块

### Prompt Template System (提示词模板系统)

基于 Jinja2 的动态提示词管理系统，支持变量注入和模板继承。

**主要组件**:
- `PromptTemplateService` - 模板 CRUD 和版本管理
- `PromptTemplateLoader` - 从文件系统/数据库加载模板
- `PromptRenderer` - Jinja2 渲染与变量注入

**Prompt 类型** (`PromptType`):
```python
- SYSTEM / SYSTEM_PROMPT  # 系统提示词
- SUMMARY                 # 对话总结
- EXTRACTION              # 信息提取
- SCORING                 # 评分提示词
- STAGE                   # 阶段评估
- EVALUATION              # 综合评估
- REPORT                  # 报告生成
- WELCOME                 # 欢迎语
- INTERRUPTION            # 中断检测
- TRACKING                # 要点跟踪
- FUZZY_DETECTION         # 模糊检测
```

**使用示例**:
```python
from prompt_templates.service import PromptTemplateService
from prompt_templates.renderer import PromptRenderer

# 获取模板
template = await PromptTemplateService.get_by_type_and_scenario(
    prompt_type="evaluation",
    scenario_id="sales_bot"
)

# 渲染模板
renderer = PromptRenderer(template)
rendered = await renderer.render({
    "conversation_history": messages,
    "stage_name": "需求挖掘"
})
```

### Staged Evaluation System (分阶段评估系统)

基于触发器的对话分阶段评估系统，将长对话划分为多个阶段进行独立评估。

**触发器类型** (`evaluation/triggers/`):
- `KeywordTrigger` - 关键词匹配触发
- `TimeIntervalTrigger` - 时间间隔触发
- `TurnCountTrigger` - 回合数触发
- `StageTransitionTrigger` - 阶段转换触发

**核心服务**:
```python
from evaluation.services.staged_evaluation import StagedEvaluationService

evaluation_service = StagedEvaluationService(db_session)

# 处理新消息，检测是否需要触发阶段评估
result = await evaluation_service.process_message(
    session_id=session_id,
    message=new_message,
    stage_configs=configs
)
```

**数据表**:
- `staged_evaluation_results` - 各阶段评估结果
- `comprehensive_reports` - 综合评估报告

### TTS 服务与降级机制

多层级 TTS 服务架构，支持自动降级和流式输出。

**服务层级** (`TTSProvider`):
```python
- ALIYUN   # 阿里云 DashScope (推荐，延迟 <200ms)
- EDGE     # Edge-TTS (免费备用)
- BROWSER  # 浏览器 TTS (最终降级)
```

**使用示例**:
```python
from common.audio.tts_factory import TTSServiceFactory, TTSProvider

# 使用工厂创建服务
tts_service = TTSServiceFactory.create(TTSProvider.ALIYUN.value)

# 流式生成音频
async for audio_chunk in tts_service.generate_stream(text="你好"):
    if audio_chunk.is_success:
        yield audio_chunk.value
```

**降级策略**:
1. 阿里云失败 → 自动降级到 Edge-TTS
2. Edge-TTS 失败 → 通知前端使用浏览器 TTS
3. 所有降级操作对上层透明

## 核心架构模式

### 0. 测试驱动开发

本项目遵循测试金字塔原则：
- **70% 单元测试**: 测试单个函数和类
- **20% 集成测试**: 测试模块间交互
- **10% 性能测试**: 测试 50 并发、延迟等

```python
# 单元测试示例
@pytest.mark.asyncio
async def test_asr_transcribe_success():
    asr = ASRService()
    result = await asr.transcribe(b"fake_audio_data")
    assert result.is_success
    assert result.value == "expected_text"
```

### 1. 错误处理: Result[T] 模式

所有函数返回 Result 类型而非抛出异常（用户可见代码）：

```python
from common.error_handling.result import Result

async def transcribe_audio(audio: bytes) -> Result[str]:
    try:
        text = await asr_service.transcribe(audio)
        return Result.ok(text)
    except ASRServiceUnavailable:
        return Result.fail("[USE_BROWSER_ASR]")  # 通知客户端切换
```

### 2. WebSocket 处理: BaseWebSocketHandler

所有 WebSocket 继承自基类，使用队列处理消息：

```python
from common.websocket.base_handler import BaseWebSocketHandler

class PresentationWebSocketHandler(BaseWebSocketHandler):
    def __init__(self):
        super().__init__(scenario="presentation")

    async def handle_message(self, message: dict):
        # 处理消息，不阻塞
        pass
```

### 3. 前端 API 客户端

统一使用 `lib/api/client.ts` 进行 API 调用，自动处理认证和错误：

```typescript
import { api } from '@/lib/api/client';

const agents = await api.admin.getAgents({ page: 1, page_size: 20 });
```

## 前端设计系统

### CSS 变量 (内联 @theme)

```css
/* 背景 */
--color-bg-main: #FAFAF9 (stone-50)
--color-bg-card: #FFFFFF

/* 文字 */
--color-text-primary: #18181B (zinc-950)
--color-text-secondary: #71717A (zinc-500)

/* 阴影 (自定义) */
--shadow-card: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02)
--shadow-float: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.01)

/* 圆角 */
--radius-subtle: 1rem (16px)
--radius-medium: 1.5rem (24px)
```

### 组件位置

- `components/ui/` - 通用原子组件 (glass-card, button, input)
- `components/layout/` - 布局组件 (sidebar, navigation)

## 关键决策树

```
遇到问题时:
├─ 前后端联调？ → 优先改前端
├─ 样式问题？ → 修改 CSS 变量或组件
├─ API 问题？ → 查 docs/api-contract/
└─ 代码报错？ → 检查版本语法 (SQLAlchemy 2.0, Pydantic v2)

新建文件时:
├─ 后端 API → backend/src/{module}/api/
├─ 能力模块 → backend/src/agent/capabilities/
├─ WebSocket → backend/src/{module}/websocket/
├─ 前端组件 → web/src/components/ui/
├─ 前端页面 → web/src/app/
└─ 测试文件 → backend/tests/{unit|integration}/
```

## 开发前必读文档

| 开发内容 | 必读文档 |
|----------|----------|
| 销售教练/对练功能 | `docs/roadmap/sales-coach-upgrade.md` |
| 新页面/前端功能 | `docs/roadmap/frontend-pages-spec.md` |
| 后端新 API/能力 | `docs/roadmap/backend-gap-analysis.md` |
| API 接口规范 | `docs/api-contract/` |
| 提示词模板系统 | `docs/specs/B-prompt-template-system.md` |
| 分阶段评估系统 | `docs/specs/C-staged-evaluation-system.md` |
| 代码审查知识库 | `docs/code-review/knowledge-system-full-analysis.md` |
| 系统深度分析 | `docs/system-deep-analysis-report.md` |
| 修复报告 | `docs/deep-repair-completion-report.md` |
| 后端原则 | `.kiro/steering/backend-principles.md` |
| 前端原则 | `.kiro/steering/frontend-principles.md` |
| 快速参考 | `.kiro/steering/QUICK-REFERENCE.md` |

## Claude Code 并行开发 (Agent Teams)

### 文档索引
- **完整文档索引**: https://code.claude.com/docs/llms.txt
- **Agent Teams 文档**: https://code.claude.com/docs/agent-teams

### 启用 Agent Teams
在 `settings.json` 或环境变量中启用:
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### 适用场景

| 场景 | 描述 |
|------|------|
| **研究与审查** | 多个 teammate 同时调查问题的不同方面 |
| **新模块/功能** | 每个 teammate 负责独立的模块 |
| **竞争假设调试** | teammate 并行测试不同理论 |
| **跨层协调** | 前端、后端、测试各由不同 teammate 负责 |

### 与 Subagents 对比

| 特性 | Subagents | Agent Teams |
|------|-----------|-------------|
| **上下文** | 独立窗口，结果返回调用者 | 独立窗口，完全独立 |
| **通信** | 只向主 agent 报告 | teammate 之间直接消息 |
| **协调** | 主 agent 管理所有工作 | 共享任务列表，自协调 |
| **最佳用例** | 只需结果的专注任务 | 需要讨论和协作的复杂工作 |
| **Token 成本** | 较低 | 较高 |

### 最佳实践
1. **给 teammate 足够上下文** - 在 spawn prompt 中包含任务特定细节
2. **任务大小适中** - 自包含单元，产生清晰交付物
3. **等待 teammate 完成** - 不要让 lead 抢先实现任务
4. **从研究和审查开始** - 清晰边界、不需写代码的任务
5. **避免文件冲突** - 每个 teammate 拥有不同的文件集
6. **监控和引导** - 检查进度，重定向无效方法

### 显示模式
- **In-process**: 所有 teammate 在主终端内运行 (Shift+Up/Down 切换)
- **Split panes**: 每个 teammate 独立分屏 (需要 tmux 或 iTerm2)

## API 契约 (已完成实现)

- `agents.md` - Agent 管理 API
- `personas.md` - Persona 管理 API
- `knowledge.md` - 知识库管理 API
- `websocket.md` - WebSocket 消息协议
- `replay.md` - 对话回放 API

## 类型定义位置

- `web/src/lib/api/types.ts` - 所有 API 类型定义
- `backend/src/common/db/schemas.py` - Pydantic 模型

## 性能边界条件

| 指标 | 限制 | 超限处理 |
|------|------|----------|
| WebSocket 连接数 | 50/实例 | 拒绝新连接 |
| 单会话时长 | 30 分钟 | 自动结束 |
| LLM 响应超时 | 10 秒 | 返回预定义响应 |

## 提交前检查

```
□ ruff check 通过
□ ruff format 已执行
□ mypy 类型检查通过
□ 无 print() 语句 (使用 logger)
□ 使用 Result[T] 包装错误
□ 前端无 alert/popup
□ API 响应格式正确 (success/data/error/trace_id)
□ 新增环境变量已添加到 .env.example
□ 数据库迁移已创建 (如有模型变更)
□ 单元测试通过
□ 前端 build 成功
```

## 日志与调试

### 后端日志
- 使用 `structlog` 进行结构化日志记录
- 所有日志包含 `trace_id` 用于追踪请求链路
- 日志级别通过 `LOG_LEVEL` 环境变量配置
- 查看 WebSocket 日志: 设置 `WEBSOCKET_DEBUG=true`

### TTS 调试
```python
# 查看 TTS 降级日志
logger.info("TTS fallback triggered", provider="aliyun", fallback_to="edge")

# 测试 TTS 服务
python -c "from common.audio.tts_factory import TTSServiceFactory; \
           tts = TTSServiceFactory.create('aliyun'); \
           print('TTS service created successfully')"
```

### 前端调试
- 使用 `use-practice-websocket.ts` 中的状态进行调试
- 浏览器 DevTools Network 标签页查看 WebSocket 消息
- 使用 `--watch` 模式进行开发时自动热重载
- 调试工具: `lib/debug.ts` 提供性能追踪和日志工具

### 常见问题排查
| 问题 | 可能原因 | 解决方法 |
|------|----------|----------|
| WebSocket 连接失败 | 后端未启动/端口错误 | 检查后端是否在 3444 端口运行 |
| ASR 转录超时 | 模型未下载/网络问题 | 首次运行会自动下载模型，请耐心等待 |
| TTS 无声音 | 浏览器自动播放策略 | 确保用户已与页面交互（点击/触摸） |
| TTS 降级频繁 | 阿里云 API Key 无效 | 检查 `ALIYUN_DASHSCOPE_API_KEY` |
| 数据库连接失败 | SQLite 文件权限问题 | 检查 `backend/data/` 目录权限 |
| 前端样式异常 | Tailwind 缓存问题 | 重启 `npm run dev` 或清除 `.next` 目录 |

## 最近更新

### 2026-02-12
- **Agent Teams 文档集成**: 添加 Claude Code 并行开发指南
  - Agent Teams 启用方式
  - 适用场景和最佳实践
  - 与 Subagents 的对比
  - 显示模式配置

### 2026-02-06
- **TTS 服务降级机制**: 实现多层级 TTS 降级策略
  - 阿里云 DashScope 流式 TTS (推荐，延迟 <200ms)
  - Edge-TTS (免费备用)
  - 浏览器 TTS (最终降级)
  - 自动降级链: 阿里云 → Edge-TTS → 浏览器TTS
  - 新增: `TTSServiceFactory`, `AliyunStreamingTTSService`

### 2026-02-05
- **C4-C7**: 分阶段评估前端集成
  - 评估结果展示组件
  - 综合报告页面
  - 实时反馈优化

### 2026-02-04
- **C1-C3**: 实现分阶段评估系统 (Staged Evaluation System)
  - 触发器系统：关键词、时间间隔、回合数、阶段转换
  - 阶段评估服务与数据模型
  - 数据表：`staged_evaluation_results`, `comprehensive_reports`

### 2026-02-03
- **B7-B10**: 提示词模板系统完善
  - B7-B8: 迁移现有 Prompts 到模板系统
  - B9-B10: 前端提示词模板管理界面
  - Jinja2 模板渲染引擎
  - 模板版本管理与热重载
  - PromptType 分类系统

### 2026-02-02
- **WebSocket 组件化重构**: `sales_bot/websocket/components/`
  - `capability_processor.py` - 能力处理
  - `message_persistence.py` - 消息持久化
  - `tts_component.py` - TTS 组件

### 2026-01-15
- 添加数据分析优化和语音训练流式功能
- 修复 .gitignore 错误忽略前端 lib 目录

<!-- MANUAL ADDITIONS START -->
<!-- 手动添加的内容放在这里，不会被自动更新覆盖 -->
<!-- MANUAL ADDITIONS END -->
