# Runtime Convergence And Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收敛训练运行时主语，降低前端浏览器侧复杂度，迁移到 cookie/server-boundary 鉴权，并补齐标准化观测入口与体系化韧性基础设施。

**Architecture:** 保持模块化单体，不拆服务。后端增加 `training_runtime` 统一描述层、cookie/session 支持、OTel 初始化和 jitter backoff；前端增加 server auth boundary、Query Provider、instrumentation 文件，并把练习页生命周期控制改成 REST 单写、WebSocket 只承载实时数据面。

**Tech Stack:** FastAPI, SQLAlchemy Async, Next.js 16 App Router, React 19, TypeScript, TanStack Query, OpenTelemetry

---

### Task 1: Cookie Auth + Runtime Subject

**Files:**
- Modify: `backend/src/common/auth/service.py`
- Modify: `backend/src/common/auth/api.py`
- Modify: `backend/src/main.py`
- Modify: `backend/src/common/db/schemas.py`
- Modify: `backend/src/common/api/practice.py`
- Create: `backend/src/training_runtime/__init__.py`
- Create: `backend/src/training_runtime/models.py`
- Create: `backend/src/training_runtime/service.py`
- Test: `backend/tests/integration/test_auth_login_api.py`
- Test: `backend/tests/contract/test_sessions.py`

**Step 1: Write failing tests**
- cookie 登录成功后返回 `Set-Cookie`
- cookie 鉴权可访问 `/users/me`
- session 返回 `runtime_subject`

**Step 2: Run tests to verify RED**
- `pytest backend/tests/integration/test_auth_login_api.py -v`
- `pytest backend/tests/contract/test_sessions.py -v`

**Step 3: Write minimal implementation**
- 后端登录/登出/dev-login 维护 httpOnly session cookie
- `get_current_user` 同时支持 bearer 和 cookie
- 新增 `TrainingRuntimeSubject`/`TrainingRuntimeDescriptor`
- 会话响应增加 `runtime_subject`

**Step 4: Run tests to verify GREEN**
- 同上

### Task 2: Single Lifecycle Source + Jitter Backoff

**Files:**
- Modify: `backend/src/common/websocket/session_manager.py`
- Modify: `backend/src/common/websocket/base_handler.py`
- Modify: `backend/src/common/api/practice.py`
- Modify: `backend/src/sales_bot/websocket/base_sales_handler.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/common/audio/asr_with_fallback.py`
- Create: `backend/src/common/resilience/backoff.py`
- Test: `backend/tests/integration/test_session_flow.py`
- Test: `backend/tests/unit/test_stepfun_upstream_router.py`

**Step 1: Write failing tests**
- REST 生命周期控制后，活动 handler 同步到 `in_progress/pause/resume/end`
- backoff 返回带 jitter 的延迟并受 max 限制

**Step 2: Run tests to verify RED**
- `pytest backend/tests/integration/test_session_flow.py -v`

**Step 3: Write minimal implementation**
- SessionManager 维护 live handler registry
- REST 生命周期写 DB 后同步 live handler 本地状态
- 前端后续删掉 WS control 双写依赖
- StepFun / ASR fallback 使用统一 jitter backoff helper

**Step 4: Run tests to verify GREEN**
- 同上

### Task 3: Backend OTel

**Files:**
- Create: `backend/src/common/monitoring/otel.py`
- Modify: `backend/src/main.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/unit/test_logger.py`

**Step 1: Write failing test**
- `OTEL_ENABLED=true` 时初始化函数不报错，禁用时安全跳过

**Step 2: Run test to verify RED**
- `pytest backend/tests/unit/test_logger.py -v`

**Step 3: Write minimal implementation**
- 增加 FastAPI OTel 初始化，缺依赖时 graceful degrade

**Step 4: Run test to verify GREEN**
- 同上

### Task 4: Frontend Server Boundary + Query Layer

**Files:**
- Modify: `web/package.json`
- Modify: `web/src/app/layout.tsx`
- Modify: `web/src/app/(dashboard)/layout.tsx`
- Modify: `web/src/app/admin/layout.tsx`
- Modify: `web/src/app/(auth)/login/page.tsx`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/lib/auth-handler.ts`
- Modify: `web/src/hooks/use-auth-protection.ts`
- Create: `web/src/components/providers/app-providers.tsx`
- Create: `web/src/lib/query/client.ts`
- Create: `web/src/lib/server-auth.ts`
- Create: `web/src/instrumentation.ts`
- Create: `web/src/instrumentation-client.ts`
- Create: `web/src/components/layout/dashboard-shell.tsx`
- Create: `web/src/components/layout/admin-shell.tsx`
- Test: `web/src/lib/api/client.auth.test.ts`
- Test: `web/src/lib/auth-handler.test.ts`

**Step 1: Write failing tests**
- 登录后不再依赖 localStorage token
- API client 默认带 `credentials: include`
- server auth helper 无 cookie 时拒绝，带 cookie 时通过

**Step 2: Run tests to verify RED**
- `npm test -- client.auth.test.ts`
- `npm test -- auth-handler.test.ts`

**Step 3: Write minimal implementation**
- Root layout 注入 Query Provider
- 登录改为 cookie session
- Dashboard/Admin layout 迁移到 server boundary + client shell
- instrumentation 文件初始化 OTel

**Step 4: Run tests to verify GREEN**
- 同上

### Task 5: Practice Runtime Split

**Files:**
- Modify: `web/src/app/(user)/practice/[sessionId]/page.tsx`
- Modify: `web/src/hooks/use-practice-websocket.ts`
- Create: `web/src/hooks/practice/use-runtime-lock.ts`
- Create: `web/src/hooks/practice/use-session-lifecycle.ts`
- Create: `web/src/hooks/practice/use-recording-hotkeys.ts`
- Create: `web/src/hooks/queries/use-session-runtime-query.ts`
- Test: `web/src/hooks/use-practice-websocket.test.ts`
- Test: `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`

**Step 1: Write failing tests**
- lifecycle action 只走 REST，不再发送 control 双写
- runtime metadata 通过 query hook 拉取

**Step 2: Run tests to verify RED**
- `npm test -- use-practice-websocket.test.ts`

**Step 3: Write minimal implementation**
- practice 页面拆 runtime lock / lifecycle / keyboard 逻辑
- WebSocket 去掉 token query 依赖
- start/pause/resume/end 只调用 REST lifecycle

**Step 4: Run tests to verify GREEN**
- 同上
