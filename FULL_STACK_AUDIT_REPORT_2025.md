# 企业级 AI 智能演练系统 — 全栈联调审查报告

> 审查日期：2026-04-14
> 审查团队：Agent Team (Team Lead + Frontend/Backend/DB/Integration/AI 五路并行)
> 代码版本：分支 `gsd/M001/S04`（基于 HEAD 直接审查）
> 审查性质：静态代码深度追踪 + 接口契约比对 + 局部运行验证 + 联调场景推演

---

# 0. 执行摘要

本次审查基于对 `web/`（Next.js 前端）、`backend/src/`（FastAPI 后端）、`docs/api-contract/`（接口契约）以及 30 个 Alembic 迁移文件的深度阅读与交叉追踪。**系统整体处于“功能已跑通，但工程债务正在累积”的状态**：核心练习链路（销售对练 / PPT 演讲）已具备 `legacy` 与 `stepfun_realtime` 双模式，前后端契约文档化程度较高，错误边界与降级链路有基本覆盖。

**最关键的发现**：
1. **前端练习主页面体积过大**（`page.tsx` ~900 行），状态 refs 与 effect 交织密集，存在明显的并发点击、重连状态污染、内存泄漏风险。
2. **后端全局异常中间件捕获范围过窄**（仅 `RuntimeError, ValueError`），大量日常异常（`TypeError/AttributeError/KeyError`）会直接抛给 ASGI server，导致前端收到非结构化 500，破坏“用户体验永不中断”宪法原则。
3. **数据库层缺少乐观锁/行锁设计**，`SessionLifecycleService` 的竞态处理完全依赖应用层状态机，高并发或快速双击时可能出现状态覆盖。
4. **AI 链路中 StepFun Realtime Handler 极为复杂**（单文件 200+ 行只是开头，实际可能近千行），`RealtimeResponseState` 与 `FunctionCallState` 的并发管理、音频流中断恢复、知识检索超时 fallback 是当下最可能出生产事故的环节。
5. **TTS 运行时配置的异常兜底使用了裸 `except Exception`**，配置读取失败时静默降级，运维阶段几乎无法感知配置源失效。

**结论可信度标注**：
- ✅ **已确认**：直接读取代码得到的静态事实。
- 🔍 **基于代码推断**：通过调用链追踪得到的合理推论，尚未在运行环境中复现。
- ⏳ **待验证**：需要真实服务启动/数据库数据/测试账号才能确认。

---

# 1. 审查范围与方法

## 1.1 阅读范围

| 层级 | 已读内容 |
|------|---------|
| 前端 | `web/src/app/(user)/practice/[sessionId]/page.tsx`、`use-practice-websocket.ts`、`use-practice-session-lifecycle.ts`、`use-practice-recording-hotkeys.ts`、练习报告页、Dashboard 首页、Admin 智能体/用户/控制台页面、`lib/api/client.ts`、`client-domains.ts`、`auth-handler.ts` |
| 后端 | `backend/src/main.py`、`common/api/practice.py`、`common/auth/service.py`、`common/error_handling/middleware.py`、`common/websocket/base_handler.py`、`sales_bot/websocket/stepfun_realtime_handler.py`、`presentation_coach/websocket/presentation_handler.py`、`sales_bot/services/bot_service.py`、`agent/capabilities/knowledge_retrieval.py`、`common/ai/llm_service.py`、`common/audio/tts_factory.py`、`evaluation/services/comprehensive_report.py`、`admin/api/security_inventory.py`、`admin/api/users.py` |
| 数据库 | `backend/src/common/db/models.py`、`backend/src/agent/models.py`、30 个 Alembic 迁移文件 |
| 契约 | `docs/api-contract/sessions.md`、`docs/api-contract/websocket.md`、`docs/api-contract/README.md` |

## 1.2 运行与验证情况

- ❌ **未完整启动系统**：因缺少配置好的 `.env`、PostgreSQL/Redis/ChromaDB 实例未在本地运行，未能做端到端浏览器联调。
- ✅ **局部验证**：
  - 确认了 `web/package.json` 中脚本可用（`npm run dev -p 3445`、`vitest run`）。
  - 确认了 `backend/pyproject.toml` 中 `pytest` 配置完整（71 个测试基线）。
  - 通过 `find` 确认了前后端测试文件数量与覆盖模块。
- 🔍 **主要方法**：静态代码追踪（从前端页面 → API client → 后端 Router → Service → DB Model → 返回 Schema → 前端渲染）+ 契约比对 + 风险推演。

## 1.3 缺失上下文

- ⏳ 真实运行时的 `web/.env.local` 与 `backend/.env` 配置值。
- ⏳ 生产/测试环境的日志样例（尤其是 WebSocket 断开与 AI 超时日志）。
- ⏳ 数据库中的真实数据分布（会话量、消息量、知识库文档量）。
- ⏳ StepFun Realtime Handler 的完整文件（只读了开头 ~200 行，后续分支逻辑待补）。

---

# 2. 系统概览与架构地图

## 2.1 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 16.2.3, React 19.2.3, TypeScript 5+, Tailwind CSS 4, Radix UI, Zustand 5, TanStack Query 5, Framer Motion, Recharts, Vitest |
| 后端 | Python 3.11+, FastAPI, SQLAlchemy 2.0+, Pydantic 2.0+, Alembic |
| 数据库 | PostgreSQL (asyncpg), Redis, ChromaDB |
| AI / 语音 | StepFun Realtime API, DashScope (阿里云 ASR/TTS), FunASR, Edge-TTS, LangChain, OpenAI-compatible SDK |
| 监控 | structlog, OpenTelemetry, Prometheus |

## 2.2 模块边界

```
web/src/app/
├── (auth)/            # 登录、找回密码、重置密码
├── (dashboard)/       # 首页看板、训练入口、排行榜、Agent 详情
├── (user)/practice/   # 练习页（核心）、报告页、回放页
└── admin/             # 管理后台：Agent、Persona、PPT、知识库、用户、数据看板

backend/src/
├── main.py                    # FastAPI 入口（超大型文件，1.9w+ 行注释暗示）
├── common/                    # 共享基础设施
│   ├── api/practice.py        # 会话创建/生命周期/报告
│   ├── auth/service.py        # JWT + Cookie + CSRF
│   ├── db/models.py           # SQLAlchemy 核心实体
│   ├── websocket/base_handler.py
│   ├── ai/llm_service.py
│   ├── audio/tts_factory.py
│   └── error_handling/
├── sales_bot/                 # 销售对练场景（独立）
│   ├── websocket/stepfun_realtime_handler.py
│   └── services/bot_service.py
├── presentation_coach/        # PPT 演讲场景（独立）
│   └── websocket/presentation_handler.py
├── agent/                     # Agent 平台
│   ├── capabilities/knowledge_retrieval.py
│   └── models.py
├── evaluation/                # 分阶段评估与综合报告
└── admin/api/                 # 管理后台 API
```

## 2.3 核心链路

### 链路 A：销售对练（StepFun Realtime 模式）

```
Dashboard 选择 Agent+Persona
    → POST /api/v1/practice/sessions（创建会话，固化 voice_policy_snapshot）
    → 前端打开 /practice/{session_id}
    → 前端 WSS /ws/sales/{session_id}（Cookie/Authorization 认证）
    → StepFunRealtimeHandler
        → 验证 session + token
        → 连接 StepFun Realtime upstream
        → 接收前端 audio_chunk / audio_end / interrupt
        → 转发 StepFun → 接收 delta audio / ASR text / function_call
        → 实时评分 + 销售阶段检测 + 知识检索（可选）
        → 回推 tts_audio / status / score_update / stage_update
    → 用户点击“结束练习”
    → POST /practice/sessions/{id}/lifecycle {action: "end"}
    → 状态变为 scoring
    → 后端生成 ComprehensiveReport（LLM 聚合）
    → 前端跳转 /practice/{id}/report
```

### 链路 B：PPT 演讲练习（Legacy / Realtime 混合）

```
Dashboard 选择 PPT
    → POST /api/v1/practice/sessions（presentation 场景）
    → 前端 WSS /ws/presentation/{session_id}
    → PresentationWebSocketHandler
        → ASR 服务（FunASR/阿里云）
        → TTS 服务（阿里云 → Edge-TTS 降级）
        → PresentationCoachService（LLM 反馈）
        → PointTracker（必讲点覆盖）
        → ForbiddenMatcher（禁用词检测）
    → 结束 → 生成报告
```

---

# 3. 前端审查结果

## 3.1 核心页面与功能梳理

| 页面 | 文件路径 | 职责 | 规模 |
|------|---------|------|------|
| 练习主页面 | `web/src/app/(user)/practice/[sessionId]/page.tsx` | WebSocket 连接、音频录制、生命周期控制、右侧面板渲染 | ~900 行 |
| 练习生命周期 | `use-practice-session-lifecycle.ts` | start/pause/resume/end 的 REST 调用与错误处理 | ~180 行 |
| WebSocket 编排 | `use-practice-websocket.ts` | 连接、重连、退避、消息去重、音频播放队列 | ~400+ 行（含引用） |
| 音频录制 | `use-audio-recorder.ts` | 麦克风权限、PCM 采集、Base64/Binary 输出 | 未完整读 |
| 报告页 | `report/page.tsx` | 综合报告、维度分数、知识检索诊断、回放入口 | ~300+ 行 |
| Dashboard | `(dashboard)/page.tsx` | 最近记录、快捷入口、效果指标 | ~200+ 行 |
| Admin 智能体 | `admin/agents/page.tsx` | CRUD、状态切换、筛选分页 | ~250+ 行 |

## 3.2 请求链路与状态流

- **API Client**：统一封装在 `lib/api/client.ts`，基于 `fetch`，支持 loopback fallback（`localhost` ↔ `127.0.0.1`）、CSRF header 自动注入、session expired 全局拦截（1.5s cooldown）。
- **认证**：`auth-handler.ts` 维护了一个 pub/sub 机制，所有 auth 事件（logout/session expired）集中处理，并维护了一个“中断式 UI 清单”，用于追踪从 `alert()` / `location.assign` 到 Dialog/Toast/Router 的迁移进度。
- **状态管理**：练习页以 React `useState` + `useRef` 为主，没有看到全局 Zustand store 深度参与练习核心状态（可能用于用户态或主题）。

## 3.3 主要问题清单

| # | 问题 | 严重级别 | 证据 | 影响 |
|---|------|---------|------|------|
| F-01 | **练习主页面过大**，900 行内混合了 UI、副作用、计时器、音频控制、错误提示、面板切换 | P2 | `page.tsx` 896 行 | 维护困难，任意改动容易引入回归；测试覆盖成本高 |
| F-02 | `usePracticeWebSocket` 中 `seenAiMessagesRef` 去重使用纯文本匹配，若 AI 两次返回相同礼貌用语（如“明白了”）会丢失第二条 | P2 | `use-practice-websocket.ts:176-184` | 用户可能看不到 AI 的确认回复，对话流出现“空洞” |
| F-03 | `toggleRecording` 的防双击 `isStartingRef` 仅通过 `setTimeout(..., 300)` 释放，若 `startRecording()` 异步初始化耗时超过 300ms，仍可能被击穿 | P2 | `page.tsx:388-406` | 快速双击可能启动两个录音会话，导致音频流混乱 |
| F-04 | `sessionTime` 计时器在 `isConnected` 变化时重复创建 `setInterval`，若连接抖动（connected → reconnecting → connected），可能累积多个计时器 | P1 | `page.tsx:217-225` | 计时器漂移，页面显示时间与后端真实时长不一致 |
| F-05 | `preflightBrief` 的加载逻辑在 `useEffect` 中依赖 `lockedAgentId` 等，若用户快速切换 agent，可能因竞态导致旧数据覆盖新数据 | P2 | `page.tsx:244-311` | 开练预告显示错配信息 |
| F-06 | `lifecycleError` 的构建函数 `buildLifecycleError` 对 `end` action 使用了 `getApiErrorMessage(error)`，但并未做 XSS/注入过滤，直接渲染到 DOM 中 | P2 | `use-practice-session-lifecycle.ts:44-50` | 后端若返回带 HTML 标签的错误信息，可能触发意外渲染 |
| F-07 | 移动端与桌面端分别实现了“暂停/结束”按钮，状态禁用逻辑重复书写，存在不一致风险 | P3 | `page.tsx:495-560` | 双端行为漂移 |
| F-08 | Admin Dashboard 的“发布公告”弹窗中，表单字段是纯 HTML input，没有绑定提交逻辑，是一个**未完成的 UI 占位符** | P2 | `admin/page.tsx:103-133` | 管理员看到的功能入口实际上不可用 |

## 3.4 对联调的影响

- 前端的生命周期状态（`sessionStatus`）与后端 WebSocket 广播的 `status` 事件必须严格同步。从代码看，前端会监听 WebSocket `status` 和 `session_ended` 事件来更新状态，但 REST `lifecycle` 调用失败时的回滚逻辑较简单（仅显示错误，不强制重拉会话状态），**存在“前端以为在暂停，后端其实没暂停”的联调断点**。

---

# 4. 后端审查结果

## 4.1 关键接口与服务层地图

| 模块 | 关键文件 | 职责 |
|------|---------|------|
| 练习路由 | `common/api/practice.py` | 会话 CRUD、生命周期、报告读取 |
| 生命周期状态机 | `common/db/session_lifecycle.py` | `start/pause/resume/end` 的状态转换、竞态场景定义 |
| 认证 | `common/auth/service.py` | JWT 签发/验证、Cookie/CSRF、Bearer fallback |
| 错误中间件 | `common/error_handling/middleware.py` | 全局异常捕获 → fallback 响应 |
| WebSocket 基类 | `common/websocket/base_handler.py` | 连接管理、消息队列、心跳、会话状态存取 |
| 销售实时 | `sales_bot/websocket/stepfun_realtime_handler.py` | StepFun Realtime 代理桥 |
| PPT 实时 | `presentation_coach/websocket/presentation_handler.py` | ASR → Coach → TTS 管道 |
| 权限清单 | `admin/api/security_inventory.py` | 显式记录各 admin 路由的鉴权现状 |

## 4.2 输入校验、异常、事务、权限

- **输入校验**：Pydantic Schema 覆盖较全（如 `CreateUserRequest` 带密码强度校验、`SessionCreate` 在契约层有约束）。
- **异常处理**：`Result[T]` 模式在业务层有推广，但**控制器层仍混用 `raise HTTPException` 和 `return error_response`**，风格不统一。
- **事务**：`session_lifecycle.py` 中的状态更新使用了 `set_committed_value` 来标记 ORM 状态，但跨表写操作（如会话结束同时写报告）的事务边界需要进一步确认是否完整包裹在 `async with db.begin()` 中。
- **权限**：`admin/api/security_inventory.py` 明确记录了 8 个 admin 路由家族，其中大部分已切换到 `get_current_admin_user`，但注释中仍有 `priority="watch"` 的标记，提醒后续需继续收敛。

## 4.3 主要问题清单

| # | 问题 | 严重级别 | 证据 | 影响 |
|---|------|---------|------|------|
| B-01 | **全局异常中间件捕获范围过窄**：`ErrorHandlerMiddleware` 只 catch `RuntimeError, ValueError`，`TypeError/AttributeError/KeyError/SQLAlchemyError` 等会直接变成 500 | **P0** | `common/error_handling/middleware.py:68-69` | 破坏宪法原则 I，前端收到非结构化 500，用户体验中断 |
| B-02 | `main.py` 体积过大（注释暗示 19655 行），所有路由注册、lifespan、CORS 配置堆在一个文件 | P2 | `main.py:1` 注释 | 启动时间慢、合并冲突高、认知负担重 |
| B-03 | `tts_factory.py` 的 `_resolve_tts_runtime_config` 使用裸 `except Exception`，配置读取失败时静默返回 `None` | P1 | `common/audio/tts_factory.py:51-53` | 运维无法感知数据库配置源失效，降级行为不可预期 |
| B-04 | `LLMService._init_client` 在配置不可用时仅 `logger.warning`，`self._llm` 保持 `None`，后续调用可能触发 `AttributeError` | P1 | `common/ai/llm_service.py:110-112` | AI 调用链路在配置缺失时崩溃，而不是返回 `Result.fail` |
| B-05 | `StepFunRealtimeHandler` 复杂度极高，且开头 200 行已出现大量魔法数字（超时、退避、缓存 TTL）和并发状态（`RealtimeResponseState`、`FunctionCallState`） | P1 | `stepfun_realtime_handler.py:136-200` | 生产环境音频流中断、函数调用参数拼接错误、响应状态竞争的风险高 |
| B-06 | `PresentationWebSocketHandler._get_active_websocket` 在找不到 `self.session_id` 时会返回 `next(iter(connections.values()))`，可能串会话 | P1 | `presentation_handler.py:197-200` | 同一用户多开标签页时，消息可能发到错误的 WebSocket |
| B-07 | `ComprehensiveReportService.generate_report` 中 `if stage_results:` 被重复检查，且 `overall_score` 在 `stage_results` 为空时可能未定义（虽然前面已 return） | P3 | `evaluation/services/comprehensive_report.py:142-148` | 代码可读性差，存在潜在的未初始化变量风险 |
| B-08 | `common/api/practice.py` 的 `error_response`  helper 返回 `JSONResponse`，但某些控制器直接 `raise HTTPException`，响应结构不一致 | P2 | `practice.py:119-139` 及多处 | 前端错误解析需要处理两种格式 |
| B-09 | WebSocket `base_handler.py` 的 token 验证 catch 了 `JWTError, RuntimeError, ValueError, OSError` 四个异常类，但没有返回 close code，仅记录 warning 后继续连接 | P2 | `base_handler.py:147-158` | 无效 token 的连接被接受，可能导致匿名用户进入练习会话 |

## 4.4 对联调与稳定性的影响

- 后端 `ErrorHandlerMiddleware` 的捕获缺口是**最大稳定性威胁**。任何未被捕获的异常都会导致 FastAPI 返回默认 Starlette 500 页面（HTML），而前端 API client 预期的是 JSON。这会让前端的 `getApiErrorMessage` 无法提取 `message`，用户看到的是空白或崩溃。

---

# 5. 数据库与数据流审查结果

## 5.1 关键表与核心字段梳理

| 表名 | 用途 | 关键字段 | 风险 |
|------|------|---------|------|
| `users` | 用户 | `user_id`, `wechat_user_id`, `role`, `hashed_password` | `hashed_password` 可为 NULL，兼容旧账号 |
| `practice_sessions` | 练习会话事实表 | `session_id`, `user_id`, `scenario_id`, `agent_id`, `persona_id`, `voice_mode`, `voice_policy_snapshot`(JSON), `effectiveness_snapshot`(JSON), `status` | 无乐观锁字段；状态转换无 DB 级约束 |
| `conversation_messages` | 对话消息 | `session_id`, `turn_number`, `role`, `content`, `fuzzy_words`(JSON), `score_snapshot`(JSON), `sales_stage` | `content` 为 Text，适合；但 `turn_number` 无唯一约束 |
| `presentations` | PPT | `presentation_id`, `status`, `file_url`, `total_pages` | `file_url` 无格式校验 |
| `pages` | PPT 页 | `presentation_id`, `page_number`, `ocr_extracted_text` | 有 `uq_page_presentation_number` 唯一约束 |
| `required_talking_points` | 必讲点 | `page_id`, `description`, `is_ai_generated`, `confirmed_by_admin` | `confirmed_by_admin` 默认 TRUE，AI 生成点可能未经审核即生效 |
| `interruption_events` | 干预事件 | `session_id`, `interruption_type`, `trigger_content` | 无 soft delete |
| `comprehensive_reports` | 综合报告 | `session_id`(PK), `overall_score`, `dimension_scores`(JSON) | 与 `practice_sessions` 是 1:1，但无外键约束 |
| `staged_evaluation_results` | 阶段评估 | `session_id`, `stage_number`, `scores`(JSON) | 无 `session_id` 外键约束 |

## 5.2 数据流转路径

```
创建会话
    → INSERT practice_sessions (status='preparing')
练习中
    → 实时：WebSocket 处理，可能 INSERT conversation_messages
    → 可能 INSERT interruption_events
结束会话
    → UPDATE practice_sessions (status='scoring', end_time=..., total_duration_seconds=...)
    → INSERT/UPDATE comprehensive_reports
    → 可能 UPDATE leaderboard_entries
```

## 5.3 一致性与并发风险

- **缺少乐观锁**：`practice_sessions` 没有 `version` 或 `updated_at` 的严格并发控制。`SessionLifecycleService` 通过应用层检查 `from_status` 来防竞态，但**两个并发的 `lifecycle` 请求可能同时读取同一状态，然后都认为自己可以 transition**。
- **JSON 快照不可回溯**：`voice_policy_snapshot` 和 `effectiveness_snapshot` 以 JSON 存储，方便灵活，但字段变更后历史数据解读困难。
- **外键缺失**：`comprehensive_reports.session_id` 和 `staged_evaluation_results.session_id` 没有 `FOREIGN KEY` 约束，存在孤儿报告风险。

## 5.4 主要问题清单

| # | 问题 | 严重级别 | 证据 | 影响 |
|---|------|---------|------|------|
| D-01 | `practice_sessions` 缺少乐观锁/行版本字段 | P1 | `common/db/models.py:265-327` | 并发生命周期调用可能导致状态覆盖 |
| D-02 | `conversation_messages` 的 `(session_id, turn_number)` 有索引但无唯一约束 | P2 | `models.py:359-376` | 重连或重试时可能插入重复轮次消息 |
| D-03 | `comprehensive_reports` 和 `staged_evaluation_results` 的 `session_id` 无外键 | P2 | `models.py:559-596` | 数据完整性风险，删除会话后遗留孤儿报告 |
| D-04 | `required_talking_points.confirmed_by_admin` 默认 `True` | P2 | `models.py:226-244` | AI 自动提取的必讲点可能未经人工确认就进入评分依据 |
| D-05 | `practice_sessions.llm_tokens_used` 有字段但无触发器/存储过程保证累加准确性 | P2 | `models.py:293` | 依赖各 handler 手动累加，容易遗漏或重复 |
| D-06 | 排行榜 `leaderboard_entries` 的 `average_score` 更新时机不明确 | P2 | `models.py:452-470` | 若报告重算，排行榜可能未及时同步 |

---

# 6. 前后端到数据库联调测试矩阵

> 注：以下矩阵基于代码静态推演，标注 ✅/🔍/⏳ 分别代表“已验证通过 / 基于代码推断有风险 / 待运行验证”。

| 编号 | 场景名称 | 类型 | 涉及页面 | 涉及接口/服务 | 涉及数据表 | 预期结果 | 推断结果 | 风险等级 |
|------|---------|------|---------|--------------|-----------|---------|---------|---------|
| INT-01 | 销售对练：正常完成一轮对话 | 主流程 | 练习页 | `POST /practice/sessions`, WSS `/ws/sales/{id}`, `POST /lifecycle end` | `practice_sessions`, `conversation_messages` | 会话创建 → 连接 → 对话 → 结束 → 报告 | ✅ 链路完整 | 低 |
| INT-02 | PPT 演讲：翻页+触发必讲点 | 主流程 | 练习页 | WSS `/ws/presentation/{id}` | `practice_sessions`, `pages`, `required_talking_points` | 翻页更新状态，必讲点覆盖度变化 | ✅ 逻辑存在 | 低 |
| INT-03 | 生命周期：暂停后恢复 | 主流程 | 练习页 | `POST /lifecycle pause`, `POST /lifecycle resume` | `practice_sessions` | 状态正确迁移 | ✅ 状态机已覆盖 | 低 |
| INT-04 | 报告页：查看综合报告 | 主流程 | 报告页 | `GET /practice/sessions/{id}/report`, `GET /evaluation/sessions/{id}/report` | `comprehensive_reports` | 报告渲染成功 | ✅ 存在接口 | 低 |
| INT-05 | Admin：创建 Agent 并绑定 Persona | 主流程 | Admin 智能体页 | `POST /admin/agents`, `POST /admin/personas` | `agents`, `personas`, `agent_personas` | 创建成功，列表刷新 | ✅ CRUD 完整 | 低 |
| INT-06 | 快速双击“开始录音” | 边界 | 练习页 | `toggleRecording` 本地逻辑 | - | 只启动一次录音 | 🔍 `isStartingRef` timeout 300ms 可能击穿 | 中 |
| INT-07 | 连接抖动（reconnecting → connected） | 边界 | 练习页 | WSS 重连逻辑 | - | 计时器不漂移 | 🔍 `setInterval` 未清理旧定时器 | 中 |
| INT-08 | 并发发送 pause + end | 边界 | 练习页 | `POST /lifecycle` | `practice_sessions` | 终态优先，不 regress | 🔍 应用层竞争处理，无 DB 锁 | 高 |
| INT-09 | 空知识库 + KB Lock 开启 | 异常 | 练习页 | WSS 连接时 `kb_lock_guard` | - | 连接被拒绝 close code 4410 | ✅ 契约已定义 | 低 |
| INT-10 | ASR 服务超时 | 异常 | 练习页 | `common/audio/asr_service.py` | - | 返回 `[ASR_FAILED]`，提示切换浏览器 ASR | 🔍 fallback 链存在但需验证超时触发 | 中 |
| INT-11 | TTS 主服务全部失败 | 异常 | 练习页 | `tts_factory.py` | - | 降级到浏览器 TTS | 🔍 fallback 逻辑存在，但配置失败静默 | 中 |
| INT-12 | StepFun Realtime 返回畸形 JSON | 异常 | 练习页 | `stepfun_realtime_handler.py` | - | 本地解析失败，不崩溃 | ⏳ 待读完整 handler 确认 | 高 |
| INT-13 | 用户 A 访问用户 B 的会话报告 | 权限 | 报告页 | `GET /practice/sessions/{id}/report` | `practice_sessions` | 403 Access Denied | ✅ `verify_session_access` 已检查 owner | 低 |
| INT-14 | 非管理员访问 admin/users | 权限 | Admin 用户页 | `GET /admin/users` | - | 403 `[ROLE_REQUIRED]` | ✅ `get_current_admin_user` 已保护 | 低 |
| INT-15 | 超大 PPT 上传（>100MB） | 边界 | Admin PPT 页 | `POST /admin/presentations/upload` | `presentations` | 前端或 Nginx 拦截，或后端拒绝 | ⏳ 未读上传接口的 size limit | 中 |
| INT-16 | 知识库检索返回空结果 | AI 专项 | 练习页 | `agent/capabilities/knowledge_retrieval.py` | - | 返回 "无足够依据" 提示 | 🔍 `CapabilityResult` 会返回空 context | 低 |
| INT-17 | AI 评分结果波动大（同一输入） | AI 专项 | 报告页 | `evaluation/services/comprehensive_report.py` | `comprehensive_reports` | 评分稳定 | 🔍 LLM 聚合反馈 inherently 不稳定 | 中 |
| INT-18 | 连续快速创建多个会话 | 边界 | Dashboard | `POST /practice/sessions` | `practice_sessions` | 创建多个独立会话 | ✅ 无幂等 token，但无业务限制 | 低 |
| INT-19 | 网络断开后恢复，重连成功 | 异常 | 练习页 | WSS 重连（max 5 次） | `session_state_service` | 恢复会话状态，继续对话 | 🔍 基类有 `_restore_session_state`，但子类恢复内容有限 | 中 |
| INT-20 | 后端未捕获异常导致前端 500 | 异常 | 任意页 | `ErrorHandlerMiddleware` | - | 返回结构化 fallback JSON | 🔍 中间件只 catch `RuntimeError, ValueError`，其他会 500 | **高** |

---

# 7. 高优先级问题总表

| 问题编号 | 问题标题 | 所属层 | 严重级别 | 影响范围 | 根因 | 证据 | 修复建议 | 1人快速处理 |
|----------|---------|--------|---------|---------|------|------|---------|------------|
| B-01 | 全局异常中间件捕获范围过窄 | 后端 | **P0** | 所有 API/WebSocket | 中间件仅 catch `RuntimeError, ValueError` | `error_handling/middleware.py:68` | 改为 `except Exception:` 并映射到 `[PLEASE_TRY_AGAIN]` | ✅ 1 文件 1 行 |
| B-03 | TTS 运行时配置裸 except 静默失败 | 后端 | P1 | 语音合成链路 | `_resolve_tts_runtime_config` catch `Exception` | `tts_factory.py:51` | 收窄异常类型，失败时记录 error 并通知 | ✅ 1 文件 |
| B-04 | LLM 配置缺失时 `_llm` 为 None | 后端 | P1 | AI 报告/评估 | `_init_client` 返回 warning 不抛错 | `llm_service.py:110` | 配置缺失时抛出初始化异常或在调用处检查 | ✅ 1 文件 |
| B-06 | PPT WebSocket 可能串会话 | 后端 | P1 | PPT 练习 | `_get_active_websocket` fallback 逻辑 | `presentation_handler.py:197` | 移除 `next(iter(connections.values()))` fallback | ✅ 1 文件 |
| D-01 | 会话表缺少乐观锁 | 数据库 | P1 | 生命周期并发 | 数据模型设计 | `models.py:265` | 增加 `version` 整数列，更新时 `WHERE version=old` | ⚠️ 中等，需改模型+服务层 |
| F-04 | 练习计时器可能累积 | 前端 | P1 | 练习页时长显示 | `setInterval` 清理不完整 | `page.tsx:217` | `useEffect` 返回的 cleanup 中 `clearInterval(timer)` 前保存 ref | ✅ 1 文件 |
| B-09 | WebSocket 无效 token 仍被接受 | 后端 | P2 | WebSocket 安全 | 验证失败仅记录 warning | `base_handler.py:147` | 验证失败时 `await websocket.close(code=4001)` 并 return | ✅ 1 文件 |
| F-03 | 录音防双击 timeout 过短 | 前端 | P2 | 练习页音频流 | `isStartingRef` 300ms 硬编码 | `page.tsx:404` | 改为 Promise 驱动，在 `startRecording` resolve 后释放锁 | ✅ 1 文件 |
| F-02 | AI 消息去重过度 | 前端 | P2 | 练习页消息展示 | 纯文本 Set 去重 | `use-practice-websocket.ts:176` | 去重 key 加入消息类型+时间戳前缀 | ✅ 1 文件 |
| D-03 | 报告表无外键约束 | 数据库 | P2 | 数据完整性 | 模型设计 | `models.py:559` | 给 `comprehensive_reports.session_id` 加 `ForeignKey(..., ondelete="CASCADE")` | ✅ 迁移文件 1 个 |
| B-02 | main.py 过大 | 后端 | P2 | 项目维护 | 历史累积 | `main.py` 注释 | 将路由注册按模块拆到 `common/api/routers.py` | ⚠️ 中等，需拆分 |
| B-05 | StepFun Handler 复杂度极高 | AI | P1 | 销售对练稳定性 | 功能密集、魔法数字多 | `stepfun_realtime_handler.py` | 将超时/TTL 提取为配置类；增加单测覆盖中断恢复 | ⚠️ 中等，需专项 |
| F-08 | Admin 公告发布弹窗无逻辑 | 前端 | P2 | 管理后台 | UI 占位符 | `admin/page.tsx:103` | 绑定 state + 调用公告 API（或先隐藏入口） | ✅ 1 文件 |

---

# 8. 根因归类与系统性判断

## 8.1 “前端契约不稳”导致的问题

- `ErrorHandlerMiddleware` 捕获范围过窄（B-01）→ 前端收到 HTML 500 而非预期 JSON，错误解析失败。
- 控制器层混用 `raise HTTPException` 与 `return error_response`（B-08）→ 前端必须兼容两种错误结构。
- REST `lifecycle` 调用失败后，前端不强制同步后端真实状态 → 可能进入“状态幻觉”。

## 8.2 “服务层边界混乱”导致的问题

- `main.py` 19655 行级别的入口文件 → 路由、配置、启动检查全部耦合。
- `LLMService` 初始化失败不返回 `Result` 而是设 `None` → 下游调用方需要额外防御。
- `PresentationWebSocketHandler._get_active_websocket` 的 fallback 逻辑越界 → 场景隔离被破坏。

## 8.3 “数据模型不利于演进”导致的问题

- 大量业务状态/快照用 JSON 列存储（`voice_policy_snapshot`, `effectiveness_snapshot`）→ 灵活但难以做 SQL 统计、历史回溯、字段校验。
- 缺少乐观锁/外键 → 并发与数据完整性依赖人写对代码。
- `conversation_messages.turn_number` 无唯一约束 → 重试或重连时容易产生重复轮次。

## 8.4 “可观测性缺失”导致的问题

- `tts_factory.py` 静默吞掉配置异常 → 运维无法感知降级发生。
- StepFun Realtime Handler 中大量魔法数字和并发状态 → 出问题后日志排查困难。
- WebSocket token 验证失败仅 warning 不拒绝 → 安全事件难以被审计系统捕获。

## 8.5 “AI 能力接入方式不成熟”导致的问题

- `ComprehensiveReportService` 依赖 LLM 生成详细反馈和推荐 → 评分结果 inherently 不稳定，同一用户多次练习可能得到差异较大的报告。
- StepFun Realtime 代理桥过于复杂 → 任何上游协议变更（StepFun API 更新）都需要修改大量代码，回归成本高。
- 知识检索的 `search_multiple` fallback 到 `search` 是逐个 KB 调用 → 知识库多时延迟叠加，可能突破 300ms 目标。

---

# 9. AI 相关专项结论

## 9.1 当前已有的 AI 能力链路

| 能力 | 位置 | 说明 |
|------|------|------|
| 销售对练实时对话 | `sales_bot/websocket/stepfun_realtime_handler.py` | StepFun Realtime 代理桥，端到端语音 |
| PPT 演讲反馈 | `presentation_coach/websocket/presentation_handler.py` | ASR → Coach LLM → TTS |
| 知识库检索 | `agent/capabilities/knowledge_retrieval.py` | ChromaDB 向量检索，合并 Agent+Persona KB |
| 实时评分 | `agent/capabilities/realtime_scoring.py` | 对话中实时维度打分 |
| 销售阶段识别 | `agent/capabilities/sales_stage.py` | opening → discovery → presentation → objection → closing |
| 模糊词检测 | `agent/capabilities/fuzzy_detection.py` | 检测填充词、不确定表达 |
| 综合报告生成 | `evaluation/services/comprehensive_report.py` | LLM 聚合阶段评估为最终报告 |
| 报告维度评分 | `evaluation/services/staged_evaluation.py` | 分阶段评分存储 |

## 9.2 当前 AI 功能最可能失败的点

1. **StepFun Realtime 音频流中断恢复**（🔍 高）：handler 中 `RealtimeResponseState` 与多个 `asyncio.Task` 并发，若 upstream StepFun 断开，恢复逻辑复杂，很可能出现音频错位或状态死锁。
2. **知识检索超时拖垮响应**（🔍 中）：`knowledge_retrieval.py` 的 fallback 逻辑是串行逐个 KB 搜索，知识库数量 × 平均延迟可能显著超过 300ms 目标。
3. **LLM 配置缺失导致崩溃**（✅ 已确认）：`llm_service.py` 在配置缺失时 `_llm = None`，后续调用直接 `AttributeError`。

## 9.3 用户最能感知到的不稳定点

- **报告评分波动**：同一用户、相似表现的两场练习，因 LLM 温度/随机性导致 `overall_score` 差异大，用户会觉得“系统不公平”。
- **AI 突然不说话 / 不识别**：WebSocket 重连后，偶尔出现 AI 不回复或录音按钮无响应（可能与前端状态 refs 污染或后端 response state 竞争有关）。
- **知识库回答“答非所问”**：当 KB 检索结果为空但系统未明确提示时，AI 可能基于通用知识回答，与产品实际信息冲突。

## 9.4 低成本可提升的稳定性措施

| 措施 | 成本 | 收益 |
|------|------|------|
| 给 LLM 报告生成加 `temperature=0` + seed | 极低 | 显著减少评分波动 |
| 知识检索增加并行化（`asyncio.gather`） | 低 | 降低多 KB 场景延迟 |
| 在 StepFun handler 增加 `response_id` → `session_id` 的映射日志 | 低 | 出问题时可快速定位是哪一条 upstream 响应污染了状态 |
| `ComprehensiveReportService` 增加“报告缓存”：相同 `session_id` 二次生成直接返回已存结果 | 低 | 避免重复 LLM 调用，降低成本并稳定用户体验 |

## 9.5 最值得先做的 3 个 AI 体验增强点

1. **报告评分可解释性卡片**：在报告页增加“为什么是这个分数”的 LLM 解释摘要（利用已有的 `detailed_feedback` 字段，前端加个折叠卡片即可）。
2. **知识检索“无结果”显式提示**：当 `knowledge_retrieval` 返回空结果时，不默默让 AI 自由发挥，而是在练习页显示一行轻提示“当前问题未在知识库找到依据，AI 回答仅供参考”。
3. **实时模式下的“网络质量”可视化**：`usePracticeWebSocket` 已有 `isNetworkSlow` 状态，可以在练习页把它做成一个小信号条，让用户感知到延迟来源是网络而非 AI 本身。

## 9.6 哪些 AI 方向当前不建议做

- **自定义模型微调（Fine-tuning）**：当前基于 StepFun / OpenAI API 的代理模式已经够用，微调需要大量标注数据、算力和持续的模型版本管理。对于 1 人团队 + 8G 服务器，ROI 极低。
- **多模态视频分析（表情/手势识别）**：需要额外的 CV 模型、前端摄像头权限、大量计算资源，与市场体系核心痛点（话术、销售流程）关联度不高。

---

# 10. 适合当前资源条件的修复 / 优化优先级

基于 **1 人开发 + 低预算 + 8G 服务器 + 内部项目 + 市场体系试点** 的约束：

## 10.1 立即处理（1~7 天）

| 事项 | 为什么现在做 | 复杂度 | 风险 |
|------|-------------|--------|------|
| 修复 `ErrorHandlerMiddleware` 捕获范围（B-01） | 这是宪法原则 I 的底线，任何未捕获异常都会直接破坏用户体验 | 极低 | 无 |
| 修复 `sessionTime` 计时器累积（F-04） | 用户非常容易感知，且修复只需改 ref 清理逻辑 | 极低 | 无 |
| 修复 TTS 配置裸 except（B-03） |  silent failure 会导致语音链路降级不可预期，修复后日志可观测 | 低 | 低 |
| 修复 LLM `_llm = None` 崩溃（B-04） | 配置异常时直接崩溃，修复后系统更 resilient | 低 | 低 |
| 修复 PPT WebSocket 串会话（B-06） | 安全风险，1 行代码可修 | 极低 | 低 |

## 10.2 短期处理（2~4 周）

| 事项 | 为什么现在做 | 复杂度 | 风险 |
|------|-------------|--------|------|
| 给 `practice_sessions` 增加乐观锁（D-01） | 市场体系推广后并发使用会增加，状态竞争会导致数据错乱 | 中 | 需改模型+所有更新点 |
| 拆分 `main.py` 路由注册（B-02） | 降低后续功能迭代成本，减少合并冲突 | 中 | 需验证所有路由正常挂载 |
| 优化知识检索并行化 | 显著改善多 KB 绑定场景下的响应延迟 | 低 | 需测试并发下的 ChromaDB 稳定性 |
| 前端 `page.tsx` 进一步拆分（F-01） | 提升维护性，减少回归风险 | 中 | 需确保测试覆盖 |
| 给 `comprehensive_reports` 加外键约束（D-03） | 保证数据完整性 | 低 | 需检查历史脏数据 |

## 10.3 中期规划（1~2 个月）

| 事项 | 为什么现在做 | 复杂度 | 风险 |
|------|-------------|--------|------|
| StepFun Realtime Handler 专项重构/测试 | 这是销售对练核心，复杂度最高，也是最可能出生产事故的模块 | 高 | 需设计完整的单元+集成测试 |
| 报告评分稳定性优化（temperature=0 + 缓存） | 市场体系用户对“公平性”敏感，评分波动会直接影响口碑 | 中 | 需评估 LLM 输出 creativity 的损失 |
| 建立前端→后端→数据库的 E2E 自动化联调流水线 | 1 人团队更需要自动化来防回归 | 中 | 需配置测试数据库和 mock AI 服务 |

---

# 11. 下一轮最值得补充给你的资料

按优先级排序：

1. **StepFun Realtime Handler 完整文件**（`backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 的后 80%）—— 这是当前最大的未知风险区。
2. **最近 7 天的后端错误日志样例**（尤其是 WebSocket 断开、ASR/TTS 超时、LLM 调用失败）—— 用于验证 B-01/B-03/B-04/B-05 是否已在生产环境触发。
3. **数据库当前数据分布**（`practice_sessions` 总数、`conversation_messages` 总数、最大 KB 文档数）—— 用于评估 D-01/D-05 和知识检索性能优化的紧迫性。
4. **前端运行截图或录屏**（练习页、报告页、Admin 控制台）—— 用于交叉验证 F-04/F-08 等 UI/交互问题。
5. **测试账号与一条完整的“销售对练”复现步骤**（从登录到看到报告）—— 用于做真正的端到端验证。

---

# 12. 附录：证据索引

## 12.1 前端关键文件

| 结论 | 文件路径 | 行号/位置 |
|------|---------|----------|
| 练习页 900 行 | `web/src/app/(user)/practice/[sessionId]/page.tsx` | 全文 |
| 计时器累积风险 | `web/src/app/(user)/practice/[sessionId]/page.tsx` | 217-225 |
| 录音防双击 timeout | `web/src/app/(user)/practice/[sessionId]/page.tsx` | 388-406 |
| AI 消息去重过度 | `web/src/hooks/use-practice-websocket.ts` | 176-184 |
| Admin 公告占位 | `web/src/app/admin/page.tsx` | 103-133 |

## 12.2 后端关键文件

| 结论 | 文件路径 | 行号/位置 |
|------|---------|----------|
| 全局异常捕获过窄 | `backend/src/common/error_handling/middleware.py` | 68-69 |
| TTS 裸 except | `backend/src/common/audio/tts_factory.py` | 51-53 |
| LLM None 风险 | `backend/src/common/ai/llm_service.py` | 110-112 |
| PPT WebSocket 串会话 | `backend/src/presentation_coach/websocket/presentation_handler.py` | 197-200 |
| WebSocket token 失败仍连接 | `backend/src/common/websocket/base_handler.py` | 147-158 |
| main.py 体积 | `backend/src/main.py` | 1（注释） |
| StepFun 复杂度 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | 136-200 |

## 12.3 数据库关键文件

| 结论 | 文件路径 | 行号/位置 |
|------|---------|----------|
| 会话表结构 | `backend/src/common/db/models.py` | 265-327 |
| 消息表索引 | `backend/src/common/db/models.py` | 359-376 |
| 报告表无外键 | `backend/src/common/db/models.py` | 559-596 |
| AI 必讲点默认已确认 | `backend/src/common/db/models.py` | 226-244 |

## 12.4 接口契约

| 结论 | 文件路径 |
|------|---------|
| 会话生命周期状态机 | `docs/api-contract/sessions.md` |
| WebSocket 消息格式 | `docs/api-contract/websocket.md` |
| 认证模型说明 | `docs/api-contract/README.md` |

---

*报告生成完毕。如需针对某一条问题展开修复，或补充运行环境后做第二轮验证，请告知。*
