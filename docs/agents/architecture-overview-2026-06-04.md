# 销售训练 Qoder 架构总览

> 生成时间：2026-06-04
> 生成方式：6 个只读 agent 并行扫描（结构/后端/前后端+数据/WS 实时子系统/配置与横切/综合），480 次工具调用，~498k tokens。
> 状态：**只读扫描报告**。未修改任何代码；所有结论带 file:line 证据；未读到/无法验证的项已标注"待澄清"。

---

## 1. 概述摘要

**产品**：Enterprise AI Intelligent Practice System — 集成企业微信的全双工语音 AI 演练平台。

**核心场景**：PPT 演讲复盘、销售对练、课程考核（examiner runtime）— 三者**全部走 WebSocket + 实时语音**。

**后端**：FastAPI + SQLAlchemy 2 (async) + Pydantic 2 + PostgreSQL + Redis + ChromaDB，Python 3.11+，全异步。`main.py` 仅 75 行，是 `app_factory.create_app()` 的薄壳。

**前端**：Next.js 16 + React 19 + Tailwind 4 + Zustand，App Router 模式，路由分 `(auth)` / `(dashboard)` / `(user)` / `admin` 四组。

**关键模式**：

- `Result[T]` 错误处理
- `BaseWebSocketHandler` + 三套业务 handler
- `TrainingRuntimeDescriptor` 插件系统 + `dispatch_scenario_plugin`
- TTS 降级链 (aliyun → edge → browser)
- KB Lock 强约束 grounding

**宪法锚点**：

- `AGENTS.md`（根目录）= L0 宪章
- `CLAUDE.md` = L3 操作手册
- 项目内 12 个 `*/AGENTS.md` = 子域"本地地图"，必须与代码同步

> ⚠️ **重要偏差**：仓库里**比 CLAUDE.md 描述的更多** — 至少多出 6 个目录：`supervisor/`、`curriculum_analytics/`、`training_runtime/`、`app_factory.py`、`app_lifespan.py`、`http_routes.py`、`websocket_routes.py`。CLAUDE.md 滞后，建议在 L1 `CONTEXT.md` 增补。

---

## 2. 模块地图

### 2.1 顶层目录

| 目录 | 角色 |
|------|------|
| `backend/` | FastAPI 后端（`src/` 是代码） |
| `web/` | Next.js 前端（`src/app/` 是 App Router） |
| `docs/` | API 契约、ADR、架构图 |
| `.claude/rules/` | L1/L2 协作规则 |
| `evidence/` | 演练产出物（录音、转写等） |
| `data/chromadb/` | 向量库持久化 |
| `backend/alembic/` | 数据库迁移 |
| `*.md`（根目录） | `AGENTS.md` (L0)、`CLAUDE.md` (L3)、`CONTEXT.md`、`PROJECT_AUDIT_REPORT.md`、`api_routing_audit.md` |

### 2.2 后端 `backend/src/` 关键包

| 包 | 角色 | 入口/关键文件 |
|----|------|--------------|
| `main.py` (75 行) | 入口薄壳 | `app = create_app()` |
| `app_factory.py` (~196) | FastAPI 工厂、middleware、lifespan | `create_app` |
| `app_lifespan.py` | startup/shutdown 钩子 | `lifespan` |
| `router_registry.py` | **单一权威**：所有 HTTP router 装配 | `_build_knowledge_bases_alias_router` 在 :68（**潜在歧义**） |
| `http_routes.py` / `websocket_routes.py` | HTTP/WS 路由顶层挂载 | `register_websocket_routes` 在 :348 |
| `common/` | **平台内核**：auth/audio/db/knowledge/websocket/ai/error_handling/resilience/rate_limit/cache/storage/conversation/monitoring/validation/knowledge_engine/analytics/business_rules/growth/jobs/e2e/effectiveness/oss/cos/ppt/middleware | `result.py`、`runtime_gate.py`、`base_handler.py`、`tts_factory.py`、`aliyun_streaming_tts.py`、`kb_lock_guard.py` |
| `sales_bot/` | 销售对练场景；`websocket/components/` 下 21 个 stepfun_* 组件 | `api/scenarios.py`、`websocket/router.py`、`websocket/stepfun_realtime_handler.py` |
| `presentation_coach/` | PPT 演讲场景 | `api/presentations.py`、`websocket/presentation_handler.py` |
| `curriculum_practice/` | 课程/题库/考官 runtime；`api.py` 2542 行 9 router | `api.py`、`services/practice_templates.py`、`websocket/router.py`、`websocket/examiner_runtime.py` |
| `sales_trainer/` | 新人训练/试卷/重判；`api.py` 1285 行 + 56 个 service | `api.py`、`router_registration.py` |
| `training_runtime/` | **运行时描述符 + 插件分发**（被三个 runtime 共用） | `plugins.py` (`dispatch_scenario_plugin`)、`models.py`、`stepfun_transport.py` |
| `agent/` | Agent 平台（agent/persona CRUD + capability runner） | `capabilities/{runner,registry,base,knowledge_retrieval,fuzzy_detection,sales_stage,realtime_scoring}.py` |
| `prompt_templates/` | 提示词模板 + 场景模板 | `api/routes.py` |
| `evaluation/` | 分阶段评估 | `services/staged_evaluation.py` |
| `admin/` | 治理/配置中心/审计/版本验证 | `api/governance.py`、`api/config_assets.py`、`api/config_bundles.py` |
| `support/` | 运行状态/可观测 | `services/runtime_status_service.py` |
| `supervisor/` | （CLAUDE.md 未提，**待澄清职责**） | — |
| `curriculum_analytics/` | 学习路径/考试数据聚合 | `service.py` |

### 2.3 前端 `web/src/app/` 路由

| 路由组 | 路由 | 用途 |
|--------|------|------|
| `(auth)/` | login | 共享密码登录 |
| `(dashboard)/` | dashboard | 学员主面板 |
| `(user)/practice/[sessionId]` | page + report | 销售/PPT 演练主页面 + 报告 |
| `(user)/exam/[sessionId]` | — | 课程考核会话 |
| `(user)/learning-path` / `study/[id]` | — | 学习路径/章节学习 |
| `admin/` | agents/personas/presentations/presentation-ai/prompts/voice-runtime/knowledge/users/records/analytics/settings/curriculum | 管理后台（**含 curriculum 子区**） |

### 2.4 数据层

- **ORM**：`backend/src/common/db/models.py`（按 scenario 前缀命名）。
- **迁移**：`backend/alembic/versions/`。
- **向量**：`common/knowledge/`（ChromaDB），KB Lock 强约束在 `common/knowledge/kb_lock_guard.py`。
- **缓存/会话**：`common/cache/redis_cache.py`，常用作 PubSub + 缓存。

### 2.5 配置层

- `backend/.env.example` — TTS/ASR/StepFun/DB/Redis/Auth 全部环境变量。
- `web/.env.example` — 前端 API 地址。
- 运行时配置：**有 DB-backed 动态配置**（在 `admin/api/config_center.py`、`config_assets/`），优先级：DB > env > 默认值。
- Feature flag：靠 env（如 `DEFAULT_VOICE_MODE=stepfun_realtime`）+ `common/api/feature_flags.py`。

---

## 3. 关键调用链

### 3.1 用户发起"销售对练"（最关键流程）

| # | 层 | 文件:行 | 行为 |
|---|----|---------|------|
| 1 | 前端 | `web/src/app/(user)/practice/[sessionId]/page.tsx:1` | 学员进入练习页，调用 api client |
| 2 | API | `backend/src/common/api/practice.py:306` | `POST /api/v1/practice/sessions` → `PracticeRouteServices.session_create.create_session` |
| 3 | WS | `backend/src/sales_bot/websocket/router.py:71` | `GET /ws/sales/{session_id}`（query token 已弃用，走 `Authorization: Bearer`） |
| 4 | 鉴权 | `router.py:188` | 校验 session_id，从 PracticeSession 解析 voice_mode/agent_id/persona_id，调用 `RuntimeGate.admit_session` |
| 5 | 分发 | `router.py:445` | 构造 `TrainingRuntimeDescriptor(scenario_type=sales, voice_mode=stepfun_realtime)` → `dispatch_scenario_plugin` |
| 6 | Handler | `sales_bot/websocket/stepfun_realtime_handler.py:238` | `StepFunRealtimeHandler.handle_connection`（6 个 mixin 组合） |
| 7 | 传输 | `stepfun_realtime_connection.py:1` | 打开 StepFun 上游 WS，下发 `session.update`（含 VoiceRuntimeProfile + 角色扮演契约） |
| 8 | 音频 | `realtime_audio_flow.py:1` | 客户端二进制帧 `0x01`/`0x02` ↔ StepFun 上行 ↔ `tts_audio` 下行；消息由 `components/message_persistence.py` 持久化 |
| 9 | 能力 | `components/capability_processor.py:1` | fuzzy detection / realtime scoring / sales stage 三件套 + RealtimeFeedbackArbiter 仲裁；每轮评估 KB Lock |

### 3.2 用户上传 PPT 并开始 PPT 演练

| # | 文件:行 | 行为 |
|---|---------|------|
| 1 | `web/src/app/admin/presentations:1` | admin 上传 PPT（multipart POST /api/v1/presentations） |
| 2 | `backend/src/presentation_coach/api/presentations.py:523` | 校验文件 → `_atomic_write_bytes` → 写 Presentation(status=processing) |
| 3 | `presentation_coach/services/ppt_parser.py:1` | 解析、存缩略图；**OCR 后台任务尚未落地**（备份文件 `presentations.py.backup:91` 仍 TODO） |
| 4 | `websocket_routes.py:237` | 学员 `/practice/{sessionId}`，客户端建 `/ws/presentation/{session_id}` |
| 5 | `websocket_routes.py:291` | `RuntimeGate.admit_session(expected_runtime_type=presentation)` |
| 6 | `presentation_coach/websocket/presentation_handler.py:52` | 准入后 `PresentationWebSocketHandler` 接棒（若 voice_mode=stepfun_realtime 则走 `presentation_stepfun_realtime_handler.py`，复用 sales transport + 加 PPT 上下文） |
| 7 | `coach_service.py:1` | 音频入 → ASR (`common/audio/asr_service.py`) → point_tracker / interruption_detector / coach_service 编排 → TTS 出 |
| 8 | `common/websocket/session_state_service.py:1` | 状态通过 `SessionStateSnapshot` 持久化；`SessionLifecycleService` 推进生命周期 |

### 3.3 管理员发布练习模板/场景配置

| # | 文件:行 | 行为 |
|---|---------|------|
| 1 | `web/src/app/admin/curriculum:1` | admin UI → `POST /api/v1/curriculum-practices/templates/{template_id}/publish` |
| 2 | `curriculum_practice/api.py:1905` | `publish_practice_template` → `PracticeTemplateService.publish_template` |
| 3 | `services/practice_templates.py:115` | 若已发布，先 `stage_publish_working_revision`（不走直接列更新） |
| 4 | `practice_templates.py:136` | `validate_current_template` 返回 `PublishGateDecision`（can_publish + 各 gate 结果） |
| 5 | `practice_templates.py:142` | 翻 `status=published`，写 `content_hash`、`published_asset_refs`、`situation_pack_code` |
| 6 | `practice_templates.py:150` | `stage_initial_published_revision` 写审计行；`serialize_template` + `published_ref` 装配响应 |
| 7 | `api.py:1942` | 返回；admin UI 失效缓存（materials / examiner-agents refs） |
| 8 | `api.py:1695` | `runtime_dossier_preview` 预算 roleplay contract，WebSocket 启动时直接消费 |

---

## 4. 高风险 / 高耦合区域（Top 7）

### 4.1 StepFunRealtimeHandler 万行类

- **位置**：`backend/src/sales_bot/websocket/stepfun_realtime_handler.py`（1157 行） + 6 个 mixin（`stepfun_realtime_{connection,policy,upstream,feedback,sales_stage,state}.py`） + 1300 行 `STEPFUN_RUNTIME_EVENT_INVENTORY`。
- **风险**：任何 transport / 语音策略 / KB Lock / 评分改动会横穿所有 mixin。
- **影响范围**：销售全部语音演练；评分、KB Lock、TTS chunk、roleplay disclosure、上游自愈全部受影响。
- **缓解**：拆为 `SessionDirector` + 关注点分离的 per-concern 类；`STEPFUN_RUNTIME_EVENT_INVENTORY` 独立 loader。

### 4.2 curriculum_practice/api.py 单文件 2542 行 + 9 router

- **位置**：`backend/src/curriculum_practice/api.py` + `services/{practice_templates,content_assets,test_bank,examiner_agents,roleplay_contracts}.py`。
- **风险**：模板/学习内容/案例/考官 Agent/角色画像/roleplay 全部塞一起；revision + payload + serializer 三件套每实体重复。
- **影响范围**：发布门、资产引用、模板生命周期一处改 admin + learner 双面错。
- **缓解**：按域拆子包（templates / learning_contents / examiner_agents / roleplay），三件套提为通用基类。

### 4.3 sales_trainer：api.py 1285 行 + 56 个 service

- **位置**：`backend/src/sales_trainer/api.py` + `router_registration.py`（挂 12 子路由）+ `services/` 下 56 文件。
- **风险**：多个 workflow 文件（`exam_paper_lifecycle/publish/revision`、`material_publish`）汇流到同一会话状态机。
- **影响范围**：改工作流/Schema 同时影响学员和 admin；不一致的 revision 状态会让已发布试卷孤立。
- **缓解**：把 revision 三件套合成通用 `WorkflowService` 基类；`permissions.py` 改为角色装饰器。

### 4.4 router_registry + 备份/弃用文件歧义

- **位置**：`backend/src/router_registry.py`（200+ 行） + `sales_trainer/router_registration.py` + `presentation_coach/api/presentations.py.backup` + `evaluation/websocket/broadcaster.py.backup` + `sales_bot/websocket/sales_handler.py.deprecated`。
- **风险**：`_build_knowledge_bases_alias_router` 静默镜像 `/admin/knowledge/*` 到 `/admin/knowledge-bases/*`；三个备份/弃用文件仍在盘上（**不参与 import graph，会腐烂**）。
- **影响范围**：两条 alias 路径可能漂移；误 import 死代码。
- **缓解**：删除 `.backup` / `.deprecated` 文件；alias 改单一路由；加 lint 阻止此类文件提交。

### 4.5 WebSocket router 三重复制

- **位置**：
  - `backend/src/sales_bot/websocket/router.py`
  - `backend/src/websocket_routes.py`
  - `backend/src/curriculum_practice/websocket/router.py`
  - 挂载入口：`websocket_routes.py:348` `register_websocket_routes`；runtime descriptor 构造在 `training_runtime/plugins.py:114,130,242,268`。
- **风险**：`_parse_session_id` / `_resolve_session_owner_id` / `_is_admin_user_id` / `_normalize_requested_voice_mode` / `_default_voice_mode` 三处各写一遍。
- **影响范围**：鉴权策略漂移（`sales_bot/AGENTS.md:39` 已显式标为 M020/S01/T01 风险）。
- **缓解**：抽 `WebsocketAuthGuard` + `RuntimeAdmissionRouter` 基类；策略表下沉到 `common/auth`；`training_runtime/plugins.py` 改为引用。

### 4.6 `voice_mode=legacy` 全局残留

- **位置**：
  - `backend/src/sales_bot/services/voice_runtime_policy.py:92`（`ALLOWED_VOICE_MODES`）
  - `backend/src/sales_bot/websocket/router.py`
  - `backend/src/sales_bot/websocket/voice_runtime_profile.py:144`（fallback 默认）
  - `backend/src/websocket_routes.py:285`（默认）
  - `backend/src/agent/schemas.py:91,100,114,121`（`deprecated=True` 字段）
- **风险**：已禁用的 legacy runtime 仍在默认/fallback 路径；schema 仍有 `deprecated=True` 字段。
- **影响范围**：误路由到 legacy 路径；pydantic schema 漂移。
- **缓解**：sales profile 默认改为 `stepfun_realtime`；presentation 保留独立默认；Alembic 迁移清理字段。

### 4.7 RuntimeGate 与 lifecycle hooks 耦合

- **位置**：`backend/src/common/services/runtime_gate.py`（`RuntimeGate.admit_session`） + `backend/src/common/services/session_runtime_lifecycle_hooks.py`（`mark_session_runtime_failed`）。
- **风险**：`RuntimeGate.admit_session` 被三处 WS 复用；reject 时统一调用 `mark_session_runtime_failed`。
- **影响范围**：任一 runtime 误标 session=failed，会静默关闭学员演练。
- **缓解**：把 admission 状态与 lifecycle 状态写入同一事务；加跨 runtime 一致性测试。

---

## 5. Legacy / 高腐点

| 文件:行 | 证据 | 建议 |
|---------|------|------|
| `backend/src/sales_bot/websocket/sales_handler.py.deprecated:0` | `AGENTS.md:37` 显式禁用，但 `training_runtime/plugins.py:LEGACY_SALES_HANDLER_MODULES` 仍在 runtime 校验 | **直接删除文件 + 删 guard list** |
| `backend/src/presentation_coach/api/presentations.py.backup:91` | 仍含 `# TODO: Add background task for OCR` | **删备份，OCR 任务要么落地要么写 ADR** |
| `backend/src/evaluation/websocket/broadcaster.py.backup:0` | 备份文件 | **删** |
| `backend/src/sales_bot/services/voice_runtime_policy.py:124-125` | `DEPRECATED_RUNTIME_PROFILE_FIELDS` / `DEPRECATED_AGENT_POLICY_FIELDS` 通过 `_assert_no_deprecated_*` 主动断言 | 写 Alembic 迁移清理 |
| `backend/src/agent/services/agent_service.py:37` | `DEPRECATED_AGENT_WRITE_FIELDS` 拒绝写 | 同上 |
| `backend/src/evaluation/services/staged_evaluation.py:153` | `# TODO: parameterize` 把 `scenario_type=sales` 写死 | 参数化 |
| `backend/src/sales_bot/services/bot_service.py:94,117` | `_build_legacy_langchain_chain` + `clear_inactive_legacy_sessions` 残留 | 确认无人调用后删除 |
| `backend/src/sales_bot/websocket/voice_runtime_profile.py:144` | profile 加载默认 `voice_mode="legacy"` | 改为 `stepfun_realtime` |

---

## 6. 推荐阅读顺序（新人 8–15 步）

1. `CLAUDE.md` — L3 操作手册（命令、端口、反模式列表）
2. `AGENTS.md` — L0 宪章（工程原则 + AI 协作）
3. `docs/architecture.md` — 系统大图与模块边界
4. `backend/src/main.py` (75 行) — 入口结构
5. `backend/src/router_registry.py` — **HTTP 路由权威清单**
6. `backend/src/training_runtime/AGENTS.md` + `plugins.py` — 三个 runtime 共用的描述符 + 插件分发
7. `backend/src/sales_bot/AGENTS.md` — 销售域最高复杂度热点 + **禁用的 legacy 路径**
8. `backend/src/sales_bot/websocket/router.py` — 销售 WS 入口与 admission 流
9. `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFunRealtimeHandler **先读 docstring 和 mixin 组合，再决定是否深读**
10. `backend/src/curriculum_practice/AGENTS.md` + `services/practice_templates.py` — 课程/考试 runtime
11. `backend/src/sales_trainer/AGENTS.md` — 培训任务/重判模块
12. `docs/api-contract/websocket.md` — WS 协议：`audio_chunk` / `audio_end` / `text` / `control` 入；`asr_transcript` / `tts_audio` / `error` / `heartbeat` 出
13. `.claude/rules/L2-project/ai-practice-system.md` — `Result[T]`、TTS 降级链、KB Lock、WS 管理、组件化解耦
14. `.claude/rules/L1-global/programming-patterns.md` — 通用编程模式
15. **可选**：`PROJECT_AUDIT_REPORT.md`、`api_routing_audit.md`、`type_debt_baseline.md`（在 root）— 大改前必读

---

## 7. 关键锚点速查

| 关注点 | 文件:行 | 标识 |
|--------|---------|------|
| FastAPI app 工厂 | `backend/src/app_factory.py` | `create_app` |
| HTTP router 注册 | `backend/src/router_registry.py` | `register_routers` |
| WS 顶层挂载 | `backend/src/websocket_routes.py:348` | `register_websocket_routes` |
| Sales WS 端点 | `backend/src/sales_bot/websocket/router.py:71` | `sales_websocket_with_path` |
| StepFun Handler | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:238` | `StepFunRealtimeHandler` |
| Presentation WS（legacy） | `backend/src/presentation_coach/websocket/presentation_handler.py:52` | `PresentationWebSocketHandler` |
| Presentation WS（stepfun 变体） | `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py:47` | `PresentationStepFunRealtimeHandler` |
| Examiner WS | `backend/src/curriculum_practice/websocket/router.py:51` | `examiner_websocket_with_path` |
| 模板发布 | `backend/src/curriculum_practice/services/practice_templates.py:115` | `publish_template` |
| 创建演练会话 | `backend/src/common/api/practice.py:306` | `start_session` |
| Runtime 准入 | `backend/src/common/services/runtime_gate.py` | `RuntimeGate.admit_session` |
| 插件分发 | `backend/src/training_runtime/plugins.py` | `dispatch_scenario_plugin` |
| 语音策略 | `backend/src/sales_bot/services/voice_runtime_policy.py` | `ALLOWED_VOICE_MODES` |
| TTS/ASR 降级 | `backend/src/common/audio/` | aliyun + edge + browser |
| 前端练习页 | `web/src/app/(user)/practice/[sessionId]/page.tsx` | — |
| 前端 Examiner WS Hook | `web/src/hooks/use-examiner-websocket.ts:133` | `/ws/curriculum/examiner/{sessionId}` |
| 协作规则（L2） | `.claude/rules/L2-project/ai-practice-system.md` | — |
| 协作规则（L1） | `.claude/rules/L1-global/programming-patterns.md` | — |

---

## 8. 给更强模型使用的精简上下文包

> 适合作为后续 LLM 的 system prompt 注入。约 14500 字符。

```markdown
# Enterprise AI Intelligent Practice System — Compressed Context Package

## Architecture Summary
Web(H5) enterprise AI practice platform on WeChat Work. Two realtime voice scenarios (PPT coaching, sales bot) over WebSockets via unified `BaseWebSocketHandler` + `TrainingRuntimeDescriptor` plugin system. Backend: FastAPI + Python 3.11 + SQLAlchemy 2 async + Pydantic 2 + PostgreSQL + Redis + ChromaDB + structlog. Frontend: Next.js 16 + React 19 + Tailwind 4 + Zustand. Three runtimes (sales, presentation, examiner) all dispatch through `backend/src/training_runtime/plugins.py:dispatch_scenario_plugin`. **Sales runtime is StepFun-Realtime only**; legacy ASR→LLM→TTS handlers (`base_sales_handler`/`enhanced_handler`/`simple_handler`) are explicitly banned (sales_bot/AGENTS.md:36-37). Presentation runtime: BaseWebSocketHandler (`presentation_coach/websocket/presentation_handler.py:52`) + parallel StepFun variant. Curriculum runtime: `ExaminerRuntime` (`curriculum_practice/websocket/examiner_runtime.py:152`).

## Module Map
- `backend/src/main.py` (75 LOC): thin shim, calls `app_factory.create_app()` + re-exports legacy presentation-WS helpers.
- `backend/src/app_factory.py` (~196): wires routers, middleware, lifespan; calls `register_routers(app)` + `register_websocket_routes(app)`.
- `backend/src/router_registry.py`: single source for HTTP routers; mounts 30+ APIRouter objects; builds a knowledge-bases alias at line 68 that mirrors `/admin/knowledge*` under `/admin/knowledge-bases*` (potential drift).
- `backend/src/websocket_routes.py`: presentation WS `/ws/presentation`, `/ws/presentation/{session_id}` at 237/257; `register_websocket_routes` at 348 mounts sales + examiner + presentation.
- `backend/src/sales_bot/websocket/router.py`: sales WS `/ws/sales`, `/ws/sales/{session_id}` at 47/71; auth posture inventoried at 38-44 (`SALES_WS_AUTH_POLICY`).
- `backend/src/curriculum_practice/websocket/router.py`: examiner WS at 36/51; handler `ExaminerWebSocketHandler` from `examiner_runtime.py`.
- `backend/src/training_runtime/`: `models.py` (descriptor), `service.py` (builder), `plugins.py` (registry + dispatch + `LEGACY_SALES_HANDLER_MODULES` ban), `stepfun_transport.py`.
- `backend/src/sales_bot/`: scenario/persona REST (`api/scenarios.py`), bot service, voice policy, WS with 21 components in `websocket/components/`.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`: largest file (1157 LOC). Class `StepFunRealtimeHandler` mixes `StepFunRealtimeConnectionMixin + Policy + Upstream + Feedback + SalesStage` on top of `StepFunRealtimeStateBase`. Frontend protocol declared at 246-252.
- `backend/src/presentation_coach/`: `api/presentations.py` (upload at 523), services (coach_service, point_tracker, interruption_detector, presentation_ai_policy_service, prompt_role_resolver), WS (`presentation_handler.py` legacy + `presentation_stepfun_realtime_handler.py`).
- `backend/src/curriculum_practice/`: `api.py` (2542 LOC, 9 routers), services for templates/learning_contents/case_items/examiner_agents/role_profiles/test_bank/roleplay. `services/practice_templates.py` is canonical publish lifecycle (38-153).
- `backend/src/sales_trainer/`: newcomer training + audio submission + exam papers + regrade. `api.py` (1285 LOC) + 56 services. `router_registration.py` mounts 12 sub-routers.
- `backend/src/admin/`: governance, config bundles, voice runtime, knowledge admin, training records, release verification, audit trail, interventions, scoring rulesets.
- `backend/src/common/`: `auth` (JWT + shared password), `audio` (ASR/TTS, fallback chain), `websocket` (BaseWebSocketHandler, SessionManager, SessionStateService), `db` (models + session), `services/runtime_gate.py` (admit_session), `services/session_runtime_lifecycle_hooks.py` (mark_session_runtime_failed), `knowledge` (ChromaDB), `error_handling/result.py` (Result[T]), `monitoring` (structlog, trace_id), `conversation` (storage + replay), `resilience` (circuit breaker, backoff), `rate_limit`, `validation`, `storage`.
- `web/src/app/`: `(auth)/`, `(dashboard)/`, `(user)/practice/[sessionId]`, `(user)/exam/[sessionId]`, `(user)/learning-path`, `(user)/study/[learningContentId]`, `admin/`. `web/src/hooks/use-examiner-websocket.ts:133` builds `/ws/curriculum/examiner/{sessionId}`.

## Key Data Flows
**Sales practice**: Frontend POST `/api/v1/practice/sessions` (common/api/practice.py:306) → `PracticeRouteServices.session_create.create_session` → return `session_id`+`voice_mode`. Frontend opens `/ws/sales/{session_id}` (sales_bot/websocket/router.py:71). Query `token` deprecated (77); prefer `Authorization: Bearer` via `resolve_websocket_auth`. Router validates session_id, fetches voice_mode/agent_id/persona_id (359-395), runs `RuntimeGate.admit_session` (303). If voice_mode=stepfun_realtime: dispatches `TrainingRuntimeDescriptor(scenario_type=sales, voice_mode=stepfun_realtime)` (445) → `dispatch_scenario_plugin` → `StepFunRealtimeHandler`. Handler opens StepFun upstream WS via connection mixin, applies `session.update` from `VoiceRuntimeProfile` + roleplay contract, then runs event loop: client `audio_chunk` (binary 0x01) / `audio_end` / `interrupt` (0x02) / `text` / `control` → realtime ASR+LLM+TTS → `tts_audio` / `asr_transcript` / `status` / `stage_update` / `error` / `heartbeat` events. Capability processor (fuzzy detection, realtime scoring, sales stage) and RealtimeFeedbackArbiter emit scoring rows; KB lock decision evaluated each turn; message persistence writes PracticeSession messages.

**PPT practice**: Admin POST `/api/v1/presentations` (presentations.py:523) → validate → write file → persist Presentation(status=processing) → `ppt_parser.parse_presentation` → thumbnails. Learner `/ws/presentation/{session_id}` (websocket_routes.py:257) → RuntimeGate.admit_session(expect=presentation) → PresentationWebSocketHandler. Binary audio in → ASR → point_tracker / interruption_detector / coach_service → TTS out. State saved via SessionStateSnapshot; lifecycle via SessionLifecycleService.

**Admin publishes practice template**: Admin POST `/api/v1/curriculum-practices/templates/{template_id}/publish` (curriculum_practice/api.py:1905) → `PracticeTemplateService.publish_template` (services/practice_templates.py:115). If already published, `stage_publish_working_revision` first. Otherwise `validate_current_template` returns `PublishGateDecision`. On success: status=published, content_hash, published_asset_refs, situation_pack_code persisted; `stage_initial_published_revision` writes audit row. `serialize_template` + `published_ref` shape response (api.py:1942-1944). `runtime_dossier_preview` (1695) pre-computes roleplay contract.

## Conventions
- **Result[T]** for all user-facing service layer: `Result.ok(value)` / `Result.fail("[CODE]")`; never raise.
- **WebSocket**: always extend `BaseWebSocketHandler`; `BINARY_AUDIO_CHUNK=0x01`, `BINARY_AUDIO_INTERRUPT=0x02`; preserve message-queue back-pressure; save state before close.
- **Auth**: `get_current_user` / `get_current_admin_user` / `require_role([...])`; WS via `resolve_websocket_auth` (Bearer → cookie → query_token compat).
- **Persistence**: SQLAlchemy 2 `select()`; `from_attributes = True`; Alembic migrations; lifespan startup (never `@app.on_event`).
- **Error surface**: never `alert()`; use state indicators + recovery buttons; backend shape `{"success": false, "error": "[CODE]", "message": "...", "trace_id": "..."}`.
- **KB lock**: when enabled, retrieval must succeed before AI responds; never silently fall back to web search.
- **Voice mode enum**: `"legacy"` or `"stepfun_realtime"`; sales rejects non-`stepfun_realtime` (sales_bot/websocket/router.py:215).
- **Logs**: structlog JSON; every log carries `trace_id`; sensitive keys masked.
- **Component naming**: helpers in `sales_bot/websocket/components/` use prefix `stepfun_*`; legacy `*_legacy_*` helpers kept as compatibility shims.

## Gotchas
1. `stepfun_realtime_handler.py` is 1157 LOC dominant hotspot (sales_bot/AGENTS.md:32-38). Mixins share state via `self._effective_policy`, `self._roleplay_disclosure_state`, `self._roleplay_repair_instruction`. Touching one mixin ripples.
2. `presentation_coach/api/presentations.py.backup` and `evaluation/websocket/broadcaster.py.backup` still on disk; backup:91 contains `TODO: Add background task for OCR`. Not in import graph.
3. `sales_bot/websocket/sales_handler.py.deprecated` on disk and explicitly banned (sales_bot/AGENTS.md:37). `training_runtime/plugins.py:LEGACY_SALES_HANDLER_MODULES` enforces ban at runtime.
4. `router_registry.py:_build_knowledge_bases_alias_router` (68) silently mirrors `/admin/knowledge/*` under `/admin/knowledge-bases/*`. Never edit the alias.
5. `curriculum_practice/api.py` is 2542 LOC with 9 routers. Templates, learning contents, case items, examiner agents, role profiles, roleplay situation packs, test bank all in one file. Revision/payload/serializer triplet repeats per entity.
6. Three WebSocket routers reimplement `_parse_session_id` / `_resolve_session_owner_id` / `_is_admin_user_id` / `_normalize_requested_voice_mode` / `_default_voice_mode`. Auth drift is real risk (sales_bot/AGENTS.md:39 inventories posture as M020/S01/T01).
7. `voice_mode=legacy` still accepted in `ALLOWED_VOICE_MODES` (voice_runtime_policy.py:92), still default in `websocket_routes.py:285`, still fallback in `voice_runtime_profile.py:144`, but legacy sales runtime is disabled. Dead branches inflate every path.
8. `stepfun_realtime_policy.py` has explicit `DEPRECATED_RUNTIME_PROFILE_FIELDS` (124), `DEPRECATED_AGENT_POLICY_FIELDS` (125) actively asserted in `_assert_no_deprecated_*` (1277-1297). Schema still has `deprecated=True` (agent/schemas.py:91-121).
9. Presentation upload/replace/delete has documented race conditions (presentations.py:57-180, M017/S03/T01). Replace in place is highest priority; delete while live sessions reference row can detach session state from presentation authority.
10. `PracticeTemplateRevisionService` invoked from `PracticeTemplateService.publish_template` (practice_templates.py:121-150). Working-revision staging for already-published templates means a `publish` call is non-trivial; never call without going through the service.
11. `RuntimeGate.admit_session` invoked by all three WS routers; on reject all call `mark_session_runtime_failed`. Lifecycle state and admission state persisted separately; drift breaks all three runtimes.
12. Frontend `use-examiner-websocket.ts:133` builds WS URL pattern; `web/src/hooks/websocket/transport.test.ts:27` confirms canonical presentation URL `ws://host:3444/api/v1/ws/presentation?session_id=...&agent_id=...&persona_id=...&voice_mode=stepfun_realtime&trace_id=...`. Match exactly when adding hooks.
13. `curriculum_practice/services/practice_templates.py:34` defines `PracticeTemplateNotEditableError`; archivers get 200, editors of archived templates get error. Editing a published template goes through `stage_future_revision`, not direct column update.
14. The AGENTS.md tree (12 files under `backend/src/*/AGENTS.md`) is the canonical local map; treat as part of the LLM collaboration contract and update when changing a subtree.
15. `type_debt_baseline.md`, `api_routing_audit.md`, `PROJECT_AUDIT_REPORT.md` in repo root capture current tech debt and routing hazards; read before large refactors.

## Quick Anchors
- FastAPI app factory: `backend/src/app_factory.py:create_app`
- HTTP router registry: `backend/src/router_registry.py:register_routers`
- WS mount: `backend/src/websocket_routes.py:register_websocket_routes`
- Sales WS endpoint: `backend/src/sales_bot/websocket/router.py:71` (`sales_websocket_with_path`)
- StepFun handler: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:238` (`StepFunRealtimeHandler`)
- Presentation WS: `backend/src/presentation_coach/websocket/presentation_handler.py:52` (`PresentationWebSocketHandler`)
- Examiner WS: `backend/src/curriculum_practice/websocket/router.py:51` (`examiner_websocket_with_path`)
- Template publish: `backend/src/curriculum_practice/services/practice_templates.py:115` (`publish_template`)
- Practice session create: `backend/src/common/api/practice.py:306` (`start_session`)
- Runtime admission: `backend/src/common/services/runtime_gate.py:RuntimeGate.admit_session`
- Plugin dispatch: `backend/src/training_runtime/plugins.py:dispatch_scenario_plugin`
- Voice runtime policy: `backend/src/sales_bot/services/voice_runtime_policy.py`
- TTS/ASR fallback: `backend/src/common/audio/` (aliyun + edge + browser)
- Frontend practice page: `web/src/app/(user)/practice/[sessionId]/page.tsx`
- Frontend examiner WS hook: `web/src/hooks/use-examiner-websocket.ts`
- Local LLM rules: `.claude/rules/L2-project/ai-practice-system.md` + `.claude/rules/L1-global/programming-patterns.md`
```

---

## 9. 待澄清（Open Questions）

- `supervisor/` 包的具体职责（CLAUDE.md 未提）。
- `curriculum_analytics/` 与 `admin/api/analytics_curriculum.py` 的边界（聚合 vs API）。
- `http_routes.py` 与 `router_registry.py` 的分工（`http_routes` 是再封装层？）。
- `app_lifespan.py` 中具体哪些 startup/shutdown 任务。
- 运行时配置中心 `admin/api/config_center.py` 与 `config_assets/`、`config_bundles/` 的差异。
- 三个 `.backup`/`.deprecated` 文件的实际创建时间与最后引用方。
- `voice_mode=legacy` 在 presentation runtime 中是否仍为有效路径（与 sales 不同）。

---

## 10. 工作流元数据

- **6 个 agent 并行扫描**：structure / backend / frontend+data / WS / config+cross-cutting / synthesis
- **工具调用**：480 次
- **token 消耗**：~498k
- **耗时**：~42 分钟
- **所有结论**：均带 file:line 证据；未读到/无法验证的项已标注
- **修改文件数**：0
