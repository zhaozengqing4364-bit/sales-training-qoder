# M016: 

## Vision
把 password reset、鉴权模式、错误响应、RBAC、日志脱敏从“能用”升到“可依赖”，让认证与错误表面成为后续治理和扩展的稳定基线。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Password reset / auth backend 正式化 | high | — | ⬜ | forgot/reset 走正式 token 持久化与 lifecycle contract，现有登录兼容路径保持可证明 |
| S02 | API 错误契约与异常分类收口 | high | S01 | ⬜ | audit 命中的高频 API surface 返回统一错误 shape，frontend client 不再 page-local 猜测 |
| S03 | RBAC、敏感日志与 admin 安全面 audit | high | S02 | ⬜ | admin 高风险接口有权限证明，日志敏感字段脱敏规则落到高风险出口 |
