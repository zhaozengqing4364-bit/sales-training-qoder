# StepFun 官方生产合同核对

日期：2026-07-12 UTC

## 官方事实

- Realtime API：`wss://api.stepfun.com/v1/realtime`
- 鉴权：WebSocket `Authorization: Bearer STEP_API_KEY`
- 模型 query：`stepaudio-2.5-realtime`
- 交互：WebSocket 长连接，服务端管理上下文，支持内置 ASR、VAD、Tool Call 与双向音频。
- `session.update`：modalities 固定 text/audio；voice 建连后不可更改；输入输出格式当前为 PCM16。
- Server VAD 可配置 prefix padding、silence duration 与 energy threshold。
- 官方开发指南明确：`input_audio_buffer.commit` 与 `response.create` 是禁用 VAD 后的手动提交事件；
  Server VAD 开启时由服务端检测并提交，不能再走手动 commit。
- 错误事件不会当然终止 session；客户端仍须按 error category、连接状态和 retry policy 处理。

## 与仓库映射

- Endpoint/model：`training_runtime.stepfun_transport.build_stepfun_realtime_endpoint` 会清理旧 model query，
  拒绝 userinfo 和敏感 query，再添加当前 model。
- Credential：`StepFunTransport.connect` 通过 Authorization header 发送；repr/diagnostics 不输出 key。
- Session：`build_stepfun_session_update_payload` 统一生成 modalities/voice/format/VAD/tools。
- 浏览器协议显式发送 `audio_end`，因此生产环境使用 `manual_commit` 并投影
  `turn_detection=null`；`policy` 保留 Server VAD 回滚。
- 真实 2.5 上游会先发送带空 transcript 的 pending `conversation.item.created`，codec 必须把空值
  视为“尚未转录”，而不是协议错误。
- 错误与恢复：`RealtimeProviderError` 使用 closed category/reason；shared handler 有 generation rollover、
  timeout、retry、backpressure 与 stale epoch 防护。
- 验证：`CRITICAL_GATE_MODE=newcomer-real-provider` 只跑真实 Sales realtime 关键链并生成脱敏 JSON evidence。

## 官方资料

- https://platform.stepfun.com/docs/zh/api-reference/realtime/chat
- https://platform.stepfun.com/docs/zh/guides/models/stepaudio-2.5-realtime
- https://platform.stepfun.com/docs/zh/guides/developer/realtime
- https://platform.stepfun.com/docs/zh/guides/pricing/details
