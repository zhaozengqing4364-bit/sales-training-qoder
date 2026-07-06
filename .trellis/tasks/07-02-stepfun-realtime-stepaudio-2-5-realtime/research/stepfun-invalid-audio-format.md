# Research: StepFun invalid audio protocol and audio format

- Query: 基于用户提供的 StepAudio 2.5 官方资料，定位 `[STEPFUN_API_ERROR] invalid audio, check your audio format` 的最可能协议/音频格式根因，并判断应改真实 provider E2E 测试音频还是服务端转码/声明。
- Scope: mixed
- Date: 2026-07-02

## Findings

### Files found

- `/Users/zhaozengqing/.codex/attachments/0809b48d-d4c7-401a-b413-14a44680ebaf/pasted-text.txt` — 用户提供的官方资料清单；重点指向 StepAudio 2.5 Realtime 模型页、Realtime API、Realtime 开发指南。
- `.trellis/workflow.md` — Trellis 要求研究结论落盘到任务目录，不能只留在聊天里。
- `.trellis/spec/backend/realtime-roleplay-v1.md` — 约束销售 realtime runtime 应走 `sales_bot` 平台直练，不启用 `sales_trainer` 自建 realtime runtime。
- `.trellis/spec/backend/error-handling.md` — WebSocket 错误应显式分类并对客户端安全呈现。
- `.trellis/spec/backend/quality-guidelines.md` — 单元测试不得打真实 StepFun/LLM/TTS，真实 provider 只适合受控 smoke/e2e。
- `backend/AGENTS.md` — 后端域路由，`sales_bot`、`training_runtime`、`sales_trainer` 分属不同边界。
- `backend/src/sales_bot/AGENTS.md` — StepFun realtime 集成位于 `sales_bot/websocket/stepfun_realtime_handler.py`，二进制音频帧协议需保持兼容。
- `backend/src/sales_trainer/AGENTS.md` — `sales_trainer` 是新人训练 REST/异步学习域，不是 realtime runtime；实时逻辑归 `sales_bot`/`training_runtime`。
- `web/AGENTS.md` — 新人训练路径与实时对练是两条轨道；`/sales-trainer/*` 启动后进入 `/practice/{sessionId}` 的 sales realtime runtime。
- `backend/src/training_runtime/stepfun_transport.py` — StepFun session 配置与 upstream JSON 发送深模块；session.update payload 写入 `input_audio_format`/`output_audio_format`。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun handler 默认模型/音频格式、连接 upstream、构造并发送 `session.update`。
- `backend/src/sales_bot/websocket/stepfun_realtime_policy.py` — 前端 JSON 音频和二进制 PCM 帧转换为 `input_audio_buffer.append`，`audio_end` 触发 commit/response。
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py` — `input_audio_buffer.commit`、`response.create`、upstream error 到 `[STEPFUN_API_ERROR]` 的映射。
- `web/src/hooks/use-audio-recorder.ts` — 真实浏览器录音路径默认重采样为 24000Hz，单声道，Float32 转 PCM16。
- `web/src/hooks/use-practice-websocket.ts` — realtime 前端首选发送 Int16Array 的二进制帧；JSON Base64 是 legacy/backpressure 路径。
- `web/tests/e2e/newcomer-training-closed-loop.spec.ts` — 新人训练 real provider E2E 直接发送 `audio: "AAAA"` 后 `audio_end`。
- `scripts/critical-quality-gate.sh` — real provider gate 通过 `PHASE4_E2E_PROVIDER`/`NEWCOMER_E2E_EXPECT_REAL_PROVIDER` 跑上述 Playwright 用例。

### External references

- StepAudio 2.5 Realtime 模型页：`https://platform.stepfun.com/docs/zh/guides/models/stepaudio-2.5-realtime`
  - 官方说明模型类型是端到端实时语音，语音输入/语音输出，协议为 WebSocket；快速示例在 `session.update` 中显式设置 `input_audio_format: "pcm16"`、`output_audio_format: "pcm16"`，连接后先 `session.update`，再持续 `input_audio_buffer.append`，ServerVAD 结束后返回 `response.audio.delta`。
- Realtime 双向实时语音 API：`https://platform.stepfun.com/docs/zh/api-reference/realtime/chat`
  - 请求地址为 `wss://api.stepfun.com/v1/realtime`，`model` 当前支持 `stepaudio-2.5-realtime` 等模型；`input_audio_format` 当前仅支持 `pcm16`，`output_audio_format` 当前仅支持 `pcm16`。
  - `input_audio_buffer.append` 的 payload 字段名是 `audio`，内容是 Base64 编码音频字节，必须采用会话 `input_audio_format` 指定的格式。
  - `input_audio_buffer.commit` 会提交音频缓冲并创建用户消息项，空缓冲会产生错误；`response.create` 触发模型推理。
  - `session.created`/`session.updated` 示例返回的默认 session 中 `input_audio_format` 和 `output_audio_format` 均为 `pcm16`。
- Realtime 开发指南：`https://platform.stepfun.com/docs/zh/guides/developer/realtime`
  - 生命周期表给出的顺序是：`session.update` 初始化；音频输入用 `input_audio_buffer.append` 分块；禁用 VAD 时手动 `input_audio_buffer.commit`、`response.create`；服务端输出包含 `input_audio_buffer.committed`、`response.created`、`response.audio.delta`、`response.audio_transcript.delta/done`、`response.done`。
  - 开发指南明确 `append` 每个 Base64 音频块最大 15 MB；音频格式可由 `session.update.session.input_audio_format` 或 `response.create.response.input_audio_format` 指定。
  - 官方示例把 `Float32Array` 写成 16-bit PCM，`DataView.setInt16(..., true)` 表示 little-endian，然后 Base64 后发送到 `audio` 字段；示例取 `audioBuffer.getChannelData(0)`，即单通道数据。

### Code patterns

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:296` 初始化默认 `STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime`，`STEPFUN_REALTIME_INPUT_AUDIO_FORMAT=pcm16`，`STEPFUN_REALTIME_OUTPUT_AUDIO_FORMAT=pcm16`，输出采样率默认 24000。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:1028` 连接 upstream 后立即通过 `build_stepfun_session_update_payload()` 发送 `session.update`。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:1037` `_build_stepfun_session_config()` 将当前 handler/profile 的 `input_audio_format`、`output_audio_format`、transcription、instructions、tools 写入 session config。
- `backend/src/training_runtime/stepfun_transport.py:93` `build_stepfun_session_update_payload()` 将 `modalities`、`voice`、`temperature`、`input_audio_format`、`output_audio_format`、`turn_detection` 放进 `session.update`。
- `backend/src/sales_bot/websocket/stepfun_realtime_policy.py:1113` JSON `audio_chunk` 路径不解码、不校验、不转码，直接把前端 `data.audio` 作为 `input_audio_buffer.append.audio` 发送给 StepFun。
- `backend/src/sales_bot/websocket/stepfun_realtime_policy.py:1131` JSON `audio_end` 触发 `_commit_and_respond()`。
- `backend/src/sales_bot/websocket/stepfun_realtime_policy.py:1275` 二进制帧路径把首字节后的 payload 视为 PCM16 原始字节，Base64 后发送 `input_audio_buffer.append.audio`，并记录 PCM16 质量统计。
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py:207` `_commit_and_respond()` 先发送 `input_audio_buffer.commit`，清掉本地缓冲后调度响应。
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py:684` `_create_response()` 发送 `response.create`，默认 `response.modalities=["audio","text"]`，必要时附加 turn instructions。
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py:2325` upstream error 默认被转发为 `[STEPFUN_API_ERROR]`，消息体来自 StepFun `error.message`。
- `web/src/hooks/use-audio-recorder.ts:155` 前端录音默认 `targetSampleRate = 24000`，bufferSize 1024。
- `web/src/hooks/use-audio-recorder.ts:390` 前端真实录音路径会重采样到目标采样率，Float32 转 Int16Array PCM；有 binary 回调时直接交给二进制发送。
- `web/src/hooks/use-audio-recorder.ts:553` 浏览器麦克风请求单声道 `channelCount: 1`，AudioContext 采样率用于重采样来源。
- `web/src/hooks/use-practice-websocket.ts:86` 前端声明 realtime input sample rate 为 24000。
- `web/src/hooks/use-practice-websocket.ts:558` 首选发送二进制 PCM16 帧；backpressure/legacy 下才转 Base64 JSON。
- `web/tests/e2e/newcomer-training-closed-loop.spec.ts:1741` real provider E2E 直接发送 `{"type":"audio_chunk","data":{"audio":"AAAA"}}`，随后发送 `audio_end`。
- 本次确认命令 `python3 -c "import base64; data=base64.b64decode('AAAA'); print(len(data), data.hex(), len(data)%2)"` 输出 `3 000000 1`；即 `"AAAA"` 解码后是 3 字节全零，字节数为奇数。

### Root cause hypotheses, ranked

1. **最高概率：real provider E2E 的测试音频不是有效 PCM16 音频。** 官方要求 `input_audio_buffer.append.audio` 是会话 `input_audio_format` 指定格式的 Base64 音频字节；当前会话声明 `pcm16`。E2E 发送的 `"AAAA"` 解码后只有 3 个零字节，既不是完整的 16-bit sample 序列，也太短且全静音。这与 StepFun 报 `invalid audio, check your audio format` 高度吻合。
2. **高概率：测试绕过了真实前端录音链路。** 真实前端会将麦克风单声道音频重采样到 24000Hz 并转 PCM16，再用二进制帧发送；E2E 手写 JSON `audio_chunk`，后端 JSON 路径没有校验或转码，直接转发给 StepFun。因此真实 provider E2E 应优先改测试音频生成，而不是先改生产服务端声明。
3. **中概率：服务端缺少 PCM16 输入防御校验，导致错误延迟到 provider 才暴露。** 即使主要问题是测试数据，后端在 `input_audio_format=pcm16` 时可以在 JSON 路径 decode Base64 并检查偶数字节、最小时长、非全零/RMS 下限，用本地 typed error 提前失败；这不是必须的转码，但能让失败更可诊断。
4. **低到中概率：VAD/commit/response 顺序与当前测试音频组合放大了问题。** 官方模型页强调 ServerVAD 可自动触发推理；开发指南说禁用 VAD 时才必须手动 `commit` + `response.create`。当前 handler 在 `audio_end` 后总是 commit 并延迟 create response。若音频有效，这条路径不应直接造成 `invalid audio`；但在 3 字节静音输入下，commit 会把坏缓冲提交给 StepFun，从而稳定触发错误。
5. **低概率：`input_audio_format`/`output_audio_format` 声明值错误。** 当前默认是 `pcm16`，官方当前仅支持 `pcm16`。若环境或后台 profile 把它改成 g711/opus/wav/mp3，将违反 StepFun 文档；但从当前默认和 real provider E2E 看，不是首要根因。

### Recommended minimal fix

- **先改 real provider E2E 测试音频生成。** 将 `web/tests/e2e/newcomer-training-closed-loop.spec.ts:1741` 的 `"AAAA"` 替换为有效的 raw PCM16 little-endian、单声道、建议 24000Hz、至少 0.5-1.0 秒的非全零音频，并按 20-100ms 块发送。不要把 WAV 容器头一起 Base64 后发给 `append`，除非服务端明确新增 WAV 解包/转码。
- 最小可接受做法：在 Playwright `page.evaluate` 中生成 `Int16Array` PCM 样本，用二进制帧模拟真实前端 `BINARY_AUDIO_CHUNK` 路径；或用一个真实人声 fixture，在测试内转换为 raw PCM16 Base64 后通过 JSON `audio_chunk` 分块发送。
- **服务端不需要为了这个错误优先做转码。** 生产前端已经按 24000Hz/PCM16/单声道发送；服务端应保持声明 `pcm16`。若未来要支持 WAV、Opus、G.711 或浏览器 MediaRecorder 输出，才需要新增明确的输入格式协商和服务端转码层。
- 建议追加一个后端/前端测试保护：断言 real-provider smoke 生成的 Base64 解码后 `len(bytes) % 2 == 0`、字节数达到预期时长、RMS/peak 不为 0，并且没有 WAV `RIFF` 头。

### Commands / evidence to verify next

- 证明当前测试 payload 无效：
  - `python3 -c "import base64; data=base64.b64decode('AAAA'); print(len(data), data.hex(), len(data)%2)"`
  - 期望当前输出：`3 000000 1`，说明不是完整 PCM16 sample 序列。
- 生成/检查有效测试 payload 后应验证：
  - `python3 - <<'PY' ... PY`：解码测试 Base64，断言偶数字节、`bytes == sample_rate * seconds * 2`、RMS 大于阈值、前 4 字节不是 `RIFF`。
- 真实 provider E2E 验证命令（不要输出密钥）：
  - `cd web && SMOKE_REUSE_EXISTING_STACK=1 PHASE4_E2E_PROVIDER=stepfun_realtime NEWCOMER_E2E_EXPECT_REAL_PROVIDER=1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "realtime roleplay starts from active path" --workers=1`
- 如果加服务端防御校验，补跑：
  - `cd backend && pytest tests/unit/test_stepfun_realtime_handler.py -k "audio"`
  - `cd web && npx vitest run src/hooks/use-audio-recorder.test.ts src/hooks/use-practice-websocket.test.ts`

### Related specs

- `.trellis/spec/backend/realtime-roleplay-v1.md` — realtime runtime 不应迁移到 `sales_trainer`；新人训练只启动 sales realtime session。
- `.trellis/spec/backend/error-handling.md` — provider 的 terminal format error 应显式呈现，不应当被无限重连掩盖。
- `.trellis/spec/backend/quality-guidelines.md` — 单元测试 mock 外部 provider，真实 provider gate 通过显式环境变量启用。
- `backend/src/sales_trainer/AGENTS.md` — 不要在 `sales_trainer` 内构造新的 WebSocket runtime；只通过 start service 进入 `sales_bot` runtime。
- `backend/src/sales_bot/AGENTS.md` — 修改 binary audio frame 或 StepFun runtime 时保持协议兼容。

## Caveats / Not Found

- `python3 ./.trellis/scripts/task.py current --source` 返回 `Current task: (none)`；本研究按用户消息中明确给出的 `.trellis/tasks/07-02-stepfun-realtime-stepaudio-2-5-realtime` 写入。
- StepFun 中文官方文档没有明确写出输入 PCM16 的采样率、帧大小、最小时长，也没有列出 g711/opus；只明确当前 `input_audio_format`/`output_audio_format` 支持 `pcm16`、`append.audio` 是指定格式的 Base64 字节、单块最大 15 MB。24kHz/单声道是当前代码和前端实现的约定，也与 output sample rate 默认值一致，但仍需真实 provider 验证。
- 本次只读研究，未修改代码，未运行真实 provider E2E，也未接触或输出任何密钥。
- 官方 API 公共参数包含 `event_id`，示例均带 `event_id`；当前代码发送事件未统一带 `event_id`。这更可能导致请求参数类错误，不符合本次 `invalid audio` 文案，故未列为主要根因。
