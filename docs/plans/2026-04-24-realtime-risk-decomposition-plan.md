# 2026-04-24 Realtime 高风险模块 contract-first 拆分计划

## Goal

降低 StepFun realtime、`main.py`、报告页和练习页等高风险模块的演进风险。拆分必须 contract-first：先锁定外部协议、payload snapshot 和关键交互，再按单一职责小步抽离。不得把本计划解释为一次性重写。

## Non-goals

- 不一次性重写 StepFun handler。
- 不改变 WebSocket 对外消息协议。
- 不改变报告、练习页面的用户可见流程。
- 不引入新依赖。
- 不启用自适应难度、外部分享或视觉重设计。

## Risk Map

| Surface | Current risk | Contract to freeze first | Allowed first extraction |
| --- | --- | --- | --- |
| StepFun realtime handler | 上游 WS、音频、tool call、KB lock、feedback、resume、persistence 混在核心路径 | incoming/outgoing WebSocket payload snapshots, upstream event fixtures, reconnect state contract | payload builder、tool-call adapter、TTS outbound adapter |
| `main.py` | app creation、router registration、lifespan、websocket routes 混合，启动副作用难审计 | app factory smoke, route registry snapshot, lifespan startup/shutdown tests | app factory、router registry、lifespan module、websocket route registration |
| Report page | 数据获取、证据解释、趋势/推荐、展示耦合 | report API fixture, legacy report compatibility snapshot, retry/recommendation interactions | data hook first, then display components |
| Practice page | WebSocket 状态、录音、快捷键、移动入口、状态标签耦合 | practice page interaction tests, status label snapshots, recording/hotkey regressions | data/runtime hook first, then visual components |

## StepFun Decomposition

### Contract inventory

Before any extraction, lock these outward behaviors:

- Incoming frontend messages: `audio_chunk`, `audio_end`, `text`, `control`, `user_speaking`, `interrupt`。
- Outgoing frontend messages: `asr_transcript`, `status`, `tts_audio`, `error`, `heartbeat`, realtime score/fuzzy/action-card payloads。
- Tool-call flow: `response.create`, tool result append, KB lock blocked, tool failure fallback。
- TTS chunk contract: v1/v2 fixture compatibility, playback metadata, chunk ordering。
- Reconnect/resume: persisted minimal runtime state and safe restoration behavior。

### Extraction order

1. **Payload builder**
   - Move pure construction of StepFun session/update/response payloads behind a helper.
   - Keep field names and defaults byte-for-byte equivalent where possible.
   - Tests: payload snapshot for session.update, response.create, error fallback.

2. **Tool-call adapter**
   - Isolate function-call argument parsing, tool result append, and failure envelope.
   - Keep KB lock and tool definitions unchanged.
   - Tests: tool result success, malformed args, KB lock blocked, tool exception fallback.

3. **TTS outbound adapter**
   - Isolate outbound audio chunk mapping and playback metadata.
   - Keep frontend `tts_audio` contract stable.
   - Tests: chunk v1/v2 fixtures, metadata fallback, unsupported rate not sent upstream.

4. **Only after the above pass**: consider state/reconnect adapter or feedback adapter extraction, one responsibility per slice.

## `main.py` Decomposition

1. Characterize current startup:
   - route list snapshot。
   - middleware list and CORS/auth envelope expectations。
   - lifespan startup/shutdown behavior。
2. Extract app factory without changing import path used by deployment。
3. Move router registration into a registry module with deterministic order。
4. Move websocket route registration only after WebSocket contract tests pass。

Acceptance:

- Health and auth smoke pass。
- Existing route paths remain registered。
- Startup side effects do not run during pure import tests unless explicitly invoked。

## Report / Practice Frontend Decomposition

### Report page

1. Extract data hook around existing API calls and derived evidence state。
2. Keep presentation components pure and fixture-backed。
3. Preserve legacy report compatibility: missing `ruleset_version` shows `legacy_unversioned` explanation instead of crashing。
4. Keep retry/recommendation interactions unchanged。

### Practice page

1. Extract runtime hook for WebSocket/session status if not already isolated。
2. Keep recording controls, hotkeys, status labels, mobile shortcuts covered by tests before moving UI blocks。
3. Do not alter `/test-mic` discoverability unless a separate UX task owns it。
4. Preserve pause/resume/end failure copy and reconnect behavior。

## Verification Matrix

| Slice | Required proof |
| --- | --- |
| StepFun payload builder | `backend/tests/unit/test_stepfun_payload_snapshots.py`, `backend/tests/unit/test_stepfun_event_payloads.py` |
| StepFun tool-call adapter | `backend/tests/unit/test_stepfun_function_call_helpers.py`, `backend/tests/unit/test_stepfun_tool_helpers.py` |
| TTS outbound adapter | `backend/tests/integration/test_sales_websocket_tts.py`, focused TTS unit tests |
| WebSocket status/reconnect | `backend/tests/integration/test_websocket_status_contract.py`, `backend/tests/integration/test_sales_realtime_reconnect_flow.py` |
| Frontend WebSocket projection | `pnpm --dir web exec vitest run 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/use-practice-websocket.presentation-flow.test.ts' 'src/hooks/websocket/message-handlers.test.ts' --reporter=dot` |
| Report page hook | report page tests plus legacy report fixture |
| Practice page hook | practice page, lifecycle, hotkey, recording tests |
| `main.py` factory | backend route/app startup smoke and ruff |

## Rollback and Safety Rules

- Every extraction must keep one old import compatibility seam until all call sites are migrated.
- No slice may combine protocol changes with file movement.
- If snapshot output changes, treat it as a product/API change and stop for review.
- If tests reveal existing contract drift, document it before changing production behavior.
- Commit each responsibility extraction separately with focused verification evidence.
