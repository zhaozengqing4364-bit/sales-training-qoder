# Design artifact audit

日期：2026-07-12 UTC

## 总体结论

方向成立，硬错误 0，建议项 0。PRD 不引入新 Provider 或协议，只把现有、已测试的 StepFun Port 从
placeholder credential 切到官方生产配置，并调用仓库已有真实门禁。

## 七维证据

1. **参照真实性**：`StepFunRealtimeProvider`、`StepFunEventCodec`、真实 Provider gate 和
   `stepaudio-2.5-realtime` prereq tests 均真实存在。
2. **依赖方向**：只修改 ignored environment secret 和 Trellis 证据；不新增包 import 或 policy edge。
3. **字段完整性**：URL/model/voice/PCM16/sample rate/transcription/recovery variables 均有现有读取点；
   model inline comment 会被 prereq 规范化测试覆盖，生产值明确要求无 comment。
4. **事务/IO**：真实 WebSocket IO 不进入 DB transaction；现有 E2E 在 session/bootstrap 后单独建连。
5. **调用语义**：Sales/Presentation 仍由 runtime selection、RuntimeGate 和 Provider Port 进入同一链路；
   credential 不改变 scenario、Grounding 或 report authority。
6. **测试影响**：静态 prereq/transport/codec tests 不访问上游；仅专用 opt-in gate 使用真实 credential。
7. **内部一致性**：PRD、官方 research、acceptance 和现有 command 使用相同 endpoint/model/变量名。

## 安全确认

- credential 不进入 tracked artifact、命令参数、environment dump 或 evidence。
- `backend/.env` 已被 Git ignore，权限为 `0600`。
- 上游失败只记录 closed classification/HTTP status，不复制 Authorization 或原始敏感 URL。
