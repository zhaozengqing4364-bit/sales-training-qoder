---
id: S02
parent: M012
milestone: M012
provides:
  - 共享 learner navigation/help seam，可直接被后续 learner 页面与 shell 扩展复用。
  - 一个无静默 no-op 的 dashboard learner CTA contract，后续首页/个人中心扩展可沿用。
  - practice / report / replay 共用的 route error fallback seam，避免白屏和 copy/行为漂移。
requires:
  - slice: S01
    provides: 已落地的真实登录/首页用户信息与 learner dashboard 基线，使 S02 能在现有 learner shell 和 dashboard 首页之上收口导航、CTA 与 route fallback。
affects:
  - S03
key_files:
  - web/src/components/layout/sidebar.tsx
  - web/src/components/layout/dashboard-shell.tsx
  - web/src/app/(user)/practice/layout.tsx
  - web/src/components/layout/learner-help-entry.tsx
  - web/src/app/(dashboard)/page.tsx
  - web/src/components/learner/learner-route-error-state.tsx
  - web/src/app/(user)/practice/[sessionId]/error.tsx
  - web/src/app/(user)/practice/[sessionId]/report/error.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/error.tsx
  - web/src/app/(user)/practice/[sessionId]/error.test.tsx
key_decisions:
  - 继续把 `SidebarContent` 作为 learner 导航 authority seam，并把帮助/反馈挂在共享 shell seam，而不是在单个页面上零散补入口。
  - dashboard 首页 learner CTA 只允许复用已经存在的 `/history` 与 `/practice/{sessionId}/report` 路由族；做不到真实动作的能力必须显式禁用并写清说明。
  - practice / report / replay 全部使用 App Router `error.tsx` + 共享 `LearnerRouteErrorState` presenter，并只在 development 暴露受限 raw message。
patterns_established:
  - Learner 导航 authority 继续集中在 `SidebarContent`，新增辅助入口通过共享 shell seam 接入而不是页面级复制。
  - Learner-visible CTA 只复用已存在的真实 route family；暂不支持的能力用显式禁用态说明而不是静默 no-op。
  - App Router learner route 统一使用共享 fallback presenter，并把 raw diagnostics 限定在 development。
observability_surfaces:
  - `LearnerRouteErrorState` 带 tag 的 `console.error` 日志：`[LearnerRouteErrorState:practice-live]`、`[LearnerRouteErrorState:practice-report]`、`[LearnerRouteErrorState:practice-replay]`。
  - 三条 focused Vitest gate 分别锁定 learner shell 导航/帮助入口、dashboard CTA 退化策略与 practice route fallback。
  - close-out LSP diagnostics 覆盖 learner shell、dashboard 首页与 practice route 文件，结果为 clean。
drill_down_paths:
  - .gsd/milestones/M012/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M012/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M012/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-09T10:12:29.546Z
blocker_discovered: false
---

# S02: 导航与系统体验基础

**S02 把 learner 侧共享导航/反馈入口、dashboard 首页 CTA 以及 practice 路由 fallback 收口到真实可用 seams，避免新用户在首练闭环里被隐藏入口、空壳按钮或白屏卡住。**

## What Happened

S02 围绕“首练闭环里最容易把新人卡住的 learner 体验断点”做了三段收口。T01 没有在页面上分散补按钮，而是把 `SidebarContent` 继续作为 learner 导航 authority seam，稳定保留 `历史记录`，同时新增前端本地的 `LearnerHelpEntry` 并通过 dashboard shell 与 practice shell 两条共享壳层复用，保证 desktop / collapsed / mobile / practice 四类展示面都能看到一致的帮助与反馈入口。T02 则把 dashboard 首页剩余 learner CTA 全部逼回真实已存在的 route family：能工作的入口只指向 `/history` 或 `/practice/{sessionId}/report`，暂时不支持的筛选/详情能力改成显式禁用态和说明文案，避免继续留下看起来可点、实际什么都不做的空壳控件。T03 补齐了 live practice route 缺失的 App Router `error.tsx` 边界，并把 practice / report / replay 三个 learner 路由统一收口到 `LearnerRouteErrorState` presenter：用户在 route 报错时至少能看到友好的 fallback、`重试` 行为和安全返回路径，而开发环境下仍保留受限的 `error.message` 可见性和带 tag 的 `console.error` 诊断。

这组改动给下游 slice 提供了三条可复用模式：一是 learner 导航/辅助入口要挂在 shared shell seam，而不是页面本地补丁；二是 learner-visible CTA 只能复用已经存在的真实 route family，做不到就显式禁用；三是 App Router learner route 异常统一走共享 presenter + route-specific copy，避免 report/replay/practice 各自漂移。

## Operational Readiness (Q8)
- **Health signal:** learner dashboard 与 practice shell 都能稳定暴露 `历史记录`/帮助入口；dashboard 首页 CTA 只通向真实 `/history` / `/practice/{sessionId}/report`；practice/report/replay route 出错时都出现统一 fallback、`重试` 和返回路径。
- **Failure signal:** `历史记录` 或帮助入口在任一 learner shell 消失；dashboard 再次出现静默空壳 CTA；控制台出现 `[LearnerRouteErrorState:practice-live|practice-report|practice-replay]` 说明 route fallback 被触发。
- **Recovery procedure:** 先用 fallback 上的 `重试` 与返回链接恢复用户路径；若问题持续，优先检查共享 shell seam 与 presenter seam，然后重跑本 slice 三条 focused Vitest gate 来确认导航、CTA 和 route fallback 是否回归。
- **Monitoring gaps:** 当前帮助/反馈入口仍是 frontend-only affordance，没有持久化工单或使用量埋点；route fallback 也还没有集中式 boundary-hit telemetry，只能依赖页面表现与 tagged console 日志。

## Verification

已按 slice plan 重新运行三条 focused Vitest gate，并在 close-out 时额外确认 learner shell / dashboard / practice route 相关 TypeScript diagnostics 为 clean：

1. `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx" "src/app/(user)/practice/layout.test.tsx"` 通过，锁定 `SidebarContent` 仍是 learner nav authority seam，`历史记录` 与共享帮助入口在 dashboard/practice 两套 shell 中都可见。
2. `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` 通过，锁定 dashboard 首页 learner CTA 只落到真实 `/history` / `/practice/{sessionId}/report` 动作或显式禁用态，没有静默 no-op。
3. `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/error.test.tsx"` 通过，锁定 live practice route fallback 的 `重试` / 安全返回路径，以及 dev/prod 诊断显隐规则。
4. `lsp diagnostics web/src/components/layout/sidebar.tsx`、`dashboard-shell.tsx`、`learner-help-entry.tsx`、`web/src/app/(dashboard)/page.tsx` 以及 `web/src/app/(user)/practice/**/*.tsx` 全部无诊断问题。

## Requirements Advanced

- R032 — 把 `历史记录` 继续钉在 `SidebarContent` learner-nav authority seam 上，并通过 dashboard/practice 两套 learner shell 验证该入口不会再被隐藏。

## Requirements Validated

- R032 — Fresh Vitest gate `src/components/layout/sidebar.test.tsx` + `src/components/layout/dashboard-shell.test.tsx` + `src/app/(user)/practice/layout.test.tsx` 全绿，且 close-out diagnostics 对 learner shell/practice route 文件均无问题。

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

帮助/反馈入口当前仍是 frontend-only affordance，不会创建工单、发送请求或读取 admin support-email 配置。dashboard 首页也只收口到了现有 history/report 路由族，尚未实现新的筛选器或详情工作流。

## Follow-ups

S03 可以直接复用当前 learner shell seam 继续收口个人中心与排行榜体验；如果后续要把“帮助与反馈”升级成真实支持流程，优先在 `LearnerHelpEntry` 这条共享 shell seam 上接入后端联系方式/工单能力，而不是重新分散到各页面实现。

## Files Created/Modified

- `web/src/components/layout/sidebar.tsx` — 保留 `SidebarContent` 作为 learner 导航 authority seam，并锁定 `历史记录` 入口仍在共享侧边栏内。
- `web/src/components/layout/dashboard-shell.tsx` — 把共享 learner help/feedback affordance 挂到 dashboard learner shell。
- `web/src/app/(user)/practice/layout.tsx` — 在 practice learner shell 复用同一帮助/反馈入口。
- `web/src/components/layout/learner-help-entry.tsx` — 新增前端本地的 learner 帮助/反馈组件，使用有界 route/session 上下文而不依赖后台配置。
- `web/src/app/(dashboard)/page.tsx` — 把首页 learner CTA 收口到真实 `/history` / `/practice/{sessionId}/report` 动作或显式禁用态。
- `web/src/app/(dashboard)/page.test.tsx` — 补 dashboard 首页 CTA 回归，防止空壳按钮重新出现。
- `web/src/app/(dashboard)/history/page.test.tsx` — 锁定首页与 history 路由族之间的真实 learner 行为衔接。
- `web/src/components/learner/learner-route-error-state.tsx` — 新增 practice/report/replay 共用的 learner route fallback presenter，带 tagged console diagnostics。
- `web/src/app/(user)/practice/[sessionId]/error.tsx` — 为 live practice route 新增 App Router `error.tsx` 边界。
- `web/src/app/(user)/practice/[sessionId]/report/error.tsx` — 把 report route error boundary 改为复用共享 learner fallback presenter。
- `web/src/app/(user)/practice/[sessionId]/replay/error.tsx` — 把 replay route error boundary 改为复用共享 learner fallback presenter。
- `web/src/app/(user)/practice/[sessionId]/error.test.tsx` — 新增 focused Vitest 覆盖 live practice route fallback 的 retry / back / diagnostics 行为。
