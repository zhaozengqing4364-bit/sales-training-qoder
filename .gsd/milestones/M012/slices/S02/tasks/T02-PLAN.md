---
estimated_steps: 5
estimated_files: 3
skills_used:
  - safe-grow
  - react-best-practices
  - vitest
  - verification-before-completion
---

# T02: 把首页空壳按钮替换成真实 history/report 行为

**Slice:** S02 — 导航与系统体验基础
**Milestone:** M012

## Description

处理 `web/src/app/(dashboard)/page.tsx` 里还会误导 learner 的假动作：fake filter、inert detail、inert overflow。这里不能发明新的 dashboard-only API 或 detail route；必须复用已经工作的 `/history` 与 `/practice/{sessionId}/report` 路由族。任何暂时做不到的交互，都必须被明确 disabled 并说明原因，而不是看起来能点但没有结果。

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `api.dashboard.getHistory()` / dashboard payload | 回落到现有 empty / degraded state，并把 learner 引导到 `/history`；不能保留 fake filter/detail。 | 保持现有 loading skeleton 与失败降级，不新增阻塞。 | 缺失 `session_id` / `status` / `scenario_type` 时，相关 CTA 必须隐藏或 disabled，并给出明确说明。 |
| 既有 `/history` 与 `/practice/{sessionId}/report` 路由 | 只把 CTA 指向这些真路由；如果 session 尚不可报告，明确 disabled。 | 同 error：不允许再回到假 modal 流程。 | 绝不拼接不存在的 filter 参数或 detail path。 |

## Load Profile

- **Shared resources**: 仅复用现有 dashboard stats / recommendation / history 请求。
- **Per-operation cost**: 无新增网络请求，只是对已有 history item 做 link / disabled 判定。
- **10x breakpoint**: 现有 history list 渲染会先退化；本任务不应引入额外负担。

## Negative Tests

- **Malformed inputs**: 缺失 `session_id`、未完成 session、空 history 都要得到明确 learner-safe CTA。
- **Error paths**: history 加载失败时仍不能暴露 hollow actions。
- **Boundary conditions**: sales 与 presentation item 都继续使用共享 report / replay 路由族。

## Steps

1. 把首页 fake filter 行为替换成真实动作：优先跳转 `/history` 或明确说明“高级筛选请在历史页进行”。
2. 把 recent-history 卡片与 dialog 中的 inert detail / overflow affordance 替换为真实 report/history link，或基于 session 数据的明确 disabled 状态。
3. 扩展 `web/src/app/(dashboard)/page.test.tsx`，必要时补 `web/src/app/(dashboard)/history/page.test.tsx` 断言，确保首页不存在 silent no-op CTA。

## Must-Haves

- [ ] learner 在 dashboard 首页看见的 CTA 不再 silent no-op。
- [ ] 激活态 CTA 只指向现有 `/history` 或 `/practice/{sessionId}/report`。
- [ ] 不支持的 filter / detail 行为必须显式 disabled 并说明原因。
- [ ] S01 已锁定的真实用户名 / 动态版本 / empty-state 行为不能回归。

## Verification

- `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"`
- Manual review fallback if needed: homepage learner CTA 文案 / href 与 disabled 状态清晰可见。

## Observability Impact

- Signals added/changed: homepage CTA 从“点击无效果”变为可断言的真实 href 或 disabled state。
- How a future agent inspects this: 运行 `page.test.tsx` 与 `history/page.test.tsx`，查看 CTA 名称、href、disabled 文案。
- Failure state exposed: 新增或遗漏的 dead-end CTA 会直接体现在测试失败或页面文案不一致上。

## Inputs

- `web/src/app/(dashboard)/page.tsx` — 当前含 fake filter / inert detail / inert overflow 的首页
- `web/src/app/(dashboard)/page.test.tsx` — 现有 dashboard 首页回归测试
- `web/src/app/(dashboard)/history/page.tsx` — 已存在的真实历史页目标面
- `web/src/app/(dashboard)/history/page.test.tsx` — 现有 history route-family 回归测试

## Expected Output

- `web/src/app/(dashboard)/page.tsx` — learner 首页 CTA 全部改为真实动作或显式 disabled
- `web/src/app/(dashboard)/page.test.tsx` — 首页 CTA 无 dead-end 的回归断言
- `web/src/app/(dashboard)/history/page.test.tsx` — 必要的 route-family 兼容断言
