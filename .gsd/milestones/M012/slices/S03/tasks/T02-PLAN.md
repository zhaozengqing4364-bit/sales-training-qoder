---
estimated_steps: 24
estimated_files: 6
skills_used:
  - safe-grow
  - react-best-practices
  - tanstack-query-best-practices
  - vitest
  - verification-before-completion
---

# T02: 建立单一语速偏好 seam 并把它真正接到训练音频播放链

Skills: safe-grow, react-best-practices, tanstack-query-best-practices, vitest, verification-before-completion

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

## Inputs

- `web/src/hooks/use-theme.ts`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-streaming-audio-player.ts`
- `web/src/hooks/use-streaming-audio-player.test.ts`
- `web/src/lib/api/client.ts`

## Expected Output

- `web/src/hooks/use-voice-speed-preference.ts`
- `web/src/hooks/use-voice-speed-preference.test.ts`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-streaming-audio-player.ts`
- `web/src/hooks/use-streaming-audio-player.test.ts`
- `web/src/app/(dashboard)/profile/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts" "src/hooks/use-streaming-audio-player.test.ts"

## Observability Impact

- Signals added/changed: `voice_speed_preference` 的归一化值可从 profile UI、`localStorage` 和 player focused tests 三处交叉确认。
- How a future agent inspects this: 运行 `use-voice-speed-preference.test.ts` 与 `use-streaming-audio-player.test.ts`，并在浏览器里检查 `localStorage["voice_speed_preference"]` 与 profile select 当前值。
- Failure state exposed: 默认值漂移、非法 storage 值未归一化、或任一播放路径仍停在 `1.0` 都会被 focused tests 直接定位。
