---
id: T03
parent: S01
milestone: M001
provides:
  - Practice page lifecycle state that follows server events only, with visible end-failure retry/reconnect handling and report navigation gated by confirmed terminal status
key_files:
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/websocket/message-handlers.ts
  - web/package.json
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/hooks/websocket/message-handlers.test.ts
key_decisions:
  - D011: Practice-page lifecycle state and report navigation now trust only server lifecycle events; local code only clears transient audio/runtime state
patterns_established:
  - REST end requests leave the page in an explicit pending/error state, while a separate effect routes to `/practice/{sessionId}/report` only after websocket/session props confirm terminal status
  - Websocket `sendControl()` no longer optimistically mutates `sessionStatus` / `aiState`; server `status` / `reconnected` / `session_ended` events reconcile both visible lifecycle state and transient audio flags
observability_surfaces:
  - training-page error banner now shows end-session failures with `重试结束` and existing reconnect affordance instead of masking failures behind report navigation
  - browser-verifiable end failure surface on `/practice/{sessionId}` and terminal-only report redirect
  - targeted vitest coverage for end failure, server-confirmed redirect timing, paused audio gate, and reconnected state restoration
  - slice verification commands for backend lifecycle, backend reconnect contract, and frontend lifecycle tests
duration: 1h35m
verification_result: passed
completed_at: 2026-03-23T02:35:20+08:00
blocker_discovered: false
---

# T03: 让训练页只信服务端生命周期并显式暴露结束失败

**Removed the practice page’s optimistic lifecycle guesses so end failures stay visible on the training page, retry/reconnect is explicit, and report navigation happens only after the server confirms a terminal session state.**

## What Happened

这轮把前端训练页的生命周期状态面收口到服务端事件上，而不是继续让本地状态猜 pause / resume / end 结果。

实现分成四块：

1. `use-practice-session-lifecycle.ts`
   - 去掉 `handleEndSession()` 里无条件 `finally -> router.push()` 的行为。
   - 结束请求现在只负责：清空旧错误、停止本地录音、调用 `api.practice.endSession(sessionId)`。
   - 如果 end 失败，hook 会把 API 友好错误消息放进 `lifecycleError`，并把 `isEndingSession` 复位，用户继续留在训练页。
   - 新增基于 `sessionStatus` 的 effect：只有当 props 已经进入 `completed` / `scoring` 终态时，才真正跳转到 `/practice/{sessionId}/report`。

2. `page.tsx`
   - 训练页错误提示面现在合并 `lifecycleError` / websocket / 音频 / session meta 错误。
   - 当 end 失败时，会在原有红色错误提示面上直接出现 `重试结束`；连接失败时继续复用 `重新连接`。
   - 结束按钮在终态或结束进行中会禁用，避免重复点击。

3. `use-practice-websocket.ts`
   - `sendControl()` 不再乐观地把 `sessionStatus` 改成 `paused` / `in_progress`，也不再乐观改 `aiState`。
   - 本地仍保留真正属于客户端职责的音频清理：中断播放、清空队列、清理 interim transcript 与 backpressure 标记。
   - 这样录音/发送门禁改为真正跟随服务端 `status` / `reconnected` / `session_ended` 结果，而不是跟随点击时机。

4. `message-handlers.ts`
   - `status` 在收到非 `in_progress` 的服务端状态时，会同步清掉本地瞬时音频状态（播放中、streaming、interim transcript、backpressure、network slow）。
   - `reconnected` 和 `session_ended` 也会显式重置这些临时 runtime 标记，避免 UI 在恢复后继续显示旧的“AI 正在说话 / 网络慢 / transcript 残留”。

另外补了一处执行性修正：`web/package.json` 的 `test` script 从 `vitest --run` 改为 `vitest run`，这样 slice 计划里写死的 `npm test -- --run ...` 命令终于能原样跑通，不再因为重复 `--run` 在进入测试前就失败。

## Verification

Passed:
- `cd web && npx vitest --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - 30 tests passed
  - 明确断言：
    - end 失败时不会跳报告页，`lifecycleError` 可见
    - end 成功后不会立刻跳转，必须等 `sessionStatus` 进入终态
    - `sendControl('pause')` 后音频发送门禁仍等待后端 `status=paused`
    - `reconnected` 会恢复 `sessionStatus` / `aiState` 并清理本地瞬时音频状态
- `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`
  - 18 selected tests passed
- `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
  - 13 tests passed
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - 3 files / 30 tests passed

Browser verification (local real app):
- Logged in through local dev-login and opened a real sales practice session in legacy voice mode.
- Injected a real end failure by stopping the backend, then clicked `结束练习`:
  - page stayed on `/practice/{sessionId}`
  - error surface exposed `重试结束`
  - existing reconnect recovery copy remained visible instead of redirecting to `/report`
- Started a fresh legacy session, cleared the start overlay, clicked `结束练习`, and verified the page stayed on `/practice/...` briefly before routing to `/report` once the server completed the terminal transition.

## Diagnostics

- Frontend regression tests:
  - `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
  - `web/src/hooks/use-practice-websocket.test.ts`
  - `web/src/hooks/websocket/message-handlers.test.ts`
- Runtime UI surfaces:
  - training-page red error banner with `重试结束` and `重新连接`
  - header lifecycle labels (`准备中` / `进行中` / `已暂停` / `评分中` / `已完成`)
  - report redirect now keyed to confirmed terminal status only
- Browser verification path used in this task:
  - `/agents/{agentId}` → select legacy mode → `开始对练`
  - kill backend → click `结束练习` → confirm still on `/practice/{sessionId}` with retry UI
  - restore backend → fresh legacy session → click `结束练习` → confirm `/report`

## Deviations

- Updated `web/package.json` test script from `vitest --run` to `vitest run` so the slice-plan verification command (`npm test -- --run ...`) is executable as written.

## Known Issues

- Local StepFun realtime browser sessions on this machine still hit repeated websocket `1006` closes after connection; browser verification of the successful end-path therefore used legacy mode, while realtime reconnect/state recovery remains covered by the targeted vitest suite.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` — removed unconditional report navigation, added end-failure state, and gated report routing on confirmed terminal session status.
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — surfaced lifecycle errors in the existing training-page error banner and added explicit retry-end handling.
- `web/src/hooks/use-practice-websocket.ts` — removed optimistic lifecycle state writes from `sendControl()` and kept only local audio/runtime cleanup.
- `web/src/hooks/websocket/message-handlers.ts` — made server `status` / `reconnected` / `session_ended` events reconcile transient audio/runtime flags along with lifecycle state.
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts` — covers end failure staying on-page and terminal-only report navigation.
- `web/src/hooks/use-practice-websocket.test.ts` — covers pause audio gating and reconnect recovery only after backend state changes.
- `web/src/hooks/websocket/message-handlers.test.ts` — covers paused-status cleanup and reconnected runtime restoration.
- `web/package.json` — normalized the Vitest script so the slice verification command works as written.
- `.gsd/DECISIONS.md` — recorded D011 for server-authoritative frontend lifecycle state.
- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — marked T03 done.
