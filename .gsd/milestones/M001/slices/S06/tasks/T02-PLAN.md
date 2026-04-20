---
estimated_steps: 5
estimated_files: 4
skills_used:
  - safe-grow
  - test-driven-development
  - accessibility
  - baseline-ui
  - react-best-practices
  - verification-before-completion
---

# T02: 把 `/admin/users/[id]` 改成主管可读的连续变化视图

**Slice:** S06 — 连续变化视图（主管判断是否进步）
**Milestone:** M001

## Description

这个任务把 richer supervisor progress contract 真正翻译成主管可读的页面。当前 `web/src/app/admin/users/[id]/page.tsx` 只会显示 improvement 百分比和 generic score line chart，progress 失败时也只写 `console.error`。S06 要求的是：主管一眼能看出最近有没有进步、重复卡在哪类问题、重复下一轮目标是什么、是否其实只是“证据不足”，以及是否该切换训练重点。页面应继续保留当前壳和 completed-session canonical report drill-in，但 progress 区域必须换成真正可决策的摘要面，而不是另一张脱离 report 词汇表的图。

## Steps

1. 先扩展 `web/src/app/admin/users/[id]/page.test.tsx` 的 mock progress payload，写 failing assertions，锁住新的页面行为：显示 repeated blocker / repeated next goal / switch-focus recommendation / not-evaluable count，以及 progress 读取失败或无可评估数据时的本地 inline state。
2. 在 `web/src/lib/api/types.ts` 更新 `UserProgressResponse` 到 richer supervisor contract；如前端需要把 `issue_type` / `goal_type` 翻译成稳定文案，优先在 `web/src/lib/session-evidence.ts` 增加共享 formatter，而不是在 page 里硬编码第二套 vocabulary。
3. 更新 `web/src/app/admin/users/[id]/page.tsx` 的 data-loading 与 state 管理，让 progress 区域有独立的 success / empty / error state；不要再把 progress failure 隐藏在 `console.error` 里，也不要因为 `/progress` 失败就把整页误判成“用户不存在”。
4. 把现有“进步率 + generic 折线图”改成 supervisor-readable summary：趋势方向、重复 blocker、重复 next goal、not-evaluable 说明、是否切换重点与 recommendation；可以保留趋势图作为辅助手段，但它必须服务这个判断，而不是继续当唯一信息面。
5. 运行 focused web test；如果需要本地 runtime/UAT，再先执行 `cd backend && venv/bin/alembic upgrade head`。若浏览器或本地 API 报 `conversation_messages.transcript_metadata` 缺失，要把它归类为 migration/blocker，而不是误判成前端 regressions。

## Must-Haves

- [ ] 页面必须直接消费 richer `UserProgressResponse` 合同来显示 repeated blocker / repeated next goal / switch-focus recommendation，不能退回从 sessions table 本地推断趋势结论。
- [ ] progress 区域必须有本地 inline empty/error state，并明确区分“暂无可评估训练数据”和“progress 请求失败”；不能继续只靠 `console.error` 暗中失败。
- [ ] 现有 completed-session canonical `查看报告` drill-in、session preview 以及整体页面壳必须保留，S06 只改 continuous-change surface，不新造 supervisor-only report 页面。

## Verification

- `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'`
- Manual review — 在有真实数据的 `/admin/users/{id}` 页面确认 progress 区域能用与 session preview/report 一致的 vocabulary 回答“有没有进步 / 卡在哪 / 要不要换重点”，并且在无数据或请求失败时显示本地状态文案。

## Observability Impact

- Signals added/changed: page-level progress success/empty/error state、rendered not-evaluable count、repeated blocker/goal summary、switch-focus recommendation copy。
- How a future agent inspects this: 查看 `web/src/app/admin/users/[id]/page.test.tsx`、浏览器打开 `/admin/users/{id}`、或在 mock payload 下检查 progress 区域渲染。
- Failure state exposed: progress 请求失败的 inline 提示、无可评估 sessions 的 empty state、以及 migration 缺失导致的 admin evidence failure 与前端 regressions 的区分。

## Inputs

- `backend/src/admin/api/users.py` — T01 产出的 richer `/progress` / aligned `/stats` contract 来源；T02 必须按这条真实 API 线消费，不要自己推断。
- `backend/tests/integration/test_admin_users_api.py` — T01 会在这里锁住 progress/stats payload 形状，前端 mock 和断言应跟它保持一致。
- `web/src/lib/api/types.ts` — 当前 `UserProgressResponse` 只有 `trend_data` / `improvement_rate` / `total_data_points`，不足以承载 S06。
- `web/src/lib/session-evidence.ts` — 已有 not-evaluable / stage formatter，可作为 issue/goal label helper 的共享位置。
- `web/src/app/admin/users/[id]/page.tsx` — 当前 progress 区域还是 generic score trend，且失败只记 console。
- `web/src/app/admin/users/[id]/page.test.tsx` — 当前只锁 completed-session preview 与 `查看报告` CTA，需要扩到连续变化视图与 failure state。

## Expected Output

- `web/src/lib/api/types.ts` — richer supervisor progress contract 的前端类型定义。
- `web/src/lib/session-evidence.ts` — issue/goal / not-evaluable 相关的共享显示 helper（如有需要）。
- `web/src/app/admin/users/[id]/page.tsx` — supervisor-readable continuous-change summary + local progress empty/error state。
- `web/src/app/admin/users/[id]/page.test.tsx` — 锁住 repeated blocker / next goal / switch-focus / inline empty-error state 的 focused regression proof。
