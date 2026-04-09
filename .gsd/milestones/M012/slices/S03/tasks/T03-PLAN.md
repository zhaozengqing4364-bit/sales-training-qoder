---
estimated_steps: 24
estimated_files: 2
skills_used:
  - safe-grow
  - react-best-practices
  - vitest
  - verification-before-completion
---

# T03: 把 learner 排行榜评分说明收口到当前 evaluable-session 语义

Skills: safe-grow, react-best-practices, vitest, verification-before-completion

排行榜现在已经有“说明”占位，但仍停留在旧 learner weighted-score 语义；而 admin analytics 已经把“只纳入可评估训练、证据不足单独记账”作为当前权威口径。这个任务不做 backend 契约或排序逻辑变更，只把 learner 排行榜的 header/footer 说明收口到真实语义，让新人知道为什么自己会/不会上榜以及均分是怎么算的。保留现有的周期/场景筛选、`myRank` fallback 与空态行为，不要把 S03 扩张成 analytics backend slice。

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `api.dashboard.getPublicLeaderboard()` | 保持现有空态/加载态，不因为 copy 调整引入新异常。 | 继续显示 loading -> empty/fallback 行为。 | 缺失 `entries` / `my_rank` 时使用既有 fallback fetch 与默认空态。 |
| `api.dashboard.getMyRank()` fallback | 若失败则隐藏我的排名卡片，不能影响主榜单 copy。 | 同 error：保留榜单主体与说明文案。 | 对缺失 rank / totals 的响应保持现有 defensive fallback。 |

## Load Profile

- **Shared resources**: 现有 leaderboard 两次 API fetch（主榜单 + 可选 my-rank fallback）；不新增请求种类。
- **Per-operation cost**: 仅文案与测试断言变化；运行时成本基本不变。
- **10x breakpoint**: 首先受限于现有 leaderboard API，而不是这次 copy 收口。

## Negative Tests

- **Malformed inputs**: 空榜单、缺失 `my_rank`、缺失 `entries` 时仍显示 learner-safe 说明和空态。
- **Error paths**: 主榜单或 my-rank fallback 失败时不回退到旧 weighted-score 语义，也不抛出白屏。
- **Boundary conditions**: 周榜/月榜/总榜与不同场景筛选切换后，说明文案仍保持 evaluable-session 语义。

## Steps

1. 以 `web/src/app/admin/analytics/page.tsx` 的权威 copy 为参考，更新 learner leaderboard 页头/页尾说明，明确只纳入可评估已完成训练，证据不足会话不混入均分。
2. 保持当前筛选、加载、空态与 `myRank` fallback 行为不变，不修改 backend 排序/字段契约。
3. 新增 focused Vitest 覆盖正常榜单、空榜单和 fallback `myRank` 场景下的说明文案与现有交互状态。

## Must-Haves

- [ ] learner leaderboard 明确说明均分/排行只纳入可评估已完成训练。
- [ ] 证据不足/未评估会话不会再被文案描述成旧 weighted-score 统计。
- [ ] 现有 time-period / scenario filters 与 `myRank` fallback 继续工作。
- [ ] 不新增 backend leaderboard 变更。

## Inputs

- `web/src/app/(dashboard)/leaderboard/page.tsx`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/lib/api/client.ts`

## Expected Output

- `web/src/app/(dashboard)/leaderboard/page.tsx`
- `web/src/app/(dashboard)/leaderboard/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/leaderboard/page.test.tsx"

## Observability Impact

- Signals added/changed: learner leaderboard 直接暴露当前 score-basis 文案，避免用户在 UI 上读到与 admin analytics 相冲突的语义。
- How a future agent inspects this: 运行 `leaderboard/page.test.tsx` 并查看页头/页尾 copy 是否仍保持 evaluable-session 说明。
- Failure state exposed: 一旦 copy 回退到旧 weighted-score 语义、或空态/fallback 场景丢失说明，focused tests 会直接失败。
