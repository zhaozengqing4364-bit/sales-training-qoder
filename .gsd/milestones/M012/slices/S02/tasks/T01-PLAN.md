---
estimated_steps: 6
estimated_files: 7
skills_used:
  - safe-grow
  - react-best-practices
  - vitest
  - verification-before-completion
---

# T01: 锁定共享 learner 导航并接入壳层反馈入口

**Slice:** S02 — 导航与系统体验基础
**Milestone:** M012

## Description

把 `R032` 锁在真正的 authority seam：`web/src/components/layout/sidebar.tsx` 里的 `SidebarContent`。不要在单个页面上补一个临时 history 按钮。与此同时，补一个 frontend-only 的 learner 帮助 / 反馈入口，并让它同时出现在 `DashboardShell` 与 `web/src/app/(user)/practice/layout.tsx` 两套 learner 壳层里。这个入口只能依赖本地路由 / 会话上下文与静态帮助文案，不能绑定当前未接线的 admin 支持邮箱设置，也不能假装有真实工单系统。

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `useCurrentUser` / dashboard 壳层鉴权状态 | 保持 history nav 与帮助入口的静态结构不依赖新 fetch；让现有 auth redirect 行为继续工作。 | 同 error：帮助入口本地渲染，不阻塞壳层。 | 忽略异常 user 字段，只保留受控帮助文案。 |
| `next/navigation` 路由上下文 | 无法拿到 pathname / `sessionId` 时退回通用帮助文案。 | 不显示上下文元数据，但入口仍可用。 | 绝不回显 query token 或超长原始 URL，只展示有界 route / `sessionId`。 |

## Load Profile

- **Shared resources**: 仅 learner 壳层本地渲染；无新网络请求。
- **Per-operation cost**: 每个壳层多一个帮助入口 / dialog，开销可忽略。
- **10x breakpoint**: N/A，优先风险是 UI 漂移而非资源耗尽。

## Negative Tests

- **Malformed inputs**: 缺失 `currentUser`、缺失路由上下文、collapsed sidebar、mobile drawer、practice layout 都要安全渲染。
- **Error paths**: 帮助入口不能依赖 admin 支持邮箱配置或异步请求；鉴权失败时也不能引入新的阻塞。
- **Boundary conditions**: Desktop sidebar、collapsed sidebar、dashboard mobile drawer、practice shell 都出现预期 affordance。

## Steps

1. 新建 `web/src/components/layout/learner-help-entry.tsx`，提供 frontend-only 帮助 / 反馈入口，文案明确说明“请把页面路径 / 会话编号反馈给管理员”，并对 route / `sessionId` 做有界展示。
2. 保持 `SidebarContent` 作为 learner 导航唯一 authority seam，确认 `历史记录` 入口继续存在，并把帮助入口挂到 `DashboardShell` 与 `web/src/app/(user)/practice/layout.tsx`。
3. 新增 focused Vitest 覆盖：锁定 shared nav 中的 `历史记录`、dashboard shell 中的帮助入口、practice shell 中的帮助入口。

## Must-Haves

- [ ] `SidebarContent` 明确保留 `历史记录` 作为 learner nav 入口。
- [ ] 同一 learner help/feedback 组件被 dashboard shell 与 practice shell 复用。
- [ ] 实现不读取 `web/src/app/admin/settings/page.tsx` 的 mock 支持邮箱配置。
- [ ] 桌面 / 折叠 / 移动 / practice 壳层都有回归测试覆盖。

## Verification

- `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx" "src/app/(user)/practice/layout.test.tsx"`
- Manual review fallback if needed: learner 帮助入口可见且文案不依赖支持邮箱配置。

## Observability Impact

- Signals added/changed: learner 帮助入口显式暴露受控 route / `sessionId` 上下文，替代“无处反馈”的隐性失败。
- How a future agent inspects this: 运行 `sidebar.test.tsx`、`dashboard-shell.test.tsx`、`practice/layout.test.tsx`，并查看壳层是否渲染 `历史记录` 与帮助入口。
- Failure state exposed: 壳层缺入口、入口串到 mock support-email、或上下文泄漏过多信息都会被测试直接打断。

## Inputs

- `web/src/components/layout/sidebar.tsx` — learner nav authority seam
- `web/src/components/layout/dashboard-shell.tsx` — dashboard learner shell
- `web/src/app/(user)/practice/layout.tsx` — live learner shell

## Expected Output

- `web/src/components/layout/learner-help-entry.tsx` — shared frontend-only learner help / feedback affordance
- `web/src/components/layout/sidebar.tsx` — shared nav still exposes `历史记录`
- `web/src/components/layout/dashboard-shell.tsx` — dashboard shell mounts help entry
- `web/src/app/(user)/practice/layout.tsx` — practice shell mounts help entry
- `web/src/components/layout/sidebar.test.tsx` — shared nav regression coverage for `历史记录`
- `web/src/components/layout/dashboard-shell.test.tsx` — dashboard shell help-entry coverage
- `web/src/app/(user)/practice/layout.test.tsx` — practice shell help-entry coverage
