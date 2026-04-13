# M020: Security / multi-instance runtime / recovery hardening

## Vision
把现有‘单机可跑、兼容路径较多’的 auth/runtime/ops 基座收口成更可信的生产底座：cookie 与 websocket auth 边界清楚，日志/系统日志对敏感信息有统一暴露策略，SessionManager/SessionStateService 在多实例与重启语义上不再依赖隐性假设，M018 的恢复基线升级为可执行 drill。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Auth transport hardening | high | — | ⬜ | After this: auth/cookie/websocket 的 transport policy 会落成真实代码与 focused tests，后续不再靠‘兼容默认值’猜测安全边界。 |
| S02 | Sensitive log 与 admin observability redaction 收口 | medium | S01 | ⬜ | After this: support/admin 能看到对排障有用但不泄密的日志与错误上下文，敏感字段不会在 logger 或 admin logs page 原样外露。 |
| S03 | Multi-instance session state 与 reconnect authority 收口 | high | S01, S02 | ⬜ | After this: runtime connection visibility、session snapshot、reconnect/drain 语义对单实例和多实例都清晰，后续扩容不再完全依赖进程内假设。 |
| S04 | Recovery drill automation 与部署指导收口 | medium | S01, S02, S03 | ⬜ | After this: M018 的 backup/recovery baseline 会升级成可执行 drill/script，能针对 hardened auth/runtime/observability seams 做真实恢复验证。 |
