# AGENTS.md / CLAUDE.md / .claude/rules 规范回写 diff (2026-06-03)

> **状态**：Draft → 待批准（按 CLAUDE.md 协作规则：Draft → Approved → In Progress → Changed → Reapproved → Done）
> **目标**：把 8 份 agent 报告中的"规范与代码脱节"项以 PR diff 形式呈现，**不直接修改**根级 `AGENTS.md` / `CLAUDE.md` / `.claude/rules/`。
> **关联**：`00-executive-summary.md` + `09-doc-cleanup-checklist.md` + `10-issue-drafts.md` + `12-code-issues-record.md`

---

## 0. 摘要

| 变更类型 | 文件 | 段落 | 状态 |
|---------|------|------|------|
| 🔴 必改 | `CLAUDE.md` | "禁止事项" + "Project Structure" + "环境变量 StepFun" + L1-global 限流/熔断 | 待批准 |
| 🟡 强化 | `AGENTS.md` (根) | 核心架构模式 Result[T] + 宪法原则 VII trace_id | 待批准 |
| 🟡 强化 | `backend/AGENTS.md` | 业务逻辑禁入 common + legacy sales 禁令 | 待批准 |
| ➕ 新建 | `.claude/rules/L3-domain/sales-trainer.md` | 销售训练域 L3 规则（用户决策要求） | 待批准 |
| ➕ 新建 | `docs/error-codes.md` | 错误码中心表 | 待批准 |
| ➕ 新建 | `docs/observability/dead-metrics-action-plan.md` | 17 死指标接入路径 | 待批准 |
| ➕ 新建 | `docs/agents/audit-2026-06/README.md` | 本次审计索引 | 待批准 |
| ➕ 新建 | `docs/agents/audit-2026-06/12-code-issues-record.md` | 代码问题追踪（用户决策要求） | 待批准 |

---

## 1. CLAUDE.md 变更（diff 形式）

### 1.1 L45 — main.py 行数纠错

```diff
- backend/src/main.py                    # FastAPI 应用入口 (19655 lines)
+ backend/src/main.py                    # FastAPI thin entry (75 lines; 实际应用由 `app_factory.create_app()` 构造)
```

**依据**：Agent 1 F-04，`wc -l backend/src/main.py` = 75。

### 1.2 L80 — common/ 子目录数纠错

```diff
- common/                    # 共享模块
+ common/                    # 共享模块（30 个子目录，其中 17 个无 `__init__.py` / PEP 420 隐式）
```

**依据**：Agent 1 F-12。

### 1.3 "Project Structure" 段 — sales_bot/websocket/ 补齐

```diff
- └── websocket/             # 销售对练 WebSocket
-     ├── base_sales_handler.py    # Handler基类
-     ├── enhanced_handler.py      # 增强版handler (TTS降级)
-     └── simple_handler.py        # 简化版handler
+ └── websocket/             # 销售对练 WebSocket（12 个 BaseWebSocketHandler 子类）
+     ├── base_handler.py         # 在 common/websocket/（基类）
+     ├── router.py               # 4 个 WS 路由挂载点
+     ├── stepfun_realtime_state.py
+     ├── stepfun_realtime_handler.py    # 1157 行主类
+     ├── stepfun_realtime_{connection,policy,upstream,feedback,sales_stage}.py  # 5 个 mixin
+     ├── sales_handler.py.deprecated     # ⚠️ .deprecated 死代码（待清理，关联 LEGACY 列表）
+     └── components/                     # 8 个 stepfun_* 组件 + 7 个其他
```

### 1.4 "Project Structure" 段 — presentation_coach/services/ 补齐

```diff
  └── services/              # Coach, PointTracker, InterruptionDetector
-     ├── coach_service.py
-     ├── feedback_service.py
-     └── ppt_parser.py
+     ├── coach_service.py
+     ├── feedback_service.py
+     ├── ppt_parser.py
+     ├── presentation_ai_policy_service.py    # 2026-02 新增
+     ├── prompt_role_resolver.py              # 2026-02 新增
+     ├── point_extraction.py
+     ├── point_tracker.py
+     ├── semantic_point_tracker.py
+     ├── user_presentation_progress.py
+     ├── aho_matcher.py
+     ├── forbidden_matcher.py
+     └── interruption_detector.py
```

### 1.5 "环境变量" 段 — StepFun 加密强化

```diff
  # ============================================
  # StepFun Realtime（双轨语音模式）
  # ============================================
  STEPFUN_API_KEY=replace-with-stepfun-api-key
+ # ⚠️ 2026-06 审计：STEPFUN_API_KEY 必须经 `MODEL_CONFIG_ENCRYPTION_KEY` Fernet 加密后存 DB；
+ # env 直读模式已弃用，将在 Sprint-1 移除（关联 P0-03 issue）
  STEPFUN_REALTIME_URL=wss://api.stepfun.com/v1/realtime
```

### 1.6 "环境变量" 段 — TTS env 实际未消费提示

```diff
  TTS_ENABLE_FALLBACK=true
  TTS_FALLBACK_CHAIN=aliyun,edge,browser
+ # ⚠️ 2026-06 审计：TTS_TIMEOUT / TTS_SAMPLE_RATE / TTS_CONNECTION_POOL_SIZE /
+ # TTS_ENABLE_WARMUP / TTS_FALLBACK_CHAIN 5 个 env 当前未被代码消费（Agent 4 F-CFG-1），
+ # 仅 TTS_PROVIDER / TTS_VOICE 实际生效。Sprint-1 修复。
  TTS_TIMEOUT=10
  TTS_CONNECTION_POOL_SIZE=10
  TTS_ENABLE_WARMUP=true
```

### 1.7 "禁止事项" 段 — bg-white / ErrorBoundary 强化

```diff
  前端:
- ❌ bg-white（全页背景）→ bg-slate-50
- ❌ text-black → text-slate-900
+ ❌ bg-white → 任何场景（含 526 处历史违规、140 个文件）必须替换为 design token（`bg-bg-card` / `bg-bg-muted` / `bg-background`）
+ ❌ 缺 `error.tsx` → 任何 Next.js app 段必须有 `error.tsx`；`app/global-error.tsx` 必须存在
+ ❌ 缺 `loading.tsx` → 任何含数据获取的段必须有 `loading.tsx`
  ❌ text-black → text-slate-900
- ❌ 猜测 API → 查 docs/api-contract/
+ ❌ 猜测 API → 查 docs/api-contract/ + 检查对应 contract 测试文件
  ❌ alert/popup → 状态指示器
+ ❌ raw fetch() 绕过 apiFetch → 走 lib/api/client.ts
+ ❌ window.location.href 跳转 → 用 router.push
```

**依据**：Agent 7 §1.4 (bg-white 526) + §2.1 (global-error 缺失) + §3.3 (raw fetch 3 处) + §9 (window.location 1 处)。

### 1.8 "L1-global programming-patterns" 段 — 限流 / 熔断 / 错误码补齐

```diff
- ## 9. 限流保护：防止压垮服务
+ ## 9. 限流保护：防止压垮服务
+ ⚠️ 2026-06 审计：当前仅实现端点级装饰器（`@rate_limit`），全局/用户级/IP 级 **待实现**（Agent 1 F-06 / Agent 4 D-LIMIT-1）。
+ 装饰器当前仅 1 处生产应用（`common/auth/api.py:558` 登录）。
+ Sprint-2 计划：抽 `common/middleware/rate_limit.py` 中间件 + 4 维度覆盖。

  ## 10. 熔断器（已实施于 `common/resilience/circuit_breaker.py`）
+ ⚠️ 2026-06 审计：仅 ASR 接入（5/3/60s），TTS/LLM/StepFun/ChromaDB/OSS/COS 6 个外部依赖零熔断。
+ 文档 §9 写 "recovery_timeout=30s" 与代码 `timeout_seconds=60` 不一致，**修正为 60s**。

+ ## 11. Result 错误码规范（补强）
+ - 所有错误码必须 `[SCREAMING_SNAKE]`，参考 `docs/error-codes.md` 中心表
+ - 禁用 `Result.fail("中文/英文文案")`，必须带 `[CODE]`
+ - 错误码中心表 99 个 + 待补 STEPFUN_* / CHROMADB_* / RATE_LIMITED 域
+ - `result.py` 缺 `error_code` / `trace_id` 字段、`and_then` 方法（Agent 2 §7），Sprint-2 升级
```

### 1.9 "最近更新" 段 — 加审计批次

```diff
- ## 最近更新
-
- - **2026-02-16**: CLAUDE.md 更新
+ ## 最近更新
+
+ - **2026-06-03**: 严苛架构师 8-Agent 全量审计完成（docs/agents/audit-2026-06/00-executive-summary.md）
+   - 24 个 P0 + 60 个 P1 + 30 个持续项
+   - 跨域继承 / WebSocket 鉴权 / STEPFUN 加密 / 17 死指标 / bg-white 526 / CI 零门禁
+   - 38 个 Issue 草稿（10-issue-drafts.md）；规范回写 diff（本文档）
+
+ - **2026-02-16**: CLAUDE.md 更新
    - 销售对练 WebSocket 组件化 (stepfun_* 模块拆分)
    - PPT 演练增强 (presentation_ai_policy, prompt_role_resolver)
    - TTS 服务工厂化 (tts_factory, aliyun_streaming_tts)
    - 前端新增 presentation-ai 管理页面

- - **2026-02-15**: Claude Code 钩子系统 V2 优化
+ - **2026-02-15**: Claude Code 钩子系统 V2 优化
```

---

## 2. AGENTS.md (根) 变更

### 2.1 "核心架构模式" — Result[T] 补强

```diff
  ### 错误处理: Result[T]
  ```python
  from common.error_handling.result import Result

  async def process() -> Result[str]:
      try:
          return Result.ok(await do_work())
      except SomeError:
          return Result.fail("[ERROR_CODE]")
  ```
+ ### Result 完整 API 契约
+
+ ```python
+ @dataclass
+ class Result(Generic[T]):
+     value: T | None = None
+     fallback: str | None = None
+     error_code: str | None = None          # ⚠️ 2026-06 审计：当前缺，Sprint-2 补
+     trace_id: str | None = None            # ⚠️ 2026-06 审计：当前缺，Sprint-2 补
+     is_success: bool = True
+ ```
+
+ - `ok(value)` / `fail(fallback)` / `fail(code, message)` / `unwrap()` / `unwrap_or(default)` / `map(fn)`
+ - ⚠️ 2026-06 审计：缺 `and_then` (monadic bind)，`map` 仅捕获 `RuntimeError` + `ValueError`，Sprint-2 补
+ - 错误码中心表：`docs/error-codes.md`
+ - 所有用户面 service 层函数必须返回 `Result`，禁止 `raise HTTPException(5xx)`（违宪 I）
```

### 2.2 宪法原则 VII 可观测性 — trace_id 强化

```diff
  ### VII. 可观测性
  结构化日志，所有日志包含 trace_id
+ ⚠️ 2026-06 审计：当前 15 个文件 116 调用点使用 stdlib `logging.getLogger`，
+ **不自动注入 trace_id**，必须改为 `get_logger(__name__)`（Agent 8 P0-1）。
+ 范围：`sales_bot/services/{context_manager,bot_service,vagueness_detector,summary_service}.py`、
+ `common/{cache,ppt,jobs/audio_archival,monitoring,analytics}/*.py`、`presentation_coach/services/point_extraction.py`。
+ 个保法重点文件 `common/jobs/audio_archival.py`（18 调用）必须最先改。
```

---

## 3. backend/AGENTS.md 变更

### 3.1 业务逻辑禁入 common 规则 — 已知违规补强

```diff
- ## 1. Result[T] 错误处理模式
+ ## 1. Result[T] 错误处理模式
  宪法原则 I: 用户体验永不中断
  ...
+ ⚠️ 2026-06 审计：已发现 3 处反向依赖业务域（Agent 1 I-2~I-5），Sprint-2 拆 `practice_orchestrator`：
+ - `common/services/practice_session_service.py:54-57` 同时 import sales + presentation
+ - `common/services/practice_service.py:30` import sales_bot services
+ - `common/services/session_runtime_repair_service.py:18` import sales_bot services
+ - `common/conversation/session_evidence.py:317` lazy import presentation
```

### 3.2 legacy sales handler 禁令

```diff
- Legacy sales websocket modules are explicitly banned; do not reintroduce `base_sales_handler` / `enhanced_handler` / `simple_handler`.
+ Legacy sales websocket modules are explicitly banned; do not reintroduce `base_sales_handler` / `enhanced_handler` / `simple_handler`.
+ ⚠️ 2026-06 审计：`sales_bot/websocket/sales_handler.py.deprecated` 仍存在（12.5 KB），
+ 因 `training_runtime/plugins.py:14` `LEGACY_SALES_HANDLER_MODULES` 元组持有（用于"必须缺失"审计）。
+ 清理路径：先删除 LEGACY 列表 + 审计调用（`legacy_sales_handlers_absent()` in `plugins.py:92`），再删 .deprecated 文件。
```

---

## 4. .claude/rules/L3-domain/sales-trainer.md（新建）

```markdown
# L3 · 销售训练 (Sales Trainer) 域规则

> 状态：Draft（待批准）
> 关联：`docs/agents/audit-2026-06/00-executive-summary.md` + `12-code-issues-record.md`
> Owner：销售训练域 maintainer

## 1. 域范围
- 学员端 `/sales-trainer/*`（13 个 API + 9 个 page）
- 管理员 `/admin/sales-trainer/*`（36 个 API + 27 个 page + 12 张表）
- 域代码：`backend/src/sales_trainer/`（12 模型 + 6 服务 + 1 权限 + 3 API）
- 域前端：`web/src/app/(dashboard)/sales-trainer/` + `web/src/app/admin/sales-trainer/` + `web/src/components/admin/sales-trainer/`

## 2. RBAC 矩阵（来自 `sales_trainer/permissions.py`）

| 角色 | 学员记录 | 全局记录 | 任务重试 | 训练内容 | 运维日志 | 设置健康 |
|------|---------|---------|---------|---------|---------|---------|
| user | 自己 | ❌ | ❌ | ❌（仅看 published） | ❌ | ❌ |
| training_lead / training_manager | 本部门 | ❌ | ❌ | ❌ | ❌ | ❌ |
| content_admin / newcomer_content_admin | ❌ | ⚠ | ❌ | ✅ | ❌ | ❌ |
| ops / operator / operations / sre | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| admin / super_admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| support | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| readonly_auditor | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## 3. 域特定规则

### 3.1 错误处理
- 服务层**必须**返回 `Result[T]`（非裸 `raise`）
- 当前 5 个 service 文件累计 110+ raise 已识别为 P0-14，将在 Sprint-1 重构
- 错误码统一在 `docs/error-codes.md` 注册

### 3.2 音频数据合规（个保法）
- 提交音频 `SalesTrainerAudioSubmission` 生命周期：
  - 提交 → 30 天本地缓存 → 365 天 OSS/COS 归档 → 用户删除即软删
- 必须实现 `DELETE /api/v1/admin/sales-trainer/audio-submissions/{submission_id}` 路由 + 软删除字段 `deleted_at`
- admin 列表返回时**必须**对 `user_email` 走 `_mask_email()`（与 `admin/api/users.py` 标杆一致）

### 3.3 表结构
- 表前缀 `sales_trainer_`（CLAUDE.md §III 场景隔离）
- 12 表：`units` / `unit_questions` / `exam_papers` / `quiz_attempts` / `quiz_answers` / `audio_submissions` / `audio_transcripts` / `audio_score_prompts` / `audio_score_results` / `materials` / `material_versions` / `operation_logs`
- 全部模型**不**声明 `relationship()`，全走显式 `select()` 关联（这是域规约）
- FK `ondelete` 覆盖率必须 ≥ 80%（当前 28%，P1 补强）
- JSONB 列（`config` / `answer_payload` / `material_snapshot` / `transcript_snapshot` / `dimension_scores`）**必须**有 GIN 索引

### 3.4 RBAC 演进
- 当前 13 角色枚举在 `User.role` CheckConstraint
- 迁移 075（`20260603_1000_075_sales_trainer_rbac_roles.py`）扩展
- 未来如需细粒度权限，引入 `roles × permissions × user_roles` 三表

### 3.5 WebSocket 集成（如未来扩展）
- 当前 sales-trainer 域**不直接用 StepFun**（学员对练走 sales_bot 域）
- 如未来引入，**禁止**跨域继承 `sales_bot.StepFunRealtimeHandler`，应继承 `common/websocket/stepfun_realtime_handler.py`（P0-01 修复后）

## 4. 域测试

- 单元测试：`tests/unit/test_sales_trainer_services.py`（19 test funcs）
- 集成测试：`tests/integration/test_sales_trainer_api.py`（11 tests）+ `test_sales_trainer_real_providers.py`
- E2E：`tests/e2e/test_sales_training_learning_examiner_flow.py`
- **缺口**：
  - 49 个 API 端点 0 contract test（P1-03）
  - 49 个 API 失败态测试 1/49（P1-03）
  - 9 个 admin page 0 测试（P1-03）
  - WS `close(4401)` 回归 + sub↔session 绑定回归（P0-02）
  - audio_submission DELETE 路由回归（P0-06）

## 5. 域 Sprint 优先级

| Sprint | 修复项 |
|--------|--------|
| Sprint-1 | P0-06 (DELETE) / P0-14 (110+ raise 改 Result) / P0-16 (JSONB GIN) / P0-18 (分页) / P0-20/21 (admin 邮箱脱敏) / P0-23 (ASR/TTS 降级链接入) |
| Sprint-2 | P1-03 (49 端点 contract) / P1-08 (log marker api_key) / P1-09 (14 子段 error.tsx) / P1-10 (React Query) |
| Sprint-3 | P1-11 (client.ts 拆分) / P1-12 (use-practice-websocket.ts 拆分) / domain dark mode |
```

---

## 5. docs/error-codes.md（新建）

```markdown
# 错误码中心表

> 状态：Draft（待批准）
> 来源：`docs/agents/audit-2026-06/02-result-and-error-handling.md` §4 + `04-audio-and-ai-capabilities.md` §1.4 + `03-websocket-realtime.md` §8.5
> 规范：所有 `Result.fail("[CODE]")` 必须在本表注册，禁止口语化

## 命名规范
- 严格 `[A-Z_]+`（不含数字 / 空格 / 短横线 / 中文 / 异常类型）
- 复合错误用 `code + sub_code` 双字段（`[X:Y]` 仅作内部使用，外部 i18n 用 `code` 字段）
- 域前缀清晰：`ASR_` / `TTS_` / `LLM_` / `KB_` / `STEPFUN_` / `CHROMADB_` / `WS_` / `RATE_LIMITED`

## 现有 99 个错误码（按域）

[从 02-result-and-error-handling.md §4.1 提取聚合]

## 待补（Agent 2 §4.3 缺失域）

### STEPFUN_*（0 → ≥6）
- `[STEPFUN_KEY_MISSING]` — handler.py:858
- `[STEPFUN_UPSTREAM_REJECTED]` — handler.py:931
- `[STEPFUN_TRANSPORT_ERROR]` — handler.py:941
- `[STEPFUN_CONNECTION_ERROR]` — handler.py:954
- `[STEPFUN_CIRCUIT_OPEN]` — 熔断（建议）
- `[STEPFUN_HANDOFF]` — 断流回退 legacy（建议）

### CHROMADB_*（0 → ≥3）
- `[VECTOR_STORE_UNAVAILABLE]` — 已存在
- `[VECTOR_STORE_TIMEOUT]` — 建议
- `[VECTOR_STORE_EMPTY]` — 建议

### RATE_LIMIT_*（0 → ≥2）
- `[RATE_LIMITED]` — 触发限流 429
- `[RATE_LIMIT_GLOBAL]` — 全局 QPS 限流

### WS_（0 → ≥4）
- `[WS_QUEUE_OVERFLOW]` — base_handler.py:30
- `[WS_BACKPRESSURE_DROP]` — 上游音频背压
- `[WS_STATE_SAVE_FAILED]` / `[WS_STATE_GET_FAILED]` — session_state_service.py:278, 316
- `[WS_HANDSHAKE_TIMEOUT]` — 协议协商超时

### 通用降级指令（4）
- `[USE_BROWSER_TTS]` / `[USE_BROWSER_ASR]` / `[USE_KEYWORD_SEARCH]` / `[USE_FALLBACK_RESPONSE]`

## 13 处口语化违例（必改）

[从 02-result-and-error-handling.md §4.2 列出]

## 状态码映射

| 域 | 4xx | 5xx | 降级 |
|----|-----|-----|------|
| HTTP API | `[X_NOT_FOUND]` → 404 / `[X_FORBIDDEN]` → 403 / `[X_INVALID]` → 400 | 仅基础设施级（DB / Redis） | `[USE_BROWSER_*]` / `[RETRY_LATER]` |
| WebSocket | `[WS_HANDSHAKE_FAILED]` → close(4401) | close(1011) | 不在 WS 层降级 |
| 后台任务 | `[TASK_FAILED]` → Celery state | retry x3 后 FAIL | 邮件告警 |
```

---

## 6. docs/observability/dead-metrics-action-plan.md（新建）

```markdown
# 17 个 Prometheus 死指标接入/删除决策

> 关联：`docs/agents/audit-2026-06/10-issue-drafts.md` P0-04
> 决策日：2026-06-03 → 待 Sprint-1 实施

| # | 指标 | 决策 | 接入点 | 估时 |
|---|------|------|--------|------|
| 1 | `websocket_connections_active` | **接入** | `common/websocket/base_handler.py:__init__` / `close` | 0.5d |
| 2 | `websocket_messages_total` | **接入** | `base_handler.py:_enqueue_message` | 0.25d |
| 3 | `websocket_message_duration_seconds` | **接入** | `base_handler.py:_process_messages` | 0.5d |
| 4 | `practice_sessions_total` | **接入** | `common/services/practice_session_service.py` | 0.25d |
| 5 | `practice_session_duration_seconds` | **接入** | `practice_session_service.py` | 0.25d |
| 6 | `practice_scores` | **接入** | `evaluation/services/staged_evaluation.py` | 0.25d |
| 7 | `llm_requests_total` | **接入** | `common/ai/llm_service.py:generate/evaluate/generate_report` | 0.5d |
| 8 | `llm_request_duration_seconds` | **接入** | 同上 | 0.5d |
| 9 | `llm_tokens_total` | **接入** | `llm_service.py` CostTrackingHandler | 0.5d |
| 10 | `asr_requests_total` | **接入** | `common/audio/asr_alibaba.py:stream_transcribe` | 0.5d |
| 11 | `asr_request_duration_seconds` | **接入** | 同上 | 0.5d |
| 12 | `tts_requests_total` | **接入** | `tts_factory.py:synthesize_streaming` | 0.5d |
| 13 | `tts_request_duration_seconds` | **接入** | 同上 | 0.5d |
| 14 | `voice_policy_rollbacks_total` | **接入** | `sales_bot/services/voice_policy_monitor.py` | 0.25d |
| 15 | `voice_policy_state_changes_total` | **接入** | 同上 | 0.25d |
| 16 | `errors_total` | **接入** | 各 WS handler `except` 分支 | 0.5d |
| 17 | `application_info` | **保留**（Info 类型，初始化时设） | 已隐式 | 0d |

## Grafana 仪表盘（4 个）

- `docs/observability/grafana/http-dashboard.json`（HTTP 请求 + P95）
- `docs/observability/grafana/ws-dashboard.json`（WS 连接 / 消息 / 背压）
- `docs/observability/grafana/ai-dashboard.json`（ASR/TTS/LLM/StepFun + 降级率）
- `docs/observability/grafana/practice-dashboard.json`（练习会话 + 评分分布）

## 告警规则（5 条）

- 5xx 错误率 > 1% / 5min
- API P95 延迟 > 300ms / 5min
- TTS 降级率 > 5% / 5min（`browser_fallbacks / tts_requests_total`）
- 错误率 > 0.1% / 5min
- StepFun close 4000 > 0 / 5min（API key 异常）
```

---

## 7. docs/agents/audit-2026-06/README.md（新建）

```markdown
# 销售训练 qoder · 严苛架构师审计 (2026-06)

> 入口索引，链接到 12 份审计产出物
> 审计基线：`feat(sales-trainer): 落地销售训练 MVP 与配置资产中心` (3c14f5d5)
> 审计方法：8 agent 并行静态分析；0 行代码修改

## 报告清单

| # | 主题 | 路径 |
|---|------|------|
| 00 | 执行摘要 | [00-executive-summary.md](./00-executive-summary.md) |
| 01 | 架构边界与模块依赖 | [01-architecture-boundary.md](./01-architecture-boundary.md) |
| 02 | 错误处理与 Result 范式 | [02-result-and-error-handling.md](./02-result-and-error-handling.md) |
| 03 | WebSocket 实时链路与 StepFun | [03-websocket-realtime.md](./03-websocket-realtime.md) |
| 04 | 音频 / AI 能力 | [04-audio-and-ai-capabilities.md](./04-audio-and-ai-capabilities.md) |
| 05 | 数据库与持久化 | [05-database-and-persistence.md](./05-database-and-persistence.md) |
| 06 | 安全 / 鉴权 / 数据隐私 | [06-security-and-privacy.md](./06-security-and-privacy.md) |
| 07 | 前端架构与用户体验 | [07-frontend-architecture.md](./07-frontend-architecture.md) |
| 08 | 测试 / 可观测性 / CI | [08-testing-observability-ci.md](./08-testing-observability-ci.md) |
| 09 | 文档治理清单 | [09-doc-cleanup-checklist.md](./09-doc-cleanup-checklist.md) |
| 10 | GitHub Issue 草稿 | [10-issue-drafts.md](./10-issue-drafts.md) |
| 11 | AGENTS.md / CLAUDE.md 回写 diff | [11-AGENTS-CLAUDE-patch.md](./11-AGENTS-CLAUDE-patch.md) |
| 12 | 代码问题追踪记录 | [12-code-issues-record.md](./12-code-issues-record.md) |

## 评级总览

| 域 | 评级 | 关键问题 |
|----|------|---------|
| 架构 | C+ | 跨域继承、文档失真 |
| 错误处理 | D+ | 36% 覆盖、熔断/限流几乎全裸 |
| WebSocket | B-/D | 心跳扎实 / 鉴权缺口 / 协议漂移 |
| 音频/AI | C- | 降级链声明完整 / 生产 0 引用 |
| 数据库 | B | ORM 完美 / 5 P0 性能 |
| 安全 | B- | 横向越权全挡 / WS 鉴权漏 |
| 前端 | B- | bg-white 526 / binaryType 缺 |
| 测试/CI | D | 17 死指标 / PR 零门禁 |

## Sprint 路线

- **Sprint-1 (1-2 周)**：10 个 P0（详见 00 §6）
- **Sprint-2 (2-4 周)**：15 个 P1
- **Sprint-3 (1-3 月)**：30+ 个持续项

## 协作规则

按 CLAUDE.md 协作规则：Draft → Approved → In Progress → Changed → Reapproved → Done。
本审计产出物均处于 **Draft** 状态，等待您批准后进入实施。
```

---

## 8. docs/agents/audit-2026-06/12-code-issues-record.md（新建）

```markdown
# 代码问题追踪记录 (2026-06-03)

> 状态：Draft（待批准）
> 来源：8 份专题报告（00 ~ 08）
> 关联：10-issue-drafts.md（含 gh issue 草稿）
> 维护：本文件为"代码问题总账"，每个 issue 提交后回填编号

## P0 阻断 (24 项)

| 编号 | 主题 | 来源 | 关联 | 状态 |
|------|------|------|------|------|
| code-001 | 跨域继承 `PresentationStepFunRealtimeHandler` → `StepFunRealtimeHandler` | 1 F-01 / 3 §10 | P0-01 | 待办 |
| code-002 | WS 鉴权失败不 `close(4401)` | 6 P1-3 | P0-02 | 待办 |
| code-003 | WS 鉴权 `payload["sub"]` 与 session 不绑 | 6 P1-4 | P0-02 | 待办 |
| code-004 | `STEPFUN_API_KEY` 明文读取 | 4 F-SEC-1 | P0-03 | 待办 |
| code-005 | 17 个 Prometheus 指标死代码 | 4 F-OBS-1 / 8 P0-2 | P0-04 | 待办 |
| code-006 | trace_id 15 文件 116 调用点断崖 | 8 P0-1 | P0-05 | 待办 |
| code-007 | 销售训练 audio_submission 无 DELETE 路由 | 4 D-SEC-2 / 6 / 8 | P0-06 | 待办 |
| code-008 | `bg-white` 526 处全量 | 7 §1.4 | P0-07 | 待办 |
| code-009 | WS 客户端 `binaryType` 缺 + 二进制 PCM 入站 | 7 §10.3 | P0-08 | 待办 |
| code-010 | CI 常规 PR 5 门禁缺失 | 8 P0-3 | P0-09 | 待办 |
| code-011 | CLAUDE.md `main.py 19655 行` 失真 | 1 F-04 | P0-24 | 待办 |
| code-012 | 3 处 `HTTPException(500)` 违宪 I | 2 P0-1 | P0-11 | 待办 |
| code-013 | `common/business_rules/validators.py` 80 raise 违宪 I | 2 P0-4 | P0-12 | 待办 |
| code-014 | `support/` + `supervisor/` 0 Result 引用 | 2 P0-5 | P0-13 | 待办 |
| code-015 | `sales_trainer/services/*` 110+ raise | 2 P0-6 | P0-14 | 待办 |
| code-016 | `agent_service.py` 13 查询零 `selectinload` | 5 P0-3 | P0-15 | 待办 |
| code-017 | 14 个 JSONB 列无 GIN 索引 | 5 P0-1 | P0-16 | 待办 |
| code-018 | `pool_recycle` 缺失 | 5 P0-2 | P0-17 | 待办 |
| code-019 | sales_trainer list 接口零分页 | 5 P0-4 | P0-18 | 待办 |
| code-020 | 项目级软删除字段缺失 | 5 P0-5 | P0-19 | 待办 |
| code-021 | admin audio_submission 列表裸露 user_email | 6 P1-1 | P0-20 | 待办 |
| code-022 | admin quiz_attempt 列表裸露 user_email | 6 P1-2 | P0-21 | 待办 |
| code-023 | `X-Forwarded-For` 无条件信任 | 6 P1-5 | P0-22 | 待办 |
| code-024 | `ASRServiceWithFallback` / `TTSServiceWithFallback` 生产 0 引用 | 4 F-ASR-1 / F-TTS-1 | P0-23 | 待办 |

## P1 严苛（约 60 项 — 编号 code-025 ~ code-085）

| 编号 | 主题 | 来源 | 关联 | 状态 |
|------|------|------|------|------|
| code-025 | 错误码中心表缺失 + Result 缺 `error_code/trace_id/and_then` | 2 §7 | P1-01 | 待办 |
| code-026 | TTS 5 个必备 env 未消费 | 4 F-CFG-1 | P1-02 | 待办 |
| code-027 | 49 端点失败态测试 1/49 | 7 §8.3 | P1-03 | 待办 |
| code-028 | sales-trainer 0 contract test | 8 §6 | P1-03 | 待办 |
| code-029 | 9 个 admin sales-trainer page 0 测试 | 7 §8.2 | P1-03 | 待办 |
| code-030 | 全局/用户级/IP 级限流中间件缺失 | 1 F-06 / 4 D-LIMIT-1 | P1-04 | 待办 |
| code-031 | TTS/LLM/StepFun/ChromaDB 6 外部依赖零熔断 | 4 D-CB-1 | P1-05 | 待办 |
| code-032 | JWT 无 `audience` / `issuer` 校验 | 6 P1-7 | P1-06 | 待办 |
| code-033 | 9 个 WS 错误码无文档 | 3 §8.5 | P1-07 | 待办 |
| code-034 | WS 协议无 `schema_version` 顶层字段 | 3 §3.3 | P1-07 | 待办 |
| code-035 | 日志脱敏 marker 缺 `api_key/apikey/secret/authorization` | 6 P1-9 | P1-08 | 待办 |
| code-036 | sales-trainer 14 子段 0 error.tsx | 7 §2 | P1-09 | 待办 |
| code-037 | `app/global-error.tsx` 缺失 | 7 §2 | P1-09 | 待办 |
| code-038 | React Query 未接入 sales-trainer（272 处 useState 抓数据） | 7 §4 | P1-10 | 待办 |
| code-039 | `client.ts` 4648 行单点巨型 | 7 §3 | P1-11 | 待办 |
| code-040 | `use-practice-websocket.ts` 1047 行单文件 | 3 §9.4 | P1-12 | 待办 |
| code-041 | `common/services/practice_session_service.py` 双向耦合业务域 | 1 I-2 | P1-14 | 待办 |
| code-042 | NFR 性能测试 5/10/50/200 并发错位 | 8 §4.5 | P1-15 | 待办 |
| code-043 | `common/knowledge` + `common/knowledge_engine` 双轨 6+ 自闭 | 4 D-KNOW-1 | — | 待办 |
| code-044 | KB Lock 4 衍生状态码未入文档 | 4 C-KB-1 | — | 待办 |
| code-045 | OTel 接入 0 业务 span | 8 §3.3 | — | 待办 |
| code-046 | 3 处 raw `fetch` 绕过 `apiFetch` | 7 §3.3 | — | 待办 |
| code-047 | `path_service.outerjoin` 一次取 submission+score 是好范式（参考） | 5 | — | OK |
| code-048 | `curriculum_practice` `selectinload(scenario)` 是好范式（参考） | 5 | — | OK |
| code-049 | JWT_SECRET 默认值硬编码（生产已 fail-fast） | 6 P3-1 | — | 待办 |
| code-050 | `ModelConfig.extra_config` 未加密 | 6 P2-4 | — | 待办 |
| code-051 | `CORS` 生产误置 `ENVIRONMENT=development` 风险 | 6 P1-8 | — | 待办 |
| code-052 | `allow_methods=["*"]` + `allow_credentials=True` | 6 P2-5 | — | 待办 |
| code-053 | `original_filename` 反射 Content-Disposition 浏览器下载 XSS | 6 P2-7 | — | 待办 |
| code-054 | `audio_submission.user_id` 已规范化（OK 标杆） | 6 | — | OK |
| code-055 | `coverage.json` 4 月未刷新 | 8 P2-4 | — | 待办 |
| code-056 | `roleplay-contract-eval` 依赖 LLM grader 不可重复 | 8 P3-2 | — | 待办 |
| code-057 | contract 24 / docs 18 结构性不对齐 | 8 §6 | — | 待办 |
| code-058 | `WeCom SSO` state 验证 + return_to 防越权（OK 标杆） | 6 | — | OK |
| code-059 | 16 个 sales_trainer 端点 0 admin page 测试 | 7 §8.2 | — | 待办 |
| code-060 | `client.ts` 3.24% 覆盖率（灾难） | 8 §2.4 | — | 待办 |
| code-061 | `learn/[unitId]/page.test.tsx` 0 测试 | 7 §8.2 | — | 待办 |
| code-062 | 9 admin sales-trainer 测试 0 失败态 | 7 §8.3 | — | 待办 |
| code-063 | `useState` 抓数据 1177 处 | 7 §4.2 | — | 待办 |
| code-064 | `next/dynamic` 0 处使用 | 7 §7 | — | 待办 |
| code-065 | `lucide-react` 全量导入 | 7 §7 | — | 待办 |
| code-066 | a11y: Radix 3/12 + aria-label 87 处 | 7 §6 | — | 待办 |
| code-067 | `useTheme()` hook 在、dark mode 样式 0 | 7 §1.3 | — | 待办 |
| code-068 | design system token 仓库未被 `@import` | 7 §1.2 | — | 待办 |
| code-069 | `path_service.outerjoin` 是好范式 | 5 | — | OK |
| code-070 | `Materialize` migration 链路 0 孤儿 | 5 | — | OK |
| code-071 | `pool_pre_ping=True` OK 标杆 | 5 | — | OK |
| code-072 | RFC 4122 UUID in user_id (规范化) | 6 | — | OK |
| code-073 | `CORS` `_validate_cors_origins` 拒绝通配符 + 凭据（OK 标杆） | 6 | — | OK |
| code-074 | `_load_sales_stage_runtime_config` 重复 | 3 P2 | — | 待办 |
| code-075 | `_send_status` / `_send_heartbeat` 重复 | 3 P1 | — | 待办 |
| code-076 | `BoundedSemaphore` 协商未实际使用 | 3 P2 | — | 待办 |
| code-077 | `tts_audio` + `tts_chunk` 双轨 | 3 P2 | — | 待办 |
| code-078 | UNHANDLED 事件无 metrics | 3 P2 | — | 待办 |
| code-079 | `_load_persisted_state` 另起 `async_sessionmaker` 可见性偏移 | 5 P1 | — | 待办 |
| code-080 | `User.email` `unique=True, nullable=True` 多 NULL | 5 P1 | — | 待办 |
| code-081 | `_startup_schema_repairs_allowed` 在 staging 应禁用 | 5 P1 | — | 待办 |
| code-082 | 迁移命名 4 风格共存 | 5 P1 | — | 待办 |
| code-083 | `get_db()` `except` 列表未覆盖 `OperationalError` | 5 P1 | — | 待办 |
| code-084 | `Result` 缺 `and_then` (monadic bind) | 2 P2-1 | — | 待办 |
| code-085 | `Result.fail` 静默接受空串 | 2 P2-3 | — | 待办 |

## P2/P3 持续（约 30 项）

- PEP 420 17 个子目录 + 3 根包无 `__init__.py`
- `main.py` 9 个 shim helper + `create_app` 自赋值
- `_normalize_requested_voice_mode` / `_default_voice_mode` / `_is_admin_user_id` 在 `main.py` 与 `sales_bot/websocket/router.py` 重复
- `sales_handler.py.deprecated` + `presentations.py.backup` + `broadcaster.py.backup` 29.4 KB 死代码
- `presentation_coach/websocket/presentation_handler.py` 仍作 legacy fallback
- `_build_knowledge_bases_alias_router` 旧路径别名
- 23+ `except Exception: # noqa: BLE001` WS 边界裸吞
- CORS 配置占 `app_factory.py` 50% 行数
- `LEGACY_SALES_HANDLER_MODULES` 元组持有死代码
- `SalesBotWebSocketHandler_DEPRECATED` 类
- `stepfun_knowledge_helpers.py` / `stepfun_internal_knowledge_searcher.py` 空壳
- `__getattr__` raise 模板（state_base.py:158）
- `_load_sales_stage_runtime_config` 与 `_disable_sales_capabilities` 重复
- StepFun 模型/音色/voice_mode 默认值硬编码 3+ 处
- `sales_handler.py.deprecated` 在 LEGACY 列表被持有
- `MAX_RECONNECT_ATTEMPTS=5` 硬编码
- `audio_drop_notice` / `system_backpressure` / `response` / `transcript` / `evaluation_feedback` 服务端无发射点
- `pause` / `resume` 顶级 type 与 `control.action` 双轨
- `ScorePanel` / `SlideViewer` 未懒加载
- sales-trainer admin 8 个 page 0 testing
- 测试 fixtures SQLite vs PostgreSQL 不一致
- Redis fixture 未自动启动
- 10 个 seed 脚本无冒烟
- ...（略）

## Sprint 分组

| Sprint | 编号范围 | 估时 |
|--------|---------|------|
| Sprint-1 | code-001 ~ code-024 | ~14 人天 |
| Sprint-2 | code-025 ~ code-050 | ~18 人天 |
| Sprint-3 | code-051 ~ code-085 + P2/P3 | ~25 人天 |

## 状态更新约定

- 提交 issue 后回填：`状态: 提交 #NNN`
- 实施完成：`状态: 已修 (#NNN merged @YYYY-MM-DD)`
- 关闭：`状态: 关闭（won'tfix / duplicate / ...）`
```

---

## 9. 提交方式

**不直接修改**根级文件。所有 diff 以上方文本形式呈现，您 review 后：

| 方式 | 命令 |
|------|------|
| **方式 A（推荐）** | 把本文件复制到 `docs/agents/audit-2026-06/11-AGENTS-CLAUDE-patch.md` 已落地；将本节各变更拆为独立 PR，逐文件应用 diff |
| **方式 B** | 主 agent 在下一轮会话应用 diff，先生成 `git apply` 风格的 patch 文件 `patches/0001-...patch`，再 `git apply` |
| **方式 C** | 把每节作为单独 PR 描述，由您或团队成员手动 apply |

---

## 10. 关联

- `00-executive-summary.md` — 综合摘要
- `09-doc-cleanup-checklist.md` — 文档治理清单
- `10-issue-drafts.md` — Issue 草稿
- `12-code-issues-record.md` — 代码问题追踪（本节内 §8）
- 各 Agent 报告

---

**本文档不修改任何源代码或现有文档**。所有变更需走 PR 评审流程。
