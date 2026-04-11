# M017: Realtime contract 与 concurrency proof 收口

## Vision
围绕 session lifecycle、practice websocket、上传并发与资源竞争建立明确的事实线和修复边界，把高风险但证据不足的问题从表面 patch 转成可证伪、可维护的 contract。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | S01 | high | — | ⬜ | pause/resume/end 并发行为有可重复证明，状态收敛策略清晰。 |
| S02 | Practice WebSocket 复杂度与重连策略收口 | high | S01 | ⬜ | practice websocket 的 reconnect/backpressure/interrupt contract 更清晰，测试保持通过。 |
| S03 | 文件上传 / 资源竞争 / 分布式锁风险 discovery | medium | S01 | ⬜ | presentation upload / replace 等并发风险点被列成可证据化清单，并给出下一步建议。 |
