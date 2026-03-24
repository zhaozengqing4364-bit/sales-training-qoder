---
estimated_steps: 4
estimated_files: 4
skills_used:
  - safe-grow
  - test-driven-development
  - accessibility
  - fixing-accessibility
  - baseline-ui
  - react-best-practices
  - vercel-react-best-practices
  - agent-browser
  - verification-before-completion
---

# T03: 让共享 report page 按 scenario_type 渲染 PPT 会后复盘

**Slice:** S07 — PPT 对练会后统一复盘可用化
**Milestone:** M001

## Description

这个任务把 T02 的 canonical presentation contract 翻译成真实可用的用户界面。当前 `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 无论 session 是 sales 还是 presentation，都会默认构建三张 sales score card、渲染“销售推进结果 / 下一轮销售目标 / 销售推进基线”，并且无条件请求 `getKnowledgeCheck(sessionId)`。这意味着即使 backend 已经返回了 PPT-specific facts，用户仍然会在 shared report page 上看到 sales 语义。T03 要做的是最小 scenario branch：presentation 场景下展示 canonical `presentation_review`、显式 degraded 文案与再练入口；sales 场景继续走现有视图。

## Steps

1. 先扩展 `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`，写 failing presentation-focused assertions：页面展示六维 PPT 评分、逐页总结、coverage / forbidden / missing diagnostics 与建议；`销售推进结果`、`销售推进基线`、`知识库命中检测` 不出现；retry 仍带 `presentation_id`；缺页码历史数据时显示 presentation-specific degraded 文案而不是 sales fallback。
2. 在 `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 基于 `report.scenario_type` 分支加载与渲染：presentation 场景跳过 knowledge-check 请求，消费 canonical `presentation_review` 作为 baseline；sales 场景保持现有 cards/knowledge-check 逻辑。
3. 如有必要，在 `web/src/lib/session-evidence.ts` 增加小而共享的 label/format helper，用现有 `GlassCard` / `Button` / 语义化文本把 page summaries、coverage 和 degraded copy 渲染出来；不要引入新的 UI 系统或复杂交互。
4. 运行 focused web tests，并对本地 completed presentation session 做浏览器/UAT：确认共享 report page 现在确实展示 PPT postmortem、enhanced report 缺失时仍保留 canonical PPT facts、且 retry 继续指向同一课件。

## Must-Haves

- [ ] presentation 场景必须以 canonical `presentation_review` 为 baseline 渲染共享 report page，不再显示 `销售推进结果`、`下一轮销售目标`、`销售推进基线` 和 `知识库命中检测` 这类 sales-only 区块。
- [ ] 页面只能在 sales 场景请求 knowledge-check；presentation 场景必须停止这类无意义 client request，避免产生噪声与错误态。
- [ ] 缺页码历史数据时，页面必须显示 presentation-specific degraded 文案并保留 retry CTA；不能因为 enhanced report 缺失或 coverage 不完整而回退到 sales UI。

## Verification

- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
- Runtime/UAT — 在本地打开一个 completed presentation session 的 `/practice/{sessionId}/report`，确认 PPT 评分/逐页总结/coverage 展示正常，sales-only sections 不出现，且“按目标再练一轮”继续携带 `presentation_id`。

## Observability Impact

- Signals added/changed: page-level report diagnostics 需要能区分 `scenario_type` 分支、presentation 下 knowledge-check skip、enhanced-report unavailable fallback 与 degraded page-metadata copy。
- How a future agent inspects this: 查看 `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`，并在浏览器打开 `/practice/{sessionId}/report` 对照 network/console logs 验证 presentation 场景没有 knowledge-check 请求。
- Failure state exposed: presentation contract 缺页级 evidence 时显示本地 degraded 文案；enhanced report 失败时继续展示 canonical PPT facts，不再以 sales cards 伪装“正常”。

## Inputs

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 当前共享 report page，仍硬编码 sales 语义并无条件拉 knowledge-check。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 当前 focused tests 只锁 sales contract，需要补 presentation 分支与 degraded path。
- `web/src/lib/api/types.ts` — T02 产出的 `scenario_type` / `presentation_review` shared contract 类型。
- `web/src/lib/session-evidence.ts` — 现有 stage/evaluable formatter，可作为少量 presentation label helper 的共享位置。

## Expected Output

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 按 `scenario_type` 分支渲染的 shared report page，presentation 场景展示 canonical PPT postmortem 并跳过 sales-only requests/sections。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 锁住 presentation branch、degraded fallback、retry `presentation_id` 与 sales-only affordance 缺席的 focused regression proof。
- `web/src/lib/session-evidence.ts` — 如有需要，补充 presentation-aware label / degraded copy helper。
- `web/src/lib/api/types.ts` — 如果页面落地时还需要补全 `presentation_review` 前端类型细节，则在这里完成最终对齐。
