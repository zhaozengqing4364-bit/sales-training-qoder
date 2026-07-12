# Implementation notes

## Safety

- Never copy the credential into this file, tracked source, tests, evidence, logs, commands or responses.
- Preserve the unrelated dirty readiness plan.

## Deviations

- 真实 Provider 首轮暴露 `server_vad` 与 client-driven `audio_end` commit 冲突；新增显式
  `STEPFUN_REALTIME_TURN_DETECTION_MODE=manual_commit`，保留 `policy` 回滚。
- 真实 StepAudio 2.5 pending audio item 的 transcript 为空字符串；codec 原先将其误判为
  `INVALID_EVENT`。新增真实形状回归测试，并仅在 transcript 非空时投影顶层字段。
- `.kiro/steering/backend-principles.md` 在当前仓库不存在；本次按 `backend/AGENTS.md` 与
  `.trellis/spec/backend/` 的现有规范执行。
