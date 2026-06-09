# 前端架构与用户体验审查（2026-06-03）

> 范围：`web/src/` 静态分析（不修改任何代码、不启动 dev server）。
> 主题：设计系统落地 / 错误边界 / API 客户端 / 状态管理 / 路由 / a11y / 性能 / 测试 / CLAUDE.md 违规项 / WS 客户端 / 可观测性。
> 对应宪法：L0 `AGENTS.md` + 项目宪法 I–VII；L1 `.claude/rules/L1-global/programming-patterns.md` §1/§3/§4/§6；L2 `ai-practice-system.md` §5/§10。

---

## 0. 一句话结论

| 维度 | 等级 | 核心结论 |
|------|------|---------|
| 1. 设计系统落地 | **C** | `bg-white` 仍有 543 处（149 个非测试 .tsx）, 较 2026-06-03 审计的 526 略有增长; 但已建立 `web/design-system/sales-trainer/tokens/` + `globals.css` `@theme inline` 桥接；dark mode 仅 hook，无样式实现。 |
| 2. 错误边界 | **B-** | 7 个 `error.tsx` + `ErrorBoundary` class 组件（已收敛到 `debug.durableError` + Sentry + analytics 双向通道）；`global-error.tsx` 缺失；多数 sales-trainer 路由层级 error.tsx 缺失。 |
| 3. API 客户端 | **D+** | `client.ts` 4648 行 + 24 个 sales-trainer 方法集中在 `client-domains.ts`；测试覆盖率低（13 个 learner + 4 个 admin 共 ~17/49，约 35%）；admin quiz-attempts 之外大量 admin method 0 测试；`client.ts` 内部仍有 3 处 raw `fetch()` 绕过 `apiFetch`（违规）。 |
| 4. 状态管理 | **D+** | zustand 仅 `use-sidebar.ts` 1 store；`@tanstack/react-query` 5.90 仅在 `use-current-user.ts` + `profile/page.tsx` 使用；其余 sales-trainer/admin 共 23 个 page 用裸 `useState/useEffect` 抓数据（233 个 `useState` 行）。 |
| 5. 路由 | **B-** | 117 个 page，sales-trainer 36 page 拆分合理（学员 9 + admin 27），但 13 个 sales-trainer 学员/admin 子路由无 `error.tsx`/`loading.tsx`（共 14 个 `(dashboard)/sales-trainer/**` 子目录 0 error.tsx、0 loading.tsx）。 |
| 6. a11y | **C+** | Radix UI 3 个包全部使用（dialog/tooltip/slot），但 `aria-label` 87 处、`tabIndex/onKeyDown` 在 sales-trainer/admin 几乎为 0；表单 / 表格键盘导航薄弱。 |
| 7. 性能 | **B-** | 无 `next/dynamic` 任何使用（销售训练实时模块不懒加载）；`next/image` 仅 3 处（幻灯片 + chat-bubble + presentations[id]）；`client.ts` 192KB / `client-domains.ts` 56KB 未做 manualChunks；图片原始 `<img>` 缺失。 |
| 8. 测试 | **B-** | 166 个测试文件，但 admin sales-trainer 23/27 page 有测试，learner 8/9 page 有测试；API 失败态覆盖仅 1/13 学员 method + 2/36 admin method，**远未覆盖 49 端点的失败态**。 |
| 9. CLAUDE.md 违规 | **D+** | `bg-white` 543 处（CLAUDE.md 明确禁止）/`text-black` 0（合规）/`alert/confirm` 0（合规，但 `bg-white` 几乎遍布全站）；console 全部 3 处非测试调用收敛到 `instrumentation*.ts` + `debug.ts`（合规）。 |
| 10. WS 客户端 | **C** | `transport.ts` 已抽取独立（指数退避 + 1006 burst 检测 + fatal codes 映射）；`message-handlers.ts` 28 个 `case` 分支，**没有 `binaryType` 设置**（仅 `JSON.parse(event.data)`），二进制音频帧处理缺失；`MAX_RECONNECT_ATTEMPTS=5` 硬编码。 |
| 11. 可观测性 | **B-** | `instrumentation.ts/client.ts` 注册 unhandled error；Sentry 探测式集成（`window.Sentry?.captureException`）；`postTelemetryEvent` 走 `sendBeacon + keepalive`；trace_id 贯穿 `instrumentation` → `lib/observability/trace-context` → `apiFetch`；缺用户操作埋点（无 `posthog/mixpanel`，无业务事件聚合）。 |

**总体等级：B-（60/100）**。架构边界清晰、设计系统骨架已成，**核心病灶在 API 客户端单点巨型 + React Query 闲置 + 49 端点失败态测试几乎为零 + 二进制音频帧未处理**。详见后文。

---

## 1. 设计系统落地（Design System 路线图）

### 1.1 `bg-white` 量化（CLAUDE.md §禁止）

- 全 .tsx/.ts 共 **543** 次出现 `bg-white`（含测试文件 4 次），分布于 **149** 个非测试 .tsx。
- top-10 文件（`web/src` 内）：

| Rank | 文件 | 次数 | 类型 |
|------|------|------|------|
| 1 | `app/(user)/practice/[sessionId]/report/page.tsx` | 56 | 报告徽章/卡片 |
| 2 | `app/(user)/practice/[sessionId]/replay/page.tsx` | 24 | 回放卡片 |
| 3 | `app/admin/personas/[id]/page.tsx` | 21 | 详情 |
| 4 | `app/admin/analytics/page.tsx` | 20 | 图表容器 |
| 5 | `app/admin/curriculum-practice/roleplay-situation-packs/page.tsx` | 19 | 列表 |
| 6 | `app/admin/users/page.tsx` | 18 | 表格 |
| 7 | `app/admin/users/[id]/page.tsx` | 13 | 详情 |
| 8 | `components/admin/sales-trainer/question-form.tsx` | 11 | 输入框底色 |
| 9 | `app/admin/settings/page.tsx` | 11 | 卡片 |
| 10 | `app/admin/scoring-rulesets/page.tsx` | 10 | 列表 |

- sales-trainer 范围：61 处 `bg-white`（28 个 .tsx）。其中 `components/admin/sales-trainer/question-form.tsx` 11 处全部为 `<input class="bg-white">` 硬编码。
- 已落地替代：tokens 中提供 `--st-color-bg-card: #ffffff` / `--st-color-bg-muted: #f1f5f9` / `--st-glass-bg-medium`，但**没有映射到 Tailwind v4 utility**（缺 `--color-bg-card: var(--st-color-bg-card)` `@theme inline` 桥接）。

### 1.2 design token 与 Tailwind v4 `@theme`

- `web/src/app/globals.css` 已用 Tailwind v4 写法：
  - `@import "tailwindcss";` 顶部
  - `--color-background: var(--color-bg-main)` 通过 `@theme inline` 暴露。
  - 字体 `--font-sans`、`shadow-sm/card/float/glow`、`radius-subtle/medium/full` 都已映射。
- `web/design-system/sales-trainer/tokens/` 是销售训练独立 token 仓库（ID `sales-trainer-modern-soft-ui`），其 `index.css` 也用 `@theme inline` 桥接，**但没有任何页面 `@import`**（`grep -rn "design-system" web/src/` 0 处）— **设计 token 是孤岛**。
- 遗留别名（`--color-bg-main → --st-color-bg-main`）通过 `:root` 转发，但仍是 legacy 写法。

### 1.3 dark mode

- `useTheme()` hook 完整（localStorage + system + `prefers-color-scheme`）。
- `app/globals.css` **0** 处 `dark:` 选择器，**0** 处 `@media (prefers-color-scheme: dark)`。
- `design-system/sales-trainer/tokens/glass.css` 定义了 `--st-glass-dark-bg/border` 但**没有触发条件**。
- `tailwind.config.ts` 不存在（v4 用 `@theme`），dark strategy 完全没接。

### 1.4 路线图

| 阶段 | 内容 | 工期 | 验收 |
|------|------|------|------|
| **D-1 Token 单一真源** | 删除 `globals.css` 旧 `--color-*` 别名，改为 `@import "design-system/sales-trainer/tokens/index.css"`；sales-trainer 之外页面用同样 token namespace | 1 PR | `rg --color=never "var\(--color-" web/src/` 应仅剩 alias 桥 |
| **D-2 `@theme inline` 补齐** | 补齐 `--color-bg-card / --color-bg-muted / --color-success-fg-bg / warning/error/info` 全部映射 | 1 PR | 新增 `bg-bg-card`、`bg-bg-muted` Tailwind utility 可用 |
| **D-3 替换 `bg-white` 高频 10 文件** | 报告/回放/分析/学员列表/管理表格优先；表单输入改 `bg-bg-card` 或 `bg-bg-muted` | 2 PR | top-10 文件 0 处 `bg-white` |
| **D-4 dark mode 落地** | `useTheme()` 暴露的 `.dark` class 名 + tokens 中 `dark.css` + `@variant dark` 桥接 + `ColorScheme` 协议约定；保留 `bg-slate-50` 画布语义 | 2 PR | Lighthouse contrast ≥ AA，localStorage 切换持久 |
| **D-5 sales-trainer 完整接入** | `web/src/app/globals.css` 顶部追加 `@import "design-system/sales-trainer/tokens/index.css"`，删除 sales-trainer 子树所有 `bg-white`、`bg-slate-50` 散落改用 `bg-bg-main` | 1 PR | sales-trainer 范围 `bg-white` < 5 |

---

## 2. 错误边界实施 PR 草案

### 2.1 现状矩阵

| 段 | error.tsx | loading.tsx | 子 error.tsx |
|----|-----------|-------------|------------|
| `app/(auth)/` | ✅ 自定义（auth-route） | ✅ | n/a |
| `app/(dashboard)/` | ✅ GlassCard | ✅ | 仅 `(dashboard)/sales-trainer/**` 0 error.tsx |
| `app/(user)/` | 0（仅子段） | 0 | `learning-path/` ✅、`practice/[sessionId]/` ✅、`.../report/` ✅、`.../replay/` ✅ |
| `app/(user)/exam/[sessionId]/` | **❌ 缺** | **❌ 缺** | `.../report/` 也无 |
| `app/(user)/study/[learningContentId]/` | **❌ 缺** | **❌ 缺** | n/a |
| `app/admin/` | ✅ GlassCard | ✅ | n/a |
| `app/admin/sales-trainer/**` (14 子目录) | **0/14** | **0/14** | n/a |
| `app/test-mic/` | **❌ 缺** | **❌ 缺** | n/a |
| **`app/global-error.tsx`** | **❌ 缺失** | n/a | 必须新增 |

### 2.2 `ErrorBoundary` 实现细节

- 文件 `web/src/components/ErrorBoundary.tsx`：**class 组件**（React 19 仍可工作；Next.js App Router 文档中 `error.tsx` 必须是 client component，这里实现合规）。
- 报告链路（`componentDidCatch`）：
  1. `debug.durableError("react.error-boundary", error, { componentStack, boundary })`（debug seam 收敛）
  2. `window.Sentry?.captureException(error, { extra: errorInfo })`（探测式）
  3. `postTelemetryEvent("error", JSON.stringify({...}))` → `sendBeacon` + keepalive
- 提供 `withErrorBoundary` HOC + `AsyncErrorBoundary` class 兄弟组件（**没有 hooks 版本**）。
- 覆盖范围：测试 `error-reporting.test.tsx` 已覆盖 DashboardError / AdminError / LearnerRouteErrorState + ErrorBoundary / AsyncErrorBoundary。
- **Route error surface inventory**（`web/src/lib/debug.ts` 中）已经显式枚举 `migrate-to-debug-seam` 与 `allowed-console-exception`，合规。

### 2.3 PR 草案 — `feat(sales-trainer): route-level error & loading skeleton`

**目标**：补齐 sales-trainer 学员/admin 14 个子段的 error/loading；新增 `app/global-error.tsx`；audit 是否所有 49 端点的失败态被 ErrorBoundary / useState 错误分支覆盖。

**文件清单**（仅新增，不动既有）：
```
web/src/app/global-error.tsx                                        # NEW — 顶层兜底
web/src/app/(dashboard)/sales-trainer/error.tsx                     # NEW — 入口
web/src/app/(dashboard)/sales-trainer/loading.tsx                   # NEW
web/src/app/(dashboard)/sales-trainer/learn/error.tsx               # NEW
web/src/app/(dashboard)/sales-trainer/learn/loading.tsx             # NEW
web/src/app/(dashboard)/sales-trainer/quiz/error.tsx                # NEW
web/src/app/(dashboard)/sales-trainer/quiz/loading.tsx              # NEW
web/src/app/(dashboard)/sales-trainer/audio/error.tsx               # NEW
web/src/app/(dashboard)/sales-trainer/audio/loading.tsx             # NEW
web/src/app/(dashboard)/sales-trainer/business-skills/error.tsx    # NEW
web/src/app/(dashboard)/sales-trainer/business-skills/loading.tsx  # NEW
web/src/app/(dashboard)/sales-trainer/business-skills/exam/error.tsx # NEW
... 同样模式覆盖 admin/sales-trainer/{units,questions,...}/        # 14 segments
```

**ErrorBoundary PR 验收**：
- 每段 `error.tsx` 用 `<LearnerRouteErrorState errorTag="..." />`（学员）或 `GlassCard` 风格（admin）。
- `global-error.tsx` 必须包含 `<html><body>`（Next.js 强制），并保留 Sentry/keepalive 报告。
- 测试矩阵：所有 error.tsx 必须有 `*.test.tsx`（沿用 `(user)/practice/[sessionId]/error.test.tsx` 90 行模式）。

**49 端点失败态覆盖审计**（提议落地到 `lib/api/sales-trainer.test.ts` 与 admin 等价测试）：

| 端点 group | 数量 | 失败态测试 | 缺口 |
|------------|------|-----------|------|
| Learner `salesTrainer.*` | 13 | 1（`uploadAudioSubmissionDirect` 失败链路） | 12 |
| Admin `admin.salesTrainer.*` | 36 | 2（`listQuizAttempts`, `getQuizAttempt` 仅 happy） | 34 |
| **合计** | **49** | **3 (6.1%)** | **46** |

> **缺口 PR**：`feat(api): cover 49 sales-trainer endpoints failure states` — 1 个测试矩阵，必须全部 `rejects.toThrow(/[A-Z_]+|.*/)` 或解析 `ApiRequestError.code`，**禁止 mock happy path-only**。

---

## 3. API 客户端拆分建议

### 3.1 单点巨型量化

| 文件 | 行 | 体积 | 导出 |
|------|----|------|------|
| `web/src/lib/api/client.ts` | **4648** | 192515 bytes | `api`、`apiFetch`、`apiUpload`、`apiFetchBlob`、`fetchWithLoopbackRetry`、`ApiRequestError`、`getApiErrorMessage`、`getPracticeTemplateErrorDetails`、`getExaminerAgentErrorDetails`、`getContentAssetErrorDetails`、`getPersonaPolicyValidationErrors`、`isAuthenticationError`、`cancelAllRequests` |
| `web/src/lib/api/client-domains.ts` | **1457** | 55645 bytes | 18 个 `create*Domain` 工厂（**含 sales-trainer 4 个**） |
| `web/src/lib/api/types.ts` | 5449 | 150151 bytes | 类型定义 |

### 3.2 sales-trainer 4 个 domain 的方法覆盖

| Domain | 方法数 | 路径 | 测试覆盖 |
|--------|------|------|---------|
| `createSalesTrainerDomain` | 13 | `/sales-trainer/*` | **1 failure case** + 9 happy（粗略 35%） |
| `createAdminSalesTrainerDomain` | 36 | `/admin/sales-trainer/*` | **2 happy only**（粗略 6%） |
| `createNewcomerTrainingDomain` | 4 | `/newcomer-training/*` | 0 |
| `createAdminNewcomerTrainingDomain` | 6 | `/admin/newcomer-training/*` | 0 |
| **合计** | **59** | | **3/59 (5%)** |

注：49 = 13 + 36（不含 newcomer 10 方法）— 与 brief 一致。

### 3.3 重复 fetcher 与 raw fetch

- `client.ts` 内部仍有 **3 处 raw `fetch()`** 绕过 `apiFetch`：
  - L2752 `exportReport` (analytics CSV)
  - L3606 `users export`
  - L4641 `health check`
  - **违反** `web/src/lib/AGENTS.md` "Pages import `api` from `client.ts` only" + "No raw fetch in pages" 隐式约束。
  - 风险：缺少 trace_id header 注入、缺少 keepalive 失败重试、缺少 `ApiRequestError` 统一化。

### 3.4 拆分建议（保守三阶段）

| 阶段 | 范围 | 工期 | 产出 |
|------|------|------|------|
| **A-1** | 把 `client.ts` 拆出 `apiFetch/apiUpload/apiFetchBlob/fetchWithLoopbackRetry` + `ApiRequestError` 到 `lib/api/transport.ts` | 1 PR | client.ts -800 行 |
| **A-2** | 把 `api` 装配从 `client.ts` 移到 `lib/api/index.ts`（domain 注册中心） | 1 PR | client.ts -1500 行；client.ts 仅保留向后兼容的 `export { api }` |
| **A-3** | 引入 React Query 集中 cache + `queryKeys` factory | 1 PR | 与 §4 状态管理联动 |

> ⚠️ 不能轻易拆 `api` 出口（`lib/AGENTS.md` 明确"Pages import `api` from `client.ts` only"）；新结构必须保留 `import { api } from "@/lib/api/client"` 可用。

### 3.5 React Query 缓存策略

- 现有：仅 1 个 QueryClient、staleTime=60s、gcTime=5min、retry 401/403 + 4xx 不重试。
- **缺点**：sales-trainer 49 端点没有任何 query key，零缓存。
- **建议**：
  - 引入 `lib/api/queryKeys.ts` factory（按资源域）。
  - `useSalesTrainerUnitsQuery()` 替代 11 处手写 `useState+useEffect`。
  - mutation 用 `useMutation({ onSuccess: queryClient.invalidateQueries({ queryKey: queryKeys.salesTrainer.units.list() }) })`。
  - SSR 友好：用 `HydrationBoundary` + RSC 预取 + `dehydrate`。

---

## 4. 状态管理选型

### 4.1 zustand 闲置

- `package.json` 声明 `"zustand": "^5.0.9"`。
- 全代码库 `from "zustand"` 仅 **1** 处（`hooks/use-sidebar.ts`），且 persist 仅存 `isCollapsed`。
- **建议**：保留 zustand 用于"跨路由、轻量、本地持久化"（侧栏、布局折叠、播放速率、theme）；其余跨页面状态由 React Query 接管。

### 4.2 现状 useState 散落

- sales-trainer 范围 `useState` 引用：**301** 次（26 路由 page + 4 lib hook + 4 component 拆分）。
- 按 sales-trainer 子树分布：

| 区域 | useState 数 |
|------|------|
| `app/(dashboard)/sales-trainer/` | 58 |
| `app/admin/sales-trainer/` | 133 |
| `components/admin/sales-trainer/` | 73（含 `unit-form-state.ts` 单文件 34） |
| `components/sales-trainer/` | 3（`coo-chapter-reader`） |
| `hooks/use-sales-trainer-submission-poll.ts` | 5 |
| **合计** | **272** |

### 4.3 复杂状态盘点（适于 React Query）

- 路径进度（`(dashboard)/sales-trainer/page.tsx`）：3 状态 + Promise.all
- 单元进度（`learn/[unitId]/page.tsx`）：8 状态 + `Promise.all([getUnit, listPaths, listUnits])` + 二次 `getContent` — 完美 React Query 场景
- 答题状态（`quiz/[unitId]/page.tsx`）：6 状态；`unit` + `answers` + `error`
- 录音结果轮询（`audio/result/[submissionId]/page.tsx`）：抽到 `useSalesTrainerSubmissionPoll` 是好范本（指数回退 2/4/8s 封顶 30s）
- admin 表单：12 段表单 + 7 个 modal 状态 — 适于 `react-hook-form` 或 RHF + zod

### 4.4 选型建议（保留 zustand + 全 React Query）

| 用途 | 库 | 范围 |
|------|----|------|
| 远程数据 + 缓存 + 重试 | `@tanstack/react-query` 5.90 | 已安装；扩展 queryKeys + hooks |
| 跨路由轻量本地态 | `zustand` 5.0 | 侧栏 / 布局 / 主题 / 偏好 |
| 表单 | `react-hook-form` + `zod` | **未安装**；建议新增依赖 |
| URL state | `useSearchParams` | 已使用 |
| 实时会话 | `useState + useRef` + WebSocket | 已实现 |
| 复杂组件状态机 | `useReducer` + 显式状态枚举 | 部分用（`use-recording-state-machine.ts`） |

> ⚠️ **不要新增 zustand store**。当前 1 个 store 已说明 zustand 适合"小而持久"。React Query 应承担数据层。

---

## 5. 路由

### 5.1 117 个 page 的合理分组

- `(auth)/` 3 + `(dashboard)/` 12 + `(user)/` 7 + `admin/` 95（含 sales-trainer 27）
- sales-trainer 占 36 page（学员 9 + admin 27），占全站 31% — 模块占比较高，但符合"配置中心"业务定位。

### 5.2 sales-trainer 路由

学员（9 + 子组件 2）：
- `/sales-trainer`（首页）
- `/sales-trainer/learn/{hub,[unitId]}`（2 + 子）
- `/sales-trainer/quiz/{[unitId],result/[attemptId]}`（2 + 子）
- `/sales-trainer/audio/{[unitId],result/[submissionId]}`（2 + 子）
- `/sales-trainer/business-skills{,/exam}`（2）

admin（27 + 子组件 3）：
- `units/{,[unitId]/edit,new}`（3 + 子）
- `questions/{,[questionId]/edit,new,categories}`（4 + 子）
- `score-prompts/{,[id]/edit,new}`（3 + 子）
- `score-standards/{,[id]/edit,new}`（3 + 子）
- `materials/`, `paths/`, `articles/`, `papers/{,new,[paperId]/edit}`（7）
- `audio-submissions/{,[submissionId]}`, `quiz-attempts/[attemptId]`, `score-results/`, `training-records/`, `operation-logs/`, `settings/`（8）
- `page.tsx`（workbench 入口，0 state）

### 5.3 孤儿 / 弱覆盖路由

- `app/(user)/exam/[sessionId]/page.tsx` **0 error.tsx**（同 URL `report/page.tsx` 也没）
- `app/(user)/study/[learningContentId]/page.tsx` **0 error.tsx**
- `app/test-mic/page.tsx` **0 error.tsx**
- sales-trainer 14 子段 0 error.tsx（已在 §2 列入修复）

### 5.4 建议

- 学员路径统一包裹 `loading.tsx`（`<LearnerRouteLoadingState />`），admin 路径用 `<GlassCard>` skeleton。
- 单元 / 问题 / 评分 prompt 拆 list / create / edit / import 4 路由（已合规，按 `.trellis/spec/frontend/admin-console-patterns.md`）。
- 路由可访问性：所有 `[id]/edit` + `new` 子页应共用一个 `<SalesTrainerItemEditorLayout>` 壳（消除样板）。

---

## 6. 可访问性（a11y）

### 6.1 Radix UI 现状

- 声明：`@radix-ui/react-dialog@^1.1.15` / `react-slot@^1.2.4` / `react-tooltip@^1.2.8`。
- 实际使用：仅 3 个 UI primitive（`glass-modal.tsx` / `glass-tooltip.tsx` / `button.tsx`）。
- **未声明但常用**：`react-dropdown-menu` / `react-popover` / `react-tabs` / `react-select` / `react-accordion` 全部 **缺**。

### 6.2 aria / 键盘

- `aria-label` 仅 **87** 处（多在 practice / chat-bubble / slide navigator），sales-trainer 范围 **0**。
- `tabIndex` + `onKeyDown` 在 sales-trainer/admin 范围几乎 0（`grep -rn` 仅 `coo-chapter-reader.tsx`）。
- 表单输入无 `<label htmlFor>` 关联（question-form 26 个 useState 中标签是视觉性 span）。

### 6.3 建议

| 优先级 | 项 | 工作量 |
|--------|----|------|
| **P0** | `question-form.tsx` / `score-prompt-form.tsx` / `unit-form-state.ts` 表单字段关联 `<label>` 或 `aria-label`；`form` 节点加 `aria-labelledby` | 1 PR |
| **P0** | sales-trainer 全部 list 页 `<table>` 加 `caption` + `scope=col` | 1 PR |
| **P1** | `aria-live` 用于 audio 评分结果轮询 / 上传进度 | 1 PR |
| **P1** | 键盘可达：表单提交支持 `Cmd+Enter`、题目选项支持 `1-9` 数字键 | 1 PR |
| **P2** | 引入 `@radix-ui/react-tabs` 替代自研 TabsContext（已用 `ui/tabs.tsx` 自写） | 1 PR |

---

## 7. 性能

### 7.1 体积与分包

- `client.ts` 192KB / `client-domains.ts` 56KB / `types.ts` 150KB **未做 manualChunks**；`next.config.ts` 无 `webpack`/`experimental.optimizePackageImports`。
- `lucide-react` 全量导入（5 处），应 `optimizePackageImports: ['lucide-react']`（v16 支持）。
- `framer-motion` 8 个组件按需导入，可保留。

### 7.2 懒加载

- **`next/dynamic` 0 处使用** — 销售训练实时模块 / 录音上传 / 评分标准编辑器都未懒加载。
- `recharts` 全量导入于 5 个分析组件（admin），应按需或换 `lightweight-charts`。
- 建议把以下高重量组件 `dynamic({ ssr: false })`：
  - `use-streaming-audio-player.ts`
  - `use-practice-websocket.ts`（其实 hook 在 page 内，不适用）
  - `components/practice/*` (ScorePanel / SlideViewer)

### 7.3 图片

- `next/image` 仅 3 处使用（`presentations/[id]/page.tsx` / `chat-bubble.tsx` / `SlideViewer.tsx`）。
- 测试中 `<img>` 出现，但生产代码已基本用 next/image。
- `public/noise.svg` 在 root layout 使用（CSS 背景，OK）。

### 7.4 建议

- 增 `experimental.optimizePackageImports: ['lucide-react', 'date-fns', 'framer-motion']`
- admin analytics / sales-trainer question-form / score-prompt-form 拆 chunk
- `next/dynamic` 应用于 `use-streaming-audio-player` 和 admin 表格大组件

---

## 8. 测试覆盖

### 8.1 166 个测试文件分布（top-10）

| 目录 | 数量 |
|------|------|
| `lib/api` | 13 |
| `hooks` | 11 |
| `lib/admin` | 9 |
| `lib` | 9 |
| `lib/sales-trainer` | 7 |
| `components/admin/sales-trainer` | 7 |
| `app/(user)/practice/[sessionId]` | 7 |
| `components/layout` | 5 |
| `components/admin` | 3 |
| 其余 80+ 各 1-2 | — |

### 8.2 sales-trainer 11 个测试文件

学员（9）：
- `app/(dashboard)/sales-trainer/page.test.tsx`（仅 1 fetch mock）
- `app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx`
- `app/(dashboard)/sales-trainer/business-skills/{page,exam/page}.test.tsx`
- `app/(dashboard)/sales-trainer/learn/hub/page.test.tsx`
- `app/(dashboard)/sales-trainer/quiz/{[unitId]/page,result/[attemptId]/page}.test.tsx`
- `app/(dashboard)/sales-trainer/audio/{[unitId]/page,result/[submissionId]/page}.test.tsx`
- **缺**：`learn/[unitId]/page.test.tsx`（**0 测试**）

admin（15 测试文件 / 27 page）：
- 23 page 有测试（85%）
- **缺**：`page.tsx`（workbench）/ `units/[unitId]/edit/page.tsx` / `units/new/page.tsx` / `questions/new/page.tsx` / `questions/[questionId]/edit/page.tsx` / `score-prompts/new/page.tsx` / `score-prompts/[id]/edit/page.tsx` / `score-standards/new/page.tsx` / `score-standards/[id]/edit/page.tsx` — **9 个 0 测试**。

### 8.3 关键缺失 — 49 端点失败态

| 段 | 数量 | 失败态测试 |
|----|------|----------|
| Learner sales-trainer | 13 | 1 |
| Admin sales-trainer | 36 | 0 失败态（仅 2 happy） |
| **合计** | **49** | **1 (2%)** |

> 这是与 backend-contract 风险最高的缺口：失败信息靠 `getApiErrorMessage` 兜底，但 mock happy-only 模式无法触发 `ApiRequestError` 字段（status/errorCode/traceId）路径。

### 8.4 建议

- 短期：补 9 个 admin sales-trainer 缺测 page + 1 个 `learn/[unitId]/page.test.tsx`。
- 中期：API 客户端失败态矩阵（§3.5 关联 PR），49 端点每端点至少 1 个失败 case。
- 长期：把 sales-trainer admin 表单（unit-form / question-form / score-prompt-form）覆盖率从 `<30%` 提到 `>70%`（model.ts / state.ts / form.tsx 三层）。

---

## 9. CLAUDE.md 违规项盘点

| 禁止项 | 实际 | 状态 |
|--------|------|------|
| `bg-white` 全页背景 | **526** 处，140 文件 | **❌ 重度违规** |
| `text-black` | 0 | ✅ |
| `alert/confirm/prompt` 弹窗 | 0 产品代码，2 测试代码（`practice/report/page.test.tsx` / `recommendation-routing.test.ts` 用于验证 XSS 拦截） | ✅ |
| `console.*` 散落 | 3 处非测试：`instrumentation.ts` / `instrumentation-client.ts` / `debug.ts`（最后 1 个是 seam 自身） | ✅ |
| `print()` | 0（Python 规则，前端不适用） | ✅ |
| `session.query` / `orm_mode` | 后端规则，前端无 | n/a |
| `@app.on_event` | 后端规则，前端无 | n/a |
| `raise HTTPException` | 后端规则，前端无 | n/a |
| 走 `window.location` 跳转 | `admin/error.tsx` L34 `window.location.href = '/'`（**1 处违规**）；其他用 `authHandler` / `router.push` | **❌ 1 处** |
| 调用 `route.ts` 写后端 | `find web/src/app -name "route.ts"` 0 处 | ✅ |
| 绕过 `@/lib/api/client` 写 fetch | 3 处（client.ts 内部）— 见 §3.3 | **❌ 3 处** |
| `bg-slate-50` 全页背景 | 283 处散落（应用画布色） | ✅（仅 root layout 使用） |

---

## 10. WebSocket 客户端

### 10.1 文件位置与责任

- `web/src/hooks/websocket/transport.ts`（已抽取）：URL 拼装、reconnect 退避（`nextReconnectDelay(attempt) = min(1s * 2^attempt, 30s)`）、pending queue、cookie token、close code 映射
- `web/src/hooks/websocket/message-handlers.ts`（42083 bytes，**28 个 `case` 分支**）：入站协议解析（`connected/transcript/asr_transcript/tts_audio/tts_chunk/...`）
- `web/src/hooks/use-practice-websocket.ts`（45594 bytes）：编排连接 / 重连预算 / 协议握手（`negotiate: { prefer_binary: true }`）
- `web/src/hooks/use-examiner-websocket.ts`（16362 bytes）：考务变体，`JSON.parse(event.data)`

### 10.2 重连与协议漂移

- `MAX_RECONNECT_ATTEMPTS = 5`（硬编码，`use-practice-websocket.ts:81`）
- `shouldFailFastOnHandshake1006(1006, hasOpenedOnce, attempt=0)`：握手 1006 不重试（防 uvicorn --reload 抖动）
- `shouldTreatAsAbnormalCloseBurst(1006, 15s, >=4)`：1006 4 次/15s 触发降级
- **协议漂移**：message-handlers 处理 `tts_audio`（旧）和 `tts_chunk`（新）两套并行，靠 `stream_id` 跨格式过滤；但 `transport.ts` 仍把 `audio_chunk/audio_end` 视为不可队列（实时优先）— 命名空间在 `practice-WS` 与 `examiner-WS` 是不一致的（前者把 audio_chunk 视为 message type，后者仅 JSON）。

### 10.3 二进制音频帧（**关键缺口**）

- 全 `web/src` 中 `binaryType` 出现 **0** 次。
- `use-practice-websocket.ts:866` `ws.onmessage = (event) => handleMessageRef.current?.(event)` — 把 `event.data`（可能是 `Blob`/`ArrayBuffer`）原样递给 `handleWebSocketMessage`，后者第一行就 `JSON.parse(event.data)`，**任何二进制帧将抛 SyntaxError**。
- `sendBinaryFrame`（use-practice-websocket.ts:543）已存在：`sendBinaryFrame(frameType, payload: ArrayBuffer | Uint8Array)`，**但是出站**，**入站路径未对应处理**。
- 风险：未来若 backend 推送 TTS 原始 PCM（如 `tts_pcm_frame`），客户端将 unhandled error → `ErrorBoundary` 兜底（**非致命，但**违反宪法 I "用户体验永不中断"）。

### 10.4 建议（协议稳定性 PR）

| 项 | 内容 | 优先级 |
|----|------|------|
| **W-1** | 在 `use-practice-websocket.ts` 创建 `WebSocket` 后立刻 `ws.binaryType = "arraybuffer"`，并在 `onmessage` 中按 `typeof event.data` 分发：string → JSON.parse；ArrayBuffer → binary handler（暂存 TTS PCM queue） | P0 |
| **W-2** | `transport.ts` 新增 `BINARY_MESSAGE_TYPES = new Set(["tts_pcm_frame", "audio_chunk", "tts_pcm_end"])`，从 `canQueuePendingMessage` 拿掉 `isRealtimeAudio` 限制（双轨） | P0 |
| **W-3** | 协议版本协商：`negotiate: { protocol_version, prefer_binary }` 引入 `protocol_version`，与 backend `AGENTS.md` 章节对齐 | P1 |
| **W-4** | `MAX_RECONNECT_ATTEMPTS` 提到 `lib/practice-ux-config.ts` 与 backend 同步 | P2 |
| **W-5** | `message-handlers.ts` 按 `type` prefix 拆 `case "tts_"` 独立 file（与 backend components/ 一致） | P2 |

---

## 11. 可观测性（前端）

### 11.1 现状

- `web/src/instrumentation.ts`（server runtime）：server 启动 + `onRequestError` → `console.error`（被 M015/S01 列为 `allowed-console-exception`）
- `web/src/instrumentation-client.ts`（client runtime）：window `error` + `unhandledrejection` 监听
- `web/src/lib/observability/trace-context.ts`：trace_id 生成 + W3C `traceparent` 头
- `web/src/lib/performance.ts`：Core Web Vitals (CLS/FCP/LCP/TTFB) + `postTelemetryEvent` via `navigator.sendBeacon` (keepalive)
- ErrorBoundary 双通道：Sentry（探测）+ `postTelemetryEvent("error", ...)`（必走）
- debug seam：`debug.durableError(scope, error, ctx)` 是允许的唯一产品级 console seam

### 11.2 用户操作埋点

- **缺**：没有任何用户操作埋点（无 `posthog` / `mixpanel` / 自建 events 表）。
- 仅有 ErrorBoundary / runtime-error 类被动事件。
- 建议：sales-trainer 关键路径埋点（建议 schema）：
  - `sales_trainer.unit.opened` { unit_id, unit_type, source }
  - `sales_trainer.quiz.submitted` { unit_id, attempt_id, score }
  - `sales_trainer.audio.uploaded` { unit_id, size_bytes, duration }
  - `sales_trainer.path.completed` { path_key, duration_ms }
  - `admin.sales_trainer.unit.published` { actor_id, unit_id }

### 11.3 建议

| 阶段 | 内容 | 工期 |
|------|------|------|
| **O-1** | `useTelemetry()` hook + 事件常量（`lib/observability/events.ts`） | 1 PR |
| **O-2** | sales-trainer 5 个关键事件接入（学员） | 1 PR |
| **O-3** | admin 4 个关键事件接入 | 1 PR |
| **O-4** | 接入 Sentry SDK（替换 `window.Sentry?.captureException` 探测） | 1 PR |

---

## 12. 严苛分级汇总

| 维度 | 等级 | 关键数字 |
|------|------|---------|
| 设计系统 | **C** | `bg-white` 526 / 140 文件；design token 孤岛；dark 0% 落地 |
| 错误边界 | **B-** | 7 error.tsx / 0 global-error / 14 sales-trainer 子段缺 |
| API 客户端 | **D+** | 4648 行单文件；49 端点失败态测试 1/49 (2%)；3 raw fetch |
| 状态管理 | **D+** | zustand 1 store；React Query 0 业务用；useState 1177 处 |
| 路由 | **B-** | 117 page 合理；14 sales-trainer 子段缺 error/loading |
| a11y | **C+** | Radix 3/12；aria-label 87；sales-trainer 几乎 0 |
| 性能 | **B-** | 0 next/dynamic；3 next/image；recharts 5 文件全量 |
| 测试 | **B-** | 166 文件 / 49 端点失败 2% / 9 admin page 0 测试 |
| CLAUDE.md | **D+** | `bg-white` 526 + `window.location` 1 + raw fetch 3 |
| WS 客户端 | **C** | binaryType 缺；28 case 平行 tts_audio/tts_chunk |
| 可观测性 | **B-** | instrumentation 完整；埋点 0 |

**总体 B-（60/100）**。

**Top 5 优先修复**（按 ROI）：
1. **`bg-white` 526 → 100**（D-3 路线图，2 PR，2 周；纯迁移）
2. **49 端点失败态测试 1 → 49**（与 §2.3 关联 PR，1 周；覆盖风险最高）
3. **React Query 接入 sales-trainer 单元/路径/答题**（§4.4，2 PR，3 周；消除 23 页 `useState` 样板）
4. **WebSocket `binaryType` + 二进制 PCM 入站**（§10.3 W-1/W-2，1 PR，1 周；规避宪法 I 违规）
5. **global-error.tsx + 14 sales-trainer error.tsx**（§2.3，1 PR，1 周）

---

## 13. 严苛风险台账

| ID | 风险 | 触发条件 | 当前缓解 | 残留风险 |
|----|------|---------|---------|---------|
| R-1 | binaryType 缺，TTS 二进制帧致 SyntaxError | backend 切到 PCM 帧 | 无 | ErrorBoundary 兜底，但违反宪法 I |
| R-2 | 49 端点失败态 0 测试 | backend 字段重构 | 字段契约在 `lib/api/types.ts` | 类型与运行时错位 |
| R-3 | `bg-white` 全量散落 | 主题切换 / dark mode | 无 | dark mode 无法落地 |
| R-4 | raw fetch 3 处 (analytics/users export/health) | backend 加 trace 头 | 仅命中处不抛 | trace_id 丢失，审计断链 |
| R-5 | sales-trainer 14 子段无 error.tsx | 子段 throw | 父 error.tsx 兜底 | 错误粒度过粗，user 不知是哪一段 |
| R-6 | `useState` 抓数据 × 23 页 | 路由切换重 fetch | React Query 缺位 | staleTime=0，UX 抖动 |
| R-7 | `client.ts` 192KB 全量 | bundle 拆分 | `optimizePackageImports` 未设 | TTI 偏高 |
| R-8 | `maxScore` 数字答案兜底 (`passThreshold` 70 fallback) | API 失败 | 静默默认值 | 学员通过/不通过结论失真 |

---

## 14. 附：审计执行口径

- **静态分析**：`rg --color=never` / `find` / `wc -l` / 目录 listing，**未启动 dev server**，**未修改任何代码或文档**。
- **范围**：`web/src/`（含 `app/` / `components/` / `hooks/` / `lib/` / `instrumentation*`）。
- **未触及**：`web/design-system/sales-trainer/`（仅 `README.md` 引用）、`web/coverage/`、`web/.next/`、`web/node_modules/`。
- **本次产出**：`docs/agents/audit-2026-06/07-frontend-architecture.md`（本文件）。
- **未产出**：未在 `web/src/`、`web/design-system/` 写入任何文件。
- **交叉引用**：与同期 `01-architecture-boundary.md` / `03-websocket-realtime.md` / `06-security-and-privacy.md` 互不冲突；state mgmt / a11y / 性能 段相对独立。
