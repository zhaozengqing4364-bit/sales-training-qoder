---
estimated_steps: 5
estimated_files: 5
skills_used:
  - safe-grow
  - react-best-practices
  - vitest
  - verification-before-completion
---

# T03: 为 live practice 补齐错误边界并统一 learner fallback

**Slice:** S02 — 导航与系统体验基础
**Milestone:** M012

## Description

补上 `web/src/app/(user)/practice/[sessionId]/error.tsx`，把 live practice 从白屏风险中拉出来；同时把 report / replay 现有的 `error.tsx` 收敛到同一个共享 learner fallback presenter。这里必须坚持 Next App Router 的 `error.tsx` seam，而不是改回 legacy `components/ErrorBoundary.tsx`。共享 presenter 需要保留 dev-only raw message 诊断边界，但生产态只能显示友好、有限的恢复文案。

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Next App Router `error.tsx` + `reset()` 契约 | 渲染可重试的 fallback，并提供安全返回导航；不能冒泡成白屏。 | 同 error，保持本地可恢复。 | 对异常 thrown value 做兜底，生产态展示通用文案。 |
| 共享 learner fallback presenter | route-specific props 缺失时退回通用标题 / 描述 / 返回文案。 | 同 error。 | 只在 development 展示受控 `error.message`；绝不展示 raw stack。 |

## Load Profile

- **Shared resources**: 仅 route error fallback 本地渲染。
- **Per-operation cost**: 成功路径零额外网络成本；仅在报错时渲染轻量 presenter。
- **10x breakpoint**: N/A，重点是诊断清晰度而不是吞吐。

## Negative Tests

- **Malformed inputs**: `error.message` 缺失、非 Error 抛出、route metadata 缺失都要安全回退。
- **Error paths**: live practice fallback 的 `reset()` 可调用；生产态隐藏 raw diagnostics，development 保留受控可见性。
- **Boundary conditions**: practice / report / replay 保持各自标题与返回语义，但共享统一 fallback presenter。

## Steps

1. 新建 `web/src/components/learner/learner-route-error-state.tsx`，封装共享 learner fallback presenter、tagged `console.error`、retry CTA、返回导航与 dev-only diagnostics。
2. 新增 `web/src/app/(user)/practice/[sessionId]/error.tsx`，并让 `report/error.tsx` 与 `replay/error.tsx` 复用共享 presenter。
3. 编写 `web/src/app/(user)/practice/[sessionId]/error.test.tsx`，锁定 live practice fallback 的 retry / safe navigation / dev-prod diagnostics 行为。

## Must-Haves

- [ ] `/practice/[sessionId]` 拥有自己的 App Router `error.tsx`。
- [ ] practice / report / replay 三处 fallback 复用同一个 learner presenter。
- [ ] 生产态不泄漏 raw diagnostics；development 保留受控 `error.message` 展示。
- [ ] focused 测试锁定 live practice fallback 的 retry 与 safe navigation。

## Verification

- `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/error.test.tsx"`
- Manual review fallback if needed: report / replay 错误页与 live practice fallback 使用一致的 presenter 样式与恢复动作。

## Observability Impact

- Signals added/changed: learner route failures统一带标签的 `console.error` 与可见 fallback UI。
- How a future agent inspects this: 运行 `error.test.tsx`，并检查 `error.tsx` 三个 route 是否都委托到共享 presenter。
- Failure state exposed: 过去的 white screen 会变成明确的 retry / 返回路径与受控诊断边界。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/page.tsx` — 当前缺少 live route `error.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/error.tsx` — 现有 report fallback 模式
- `web/src/app/(user)/practice/[sessionId]/replay/error.tsx` — 现有 replay fallback 模式

## Expected Output

- `web/src/components/learner/learner-route-error-state.tsx` — 共享 learner fallback presenter
- `web/src/app/(user)/practice/[sessionId]/error.tsx` — 新增 live practice route error boundary
- `web/src/app/(user)/practice/[sessionId]/report/error.tsx` — 改为复用共享 presenter
- `web/src/app/(user)/practice/[sessionId]/replay/error.tsx` — 改为复用共享 presenter
- `web/src/app/(user)/practice/[sessionId]/error.test.tsx` — live practice fallback focused regression
