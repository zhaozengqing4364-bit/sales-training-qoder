# M016: Auth / API / admin security contract hardening

## Vision
把 password reset、鉴权模式、错误响应、RBAC、日志脱敏从“能用”升到“可依赖”，让认证与错误表面成为后续治理和扩展的稳定基线。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | S01 | high | — | ✅ | forgot/reset 走正式 token 持久化与 lifecycle contract，现有登录兼容路径保持可证明。 |
| S02 | S02 | high | — | ✅ | audit 命中的高频 API surface 返回统一错误 shape，frontend client 不再 page-local 猜测。 |
| S03 | S03 | high | — | ✅ | admin 高风险接口有权限证明，日志敏感字段脱敏规则落到高风险出口。 |
