# S03: 个人中心与排行榜体验收敛

**Goal:** 在不扩张 backend 用户设置或排行榜契约的前提下，把 learner 侧个人中心与排行榜收口成真实可达、语义可信、行为闭环的体验：用户能从共享壳层进入 `/profile`，在个人中心里管理真实会影响训练体验的语速偏好，清楚知道如何修改密码，并看懂排行榜分数是按什么口径计算的。
**Demo:** After this: Profile 语速设置持久化，通知开关移除，排行榜有评分说明，个人中心可修改密码

## Tasks
- [x] **T01: 让 learner 壳层个人中心入口和密码动作都落到真实路由** — Skills: safe-grow, react-best-practices, vitest, verification-before-completion

把 `/profile` 的可达性收口在现有 learner shell authority seam，而不是额外发明新导航。`web/src/components/layout/sidebar.tsx` 里的用户弹窗目前把“编辑资料”渲染成了无动作按钮；这个任务要把它变成真实的 `/profile` 导航，同时保持 `历史记录` 继续留在 `SidebarContent` 里，不回归 S02 已关闭的问题。`web/src/app/(dashboard)/profile/page.tsx` 里的密码动作则要保持复用 S01 的 forgot/reset 流程：用 truthful copy（例如“通过邮箱重置密码”）和 Next 路由跳转替换 `window.location.href`，但不要新增 authenticated password API。

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `next/link` / `next/navigation` routing | 保持按钮退化成明确可见的 link/button affordance，不能回到静默 dead button。 | 同 error：优先保留明确目标路由。 | 仅导航到受控的 `/profile` 与 `/forgot-password`，绝不拼接不可信 query。 |
| `api.user.getMe()` / 现有 profile 加载流 | 保持当前 loading/error fallback，不因路由改造新增白屏。 | 维持现有 skeleton / 错误文案。 | 缺失用户字段时继续回退到既有 display-name / email fallback。 |

## Load Profile

- **Shared resources**: learner shell render tree 与现有 profile 数据请求；不新增 backend/shared infra。
- **Per-operation cost**: 一次本地路由跳转 + 既有 profile 页面加载，成本与当前页面一致。
- **10x breakpoint**: 首先暴露的问题会是 dead CTA 或错误目标路由，而不是资源耗尽。

## Negative Tests

- **Malformed inputs**: 缺失 `currentUser`、缺失 display name / email 时，sidebar 用户入口与 profile 页面仍保持可达与安全 fallback。
- **Error paths**: profile 页面数据加载失败时仍显示现有错误态，不因为密码 CTA 改造而阻塞页面。
- **Boundary conditions**: expanded / collapsed learner user affordance 都能到 `/profile`；密码 CTA 始终指向 `/forgot-password` 而不是浏览器硬跳转字符串拼接。

## Steps

1. 把 `sidebar.tsx` 里的用户弹窗“编辑资料”改成真实 `/profile` 导航，并补齐 focused tests，确认 `历史记录` 入口仍在共享 nav seam。
2. 在 `profile/page.tsx` 内把密码动作改成 truthful copy + Next 路由导航到 `/forgot-password`，避免 `window.location.href`。
3. 新增/扩展 profile focused Vitest，锁定 learner shell `/profile` 入口与密码 CTA 的真实 route handoff。

## Must-Haves

- [ ] learner shell 用户弹窗不再存在无动作的“编辑资料”按钮。
- [ ] `SidebarContent` 中的 `历史记录` 入口保持不变。
- [ ] profile 页密码 CTA 明确说明通过既有 forgot/reset 流程修改密码。
- [ ] focused tests 直接断言 `/profile` 与 `/forgot-password` 的目标路由。

  - Estimate: 1.25h
  - Files: web/src/components/layout/sidebar.tsx, web/src/components/layout/sidebar.test.tsx, web/src/app/(dashboard)/profile/page.tsx, web/src/app/(dashboard)/profile/page.test.tsx
  - Verify: npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/app/(dashboard)/profile/page.test.tsx"
- [x] **T02: Added a shared voice-speed preference hook, removed fake profile persistence, and wired the same normalized rate through MediaSource, fallback Audio, and PCM playback.** — Skills: safe-grow, react-best-practices, tanstack-query-best-practices, vitest, verification-before-completion

把“语音播放速度”从 profile 页里的页面内小把戏收口成一个真正影响训练体验的前端 seam。当前实现同时存在三个问题：render 期间直接读 `localStorage`、尝试发一个实际上不会落盘的 `voice_speed_preference` PATCH、以及训练音频播放链根本不消费这个值。这个任务应以 `web/src/hooks/use-theme.ts` 为参考，新增一个 SSR-safe 的 `useVoiceSpeedPreference` hook，限定支持值枚举并负责本地持久化；profile 页面只通过这个 hook 读写状态，不再伪装 backend persistence。随后把该偏好接到 `usePracticeWebSocket` / `useStreamingAudioPlayer` 所覆盖的三条播放路径：MediaSource `HTMLAudioElement`、fallback `new Audio(audioUrl)`、以及 PCM Web Audio `AudioBufferSourceNode`。

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Browser `localStorage` | 回退到默认 `1.0x`，UI 仍可操作；不能崩溃或无限重渲染。 | 视为读取失败并使用默认值。 | 非法值必须被归一化到受支持枚举，而不是直接喂给播放链。 |
| `HTMLAudioElement` / MediaSource / Web Audio | 在不支持或 autoplay 被拦截时保留现有播放错误/缓冲行为，只修正 `playbackRate` 应用。 | 不新增额外重试循环；保留当前 stop/reset 逻辑。 | 只对受支持 rate 赋值；PCM / fallback / MediaSource 任一路径缺字段时回退到 `1.0`。 |

## Load Profile

- **Shared resources**: browser `localStorage`、当前 audio element、MediaSource、`AudioContext` / `AudioBufferSourceNode`。
- **Per-operation cost**: 一次本地 storage 读写 + 每条播放路径一次 `playbackRate` 赋值；无新网络请求。
- **10x breakpoint**: 高频开练/中断时首先暴露的是播放链资源清理或默认值漂移，而不是业务 API 压力。

## Negative Tests

- **Malformed inputs**: `localStorage` 缺失、空字符串、非法数字、超出枚举范围时统一回退到默认值。
- **Error paths**: autoplay blocked、fallback audio、PCM chunk 流、MediaSource 不支持场景都不会因为新增语速逻辑而失效。
- **Boundary conditions**: `0.75x`、`1.0x`、`1.25x`、`1.5x` 四个受支持值都能被 profile UI 选中并应用到播放链。

## Steps

1. 新增 `use-voice-speed-preference.ts`（必要时连同 focused test），实现 SSR-safe 默认值、枚举归一化和 `localStorage` 持久化。
2. 重构 `profile/page.tsx` 的语速设置，只通过新 hook 读写状态；移除 inline `localStorage` IIFE 和伪造的 `voice_speed_preference` PATCH，同时确保通知 toggle 不会被重新引入。
3. 给 `use-streaming-audio-player.ts`（必要时经 `use-practice-websocket.ts` 传参）补齐 playbackRate wiring，并新增 focused Vitest 覆盖 hook 归一化和三条播放路径的 rate 应用。

## Must-Haves

- [ ] 语速偏好只有一个前端 authority seam，并限制在受支持枚举值内。
- [ ] profile 页不再 render-time 读取 `localStorage`，也不再调用假的 `voice_speed_preference` PATCH。
- [ ] MediaSource、fallback `Audio`、PCM Web Audio 三条播放路径都应用同一个 rate。
- [ ] profile 设置区不会重新出现通知开关。

  - Estimate: 2h
  - Files: web/src/hooks/use-voice-speed-preference.ts, web/src/hooks/use-voice-speed-preference.test.ts, web/src/app/(dashboard)/profile/page.tsx, web/src/hooks/use-practice-websocket.ts, web/src/hooks/use-streaming-audio-player.ts, web/src/hooks/use-streaming-audio-player.test.ts
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts" "src/hooks/use-streaming-audio-player.test.ts"
- [x] **T03: Updated learner leaderboard copy and regression tests so ranking and averages are clearly limited to evaluable completed sessions.** — Skills: safe-grow, react-best-practices, vitest, verification-before-completion

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

  - Estimate: 1h
  - Files: web/src/app/(dashboard)/leaderboard/page.tsx, web/src/app/(dashboard)/leaderboard/page.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/leaderboard/page.test.tsx"
