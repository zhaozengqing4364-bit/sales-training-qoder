# S03 Research — 个人中心与排行榜体验收敛

## Summary
- 当前 compact requirements 里没有新的 active RXXX 明确挂到 S03；这更像是 M012 首练闭环里的 roadmap UX 收口 slice，而不是新的后端 capability slice。规划时应优先围绕现有 learner shell 和 S01/S02 已落地 seams 收口，不要平白扩张成“用户设置系统”。
- 相关路由已经存在：`web/src/app/(dashboard)/profile/page.tsx` 和 `web/src/app/(dashboard)/leaderboard/page.tsx`。S03 不是从零搭页面，而是要把已有页面变成“真实可达、语义可信、行为闭环”。
- `通知开关移除` 在 learner web surface 上其实已经基本成立：当前 profile page 没有通知 toggle；只有 `backend/src/common/api/users.py` 还返回一个硬编码 `settings.notifications_enabled` stub，但前端完全没有消费它。不要为了“完成 roadmap 文案”硬造一个删除任务。
- `排行榜有评分说明` 也并非完全缺失：`leaderboard/page.tsx` 已有标题副文案 + 底部说明。但它仍停留在旧 learner leaderboard 语义上，而 admin analytics 已经切到 projection / evaluable-only 口径，所以这里更像“说明收敛/修正”而不是从无到有。
- 现在最真实的缺口有三个：
  1. `/profile` 没有 learner shell 内的真实入口，sidebar 用户弹窗里的“编辑资料”按钮是 dead button。
  2. 语速设置只是 profile 页里的半成品：用 `localStorage` 临时写值、没有 React authority state、尝试调用的 API 实际不会持久化这个字段，而且训练音频播放链根本不读取该偏好。
  3. 个人中心“修改密码”只是 `window.location.href = "/forgot-password"` 的跳转，虽然复用了 S01 已有 forgot/reset flow，但在个人中心里缺少明确、可信的 account-action 语义。

## Skills Discovered
No new installs needed. Relevant already-installed skills:
- `react-best-practices`
- `tanstack-query-best-practices`
- `fastapi-python`

These skills materially informed the recommendation:
- `react-best-practices`: prefer one local-storage authority seam over ad-hoc reads in JSX (`client-localstorage-schema`, derived state instead of effect-free drift).
- `tanstack-query-best-practices`: if profile updates still mutate current-user identity, keep `currentUserQueryKey` synchronized via targeted cache update/invalidation rather than hoping a full reload fixes learner chrome drift.
- `fastapi-python`: if backend profile contract expands, do it through typed Pydantic request/response models (`UserMeUpdateRequest`, `UserMeResponse`) rather than raw dict sprawl.

## Recommendation
Treat S03 as **frontend-first** unless the planner explicitly decides that “持久化” must mean account-level cross-device storage or that learner leaderboard must fully converge to admin projection semantics.

Recommended path:
1. **Close profile discoverability first** through the existing learner shell seam in `web/src/components/layout/sidebar.tsx`. This removes the dead “编辑资料” affordance and makes `/profile` reachable without inventing a new nav system.
2. **Create one frontend authority seam for voice speed preference** — ideally a small hook/util modeled after `web/src/hooks/use-theme.ts` — then read/write that seam from both the profile page and the streaming audio player. This is the smallest change that makes the setting real.
3. **Reuse S01’s forgot/reset flow for password change** instead of inventing a second authenticated password API. The UX can still improve by making the profile CTA explicit/truthful (“通过邮箱重置密码” or similar), but backend scope does not have to grow.
4. **Tighten leaderboard explanation copy** to match whichever semantics the slice keeps. If the team wants only roadmap closure, this can stay frontend-only. If the team wants learner/admin score-language convergence, that becomes a separate backend contract task.

Why this recommendation fits the repo rules:
- Preserves the stack.
- Minimizes direct change.
- Avoids batching a new user-settings backend into a slice whose roadmap promise is primarily learner UX convergence.
- Uses established seams from S02 instead of inventing page-local patches.

## Implementation Landscape
- `web/src/app/(dashboard)/profile/page.tsx`
  - Existing client page that loads three data sources with `Promise.allSettled`: `api.user.getMe()`, `api.dashboard.getHistoryStatistics()`, and `api.sessions.getStats()`.
  - Owns editable `display_name/email/department` state and manually updates `currentUserQueryKey` after save so learner chrome updates immediately.
  - Current speech-speed control problems:
    - `select` value reads `localStorage` inline during render instead of from React state.
    - `onChange` writes `localStorage` and then calls `api.user.updateProfile({ voice_speed_preference })` inside a sync `try/catch` without `await`.
    - No other web code reads `voice_speed_preference`, so the “setting” does not affect practice playback.
  - Current password CTA is imperative `window.location.href = "/forgot-password"`, so it works only as a blunt redirect and bypasses normal Next navigation semantics.

- `web/src/components/layout/sidebar.tsx`
  - Remains the learner shell authority seam from S02.
  - `/profile` is **not** in `navItems`.
  - `UserProfileModal` ends with a plain `编辑资料` `<Button>` that has no `href`, no router push, and no click handler. This is the cleanest discoverability seam to fix because it already exists in both expanded and collapsed user-entry flows.
  - If S03 wants profile access everywhere the learner sees their account avatar, this is the right file.

- `web/src/hooks/use-streaming-audio-player.ts`
  - Sole learner TTS playback seam.
  - Has three playback branches that matter for speech-rate work:
    1. MediaSource + `HTMLAudioElement`
    2. fallback buffered `new Audio(audioUrl)`
    3. PCM16/Web Audio via `AudioContext.createBufferSource()`
  - Any user-level playback-speed preference that should actually change the learner experience must be wired here, not only on the profile page.
  - Concretely, HTMLAudio paths need `audio.playbackRate`; PCM path needs `source.playbackRate.value` before `source.start(...)`.

- `web/src/hooks/use-practice-websocket.ts`
  - Instantiates `useStreamingAudioPlayer(...)` and is the natural injection seam if the player receives a `playbackRate` option or reads a shared preference hook.

- `web/src/hooks/use-theme.ts`
  - Existing example of an SSR-safe, localStorage-backed preference hook. Best in-repo pattern reference for a new `useVoiceSpeedPreference`-style seam.

- `web/src/lib/api/client.ts`
  - `api.user.updateProfile()` only serializes `name`, `department`, and `email`; it silently drops `voice_speed_preference`.
  - `api.dashboard.getPublicLeaderboard()` + `getMyRank()` are the learner leaderboard client seams.

- `backend/src/common/api/users.py`
  - `/users/me` returns a hardcoded `settings` object (`notifications_enabled`, `language`, `theme`) but PATCH only accepts `name`, `department`, `email`.
  - There is no backend place to store voice speed today.
  - If the planner chooses account-level persistence, this is a real API/schema expansion task, not a tiny frontend follow-up.

- `backend/src/common/db/models.py`
  - `User` currently has `name`, `department`, `email`, `hashed_password`, role/login fields — no settings JSON / preference columns.

- `backend/src/common/analytics/leaderboard_service.py`
  - Learner leaderboard backend still uses legacy weighted SQL (`logic*0.4 + accuracy*0.3 + completeness*0.3`) and sorts by average score only.
  - This explains why learner leaderboard copy still sounds older than admin analytics.

- `backend/src/common/analytics/admin_analytics_service.py`
  - Admin leaderboard already uses projection-backed semantics with `evaluable_sessions`, `not_evaluable_sessions`, `score_basis`, `primary_issue_type`, and `primary_next_goal_type`.
  - If S03 wants semantic convergence instead of mere copy cleanup, this is the richer reference seam — but it is admin-only today.

- `web/src/app/admin/analytics/page.tsx`
  - Already contains the current authoritative copy for projection/evaluable-only score semantics:
    - “综合分只纳入可评估训练…”
    - “不再沿用旧的加权 SQL 语义。”
  - This is the right copy source if learner leaderboard wording should converge.

## Natural Task Split
1. **Profile entry + dead-CTA closure**
   - Likely files: `web/src/components/layout/sidebar.tsx`, `web/src/components/layout/sidebar.test.tsx`
   - Goal: make `/profile` actually reachable from learner shell and retire the dead `编辑资料` affordance.

2. **Voice-speed authority seam**
   - Likely files: new `web/src/hooks/use-voice-speed-preference.ts` (recommended), `web/src/app/(dashboard)/profile/page.tsx`, `web/src/hooks/use-streaming-audio-player.ts`, maybe `web/src/hooks/use-practice-websocket.ts`
   - Goal: one SSR-safe local preference source of truth, no ad-hoc render-time `localStorage` reads, actual playback impact.

3. **Password-change UX closure**
   - Likely files: `web/src/app/(dashboard)/profile/page.tsx` and maybe `web/src/components/layout/sidebar.tsx`
   - Goal: keep reusing the S01 forgot/reset flow, but present it as a truthful personal-center action instead of a contextless redirect.

4. **Leaderboard explanation convergence**
   - Frontend-only version: `web/src/app/(dashboard)/leaderboard/page.tsx` + new page test.
   - Bigger backend+frontend version: `backend/src/common/api/analytics.py`, `backend/src/common/analytics/leaderboard_service.py`, client typing/tests, then learner copy.

## Risks / Unknowns
- `通知开关移除` is already effectively true on the learner surface. The only remaining drift is backend stub data. Do not invent contract work unless the planner explicitly wants API cleanup.
- `排行榜有评分说明` is also partially done already. The real decision is whether S03 wants:
  - **Option A:** better/truthful learner copy only, or
  - **Option B:** actual learner/admin leaderboard semantic convergence.
  Option B is meaningfully bigger because it changes backend ordering and contract expectations.
- “语速设置持久化” is ambiguous:
  - If it means **same-browser persistence + actual playback effect**, frontend-only is enough.
  - If it means **user/account-level cross-device persistence**, backend schema + API work is required.
- Audio-speed support is not one-line because the player has multiple playback branches. Fixing only one branch will create browser/format inconsistencies.
- If profile save behavior changes, keep `currentUserQueryKey` in sync; otherwise sidebar/dashboard learner identity chrome will drift until a full reload.

## Verification
Minimum web proof bundle:
- `npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/app/(dashboard)/leaderboard/page.test.tsx" "src/components/layout/sidebar.test.tsx"`

If the slice changes actual playback behavior:
- add focused coverage for the preference seam and/or `use-streaming-audio-player.ts` playback-rate application.

If the slice expands `/users/me` or learner leaderboard backend contracts:
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_api_users.py backend/tests/unit/common/test_leaderboard_service.py backend/tests/contract/test_analytics.py -x -q`
- Run backend gates serially; project knowledge warns repo-root pytest-cov commands can race on the shared `.coverage` file.

Current diagnostics baseline checked and clean on:
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(dashboard)/leaderboard/page.tsx`
- `web/src/components/layout/sidebar.tsx`
- `web/src/hooks/use-streaming-audio-player.ts`
- `web/src/hooks/use-practice-websocket.ts`
- `backend/src/common/api/users.py`
- `backend/src/common/analytics/leaderboard_service.py`
