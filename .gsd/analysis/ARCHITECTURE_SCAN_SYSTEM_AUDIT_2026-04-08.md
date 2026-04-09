# Architecture Scan — SYSTEM_AUDIT_REPORT 修复规划（2026-04-08）

## 1. 仓库形态

- **仓库类型**：单仓库、双应用结构，不是 pnpm workspace monorepo，但根目录同时承载 `backend/` 与 `web/` 两个主应用。
- **仓库根目录确认**：当前工作目录为 `/Users/zhaozengqing/github/销售训练qoder`，存在 `.git/`、`.gsd/`、`backend/`、`web/`、`.github/workflows/`。
- **现有规划体系**：项目已深度使用 `.gsd/`，当前活跃里程碑为 **M012**，已存在：
  - `.gsd/STATE.md`
  - `.gsd/PROJECT.md`
  - `.gsd/REQUIREMENTS.md`
  - `.gsd/milestones/M012/M012-ROADMAP.md`
  - `.gsd/milestones/M012/slices/S01..S03`
- **结论**：本次不应另起一套“脱离现有 GSD”的虚构计划。需要在现有 M012 / active requirements 基础上扩展，并明确哪些 SYSTEM_AUDIT_REPORT 条目是：
  1. 已修复但审计未更新
  2. 真实缺口
  3. 需要专项审计才能确认
  4. 产品上已 deferred / out-of-scope

---

## 2. 技术栈识别

### 前端
- **框架**：Next.js 16.1.1 + React 19.2.3 + TypeScript
- **UI**：Tailwind CSS v4、Radix UI Dialog / Tooltip、Lucide icons
- **状态 / 数据**：TanStack Query、Zustand
- **测试**：Vitest + Testing Library + jsdom
- **关键配置**：
  - `web/package.json`
  - `web/next.config.ts`
  - `web/tsconfig.json`
  - `web/vitest.config.ts`
  - `web/eslint.config.mjs`

### 后端
- **框架**：FastAPI
- **ORM / 数据库**：SQLAlchemy Async + Alembic，面向 PostgreSQL，兼容 SQLite 测试/本地路径
- **缓存 / 协调**：Redis 已作为运行时依赖
- **实时通信**：WebSocket（sales / presentation 双链路）
- **日志 / 监控**：structlog、Prometheus、OpenTelemetry
- **测试**：pytest / pytest-asyncio / pytest-cov
- **关键配置**：
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `alembic.ini`, `backend/alembic.ini`

### CI / 脚本
- **CI**：`.github/workflows/nfr-performance-check.yml`
- **脚本**：`scripts/dev-up.sh`, `scripts/dev-stop.sh`, `scripts/run-vitest-root.mjs`

### 鉴权
- **当前实现**：JWT + HttpOnly cookie；登录使用 env shared password / user override / user.hashed_password 三层混合模式。
- **相关文件**：
  - `backend/src/common/auth/service.py`
  - `backend/src/common/auth/api.py`
  - `web/src/app/(auth)/login/page.tsx`
  - `web/src/app/(auth)/forgot-password/page.tsx`
  - `web/src/app/(auth)/reset-password/page.tsx`

---

## 3. 与本次 SYSTEM_AUDIT_REPORT 最相关的工程分层

| 层级 | 当前项目现状 | 与本次审计的关系 |
|---|---|---|
| 用户入口 / 路由层 | `web/src/app/(auth)`, `(dashboard)`, `(user)/practice`, `admin` | SYSTEM_AUDIT_REPORT 的大多数 UX 问题都落在这里 |
| 共享前端壳层 | `web/src/components/layout/*`, `web/src/components/ErrorBoundary.tsx` | 导航、跳转、error boundary、window.location、console 输出集中在此 |
| 前端 API / 可观察性层 | `web/src/lib/api/client.ts`, `web/src/lib/debug.ts`, `web/src/lib/auth-handler.ts` | API 错误统一性、日志规范、跳转模式都受该层影响 |
| 实时训练前端 | `web/src/app/(user)/practice/[sessionId]/page.tsx`, `web/src/hooks/use-practice-websocket.ts` | 录音状态、暂停/恢复、重连、复杂度、潜在泄漏点集中在此 |
| 鉴权后端 | `backend/src/common/auth/*` | 忘记密码、修改密码、JWT secret、防敏感信息、HTTPException 使用方式 |
| 统一会话事实 / 生命周期 | `backend/src/common/db/session_lifecycle.py`, `common/conversation/*` | 会话状态流转、竞态条件、report/replay 一致性 |
| Admin 后端 / 前端 | `backend/src/admin/api/*`, `web/src/app/admin/*` | 权限细粒度、原生弹窗、空壳功能、导出/筛选/监控假数据 |
| 运维 / 性能 / 安全 | `backend/src/common/monitoring/*`, `.github/workflows/*`, requirements | N+1、索引、slow query、依赖审计、备份/容灾 |

---

## 4. 现有 GSD / 规划痕迹与本次审计的重叠

### 已有 M012 规划（2026-04-02 audit 衍生）
当前 `M012-ROADMAP.md` 已覆盖一部分“新手首练 launchability”问题：
- S01：认证与首页修复
- S02：导航与系统体验基础
- S03：个人中心与排行榜体验收敛

### 已进入 REQUIREMENTS 的条目
- `R029`：忘记密码自助完成
- `R030`：首页/仪表盘不得硬编码用户名、日期、版本号
- `R031`：登录页提供忘记密码入口
- `R032`：侧边栏必须包含历史记录入口

### 与 SYSTEM_AUDIT_REPORT 的冲突 / 不一致
SYSTEM_AUDIT_REPORT 中存在若干条已经与当前仓库状态不一致：
1. **忘记密码 / reset-password**：已存在前后端页面与 API，不是“从零缺失”。
2. **企业微信按钮**：当前 login 页已 disabled，并标注“即将支持”。
3. **侧边栏历史入口**：`web/src/components/layout/sidebar.tsx` 已包含“历史记录”。
4. **训练中暂停**：practice 页与 websocket 生命周期已存在 pause/resume 控制。`
5. **排行榜无说明**：`leaderboard/page.tsx` 底部已有评分说明。
6. **learner 完全没有 error boundary**：不准确；dashboard/report/replay 已有 route-level error/loading，但 coverage 仍不完整。
7. **报告导出缺失**：当前项目知识库明确要求继续断言“导出报告”不存在，说明该问题在现阶段不是默认实施目标，而是需要产品重新决策。

### 结论
本次规划必须先做 **审计归一化**，否则会把 stale finding、已修问题、真实缺口、产品 deferred 项混成一锅，导致执行模型浪费上下文和工时。

---

## 5. 当前代码成熟度判断

### 已经存在的能力（不是空项目）
- 认证登录、forgot/reset password 已经打通最小链路。
- learner 首页 / history / leaderboard / practice / report / replay 主链路存在。
- practice 页已具备：录音、pause/resume、end、retry-end、audio unlock、continuous audio uploader。
- report/replay/history/admin 已有大量 contract/unit/web focused tests。
- 会话状态流转已经集中在 `SessionLifecycleService`，说明不是散落式状态修改。

### 明显半成品 / 占位逻辑
- dashboard 存在多个带 UI 无闭环动作的按钮/筛选弹窗。
- profile 语速偏好只写 localStorage，且后端持久化是“try/catch 静默忽略”。
- profile“修改密码”按钮仍通过 `window.location.href = "/forgot-password"` 跳转，不是已完成的 in-session 修改密码体验。
- forgot/reset password 虽存在，但后端实现是：
  - 请求路径里动态 `CREATE TABLE IF NOT EXISTS`
  - 没有真实 EmailService
  - 注释写着 rate limit，但未见真正限流
  - 仍属于“能跑但不够稳”的过渡实现
- 多个 admin 页面仍存在 `alert()/confirm()`。
- 前端 `console.*` 使用面很广，远超 audit 列出的少量文件。
- backend 仍有 `print()`、裸 `HTTPException`、`except Exception` 大面积存在。

### AI / 快速开发痕迹
- 许多页面具备 polished UI，但动作未闭合（典型空壳按钮、筛选 UI 无逻辑、假监控数据）。
- 一些审计项是“建议”而非 defect，例如 dark mode / PWA / i18n / mobile full support，被写进同一问题表但并不都应进入当前 launch backlog。

---

## 6. 针对 SYSTEM_AUDIT_REPORT 的归一化结论

### A. 已修复 / 需文档回写关闭
- 忘记密码入口与 reset-password 页面
- 企业微信按钮 disabled 提示
- 历史记录侧边栏入口
- practice pause/resume 控制
- leaderboard 评分说明
- learner 局部 error/loading（dashboard/report/replay）

### B. 真实可执行缺口
- dashboard 首页空壳按钮、筛选 UI、版本弹窗内容仍硬编码/半静态
- 新用户 onboarding 缺失
- profile 修改密码体验不合理、语速偏好持久化不完整
- 缺少统一反馈/联系管理员入口
- learner error/loading 覆盖仍不完整（auth / training / history 等路由簇）
- front-end `console.*`、`window.location.assign/href`、admin 原生 `alert/confirm` 仍广泛存在
- auth/password-reset 实现需要从“过渡方案”升为正式 contract
- API 错误格式与 auth/service 异常模式仍不统一
- SessionLifecycle 并发安全尚无锁 / 版本控制证据
- WebSocket orchestrator 仍过大，且 reconnect/backpressure 规则还可以继续收口
- 敏感信息日志脱敏、RBAC 细化、依赖安全扫描、备份/容灾没有形成正式治理闭环

### C. 需要专项审计先出证据，再决定是否修
- N+1 / 索引 / slow query
- WebSocket / useEffect / event listener 泄漏
- 文件上传并发 / 分布式锁
- a11y 缺口的真实范围
- 时区显示问题的真实影响面
- 第三方依赖许可证合规性

### D. 当前不应直接当成“马上修复”的项目
- 自助注册 / 对外试玩
- 移动端完整适配（已与当前 PROJECT.md 的“桌面优先首发”冲突）
- i18n / 多语言
- 暗色模式
- PWA / 离线
- 报告导出（当前知识约束明确要求继续断言该按钮不存在，除非产品方向变化）

---

## 7. 关键风险与缺口

1. **活跃 M012 与新审计范围不一致**
   - 当前 M012 更像“首练 launchability 修补”，SYSTEM_AUDIT_REPORT 则试图覆盖 UX、后端规范、安全、性能、运维、国际化、容灾。
   - 如果不切开，会让单里程碑失控。

2. **auth/password reset 处于过渡实现**
   - 当前实现可以演示，但不适合作为正式安全基线。
   - 必须先补 migration、token storage seam、rate limit / email abstraction / tests。

3. **大量前端 console 与 admin 原生弹窗是系统性问题**
   - 不应按单文件打补丁；需要统一规则、helper、lint/test proof。

4. **SessionLifecycleService 具备统一入口，但无并发安全证据**
   - 这是“看起来设计不错，但在高并发/重试下是否安全”类型问题，必须专项验证。

5. **性能 / 安全 / 运维类条目大多是“未证实的风险”**
   - 不宜直接承诺“修复”；应先做 discovery slice，产出慢查询、索引、依赖漏洞、备份恢复现状等证据，再决定实现切片。

6. **当前项目知识与 REQUIREMENTS 对某些 audit finding 有明确反向约束**
   - 例如 report export 缺失并不是当前 defect；盲目恢复会违反现有事实线。

---

## 8. 与本次需求最相关的模块清单

### 前端
- `web/src/app/(auth)/login/page.tsx`
- `web/src/app/(auth)/forgot-password/page.tsx`
- `web/src/app/(auth)/reset-password/page.tsx`
- `web/src/app/(dashboard)/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `web/src/app/(dashboard)/leaderboard/page.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/components/layout/sidebar.tsx`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/lib/api/client.ts`
- `web/src/lib/debug.ts`
- `web/src/lib/auth-handler.ts`
- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`

### 后端
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/session_lifecycle.py`
- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/admin/api/*`
- `backend/src/common/monitoring/*`

### 测试
- `web/src/app/(auth)/login/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/hooks/use-practice-websocket.test.ts`
- `backend/tests/integration/test_auth_login_api.py`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/integration/test_session_lifecycle_api.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_replay_api.py`

---

## 9. 规划建议（供后续 GSD 计划使用）

- **先做一层“审计归一化 + stale finding closeout”**，再拆实现。
- **把 learner launchability / frontend hygiene / backend auth-error-contract / realtime concurrency / performance-security-ops governance 分成独立里程碑或 workstream**。
- **对“需要证据”的条目先做 discovery slice**，不要直接承诺修复结果。
- **所有 backend focused pytest 在 repo root 串行执行**，避免 `.coverage` 竞争。
- **不要恢复 report export 按钮**，除非用户明确改变产品方向并同步 requirement / knowledge。
